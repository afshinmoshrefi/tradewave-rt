"""The workspace: Anne-Marie's tools (teach, answers, insights, schedule,
knowledge, feed) + the operator-only operations room."""
from datetime import datetime, timedelta, timezone

from flask import (Blueprint, flash, redirect, render_template, request, url_for)

from .extensions import db
from .marketdata import ET
from .models import Appearance, KnowledgeEntry, Post
from .rag import index as kb_index, rebuild_index
from .security import admin_required, current_user, operator_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def dashboard():
    """Role-aware front door: the operator lands in Operations (his room);
    Anne-Marie lands in her workspace. The operator can still open her
    workspace explicitly via ?workspace=1 (he runs her tools too)."""
    from .models import ChatMessage
    if current_user().is_admin and not request.args.get("workspace"):
        return redirect(url_for("admin.ops"))
    return render_template(
        "admin/dashboard.html",
        kb_total=KnowledgeEntry.query.count(),
        kb_published=KnowledgeEntry.query.filter_by(published=True).count(),
        post_total=Post.query.count(),
        index_size=kb_index.size,
        review_open=ChatMessage.query.filter(ChatMessage.rating <= -1,
                                             ChatMessage.reviewed.is_(False)).count(),
    )


# ---------- Schedule (her appearances - the ONLY source the coach cites) ----
@bp.route("/schedule", methods=["GET", "POST"])
@admin_required
def schedule():
    if request.method == "POST":
        try:
            starts_et = datetime.strptime(
                f"{request.form['date']} {request.form['time']}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=ET)
        except (KeyError, ValueError):
            flash("Date and time are required (ET).", "warn")
            return redirect(url_for("admin.schedule"))
        db.session.add(Appearance(
            title=(request.form.get("title") or "Anne-Marie live").strip(),
            where=(request.form.get("where") or "Discord").strip(),
            starts_at=starts_et.astimezone(timezone.utc).replace(tzinfo=None),
            note=(request.form.get("note") or "").strip()))
        db.session.commit()
        flash("Scheduled. Members see it on Today, and the coach can mention it.", "ok")
        return redirect(url_for("admin.schedule"))
    upcoming = (Appearance.query
                .filter(Appearance.starts_at >= datetime.utcnow() - timedelta(hours=3))
                .order_by(Appearance.starts_at).all())
    past = (Appearance.query
            .filter(Appearance.starts_at < datetime.utcnow() - timedelta(hours=3))
            .order_by(Appearance.starts_at.desc()).limit(10).all())
    return render_template("admin/schedule.html", upcoming=upcoming, past=past, ET=ET)


@bp.route("/schedule/<int:appearance_id>/delete", methods=["POST"])
@admin_required
def schedule_delete(appearance_id):
    a = Appearance.query.get_or_404(appearance_id)
    db.session.delete(a)
    db.session.commit()
    flash("Removed.", "ok")
    return redirect(url_for("admin.schedule"))


# ---------- Operations (site operator only) ----------
@bp.route("/ops")
@operator_required
def ops():
    from .models import (ChatMessage, DayMap, MarketCandle, NotificationLog,
                         Subscription, User, UserProfile)
    from .marketdata import latest_session
    session = latest_session()
    candles = (MarketCandle.query.filter_by(session_date=session)
               .order_by(MarketCandle.instrument, MarketCandle.window).all())
    maps = DayMap.query.filter_by(session_date=session).all()
    week_ago = datetime.utcnow() - timedelta(days=7)
    drift = (MarketCandle.query
             .filter(MarketCandle.recon_drift.isnot(None),
                     MarketCandle.recon_drift > 0.5,
                     MarketCandle.captured_at >= week_ago)
             .order_by(MarketCandle.captured_at.desc()).limit(10).all())
    # People & roles: staff always shown (a handful), everyone else via search,
    # newest signups by default - the list never grows with the member base.
    q = (request.args.get("q") or "").strip()
    staff = (User.query.filter(User.role.in_(("admin", "partner")))
             .order_by(User.role, User.created_at).all())
    results, result_total, recent = [], 0, []
    if q:
        like = f"%{q}%"
        base = User.query.filter(db.or_(User.email.ilike(like),
                                        User.display_name.ilike(like)))
        result_total = base.count()
        results = base.order_by(User.created_at.desc()).limit(20).all()
    else:
        recent = (User.query.filter(User.role == "member")
                  .order_by(User.created_at.desc()).limit(8).all())
    return render_template(
        "admin/ops.html", session=session, candles=candles, maps=maps, drift=drift,
        q=q, staff=staff, results=results, result_total=result_total, recent=recent,
        users_total=User.query.count(),
        intakes_done=UserProfile.query.filter_by(intake_done=True).count(),
        subs_active=Subscription.query.filter(
            Subscription.status.in_(Subscription.ACTIVE_STATUSES)).count(),
        msgs_24h=ChatMessage.query.filter(
            ChatMessage.created_at >= datetime.utcnow() - timedelta(hours=24)).count(),
        recent_sends=NotificationLog.query.order_by(
            NotificationLog.sent_at.desc()).limit(10).all())


@bp.route("/ops/users/<int:user_id>/role", methods=["POST"])
@operator_required
def ops_set_role(user_id):
    """The operator assigns who can see what. This is THE mechanism for giving
    Anne-Marie her workspace once she signs in with her real email - roles live
    in this app's own database, never in WorkOS."""
    from .models import User
    user = User.query.get_or_404(user_id)
    if user.id == current_user().id:
        flash("You can't change your own role - that's what keeps you from locking yourself out.", "warn")
        return redirect(url_for("admin.ops"))
    role = (request.form.get("role") or "").strip()
    if role not in ("member", "partner", "admin"):
        flash("Pick a role first.", "warn")
        return redirect(url_for("admin.ops"))
    user.role = role
    db.session.commit()
    labels = {"member": "Member", "partner": "Partner - the Anne-Marie workspace",
              "admin": "Site operator - everything, including this page"}
    flash(f"{user.email} is now: {labels[role]}.", "ok")
    return redirect(url_for("admin.ops", q=request.form.get("q") or None,
                            _anchor="people"))


# ---------- Teach the coach (her knowledge capture) ----------
@bp.route("/teach", methods=["GET", "POST"])
@admin_required
def teach():
    """She talks (or types), AI drafts the lesson keeping her phrasing, one tap
    publishes it as her words (pre-approved per Afshin's rule). The page has a
    browser-dictation mic so capture is voice-first with zero pipeline.
    Arriving with ?flag_id=N pre-fills the topic from a queued member question
    and marks that question handled on publish."""
    from .models import ChatMessage
    draft = None
    topic = request.form.get("topic", "")
    flag_id = request.form.get("flag_id") or request.args.get("flag_id") or ""
    if request.method == "GET" and flag_id:
        flagged = db.session.get(ChatMessage, int(flag_id))
        if flagged:
            q = (ChatMessage.query
                 .filter(ChatMessage.thread_id == flagged.thread_id,
                         ChatMessage.id < flagged.id, ChatMessage.role == "user")
                 .order_by(ChatMessage.id.desc()).first())
            if q:
                from .privacy import sanitize_for_admin
                if q.sanitized is None:
                    q.sanitized = sanitize_for_admin(q.content)
                    db.session.commit()
                topic = q.sanitized[:300]
    if request.method == "POST":
        answer = (request.form.get("answer") or "").strip()
        if not answer:
            flash("Capture her answer first.", "warn")
        else:
            draft = _draft_lesson(topic, answer)
            if draft is None:
                flash("Drafting failed - try again.", "warn")
    return render_template("admin/teach.html", draft=draft, topic=topic,
                           flag_id=flag_id,
                           answer=request.form.get("answer", ""))


@bp.route("/teach/publish", methods=["POST"])
@admin_required
def teach_publish():
    from .models import ChatMessage, DeferredQuestion, User
    flag_id = request.form.get("flag_id")
    asker = None
    if flag_id:
        flagged = db.session.get(ChatMessage, int(flag_id))
        if flagged:
            flagged.reviewed = True  # her answer closes the queued question
            dq = (DeferredQuestion.query
                  .filter_by(message_id=flagged.id, answered=False).first())
            if dq:
                asker = dq  # close the loop back to the member who asked
    e = KnowledgeEntry(
        title=(request.form.get("title") or "Untitled").strip(),
        category=(request.form.get("category") or "method").strip(),
        content=request.form.get("content") or "",
        stage=int(request.form.get("stage") or 0),
        kind="lesson" if int(request.form.get("stage") or 0) else "reference",
        provenance="her_words",
        status="approved",
        source_quote=request.form.get("source_quote") or "",
        source="Teach-the-coach session",
        published=True,
    )
    db.session.add(e)
    db.session.commit()
    rebuild_index()
    # Close the deferral loop: tell the member who asked that she answered.
    if asker is not None:
        from datetime import datetime
        asker.answered = True
        asker.answered_entry_id = e.id
        asker.answered_at = datetime.utcnow()
        db.session.commit()
        try:
            from .notify import send_answer_ready
            # Only mark notified if the send ACTUALLY went out - send_answer_ready
            # returns False (no raise) when email is unconfigured/capped, so a failed
            # send stays retryable instead of being silently recorded as closed.
            if send_answer_ready(db.session.get(User, asker.user_id), e.title):
                asker.notified = True
                db.session.commit()
        except Exception:
            from flask import current_app
            current_app.logger.exception("answer-ready notify failed")
    flash(f"Live. Every member's coach knows “{e.title}” now.", "ok")
    return redirect(url_for("admin.teach"))


def _draft_lesson(topic, answer):
    """Haiku drafts a lesson from her spoken answer, preserving her phrasing."""
    from flask import current_app
    api_key = current_app.config.get("ANTHROPIC_TOKEN")
    if not api_key:
        return {"title": topic or "New lesson", "category": "method", "stage": 0,
                "content": answer, "source_quote": answer}
    try:
        import json as _json
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=current_app.config.get("CLAUDE_MODEL", "claude-haiku-4-5"),
            max_tokens=900,
            messages=[{"role": "user", "content":
                       "Anne-Marie Baiynd (intraday futures educator) just answered a "
                       "question, transcribed below. Turn it into ONE knowledge-base "
                       "lesson for her AI coach. Keep HER phrasing wherever possible - "
                       "her voice is the product; clean up only transcription stumbles. "
                       "No day-specific prices or dates (generalize them). No em dashes. "
                       f"\n\nTOPIC (may be empty): {topic}\n\nHER ANSWER:\n{answer}"}],
            output_config={"format": {"type": "json_schema", "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "category": {"type": "string",
                                 "enum": ["method", "psychology", "rules", "glossary"]},
                    "stage": {"type": "integer",
                              "description": "Curriculum stage 1-5, or 0 for reference. "
                              "1=read the day, 2=levels, 3=permission/entries, "
                              "4=manage the trade, 5=psychology"},
                    "content": {"type": "string"},
                },
                "required": ["title", "category", "stage", "content"],
                "additionalProperties": False,
            }}})
        text = next(b.text for b in resp.content if getattr(b, "type", "") == "text")
        data = _json.loads(text)
        data["content"] = data["content"].replace(chr(0x2014), " - ")
        data["source_quote"] = answer
        return data
    except Exception:
        from flask import current_app
        current_app.logger.exception("teach draft failed")
        return None


# ---------- Coach review queue (the correction loop) ----------
@bp.route("/reviews")
@admin_required
def reviews():
    """Thumbs-down answers, anonymized, with the question that prompted them.
    This is how Anne-Marie keeps the coach sounding like her: spot a wrong or
    off-voice answer, fix the knowledge entry behind it."""
    from .models import ChatMessage
    from .privacy import sanitize_for_admin
    flagged = (ChatMessage.query.filter(ChatMessage.rating <= -1,
                                        ChatMessage.reviewed.is_(False))
               .order_by(ChatMessage.created_at.desc()).limit(50).all())
    items = []
    for m in flagged:
        question = (ChatMessage.query
                    .filter(ChatMessage.thread_id == m.thread_id,
                            ChatMessage.id < m.id, ChatMessage.role == "user")
                    .order_by(ChatMessage.id.desc()).first())
        # Member text is anonymized before it reaches this screen (names,
        # amounts, account details). Computed once, cached on the row.
        if question and question.sanitized is None:
            question.sanitized = sanitize_for_admin(question.content)
            db.session.commit()
        items.append({"msg": m,
                      "question_text": question.sanitized if question else None,
                      "kind": "couldn't answer" if m.rating == -2 else "member flagged",
                      "member": f"Member {m.thread.user_id}"})
    return render_template("admin/reviews.html", items=items)


@bp.route("/reviews/<int:message_id>/handled", methods=["POST"])
@admin_required
def review_handled(message_id):
    from .models import ChatMessage
    msg = ChatMessage.query.get_or_404(message_id)
    msg.reviewed = True
    db.session.commit()
    flash("Marked handled.", "ok")
    return redirect(url_for("admin.reviews"))


# ---------- Knowledge ----------
@bp.route("/knowledge")
@admin_required
def knowledge_list():
    entries = (KnowledgeEntry.query
               .order_by(KnowledgeEntry.category, KnowledgeEntry.updated_at.desc()).all())
    return render_template("admin/knowledge_list.html", entries=entries)


@bp.route("/knowledge/new", methods=["GET", "POST"])
@admin_required
def knowledge_new():
    if request.method == "POST":
        e = _save_knowledge(KnowledgeEntry())
        flash(f"Saved “{e.title}”. The coach just learned it.", "ok")
        return redirect(url_for("admin.knowledge_list"))
    return render_template("admin/knowledge_edit.html", entry=None,
                           categories=KnowledgeEntry.CATEGORIES)


@bp.route("/knowledge/<int:entry_id>/edit", methods=["GET", "POST"])
@admin_required
def knowledge_edit(entry_id):
    entry = KnowledgeEntry.query.get_or_404(entry_id)
    if request.method == "POST":
        _save_knowledge(entry)
        flash("Updated - coach reindexed.", "ok")
        return redirect(url_for("admin.knowledge_list"))
    return render_template("admin/knowledge_edit.html", entry=entry,
                           categories=KnowledgeEntry.CATEGORIES)


@bp.route("/knowledge/<int:entry_id>/toggle", methods=["POST"])
@admin_required
def knowledge_toggle(entry_id):
    entry = KnowledgeEntry.query.get_or_404(entry_id)
    entry.published = not entry.published
    db.session.commit()
    rebuild_index()
    flash(("Published" if entry.published else "Unpublished") + f" “{entry.title}”.", "ok")
    return redirect(url_for("admin.knowledge_list"))


@bp.route("/knowledge/<int:entry_id>/delete", methods=["POST"])
@admin_required
def knowledge_delete(entry_id):
    from .models import DeferredQuestion, UserLesson
    entry = KnowledgeEntry.query.get_or_404(entry_id)
    # Foreign keys are enforced now, so detach the two tables that reference this
    # entry before deleting it. A deferred question keeps its link nulled (preserve
    # the member's question; it just reverts to needing an answer); lesson-progress
    # rows for a lesson that no longer exists are dropped.
    DeferredQuestion.query.filter_by(answered_entry_id=entry_id).update(
        {"answered_entry_id": None, "answered": False}, synchronize_session=False)
    UserLesson.query.filter_by(entry_id=entry_id).delete(synchronize_session=False)
    db.session.delete(entry)
    db.session.commit()
    rebuild_index()
    flash("Deleted.", "ok")
    return redirect(url_for("admin.knowledge_list"))


def _save_knowledge(entry):
    entry.title = (request.form.get("title") or "Untitled").strip()
    cat = (request.form.get("category") or "method").strip()
    entry.category = cat if cat in KnowledgeEntry.CATEGORIES else "method"
    entry.content = request.form.get("content") or ""
    entry.source = (request.form.get("source") or "").strip()
    prov = (request.form.get("provenance") or "team_inference").strip()
    entry.provenance = prov if prov in KnowledgeEntry.PROVENANCES else "team_inference"
    # Admin-typed entries publish directly (Afshin operates the tool); future
    # AI-drafted flows set status='draft' explicitly and wait for approval.
    entry.status = "approved"
    entry.published = bool(request.form.get("published"))
    if entry.id is None:
        db.session.add(entry)
    db.session.commit()
    rebuild_index()
    return entry


# ---------- Today's insight (the FROM ANNE-MARIE slot) ----------
@bp.route("/insight", methods=["POST"])
@admin_required
def insight():
    """Her 2-minute daily capture: one box, one button. Lands on Today instantly,
    archives to the feed, and flows into the coach's TODAY context."""
    text = (request.form.get("text") or "").strip()
    if not text:
        flash("Write a line first.", "warn")
        return redirect(url_for("admin.dashboard"))
    from datetime import datetime
    from .marketdata import ET
    post = Post(title=f"Today's insight - {datetime.now(ET).strftime('%b %-d')}",
                kind="insight", body=text[:4000], published=True,
                author_id=current_user().id)
    db.session.add(post)
    db.session.commit()
    flash("Published - it's on every member's Today page now.", "ok")
    return redirect(url_for("admin.dashboard"))


# ---------- Posts (member feed) ----------
@bp.route("/posts")
@admin_required
def posts_list():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template("admin/posts_list.html", posts=posts)


@bp.route("/posts/new", methods=["GET", "POST"])
@admin_required
def posts_new():
    if request.method == "POST":
        _save_post(Post())
        flash("Posted to the member feed.", "ok")
        return redirect(url_for("admin.posts_list"))
    return render_template("admin/post_edit.html", post=None)


@bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@admin_required
def posts_edit(post_id):
    post = Post.query.get_or_404(post_id)
    if request.method == "POST":
        _save_post(post)
        flash("Updated.", "ok")
        return redirect(url_for("admin.posts_list"))
    return render_template("admin/post_edit.html", post=post)


@bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@admin_required
def posts_delete(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash("Deleted.", "ok")
    return redirect(url_for("admin.posts_list"))


def _save_post(post):
    post.title = (request.form.get("title") or "Untitled").strip()
    post.body = request.form.get("body") or ""
    post.published = bool(request.form.get("published"))
    if post.id is None:
        post.author_id = current_user().id
        db.session.add(post)
    db.session.commit()
    return post
