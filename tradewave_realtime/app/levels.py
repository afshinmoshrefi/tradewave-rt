"""The levels engine - Anne-Marie's Daily Level Map, computed mechanically.

Method source: /home/flask/baiynd_autotrader/video_transcripts/ (verbatim-quoted rules).
- Master candles (30m, ET): institutional 3:30pm (prior session), Globex open 6pm,
  Europe open 4am, US open 9:30am; plus the 1:30pm watch candle.
- Direction read: body STAIR-STEP across the four master candles (strict body
  no-overlap), containment = sideways with an "in charge" candle, the 30-min 50/200
  SMA stack + slope, and MOC validation (3:30 volume vs 3:00 volume).
- Levels: master-candle highs/lows for today + the prior 2 sessions.

Everything here is deterministic. The Today page, the coach, and the indicator feed
all read the DayMap rows this module writes.
"""
import re
from datetime import datetime, timedelta

from .extensions import db
from .marketdata import (ET, MASTER_SEQUENCE, WINDOWS, closes_through, extract_candle,
                         get_candle, latest_session, prior_session, window_start_dt)
from .models import DayMap

LOOKBACK_SESSIONS = 2  # her rule: levels stay in play up to 2 days prior

# MOC validation thresholds (apr-16 transcript + the confirmed gray band, apr-24).
MOC_FULL = 1.20
MOC_GRAY = 0.80


def _master_candles(instrument, session_date):
    """The four master candles for a session's read, in walkdown order."""
    out = []
    for window, back in MASTER_SEQUENCE:
        sd = prior_session(session_date, back) if back else session_date
        out.append((window, sd, get_candle(instrument, sd, window)))
    return out


def _stair_step(candles):
    """Body-stack across the master candles, in sequence, bridging gaps.
    Strict no-overlap of bodies. Bridging matters: with one window missing
    (e.g. the Europe candle before its capture lands), the read still steps
    institutional -> globex -> us_open instead of stalling at 'pending'."""
    present = [c for _, _, c in candles if c is not None]
    ups = downs = 0
    pairs = 0
    for a, b in zip(present, present[1:]):
        pairs += 1
        if b.body_low > a.body_high:
            ups += 1
        elif b.body_high < a.body_low:
            downs += 1
    return ups, downs, pairs


def _contains(outer, inner):
    return outer.high >= inner.high and outer.low <= inner.low


def _in_charge(candles):
    """The largest enclosing box wins (walkdown 3:30 -> 6pm -> 4am -> 9:30)."""
    present = [(w, sd, c) for w, sd, c in candles if c is not None]
    if not present:
        return None
    latest = present[-1]
    for w, sd, c in present[:-1]:
        if _contains(c, latest[2]):
            return {"window": w, "session_date": str(sd), "label": WINDOWS[w]["label"]}
    w, sd, c = latest
    return {"window": w, "session_date": str(sd), "label": WINDOWS[w]["label"],
            "broke_out": True}


def _moc_state(instrument, session_date):
    """MOC validation for the institutional candle framing this session
    (i.e., the prior session's 3:30 candle vs its 3:00 base candle)."""
    prior = prior_session(session_date)
    inst = get_candle(instrument, prior, "institutional")
    base = get_candle(instrument, prior, "moc_base_1500")
    if not inst or not base or not inst.volume or not base.volume:
        return {"state": "unknown", "ratio": None}
    ratio = round(inst.volume / base.volume, 2)
    if ratio >= MOC_FULL:
        state = "validated"
    elif ratio >= MOC_GRAY:
        state = "gray"
    else:
        state = "unvalidated"
    return {"state": state, "ratio": ratio}


def _sma_state(instrument, session_date):
    """30-min 50/200 period SMA stack + slope, computed through the latest stored bar."""
    asof = datetime.combine(session_date, datetime.max.time(), tzinfo=ET)
    rows = closes_through(instrument, asof, limit=260)
    if len(rows) < 206:  # the slope windows reach 206 bars back; a shorter
        # history silently deflates sma200_prev and fakes a "rising" slope
        return {"state": "building", "note": f"{len(rows)} of 206 bars of history"}
    closes = [r.close for r in rows]
    sma50 = sum(closes[-50:]) / 50
    sma200 = sum(closes[-200:]) / 200
    sma50_prev = sum(closes[-56:-6]) / 50
    sma200_prev = sum(closes[-206:-6]) / 200
    price = closes[-1]
    asof_ts = datetime.fromtimestamp(rows[-1].ts, tz=ET)

    def slope(now, prev):
        if now > prev * 1.0002:
            return "rising"
        if now < prev * 0.9998:
            return "falling"
        return "flat"

    s50, s200 = slope(sma50, sma50_prev), slope(sma200, sma200_prev)
    # Her rule is stack AND slope, both moving: "straight up or straight down"
    # (apr-8/apr-9). A flat average is a cross-current - stand down.
    if price > sma50 > sma200 and s50 == "rising" and s200 == "rising":
        gate = "aligned_up"
    elif price < sma50 < sma200 and s50 == "falling" and s200 == "falling":
        gate = "aligned_down"
    else:
        gate = "stand_down"
    return {"state": "ok", "price": round(price, 2), "sma50": round(sma50, 2),
            "sma200": round(sma200, 2), "slope50": s50, "slope200": s200,
            "gate": gate, "as_of": asof_ts.strftime("%b %-d %-I:%M%p ET")}


def _verdict(ups, downs, pairs, candles):
    """Stair-step first; a clean break of every prior box resolves a mixed read
    (her rule: sideways until the break). Nested/mixed otherwise = sideways."""
    if pairs < 2:
        return "pending", False
    if ups == pairs:
        return "up", False
    if downs == pairs:
        return "down", False
    present = [c for _, _, c in candles if c is not None]
    if len(present) >= 3:
        newest, priors = present[-1], present[:-1]
        if newest.low > max(c.high for c in priors):
            return "up", True
        if newest.high < min(c.low for c in priors):
            return "down", True
    return "sideways", False


def _levels(instrument, session_date):
    """Master-candle H/L levels for today + prior LOOKBACK_SESSIONS sessions."""
    levels = []
    windows = ["institutional", "globex_open", "europe_open", "us_open", "reversal_1330"]
    for back in range(LOOKBACK_SESSIONS + 1):
        sd = prior_session(session_date, back) if back else session_date
        for window in windows:
            c = get_candle(instrument, sd, window)
            if c is None:
                continue
            age = "today" if back == 0 else f"-{back}d"
            label = WINDOWS[window]["label"]
            approx = c.source == "capture"
            levels.append({"price": c.high, "side": "high", "window": window,
                           "label": f"{label} high", "session_date": str(sd),
                           "age": age, "approx": approx})
            levels.append({"price": c.low, "side": "low", "window": window,
                           "label": f"{label} low", "session_date": str(sd),
                           "age": age, "approx": approx})
    levels.sort(key=lambda x: -x["price"])
    return levels


def build_map(instrument, session_date=None):
    """Compute and persist the DayMap for one instrument and session."""
    session_date = session_date or latest_session()

    # Make sure every needed candle that CAN exist from stored bars does.
    for back in range(LOOKBACK_SESSIONS + 2):
        sd = prior_session(session_date, back) if back else session_date
        for window in WINDOWS:
            extract_candle(instrument, sd, window)

    candles = _master_candles(instrument, session_date)
    ups, downs, pairs = _stair_step(candles)
    in_charge = _in_charge(candles)
    verdict, by_breakout = _verdict(ups, downs, pairs, candles)
    missing = [w for w, _, c in candles if c is None]

    payload = {
        "instrument": instrument,
        "session_date": str(session_date),
        "verdict": verdict,
        "by_breakout": by_breakout,
        # True when any master candle is a live capture (body-only H/L) - the
        # read is honest-but-approximate until overnight reconciliation.
        "approx_inputs": any(c is not None and c.source == "capture"
                             for _, _, c in candles),
        "stair_step": {"ups": ups, "downs": downs, "pairs": pairs},
        "in_charge": in_charge,
        "moc": _moc_state(instrument, session_date),
        "sma": _sma_state(instrument, session_date),
        "levels": _levels(instrument, session_date),
        "master_candles": [
            {"window": w, "session_date": str(sd), "label": WINDOWS[w]["label"],
             "open": c.open, "high": c.high, "low": c.low, "close": c.close,
             "volume": c.volume, "source": c.source} if c else
            {"window": w, "session_date": str(sd), "label": WINDOWS[w]["label"],
             "missing": True}
            for w, sd, c in candles
        ],
        "missing_windows": missing,
    }

    row = DayMap.query.filter_by(instrument=instrument, session_date=session_date).first()
    if row is None:
        row = DayMap(instrument=instrument, session_date=session_date)
        db.session.add(row)
    row.payload = payload
    row.status = "ok" if not missing else ("partial" if pairs >= 2 else "pending")
    row.built_at = datetime.utcnow()
    db.session.commit()
    return row


def _todays_insight():
    """Anne-Marie's insight post for today (ET), if she published one."""
    from datetime import time, timezone
    from .models import Post
    midnight_et = datetime.combine(datetime.now(ET).date(), time.min, tzinfo=ET)
    row = (Post.query.filter(Post.published.is_(True), Post.kind == "insight",
                             Post.created_at >= midnight_et.astimezone(timezone.utc)
                             .replace(tzinfo=None))
           .order_by(Post.created_at.desc()).first())
    return row.body[:600] if row else None


def _todays_briefing():
    """The AI digest of her morning video, if today's was published."""
    from .briefing import todays_briefing_post
    row = todays_briefing_post()
    return row.body[:900] if row else None


def scrub_levels(text):
    """Replace specific level prices with 'a level' - so a free member gets the day's
    READ (bias, day type, where to watch) without the exact tradeable numbers, which
    are the paid edge. Skips 4-digit years (19xx/20xx) so it never eats a date."""
    return re.sub(r"\b(?!19\d\d\b|20\d\d\b)\d{4,6}(?:\.\d+)?\b", "a level", text or "")


def day_state(instrument=None):
    """The day's read for the aha first-read: verdict + SMA gate + in-charge + MOC,
    with NO level numbers (those are the perishable paid edge and the compliance line).
    Returns {} if there is no map. Picks the member's instrument if given, else the first."""
    maps = latest_maps()
    if not maps:
        return {}
    m = None
    if instrument:
        m = next((x for x in maps if x.instrument == (instrument or "").upper()), None)
    m = m or maps[0]
    p = m.payload
    return {
        "instrument": m.instrument,
        "verdict": (p.get("verdict") or "").lower(),
        "gate": ((p.get("sma") or {}).get("gate") or "").lower(),
        "in_charge": p.get("in_charge", ""),
        "moc": (p.get("moc") or {}).get("state", ""),
        "session_date": p.get("session_date"),
    }


def latest_maps():
    """Most recent DayMap per configured instrument (today's if built, else last).
    Bounded to real sessions so a future-dated or weekend row (bad ingest, the
    Friday-evening globex candle building Monday's map) can never shadow the
    live map - the display self-heals even if a bad row exists."""
    from flask import current_app
    out = []
    cap = latest_session()
    for instrument in current_app.config["INSTRUMENTS"]:
        row = (DayMap.query.filter(DayMap.instrument == instrument,
                                   DayMap.session_date <= cap)
               .order_by(DayMap.session_date.desc()).first())
        if row:
            out.append(row)
    return out


# Plain-language templates for the direction card. Deterministic - the LLM never
# writes this page. Educational framing only.
VERDICT_TEXT = {
    "up": "The master candles are stepping UP ({ups} of {pairs} steps). "
          "Her method reads a day like this as: dips are buys - wait for the fade.",
    "down": "The master candles are stepping DOWN ({downs} of {pairs} steps). "
            "Her method reads a day like this as: bounces are sell zones.",
    "sideways": "The candles are nested, not stepping - a sideways read. "
                "Her rule: trade the edges, not the middle, until a break.",
    "pending": "The map is still building - not enough completed candles to read yet.",
}

MOC_TEXT = {
    "validated": "MOC validated ({ratio}x the 3:00 base) - the institutional candle has "
                 "full conviction.",
    "gray": "MOC in the gray zone ({ratio}x) - her rule: reduced conviction, reduced size.",
    "unvalidated": "MOC not validated ({ratio}x) - her rule: smaller size, wider stops.",
    "unknown": "MOC validation unavailable (volume data missing).",
}

GATE_TEXT = {
    "aligned_up": "30-min SMA gate: price above the 50 and 200 - aligned up.",
    "aligned_down": "30-min SMA gate: price below the 50 and 200 - aligned down.",
    "stand_down": "30-min SMA gate: not aligned - her rule: stand down or smallest size.",
}


def direction_sentences(payload):
    """Render the fixed-template direction read for a DayMap payload."""
    out = []
    v = payload.get("verdict", "pending")
    ss = payload.get("stair_step", {})
    if payload.get("by_breakout") and v in ("up", "down"):
        side = "above" if v == "up" else "below"
        reads = "dips are buys - wait for the fade" if v == "up" else "bounces are sell zones"
        out.append(f"The newest master candle printed entirely {side} every prior box - "
                   f"the sideways read resolved {v.upper()} on the break. "
                   f"Her method reads this as: {reads}.")
    else:
        out.append(VERDICT_TEXT[v].format(ups=ss.get("ups", 0), downs=ss.get("downs", 0),
                                          pairs=ss.get("pairs", 0)))
    ic = payload.get("in_charge")
    if ic and v != "pending":
        note = " (no prior box contains it)" if ic.get("broke_out") else ""
        out.append(f"In charge: the {ic['label']} candle of {ic['session_date']}{note}.")
    moc = payload.get("moc", {})
    out.append(MOC_TEXT[moc.get("state", "unknown")].format(ratio=moc.get("ratio")))
    sma = payload.get("sma", {})
    if sma.get("state") == "ok":
        out.append(GATE_TEXT[sma["gate"]] + f" (50: {sma['slope50']}, 200: {sma['slope200']}, "
                   f"as of {sma['as_of']})")
    elif sma.get("state") == "building":
        out.append(f"30-min SMA gate: history still loading ({sma.get('note')}).")
    if payload.get("approx_inputs") and v != "pending":
        out.append("Some of today's candles are live captures (open/close prices); "
                   "the read firms up against exact data overnight.")
    return out


def now_context():
    """The live ET clock + session phase for the coach's volatile block.
    The coach must NEVER ask what time it is - it always knows, and it knows
    where the trading day stands."""
    from .marketdata import session_state
    now = datetime.now(ET)
    stamp = now.strftime("%A, %B %-d, %Y, %-I:%M %p ET")
    st = session_state(now)
    ns = st["next_session"].strftime("%A %b %-d")
    if st["phase"] == "holiday":
        phase = (f"Markets are CLOSED today for {st['holiday']} - there is NO new map or "
                 f"session today, and Anne-Marie has not posted a read. The next session is "
                 f"{ns} (Globex reopens the evening before). This is review-and-learn time, "
                 f"not entry time. Do not imply the market is open or that a fresh read exists.")
    elif st["phase"] == "weekend":
        phase = (f"Markets are CLOSED. The next session is {ns}; Globex reopens 6:00 PM ET the "
                 f"evening before, which starts that session's map. This is review-and-learn "
                 f"time, not entry time.")
    elif st["phase"] == "overnight":
        phase = ("The overnight Globex session is open (it opened 6:00 PM ET). The "
                 "Europe candle prints 4:00-4:30 AM; the US regular session opens "
                 "9:30 AM ET. Tomorrow's map is building.")
    elif st["phase"] == "pre_open":
        phase = ("Pre-open. The overnight candles are in; the US regular session "
                 "opens 9:30 AM ET. She treats pre-open trades as the exception, "
                 "not the routine.")
    elif st["phase"] == "open":
        phase = ("The US regular session is OPEN (9:30 AM - her 3:00 PM flat-by "
                 "rule). Her afternoon anchors: 1:30 watch candle, cancel resting "
                 "limits by 2:30, flat by 3:00, institutional candle 3:30-4:00.")
    elif st["phase"] == "late":
        phase = ("Late session. Her rules here: resting limits cancelled by 2:30, "
                 "flat by 3:00 PM ET. The institutional candle prints 3:30-4:00 "
                 "and closes the day's read. New entries are done for the day.")
    elif st["phase"] == "after_close_preweekend":
        phase = (f"The regular session is over and the market does NOT reopen tonight (it is "
                 f"the close before a weekend or holiday). The next session is {ns}; Globex "
                 f"reopens the evening before. This is review-and-learn time. If the member "
                 f"traded today, warmly offer to debrief it (they can log it on the Trades "
                 f"page or describe it) - completed trades only, never an open position.")
    else:  # after_close (next day IS a session)
        phase = (f"The regular session is over. Globex reopens 6:00 PM ET and starts the "
                 f"next session's map ({ns}). This is review-and-learn time, not entry time. "
                 f"If the member traded today, warmly offer to debrief it (they can log it "
                 f"on the Trades page or just describe it) - completed trades only, never an "
                 f"open position.")
    sched = ""
    try:
        from .models import Appearance
        upcoming = (Appearance.query
                    .filter(Appearance.published.is_(True),
                            Appearance.starts_at >= datetime.utcnow())
                    .order_by(Appearance.starts_at).limit(3).all())
        if upcoming:
            lines = "; ".join(f"{a.title} on {a.where}, {a.starts_at_et}"
                              for a in upcoming)
            sched = (f"\nAnne-Marie's SCHEDULED appearances (you may mention these "
                     f"factually when relevant): {lines}. Outside this list, never "
                     f"promise when she will appear.")
    except Exception:
        pass
    return (f"# NOW\nIt is {stamp}. {phase}{sched}\n"
            "You always know the current date, time, and session state - never ask "
            "the member what time it is or whether the market is open.")


def today_context(gated=False):
    """Compact text block of the latest maps for the coach's system prompt.
    Deterministic numbers from the DayMap rows - the model never invents levels."""
    from .marketdata import session_state
    maps = latest_maps()
    if not maps:
        return ""
    st = session_state()
    # On a closed day she does not post a session read; null these so a stray
    # weekend/holiday post can never leak in as an implied fresh read (the airplane,
    # on the presence surface). Belt-and-suspenders with the page-level guard.
    insight = None if st["closed_today"] else _todays_insight()
    briefing = None if st["closed_today"] else _todays_briefing()
    if gated:  # her posts can quote specific prices - hide those from the free coach too
        insight = scrub_levels(insight) if insight else insight
        briefing = scrub_levels(briefing) if briefing else briefing
    if st["closed_today"]:
        why = f"for {st['holiday']}" if st["holiday"] else "for the weekend"
        nm = maps[0].payload.get("session_date")
        lines = [f"# MOST RECENT SESSION MAP ({nm}) - markets are CLOSED today {why}, so "
                 f"this is the last session's map, not a fresh read. Anne-Marie has not "
                 f"posted today (she does not post on closed days); do not imply a new map "
                 f"or a same-day read exists. This is review-and-learn time."]
    else:
        lines = ["# TODAY - the published Daily Level Map (identical for all members; "
                 "educational reference, never trade direction for an individual). If she "
                 "has posted her read or briefing below, OFFER to walk the member through "
                 "it early in the conversation - it is the freshest, most valuable thing today."]
        if not insight and not briefing:
            lines.append("\n(Anne-Marie has not posted her own read yet today - teach from "
                         "the computed map; do not invent a note from her.)")
    if insight:
        lines.append(f"\nAnne-Marie's published note to all members today: "
                     f"\"{insight}\" (her words - you may discuss and teach around it)")
    if briefing:
        lines.append(f"\nHer morning video briefing, published to all members (an AI "
                     f"digest of today's video - summarize or teach around it, and "
                     f"point members to the full video for her exact words):\n{briefing}")
    for m in maps:
        p = m.payload
        lines.append(f"\n## {m.instrument} - session {p.get('session_date')} "
                     f"(status: {m.status})")
        for s in direction_sentences(p):
            lines.append(f"- {scrub_levels(s) if gated else s}")
        if gated:
            lines.append("- (This member is on the FREE tier: today's exact level NUMBERS are "
                         "members-only. Teach the read, the day type, and the method freely, "
                         "but do NOT state the precise level prices. If they ask for the "
                         "numbers, warmly tell them the daily levels come with membership.)")
        else:
            lines.append("- Levels (today + prior 2 sessions; '~' = live capture, "
                         "approximate until tonight's reconciliation):")
            for lv in p.get("levels", [])[:24]:
                mark = "~" if lv.get("approx") else ""
                lines.append(f"  {lv['price']:.2f}{mark}  {lv['label']} ({lv['age']})")
    return "\n".join(lines)
