"""Screenshots of the new admin split for review. Creates temp demo rows,
shoots as partner / operator / member, cleans up."""
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

from app import create_app
from app.extensions import db
from app.marketdata import ET
from app.models import Appearance, ChatMessage, ChatThread, User, UserProfile

BASE = "http://127.0.0.1:5001"
OUT = "/home/flask/shots"
PW = "tradewave2026"

app = create_app()
with app.app_context():
    # leftovers from any earlier interrupted run
    for old in Appearance.query.filter_by(title="Live drop-in: reading the open together"):
        db.session.delete(old)
    for old in ChatThread.query.filter_by(title="shot thread"):
        db.session.delete(old)
    db.session.commit()
    member = (User.query.join(UserProfile, UserProfile.user_id == User.id)
              .filter(User.role == "member", User.accepted_ai_disclaimer.is_(True),
                      UserProfile.intake_done.is_(True)).order_by(User.id).first())
    appt = Appearance(
        title="Live drop-in: reading the open together", where="Discord",
        starts_at=(datetime.now(ET) + timedelta(days=1)).replace(
            hour=16, minute=30, second=0, microsecond=0)
        .astimezone(tz=None).astimezone(tz=__import__("datetime").timezone.utc)
        .replace(tzinfo=None),
        note="Bring your marked-up chart")
    db.session.add(appt)
    thread = ChatThread(user_id=member.id, title="shot thread")
    db.session.add(thread)
    db.session.flush()
    db.session.add(ChatMessage(
        thread_id=thread.id, role="user",
        content="What does Anne-Marie do when the MOC candle engulfs the whole "
                "afternoon range? Does the stair step still count?"))
    db.session.flush()
    flagged = ChatMessage(
        thread_id=thread.id, role="assistant",
        content="I want you to have her real answer on this one. I've flagged "
                "this for Anne-Marie's next teaching session.",
        rating=-2, reviewed=False)
    db.session.add(flagged)
    db.session.commit()
    appt_id, thread_id, member_email = appt.id, thread.id, member.email


def login(pg, email):
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    summary = pg.locator("details.auth-alt summary")
    if summary.count():  # dev form is collapsed when WorkOS is enabled
        summary.click()
    pg.fill("input[name=email]", email)
    pg.fill("input[name=password]", PW)
    pg.click("form button[type=submit]")
    pg.wait_for_load_state("networkidle")


def shot(pg, path, out, full=True):
    pg.goto(f"{BASE}{path}", wait_until="networkidle")
    pg.wait_for_timeout(500)
    pg.screenshot(path=f"{OUT}/{out}", full_page=full)
    print("->", out)


try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])

        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        login(pg, "anne-marie@thetradingbook.com")
        shot(pg, "/admin/", "admin_her_workspace.png")
        shot(pg, "/admin/schedule", "admin_schedule.png")
        shot(pg, "/admin/reviews", "admin_reviews_queue.png")
        pg.goto(f"{BASE}/admin/reviews", wait_until="networkidle")
        pg.click("text=Answer this")
        pg.wait_for_load_state("networkidle")
        pg.wait_for_timeout(400)
        pg.screenshot(path=f"{OUT}/admin_teach_prefilled.png", full_page=True)
        print("-> admin_teach_prefilled.png")
        ctx.close()

        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        login(pg, "afshin@tradewave.ai")
        shot(pg, "/admin/ops", "admin_ops.png")
        ctx.close()

        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        login(pg, member_email)
        shot(pg, "/app", "today_with_live_card.png")
        ctx.close()
        b.close()
finally:
    with app.app_context():
        a = db.session.get(Appearance, appt_id)
        t = db.session.get(ChatThread, thread_id)
        if a:
            db.session.delete(a)
        if t:
            db.session.delete(t)
        db.session.commit()
        print("cleaned up temp rows")
