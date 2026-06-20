"""The trade debrief (Phase A, chat-first) - the educational flagship.

A member logs a COMPLETED trade (money-blind: price levels + a size bucket, never
dollar P&L or position value). A DETERMINISTIC grader scores it against that day's
published map - was the entry at a map level, with or against the trend gate, did it
respect her fade. The coach then teaches the correction in her voice. Compliance
line: completed round-trips only; the coach is never told about an open position.
"""
import urllib.parse
from datetime import datetime, timedelta

from flask import (Blueprint, flash, redirect, render_template, request, url_for)

from .extensions import db
from .marketdata import ET
from .models import DayMap, Trade
from .security import current_user, disclaimer_required

bp = Blueprint("trades", __name__)


# Micro contracts trade the same chart as their full-size parent, so they grade
# against the parent's map.
_MICRO_ALIAS = {"MES": "ES", "MNQ": "NQ", "MGC": "GC", "MCL": "CL"}


def _map_instrument(instrument):
    return _MICRO_ALIAS.get((instrument or "").upper(), (instrument or "").upper())


def _tolerance(price):
    """How close to a level counts as 'at the level' - a few ticks (~0.02% of
    price, floored at 1pt). Tight on purpose: a mid-range entry must NOT grade
    'at a level', or the grade flatters sloppy entries and an expert stops trusting it."""
    return max(1.0, price * 0.0002)


def _dedupe_levels(levels):
    """Collapse near-coincident levels (prior-day H/L stacking) so a dense cluster
    does not turn most of the range into 'at a level'."""
    out = []
    for lv in sorted(levels, key=lambda x: x["price"]):
        if not out or abs(lv["price"] - out[-1]["price"]) > _tolerance(lv["price"]):
            out.append(lv)
    return out


def _at_level(price, levels):
    """(is_at_level, nearest). At-level requires being within tolerance AND clearly
    closer to the nearest level than to the next one (not stranded between two)."""
    if not levels or not price:
        return None, None
    ordered = sorted(levels, key=lambda lv: abs(lv["price"] - price))
    near = ordered[0]
    d1 = abs(near["price"] - price)
    d2 = abs(ordered[1]["price"] - price) if len(ordered) > 1 else d1 * 99
    at = d1 <= _tolerance(price) and d1 <= 0.6 * d2
    return at, {"price": near["price"], "label": near.get("label", ""), "dist": round(d1, 2)}


def _trend(p):
    """The day's trend authority: trust the SMA GATE over the stair-step verdict
    (they can contradict in the engine). Returns 'up' | 'down' | None (unclear)."""
    gate = ((p.get("sma") or {}).get("gate") or "").lower()
    if gate == "aligned_up":
        return "up"
    if gate == "aligned_down":
        return "down"
    if gate == "stand_down":
        return None
    verdict = (p.get("verdict") or "").lower()  # only if the gate is absent
    if verdict.startswith("up"):
        return "up"
    if verdict.startswith("down"):
        return "down"
    return None


def grade_trade(trade):
    """Deterministic grade of a completed trade against the day's DayMap. Process
    grades + points only - never dollars. Returns a dict the coach teaches from."""
    g = {"at_level": None, "with_trend": None, "exit_at_level": None,
         "size_flag": None, "no_map": False, "notes": []}
    dm = DayMap.query.filter_by(instrument=_map_instrument(trade.instrument),
                                session_date=trade.session_date).first()
    if dm is None or not trade.entry_price:
        g["no_map"] = True
        g["notes"].append("No published map for that instrument/day, so I can talk through "
                          "the process from what you tell me but cannot grade it against the map.")
        return g
    p = dm.payload
    levels = _dedupe_levels([lv for lv in p.get("levels", []) if lv.get("price")])
    at, near = _at_level(trade.entry_price, levels)
    g["at_level"], g["nearest_level"] = at, near
    if near is not None:
        if at:
            g["notes"].append(f"Entry was right at a map level ({near['label'] or 'a level'} "
                              f"~{near['price']:.2f}) - that is exactly making price come to you.")
        else:
            g["notes"].append(f"Entry was {near['dist']:.1f} points from the nearest map level "
                              f"({near['label'] or 'a level'} ~{near['price']:.2f}). She waits "
                              f"for price to reach a level, not the middle.")
    if trade.exit_price:
        xat, _ = _at_level(trade.exit_price, levels)
        g["exit_at_level"] = xat
        g["notes"].append("Exit landed at another map level - level to level, the way she "
                          "exits." if xat else
                          "Exit was not at a clean map level - she targets level to level.")
    # With the trend? One authoritative direction (the gate), so a long and a short
    # at the same price can NEVER both grade 'with trend'.
    trend = _trend(p)
    if trend is None:
        g["notes"].append("The gate was standing down (no clean trend) - her rule there is "
                          "smallest size or no trade, edges only. A directional swing into "
                          "that is fighting a coin flip.")
        if trade.size_bucket in ("normal", "large"):
            g["size_flag"] = True
            g["notes"].append("On an unclear day, normal/large size is the opposite of 'get "
                              "risk small'. That is the lever to fix first.")
    else:
        aligned = (trade.side == "long" and trend == "up") or \
                  (trade.side == "short" and trend == "down")
        g["with_trend"] = aligned
        g["notes"].append("Trade was with the trend gate - dips are buys, bounces are sells."
                          if aligned else
                          "Trade was AGAINST the trend gate. Countertrend is her exception, "
                          "not her bread and butter - it needs a better reason and smaller size.")
    return g


def grade_summary(g):
    """A one-line headline for the trade card."""
    if g.get("no_map"):
        return "No map to grade against that day - let's talk it through."
    wins = sum(1 for k in ("at_level", "with_trend", "exit_at_level")
               if g.get(k) is True)
    flags = sum(1 for k in ("at_level", "with_trend", "exit_at_level")
                if g.get(k) is False) + (1 if g.get("size_flag") else 0)
    if wins and not flags:
        return "Clean process - this is how she trades it."
    if flags >= 2:
        return "A few process leaks to work on - that is where the edge is."
    return "Some of the process held, some slipped - let's tighten it."


# Free tier sees the debrief work, but on a leash: one debrief per rolling week, and
# the summary only (the exact map levels behind each grade are the paid product).
# Paid/staff get unlimited debriefs + the precise grade. Dormant pre-launch because
# is_paid() is True for everyone until BILLING_REQUIRED flips at launch.
FREE_DEBRIEF_DAYS = 7


def next_free_debrief(user):
    """When the user's next FREE debrief unlocks, or None if they can debrief now
    (paid/staff/pre-launch, or no debrief inside the rolling window)."""
    from .billing import is_paid
    if is_paid(user):
        return None
    cutoff = datetime.utcnow() - timedelta(days=FREE_DEBRIEF_DAYS)
    last = (Trade.query
            .filter(Trade.user_id == user.id, Trade.created_at >= cutoff)
            .order_by(Trade.created_at.desc()).first())
    if last is None:
        return None
    return last.created_at + timedelta(days=FREE_DEBRIEF_DAYS)


@bp.route("/app/trades")
@disclaimer_required
def trades_page():
    user = current_user()
    from .billing import is_paid
    rows = (Trade.query.filter_by(user_id=user.id)
            .order_by(Trade.session_date.desc(), Trade.id.desc()).limit(50).all())
    return render_template("app/trades.html", trades=rows, grade_summary=grade_summary,
                           paid=is_paid(user), next_free=next_free_debrief(user))


@bp.route("/app/trades/log", methods=["POST"])
@disclaimer_required
def log_trade():
    """Log one COMPLETED trade (money-blind) and grade it against the day's map."""
    user = current_user()
    unlock = next_free_debrief(user)
    if unlock is not None:
        # Free tier: one debrief a week. Hand over the upsell instead of grading.
        flash("You have used this week's free debrief. A subscription debriefs every "
              "trade and shows the exact map levels behind each grade. Your next free "
              f"debrief unlocks {unlock.strftime('%b %-d')}.", "warn")
        return redirect(url_for("trades.trades_page"))
    from .privacy import scrub_sensitive
    f = request.form

    def _price(name):
        try:
            return float(f.get(name) or 0) or None
        except ValueError:
            return None
    inst = (f.get("instrument") or "ES").strip().upper()[:8]
    side = (f.get("side") or "").strip().lower()
    side = side if side in ("long", "short") else "long"
    size = Trade.normalize_size(f.get("size_bucket"))
    try:
        sd = datetime.strptime(f.get("session_date") or "", "%Y-%m-%d").date()
    except ValueError:
        sd = datetime.now(ET).date()
    t = Trade(user_id=user.id, session_date=sd, instrument=inst, side=side,
              entry_price=_price("entry_price"), exit_price=_price("exit_price"),
              size_bucket=size, note=scrub_sensitive((f.get("note") or "")[:600]))
    t.grade = grade_trade(t)
    db.session.add(t)
    db.session.commit()
    # Hand the member straight to the coach to debrief it in her voice.
    q = (f"Let's debrief my {inst} {side} trade from {sd}. Walk me through what the map "
         f"says about how I traded it.")
    return redirect(url_for("chat.coach") + "?q=" + urllib.parse.quote(q))


def recent_trades_context(user, limit=5):
    """Compact, money-blind trade history for the coach's member_context - the RECEIPTS the
    coach quotes back so it reads as watching, not just listening. Ordered OLDEST-first within
    the latest session and numbered, so the coach can say 'the size jumped on trade two, not
    trade four' and get the sequence right (newest-first list misleads 'first/then' narration).
    """
    rows = (Trade.query.filter_by(user_id=user.id)
            .order_by(Trade.session_date.desc(), Trade.id.desc()).limit(limit).all())
    if not rows:
        return ""
    rows = list(reversed(rows))  # chronological: trade 1, trade 2, ... as the member lived it
    lines = ["- RECENT LOGGED TRADES (money-blind receipts; numbered in the order they were "
             "taken). QUOTE these actual entries/sizes/levels back to the member before relying "
             "on their memory - they are the objective signal. Grade vs that day's map; teach "
             "the process, never dollars, never tell them their next trade:"]
    for i, t in enumerate(rows, 1):
        g = t.grade
        bits = []
        if g.get("at_level") is not None:
            bits.append("at a level" if g["at_level"] else "not at a level")
        if g.get("with_trend") is not None:
            bits.append("with trend" if g["with_trend"] else "against trend")
        if g.get("size_flag"):
            bits.append("oversized for an unclear day")
        if g.get("no_map"):
            bits.append("no map that day to grade against - say so out loud, grade only "
                        "what they describe")
        tag = ", ".join(bits) or "process unclear"
        ep = f"{t.entry_price:.2f}" if t.entry_price else "?"
        xp = f" -> exit ~{t.exit_price:.2f}" if t.exit_price else ""
        lines.append(f"  trade {i}: {t.session_date} {t.instrument} {t.side} (entry ~{ep}{xp}, "
                     f"size {t.size_bucket}): {tag}")
    return "\n".join(lines)
