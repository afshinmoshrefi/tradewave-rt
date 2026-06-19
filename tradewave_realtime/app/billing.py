"""Stripe billing - RT's own products, cleanly separable for the Anne-Marie statement.

Products/prices carry product_line=rt metadata and lookup keys, so Net RT Revenue
(gross minus processing fees, refunds, chargebacks, sales tax) can be computed
straight off Stripe for her monthly 35% statement. One tier: $99/mo founding
(lock while continuously subscribed) or $990/yr founding annual.

BILLING_REQUIRED stays off until launch: members keep free access; checkout works
end to end in test mode so the whole flow is rehearsed before the flip.
"""
from datetime import datetime

import stripe
from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)

from .extensions import db
from .models import Subscription, User
from .security import current_user, login_required

bp = Blueprint("billing", __name__)

PLANS = {
    "monthly": {"lookup_key": "rt_founding_monthly", "amount": 9900,
                "interval": "month", "label": "Founding monthly - $99/mo"},
    "annual": {"lookup_key": "rt_founding_annual", "amount": 99000,
               "interval": "year", "label": "Founding annual - $990/yr (2 months free)"},
}


def _stripe():
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    # Pin the API version (config default tracks the installed lib) so retrieve()
    # and the webhook payloads keep the shape this module is written against.
    api_version = current_app.config.get("STRIPE_API_VERSION")
    if api_version:
        stripe.api_version = api_version
    return stripe


def billing_enabled():
    return bool(current_app.config.get("STRIPE_SECRET_KEY"))


def ensure_products():
    """Idempotently create the RT product + founding prices. Returns lookup->price_id."""
    s = _stripe()
    found = {p.lookup_key: p.id
             for p in s.Price.list(lookup_keys=[v["lookup_key"] for v in PLANS.values()],
                                   limit=10).data}
    if len(found) == len(PLANS):
        return found
    products = s.Product.search(query="metadata['product_line']:'rt'", limit=1)
    if products.data:
        product = products.data[0]
    else:
        product = s.Product.create(
            name="TradeWave Realtime",
            description="Anne-Marie Baiynd's daily level map, AI coach, and method "
                        "curriculum. Educational only.",
            metadata={"product_line": "rt"})
    for plan, spec in PLANS.items():
        if spec["lookup_key"] in found:
            continue
        price = s.Price.create(
            product=product.id, unit_amount=spec["amount"], currency="usd",
            recurring={"interval": spec["interval"]},
            lookup_key=spec["lookup_key"],
            metadata={"product_line": "rt", "founding": "true", "plan": plan})
        found[spec["lookup_key"]] = price.id
    return found


def _get_or_create_customer(user):
    s = _stripe()
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = s.Customer.create(email=user.email,
                                 name=user.display_name or None,
                                 metadata={"rt_user_id": str(user.id),
                                           "product_line": "rt"})
    user.stripe_customer_id = customer.id
    db.session.commit()
    return customer.id


def active_subscription(user):
    if user is None:
        return None
    # ACTIVE_STATUSES narrows cheaply in SQL; is_active is the authoritative check -
    # it applies the past_due grace window, which SQL cannot express portably.
    for sub in (Subscription.query
                .filter(Subscription.user_id == user.id,
                        Subscription.status.in_(Subscription.ACTIVE_STATUSES))
                .order_by(Subscription.created_at.desc()).all()):
        if sub.is_active:
            return sub
    return None


def map_access(user):
    """THE web paywall: 'full' (see today's level NUMBERS + indicator + debrief) or
    'gated' (the read/day-type only, numbers locked). Wired to BILLING_REQUIRED so it
    is dormant pre-launch and activates at launch. A free member gets ONE full real map
    on their signup day (the proof we deliver what we promise), gated thereafter."""
    if user is None:
        return "gated"
    if user.is_staff:
        return "full"
    if not current_app.config.get("BILLING_REQUIRED"):
        return "full"                       # pre-launch: nothing gated yet
    if active_subscription(user):
        return "full"
    from datetime import datetime
    from .marketdata import ET
    if user.created_at and user.created_at.date() == datetime.now(ET).date():
        return "full"                       # free tier: the one-time signup-day proof
    return "gated"


def is_paid(user):
    """True if the member has unlocked the paid product (active sub, staff, or pre-launch)."""
    if user is None:
        return False
    return bool(user.is_staff
                or not current_app.config.get("BILLING_REQUIRED")
                or active_subscription(user))


@bp.route("/billing/checkout", methods=["POST"])
@login_required
def checkout():
    if not billing_enabled():
        flash("Billing isn't configured yet.", "warn")
        return redirect(url_for("main.account"))
    plan = request.form.get("plan", "monthly")
    if plan not in PLANS:
        plan = "monthly"
    user = current_user()
    if active_subscription(user):
        flash("You already have an active subscription.", "ok")
        return redirect(url_for("main.account"))
    s = _stripe()
    prices = ensure_products()
    sess = s.checkout.Session.create(
        mode="subscription",
        customer=_get_or_create_customer(user),
        line_items=[{"price": prices[PLANS[plan]["lookup_key"]], "quantity": 1}],
        allow_promotion_codes=True,
        subscription_data={"metadata": {"product_line": "rt", "founding": "true",
                                        "rt_user_id": str(user.id)}},
        success_url=url_for("main.account", _external=True) + "?subscribed=1",
        cancel_url=url_for("main.account", _external=True),
        metadata={"rt_user_id": str(user.id), "plan": plan},
    )
    return redirect(sess.url, code=303)


@bp.route("/billing/portal", methods=["POST"])
@login_required
def portal():
    user = current_user()
    if not (billing_enabled() and user.stripe_customer_id):
        return redirect(url_for("main.account"))
    s = _stripe()
    sess = s.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=url_for("main.account", _external=True))
    return redirect(sess.url, code=303)


@bp.route("/billing/webhook", methods=["POST"])
def webhook():
    secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        return jsonify({"error": "webhook not configured"}), 400
    try:
        event = stripe.Webhook.construct_event(
            request.get_data(), request.headers.get("Stripe-Signature", ""), secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify({"error": "bad signature"}), 400

    kind = event["type"]
    obj = event["data"]["object"]
    if kind == "checkout.session.completed" and _sg(obj, "subscription"):
        _sync_subscription(_sg(obj, "subscription"))
    elif kind in ("customer.subscription.created", "customer.subscription.updated",
                  "customer.subscription.deleted"):
        _sync_subscription(obj["id"])
    return jsonify({"received": True})


def _sg(obj, key, default=None):
    """Safe getter for stripe v15 objects (bracket access only, no dict.get)."""
    try:
        value = obj[key]
    except (KeyError, TypeError):
        return default
    return default if value is None else value


def _is_rt_subscription(sub):
    """The Stripe account is shared with TradeWave EOD, so this endpoint receives
    EVERY product's subscription events. Mirror only our own product line - without
    this check, an EOD purchase by a shared customer would mint a free RT
    subscription (is_active gates the member area)."""
    if _sg(_sg(sub, "metadata") or {}, "product_line") == "rt":
        return True
    for item in (_sg(_sg(sub, "items") or {}, "data") or []):
        price = _sg(item, "price")
        if not price:
            continue
        if _sg(_sg(price, "metadata") or {}, "product_line") == "rt":
            return True
        if (_sg(price, "lookup_key") or "").startswith("rt_"):
            return True
    return False


def _sync_subscription(subscription_id):
    """Mirror one Stripe subscription into the local table (idempotent)."""
    s = _stripe()
    sub = s.Subscription.retrieve(subscription_id)
    if not _is_rt_subscription(sub):
        current_app.logger.info("webhook: ignoring non-RT subscription %s",
                                subscription_id)
        return
    user = None
    rt_user_id = _sg(_sg(sub, "metadata") or {}, "rt_user_id")
    if rt_user_id:
        # int() is unguarded no longer: a non-numeric metadata value (hand-edited
        # sub, bad import) must not raise -> 500 -> Stripe retries forever. Fall
        # through to the customer lookup instead.
        try:
            user = User.query.get(int(rt_user_id))
        except (TypeError, ValueError):
            current_app.logger.error(
                "webhook: non-numeric rt_user_id %r on RT sub %s; using customer lookup",
                rt_user_id, subscription_id)
    if user is None:
        user = User.query.filter_by(stripe_customer_id=_sg(sub, "customer")).first()
    if user is None:
        # An RT (paying) subscription we cannot tie to a local account: the member
        # gets NO entitlement and real revenue is on Anne-Marie's statement. Scream
        # at error level (journalctl -p err) so it is not lost in the access log.
        current_app.logger.error(
            "webhook: UNRESOLVED RT subscription %s (customer=%s, rt_user_id=%r) - paying "
            "customer has no local account/entitlement. MANUAL REVIEW REQUIRED.",
            subscription_id, _sg(sub, "customer"), rt_user_id)
        return
    items = sub["items"]["data"]
    item = items[0] if items else None
    price = item["price"] if item else None
    lookup = _sg(price, "lookup_key", "") if price else ""
    plan = "annual" if "annual" in lookup else "monthly"
    row = Subscription.query.filter_by(stripe_subscription_id=sub["id"]).first()
    if row is None:
        row = Subscription(user_id=user.id, stripe_subscription_id=sub["id"])
        db.session.add(row)
    row.user_id = user.id
    row.price_id = _sg(price, "id") or row.price_id if price else row.price_id
    row.plan = plan
    new_status = sub["status"]
    # Stamp when the card first fails so the grace window can be measured; clear it
    # the moment Stripe recovers (or the sub ends) so a later failure starts fresh.
    if new_status == "past_due":
        if row.past_due_since is None:
            row.past_due_since = datetime.utcnow()
    else:
        row.past_due_since = None
    row.status = new_status
    row.founding = _sg(_sg(price, "metadata") or {}, "founding", "true") == "true" if price else True
    period_end = (_sg(item, "current_period_end") if item else None) or _sg(sub, "current_period_end")
    if period_end:
        row.current_period_end = datetime.utcfromtimestamp(period_end)
    db.session.commit()
