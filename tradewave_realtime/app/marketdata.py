"""Market data layer.

EODHD supplies intraday history (30-minute bars, full Globex session, ~one session of
lag) for backfill, SMAs, and nightly reconciliation. Live candle capture arrives from
the TradeWave keyprovider quote service via POST /api/ingest/candle (see ingest.py).
All of Anne-Marie's structural candle windows are defined here, in ET.
"""
import json
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app

from .extensions import db
from .models import IntradayBar, MarketCandle

ET = ZoneInfo("America/New_York")

# Anne-Marie's structural candle windows (ET start time, 30 minutes each).
# "prior_eve" windows print on the calendar evening BEFORE the session date.
# Walkdown order for the day's read: institutional -> globex_open -> europe_open -> us_open
# (the institutional candle belongs to the PRIOR session; see levels.py).
WINDOWS = {
    "globex_open": {"start": time(18, 0), "prior_eve": True, "label": "Globex open"},
    "europe_open": {"start": time(4, 0), "prior_eve": False, "label": "Europe open"},
    "us_open": {"start": time(9, 30), "prior_eve": False, "label": "US open"},
    "reversal_1330": {"start": time(13, 30), "prior_eve": False, "label": "1:30 watch"},
    "moc_base_1500": {"start": time(15, 0), "prior_eve": False, "label": "3:00 base"},
    "institutional": {"start": time(15, 30), "prior_eve": False, "label": "Institutional"},
}

# The four master candles, in her walkdown order, as (window, sessions_back) relative
# to the map's session date. The institutional candle that frames session D printed
# on session D-1's afternoon.
MASTER_SEQUENCE = [
    ("institutional", 1),
    ("globex_open", 0),
    ("europe_open", 0),
    ("us_open", 0),
]


# ---------------------------------------------------------------------------
# THE SESSION CALENDAR - the single source of truth for "is the market open".
# Every surface (the coach's NOW block, the Today banner, the check-in card,
# re-engagement timing) derives from is_session_day()/session_state() so they
# can NEVER disagree. This is safety-critical: tech that tells a member the
# market is open on a federal holiday is the airplane crashing. The hardcoded
# table is the guaranteed floor; an optional admin override can only ADD
# closures, never remove one, so a data-entry slip can never re-open a real
# holiday.  US equity-index / index-futures full-close calendar, ET.
# ---------------------------------------------------------------------------
MARKET_HOLIDAYS = {
    date(2026, 1, 1): "New Year's Day",
    date(2026, 1, 19): "Martin Luther King Jr. Day",
    date(2026, 2, 16): "Presidents' Day",
    date(2026, 4, 3): "Good Friday",
    date(2026, 5, 25): "Memorial Day",
    date(2026, 6, 19): "Juneteenth",
    date(2026, 7, 3): "Independence Day",          # Jul 4 is a Saturday -> observed Fri
    date(2026, 9, 7): "Labor Day",
    date(2026, 11, 26): "Thanksgiving",
    date(2026, 12, 25): "Christmas",
    date(2027, 1, 1): "New Year's Day",
    date(2027, 1, 18): "Martin Luther King Jr. Day",
    date(2027, 2, 15): "Presidents' Day",
    date(2027, 3, 26): "Good Friday",
    date(2027, 5, 31): "Memorial Day",
    date(2027, 6, 18): "Juneteenth (observed)",    # Jun 19 is a Saturday
    date(2027, 7, 5): "Independence Day (observed)",  # Jul 4 is a Sunday
    date(2027, 9, 6): "Labor Day",
    date(2027, 11, 25): "Thanksgiving",
    date(2027, 12, 24): "Christmas (observed)",     # Dec 25 is a Saturday
}

# Early-close (half) days: equities close 1:00 PM ET, index futures shorten.
MARKET_EARLY_CLOSES = {
    date(2026, 11, 27): "the day after Thanksgiving",
    date(2026, 12, 24): "Christmas Eve",
    date(2027, 11, 26): "the day after Thanksgiving",
}


def _admin_closures():
    """Optional admin-added full-close dates (add-only). Fails safe to empty so
    the hardcoded table is always the guaranteed floor."""
    try:
        from .models import MarketClosure
        return {c.closed_on for c in MarketClosure.query.all()}
    except Exception:
        return set()


def market_holidays():
    """All full-close dates: the hardcoded calendar plus any admin closures."""
    return set(MARKET_HOLIDAYS) | _admin_closures()


def holiday_name(d):
    """The name of the holiday on date d, or None. Admin closures read 'a market holiday'."""
    if d in MARKET_HOLIDAYS:
        return MARKET_HOLIDAYS[d]
    return "a market holiday" if d in _admin_closures() else None


def is_session_day(d):
    """True only on a real trading day: a weekday that is not a market holiday.
    THE single gate; latest_session/prior_session/next_session_date all use it,
    so adding a holiday here fixes every downstream surface at once."""
    return d.weekday() < 5 and d not in market_holidays()


def is_early_close(d):
    return d in MARKET_EARLY_CLOSES


def prior_session(d, n=1):
    cur = d
    while n > 0:
        cur -= timedelta(days=1)
        if is_session_day(cur):
            n -= 1
    return cur


def next_session_date(d):
    """The next real trading day strictly after d (skips weekends AND holidays)."""
    cur = d + timedelta(days=1)
    while not is_session_day(cur):
        cur += timedelta(days=1)
    return cur


def latest_session(today=None):
    """The most recent session date as of now (ET)."""
    now = datetime.now(ET)
    d = (today or now.date())
    if not is_session_day(d):
        return prior_session(d)
    return d


def session_state(now=None):
    """THE single source of truth for what the market is doing right now (ET).

    Returns a dict every consumer formats from, so the coach, the Today banner,
    and the check-in card can never contradict each other:
      open        - bool, is the US regular session open right now
      closed_today- bool, is today a non-session day (weekend or holiday)
      holiday     - holiday name if today is a holiday, else None
      phase       - one of: holiday, weekend, overnight, pre_open, open,
                    late, after_close
      next_session- date of the next real trading session
      checkin     - 'plan' | 'review' | 'closed' for the Today check-in card
    """
    now = now or datetime.now(ET)
    today = now.date()
    hm = now.strftime("%H:%M")
    hol = holiday_name(today)
    weekend = today.weekday() >= 5
    nxt = today if is_session_day(today) and hm < "09:30" else next_session_date(today)

    if hol:
        return {"open": False, "closed_today": True, "holiday": hol, "phase": "holiday",
                "next_session": next_session_date(today), "checkin": "closed"}
    if weekend:
        return {"open": False, "closed_today": True, "holiday": None, "phase": "weekend",
                "next_session": next_session_date(today), "checkin": "closed"}
    # A session day after 16:00 whose NEXT day is closed (Friday, holiday-eve): the
    # session is OVER and the market does NOT reopen tonight. Distinct from a true
    # all-day weekend so the coach keeps the debrief offer and uses correct copy
    # (not a present-tense "markets are closed" minutes after a session they traded).
    next_day_closed = not is_session_day(today + timedelta(days=1))
    # Early-close (half) day: equities close 1:00 PM ET. After that the market is
    # closed - never report it OPEN (the airplane failure, one day-type over).
    if is_early_close(today) and hm >= "13:00":
        return {"open": False, "closed_today": False, "holiday": None,
                "phase": "after_close_preweekend" if next_day_closed else "after_close",
                "next_session": next_session_date(today), "checkin": "review"}
    if hm >= "16:00" and next_day_closed:
        return {"open": False, "closed_today": False, "holiday": None,
                "phase": "after_close_preweekend",
                "next_session": next_session_date(today), "checkin": "review"}
    if hm >= "18:00" or hm < "04:00":
        phase = "overnight"
    elif hm < "09:30":
        phase = "pre_open"
    elif hm < "14:30":
        phase = "open"
    elif hm < "16:00":
        phase = "late"
    else:
        phase = "after_close"
    return {"open": phase in ("open", "late"), "closed_today": False, "holiday": None,
            "phase": phase, "next_session": nxt,
            "checkin": "review" if hm >= "16:00" else "plan"}


def window_start_dt(session_date, window):
    """The ET datetime at which this window opens for the given session."""
    spec = WINDOWS[window]
    d = session_date
    if spec["prior_eve"]:
        d -= timedelta(days=1)
        while not is_session_day(d) and d.weekday() != 6:  # Sunday evening opens Monday
            d -= timedelta(days=1)
    return datetime.combine(d, spec["start"], tzinfo=ET)


def _eodhd_get(path, params):
    token = current_app.config.get("EOD_TOKEN")
    if not token:
        raise RuntimeError("EOD_TOKEN is not configured")
    params = dict(params, api_token=token, fmt="json")
    url = f"https://eodhd.com/api/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


def fetch_intraday_bars(instrument, days=12):
    """Pull 30m bars from EODHD into IntradayBar (upsert). Returns rows written."""
    symbol = current_app.config["INSTRUMENTS"][instrument]["eodhd"]
    now = datetime.now(tz=ZoneInfo("UTC"))
    frm = int((now - timedelta(days=days)).timestamp())
    bars = _eodhd_get(f"intraday/{symbol}", {"interval": "30m", "from": frm,
                                             "to": int(now.timestamp())})
    written = 0
    for b in bars or []:
        if any(b.get(k) is None for k in ("timestamp", "open", "high", "low", "close")):
            continue
        if float(b["high"]) < float(b["low"]) or float(b["low"]) <= 0:
            continue  # malformed bar from the provider
        ts = int(b["timestamp"])
        row = IntradayBar.query.filter_by(instrument=instrument, ts=ts).first()
        if row is None:
            row = IntradayBar(instrument=instrument, ts=ts)
            db.session.add(row)
            written += 1
        row.open, row.high = float(b["open"]), float(b["high"])
        row.low, row.close = float(b["low"]), float(b["close"])
        row.volume = int(b["volume"]) if b.get("volume") is not None else None
    db.session.commit()
    return written


def bar_at(instrument, dt_et):
    """The stored 30m bar opening exactly at dt_et (an ET datetime)."""
    ts = int(dt_et.timestamp())
    return IntradayBar.query.filter_by(instrument=instrument, ts=ts).first()


def closes_through(instrument, dt_et, limit=260):
    """The most recent `limit` 30m closes up to dt_et, oldest first."""
    ts = int(dt_et.timestamp())
    rows = (IntradayBar.query.filter(IntradayBar.instrument == instrument,
                                     IntradayBar.ts <= ts)
            .order_by(IntradayBar.ts.desc()).limit(limit).all())
    return list(reversed(rows))


def extract_candle(instrument, session_date, window):
    """Derive a structural candle from stored bars and upsert MarketCandle.

    EODHD-derived values are the truth source: they overwrite 'capture' rows
    (reconciliation), preserving the capture values in the audit columns and
    recording the open/close drift (the only values a boundary capture actually
    measures - capture H/L is body-only by design, so comparing it against true
    wick extremes would alarm on every reconciliation).
    Returns the MarketCandle or None if the bar is not available yet.
    """
    start = window_start_dt(session_date, window)
    bar = bar_at(instrument, start)
    if bar is None:
        return None
    row = MarketCandle.query.filter_by(instrument=instrument,
                                       session_date=session_date, window=window).first()
    if row is None:
        row = MarketCandle(instrument=instrument, session_date=session_date,
                           window=window)
        db.session.add(row)
    elif row.source == "capture":
        tol = 0.5  # two ES ticks
        drift = max(abs(row.open - bar.open), abs(row.close - bar.close))
        body_outside = row.high > bar.high + tol or row.low < bar.low - tol
        row.capture_open, row.capture_close = row.open, row.close
        row.recon_drift = round(drift, 4)
        if drift > tol or body_outside:
            current_app.logger.warning(
                "Capture drift %s %s %s: capture O/C %.2f/%.2f vs EODHD %.2f/%.2f"
                "%s", instrument, session_date, window, row.open, row.close,
                bar.open, bar.close,
                " (capture body printed OUTSIDE the true range)" if body_outside else "")
        row.source = "reconciled"
    row.open, row.high, row.low, row.close = bar.open, bar.high, bar.low, bar.close
    row.volume = bar.volume
    db.session.commit()
    return row


def get_candle(instrument, session_date, window):
    return MarketCandle.query.filter_by(instrument=instrument,
                                        session_date=session_date,
                                        window=window).first()


# ---------------------------------------------------------------------------
# Keyprovider pull adapter - the live capture source (boundary snapshots).
#
# The realtime service on keyprovider snapshots the delayed EODHD quote at exact
# ET candle boundaries (see /home/afshin/tradewave_realtime_level_quotes.md).
# A candle is DERIVED from its two boundary snapshots: open = price at the open
# boundary, close = price at the close boundary, body-only high/low (true wick
# extremes arrive overnight when EODHD history reconciles over these rows), and
# window volume = the cumulative-session-volume delta across the boundaries.
# History truth always wins: captures never overwrite eodhd/reconciled rows.
#
# KNOWN GAPS (flagged to Afshin):
# - the eu pair is captured at 03:30/04:00, but her Europe candle is 04:00-04:30
#   (transcripts + the engine window) - eu captures are SKIPPED until the
#   capture schedule moves;
# - no 15:00 snapshot, so the live MOC base comes only from history (fine for
#   the morning map: it uses the PRIOR session's MOC, already in history).

# window -> (open candle_time, close candle_time, open label, close label)
# Europe enabled 2026-06-11 after the capture schedule moved to her true
# 4:00-4:30am window (was 3:30-4:00; see the design doc's capture-schedule asks).
KEYPROVIDER_PAIRS = {
    "globex_open": ("18:00", "18:30", "globex_open_o", "globex_open_c"),
    "europe_open": ("04:00", "04:30", "eu_open_o", "eu_open_c"),
    "us_open": ("09:30", "10:00", "us_open_o", "us_open_c"),
    "reversal_1330": ("13:30", "14:00", "us_mid_o", "us_mid_c"),
    "institutional": ("15:30", "16:00", "us_close_o", "us_close_c"),
}


def fetch_keyprovider_levels(days=4):
    """Pull boundary snapshots and upsert capture-derived candles.
    Returns the number of candle rows written/updated."""
    base = current_app.config.get("KEYPROVIDER_LEVELS_URL")
    if not base:
        return 0
    symbols = list(current_app.config["INSTRUMENTS"])
    url = (f"{base}/levels_rt?symbols={','.join(symbols)}&days={days}")
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    by_symbol = data.get("levels", {})
    written = 0
    for instrument in symbols:
        dates = by_symbol.get(instrument, {})
        for date_str, snaps in dates.items():
            cal_date = date.fromisoformat(date_str)
            for window, (t_open, t_close, lbl_open, lbl_close) in KEYPROVIDER_PAIRS.items():
                s_open, s_close = snaps.get(t_open), snaps.get(t_close)
                if not s_open or not s_close:
                    continue
                # Reject manual/smoke test captures - only scheduled labels count.
                if s_open.get("label") != lbl_open or s_close.get("label") != lbl_close:
                    continue
                if s_open.get("price") is None or s_close.get("price") is None:
                    continue
                # The 18:00 Globex-open candle belongs to the NEXT session.
                session_date = cal_date
                if WINDOWS[window]["prior_eve"]:
                    session_date = cal_date + timedelta(days=1)
                    while not is_session_day(session_date):
                        session_date += timedelta(days=1)
                if _upsert_capture(instrument, session_date, window, s_open, s_close):
                    written += 1
    return written


def _upsert_capture(instrument, session_date, window, s_open, s_close):
    from sqlalchemy.exc import IntegrityError
    row = MarketCandle.query.filter_by(instrument=instrument,
                                       session_date=session_date,
                                       window=window).first()
    if row is not None and row.source in ("eodhd", "reconciled"):
        return False  # history truth already landed
    o, c = float(s_open["price"]), float(s_close["price"])
    if o <= 0 or c <= 0:
        return False  # a zeroed snapshot from a failed upstream quote
    vol = None
    if s_open.get("volume") is not None and s_close.get("volume") is not None:
        delta = int(s_close["volume"]) - int(s_open["volume"])
        if window == "globex_open":
            # The cumulative session counter resets at the 18:00 open, so the
            # close-boundary cumulative IS the window volume so far (slightly
            # undercounted by the feed delay; reconciled overnight).
            vol = int(s_close["volume"])
        elif delta >= 0:
            vol = delta
        # negative delta on any other window = counter anomaly -> leave None
    if row is None:
        row = MarketCandle(instrument=instrument, session_date=session_date,
                           window=window)
        db.session.add(row)
    row.open, row.close = o, c
    row.high, row.low = max(o, c), min(o, c)  # body-only until reconciliation
    row.volume = vol
    row.source = "capture"
    row.captured_at = datetime.utcnow()
    try:
        db.session.commit()
    except IntegrityError:
        # The 15-min sync and a web-triggered build raced on uq_candle; the
        # other writer won - re-read and let normal precedence apply next pull.
        db.session.rollback()
        return False
    return True
