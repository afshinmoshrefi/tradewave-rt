"""The 'Anne-Marie' coach: chat UI + streaming message API + ratings."""
import json

from flask import Blueprint, Response, jsonify, render_template, request, stream_with_context

from .extensions import db
from .llm import generate_reply, stream_reply
from .models import ChatMessage, ChatThread
from .security import current_user, disclaimer_required

bp = Blueprint("chat", __name__)

GREETING = (
    "Hi - I'm your AI coach, trained on Anne-Marie's method and trading psychology. "
    "I'm not Anne-Marie herself, and I won't tell you what to trade - but I'll teach you "
    "how she thinks and help your discipline. Ask me about a setup, a rule, or what to do "
    "when fear or FOMO kicks in. Where do you want to start?"
)


def _get_or_create_thread(user, thread_id):
    if thread_id:
        thread = ChatThread.query.filter_by(id=thread_id, user_id=user.id).first()
        if thread:
            return thread
    thread = ChatThread(user_id=user.id, title="Coaching session")
    db.session.add(thread)
    db.session.commit()
    return thread


PAGE_SIZE = 30
DAILY_CHAT_CAP = 60  # generous for real members, a wall for abuse/scrapers


def _over_daily_cap(user):
    from datetime import datetime, time, timedelta, timezone
    from .marketdata import ET
    midnight_et = datetime.combine(datetime.now(ET).date(), time.min, tzinfo=ET)
    since = midnight_et.astimezone(timezone.utc).replace(tzinfo=None)
    n = (ChatMessage.query.join(ChatThread)
         .filter(ChatThread.user_id == user.id, ChatMessage.role == "user",
                 ChatMessage.created_at >= since).count())
    return n >= DAILY_CHAT_CAP


@bp.route("/app/coach")
@disclaimer_required
def coach():
    user = current_user()
    thread = (ChatThread.query.filter_by(user_id=user.id)
              .order_by(ChatThread.created_at.desc()).first())
    history, has_earlier = [], False
    if thread:
        recent = (ChatMessage.query.filter_by(thread_id=thread.id)
                  .order_by(ChatMessage.id.desc()).limit(PAGE_SIZE + 1).all())
        has_earlier = len(recent) > PAGE_SIZE
        history = list(reversed(recent[:PAGE_SIZE]))
    from .mentor import coach_greeting, touch_active
    greeting = coach_greeting(user) or GREETING  # reads last_active for the lapse line
    touch_active(user)                            # ...then record this visit
    # Clear the 'debrief your trade' nudge ONLY when they actually arrive to debrief
    # (via a debrief deep-link), never on a bare coach open - or a rattled trader who
    # opens the coach to vent first would lose the nudge on the exact trade that hurt.
    if "debrief" in (request.args.get("q") or "").lower():
        try:
            from .models import Trade
            Trade.query.filter_by(user_id=user.id, reviewed=False).update({"reviewed": True})
            db.session.commit()
        except Exception:
            db.session.rollback()
    return render_template("app/coach.html", thread=thread, history=history,
                           has_earlier=has_earlier, greeting=greeting)


@bp.route("/app/coach/api/history")
@disclaimer_required
def history_page():
    """Earlier messages, newest-first pagination by id cursor."""
    user = current_user()
    thread = ChatThread.query.filter_by(id=request.args.get("thread_id", 0, int),
                                        user_id=user.id).first()
    if thread is None:
        return jsonify({"messages": [], "has_earlier": False})
    before = request.args.get("before_id", 0, int)
    q = ChatMessage.query.filter_by(thread_id=thread.id)
    if before:
        q = q.filter(ChatMessage.id < before)
    rows = q.order_by(ChatMessage.id.desc()).limit(PAGE_SIZE + 1).all()
    has_earlier = len(rows) > PAGE_SIZE
    rows = list(reversed(rows[:PAGE_SIZE]))
    return jsonify({"has_earlier": has_earlier, "messages": [
        {"id": m.id, "role": m.role, "content": m.content, "rating": m.rating}
        for m in rows]})


@bp.route("/app/coach/api/stream", methods=["POST"])
@disclaimer_required
def stream_message():
    """SSE stream of the coach's reply. Frames: {"t":"delta","text":...} per
    chunk, then {"t":"done", thread_id, message_id, citations}."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"error": "empty message"}), 400
    if _over_daily_cap(user):
        return jsonify({"error": "That's a full day of coaching - the buffet is "
                                 "open again tomorrow."}), 429
    text = text[:4000]

    thread = _get_or_create_thread(user, data.get("thread_id"))
    history = [{"role": m.role, "content": m.content} for m in thread.messages]
    db.session.add(ChatMessage(thread_id=thread.id, role="user", content=text))
    db.session.commit()

    from .mentor import member_context
    from .billing import map_access
    member_ctx = member_context(user)
    gated = map_access(user) == "gated"   # free tier past day 1: read yes, numbers no
    thread_id = thread.id

    def frame(obj):
        return f"data: {json.dumps(obj)}\n\n"

    @stream_with_context
    def generate():
        parts, meta = [], {"citations": [], "used_llm": True}
        try:
            for piece in stream_reply(text, history=history, member_context=member_ctx,
                                      gated=gated):
                if isinstance(piece, dict):
                    meta = piece
                    continue
                parts.append(piece)
                yield frame({"t": "delta", "text": piece})
        except Exception:
            from flask import current_app
            current_app.logger.exception("coach stream failed")
            if not parts:
                parts.append("Sorry - something went wrong on my end. Try that again.")
                yield frame({"t": "delta", "text": parts[0]})
        reply = "".join(parts).strip()
        from .llm import correct_level_typos, enforce_compliance
        reply, fixes = correct_level_typos(reply, text)
        # Runtime compliance backstop. A trip replaces the streamed text on 'done'
        # via the same corrected_text channel used for level repair, so the member
        # ends on the compliant reply and that is what we persist.
        reply, tripped, _ = enforce_compliance(reply)
        deferred = "flagged this for Anne-Marie" in reply
        if fixes:
            from flask import current_app
            current_app.logger.warning("level typo corrected in stream: %s", fixes)
        msg = ChatMessage(thread_id=thread_id, role="assistant", content=reply,
                          used_llm=meta.get("used_llm", True),
                          rating=(-2 if deferred else (-1 if tripped else 0)))
        db.session.add(msg)
        db.session.commit()
        if deferred:  # close-the-loop: record who asked so she can answer them back
            from .models import DeferredQuestion
            db.session.add(DeferredQuestion(user_id=user.id, message_id=msg.id,
                                            question=text[:2000]))
            db.session.commit()
        done = {"t": "done", "thread_id": thread_id, "message_id": msg.id,
                "citations": meta.get("citations", [])}
        if fixes or tripped:
            done["corrected_text"] = reply
        yield frame(done)
        # Post-stream housekeeping: the member already has their reply, so the
        # rolling memory-note update runs here instead of on page load.
        try:
            from .mentor import maybe_update_summary
            maybe_update_summary(user)
        except Exception:
            from flask import current_app
            current_app.logger.exception("post-stream summary update failed")

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.route("/app/coach/api/rate", methods=["POST"])
@disclaimer_required
def rate_message():
    """Thumbs up/down on a coach answer. Down-rated answers land in
    Anne-Marie's review queue - the correction loop that keeps it her."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    if rating not in (-1, 0, 1):
        return jsonify({"error": "rating must be -1, 0, or 1"}), 400
    msg = ChatMessage.query.get(data.get("message_id") or 0)
    if msg is None or msg.role != "assistant" or msg.thread.user_id != user.id:
        return jsonify({"error": "not your message"}), 404
    msg.rating = rating
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/app/coach/api/message", methods=["POST"])
@disclaimer_required
def message():
    user = current_user()
    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"error": "empty message"}), 400
    if _over_daily_cap(user):
        return jsonify({"error": "That's a full day of coaching - the buffet is "
                                 "open again tomorrow."}), 429
    if len(text) > 4000:
        text = text[:4000]

    thread = _get_or_create_thread(user, data.get("thread_id"))

    # Build short history for context (exclude the message we're about to add).
    history = [{"role": m.role, "content": m.content} for m in thread.messages]

    db.session.add(ChatMessage(thread_id=thread.id, role="user", content=text))
    db.session.commit()

    from .mentor import member_context
    from .billing import map_access
    reply, used_llm, citations = generate_reply(
        text, history=history, member_context=member_context(user),
        gated=map_access(user) == "gated")
    # Runtime compliance backstop on the actual reply (under the system prompt).
    from .llm import enforce_compliance
    reply, tripped, _ = enforce_compliance(reply)
    deferred = "flagged this for Anne-Marie" in reply

    amsg = ChatMessage(thread_id=thread.id, role="assistant",
                       content=reply, used_llm=used_llm,
                       rating=(-2 if deferred else (-1 if tripped else 0)))
    db.session.add(amsg)
    db.session.commit()
    if deferred:
        from .models import DeferredQuestion
        db.session.add(DeferredQuestion(user_id=user.id, message_id=amsg.id,
                                        question=text[:2000]))
        db.session.commit()

    return jsonify({
        "reply": reply,
        "thread_id": thread.id,
        "citations": citations,
        "used_llm": used_llm,
    })
