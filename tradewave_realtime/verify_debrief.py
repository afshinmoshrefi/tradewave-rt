"""Regression guard for the free-tier trade-debrief gate. Run:
    .venv/bin/python verify_debrief.py

Free members get ONE debrief per rolling 7 days; paid/staff/pre-launch are unlimited.
The exact map levels (grade notes) are paid-only - that gate lives in the template and
is exercised by eye, but the access logic (next_free_debrief) is locked here.

Runs against a throwaway temp DB, no network.
"""
import os
import tempfile

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP.name}"

import sys
from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import Trade, User
from app.trades import FREE_DEBRIEF_DAYS, next_free_debrief

P, F = [], []


def ck(n, c):
    (P if c else F).append(n)
    print(("  ok  " if c else "  FAIL") + " " + n)


def _trade(uid, when):
    t = Trade(user_id=uid, session_date=when.date(), instrument="ES", side="long",
              entry_price=5000.0, size_bucket="small")
    db.session.add(t)
    db.session.commit()
    t.created_at = when            # default is utcnow at insert; backdate explicitly
    db.session.commit()
    return t


app = create_app()
with app.app_context():
    db.create_all()
    app.config["BILLING_REQUIRED"] = True   # launch mode: the gate is live

    free = User(email="free@x.com", password_hash="x", role="member")
    staff = User(email="afshin@tradewave.ai", password_hash="x", role="admin")
    db.session.add_all([free, staff])
    db.session.commit()

    ck("free member with no trades can debrief", next_free_debrief(free) is None)

    _trade(free.id, datetime.utcnow())
    unlock = next_free_debrief(free)
    ck("free member is blocked right after a debrief", unlock is not None)
    ck("the block clears ~7 days out",
       bool(unlock) and unlock > datetime.utcnow() + timedelta(days=6))

    Trade.query.filter_by(user_id=free.id).first().created_at = (
        datetime.utcnow() - timedelta(days=FREE_DEBRIEF_DAYS + 1))
    db.session.commit()
    ck("free member unblocked once the window passes", next_free_debrief(free) is None)

    _trade(staff.id, datetime.utcnow())
    ck("staff (paid) is never blocked", next_free_debrief(staff) is None)

    app.config["BILLING_REQUIRED"] = False   # pre-launch: nothing is gated
    _trade(free.id, datetime.utcnow())
    ck("pre-launch (BILLING_REQUIRED off) nobody is blocked",
       next_free_debrief(free) is None)

os.unlink(_TMP.name)
print()
print(f"{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
