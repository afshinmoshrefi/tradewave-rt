"""Her daily video -> the member feed + the coach (the briefing-digest feature,
V1_SITE_DESIGN 4c.3).

Pipeline: newest video on her channel -> confirm it is TODAY'S -> pull the
auto-captions -> clean to a transcript -> Sonnet digest -> deterministic number
scrub -> publish to the feed as kind='briefing' (clearly labeled an AI digest,
with the video link) -> today_context surfaces it to every member's coach.

Numbers policy (ASR reality): YouTube auto-captions mangle spoken prices, so
the digest NEVER trusts a transcript number. The model is given today's real
map numbers as the ONLY allowed prices, and a regex pass then drops any
sentence carrying a 4-6 digit price that is not on the map. Worst case the
digest is number-free and points to the video.

Afshin's provenance ruling (2026-06-10): the daily video digest is
pre-approved - her words recorded daily. It still never enters the evergreen
knowledge corpus; it lives in the feed and today's coach context only.
"""
import json
import re
import subprocess
import tempfile
from datetime import datetime, time, timezone
from pathlib import Path

from flask import current_app

from .extensions import db
from .marketdata import ET
from .models import Post, User

CHANNEL_URL = "https://www.youtube.com/channel/UCJzwwj0-6GmmZrgZB71azfw/videos"
YTDLP = "/home/flask/tradewave_realtime/.venv/bin/yt-dlp"


def latest_video():
    """Newest upload on her channel: (video_id, title, upload_date YYYYMMDD)."""
    out = subprocess.run(
        [YTDLP, CHANNEL_URL, "--flat-playlist", "--playlist-items", "1",
         "--print", "%(id)s\t%(title)s"],
        capture_output=True, text=True, timeout=60, check=True).stdout.strip()
    vid, title = out.split("\t", 1)
    date = subprocess.run(
        [YTDLP, f"https://www.youtube.com/watch?v={vid}", "--skip-download",
         "--print", "%(upload_date)s"],
        capture_output=True, text=True, timeout=60, check=True).stdout.strip().splitlines()[-1]
    return vid, title.strip(), date


def fetch_transcript(video_id):
    """Download auto-captions and flatten the rolling cues into plain text."""
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(
            [YTDLP, f"https://www.youtube.com/watch?v={video_id}",
             "--skip-download", "--write-auto-subs", "--sub-langs", "en",
             "--sub-format", "vtt", "-o", f"{td}/cap"],
            capture_output=True, text=True, timeout=120, check=True)
        vtts = list(Path(td).glob("*.vtt"))
        if not vtts:
            raise RuntimeError("no captions downloaded")
        raw = vtts[0].read_text(errors="ignore")
    lines, last = [], ""
    for line in raw.splitlines():
        line = re.sub(r"<[^>]+>", "", line).strip()
        if (not line or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:"))
                or re.fullmatch(r"[\d:.\s]+", line)):
            continue
        if line == last:  # rolling captions repeat the previous line
            continue
        lines.append(line)
        last = line
    return " ".join(lines)


def _allowed_numbers():
    """Every price the digest may quote: today's levels, candle OHLC, SMAs."""
    from .levels import latest_maps
    allowed = set()
    for m in latest_maps():
        p = m.payload
        for lv in p.get("levels", []):
            allowed.add(float(lv["price"]))
        for mc in p.get("master_candles", []):
            for k in ("open", "high", "low", "close"):
                if mc.get(k):
                    allowed.add(float(mc[k]))
        sma = p.get("sma") or {}
        for k in ("price", "sma50", "sma200"):
            if sma.get(k):
                allowed.add(float(sma[k]))
    return allowed


def _scrub_numbers(text, allowed):
    """Drop any sentence quoting a 4-6 digit price that is not on today's map."""
    ok_str = {f"{v:.2f}".rstrip("0").rstrip(".") for v in allowed}
    ok_int = {str(int(v)) for v in allowed}
    kept, dropped = [], []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        nums = [q.replace(",", "").rstrip("0").rstrip(".") for q in
                re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d{4,6}(?:\.\d{1,2})?",
                           sentence)]
        bad = [q for q in nums
               if q not in ok_str and q.split(".")[0] not in ok_int
               and float(q) > 1000
               and not (q.isdigit() and 1900 <= int(q) <= 2100)]
        (dropped if bad else kept).append(sentence)
    if dropped:
        current_app.logger.warning("briefing scrub dropped: %s", dropped)
    return " ".join(kept).strip()


def make_digest(transcript, video_title, allowed):
    import anthropic
    client = anthropic.Anthropic(api_key=current_app.config["ANTHROPIC_TOKEN"])
    allowed_str = ", ".join(f"{v:.2f}" for v in sorted(allowed)) or "(none available)"
    resp = client.messages.create(
        model=current_app.config.get("CHAT_MODEL", "claude-sonnet-4-6"),
        max_tokens=700, temperature=0.3,
        messages=[{"role": "user", "content":
            "Below is the auto-generated transcript of Anne-Marie Baiynd's morning "
            "futures briefing video. Write a SHORT digest (110 to 170 words) for her "
            "subscribers: what she is watching, her read of the day, any cautions. "
            "Write in clear third person ('She is watching...', 'Her read:'). "
            "Plain language, no hype, no advice, no em dashes (use ' - ' instead). "
            "CRITICAL NUMBER RULE: the transcript's prices are speech-to-text and "
            "unreliable. You may quote a price ONLY if it appears in this verified "
            f"list from today's published map: {allowed_str}. Any other price idea "
            "must be expressed without the number (say 'the Europe low' or 'the "
            "overnight high', never an unverified figure).\n\n"
            f"VIDEO TITLE: {video_title}\n\nTRANSCRIPT:\n{transcript[:24000]}"}],
        output_config={"format": {"type": "json_schema", "schema": {
            "type": "object",
            "properties": {"digest": {"type": "string"}},
            "required": ["digest"], "additionalProperties": False}}})
    text = next(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return json.loads(text)["digest"].replace(chr(0x2014), " - ")


def todays_briefing_post():
    midnight_et = datetime.combine(datetime.now(ET).date(), time.min, tzinfo=ET)
    return (Post.query.filter(Post.published.is_(True), Post.kind == "briefing",
                              Post.created_at >= midnight_et.astimezone(timezone.utc)
                              .replace(tzinfo=None))
            .order_by(Post.created_at.desc()).first())


def publish_briefing(force=False):
    """Run the full pipeline once. Idempotent per day unless force=True."""
    existing = todays_briefing_post()
    if existing and not force:
        return existing, "already published today"
    vid, title, upload_date = latest_video()
    today_et = datetime.now(ET).strftime("%Y%m%d")
    if upload_date != today_et:
        return None, f"newest video is from {upload_date}, not today ({today_et})"
    transcript = fetch_transcript(vid)
    if len(transcript.split()) < 200:
        return None, "transcript too short - captions not ready yet"
    allowed = _allowed_numbers()
    digest = _scrub_numbers(make_digest(transcript, title, allowed), allowed)
    if len(digest.split()) < 40:
        return None, "digest too short after number scrub - not publishing"
    her = User.query.filter_by(role="partner").first()
    body = (f"{digest}\n\nThis is an AI digest of Anne-Marie's morning video "
            f"\"{title}\" - her full briefing: https://youtu.be/{vid}")
    post = Post(title=f"Her morning briefing - {datetime.now(ET).strftime('%b %-d')}: {title}",
                kind="briefing", body=body[:4000], published=True,
                author_id=her.id if her else None)
    db.session.add(post)
    db.session.commit()
    return post, "published"
