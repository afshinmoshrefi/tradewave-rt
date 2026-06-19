"""Regression guard for the UX-gap fixes (G1-G15). Run: .venv/bin/python verify_ux_fixes.py"""
import re
import sys
from datetime import date, datetime

from app import create_app
from app.marketdata import ET, session_state, is_session_day, next_session_date
from app.mentor import (experience_tier, extract_struggles, resolve_assignment,
                        foundation_lessons)
from app.models import UserProfile

P, F = [], []
def ck(n, c):
    (P if c else F).append(n)
    print(("  ok  " if c else "  FAIL") + " " + n)

app = create_app()
with app.app_context():
    # G1 - the airplane: holiday is closed, holiday-aware next session
    ck("G1 Jul 3 holiday reads CLOSED", not session_state(datetime(2026,7,3,11,0,tzinfo=ET))["open"])
    ck("G1 holiday named", session_state(datetime(2026,7,3,11,0,tzinfo=ET))["holiday"]=="Independence Day")
    ck("G1 Jul 3 not a session day", not is_session_day(date(2026,7,3)))
    ck("G1 next session after Jul 2 skips holiday+wknd -> Jul 6",
       next_session_date(date(2026,7,2))==date(2026,7,6))
    # G10 - Friday 4:30pm fixed (closed, points to Monday)
    fri = session_state(datetime(2026,6,26,16,30,tzinfo=ET))
    ck("G10 Friday 4:30pm reads closed", not fri["open"] and fri["next_session"]==date(2026,6,29))
    # G11 - check-in 'closed' on weekend/holiday
    ck("G11 Saturday checkin=closed", session_state(datetime(2026,6,27,10,0,tzinfo=ET))["checkin"]=="closed")
    ck("G11 holiday checkin=closed", session_state(datetime(2026,7,3,10,0,tzinfo=ET))["checkin"]=="closed")
    # G4 - tier classifier + foundations
    def tier(e): p=UserProfile(experience=e); return experience_tier(p)
    ck("G4 'brand new' -> beginner", tier("I am brand new, never traded")=="beginner")
    ck("G4 'new to futures' -> developing (not missed)", tier("dabbled in stocks, new to futures")=="developing")
    ck("G4 '7 years mostly green' -> experienced", tier("7 years, mostly green")=="experienced")
    ck("G4 'two years on and off' -> developing (not experienced)", tier("two years on and off")=="developing")
    ck("G4 foundations track exists (7)", len(foundation_lessons())==7)
    beg = resolve_assignment([], "beginner")
    ck("G4 beginner assigned foundations first", any("chart and a candle" in a["title"] for a in beg))
    exp = resolve_assignment(extract_struggles("revenge trade and blow my daily limit"),"experienced")
    ck("G4 experienced NOT assigned foundations", not any("chart and a candle" in a["title"] for a in exp))
    # G8 - struggle parsing keeps the account-critical struggle
    rk = extract_struggles("I revenge trade after a red trade and blow my daily limit")
    ck("G8 Renee gets revenge AND sizing", "revenge" in rk and "sizing" in rk)
    tk = extract_struggles("fear, I hesitate, and I oversize to make it back")
    ck("G8 Tom keeps revenge (priority-ordered)", rk[0]=="revenge" and "revenge" in tk)

    # ---------- ROUND 2 (residual gaps caught by the 12-persona re-run) ----------
    from datetime import datetime, date, timedelta
    from app.marketdata import session_state, ET
    from app.mentor import resolve_assignment
    from app.trades import grade_trade, grade_summary, _trend, _at_level, _map_instrument
    from app.models import Trade, DayMap

    # R2 tier: bare multi-year counts must NOT fall to beginner/developing-down
    def tier(e):
        from app.models import UserProfile; return experience_tier(UserProfile(experience=e))
    ck("R2 '7 years' -> experienced", tier("I have been trading 7 years")=="experienced")
    ck("R2 '8 years' -> experienced", tier("8 years")=="experienced")
    ck("R2 'about three years, prop account' -> experienced", tier("about three years, prop account")=="experienced")
    ck("R2 'stocks for years, serious about futures' -> experienced",
       tier("been trading stocks for years, getting serious about futures now")=="experienced")
    ck("R2 '7 years, ups and downs' -> experienced (results != newness)",
       tier("seven years, ups and downs")=="experienced")
    ck("R2 'two years on and off' -> developing (unchanged)", tier("two years on and off")=="developing")
    ck("R2 '5 years but new to futures' -> developing (newness demotes)",
       tier("5 years in stocks but new to futures")=="developing")
    ck("R2 'brand new' -> beginner (unchanged)", tier("I am brand new, never traded")=="beginner")

    # R2 assignment: developing with 2 struggles must KEEP the sizing lesson
    rdev = resolve_assignment(extract_struggles("revenge trade and blow my daily limit"), "developing")
    ck("R2 developing keeps sizing lesson (no truncation)",
       any("Risk and position sizing" in a["title"] or "Get risk small" in a["title"] for a in rdev))
    ck("R2 developing keeps revenge lesson too",
       any("Fear, FOMO" in a["title"] for a in rdev))

    # R2 overwhelm key
    ck("R2 overwhelm parsed", "overwhelm" in extract_struggles("I feel overwhelmed and confused by the numbers"))

    # R1 grader: mid-range entry NOT at level; long+short not both with-trend; MES alias; no-map
    dm = DayMap.query.filter_by(instrument="ES").order_by(DayMap.session_date.desc()).first()
    levels = [lv for lv in dm.payload.get("levels", []) if lv.get("price")]
    lv_prices = sorted(p["price"] for p in levels)
    # a price exactly between two adjacent levels = mid-range, must NOT grade at_level
    if len(lv_prices) >= 2:
        mid = (lv_prices[0] + lv_prices[1]) / 2 if (lv_prices[1]-lv_prices[0])>4 else (lv_prices[0]+lv_prices[-1])/2
        at, _ = _at_level(mid, levels)
        ck("R1 mid-range entry NOT graded at_level", at is False or at is None)
    sd = dm.session_date
    tl = Trade(user_id=1, session_date=sd, instrument="ES", side="long",
               entry_price=lv_prices[0], exit_price=lv_prices[0]+5, size_bucket="small")
    ts = Trade(user_id=1, session_date=sd, instrument="ES", side="short",
               entry_price=lv_prices[0], exit_price=lv_prices[0]-5, size_bucket="small")
    gl, gs = grade_trade(tl), grade_trade(ts)
    ck("R1 long & short at one price NOT both with_trend",
       not (gl["with_trend"] is True and gs["with_trend"] is True))
    tm = Trade(user_id=1, session_date=sd, instrument="MES", side="long",
               entry_price=lv_prices[0], exit_price=lv_prices[0]+5, size_bucket="smallest")
    gm = grade_trade(tm)
    ck("R1 MES grades against the ES map (alias)", gm["no_map"] is False and gm["at_level"] is not None)
    ck("R1 _map_instrument MES->ES", _map_instrument("MES")=="ES" and _map_instrument("MNQ")=="NQ")
    tn = Trade(user_id=1, session_date=date(2099,1,1), instrument="ZZ", side="long", entry_price=100.0)
    gn = grade_trade(tn)
    ck("R1 no-map summary does not overclaim", gn["no_map"] and "No map" in grade_summary(gn))

    # R3 Friday-after-close is its own phase (keeps debrief offer), still closed
    fri = session_state(datetime(2026,6,26,16,30,tzinfo=ET))
    ck("R3 Friday 4:30pm phase=after_close_preweekend (not weekend)",
       fri["phase"]=="after_close_preweekend" and not fri["open"])

    # R4 early-close clock: Nov 27 2026 (half day) 2pm must read CLOSED
    ec = session_state(datetime(2026,11,27,14,0,tzinfo=ET))
    ck("R4 early-close Nov 27 2pm reads CLOSED (not open)", not ec["open"])

    # ---------- ROUND 3 (the aha + the web paywall) ----------
    from datetime import datetime as _dt
    from app.billing import map_access
    from app.llm import first_read, first_read_ok
    from app.levels import scrub_levels, today_context
    from app.models import User
    from flask import current_app
    # paywall: gate is wired to BILLING_REQUIRED, with the signup-day free proof
    class U:  # transient stand-in (no sub) for the no-DB branches
        is_staff=False
        def __init__(self, days): self.id=-1; self.role="member"; self.created_at=_dt.utcnow()-timedelta(days=days)
    cfg=current_app.config
    cfg["BILLING_REQUIRED"]=False
    ck("paywall dormant pre-launch (BILLING_REQUIRED off) -> full", map_access(U(7))=="full")
    cfg["BILLING_REQUIRED"]=True
    ck("paywall: free signup-day -> full (the proof)", map_access(U(0))=="full")
    ck("paywall: free week-old -> gated", map_access(U(7))=="gated")
    staff=User(role="admin"); staff.id=-2
    ck("paywall: staff -> full", map_access(staff)=="full")
    cfg["BILLING_REQUIRED"]=False  # restore dev default
    # scrub: hides a price, keeps a year
    ck("scrub_levels hides a price", "a level" in scrub_levels("watch 7645.25 above") and "7645" not in scrub_levels("watch 7645.25 above"))
    ck("scrub_levels keeps a year", "2026" in scrub_levels("the 2026 session"))
    ck("gated coach context has NO level price", not re.search(r"\d{4,6}\.\d", today_context(gated=True)))
    ck("full coach context HAS level prices", bool(re.search(r"\d{4,6}\.\d", today_context(gated=False))))
    # first_read compliance lint
    ck("first_read_ok rejects a price number", not first_read_ok("her method says 7645.25 is key")[0])
    ck("first_read_ok rejects 'you should buy'", not first_read_ok("by her method you should buy here")[0])
    ck("first_read_ok requires her-method attribution", not first_read_ok("today is a stand-down day, sit tight")[0])
    ck("first_read_ok passes a clean read", first_read_ok("Her method reads today as a stand-down day. Her rule: a zero-trade day is a win.")[0])

print(f"\n{len(P)} passed, {len(F)} failed")
if F: print("FAILED:", ", ".join(F))
sys.exit(1 if F else 0)
