# AM Meeting Priorities — 2026-04-28
## What to lock down with Anne-Marie tomorrow

**Author:** AM-Needs Analyst (Wave 4 of V2_5 rebuild)
**Date prepared:** 2026-04-27 (eve of the meeting)
**Audience:** Afshin (the trader), pre-call prep document
**Time budget assumption:** 30–45 minutes of AM's focused attention. Use it like it's the last call of the quarter.

---

## TL;DR — The Five Items, Ranked

1. **Body-stack: three nodes or four?** (1 minute. Highest leverage of any single sentence she could say.)
2. **FADE direction on sideways days — both edges or only the slope side?** (3 minutes. Confirms a known divergence between her words and V2_4.)
3. **Walk her through one current chart so she can validate V2_5's interpretation live.** (10–15 minutes. The single highest-information-content activity.)
4. **Slope steepness threshold for runner targets — give us a starting number she can sanity-check.** (5 minutes. Unblocks the Fibonacci runner ladder.)
5. **The "most important box of the day" — teach this rule on the chart.** (10 minutes. AM promised to teach this on apr-9 and pivoted; it remains the single biggest unmaterialized rule in the corpus.)

These five fit comfortably in 30 minutes and they each address a different kind of ambiguity (interpretive, behavioural, calibration, conceptual). Everything else can be batched in email.

---

## 1. The Five Top-Priority Items

### Priority #1 — Body-stack: three nodes or four?

**The question, exactly as Afshin should ask it:**

> "Anne-Marie, on apr-23 I caught a sentence I want to lock in. You said *'The 6 PM candlestick must sit below the 4 a.m. candlestick must sit below the 9:30 candlestick to take a long. The GlobeEx must sit above the 4:00 a.m. must sit above the 9:30 to go short. All three have to converge in the right direction.'* So three candles — Globex, 4 AM, 9:30. Right now my code requires four — the prior day's 3:30 PM candle has to also stack. Should the prior 3:30 be a fourth required link in the chain, or is it just the target zone and context, with the chain itself only being three?"

**Why it matters now:** The day-type gate is the single on/off switch for the entire system. The 4-node interpretation is over-classifying valid trend days as Sideways — every V-shape recovery (B dips, C and D recover) gets thrown into the wrong bucket. The gap detective estimates this affects 20–30% of would-be LongTrend days, redirecting them into FADE-or-no-fire mode. V2_5 currently emits both interpretations as features (`stack_3node_pass: bool` and `stack_4node_pass: bool`) so the architecture is shippable either way — but AM's clarification meaningfully improves the L2 heuristic's day-type prior, and tells us which feature to weight more heavily as the labelled trade history accumulates.

**What we currently assume in code:** V2_5 L1 emits both. The L2 heuristic scorer currently down-weights candidates from a day classified `Sideways` under the 4-node test even when 3-node passes. AM's "all three" verbatim is the strongest single clue that 4-node is over-strict.

**Form of answer that unblocks:** Binary plus brief explanation. "Three nodes, A is just the target" → we down-weight 4-node feature. "Four nodes, I always look at the 3:30 too" → we keep 4-node primary. "Sometimes 3, sometimes 4 depending on overnight context" → we keep both as features, no change.

**Estimated time:** 1 minute. This is the cleanest yes/no question on the list.

---

### Priority #2 — FADE direction on sideways days: both edges, or only the slope side?

**The question, exactly as Afshin should ask it:**

> "On apr-23 you took a sideways day in two directions — short the 7172 top, then long the 7092 bottom — even though the 200 SMA was sloping up. At the end of that session you said *'You can go in both directions. You can go long, you can go short. You look for the old high, you short it. You look for the old low, you take it long.'* My code today only fires the slope-side fade — when the 200 is up, only longs at the bottom. Is that wrong? On a sideways day with an UP-sloping 200, do you take the short at the top? And if yes, at full size, half size, or quarter size?"

**Why it matters now:** This is GAP 4 in the detective report. AM's apr-23 closing recap is the cleanest statement she's ever made of the FADE rule, and it's two-sided. V2_4 wired one-sided FADE on the same day this gap was identified. Apr-23 alone was ~113 points of two-sided opportunity (65 short + 48 long), of which V2_4's one-sided rule would have captured maybe 48. On any sideways day — roughly half of all sessions per the JSONL classifier — one valid trade is currently being structurally blocked. The architectural shift in V2_5 emits both-side candidates regardless, so the question is now about how to score them: equal weighting, or counter-slope at half-size, or counter-slope blocked entirely.

**What we currently assume in code:** V2_5 L1 emits candidates at both range extremes. The L2 heuristic currently scores counter-slope FADE candidates at 0.5x of slope-direction FADE candidates (as a placeholder). She can move this to 1.0x (equal), 0.25x (heavily reduced), or 0x (block, but log).

**Form of answer that unblocks:** Scalar with sizing rule. "Both at full size, slope is just intuition" → 1.0x. "Both, but counter-slope half size" → 0.5x with sizing flag. "Only slope side, the apr-23 short was a mistake" → 0x (and we know the heuristic prior).

**Estimated time:** 3 minutes — including the apr-23 chart on screen so she can re-validate her own reasoning.

---

### Priority #3 — Walk her through one live chart and let her validate V2_5

**The question, exactly as Afshin should ask it:**

> "Anne-Marie, here's a chart from this past week. The new indicator is showing all the candidates it sees — every level inside every bar — with a little badge for which pattern type and which day-type interpretation. Can you walk through what you'd actually take here, and let me know which candidates you'd reject and which you'd take? I want to make sure the interpretation matches yours before I tune the scorer."

**Why it matters now:** Every other question on this list is a leaf in the decision tree. This question exposes the whole tree at once. AM's apr-23 walkthrough was *the* most informative session in the corpus because she narrated her decisions in real time at named price levels, and the gap detective could cross-reference each decision against V2_4's behavior and find the silent drops. A second walkthrough on V2_5's actual screen would do the same thing but proactively — we'd see her reject candidates, validate candidates, and articulate reasons that aren't in any of the existing transcripts. Specifically, we'd surface things she does that she's never explicitly named in a transcript yet (the "intuition residue" she keeps acknowledging).

**What we currently assume in code:** V2_5 L1 surfaces candidates with rich features. L2 heuristic scoring is calibrated against the 7-transcript corpus and the gap detective's gap punchlist. The heuristic has not been validated against AM's live judgment.

**Form of answer that unblocks:** Qualitative. The output is annotations on a chart — which 8 of the 30 candidates surfaced were genuinely tradable; what made the rejected 22 not tradable; whether her reasons match the L2 heuristic's score components.

**Estimated time:** 10–15 minutes — the longest single item on the list. Worth every second. This is where AM's information-density per minute is highest.

**Bring to the meeting:** A printed or screen-shared chart from a recent session where V2_5 has annotated all candidates. If V2_5 doesn't compile in time tonight, fall back to a recent V2_4 chart with hand-marked candidate levels (using the JSONL replay).

---

### Priority #4 — Slope steepness threshold for runner targets

**The question, exactly as Afshin should ask it:**

> "On apr-24 you said the 200 SMA slope decides whether the runner target is 150% or 200%-plus — *'when it's less than a certain amount, you can't look for hyperextensions'* — and you said you didn't know the percentage. You also told me machine learning would figure it out. But I need a starting heuristic for the rule-based scorer before the ML has data. If I look at the 9:30-to-9:30 SMA200 delta in points: what feels flat to you? Less than 1 point per session is flat? Less than 3? More than 5 is steep? Just give me the rough magnitude — your eyeball calibration."

**Why it matters now:** The Fibonacci runner ladder (100% / 150% / 200% / 250%) is the single change most likely to move PF from 0.94 toward AM's 2.5–4 range. The slope is the gate — flat caps the runner at 150%, steep unlocks 200–250%. Without a starting threshold the rule is unimplementable in V1 of L2's heuristic. ML eventually learns it, but ML needs labelled trades to learn from, and labelled trades need the rule to fire first. We're in a chicken-and-egg unless AM gives a starting number.

**What we currently assume in code:** V2_5 L1 emits `sma200_slope_delta_pts` as a feature. L2's heuristic currently uses a placeholder threshold of ±2.0 points/session as the flat/steep boundary. The placeholder is not data-driven.

**Form of answer that unblocks:** A scalar number, even a rough one. "Anything under 5 points feels flat to me" → use 5.0. "I'd say 2 or 3" → use 2.5. "It depends on the instrument" → ask for the ES number specifically. The number doesn't need to be precise; ML will refine it. We just need a defensible starting point.

**Estimated time:** 5 minutes including her thinking time. She'll likely want to pull up a chart and eyeball a few examples before committing to a number — that's fine.

---

### Priority #5 — Teach the "most important box of the day" rule

**The question, exactly as Afshin should ask it:**

> "On apr-9 you said *'there's a way to say which box is the most important [box]. So, let's use your chart.'* You were going to teach it but we pivoted to questions. You said October to early March it was the 4 AM box, and recently it's the 3:30 PM or 9:30. Can you walk me through how you decide which is the most important box on a given day? Once I know the rule I can encode it as a feature, and the scorer can give those candidates extra weight."

**Why it matters now:** This is the single biggest *unmaterialized* concept in the corpus. AM has stated explicitly that there's a determinable rule, named the regime shifts (oct-mar = 4 AM; recent = 3:30/9:30), and never taught the mechanic. It would be an L2 scorer feature with an outsized impact: if 60–70% of "the right trade" on any given day is anchored to a specific box, that box's candidates should be weighted up and the others' weighted down. Right now V2_5 treats all four master candles equally as candidate sources. Knowing the priority order on each day type would dramatically sharpen signal selection without requiring more setups to be added.

**What we currently assume in code:** V2_5 L1 emits all master-candle level interactions equally. L2 has no "primary box" feature — it weights by recency, body-width, and volume. The "primary box" concept is missing entirely.

**Form of answer that unblocks:** Qualitative — the rule itself, plus enough examples for us to extract the heuristic. Likely outputs: "if MOC was validated yesterday's 3:30, that's the primary box today" or "if today's 9:30 has bigger volume than yesterday's 3:30, 9:30 takes over" or "in trending overnight regimes the 4 AM is primary; in chop the 3:30 is primary." The shape of the answer is unknown; that's why we have to ask.

**Estimated time:** 10 minutes. AM will likely want to walk through 2–3 days to articulate the rule. Open the discussion with one chart from a clear 4-AM-primary day and one from a clear 3:30-primary day, and let her contrast.

---

## 2. The Wishlist (~5–10 secondary items, batchable to email)

These are real questions but they don't gate V2_5 architecturally — the heuristic scorer can hold defensible defaults until they're answered. Send them as a batched email after the meeting if there's no time.

**W1. The 1:30 PM candle — daily level or pullback-only level?** Mar-6 says it's a level "every day, by a couple of minutes." Apr-16 says it's a pullback event that "only comes into play if we have a retracement event that gives us the dip buying formation." These are different implementation shapes. V2_5 currently captures the 1:30 candle box and emits its H/L as candidates with a `requires_pullback_context: bool` flag set. AM's clarification would let us set the flag's default correctly.

**W2. Pattern B mechanics under volatile tape — single bar or multiple?** Apr-24 confirms 1-bar via screenshot 4. But apr-23's 7085 reclaim was "savage tape" and AM waited for confirmation rather than buying the limit. Is the 1-bar definition the strict rule, with multi-bar confirmation an optional discretionary overlay on volatile days? V2_5 currently emits both the 1-bar Pattern B and a 2-bar `confirmed_pattern_b` feature. ML can learn the discriminator; AM's hint sharpens the prior.

**W3. The 50% midpoint add — entry-candle midpoint, 1-min VWAP, or 50% of 9:30 specifically?** Apr-24 line 134-143 on the 40-pt 9:30 candle, vs apr-10 line 39:30 on the convergence add. AM's phrasing oscillates. V2_5 doesn't currently support adds (single-entry only); when we wire it, we need this resolved.

**W4. Day-of-week table — is the Gemini-generated stat table real, or did Gemini hallucinate it?** From `AM_questions_pending.md`: Gemini's hardcoded continuation probabilities (Mon 52, Tue 78, Wed 61, Thu 45, Fri 71) make Tuesday a higher-conviction day than Friday, but AM verbally said "Fridays are more bullish than ANY other day of the week." Need her to either confirm the table is real (in which case we encode it) or tell us it's Gemini-generated (in which case we discard it and emit DOW as an ML feature only).

**W5. CL revamp — what's the current state?** Apr-24 verbatim: *"the CL question is let's table it and let me revamp these the ideas."* Three weeks have passed. Has she made progress? If yes, get the new framing. If still tabled, confirm we leave CL out of V2_5 scope.

**W6. The news-candle wick rule on flat 200 SMA.** Apr-24 specifies slope-up → lower wick = support; slope-down → upper wick = resistance. What about flat 200? Probably "neither / no signal" but worth confirming.

**W7. Body-stacking tolerance — strict or tick-based.** V2_5 uses strict (`body_top(X) ≤ body_bottom(Y)`). Should there be a tick tolerance for "near misses" (e.g., 1-tick overlap = treated as stacked)? Probably no — strict is cleaner — but worth one sentence of confirmation.

**W8. AVWAP on her chart.** From `AM_questions_pending.md` (item 5): screenshot 2 shows what looks like an anchored VWAP. Earlier she said she didn't really use it. Is the line decorative or part of decisions on certain days?

**W9. 2-of-3 sticky case — the failed retest mechanic.** When the first three master candles stack but D breaks against, the apr-24 hint was "use the failed-retest at 9:30." V2_5 currently treats this as Sideways for MVP. The Pattern B engine implicitly handles it once wired. Worth one sentence to confirm we don't need a special case.

**W10. The 5-min confirmation rule — pure sideways/cautious only?** Apr-24 makes confirmation entry the default base case, with pre-placed limit reserved for full-trend days. V2_5's Pattern B armed-state implements this for non-trend days. Confirming that pre-placed limits are *only* for full-trend days (not also for confirmed-MOC sideways) closes the last ambiguity here.

These ten can be batched. They're worth answering, but not at the cost of the top-five items above. Sending them post-meeting also gives AM time to think rather than off-the-cuff.

---

## 3. Questions You Should NOT Ask Tomorrow

The architecture has changed since the prior question lists were drafted, and several previously-pending items are now either resolved by V2_5's "emit everything, decide explicitly" design, or covered by ML scoring once data accumulates. Don't waste AM's attention on:

**Don't ask: "What's the exact Pattern B entry/stop calculation?"** Resolved. Apr-24 plus screenshot 4 give the 1-bar definition: entry = breach candle's high (long) / low (short); stop = breach candle's low (long) / high (short). V2_5 implements this.

**Don't ask: "What's the news-candle volume threshold?"** Resolved. Apr-24 line 351-354: candle volume > max(prior 9:30 vol, prior 3:30 vol). Persistence: until eclipsed by a higher-volume candle. V2_5 implements this with a configurable `NewsVolumeMultiplierThreshold` defaulted to 1.0 = AM's exact rule.

**Don't ask: "What's the MOC 0.80–1.00 band — Orange or Gray?"** Resolved. Apr-24 verbatim: *"How about 8 to 1? It'll stay gray. Stay gray."* V2_5 collapses 0.80–1.00 into Gray.

**Don't ask: "What are the exact Fibonacci percentages?"** Resolved. Apr-24: 100% (top of trigger candle) / 150% (cap on flat slope) / 200% (steep slope) / 250% (continuation). The slope threshold separating flat from steep is the only remaining piece, which is Priority #4 above.

**Don't ask: "What's the cautious-mode size or stop widening?"** AM has explicitly tabled this twice. V2_5 treats CAUTIOUS as Sideways for MVP. ML can discover any cautious-specific size/stop adjustments later from labelled data.

**Don't ask: "What pivot levels (R1/R2/R3) are the targets and what are the stops?"** This is in the apr-8 transcript — Woody's pivots, R1–R4 / S1–S4, "extended" banner above R2/R3 — and the rules are clear enough to implement. V2_5 emits pivot interactions as candidate features. AM doesn't need to re-articulate these.

**Don't ask: "What's the right MaxSignalsPerDay?"** Apr-10 verbatim: "usually my max max is five." V2_5 caps at 5. Fine as it stands.

**Don't ask: "Should the SMA20 trail stay or go?"** Apr-9 line 149 verbatim: *"I don't trail any stops. I go level A to level B and I'm done."* This is unambiguous and V2_5 already removes the SMA20 trail in favor of level-to-level exits. No clarification needed.

**Don't ask: "What's the GlobEx box — 6:00 PM only, or wider?"** Resolved. Apr-9 line 438: *"6 p.m. to 6:30 p.m. Eastern time."* V2_5 implements as 18:00–18:30 ET.

**The principle:** AM's ambiguities that V2_5 absorbs as features should not consume meeting time. Things that genuinely change the L1 detection contract or the L2 heuristic prior in a way that materially affects the next 4–6 weeks of development — those are the only items worth her in-person bandwidth. Everything else either ships in V1, ML resolves later, or one-line emails close it.

---

## 4. Meeting Framing — How to Open the Conversation

**The honest narrative, in order:**

> "Anne-Marie, before we dive in, three quick context updates on where the project is. First, I rebuilt the indicator's architecture. The previous version (V2_4) was firing 2 trade signals in 6 months against 741 qualifying level touches — a 0.27% conversion rate. The diagnosis was unambiguous: the indicator was silently filtering out 99.7% of valid setups before they even reached the trade-decision stage. The architectural rewrite fixes the silent-drop problem at the foundation level: V2_5 emits a candidate event for every level interaction inside every bar, with a rich feature vector, and lets a separate scoring layer decide which candidates to take. The indicator never silently drops anything anymore.
>
> Second, the architecture is in three layers — L1 detects, L2 scores, L3 enforces safety. L1 (the indicator) is functional; I expect to have it compiling tonight. L2 and L3 (the strategy) are mid-debug; they're the layers that will turn the candidate stream into actual orders, with all the safety gates. The detection layer is the foundation, the scoring and safety layers are the application.
>
> Third — and this is what I want to spend our time on today — there are a small number of interpretation questions where your clarification meaningfully sharpens the scoring layer. The architecture is shippable without your answers because it emits both interpretations as features. But your clarification tells the scorer which feature to weight more heavily, which speeds up the path from breakeven to AM-grade performance. I have five questions, ranked by impact. The first one is the most important and takes a minute. I'd love to walk through them in priority order, and at the end I'd love to walk you through one live chart so you can validate that V2_5 is interpreting setups the way you would."

**Why this framing works:**

1. It anchors the conversation in *progress*, not in apologies. The 0.27% capture rate is the diagnostic finding that motivated the rebuild — it's a fact, not a confession.

2. It sets expectations: V2_5 is in active development, not finished. AM doesn't need to feel like she's reviewing a polished product; she's reviewing a foundation.

3. It explicitly says her ambiguities are no longer architecture-blockers. This removes the implicit pressure on her to "decide things she hasn't fully decided" — a pressure that's caused her in past calls to give one answer and then qualify it ("but machine learning will figure that out later"). She can give her best answer without feeling she's committing to something binding.

4. It ranks the questions for her. AM is a busy professional. Her time is best spent on the 80% of impact, not on 20 small questions where 18 don't move the needle.

5. The chart-walkthrough at the end is presented as validation, not testing. AM is the prior, V2_5 is the implementation. The walkthrough is for her to *correct* V2_5, not for V2_5 to be *graded* by her.

**What to avoid:**

- Don't apologize for what V2_4 didn't do. The diagnostic finding (0.27% capture) is a feature of the conversation, not a failure to apologize for.
- Don't hide that L2/L3 are still in debug. If the topic of order routing comes up, say honestly: "the strategy layer is mid-debug. I expect to have first orders firing in paper-trade by mid-week."
- Don't try to ask all 10 wishlist items if you have time leftover. Save them for email so AM gets to think; off-the-cuff answers are noisier than considered ones.
- Don't get drawn into the post-earnings-drift / equities discussion. That's a separate trading method (mar-6 §1.1–1.2) and it's out of scope for V2_5. If she wanders there, gently steer back: "happy to talk about that, but for tonight let me make sure we close the V2_5 items first."

---

## 5. Specific Things to Bring to the Meeting

**Must-have (printed or pre-loaded before the call):**

1. **The 0.27% diagnostic chart.** A simple bar chart or table showing "741 qualifying touches, 2 trade signals, 0.27%." This is the conversation-starter for the architecture story. Print it. Source: the JSONL data analysis Q3.

2. **A single printed page with the five P0 questions.** Numbered. Verbatim phrasing. Hand a copy to AM at the start so she can see where the call is going.

3. **A recent chart screenshot showing V2_5 in action (if it compiles tonight).** Annotated with the candidate events emitted by L1. If V2_5 doesn't compile, fall back to a V2_4 chart with hand-marked candidate levels. This is for the walkthrough item (Priority #3).

4. **The apr-23 chart (the sideways day she narrated).** This is the canonical example for Priority #2 — the FADE direction question. Have it ready to put on screen so she can see her own narrated trades and reason about whether the slope rule is one-sided or two-sided.

5. **A specific recent day where V2_5 catches a setup that V2_4 missed.** Pick one from the past 2–3 weeks where the JSONL replay shows V2_4 silent and V2_5 firing a candidate event. This is the "proof of concept" for the rebuild; it answers her implicit question of "did the architectural change actually solve anything?"

**Nice-to-have:**

6. **The gap_to_am.md detective report's GAP punchlist (1-page summary, top 5 only).** Something to refer to if she asks "how do you know what to fix?" — this is the answer.

7. **A draft of the email-batchable wishlist** (Section 2). If the meeting ends early, you can send this as a follow-up while it's fresh.

8. **A timer / clock on screen.** AM has historically said "I'll give you 30 minutes" and stretched to 60–90 when the conversation flows. Don't push past her stated limit, but don't artificially cut yourself short either. Track time.

**Do NOT bring:**

- A list of 20 questions. The whole point of this document is to rank ruthlessly.
- The full architecture spec. She doesn't need to read it; she needs to react to its outputs.
- The full wave1 transcript extracts. Same reason.
- Anything from the post-earnings-drift module. Out of scope.

---

## Closing Note for Afshin

Tomorrow is one of the higher-leverage 30-minute windows of the entire project. The five items above, answered cleanly, would unblock the next 4–6 weeks of development. If the only thing you accomplish is the chart walkthrough (Priority #3), that's still a successful meeting — because the walkthrough surfaces things she's never said in any transcript yet.

The architectural rewrite was the right call. V2_5's "fail open at L1, abstain explicitly at L2/L3" contract is what separates a discretionary tool from an institutional-grade execution stack. AM doesn't need to validate the architecture — that's an engineering judgment. She needs to validate the interpretation. The five questions, plus the chart walkthrough, do exactly that.

End of priorities document.
