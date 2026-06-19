"""Regression guard for the Stripe webhook hardening (MEDIUM-7). Run:
    .venv/bin/python verify_billing.py

Covers: int(rt_user_id) is guarded (a non-numeric value never raises -> never 500s
into a Stripe retry loop), an unresolved-but-RT subscription is handled without
minting a row, the EOD/shared-account filter still excludes non-RT subs, the dahlia
current_period_end (subscription-item) shape is read, and the API version is pinned.

Runs against a throwaway temp DB and fully mocked Stripe calls, so it never touches
the live data file or the network.
"""
import os
import tempfile

# Point the app at a throwaway DB BEFORE it loads config, so create_all/queries here
# can never hit data/tradewave_rt.db. A dummy secret key keeps _stripe() happy.
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP.name}"
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy")

import sys

import stripe

from app import create_app
from app.extensions import db
from app.models import Subscription, User
import app.billing as billing

P, F = [], []


def ck(n, c):
    (P if c else F).append(n)
    print(("  ok  " if c else "  FAIL") + " " + n)


def _rt_sub(**over):
    """A minimal dahlia-shaped RT subscription dict (current_period_end on the item)."""
    return {
        "id": over.get("id", "sub_rt1"),
        "customer": over.get("customer", "cus_known"),
        "status": over.get("status", "active"),
        "metadata": over.get("metadata", {"product_line": "rt", "rt_user_id": "1"}),
        "items": {"data": [{
            "price": {"id": "price_x", "lookup_key": "rt_founding_monthly",
                      "metadata": {"product_line": "rt", "founding": "true"}},
            "current_period_end": over.get("period_end", 4102444800),  # ~2100
        }]},
    }


def _serve(sub):
    """Make billing._stripe().Subscription.retrieve(...) return `sub` with no network."""
    stripe.Subscription.retrieve = lambda _id, **kw: sub


def _raises(fn):
    try:
        fn()
        return False
    except Exception:
        return True


app = create_app()
with app.app_context():
    db.create_all()
    u = User(email="m@example.com", password_hash="x", role="member",
             stripe_customer_id="cus_known")
    db.session.add(u)
    db.session.commit()
    uid = u.id

    # _stripe() must apply the pinned API version (and not raise).
    ck("config pins STRIPE_API_VERSION", bool(app.config.get("STRIPE_API_VERSION")))
    billing._stripe()
    ck("_stripe() applies the pinned api_version",
       stripe.api_version == app.config["STRIPE_API_VERSION"])

    # 1) Non-numeric rt_user_id must NOT raise; resolution falls back to the customer.
    _serve(_rt_sub(id="sub_badid", metadata={"product_line": "rt", "rt_user_id": "oops"}))
    ck("non-numeric rt_user_id does not raise",
       not _raises(lambda: billing._sync_subscription("sub_badid")))
    row = Subscription.query.filter_by(stripe_subscription_id="sub_badid").first()
    ck("non-numeric rt_user_id still resolves via customer lookup",
       row is not None and row.user_id == uid)
    ck("dahlia item-shaped current_period_end is read",
       row is not None and row.current_period_end is not None)

    # 2) Numeric rt_user_id resolves directly (the happy path still works).
    _serve(_rt_sub(id="sub_good", metadata={"product_line": "rt", "rt_user_id": str(uid)}))
    billing._sync_subscription("sub_good")
    ck("numeric rt_user_id resolves to the right member",
       (Subscription.query.filter_by(stripe_subscription_id="sub_good").first() or
        Subscription(user_id=-1)).user_id == uid)

    # 3) Unresolved RT sub (unknown customer, no rt_user_id) -> no raise, no row minted.
    _serve(_rt_sub(id="sub_orphan", customer="cus_unknown",
                   metadata={"product_line": "rt"}))
    ck("unresolved RT sub does not raise",
       not _raises(lambda: billing._sync_subscription("sub_orphan")))
    ck("unresolved RT sub mints no entitlement row",
       Subscription.query.filter_by(stripe_subscription_id="sub_orphan").first() is None)

    # 4) The shared-account EOD filter still drops non-RT subs.
    _serve({"id": "sub_eod", "customer": "cus_known", "status": "active",
            "metadata": {"product_line": "eod"},
            "items": {"data": [{"price": {"id": "p", "lookup_key": "eod_monthly",
                                          "metadata": {"product_line": "eod"}}}]}})
    billing._sync_subscription("sub_eod")
    ck("non-RT (EOD) subscription is ignored",
       Subscription.query.filter_by(stripe_subscription_id="sub_eod").first() is None)

    # 5) past_due 7-day grace. Use a fresh member so no other active sub masks it.
    from datetime import datetime as _dt, timedelta as _td
    u2 = User(email="pd@example.com", password_hash="x", role="member",
              stripe_customer_id="cus_pd")
    db.session.add(u2)
    db.session.commit()
    uid2 = u2.id

    def _pd_sub(status):
        return _rt_sub(id="sub_pd", customer="cus_pd", status=status,
                       metadata={"product_line": "rt", "rt_user_id": str(uid2)})

    _serve(_pd_sub("active"))
    billing._sync_subscription("sub_pd")
    ck("fresh active member is entitled", billing.active_subscription(u2) is not None)

    _serve(_pd_sub("past_due"))
    billing._sync_subscription("sub_pd")
    pd = Subscription.query.filter_by(stripe_subscription_id="sub_pd").first()
    ck("entering past_due stamps past_due_since", pd.past_due_since is not None)
    ck("past_due within grace is still entitled", billing.active_subscription(u2) is not None)

    pd.past_due_since = _dt.utcnow() - _td(days=8)   # backdate beyond the 7-day window
    db.session.commit()
    ck("past_due beyond 7 days is NOT entitled", billing.active_subscription(u2) is None)
    ck("is_active reflects the expired grace", pd.is_active is False)

    _serve(_pd_sub("active"))                          # card recovers
    billing._sync_subscription("sub_pd")
    pd = Subscription.query.filter_by(stripe_subscription_id="sub_pd").first()
    ck("recovery to active clears past_due_since", pd.past_due_since is None)
    ck("recovered member is entitled again", billing.active_subscription(u2) is not None)

os.unlink(_TMP.name)
print()
print(f"{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
