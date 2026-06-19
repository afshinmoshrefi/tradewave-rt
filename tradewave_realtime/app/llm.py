"""LLM layer for the coach.

ARCHITECTURE (decided 2026-06-10): the chat coach gets the ENTIRE method corpus
(~30k tokens: persona + voice + all published knowledge) as a prompt-cached
system prefix instead of RAG-retrieved excerpts. The corpus is byte-identical
for every member, so the whole member base shares one cache entry (reads at
0.1x input price); volatile context (today's map, the member profile) renders
AFTER the cache breakpoint. No retrieval misses, and the coach can
cross-reference lessons. TF-IDF retrieval survives only to pick the "related
lessons" citation chips in the UI.

If ANTHROPIC_TOKEN is unset, the coach runs in a retrieval-only DEMO mode so
the product is always demoable.
"""
import re

from flask import current_app

from . import persona
from .rag import index as kb_index

# Hard rule: never emit em dashes. Sanitize all coach output (Claude or fallback),
# because the model will produce them even when told not to.
_EMDASH = chr(0x2014)
_EMDASH_RE = re.compile(r"[ \t]*" + _EMDASH + r"[ \t]*")


def _no_emdash(text):
    return _EMDASH_RE.sub(" - ", text or "")


def _format_context(chunks):
    if not chunks:
        return "(No specific curated knowledge matched this question. Lean on her general approach and be honest about limits.)"
    parts = []
    for c in chunks:
        parts.append(f"### {c['title']}  [{c['category']}]\n{c['text']}")
    return "\n\n".join(parts)


def retrieve(query, k=4):
    return kb_index.search(query, k=k)


_NUM_RE = re.compile(r"\b\d{4,6}(?:\.\d{1,2})?\b")


def correct_level_typos(text, user_message=""):
    """The worst failure mode is a digit-flipped level ('5335.50' for 7335.50).
    Deterministic repair: any 4-6 digit number in the reply that is NOT a real
    map level but differs from one by exactly one digit gets corrected to the
    real level. Numbers the member themselves typed are left alone."""
    from .levels import latest_maps
    real = set()
    for m in latest_maps():
        for lv in m.payload.get("levels", []):
            real.add(f"{lv['price']:.2f}".rstrip("0").rstrip("."))
    if not real:
        return text, []

    user_nums = set(_NUM_RE.findall(user_message or ""))
    corrections = []

    def fix(match):
        tok = match.group(0)
        norm = tok.rstrip("0").rstrip(".") if "." in tok else tok
        if norm in real or tok in user_nums:
            return tok
        if norm.isdigit() and 1900 <= int(norm) <= 2100:
            return tok  # a year, not a level
        for r in real:
            if len(r) == len(norm) and sum(a != b for a, b in zip(r, norm)) == 1:
                corrections.append((tok, r))
                return r
        return tok

    fixed = _NUM_RE.sub(fix, text)
    return fixed, corrections


# --------------------------------------------------------------- runtime compliance screen
# A deterministic backstop on the ACTUAL generated reply (web coach + Discord), under the
# system prompt. It catches the egregious, unambiguous failures a prompt regression or
# jailbreak could slip through - a live directional call, an income projection, a specific
# position size - and replaces the reply with a safe redirect. Built for HIGH PRECISION: it
# is sentence-scoped, skips negated and question clauses, and ignores her teaching mantras,
# so it never nukes a compliant answer. The eval battery (build-time) stays the consistency
# check; this is the request-time net. Consistent in intent with evals' ADVICE_RE/INCOME_RE.

COMPLIANCE_REDIRECT = (
    "Let me pull this back to what I'm here for. I won't hand you a buy, a sell, a "
    "position size, or an income number, that isn't how Anne-Marie trades and leaning on "
    "a call from me won't make you better. What I can do is walk the read with you: what "
    "does your own 30-minute trend gate say right now, is price at one of her levels or "
    "stuck in the middle, and what would a failed retest look like here? Ask me any of "
    "those and we work it the way she would, so the decision stays yours."
)

# Tradable instruments incl. the common trader slang a model might emit in her folksy
# voice (spooz/spoos = ES, nas = NQ).
_SCREEN_INSTR = (r"(?:es|nq|cl|gc|rty|ym|mes|mnq|mcl|mgc|spooz|spoos|the spooz|nas|the nas|"
                 r"the es|the nq|e-?minis?|spx|nasdaq|crude|gold|russell|dow)")

# Two verb tiers. STRONG verbs are inherently "open a fresh position" calls (a model
# rarely uses them to narrate); pairing one with an instrument or here/now is enough.
# PLAIN verbs (buy/sell/short...) also appear in third-person teaching ("she sells
# bounces"), so they need an object/urgency to count as a member-directed call.
_STRONG_VERB = (r"(?:grab|scoop(?: up)?|load up(?: on)?|pile in(?:to)?|accumulate|stack|"
                r"bite)")
_PLAIN_VERB = r"(?:buy|sell|short|go long|go short|get long|get short|enter)"
_MODAL = (r"(?:should|need to|have to|ought to|could|can|may|must|want to|wanna|gotta|"
          r"might want to|may want to|'d|'ll|would|will)")

# Each pattern is a member-directed call, a first-person call, a soft directional lean,
# a named trade plan, or a concrete entry/stop/target. Soft modals (could/can/might
# want to) DO count: "you could go long ES here" is still an individualized call.
_DIRECTIONAL_PATTERNS = [
    re.compile(r"(?i)\byou " + _MODAL + r" (?:" + _PLAIN_VERB + r"|" + _STRONG_VERB +
               r"|take (?:the|this) trade)\b"),
    re.compile(r"(?i)\bi(?:'d|'ll| would| will| am going to|'m going to| am gonna|"
               r"'m gonna| plan to| intend to| am about to) (?:" + _PLAIN_VERB + r"|" +
               _STRONG_VERB + r"|be a (?:buyer|seller))\b"),
    re.compile(r"(?i)\bi(?:'d|'m| am| would| will)? ?lean(?:ing)? (?:long|short)\b"),
    re.compile(r"(?i)\btake (?:the|a) (?:long|short|trade) (?:here|now|today|right now|at \d)"),
    re.compile(r"(?i)\bthe (?:play|setup|trade|call|move) (?:here |today )?"
               r"(?:is|:) (?:a |to )?(?:long|short|buy|sell|go long|go short)\b"),
    re.compile(r"(?i)\bmy (?:trade|position|call|bias|play|view|plan) (?:is|would be|for today|:)"),
    # strong verb + a tradable object (no urgency needed; the verb is the call)
    re.compile(r"(?i)\b" + _STRONG_VERB + r" (?:up |on |in |into |to )?(?:the |some |a few )?"
               r"(?:" + _SCREEN_INSTR + r"|it|this|here|now|today|the dip|the rip)\b"),
    # plain imperative + object/urgency (so third-person narration does not trip)
    re.compile(r"(?i)\b" + _PLAIN_VERB + r" (?:it|this|here|now|today|right here|right now)\b"),
    re.compile(r"(?i)\b" + _PLAIN_VERB + r" (?:some|a few) " + _SCREEN_INSTR + r"\b"),
    re.compile(r"(?i)\b" + _PLAIN_VERB + r" (?:the )?" + _SCREEN_INSTR +
               r" (?:now|here|today|right now|right here|at \d|into)\b"),
    # add-to-position is a sizing/entry instruction
    re.compile(r"(?i)\badd(?:ing)? (?:to |into )(?:your |the )?position\b|\badd (?:here|now)\b"),
    # zero-verb structural call: "ES long here", "NQ short at 5300"
    re.compile(r"(?i)\b" + _SCREEN_INSTR + r" (?:long|short) (?:here|now|today|at \d)"),
    # explicit price plan / stop / target
    re.compile(r"(?i)\b(?:buy|sell|short|long|enter|entry) (?:at )?\d{3,}\b"),
    re.compile(r"(?i)\b(?:stop|target)(?: is| at| of)? \d{3,}\b"),
    # named-action idioms
    re.compile(r"(?i)\b(?:back up the truck|hit the bid|lift the offer)\b"),
]

# Income/earnings projection. Money-specific verbs (net/pull/clear/earn...) trip on any
# number; the ambiguous verb "make" requires a money marker so her "make 5 trades a day"
# rule is never mistaken for a $ projection. Deconstruction stays allowed: the eval-style
# "before/to make $X" lookbehind plus a refutation guard (see _income_trips).
_SCREEN_INCOME = re.compile(
    r"(?i)("
    r"(?<!before )(?<!to )\byou(?:'ll|'d)? (?:" + _MODAL + r"|expect to|be able to|"
    r"realistically|gonna|going to|now )?\s*"
    r"(?:net|pull(?: in)?|clear|average|take home|profit|earn|rake in) "
    r"(?:about |around |roughly |up to |\$)?\d"
    r"|(?<!before )(?<!to )\byou(?:'ll|'d)? (?:" + _MODAL + r"|expect to|be able to|"
    r"realistically )?\s*make (?:about |around |roughly |up to )?"
    r"(?:\$\d|\d[\d,]*\s*(?:dollars|bucks|grand|k\b|%)|"
    r"\d[\d,]*\s*(?:this |a |an |per |each |next )?(?:day|week|month|year|daily|weekly|monthly))"
    r"|\bexpect to (?:make|earn|pull|net|clear|average) (?:\$)?\d"
    r"|\b(?:making|earning|pulling|netting|clearing|averaging|profiting) (?:in )?"
    r"(?:\$)?\d[\d,]*\s*(?:k|grand)?\s*(?:a|per|/|each )?\s*"
    r"(?:day|week|month|year|daily|weekly|monthly)"
    r")")

# Refutation / deconstruction cues: when present near an income match, it is teaching
# (walking through an unrealistic number to debunk it), not a projection.
_DECONSTRUCT = re.compile(
    r"(?i)(not real|isn'?t real|not realistic|unrealistic|not how she|does(?:n'?t| not) "
    r"think|that thinking is wrong|but that is not|but that'?s not|that is not how|if the "
    r"stars align|no(?:body| one) can promise|not guaranteed|won'?t happen|not how this "
    r"works|here is why that|here'?s why that|that'?s the trap)")

# A specific position size handed to the member. Excludes 1 / one / a (protects her
# "start with one micro" teaching); fires on a deliberate count of 2+.
_UNIT = r"(?:es|nq|cl|gc|rty|ym|mes|mnq|contracts?|micros?|minis?|lots?)"
_COUNT = r"(?:two|three|four|five|six|seven|eight|nine|ten|[2-9]|\d{2,})"
_SCREEN_SIZING = re.compile(
    r"(?i)("
    r"\b(?:buy|sell|short|go long|go short|trade|put on|enter with|use|do|run|take|"
    r"go with|scale in(?:to)?|size up to|size to)\s+" + _COUNT + r"\s+" + _UNIT + r"\b"
    r"|\b" + _COUNT + r"\s+" + _UNIT + r"\s+(?:is|are)\s+(?:fine|good|right|enough|ok)\b"
    r"|\bsize up to\s+" + _COUNT + r"\b"
    r")")

_SCREEN_NEGATION = re.compile(
    r"(?i)(\bnever\b|\bnot\b|n't\b|\bno\b|\bdon't\b|\bdo not\b|\bcannot\b|\bcan't\b|"
    r"\bwon't\b|\bwould never\b|\bavoid\b|\bwithout\b|\bisn't\b|\binstead of\b|\brather than\b)")


def _strip_markup(text):
    """Remove markdown emphasis so '_short_' or '**buy**' cannot hide a call."""
    return re.sub(r"[*_`]+", "", text or "")


def _income_trips(text):
    """An unconditional, unrefuted income projection. Deconstruction (a number walked
    through and debunked, often across the next sentence) is allowed."""
    sents = re.split(r"(?<=[.!?\n])\s+", text)
    for i, s in enumerate(sents):
        if _SCREEN_INCOME.search(s):
            window = s + " " + (sents[i + 1] if i + 1 < len(sents) else "")
            if not _DECONSTRUCT.search(window):
                return True
    return False


def screen_reply(text):
    """Return (ok, reason). ok=False means the reply must NOT be shown as-is.

    NOTE on scope: this is a deterministic backstop tuned to the realistic ways the
    model fails (natural trader phrasing), under the system prompt and the build-time
    eval battery. It deliberately does NOT chase adversarial output-byte evasions
    (unicode homoglyphs), which are not a realistic model-failure mode; a future
    LLM-based screen is the path to that level of coverage."""
    t = _strip_markup(text)
    if _income_trips(t):
        return False, "income/earnings projection"
    if _SCREEN_SIZING.search(t):
        return False, "specific position size"
    for clause in re.split(r"(?<=[.!?;\n])\s+", t):
        c = clause.strip()
        if not c or c.endswith("?"):          # a question is not an instruction
            continue
        if _SCREEN_NEGATION.search(c):         # a negated clause is a refusal/teaching
            continue
        if any(p.search(c) for p in _DIRECTIONAL_PATTERNS):
            return False, "individualized buy/sell/entry call"
    return True, ""


def enforce_compliance(reply):
    """Apply the runtime screen. Returns (safe_reply, tripped, reason). On a trip,
    logs the original loudly (a trip means a prompt regression or jailbreak) and
    returns the safe redirect in the coach's voice."""
    ok, reason = screen_reply(reply)
    if ok:
        return reply, False, ""
    try:
        current_app.logger.warning(
            "COMPLIANCE screen tripped (%s); original suppressed: %r", reason, (reply or "")[:300])
    except Exception:
        pass
    return COMPLIANCE_REDIRECT, True, reason


# Module-level corpus cache, keyed by (entry count, latest update) so a
# knowledge edit in the admin tool invalidates it automatically. The string
# must be byte-stable across processes and requests - it IS the cache prefix.
_corpus_cache = {"key": None, "text": ""}


def method_corpus():
    """The full published knowledge base, rendered deterministically."""
    from .models import KnowledgeEntry
    from .extensions import db
    from sqlalchemy import func
    key = db.session.query(func.count(KnowledgeEntry.id),
                           func.max(KnowledgeEntry.updated_at)).first()
    if _corpus_cache["key"] == key:
        return _corpus_cache["text"]
    entries = (KnowledgeEntry.query.filter_by(published=True, status="approved")
               .order_by(KnowledgeEntry.stage, KnowledgeEntry.stage_order,
                         KnowledgeEntry.id).all())
    parts = ["# THE COMPLETE METHOD (every published lesson, in teaching order)"]
    for e in entries:
        stage = f"Stage {e.stage}" if e.stage else "Reference"
        tag = "" if e.provenance in ("her_words", "her_approved") else \
            " | team note: hedge if asked whether this is exactly how Anne-Marie says it"
        parts.append(f"\n## {e.title}  [{stage} | {e.category}{tag}]\n{e.content.strip()}")
    text = "\n".join(parts)
    _corpus_cache.update(key=key, text=text)
    return text


def _citations(chunks):
    """One citation per entry, in retrieval order - an entry can match on
    several chunks and members shouldn't see duplicate source chips."""
    seen, out = set(), []
    for c in chunks:
        if c["entry_id"] in seen:
            continue
        seen.add(c["entry_id"])
        out.append({"title": c["title"], "category": c["category"],
                    "entry_id": c["entry_id"]})
    return out


def generate_reply(user_message, history=None, k=4, member_context="", gated=False):
    """Return (reply_text, used_llm, citations)."""
    chunks = retrieve(user_message, k=k)
    citations = _citations(chunks)
    api_key = current_app.config.get("ANTHROPIC_TOKEN")
    if api_key:
        try:
            reply = _no_emdash(_claude_reply(api_key, user_message, chunks, history or [],
                                             member_context=member_context, gated=gated))
            reply, fixes = correct_level_typos(reply, user_message)
            if fixes:
                current_app.logger.warning("level typo corrected: %s", fixes)
            return reply, True, citations
        except Exception as exc:  # pragma: no cover - network/runtime guard
            current_app.logger.warning("Claude call failed, using fallback: %s", exc)
    return _no_emdash(_fallback_reply(user_message, chunks)), False, citations


def _build_chat_request(user_message, history, member_context="", include_today=True,
                        max_tokens=1000, extra_instruction="", gated=False):
    """The shared request shape for streaming and non-streaming chat calls.
    include_today=False = evergreen-only (the free Discord tier - today's map
    is the paid product and never crosses the paywall). gated=True keeps the
    read/day-type but strips the exact level NUMBERS (free web tier past day 1).
    The live clock is NOT paid info - every tier gets it."""
    from .levels import now_context, today_context
    now = now_context()
    today = today_context(gated=gated) if include_today else ""

    # Block 1: byte-stable across ALL members and requests - this is the shared
    # cache prefix. Nothing volatile (timestamps, member data) may enter it.
    stable = (
        persona.SYSTEM_PROMPT
        + "\n\n# REFERENCE - Anne-Marie's voice & method (always available)\n"
        + persona.SIGNATURE_NOTES
        + "\n\n" + method_corpus()
    )
    # Block 2: volatile - today's map and this member. After the breakpoint, so
    # it never invalidates the shared prefix.
    volatile = (
        now
        + (("\n" + today +
          "\nWhen discussing today's map: use ONLY the numbers above, never invent "
          "levels, and teach the method around them. Never turn a level into a "
          "personal buy or sell instruction.") if today else "")
        + (("\n\n" + member_context) if member_context else "")
        + (("\n\n" + extra_instruction) if extra_instruction else "")
    )

    msgs = []
    for m in (history or [])[-8:]:
        role = "assistant" if m.get("role") == "assistant" else "user"
        msgs.append({"role": role, "content": m.get("content", "")})
    msgs.append({"role": "user", "content": user_message})
    return {
        "model": current_app.config.get("CHAT_MODEL", "claude-sonnet-4-6"),
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "system": [
            {"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": volatile},
        ],
        "messages": msgs,
    }


def _log_usage(usage):
    current_app.logger.info(
        "coach call: in=%s cache_write=%s cache_read=%s out=%s",
        usage.input_tokens, usage.cache_creation_input_tokens,
        usage.cache_read_input_tokens, usage.output_tokens)


def _claude_reply(api_key, user_message, chunks, history, member_context="", gated=False):
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    req = _build_chat_request(user_message, history, member_context, gated=gated)
    resp = client.messages.create(**req)
    _log_usage(resp.usage)
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def stream_reply(user_message, history=None, member_context="", gated=False):
    """Yield sanitized text deltas for the coach's reply. The caller accumulates
    the full text. Falls back to one demo-mode chunk when no API key is set.
    Em dashes are single tokens, so per-delta sanitizing is safe."""
    chunks = retrieve(user_message, k=4)
    citations = _citations(chunks)
    api_key = current_app.config.get("ANTHROPIC_TOKEN")
    if not api_key:
        yield {"citations": citations, "used_llm": False}
        yield _no_emdash(_fallback_reply(user_message, chunks))
        return
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    req = _build_chat_request(user_message, history or [], member_context, gated=gated)
    yield {"citations": citations, "used_llm": True}
    with client.messages.stream(**req) as stream:
        for text in stream.text_stream:
            yield _no_emdash(text)
        _log_usage(stream.get_final_message().usage)


def intake_wrapup(profile, assigned):
    """The warm close of the intake conversation: what I heard + your plan.
    One LLM call; deterministic template when no API key."""
    focus = "\n".join(f"- {a['title']} ({a['why']})" for a in assigned) or "- (starting at the front of the method)"
    api_key = current_app.config.get("ANTHROPIC_TOKEN")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            system = (persona.SYSTEM_PROMPT
                      + "\n\nYou just finished the new-member intake. Write a SHORT warm "
                        "wrap-up (under 150 words) in Anne-Marie's coaching voice: reflect "
                        "back what you heard about them in one or two sentences, then give "
                        "them their starting focus (the lessons below, with the reason), "
                        "and close by pointing them to the Today page for the daily map. "
                        "No trade advice, no account-size talk, no em dashes.")
            content = (f"What the member told you: {profile.summary}\n\n"
                       f"Their assigned focus lessons:\n{focus}")
            # Member-facing and a first impression - runs on the chat model.
            resp = client.messages.create(
                model=current_app.config.get("CHAT_MODEL", "claude-sonnet-4-6"),
                max_tokens=350, system=system,
                messages=[{"role": "user", "content": content}])
            out = "".join(b.text for b in resp.content
                          if getattr(b, "type", "") == "text").strip()
            out, _, _ = enforce_compliance(out)  # member-facing LLM text -> same backstop
            return _no_emdash(out)
        except Exception as exc:  # pragma: no cover
            current_app.logger.warning("intake wrapup LLM failed: %s", exc)
    names = " and ".join(f"**{a['title']}**" for a in assigned[:2]) or "the start of the method"
    return _no_emdash(
        "Thank you for being straight with me - that's exactly what I need to coach you. "
        f"Here's where we start: {names}. Work those this week, and every morning open "
        "the Today page first: the day's read and levels are there before the bell. "
        "When something on the chart confuses you, come ask me. We go level to level, "
        "and we keep risk small.")


# --------------------------------------------------------------- the aha first read
def _day_type_phrase(ds):
    """Her plain-language name for today's day type (no numbers)."""
    v, g = ds.get("verdict", ""), ds.get("gate", "")
    if g == "stand_down" or v in ("sideways", "pending"):
        return "a stand-down day - her 30-minute trend gate is flat, no clean edge"
    if v.startswith("up"):
        return "an upward stair-step day - her bias is higher, and she waits for dips to her levels"
    if v.startswith("down"):
        return "a downward stair-step day - her bias is lower, and she sells bounces into her levels"
    return "a mixed day that needs careful reading before any commitment"


def _matched_rule(ds, struggle_keys):
    """The single most relevant real rule for THIS day type x THIS struggle (the engine
    picks the fusion; the model only voices it)."""
    v, g = ds.get("verdict", ""), ds.get("gate", "")
    s = set(struggle_keys or [])
    if g == "stand_down" or v in ("sideways", "pending"):
        if s & {"revenge", "overtrading", "chasing"}:
            return "a zero-trade day is a win"
        return "trade the edges if anything, the middle is where the traps are"
    if v.startswith("up"):
        return "wait for the fade to the level, never chase the breakout"
    if v.startswith("down"):
        return "bounces are sells, the edge is the level not the first drop"
    return "wait for the fade, never chase"


_FR_NUMBER = re.compile(r"\d{4,6}")
_FR_IMPERATIVE = re.compile(
    r"(?i)\byou should (buy|sell|short|go long|take|enter|exit|trade|avoid)\b"
    r"|\b(buy|sell|short|go long) (it|now|here|today)\b"
    r"|take the trade|don'?t trade today|do not trade today")
_FR_ATTRIB = re.compile(
    r"(?i)her (method|rule|read|framework|bias)|by her method|she (would|teaches|says|waits)")


def first_read_ok(text):
    """Deterministic compliance lint - runs BEFORE the read is shown. No price number,
    no individualized trade imperative, must carry an impersonal her-method attribution,
    no em dash."""
    if _FR_NUMBER.search(text):
        return False, "contains a price number"
    if _FR_IMPERATIVE.search(text):
        return False, "individualized trade imperative"
    if chr(0x2014) in text:
        return False, "em dash"
    if not _FR_ATTRIB.search(text):
        return False, "missing impersonal her-method attribution"
    return True, ""


def _first_read_fallback(profile, ds, rule):
    """Always-compliant deterministic first read (no key / closed day / lint failure)."""
    mirror = (f"You told me {profile.struggles_raw[:120]}."
              if getattr(profile, "struggles_raw", "") else
              "You told me where you are and what you want to change.")
    return _no_emdash(
        f"{mirror} Here is what today reads as by her method: {_day_type_phrase(ds)}. "
        f"Her rule for a day like this: {rule}. Tomorrow morning I will have this computed "
        f"and waiting before your coffee, and I will be right here when the screen is open "
        f"and the urge hits. That is what this is.")


def first_read(profile):
    """THE aha. Fuse what the member SAID they want (their goal + struggle, in their own
    words) with TODAY's real computed state (verdict + gate, NEVER numbers) and her matching
    rule - so they hear exactly the help they just asked for, proven on today's market.
    Compliance-linted; falls back to a safe deterministic version on any doubt."""
    from .levels import day_state
    from .marketdata import session_state
    from .mentor import experience_tier
    ds = day_state((getattr(profile, "instruments", "") or "").split(",")[0].strip()[:8])
    closed = session_state().get("closed_today")
    struggles = [k for k in (getattr(profile, "struggles_keys", "") or "").split(",") if k]
    rule = _matched_rule(ds, struggles)
    api_key = current_app.config.get("ANTHROPIC_TOKEN")
    # No live read available (no map, or market closed) -> safe generic-but-labeled fallback.
    if not ds or closed or not api_key:
        return _first_read_fallback(profile, ds, rule)
    tier = experience_tier(profile)
    altitude = {
        "beginner": "Explain each idea in plain English before naming it; tie it to a concept to "
                    "learn, not a trade. Never assume they have or should have real money at risk.",
        "developing": "Use her vocabulary with a one-line gloss. Assume chart literacy, not her system.",
        "experienced": "Meet them as a peer - shortest, most precise version, her real vocabulary, "
                       "no scaffolding.",
    }[tier]
    system = (persona.SYSTEM_PROMPT
              + "\n\nThis is the new member's FIRST moment, right after intake. Write ONE short "
                "paragraph (60 to 85 words) in Anne-Marie's voice that makes them feel you heard "
                "exactly what they want and are handing them precisely that, proven on today. "
                "STRUCTURE, in this order: (1) mirror back what THEY said they want to fix, in their "
                "own words; (2) say what today reads as by her method, naming the day type; (3) cite "
                "her one real rule for that; (4) one forward-promise sentence: tomorrow this is "
                "computed and waiting before their coffee, and you are right here when the hard "
                "moment hits; (5) close with exactly: That's what this is. "
                + altitude
                + " HARD: no price numbers, no 'you should' trade calls, no size or income, no "
                  "urgency/sales language, no em dashes. Always frame as 'her method reads' or 'her "
                  "rule', never as your own call.")
    content = (f"What they said they want to change: {getattr(profile, 'goal', '')[:160]}\n"
               f"What trips them up (their words): {getattr(profile, 'struggles_raw', '')[:200]}\n"
               f"Today by her method: day type = {_day_type_phrase(ds)}; verdict = {ds.get('verdict')}; "
               f"gate = {ds.get('gate')}; in-charge = {ds.get('in_charge')}.\n"
               f"The rule to cite for this combination: \"{rule}\".")
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=current_app.config.get("CHAT_MODEL", "claude-sonnet-4-6"),
            max_tokens=220, system=system,
            messages=[{"role": "user", "content": content}])
        text = _no_emdash("".join(b.text for b in resp.content
                                  if getattr(b, "type", "") == "text").strip())
        ok, why = first_read_ok(text)
        if not ok:
            current_app.logger.warning("first_read lint rejected (%s); using fallback", why)
            return _first_read_fallback(profile, ds, rule)
        return text
    except Exception as exc:  # pragma: no cover
        current_app.logger.warning("first_read LLM failed: %s", exc)
        return _first_read_fallback(profile, ds, rule)


def checkin_reply(user, kind, text):
    """Short mentor reflection on a daily check-in. Grounded in the method,
    today's map, and the member's profile."""
    from .mentor import member_context
    prompt = (
        f"[Daily check-in - {'morning plan' if kind == 'plan' else 'after-close review'}] "
        f"The member wrote: \"{text}\"\n\n"
        "Reply as their mentor in UNDER 80 words: acknowledge specifically, connect it "
        "to her method (the day's read if relevant), and reinforce process over P&L. "
        "If they followed their rules, say that IS the win. If they broke a rule, name "
        "it kindly and point to the relevant habit. Never give trade directions.")
    reply, used_llm, _ = generate_reply(prompt, history=[],
                                        member_context=member_context(user))
    if not used_llm:
        reply = ("Logged. Remember what matters: did you follow the process today? "
                 "A disciplined zero-trade day beats a lucky win. The buffet is open "
                 "again tomorrow.")
    reply, _, _ = enforce_compliance(reply)
    return _no_emdash(reply)


def _fallback_reply(user_message, chunks):
    """Deterministic, grounded reply for demo mode (no API key)."""
    if persona.looks_like_advice_seeking(user_message):
        lead = (
            "I hear you wanting a call here - but that's not what I'm for, and it's not "
            "how Anne-Marie trades. I won't tell you to buy or sell anything. What I *can* "
            "do is walk you through her process so **you** make the read.\n\n"
        )
    else:
        lead = ""

    if chunks:
        top = chunks[0]
        body = (
            f"Here's how Anne-Marie thinks about that - from **{top['title']}**:\n\n"
            f"> {top['text'].strip()}\n\n"
        )
        if len(chunks) > 1:
            also = ", ".join(f"*{c['title']}*" for c in chunks[1:3])
            body += f"Related in her playbook: {also}.\n\n"
        body += (
            "Want me to break any of that down further, or turn it into a checklist you "
            "can tape to your monitor?"
        )
    else:
        body = (
            "I don't have a curated note on that yet, so I won't make something up. Here's "
            "the spine of her approach, though: direction first (trade with the 30-minute "
            "200 and 50 SMA), wait for price to come to a level, take the *failed retest*, "
            "use limits, go level-to-level on exits, and keep your risk small. Ask me about "
            "any of those and I'll go deeper."
        )

    note = (
        "\n\n_(Demo mode: I'm answering straight from Anne-Marie's curated knowledge. "
        "With the live AI coach enabled, I'll talk this through with you conversationally.)_"
    )
    return (lead + body + note).strip()
