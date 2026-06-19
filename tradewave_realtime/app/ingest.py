"""Live candle ingest from the TradeWave keyprovider quote service.

Contract (see product/V1_SITE_DESIGN.md, "The ingest contract"): one POST per
completed candle window, idempotent upsert on (instrument, window, session_date).
A successful ingest rebuilds that instrument's DayMap immediately, so the Today
page, the coach, and the indicator feed update within seconds of capture.
"""
import math
from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, request

from .extensions import db
from .marketdata import ET, WINDOWS, is_session_day
from .models import MarketCandle

bp = Blueprint("ingest", __name__)


@bp.route("/api/ingest/candle", methods=["POST"])
def ingest_candle():
    token = current_app.config.get("LEVELS_INGEST_TOKEN")
    if not token or request.headers.get("X-Ingest-Token") != token:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    instrument = (data.get("instrument") or "").upper()
    window = data.get("window") or ""
    if instrument not in current_app.config["INSTRUMENTS"]:
        return jsonify({"error": f"unknown instrument {instrument!r}"}), 400
    if window not in WINDOWS:
        return jsonify({"error": f"unknown window {window!r}",
                        "valid": sorted(WINDOWS)}), 400
    try:
        session_date = date.fromisoformat(data["session_date"])
        o, h = float(data["open"]), float(data["high"])
        lo, c = float(data["low"]), float(data["close"])
        volume = int(data["volume"]) if data.get("volume") is not None else None
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"bad payload: {exc}"}), 400
    # A bad session_date would shadow the real map until manual surgery -
    # reject weekends and anything not near today (+4 covers a long-weekend
    # globex candle; -5 covers late reconciles).
    today = datetime.now(ET).date()
    if not is_session_day(session_date) or not (-5 <= (session_date - today).days <= 4):
        return jsonify({"error": f"implausible session_date {session_date}"}), 400
    # isfinite+positive closes the zero, negative, NaN, and Infinity gaps in
    # one check (NaN passes naive <= comparisons).
    if not all(math.isfinite(v) and v > 0 for v in (o, h, lo, c)):
        return jsonify({"error": "non-positive or non-finite price"}), 400
    if not (h >= max(o, c) and lo <= min(o, c) and h >= lo):
        return jsonify({"error": "inconsistent OHLC"}), 400
    if volume is not None and volume < 0:
        return jsonify({"error": "negative volume"}), 400

    row = MarketCandle.query.filter_by(instrument=instrument,
                                       session_date=session_date,
                                       window=window).first()
    if row is None:
        row = MarketCandle(instrument=instrument, session_date=session_date,
                           window=window)
        db.session.add(row)
    elif row.source in ("eodhd", "reconciled"):
        # History truth already landed for this window; captures never overwrite it.
        return jsonify({"status": "ignored", "reason": "already reconciled"}), 200
    row.open, row.high, row.low, row.close, row.volume = o, h, lo, c, volume
    row.source = "capture"
    row.captured_at = datetime.utcnow()
    db.session.commit()

    from .levels import build_map
    built = build_map(instrument, session_date)
    return jsonify({"status": "ok", "map_status": built.status}), 200
