"""The proactive email layer (Resend) - policy in one place.

Standing rules (product/COACH_BLUEPRINT.md, the proactive surface):
- Templates only. No LLM ever writes outbound email - the email is the knock,
  the chat after the click is the conversation.
- TRANSACTIONAL sends (welcome, receipts) are exempt from caps. COACH-VOICE
  sends (morning brief, check-in nudges, re-engagement) obey: max ONE per
  member per day, none 20:00-06:30 ET, none on weekends/market holidays.
- The coach voice never sells. Billing/win-back/upsell mail is NOT sent from
  this module's coach kinds and never will be.
- Every send is ledgered (NotificationLog) with its reason.

Deep links use the ?q= mechanism so a click opens the coach mid-conversation.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from flask import current_app

from .extensions import db
from .marketdata import ET, is_session_day
from .models import NotificationLog

COACH_KINDS = {"morning_brief", "checkin_nudge", "reengagement", "quiz_invite",
               "milestone", "weekend_study"}
# answer_ready is a direct reply to something the member asked - cap- and
# day-exempt (they are waiting for it), like a transactional confirmation.
TRANSACTIONAL_KINDS = {"welcome", "answer_ready"}


def email_enabled():
    return bool(current_app.config.get("RESEND_API_KEY"))


def _allowed(user, kind, allow_closed=False):
    if kind in TRANSACTIONAL_KINDS:
        return True
    now = datetime.now(ET)
    # Most coach mail is session-days only; the weekend touch is the exception
    # (the whole point is to reach members on the days they have time).
    if not allow_closed and not is_session_day(now.date()):
        return False
    if now.hour >= 20 or now.hour < 6 or (now.hour == 6 and now.minute < 30):
        return False
    since = datetime.utcnow() - timedelta(hours=24)
    sent = (NotificationLog.query
            .filter(NotificationLog.user_id == user.id,
                    NotificationLog.kind.in_(COACH_KINDS),
                    NotificationLog.sent_at >= since).count())
    return sent == 0


def send_email(user, kind, subject, html, text="", allow_closed=False):
    """Send one email through Resend, policy-gated and ledgered.
    Returns True if sent, False if skipped (no key, caps, quiet hours)."""
    if not email_enabled() or not user or not user.email:
        return False
    if not _allowed(user, kind, allow_closed=allow_closed):
        current_app.logger.info("email %s to user %s skipped by policy", kind, user.id)
        return False
    payload = {
        "from": current_app.config["EMAIL_FROM"],
        "to": [user.email],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {current_app.config['RESEND_API_KEY']}",
                 "Content-Type": "application/json",
                 # Cloudflare at Resend's edge blocks urllib's default UA (1010)
                 "User-Agent": "tradewave-realtime/1.0"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            json.loads(resp.read().decode())
    except Exception:
        current_app.logger.exception("resend send failed (%s to user %s)", kind, user.id)
        return False
    db.session.add(NotificationLog(user_id=user.id, kind=kind, subject=subject))
    db.session.commit()
    return True


def _frame(title, body_html, cta_url, cta_label, footer_reason):
    """The one shared email shell: dark, simple, one CTA, honest footer."""
    return f"""\
<div style="background:#0d0b14;color:#e8e6f0;font-family:Inter,Arial,sans-serif;
            padding:32px 20px;border-radius:12px;max-width:560px;margin:0 auto">
  <div style="font-size:13px;letter-spacing:.08em;color:#a78bfa;margin-bottom:14px">
    TRADEWAVE REALTIME</div>
  <div style="font-size:20px;font-weight:700;margin-bottom:12px">{title}</div>
  <div style="font-size:15px;line-height:1.55;color:#c9c6d4">{body_html}</div>
  <div style="margin:22px 0">
    <a href="{cta_url}" style="background:#7c5dfa;color:#fff;text-decoration:none;
       padding:11px 20px;border-radius:9px;font-weight:600;display:inline-block">
      {cta_label}</a>
  </div>
  <div style="font-size:12px;color:#807d8f;border-top:1px solid #2a2738;padding-top:12px">
    {footer_reason}<br>
    The coach is an AI trained on Anne-Marie Baiynd's strategy - educational only,
    never trade advice. Trading futures involves substantial risk of loss.
  </div>
</div>"""


def base_url():
    return current_app.config.get("PUBLIC_BASE_URL", "https://rt-dev.trxstat.com")


def send_welcome(user):
    """The signup welcome: one clear next step (meet your coach)."""
    url = f"{base_url()}/app"
    html = _frame(
        "You're in. Your coach is waiting.",
        "Here's how to start: your coach opens with a short conversation - the same "
        "questions Anne-Marie would ask any new trader. Five minutes, and it builds "
        "your plan around where <i>you</i> are.<br><br>"
        "After that, every trading morning has the same rhythm: the Daily Level Map "
        "is ready before the bell, and your coach is on call all day.",
        url, "Meet your coach",
        "Sent because you created a TradeWave Realtime account.")
    return send_email(user, "welcome", "Welcome - your coach is waiting", html)


def send_answer_ready(user, topic):
    """Close the deferral loop: tell the member who asked that Anne-Marie answered.
    Deep-links into the coach with the original question pre-loaded."""
    q = "You asked me something I had flagged for Anne-Marie - she has answered it"
    url = f"{base_url()}/app/coach?q=" + urllib.parse.quote(q)
    html = _frame(
        "Anne-Marie answered your question.",
        f"Remember the question you asked that I had to flag for her? She just taught "
        f"me the answer - on <b>{topic}</b>. Come ask me again and I will walk you "
        f"through it in her words.",
        url, "Hear her answer",
        "Sent because you asked a question the coach flagged for Anne-Marie.")
    return send_email(user, "answer_ready",
                      "Anne-Marie answered your question", html)


def send_reengagement(user):
    """A warm, non-salesy knock for a member who has drifted. Never billing/win-back."""
    url = f"{base_url()}/app"
    html = _frame(
        "The buffet is still open.",
        "I have not seen you in a few sessions - no guilt, life happens. When you are "
        "ready, your map is computed and waiting, and we can pick up exactly where you "
        "left off. Even five minutes on one lesson keeps the rhythm. Come back when "
        "you can.",
        url, "Pick up where you left off",
        "Sent because it had been a few sessions since you stopped by.")
    return send_email(user, "reengagement", "Your coach is still here", html)


def send_weekend_study(user):
    """A Sunday-evening touch: the week's map builds tonight, here is one thing to study.
    Allowed on a closed day (that is the point)."""
    url = f"{base_url()}/app/library"
    html = _frame(
        "Your week's map builds tonight.",
        "Globex reopens this evening and tomorrow's read starts forming. A quiet Sunday "
        "is the best time to work on the part that actually moves the needle - the "
        "process. Pick one lesson, ten minutes, and walk into the week sharper.",
        url, "Study one lesson",
        "Sent because a calm weekend is the best time to build the habit.",
    )
    return send_email(user, "weekend_study", "One thing to study before the week",
                      html, allow_closed=True)


def lifecycle_tick(app):
    """Daily lifecycle pass (run by the lifecycle timer): re-engage members who have
    drifted, and on Sunday evening send the weekend-study touch. Returns counts."""
    with app.app_context():
        from .models import User, UserProfile
        now_et = datetime.now(ET)
        cutoff = datetime.utcnow() - timedelta(days=4)          # inactive >= ~4 days
        no_repeat = datetime.utcnow() - timedelta(days=7)       # not re-engaged in a week
        members = (User.query.join(UserProfile, UserProfile.user_id == User.id)
                   .filter(User.role == "member",
                           UserProfile.intake_done.is_(True)).all())
        reeng = 0
        for u in members:
            if u.last_active_at and u.last_active_at > cutoff:
                continue
            recent = (NotificationLog.query
                      .filter(NotificationLog.user_id == u.id,
                              NotificationLog.kind == "reengagement",
                              NotificationLog.sent_at >= no_repeat).count())
            if recent:
                continue
            if send_reengagement(u):
                reeng += 1
        weekend = 0
        # Sunday evening (local ET): the natural "week is starting" touch.
        if now_et.weekday() == 6 and 16 <= now_et.hour < 20:
            for u in members:
                if send_weekend_study(u):
                    weekend += 1
        app.logger.info("lifecycle_tick: reengagement=%s weekend=%s", reeng, weekend)
        return {"reengagement": reeng, "weekend_study": weekend}
