"""Public landing, member area pages, and legal."""
from flask import Blueprint, abort, redirect, render_template, request, url_for

from .models import KnowledgeEntry, Post
from .rag import index as kb_index
from .security import current_user, login_required

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    recent_posts = (Post.query.filter_by(published=True)
                    .order_by(Post.created_at.desc()).limit(3).all())
    return render_template("landing.html", recent_posts=recent_posts)


@bp.route("/v2")
def v2():
    """Public preview of the V2 direction (the coach that learns you). Unlisted; share via URL."""
    return render_template("landing_v2.html")


@bp.route("/app")
@login_required
def dashboard():
    """Today - the member home. The day's map per instrument + the retention rail.
    New members meet the coach first (the intake) before they see any page."""
    from .levels import direction_sentences, latest_maps, scrub_levels
    from .mentor import (checkin_phase, get_profile, next_step, todays_checkins,
                         touch_active)
    from .billing import map_access
    user = current_user()
    touch_active(user)
    profile = get_profile(user)
    if not profile.intake_done and user.accepted_ai_disclaimer and not user.is_staff:
        return redirect(url_for("mentor.intake"))
    access = map_access(user)
    maps = []
    for m in latest_maps():
        p = m.payload
        sentences = direction_sentences(p)
        if access == "gated":  # free past day 1: keep the read, hide the exact numbers
            sentences = [scrub_levels(s) for s in sentences]
        maps.append({
            "instrument": m.instrument,
            "session_date": p.get("session_date"),
            "status": m.status,
            "sentences": sentences,
            "verdict": p.get("verdict"),
            "moc": p.get("moc", {}),
            "levels": p.get("levels", []),
            "built_at": m.built_at,
        })
    posts = (Post.query.filter_by(published=True, kind="post")
             .order_by(Post.created_at.desc()).limit(2).all())
    from datetime import datetime, time, timezone
    from .marketdata import ET
    midnight_et = datetime.combine(datetime.now(ET).date(), time.min, tzinfo=ET)
    insight = (Post.query.filter(Post.published.is_(True), Post.kind == "insight",
                                 Post.created_at >= midnight_et.astimezone(timezone.utc)
                                 .replace(tzinfo=None))
               .order_by(Post.created_at.desc()).first())
    insight_time = ""
    if insight:
        insight_time = (insight.created_at.replace(tzinfo=timezone.utc)
                        .astimezone(ET).strftime("%-I:%M%p ET").lower())
    lib_count = KnowledgeEntry.query.filter_by(published=True).count()
    # The "never lost in time" line: the page always says where the trading day
    # stands, so a stale-looking map never reads as broken.
    from .marketdata import latest_session, session_state
    now_et = datetime.now(ET)
    session = latest_session()
    st = session_state(now_et)
    ns = st["next_session"].strftime("%A %b %-d")
    if st["phase"] == "holiday":
        time_note = (f"Markets are closed today for {st['holiday']} - this is {session}'s map. "
                     f"The next session is {ns}; Globex reopens the evening before.")
    elif st["phase"] == "weekend":
        time_note = (f"Markets are closed - this is {session}'s map. The next session is {ns}; "
                     f"Globex reopens 6:00pm ET the evening before, and that map starts building then.")
    elif st["phase"] == "pre_open":
        time_note = ("Pre-market - the overnight candles are in; the read firms up "
                     "as each session candle completes.")
    elif st["phase"] == "after_close":
        time_note = (f"Session complete. The next map ({ns}) starts building at the 6:00pm "
                     f"Globex open - tonight is for the review and a lesson.")
    elif st["phase"] == "after_close_preweekend":
        time_note = (f"Session complete. The market reopens for the next session ({ns}); "
                     f"Globex opens the evening before. Tonight is for the review and a lesson.")
    else:
        time_note = ""
    from .models import UserLesson
    lessons_done = UserLesson.query.filter(
        UserLesson.user_id == user.id, UserLesson.done_at.isnot(None)).count()
    lessons_viewed = UserLesson.query.filter_by(user_id=user.id).count()
    from .mentor import experience_tier, is_beginner
    # The on-ramp is for learners finding their feet - gate on actual skill tier,
    # not "zero lessons done", so an experienced trader never sees a beginner card.
    tier = experience_tier(profile) if profile.intake_done else "developing"
    show_onramp = (profile.intake_done and tier in ("beginner", "developing")
                   and lessons_done < 3 and lessons_viewed < 5)
    from .models import Appearance
    next_live = (Appearance.query
                 .filter(Appearance.published.is_(True),
                         Appearance.starts_at >= datetime.utcnow())
                 .order_by(Appearance.starts_at).first())
    from .billing import billing_enabled, is_paid, PLANS
    return render_template("app/today.html", maps=maps, posts=posts,
                           insight=insight, insight_time=insight_time,
                           lib_count=lib_count, profile=profile,
                           checkins=todays_checkins(user),
                           checkin_phase=checkin_phase(), next_live=next_live,
                           show_onramp=show_onramp, time_note=time_note,
                           step=next_step(user, profile),
                           access=access, paid=is_paid(user),
                           billing_enabled=billing_enabled(), plans=PLANS,
                           beginner=profile.intake_done and is_beginner(profile))


@bp.route("/app/feed")
@login_required
def feed():
    posts = (Post.query.filter_by(published=True)
             .order_by(Post.created_at.desc()).all())
    return render_template("app/feed.html", posts=posts)


@bp.route("/app/progress")
@login_required
def progress():
    """The 'your month' proof-of-value view - the receipts the coach can point to at
    the renewal decision. Backed by lessons, check-ins, and (money-blind) trades."""
    from datetime import datetime, timedelta
    from .models import CheckIn, Trade, UserLesson
    user = current_user()
    since = datetime.utcnow() - timedelta(days=30)
    ul = UserLesson.query.filter_by(user_id=user.id).all()
    lessons_done = sum(1 for u in ul if u.done_at)
    lessons_viewed = len(ul)
    lessons_total = KnowledgeEntry.query.filter_by(published=True, kind="lesson").count()
    checkins = CheckIn.query.filter(CheckIn.user_id == user.id).all()
    reviews = [c for c in checkins if c.kind == "review"]
    trades = Trade.query.filter(Trade.user_id == user.id).all()
    at_level = sum(1 for t in trades if t.grade.get("at_level") is True)
    held_process = sum(1 for t in trades
                       if t.grade.get("at_level") and not t.grade.get("size_flag"))
    # Days shown up = distinct dates of ANY activity - check-ins, trades, lessons
    # opened, and last seen - so a study-only or login-only member never reads ZERO
    # at the renewal moment (the opposite of what the proof surface exists to do).
    active_days = {c.session_date for c in checkins} | {t.session_date for t in trades}
    active_days |= {u.viewed_at.date() for u in ul if u.viewed_at}
    active_days |= {u.done_at.date() for u in ul if u.done_at}
    if user.last_active_at:
        active_days.add(user.last_active_at.date())
    active_days.add(user.created_at.date())
    # A learner who has not traded should lead with study, not a wall of zeros.
    learner_lead = trades == [] and (lessons_viewed > 0 or len(checkins) > 0)
    stats = {
        "lessons_done": lessons_done, "lessons_viewed": lessons_viewed,
        "lessons_total": lessons_total,
        "checkins": len(checkins), "reviews": len(reviews),
        "trades": len(trades), "at_level": at_level, "held_process": held_process,
        "active_days": len(active_days), "learner_lead": learner_lead,
        "member_since": user.created_at,
    }
    return render_template("app/progress.html", stats=stats)


@bp.route("/app/library")
@login_required
def library():
    """The Method - her process as a staged curriculum, plus reference material."""
    from .models import UserLesson
    user = current_user()
    entries = (KnowledgeEntry.query.filter_by(published=True)
               .order_by(KnowledgeEntry.stage, KnowledgeEntry.stage_order).all())
    # A row exists when a lesson is viewed; done_at marks it completed.
    done_ids = {ul.entry_id for ul in UserLesson.query.filter_by(user_id=user.id).all()
                if ul.done_at}
    stages = []
    # Foundations (stage 0, kind=lesson) lead the path for beginners.
    foundations = [e for e in entries if e.stage == 0 and e.kind == "lesson"]
    if foundations:
        stages.append({"no": 0, "title": "Foundations",
                       "blurb": "Brand new? Start here - the floor under everything else.",
                       "lessons": foundations,
                       "done": sum(1 for e in foundations if e.id in done_ids)})
    for stage_no, (title, blurb) in KnowledgeEntry.STAGES.items():
        lessons = [e for e in entries if e.stage == stage_no and e.kind == "lesson"]
        stages.append({
            "no": stage_no, "title": title, "blurb": blurb, "lessons": lessons,
            "done": sum(1 for e in lessons if e.id in done_ids),
        })
    reference = [e for e in entries if e.stage == 0 and e.kind == "reference"]
    total = sum(len(s["lessons"]) for s in stages)
    total_done = sum(s["done"] for s in stages)
    current_stage = next((s["no"] for s in stages if s["done"] < len(s["lessons"])),
                         stages[-1]["no"] if stages else 1)
    next_lesson = next((e for s in stages for e in s["lessons"]
                        if e.id not in done_ids), None)
    return render_template("app/library.html", stages=stages, reference=reference,
                           done_ids=done_ids, total=total, total_done=total_done,
                           current_stage=current_stage, next_lesson=next_lesson)


@bp.route("/app/library/<int:entry_id>")
@login_required
def library_entry(entry_id):
    from .models import UserLesson
    entry = KnowledgeEntry.query.get_or_404(entry_id)
    if not entry.published:
        abort(404)
    user = current_user()
    from .extensions import db
    from datetime import datetime as _dt
    row = UserLesson.query.filter_by(user_id=user.id, entry_id=entry.id).first()
    if row is None:  # viewing counts as progress (dismisses the on-ramp, visible to coach)
        row = UserLesson(user_id=user.id, entry_id=entry.id, viewed_at=_dt.utcnow(),
                         done_at=None)
        db.session.add(row)
        db.session.commit()
    done = row.done_at is not None
    prev_e = next_e = None
    if entry.kind == "lesson":
        siblings = (KnowledgeEntry.query
                    .filter_by(published=True, stage=entry.stage, kind="lesson")
                    .order_by(KnowledgeEntry.stage_order).all())
        idx = next((i for i, e in enumerate(siblings) if e.id == entry.id), None)
        if idx is not None:
            prev_e = siblings[idx - 1] if idx > 0 else None
            next_e = siblings[idx + 1] if idx + 1 < len(siblings) else None
    stage_meta = KnowledgeEntry.STAGES.get(entry.stage)
    from .mentor import experience_tier, get_profile
    tier = experience_tier(get_profile(user))
    # Beginner/developing readers see the plain-English layer first (when it exists);
    # everyone can toggle it. The original (her source-of-truth) is always reachable.
    prefer_plain = bool(entry.plain) and tier in ("beginner", "developing")
    return render_template("app/library_entry.html", entry=entry, done=bool(done),
                           prev_e=prev_e, next_e=next_e, stage_meta=stage_meta,
                           prefer_plain=prefer_plain, has_plain=bool(entry.plain))


@bp.route("/app/library/<int:entry_id>/done", methods=["POST"])
@login_required
def library_entry_done(entry_id):
    from .extensions import db
    from .models import UserLesson
    entry = KnowledgeEntry.query.get_or_404(entry_id)
    user = current_user()
    from datetime import datetime as _dt
    row = UserLesson.query.filter_by(user_id=user.id, entry_id=entry.id).first()
    if row is None:
        row = UserLesson(user_id=user.id, entry_id=entry.id, viewed_at=_dt.utcnow())
        db.session.add(row)
    row.done_at = None if row.done_at else _dt.utcnow()  # toggle completion, keep the view
    db.session.commit()
    return redirect(request.referrer or url_for("main.library_entry", entry_id=entry.id))


@bp.route("/app/account")
@login_required
def account():
    from .billing import PLANS, active_subscription, billing_enabled
    user = current_user()
    return render_template("app/account.html",
                           subscription=active_subscription(user),
                           billing_enabled=billing_enabled(),
                           plans=PLANS,
                           just_subscribed=request.args.get("subscribed") == "1")


@bp.route("/app/discord/code", methods=["POST"])
@login_required
def discord_code():
    """Issue a one-time code the member types in the Discord #link-up channel
    (!link CODE) to unlock their member role."""
    import secrets as pysecrets
    from .extensions import db
    user = current_user()
    user.discord_link_code = pysecrets.token_hex(4).upper()
    db.session.commit()
    return redirect(url_for("main.account"))


@bp.route("/legal/<page>")
def legal(page):
    if page not in {"disclaimer", "terms", "privacy"}:
        abort(404)
    return render_template(f"legal/{page}.html")
