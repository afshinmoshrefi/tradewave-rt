"""End-to-end verification of the admin split: roles, schedule, answer-this.

Run: venv/bin/python verify_admin_e2e.py
Creates temporary rows, verifies every flow, cleans up after itself.
"""
import re
import sys
from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db
from app.marketdata import ET
from app.models import (Appearance, ChatMessage, ChatThread, KnowledgeEntry,
                        User)

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("  ok  " if ok else "  FAIL") + f" {name}" + (f"  [{detail}]" if detail and not ok else ""))


app = create_app()


def client_as(user_id):
    c = app.test_client()
    with c.session_transaction() as s:
        s["user_id"] = user_id
    return c


with app.app_context():
    operator = User.query.filter_by(email="afshin@tradewave.ai").first()
    partner = User.query.filter_by(email="anne-marie@thetradingbook.com").first()
    from app.models import UserProfile
    member = (User.query.join(UserProfile, UserProfile.user_id == User.id)
              .filter(User.role == "member",
                      User.accepted_ai_disclaimer.is_(True),
                      UserProfile.intake_done.is_(True))
              .order_by(User.id).first())
    if member is None:  # fall back: any member, the /app check tolerates redirects
        member = User.query.filter(User.role == "member").order_by(User.id).first()
    print(f"operator={operator and operator.email} role={operator and operator.role}")
    print(f"partner ={partner and partner.email} role={partner and partner.role}")
    print(f"member  ={member and member.email} role={member and member.role}")
    if not (operator and partner and member):
        print("missing test users - abort")
        sys.exit(1)
    check("operator.is_admin and is_staff", operator.is_admin and operator.is_staff)
    check("partner.is_staff but NOT is_admin", partner.is_staff and not partner.is_admin)

    # ---------- 1. Role enforcement ----------
    print("\n[1] role enforcement")
    op, pa, me = client_as(operator.id), client_as(partner.id), client_as(member.id)

    r = pa.get("/admin/")
    check("partner GET /admin -> 200", r.status_code == 200, str(r.status_code))
    body = r.get_data(as_text=True)
    check("partner dashboard hides Operations link", "Operations" not in body)

    r = pa.get("/admin/ops")
    check("partner GET /admin/ops -> redirected away", r.status_code == 302
          and "/admin/ops" not in (r.headers.get("Location") or ""),
          f"{r.status_code} -> {r.headers.get('Location')}")

    r = op.get("/admin/ops")
    check("operator GET /admin/ops -> 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        b = r.get_data(as_text=True)
        check("ops shows KPIs + candles table",
              "Accounts" in b or "accounts" in b.lower())

    r = me.get("/admin/", follow_redirects=False)
    check("member GET /admin -> redirected away", r.status_code == 302,
          str(r.status_code))
    r = me.get("/admin/schedule")
    check("member GET /admin/schedule -> redirected away", r.status_code == 302,
          str(r.status_code))

    # ---------- 2. Schedule flow (as the partner - her workflow) ----------
    print("\n[2] schedule: form -> list -> Today card -> coach context")
    tomorrow_et = (datetime.now(ET) + timedelta(days=1)).replace(
        hour=16, minute=30, second=0, microsecond=0)
    r = pa.post("/admin/schedule", data={
        "title": "E2E test drop-in", "where": "Discord",
        "date": tomorrow_et.strftime("%Y-%m-%d"),
        "time": tomorrow_et.strftime("%H:%M"),
        "note": "verification row"}, follow_redirects=True)
    check("partner POST /admin/schedule -> ok", r.status_code == 200,
          str(r.status_code))
    appt = Appearance.query.filter_by(title="E2E test drop-in").first()
    check("appearance row created", appt is not None)
    if appt:
        # stored UTC, displayed ET
        stored = appt.starts_at.replace(tzinfo=timezone.utc).astimezone(ET)
        check("stored UTC converts back to the ET the form sent",
              stored.strftime("%Y-%m-%d %H:%M") == tomorrow_et.strftime("%Y-%m-%d %H:%M"),
              f"stored->{stored} form->{tomorrow_et}")
        check("starts_at_et human string looks right",
              "4:30 PM ET" in appt.starts_at_et, appt.starts_at_et)
        b = pa.get("/admin/schedule").get_data(as_text=True)
        check("schedule page lists it", "E2E test drop-in" in b)

    # member Today page shows the live card
    r = me.get("/app", follow_redirects=True)
    b = r.get_data(as_text=True)
    check("member /app (Today) -> 200", r.status_code == 200, str(r.status_code))
    check("Today shows Anne-Marie live card", "E2E test drop-in" in b)
    check("Today card shows ET time", "4:30 PM ET" in b)

    # coach context cites it (the ONLY sanctioned schedule source)
    from app.levels import now_context
    nc = now_context()
    check("now_context mentions the appearance", "E2E test drop-in" in nc)
    check("now_context keeps the never-promise guard",
          "never promise" in nc.lower())

    # ---------- 3. Answer-this loop ----------
    print("\n[3] answer-this: deferral -> queue -> teach prefill -> publish -> handled")
    thread = ChatThread(user_id=member.id, title="E2E verify thread")
    db.session.add(thread)
    db.session.flush()
    q = ChatMessage(thread_id=thread.id, role="user",
                    content="My name is Bob Smith and I lost $4,500 on ES. "
                            "What does Anne-Marie do when the MOC candle "
                            "engulfs the whole afternoon?")
    db.session.add(q)
    db.session.flush()
    a = ChatMessage(thread_id=thread.id, role="assistant",
                    content="That's a great question and I want you to have her real answer. "
                            "I've flagged this for Anne-Marie's next teaching session.",
                    rating=-2, reviewed=False)
    db.session.add(a)
    db.session.commit()
    flag_id = a.id

    b = pa.get("/admin/reviews").get_data(as_text=True)
    check("reviews queue shows the deferral", "MOC candle" in b)
    check("labeled couldn't answer", "couldn" in b)
    check("member question anonymized (no name)", "Bob Smith" not in b)
    check("member question anonymized (no dollar amount)", "4,500" not in b and "4500" not in b)
    check("Answer this button targets teach?flag_id", f"flag_id={flag_id}" in b)

    b = pa.get(f"/admin/teach?flag_id={flag_id}").get_data(as_text=True)
    check("teach prefills topic from sanitized question", "MOC candle" in b)
    check("teach topic also anonymized", "Bob Smith" not in b)
    m = re.search(r'name="flag_id" value="(\d+)"', b)
    check("teach form carries flag_id forward", bool(m) and m.group(1) == str(flag_id))

    r = pa.post("/admin/teach/publish", data={
        "flag_id": str(flag_id),
        "title": "E2E verify lesson - engulfing MOC",
        "category": "method", "stage": "0",
        "content": "Test lesson body for verification.",
        "source_quote": "verbatim words here"}, follow_redirects=True)
    check("publish -> ok", r.status_code == 200, str(r.status_code))
    entry = KnowledgeEntry.query.filter_by(title="E2E verify lesson - engulfing MOC").first()
    check("knowledge entry created", entry is not None)
    if entry:
        check("provenance=her_words status=approved published",
              entry.provenance == "her_words" and entry.status == "approved"
              and entry.published)
    db.session.refresh(a)
    check("flagged message marked reviewed", a.reviewed is True)
    b = pa.get("/admin/reviews").get_data(as_text=True)
    check("queue item gone after publish", f"flag_id={flag_id}" not in b)

    # the published lesson reaches the coach corpus
    from app.llm import method_corpus
    check("published lesson lands in coach corpus",
          "engulfing MOC" in method_corpus())

    # ---------- 3.5 Role manager (operator assigns who sees what) ----------
    print("\n[3.5] role manager on /admin/ops")
    target = (User.query.filter(User.role == "member", User.id != member.id)
              .order_by(User.id.desc()).first()) or member
    orig_role = target.role
    try:
        b = op.get("/admin/ops").get_data(as_text=True)
        check("ops lists people with role dropdowns", target.email in b
              and "People &amp; roles" in b)
        # partner may NOT assign roles
        r = pa.post(f"/admin/ops/users/{target.id}/role", data={"role": "partner"})
        db.session.refresh(target)
        check("partner POST role -> redirected, role unchanged",
              r.status_code == 302 and target.role == orig_role,
              f"{r.status_code} role={target.role}")
        # operator promotes member -> partner
        r = op.post(f"/admin/ops/users/{target.id}/role", data={"role": "partner"},
                    follow_redirects=True)
        db.session.refresh(target)
        check("operator promotes member to partner",
              r.status_code == 200 and target.role == "partner"
              and target.is_staff and not target.is_admin,
              f"role={target.role}")
        # promoted partner can now open the workspace
        b = client_as(target.id).get("/admin/")
        check("newly promoted partner reaches /admin", b.status_code == 200,
              str(b.status_code))
        # operator demotes back
        op.post(f"/admin/ops/users/{target.id}/role", data={"role": "member"})
        db.session.refresh(target)
        check("operator demotes back to member", target.role == "member")
        # invalid role rejected
        op.post(f"/admin/ops/users/{target.id}/role", data={"role": "root"})
        db.session.refresh(target)
        check("invalid role value rejected", target.role == "member")
        # operator cannot change own role (lockout guard)
        op.post(f"/admin/ops/users/{operator.id}/role", data={"role": "member"})
        db.session.refresh(operator)
        check("operator self-change blocked", operator.role == "admin")
    finally:
        if target.role != orig_role:
            target.role = orig_role
            db.session.commit()

    # ---------- 4. Partner sees her workspace, not raw ops ----------
    print("\n[4] dashboard content")
    b = pa.get("/admin/").get_data(as_text=True)
    check("dashboard: insight composer present", "Today's insight" in b)
    check("dashboard: schedule card present", "Your schedule" in b)
    check("dashboard: questions-for-you counter present", "Questions for you" in b)
    r_op = op.get("/admin/", follow_redirects=False)
    check("operator /admin lands in Operations (role-aware front door)",
          r_op.status_code == 302 and "/admin/ops" in (r_op.headers.get("Location") or ""),
          f"{r_op.status_code} -> {r_op.headers.get('Location')}")
    b_op = op.get("/admin/?workspace=1").get_data(as_text=True)
    check("operator can still open her workspace explicitly",
          "Today's insight" in b_op)
    b_ops = op.get("/admin/ops").get_data(as_text=True)
    check("ops page links back to her workspace", "workspace=1" in b_ops)

    # ---------- cleanup ----------
    print("\n[cleanup]")
    if appt:
        db.session.delete(appt)
    if entry:
        db.session.delete(entry)
    db.session.delete(thread)  # cascades messages
    db.session.commit()
    from app.rag import rebuild_index
    rebuild_index()
    check("cleanup: appearance gone",
          Appearance.query.filter_by(title="E2E test drop-in").first() is None)
    check("cleanup: lesson gone",
          KnowledgeEntry.query.filter_by(title="E2E verify lesson - engulfing MOC").first() is None)
    check("cleanup: corpus no longer has test lesson",
          "engulfing MOC" not in method_corpus())

print(f"\n{'='*50}\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("ALL CHECKS PASSED")
