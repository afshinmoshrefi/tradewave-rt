#!/usr/bin/env python
"""coach_sim.py - drive the REAL TradeWave Realtime coach as a simulated member.

A reusable CLI that runs inside the live Flask app context and exercises the
ACTUAL coach functions (no mocks): generate_reply, member_context,
maybe_update_summary, first_read, and the runtime compliance screen. It lets us
test the coach the way a real member would meet it - across multiple sessions,
with cross-session memory accumulating between them.

Run with the dev venv, from the project root:

    .venv/bin/python coach_sim.py new --persona '{"level":"beginner", ...}'
    .venv/bin/python coach_sim.py firstread <id>
    .venv/bin/python coach_sim.py turn <id> "what is a failed retest?"
    .venv/bin/python coach_sim.py addtrade <id> '{"instrument":"ES","side":"long",...}'
    .venv/bin/python coach_sim.py endsession <id>
    .venv/bin/python coach_sim.py dump <id>

Persona JSON (all optional except level/goal are recommended). The fields map to
exactly what the server-driven intake (app/mentor.py) writes onto UserProfile, so
a simulated member is indistinguishable from one who answered the intake script:

    {
      "level":       "beginner|developing|experienced" OR a free-text experience
                     line (e.g. "5 years but new to futures"),
      "goal":        "what they want this to become",
      "struggles":   "free text - what trips them up (drives struggle_keys + lessons)",
      "instruments": "ES and NQ, personal account",
      "recent":      "how it's been going lately",
      "schedule":    "when they trade",
      "name":        "display name (optional)"
    }
"""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime


def _load_service_env(path="/etc/tradewave_realtime/secrets.env"):
    """Load the same EnvironmentFile the live gunicorn service uses, so the harness
    shares the real ANTHROPIC_TOKEN / model config / DATABASE_URL when run directly
    with the venv python. Without this the coach silently drops to demo (no-key)
    mode and maybe_update_summary no-ops, so the harness would not exercise the REAL
    LLM coach. Never clobbers anything already set; silent if the file is absent."""
    if not os.path.exists(path):
        return
    try:
        with open(path) as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(),
                                      val.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_service_env()

from app import create_app  # noqa: E402  (after env load so config picks up the token)
from app.extensions import db  # noqa: E402


# Map the friendly persona "level" to an intake-style experience sentence that
# experience_tier() will classify the same way the real intake answer would.
_LEVEL_TO_EXPERIENCE = {
    "beginner": "I'm brand new, just starting out and learning to trade.",
    "developing": "I'm fairly new, dabbled in stocks but new to futures, about a year in.",
    "experienced": "I've been trading for years, been at this a long time.",
}


def _persona_experience(persona):
    """Resolve the persona into the free-text 'experience' the intake stores.
    A bare level keyword becomes a canonical sentence; anything else is treated
    as the member's own words (so '5 years but new to futures' flows through
    experience_tier untouched)."""
    raw = (persona.get("level") or persona.get("experience") or "").strip()
    return _LEVEL_TO_EXPERIENCE.get(raw.lower(), raw or _LEVEL_TO_EXPERIENCE["developing"])


def cmd_new(args):
    """Create a synthetic test member (User + completed-intake UserProfile),
    filling the profile the way app/mentor.py's intake would, and print the id."""
    from app.models import User, UserProfile
    from app.mentor import (extract_struggles, experience_tier, get_profile,
                            resolve_assignment)

    persona = json.loads(args.persona)
    short = uuid.uuid4().hex[:8]
    email = f"sim_{short}@test.local"

    user = User(email=email,
                display_name=persona.get("name") or f"Sim {short}",
                role="member",
                accepted_ai_disclaimer=True,
                accepted_at=datetime.utcnow())
    user.set_password(uuid.uuid4().hex)
    db.session.add(user)
    db.session.commit()

    profile = get_profile(user)
    profile.experience = _persona_experience(persona)
    profile.goal = persona.get("goal", "")
    profile.recent = persona.get("recent", "")
    profile.schedule = persona.get("schedule", "")

    # instruments + account_type, mirroring intake_answer()'s field handling
    instruments = persona.get("instruments", "")
    profile.instruments = instruments
    low = instruments.lower()
    if any(w in low for w in ("prop", "funded", "combine", "topstep", "apex")):
        profile.account_type = "prop/funded"
    elif any(w in low for w in ("personal", "own", "my account", "cash", "ira")):
        profile.account_type = "personal"

    # struggles -> raw + deterministic keys, exactly like intake
    struggles = persona.get("struggles", "")
    profile.struggles_raw = struggles
    profile.struggles_keys = ",".join(extract_struggles(struggles))

    # Finalize intake the same way intake_answer() does on the last step:
    # build assignment, the summary, and seed the rolling coaching summary so
    # memory is non-empty from day 1.
    keys = [k for k in profile.struggles_keys.split(",") if k]
    tier = experience_tier(profile)
    profile.assigned = resolve_assignment(keys, tier)
    profile.summary = (
        f"Experience: {profile.experience}. Trades: {profile.instruments} "
        f"({profile.account_type or 'account type not stated'}). "
        f"Goal: {profile.goal}. Recently: {profile.recent}. "
        f"Struggles: {profile.struggles_raw}. Schedule: {profile.schedule}.")
    profile.coaching_summary = (
        f"New member, {tier} trader. Goal: {profile.goal[:120]}. "
        f"Watch for: {profile.struggles_raw[:140] or 'no pattern named yet'}. "
        f"Trades: {profile.schedule[:80]}.")[:1200]
    profile.summary_updated_at = datetime.utcnow()
    profile.intake_step = 6
    profile.intake_done = True
    db.session.commit()

    print(f"member id: {user.id}")
    print(f"email:     {email}")
    print(f"tier:      {tier}")
    print(f"struggles: {profile.struggles_keys or '(none matched)'}")
    print("assigned:  " + "; ".join(a["title"] for a in profile.assigned))


def _load_user(user_id):
    from app.models import User
    user = User.query.get(user_id)
    if user is None:
        sys.exit(f"no member with id {user_id} (create one with `new`)")
    return user


def cmd_firstread(args):
    """Run the REAL first_read(profile) - the new-member aha - and print it."""
    from app.mentor import get_profile
    user = _load_user(args.id)
    profile = get_profile(user)
    if not profile.intake_done:
        sys.exit("member has not completed intake")
    from app.llm import first_read
    print(first_read(profile))


def _get_or_create_thread(user):
    from app.models import ChatThread
    thread = (ChatThread.query.filter_by(user_id=user.id)
              .order_by(ChatThread.created_at.desc()).first())
    if thread is None:
        thread = ChatThread(user_id=user.id, title="Sim coaching session")
        db.session.add(thread)
        db.session.commit()
    return thread


def cmd_turn(args):
    """Append the user message to the member's thread, call the REAL coach
    (generate_reply with the live member_context + thread history), then persist
    and print the coach's reply. Mirrors app/chat.py's non-streaming message()
    path including the runtime compliance backstop."""
    from app.models import ChatMessage
    from app.mentor import member_context
    from app.llm import enforce_compliance, generate_reply

    user = _load_user(args.id)
    thread = _get_or_create_thread(user)

    # History is the prior turns, excluding the message we are about to add.
    history = [{"role": m.role, "content": m.content} for m in thread.messages]
    db.session.add(ChatMessage(thread_id=thread.id, role="user", content=args.message))
    db.session.commit()

    reply, used_llm, citations = generate_reply(
        args.message, history=history, member_context=member_context(user))
    reply, tripped, reason = enforce_compliance(reply)

    db.session.add(ChatMessage(thread_id=thread.id, role="assistant",
                               content=reply, used_llm=used_llm,
                               rating=(-1 if tripped else 0)))
    db.session.commit()

    print(f"[used_llm={used_llm} compliance_tripped={tripped}"
          + (f" reason={reason!r}" if tripped else "")
          + (f" citations={[c['title'] for c in citations]}" if citations else "")
          + "]")
    print(reply)


def cmd_addtrade(args):
    """Insert a completed Trade row (money-blind: levels + side + size bucket)
    and run the deterministic grade against the day's map, so trade-debrief
    scenarios can be coached. JSON keys: instrument, side, entry/entry_price,
    exit/exit_price, size_bucket, note, session_date (YYYY-MM-DD, default today)."""
    from app.models import Trade
    from app.marketdata import ET
    user = _load_user(args.id)
    t = json.loads(args.trade)

    sd = t.get("session_date")
    session_date = (datetime.strptime(sd, "%Y-%m-%d").date() if sd
                    else datetime.now(ET).date())
    size = Trade.normalize_size(t.get("size_bucket"))

    trade = Trade(
        user_id=user.id,
        session_date=session_date,
        instrument=(t.get("instrument") or "").strip().upper()[:8],
        side=(t.get("side") or "").strip().lower(),
        entry_price=t.get("entry", t.get("entry_price")),
        exit_price=t.get("exit", t.get("exit_price")),
        size_bucket=size,
        note=(t.get("note") or "")[:600])
    try:
        from app.trades import grade_trade
        trade.grade = grade_trade(trade)
    except Exception as exc:  # grading is an enhancement, never a blocker
        print(f"(grade skipped: {exc})")
    db.session.add(trade)
    db.session.commit()

    print(f"trade id: {trade.id}  {trade.session_date} {trade.instrument} "
          f"{trade.side} entry={trade.entry_price} exit={trade.exit_price} "
          f"size={trade.size_bucket}")
    if trade.grade.get("notes"):
        print("grade notes:")
        for n in trade.grade["notes"]:
            print(f"  - {n}")


def cmd_endsession(args):
    """Call the REAL maybe_update_summary(user) to build/refresh the rolling
    cross-session memory, so the next session has continuity. Forces the time
    cadence (no per-call cap fight) by clearing summary_updated_at first - the
    way an end-of-session would naturally trigger it."""
    from app.mentor import get_profile, maybe_update_summary
    user = _load_user(args.id)
    profile = get_profile(user)
    before = profile.coaching_summary
    # Let the time-cadence trigger fire (>2 days stale OR >=8 new msgs). For a sim
    # session we want it to run now, so age the stamp.
    profile.summary_updated_at = datetime.min
    db.session.commit()
    maybe_update_summary(user)
    db.session.refresh(profile)
    after = profile.coaching_summary
    changed = after != before
    print(f"[summary updated={changed} length={len(after or '')}]")
    print(after or "(empty)")


def cmd_dump(args):
    """Print the full transcript plus the member's current memory summary and
    profile - the whole picture a coach would carry between sessions."""
    from app.models import ChatMessage, ChatThread, Trade
    from app.mentor import experience_tier, get_profile, member_context
    user = _load_user(args.id)
    profile = get_profile(user)

    print("=" * 70)
    print(f"MEMBER {user.id}  <{user.email}>  ({user.display_name})")
    print("=" * 70)
    print("\n--- PROFILE ---")
    print(f"tier:        {experience_tier(profile)}")
    print(f"experience:  {profile.experience}")
    print(f"instruments: {profile.instruments} ({profile.account_type or 'n/a'})")
    print(f"goal:        {profile.goal}")
    print(f"recent:      {profile.recent}")
    print(f"struggles:   [{profile.struggles_keys}] {profile.struggles_raw}")
    print(f"schedule:    {profile.schedule}")
    print("assigned:    " + "; ".join(a["title"] for a in profile.assigned))

    print("\n--- MEMORY SUMMARY (coaching_summary) ---")
    print(profile.coaching_summary or "(empty)")
    print(f"  summarized_upto={profile.summarized_upto} "
          f"updated_at={profile.summary_updated_at}")

    trades = (Trade.query.filter_by(user_id=user.id)
              .order_by(Trade.session_date, Trade.id).all())
    if trades:
        print("\n--- TRADES ---")
        for t in trades:
            print(f"  #{t.id} {t.session_date} {t.instrument} {t.side} "
                  f"entry={t.entry_price} exit={t.exit_price} size={t.size_bucket}")

    print("\n--- TRANSCRIPT ---")
    threads = (ChatThread.query.filter_by(user_id=user.id)
               .order_by(ChatThread.created_at).all())
    n = 0
    for th in threads:
        msgs = (ChatMessage.query.filter_by(thread_id=th.id)
                .order_by(ChatMessage.id).all())
        for m in msgs:
            n += 1
            who = "MEMBER" if m.role == "user" else "COACH "
            print(f"\n[{who}] {m.content}")
    if not n:
        print("(no messages yet)")

    print("\n--- MEMBER_CONTEXT (what the coach actually sees) ---")
    print(member_context(user))


def main():
    parser = argparse.ArgumentParser(
        description="Drive the real TradeWave Realtime coach as a simulated member.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="create a synthetic test member")
    p.add_argument("--persona", required=True, help="persona JSON")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("firstread", help="run first_read(profile) for a member")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_firstread)

    p = sub.add_parser("turn", help="send a member message, get the real coach reply")
    p.add_argument("id", type=int)
    p.add_argument("message")
    p.set_defaults(func=cmd_turn)

    p = sub.add_parser("addtrade", help="insert a completed Trade row")
    p.add_argument("id", type=int)
    p.add_argument("trade", help="trade JSON")
    p.set_defaults(func=cmd_addtrade)

    p = sub.add_parser("endsession", help="build the rolling cross-session memory")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_endsession)

    p = sub.add_parser("dump", help="print transcript + memory summary + profile")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_dump)

    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        args.func(args)


if __name__ == "__main__":
    main()
