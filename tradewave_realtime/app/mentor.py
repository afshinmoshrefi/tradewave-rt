"""The mentor core - the coach that knows you.

Design: product/V1_SITE_DESIGN.md section 4. The intake is SERVER-DRIVEN (fixed
questions in her voice, free-text answers stored straight into the trader profile),
so the flow is deterministic and cheap; the LLM writes only the warm wrap-up.
Lesson assignment is a deterministic struggle-to-lessons mapping - auditable, no
model whim. Guardrails: the profile never stores positions, balances, or dollar
amounts; personalization serves teaching only.
"""
import re
from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from .extensions import db
from .marketdata import ET
from .models import CheckIn, KnowledgeEntry, UserProfile
from .security import current_user, disclaimer_required

bp = Blueprint("mentor", __name__)

# ---------------------------------------------------------------- intake script
# Fixed questions, her voice. One at a time; answers land in the named field.
INTAKE_STEPS = [
    ("experience",
     "Before we look at a single chart, I want to know where you are. "
     "How long have you been trading - brand new, a year or two in, or have you "
     "been at this a while?"),
    ("instruments",
     "Good. What do you trade, or want to trade? Futures like the ES and NQ, "
     "stocks, options - and is it a personal account or a prop/funded account?"),
    ("goal",
     "What do you want this to become for you? Be honest with me - consistency, "
     "a side income, full time someday?"),
    ("recent",
     "And how has it actually been going lately? No judgment here - the truth is "
     "what lets me coach you."),
    ("struggles",
     "Now the important one. What trips you up the most? Chasing entries, sizing "
     "too big, overtrading, hesitating on good setups, revenge trading after a "
     "loss - what's your pattern?"),
    ("schedule",
     "Last one, and it matters more than it sounds. When do you actually trade, and "
     "what does your day look like around it? Every morning at the open, afternoons, "
     "a few days a week - and do you have a day job or a night shift I should work "
     "around? I want my timing to fit your real life, not the other way around."),
]

INTAKE_ACKS = ["Got it.", "Okay, good to know.", "Thank you for being straight with me.",
               "That helps.", "I hear you."]

# ----------------------------------------------- struggles -> lesson assignment
# Deterministic mapping: struggle key -> (title substrings to look up, why).
# Patterns broadened so natural phrasing ("blow my daily limit", "gave it all
# back", "oversize") maps to the right lesson instead of being missed.
STRUGGLE_PATTERNS = {
    "chasing": ["chas", "fomo", "jump in", "too early", "breakout", "buy the high",
                "buy the top", "miss the move then"],
    "overtrading": ["overtrad", "too many trades", "can't stop", "all day", "force",
                    "forcing", "bored", "boredom", "churn"],
    "sizing": ["siz", "too big", "blew", "blow up", "blow my", "risk too", "oversiz",
               "over size", "loss limit", "daily limit", "max loss", "drawdown",
               "gave it all back", "gave it back", "too much risk", "too much size"],
    "hesitation": ["hesitat", "scared", "afraid", "miss", "pull the trigger",
                   "don't take", "freeze", "froze", "fear", "gun shy", "gun-shy"],
    "revenge": ["revenge", "tilt", "angry", "make it back", "get it back",
                "win it back", "double down after"],
    "discipline": ["disciplin", "rules", "plan", "stick to", "no plan", "wing it"],
    "overwhelm": ["overwhelm", "confused", "lost", "too much", "can't keep up",
                  "cannot keep up", "over my head", "complicated", "freeze up",
                  "do something dumb", "don't know where to start"],
}

# Account-critical struggles first, so when a member names 3+ patterns the most
# dangerous one (revenge, sizing/loss-limit) is never the one truncated away.
STRUGGLE_PRIORITY = ["revenge", "sizing", "overwhelm", "discipline", "chasing",
                     "hesitation", "overtrading"]

ASSIGNMENT_MAP = {
    "chasing": (["Wait for the fade", "Entry routine"],
                "you told me you chase - so we start where she starts: making "
                "price come to you"),
    "overtrading": (["Discipline, routine, and grading your day", "Process over P&L"],
                    "you told me you overtrade - so we start with her day "
                    "structure and the 5-trade cap"),
    "sizing": (["Risk and position sizing", "Get risk small"],
               "you told me sizing hurts you - so we start with how she sizes "
               "and why small wins"),
    "hesitation": (["if-and-then conditional entry rule", "Wait for the fade"],
                   "you told me you hesitate - so we start with her if-and-then "
                   "rule that makes entries mechanical"),
    "revenge": (["Fear, FOMO, and revenge trading", "Process over P&L"],
                "you told me losses tilt you - so we start with her psychology "
                "of the red day"),
    "discipline": (["Discipline, routine, and grading your day",
                    "Open-read routine"],
                   "you told me the rules slip - so we start with her daily "
                   "routine, start to finish"),
    "overwhelm": (["Patience - the buffet is open tomorrow", "Process over P&L"],
                  "you told me it can feel like a lot - so we slow it down to one "
                  "idea at a time and let the pressure off"),
}

DEFAULT_ASSIGNMENT = (["Grade the trend first", "master candles"],
                      "we start at the front of her process: reading the day "
                      "before trading it")


def extract_struggles(text):
    """Struggle keys present in the text, ordered by account-criticality so the
    most dangerous pattern is never the one dropped by a truncation."""
    low = (text or "").lower()
    found = [k for k in STRUGGLE_PATTERNS
             if any(p in low for p in STRUGGLE_PATTERNS[k])]
    return sorted(found, key=lambda k: (STRUGGLE_PRIORITY.index(k)
                                        if k in STRUGGLE_PRIORITY else 99))


def _find_lesson(fragment):
    """Resolve a lesson by title - exact match preferred, then a deterministic
    substring match (stable across reseeds: ordered by stage/order/id, not luck)."""
    base = KnowledgeEntry.query.filter(KnowledgeEntry.published.is_(True))
    exact = base.filter(db.func.lower(KnowledgeEntry.title) == fragment.lower()).first()
    if exact:
        return exact
    return (base.filter(KnowledgeEntry.title.ilike(f"%{fragment}%"))
            .order_by(KnowledgeEntry.stage, KnowledgeEntry.stage_order,
                      KnowledgeEntry.id).first())


def foundation_lessons():
    """The Stage 0 'Foundations' track (kind=lesson), in order. The floor a true
    beginner needs before the master-candle curriculum."""
    return (KnowledgeEntry.query
            .filter(KnowledgeEntry.published.is_(True),
                    KnowledgeEntry.stage == 0, KnowledgeEntry.kind == "lesson")
            .order_by(KnowledgeEntry.stage_order, KnowledgeEntry.id).all())


def resolve_assignment(struggle_keys, tier="experienced"):
    """Map skill tier + struggles to published lessons -> [{entry_id, title, why}].
    Beginners are floored on the Foundations track first; developing traders get
    their struggle work FIRST (so the account-critical lesson is never crowded out
    by foundations) then a few skippable mechanics; experienced go straight to the
    struggle lessons. Struggle lessons are added round-robin - every named
    struggle's PRIMARY lesson survives before any struggle gets its second - so a
    multi-struggle member never loses their most dangerous lesson to a cap."""
    out, seen = [], set()

    def add(entry, why):
        if entry and entry.id not in seen:
            seen.add(entry.id)
            out.append({"entry_id": entry.id, "title": entry.title, "why": why})

    def add_struggles(cap=5):
        plans = [ASSIGNMENT_MAP.get(k, DEFAULT_ASSIGNMENT) for k in struggle_keys[:3]] \
            or [DEFAULT_ASSIGNMENT]
        before = len(out)
        depth = max(len(titles) for titles, _ in plans)
        for i in range(depth):                       # round-robin: column i of every plan
            for titles, why in plans:
                if i < len(titles):
                    add(_find_lesson(titles[i]), why)
                    if len(out) - before >= cap:
                        return

    foundations = foundation_lessons()
    if tier == "beginner":
        for e in foundations:
            add(e, "you told me you're brand new - so we start at the very floor, "
                   "one idea at a time, before any chart-reading")
        add_struggles(cap=3)
    elif tier == "developing":
        add_struggles(cap=5)                          # their problem first, guaranteed
        for e in foundations[1:4]:                    # skippable mechanics, appended after
            add(e, "you're newer to futures - a quick floor on the mechanics, "
                   "skip any you already know")
    else:
        add_struggles(cap=5)
    return out


def get_profile(user):
    profile = UserProfile.query.filter_by(user_id=user.id).first()
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.session.add(profile)
        db.session.commit()
    return profile


def missed_sessions(last_active):
    """Trading sessions missed since the member was last active (weekends/holidays
    do not count). Used so the lapse greeting fires on a real absence, not a weekend."""
    from datetime import timedelta
    from .marketdata import is_session_day
    if not last_active:
        return 0
    cur, end, n = last_active.date(), datetime.utcnow().date(), 0
    while cur < end:
        cur += timedelta(days=1)
        if cur < end and is_session_day(cur):
            n += 1
    return n


def touch_active(user):
    """Record that the member is here (throttled to ~10 min) - the activity
    signal the re-engagement lifecycle fires on. Without it a lapse is invisible."""
    from datetime import timedelta
    now = datetime.utcnow()
    if user.last_active_at is None or (now - user.last_active_at) > timedelta(minutes=10):
        user.last_active_at = now
        db.session.commit()


# ------------------------------------------------------------- context builders
BEGINNER_HINTS = ("brand new", "never traded", "total beginner", "just starting",
                  "haven't traded", "have not traded", "no experience", "newbie",
                  "complete beginner", "never done this", "new to trading",
                  "just signed up to learn", "learning to trade")
# Newer-but-not-zero, or specifically new to FUTURES (catches the "dabbled in
# stocks, new to futures" case the old keyword-only check missed entirely).
DEVELOPING_HINTS = ("new to futures", "dabbl", "few months", "couple months",
                    "less than a year", "about a year", "year or so", "1 year",
                    "one year", "getting started", "still learning", "part time",
                    "part-time", "fairly new", "pretty new", "newer")
EXPERIENCED_HINTS = ("a while", "long time", "many years", "trading for years",
                     "for years", "years now", "years of trading", "years trading",
                     "years experience", "decade", "seasoned", "profitable",
                     "consistent", "full time", "full-time", "professional",
                     "veteran", "experienced", "mostly green", "been at this",
                     "been doing this a while")
# NEWNESS = low KNOWLEDGE (these demote). Deliberately NOT result words like
# "ups and downs"/"inconsistent"/"blew up" - a multi-year trader with bad RESULTS
# still knows the basics and must not be talked down to (their struggles drive
# the lessons, not their tier).
NEWNESS_HINTS = ("new to futures", "new to trading", "still learning", "getting started",
                 "just getting", "just starting", "learning the basics", "fairly new",
                 "pretty new", "newer", "dabbl", "few months", "couple months",
                 "about a year", "a year or so", "year or so", "1 year", "one year",
                 "less than a year")

_YEARS_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "couple": 2, "few": 3, "several": 4,
                "many": 6, "decade": 10}


def _years_mentioned(low):
    """Largest trading-years count the member stated (digit or word). 0 if none."""
    nums = [int(m) for m in re.findall(r"(\d+)\s*\+?\s*(?:years?|yrs?|yr)\b", low)]
    for w, n in _YEARS_WORDS.items():
        if re.search(rf"\b{w}\b[\s-]*(?:years?|yrs?)", low) or (w == "decade" and "decade" in low):
            nums.append(n)
    return max(nums) if nums else 0


_PRO_HINTS = ("full time", "full-time", "professional", "prop", "funded", "combine",
              "allocated", "own capital", "for a living", "trade for a living",
              "decade", "veteran", "seasoned")


def experience_tier(profile):
    """beginner | developing | experienced - from the intake experience answer (and the
    instruments/account answer, which carries prop/funded). Drives both coach posture AND
    which lessons are assigned. Biased so a knowledge signal (multi-year count, professional
    history) is respected, but newness-framing demotes; result/struggle words never demote a
    knowledgeable trader's tier. A clear veteran (many years, or years + a professional/prop
    signal) is PINNED to experienced and can never be talked down to as developing, even if
    their answer also carries humble or struggle language - struggle is orthogonal to
    experience, and condescending to an 11-year pro loses them in 30 seconds."""
    # Prop/funded shows up in the instruments answer, not just the experience answer; pull
    # both so a "11 years, 4 of them prop" trader floors at experienced from either field.
    low = (profile.experience or "").lower()
    acct = ((profile.instruments or "") + " " + (profile.account_type or "")).lower()
    both = low + " " + acct
    if any(h in low for h in BEGINNER_HINTS):
        return "beginner"
    yrs = _years_mentioned(low)
    newish = any(h in low for h in NEWNESS_HINTS)
    pro = any(h in both for h in _PRO_HINTS)
    # HIGH-confidence veteran that PINS to experienced even past newness/struggle language: a
    # professional / prop / own-capital / decade signal. Struggle words ('my edge is fine, I
    # give back gains') and humility never demote a real pro - condescending to an 11-year/prop
    # trader loses them in 30 seconds. A professional/prop signal also OVERRIDES a 'new to
    # futures' framing (a funded multi-year trader is not a developing member).
    if (pro and (yrs >= 2 or "years" in both)) or (yrs >= 3 and pro) or yrs >= 10:
        return "experienced"
    # Strong-but-not-pro experience (multi-year, or a clear veteran phrase): experienced UNLESS
    # they explicitly frame themselves as new (e.g. '5 years in stocks but new to futures' still
    # wants the futures floor - that newness is real, not false modesty about results).
    strong = yrs >= 3 or any(h in low for h in EXPERIENCED_HINTS)
    if strong and not newish:
        return "experienced"
    if newish or yrs >= 1 or strong:
        return "developing"   # e.g. "5 years but new to futures" -> hand-hold the futures part
    return "developing"        # safest default: never assume expertise


def is_beginner(profile):
    return experience_tier(profile) == "beginner"


def current_focus(user, profile):
    """Living focus: assigned lessons not yet completed, else the next unfinished
    method lesson - so 'your focus' advances instead of looping the Day-1 pair."""
    from .models import UserLesson
    done_ids = {r.entry_id for r in UserLesson.query.filter_by(user_id=user.id).all()
                if r.done_at}
    focus = [a for a in (profile.assigned or []) if a.get("entry_id") not in done_ids]
    if not focus:
        q = (KnowledgeEntry.query
             .filter(KnowledgeEntry.published.is_(True), KnowledgeEntry.kind == "lesson",
                     KnowledgeEntry.stage >= 1)
             .order_by(KnowledgeEntry.stage, KnowledgeEntry.stage_order, KnowledgeEntry.id))
        for nxt in q.all():
            if nxt.id not in done_ids:
                focus = [{"entry_id": nxt.id, "title": nxt.title,
                          "why": "you've cleared your starting focus - this is the next step"}]
                break
    return focus


def next_step(user, profile):
    """The ONE concrete next action for this member right now - never blank. Drives
    the Today next-step card and the coach's answer to 'what should I do?'. So a
    non-trader on a weekend always has somewhere to go, not a dead page."""
    if not profile or not profile.intake_done:
        return {"label": "Tell your coach about you - the 2-minute intake", "url": "/app/intake"}
    # An open, not-yet-debriefed trade from today takes priority (set up in G3).
    try:
        from .models import Trade
        from datetime import datetime as _dt
        t = (Trade.query.filter_by(user_id=user.id, reviewed=False)
             .order_by(Trade.created_at.desc()).first())
        if t:
            return {"label": "Debrief your last trade with your coach",
                    "url": "/app/coach?q=" + "Let's debrief the trade I just logged"}
    except Exception:
        pass
    focus = current_focus(user, profile)
    if focus:
        a = focus[0]
        return {"label": f"Your focus: {a['title']}",
                "url": f"/app/library/{a['entry_id']}"}
    return {"label": "Ask your coach anything", "url": "/app/coach"}


def lesson_state(user):
    """(done_titles, done_ids, viewed_ids) for coach context + on-ramp gating."""
    from .models import UserLesson
    rows = UserLesson.query.filter_by(user_id=user.id).all()
    done_ids = {r.entry_id for r in rows if r.done_at}
    viewed_ids = {r.entry_id for r in rows}
    done_titles = []
    if done_ids:
        done_titles = [e.title for e in KnowledgeEntry.query
                       .filter(KnowledgeEntry.id.in_(done_ids)).all()]
    return done_titles, done_ids, viewed_ids


_POSTURE = {
    "beginner":
        "- POSTURE: TOTAL BEGINNER. Define every term the first time you use it "
        "(level, candle, limit order, stop). Short answers, one idea at a time. "
        "Celebrate small understanding. Strongly encourage paper/sim practice "
        "and never assume they have or should have real money at risk - her own "
        "teaching: learn the read first, the buffet is open every day.",
    "developing":
        "- POSTURE: DEVELOPING / newer to futures. They can read a chart but do not "
        "know futures specifics yet - define futures-specific terms (tick, contract "
        "size, MES vs ES, RTH vs Globex) the first time. Keep it concrete, steer to "
        "sim for anything new, do not assume size or a funded account.",
    "experienced":
        "- POSTURE: EXPERIENCED. Skip the basics unless asked; do not re-explain what "
        "they clearly know. Engage at the level of nuance, edge cases, and her finer "
        "distinctions; respect their time. If a question is advanced, go deep.",
}


def member_context(user):
    """Compact profile block for the coach's system prompt. Teaching only."""
    profile = UserProfile.query.filter_by(user_id=user.id).first()
    if not profile or not profile.intake_done:
        return ""
    lines = ["# THIS MEMBER (private to this member; use to TEACH better, never to "
             "give personal trade directions; never mention account sizes)"]
    lines.append(_POSTURE[experience_tier(profile)])
    if profile.experience:
        lines.append(f"- Experience: {profile.experience}")
    if profile.instruments:
        lines.append(f"- Trades: {profile.instruments}"
                     + (f" ({profile.account_type})" if profile.account_type else ""))
    if profile.goal:
        lines.append(f"- Goal: {profile.goal}")
    if profile.struggles_raw:
        keys = f" [{profile.struggles_keys}]" if profile.struggles_keys else ""
        lines.append(f"- Struggles{keys}: {profile.struggles_raw}")
    if profile.schedule:
        lines.append(f"- Trades when: {profile.schedule}")
    if profile.coaching_summary:
        lines.append(f"- Coaching so far: {profile.coaching_summary}")
    focus = current_focus(user, profile)
    if focus:
        lines.append("- Current focus lessons (advances as they finish): "
                     + "; ".join(a["title"] for a in focus[:3]))
    done_titles, _, _ = lesson_state(user)
    if done_titles:
        lines.append("- Lessons completed (do not re-teach unless asked): "
                     + "; ".join(done_titles[:12]))
    try:
        from .trades import recent_trades_context
        tctx = recent_trades_context(user)
        if tctx:
            lines.append(tctx)
    except Exception:
        pass
    recents = (CheckIn.query.filter_by(user_id=user.id)
               .order_by(CheckIn.session_date.desc(), CheckIn.kind.desc())
               .limit(4).all())
    for c in reversed(recents):
        lines.append(f"- Check-in {c.session_date} ({c.kind}): {c.text[:200]}")
    return "\n".join(lines)


SUMMARY_EVERY = 8  # regenerate after this many new messages


def maybe_update_summary(user):
    """Rolling cross-session coaching summary (Haiku, ~1 call per 8 messages).
    Runs on coach-page load; failures are swallowed - the summary is an
    enhancement, never a blocker."""
    from .models import ChatMessage, ChatThread
    profile = UserProfile.query.filter_by(user_id=user.id).first()
    if not profile or not profile.intake_done:
        return
    try:
        from datetime import timedelta
        new_msgs = (ChatMessage.query.join(ChatThread)
                    .filter(ChatThread.user_id == user.id,
                            ChatMessage.id > profile.summarized_upto)
                    .order_by(ChatMessage.id).all())
        since = profile.summary_updated_at or datetime.min
        new_ci = (CheckIn.query.filter(CheckIn.user_id == user.id,
                                       CheckIn.created_at > since).count())
        stale = (profile.summary_updated_at is None
                 or (datetime.utcnow() - profile.summary_updated_at) > timedelta(days=2))
        # Heavy chatter: every 8 messages. Light engager: on a time cadence too,
        # folding in check-ins - so the lightest users still compound.
        trigger = (len(new_msgs) >= SUMMARY_EVERY
                   or (stale and (len(new_msgs) >= 2 or new_ci >= 1)))
        if not trigger:
            return
        from flask import current_app
        api_key = current_app.config.get("ANTHROPIC_TOKEN")
        if not api_key:
            return
        import anthropic
        recents = (CheckIn.query.filter_by(user_id=user.id)
                   .order_by(CheckIn.session_date.desc(), CheckIn.kind.desc())
                   .limit(4).all())
        ci_text = "\n".join(f"check-in {c.session_date} ({c.kind}): {c.text[:200]}"
                            for c in reversed(recents))
        transcript = "\n".join(f"{m.role}: {m.content[:400]}" for m in new_msgs[-24:])
        if ci_text:
            transcript = (ci_text + "\n" + transcript) if transcript else ci_text
        prompt = (
            "You maintain a tough, candid trading coach's private notes on ONE member - "
            "the kind of notes a friend who is invested in them keeps so they can pick up "
            "exactly where they left off, bring the right thing back at the right moment, "
            "and not re-teach what is already landed. Merge the EXISTING NOTES with the NEW "
            "CONVERSATION into UPDATED NOTES. Keep it under 130 words, plain prose, and "
            "capture, in priority order:\n"
            "1. HABITS / recurring trading mistakes and leaks (chasing, oversizing after a "
            "win, revenge after a loss, hesitating) - and whether each is improving or still "
            "live.\n"
            "2. PERSONALITY / how they talk and take coaching (anxious and self-doubting, "
            "cocky and hype-allergic, impulsive, curt, needs reassurance vs needs a kick) - "
            "so the next session matches their wavelength.\n"
            "3. REAL PROGRESS worth celebrating, with the concrete evidence.\n"
            "4. COMMITMENTS they made and the NEXT GATE/RULE you agreed to build next.\n"
            "5. PERSONAL CONTEXT that should be handled with care (e.g. works nights, trades "
            "before a shift, a prop/funded reality, a rough stretch).\n"
            "Then end with ONE LINE starting exactly 'NEXT TIME:' that names the single most "
            "important dated callback hook to open the next session with - the specific thing "
            "to check against them (e.g. 'NEXT TIME: ask if the grab-it-now urge showed up, "
            "and whether the two-loss stop held'). Never record account sizes, balances, "
            "dollar amounts, or specific live positions. No em dashes.\n\n"
            f"EXISTING NOTES: {profile.coaching_summary or '(none yet)'}\n\n"
            f"NEW CONVERSATION:\n{transcript}\n\nUPDATED NOTES:")
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=current_app.config.get("CLAUDE_MODEL", "claude-haiku-4-5"),
            max_tokens=250, messages=[{"role": "user", "content": prompt}])
        notes = "".join(b.text for b in resp.content
                        if getattr(b, "type", "") == "text").strip()
        if notes:
            # This summary is shown on the profile AND fed back into the coach's
            # context, so it goes through the same compliance screen. If it reads like
            # a trade call, keep the prior summary rather than persist a bad note.
            from .llm import screen_reply
            ok, reason = screen_reply(notes)
            if not ok:
                current_app.logger.warning(
                    "coaching summary tripped compliance screen (%s); keeping prior", reason)
                return
            profile.coaching_summary = notes.replace(chr(0x2014), " - ")[:1200]
            if new_msgs:
                profile.summarized_upto = new_msgs[-1].id
            profile.summary_updated_at = datetime.utcnow()
            db.session.commit()
    except Exception:
        from flask import current_app
        current_app.logger.exception("coaching summary update failed")
        db.session.rollback()


def coach_greeting(user):
    """Deterministic continuity greeting. Lapse-aware (welcomes a returning user
    instead of cold), draws 'last time' from the most recent meaningful signal
    (any check-in OR the last chat turn), and never replays a stale good day."""
    from datetime import datetime as _dt
    from .models import ChatMessage, ChatThread
    profile = UserProfile.query.filter_by(user_id=user.id).first()
    if not profile or not profile.intake_done:
        return None
    now = _dt.utcnow()
    # Count missed SESSIONS, not calendar days - a weekend or holiday is not a lapse,
    # so a faithful daily trader returning Monday is never greeted as if they vanished.
    if missed_sessions(user.last_active_at) >= 2:
        parts = [f"Good to have you back, {user.name_or_email} - it has been a little while."]
    else:
        parts = [f"Welcome back, {user.name_or_email}."]
    # Most recent meaningful signal: any check-in (review preferred same day), else
    # the last thing they said in chat - with a staleness guard so we never echo an
    # old good day during a fresh rough patch.
    signal = None
    last_ci = (CheckIn.query.filter_by(user_id=user.id)
               .order_by(CheckIn.session_date.desc(), CheckIn.kind.desc()).first())
    if last_ci:
        signal = (last_ci.session_date, last_ci.text)
    else:
        last_msg = (ChatMessage.query.join(ChatThread)
                    .filter(ChatThread.user_id == user.id, ChatMessage.role == "user")
                    .order_by(ChatMessage.id.desc()).first())
        if last_msg:
            signal = (last_msg.created_at.date(), last_msg.content)
    if signal:
        sdate, stext = signal
        if (now.date() - sdate).days > 6:
            parts.append("It has been a bit since we last talked - no problem, we pick "
                         "up wherever you are right now.")
        else:
            parts.append(f"Last time you told me: \"{stext[:160]}\"")
    try:  # surface her freshest content proactively when it exists (never on a closed day)
        from .levels import _todays_insight, _todays_briefing
        from .marketdata import session_state
        if not session_state()["closed_today"] and (_todays_insight() or _todays_briefing()):
            if experience_tier(profile) == "beginner":
                # A never-traded member has no context for a live session read - frame
                # it as learning to read a day, not a walkthrough of today's trade.
                parts.append("Anne-Marie shared her read this morning - want to use it to "
                             "learn how she reads a day like today?")
            else:
                parts.append("Anne-Marie posted her read this morning - want me to walk "
                             "you through it?")
    except Exception:
        pass
    focus = current_focus(user, profile)
    if focus:
        parts.append("Your focus right now: " + " and ".join(
            f"**{a['title']}**" for a in focus[:2]) + ".")
    parts.append("What's on your mind - today's map, a lesson, or how it's going?")
    return " ".join(parts)


def free_tier_stub(user):
    """Minimal continuity for the free/unauthenticated coach tier (Discord), which
    otherwise gets an empty member_context and answers as a stateless generic bot.
    Keeps the paid personalization boundary while not feeling cold, and nudges intake."""
    name = getattr(user, "name_or_email", None) or "there"
    return ("# FREE TIER (no full profile yet)\n"
            f"- You are talking to {name} on the free tier. You do not have their trader "
            "profile or today's private map. Coach the method generally and warmly. Once, "
            "naturally, mention they will get a coach tuned to them (and the daily map) with "
            "membership and the 5-minute intake - never pushy.")


# --------------------------------------------------------------------- routes
@bp.route("/app/intake")
@disclaimer_required
def intake():
    user = current_user()
    profile = get_profile(user)
    if profile.intake_done:
        return redirect(url_for("main.dashboard"))
    step = min(profile.intake_step, len(INTAKE_STEPS) - 1)
    return render_template("app/intake.html", profile=profile, step=step,
                           question=INTAKE_STEPS[step][1],
                           total=len(INTAKE_STEPS))


@bp.route("/app/intake/api/answer", methods=["POST"])
@disclaimer_required
def intake_answer():
    user = current_user()
    profile = get_profile(user)
    if profile.intake_done:
        return jsonify({"done": True, "redirect": url_for("main.dashboard")})
    text = ((request.get_json(silent=True) or {}).get("answer") or "").strip()
    if not text:
        return jsonify({"error": "empty answer"}), 400
    from .privacy import scrub_sensitive
    text = scrub_sensitive(text[:1500])

    field, _ = INTAKE_STEPS[min(profile.intake_step, len(INTAKE_STEPS) - 1)]
    if field == "instruments":
        profile.instruments = text
        low = text.lower()
        if any(w in low for w in ("prop", "funded", "combine", "topstep", "apex")):
            profile.account_type = "prop/funded"
        elif any(w in low for w in ("personal", "own", "my account", "cash", "ira")):
            profile.account_type = "personal"
    elif field == "struggles":
        profile.struggles_raw = text
        profile.struggles_keys = ",".join(extract_struggles(text))
    else:
        setattr(profile, field, text)
    profile.intake_step += 1

    if profile.intake_step < len(INTAKE_STEPS):
        db.session.commit()
        ack = INTAKE_ACKS[profile.intake_step % len(INTAKE_ACKS)]
        return jsonify({"ack": ack,
                        "question": INTAKE_STEPS[profile.intake_step][1],
                        "step": profile.intake_step,
                        "total": len(INTAKE_STEPS)})

    # Final answer: build the assignment, the summary, and the wrap-up.
    keys = profile.struggles_keys.split(",") if profile.struggles_keys else []
    assigned = resolve_assignment([k for k in keys if k], experience_tier(profile))
    profile.assigned = assigned
    profile.summary = (
        f"Experience: {profile.experience}. Trades: {profile.instruments} "
        f"({profile.account_type or 'account type not stated'}). "
        f"Goal: {profile.goal}. Recently: {profile.recent}. "
        f"Struggles: {profile.struggles_raw}. Schedule: {profile.schedule}.")
    # Seed the rolling coaching summary from intake so memory is NON-EMPTY from
    # Day 1 - even a member who never chats 8 messages gets continuity.
    profile.coaching_summary = (
        f"New member, {experience_tier(profile)} trader. Goal: {profile.goal[:120]}. "
        f"Watch for: {profile.struggles_raw[:140] or 'no pattern named yet'}. "
        f"Trades: {profile.schedule[:80]}.")[:1200]
    profile.summary_updated_at = datetime.utcnow()
    profile.intake_done = True
    db.session.commit()

    from .llm import first_read, intake_wrapup
    wrap = intake_wrapup(profile, assigned)
    read = first_read(profile)  # the aha: exactly the help they just asked for, on today
    return jsonify({"done": True, "wrap": wrap, "first_read": read,
                    "redirect": url_for("main.dashboard")})


@bp.route("/app/profile", methods=["GET", "POST"])
@disclaimer_required
def profile_page():
    user = current_user()
    profile = get_profile(user)
    saved = False
    if request.method == "POST":
        from .privacy import scrub_sensitive
        for field in ("experience", "instruments", "account_type", "goal",
                      "recent", "struggles_raw", "schedule"):
            if field in request.form:
                setattr(profile, field,
                        scrub_sensitive(request.form[field].strip()[:1500]))
        profile.struggles_keys = ",".join(extract_struggles(profile.struggles_raw))
        if profile.intake_done:
            keys = [k for k in profile.struggles_keys.split(",") if k]
            profile.assigned = resolve_assignment(keys, experience_tier(profile))
        db.session.commit()
        saved = True
    return render_template("app/profile.html", profile=profile, saved=saved)


@bp.route("/app/profile/delete-chats", methods=["POST"])
@disclaimer_required
def chats_delete():
    """Member right: genuinely erase conversation history (and everything the
    coach derived from it) without touching the profile facts they gave us."""
    from .models import ChatMessage, ChatThread
    user = current_user()
    thread_ids = [t.id for t in ChatThread.query.filter_by(user_id=user.id).all()]
    if thread_ids:
        ChatMessage.query.filter(ChatMessage.thread_id.in_(thread_ids)).delete(
            synchronize_session=False)
        ChatThread.query.filter(ChatThread.id.in_(thread_ids)).delete(
            synchronize_session=False)
    profile = UserProfile.query.filter_by(user_id=user.id).first()
    if profile:
        profile.coaching_summary = ""   # derived from the chats - goes with them
        profile.summarized_upto = 0
    db.session.commit()
    return redirect(url_for("mentor.profile_page"))


@bp.route("/app/profile/delete", methods=["POST"])
@disclaimer_required
def profile_delete():
    user = current_user()
    profile = UserProfile.query.filter_by(user_id=user.id).first()
    if profile:
        db.session.delete(profile)
        CheckIn.query.filter_by(user_id=user.id).delete()
        db.session.commit()
    return redirect(url_for("main.dashboard"))


@bp.route("/app/checkin", methods=["POST"])
@disclaimer_required
def checkin():
    user = current_user()
    data = request.get_json(silent=True) or {}
    kind = data.get("kind")
    from .privacy import scrub_sensitive
    text = scrub_sensitive((data.get("text") or "").strip()[:1000])
    if kind not in ("plan", "review") or not text:
        return jsonify({"error": "bad request"}), 400
    today = datetime.now(ET).date()
    row = CheckIn.query.filter_by(user_id=user.id, session_date=today,
                                  kind=kind).first()
    if row is None:
        row = CheckIn(user_id=user.id, session_date=today, kind=kind, text=text)
        db.session.add(row)
    else:
        row.text = text
    db.session.commit()

    from .llm import checkin_reply
    reply = checkin_reply(user, kind, text)
    row.reply = reply
    db.session.commit()
    maybe_update_summary(user)  # a check-in is a signal; let memory compound on it
    return jsonify({"reply": reply})


def todays_checkins(user):
    today = datetime.now(ET).date()
    rows = CheckIn.query.filter_by(user_id=user.id, session_date=today).all()
    return {r.kind: r for r in rows}


def checkin_phase():
    """Which check-in the Today card asks for right now (ET): plan / review /
    closed. Routes through the one holiday-aware session clock so it can never
    ask 'what's your plan today?' on a Saturday or a market holiday."""
    from .marketdata import session_state
    return session_state()["checkin"]
