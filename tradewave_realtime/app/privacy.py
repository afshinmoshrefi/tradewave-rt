"""Privacy helpers.

scrub_sensitive(): deterministic write-time masking of dollar amounts and
position sizes in member-authored text we STORE for coaching (check-ins, intake
answers, profile edits). Raw chat messages are NOT scrubbed - they are the
member's own record - but anything derived from them for long-term memory is.
Careful: bare numbers are NEVER touched (level prices like 7491.00 must
survive); only money-marked and size-marked phrases are masked.

sanitize_for_admin(): anonymizes member text before it reaches Anne-Marie's
review surfaces - names, dollar amounts, account/prop details - keeping the
trading question intact. Haiku with a deterministic fallback; cached by caller.
"""
import re

from flask import current_app

# $5,000 / $5k / $3.2m / 5000 dollars / 5 grand / 5k account
_MONEY = re.compile(
    r"(?i)(\$\s?[\d,]+(?:\.\d+)?\s?[kKmM]?\b"
    r"|\b[\d,]+(?:\.\d+)?\s?(?:dollars|bucks|grand)\b"
    r"|\b\d+(?:\.\d+)?\s?[kK]\s?(?=(?:account|acct|drawdown|profit|loss|funded))"
    r")")
# 3 lots / 2 contracts / 5 cars / 4 micros / 2 minis
_SIZE = re.compile(r"(?i)\b\d+\s?(?:lots?|contracts?|cars?|micros?|minis?)\b")


def scrub_sensitive(text):
    if not text:
        return text
    text = _MONEY.sub("[amount]", text)
    text = _SIZE.sub("[size]", text)
    return text


def sanitize_for_admin(text):
    """Anonymize member text for Anne-Marie's screens. Never raises."""
    if not text:
        return text
    fallback = scrub_sensitive(text)
    api_key = current_app.config.get("ANTHROPIC_TOKEN")
    if not api_key:
        return fallback
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=current_app.config.get("CLAUDE_MODEL", "claude-haiku-4-5"),
            max_tokens=400,
            messages=[{"role": "user", "content":
                       "Rewrite this trading-member message for an instructor's "
                       "review screen: remove names, dollar amounts, account sizes, "
                       "firm/prop names, and personal identifying details; keep the "
                       "trading question/content and its tone intact; keep price "
                       "LEVELS (e.g. 7491.00) as-is - they are chart values, not "
                       "money. Reply with ONLY the rewritten text.\n\n" + text[:1500]}])
        out = "".join(b.text for b in resp.content
                      if getattr(b, "type", "") == "text").strip()
        return scrub_sensitive(out) if out else fallback
    except Exception:
        current_app.logger.exception("sanitize_for_admin failed; using fallback")
        return fallback
