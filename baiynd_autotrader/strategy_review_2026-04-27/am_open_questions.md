# Open Questions for AM — Escalation Queue
## Anne-Marie Baiynd Strategy Clarifications

**Author:** Final Synthesis Writer (Agent 22 of 22)
**Date:** 2026-04-27
**Companion documents:** `strategy_synthesis.md`, `improvement_roadmap.md`

---

## How to Use This Document

This is the queue of questions to bring to Anne-Marie Baiynd in upcoming sessions. They are ranked P0 (ask first), P1 (ask soon), P2 (batch later).

Each item includes:
- **ID** for cross-reference
- **Question** in one sentence, plain English
- **Why it matters** — what changes based on her answer
- **Default assumption** — what V2_4 will do until she clarifies
- **Source** — transcripts and reports that surfaced it
- **Blocks** — code work items dependent on the answer

Bring the P0 items to the next conversation. Aim for one walkthrough session and one rapid-fire Q&A session to clear the P0 + P1 queue.

---

## P0 — Ask First (Blocking the Indicator Rebuild)

These three answers unlock the most impactful indicator fixes. Without them, the indicator stays at PF 0.94.

---

### AM-Q-01 — Body-Stack Node Count: 3 or 4?

**Question:** When you said in the apr-23 session "the 6 PM must sit below the 4 AM must sit below the 9:30 to take a long" and "all three have to converge in the right direction," does that mean only B, C, D need to stair-step (3 nodes), or do you also include the prior-day 3:30 candle (A) so that A < B < C < D (4 nodes)?

**Why it matters:** V2_4 currently requires all four candles to stair-step (A < B < C < D for long trend). The transcript explicitly says only three. If the rule is 3-node, V-shape recovery days (B dips below A, C recovers above B, D breaks above A) are valid LONG TREND days. V2_4 currently classifies these as Sideways and routes them to FADE — which itself is dead because of the vocabulary bug. The 3-node interpretation is estimated to expand the LongTrend day count by 20-30% in the historical corpus.

**Default assumption (until answered):** Keep V2_4 at 4-node strict. Document the open question. Switching to 3-node retroactively reclassifies historical sessions and requires re-running the FADE filter analysis.

**Source:** `wave1_extracts/transcript_apr-23_extract.md` §1.3, lines 60-62 of the transcript. Also `wave3_synthesis/gap_to_am.md` §GAP3.

**Blocks:** C-11 (body-stack code change). Also informs M-03 (body_stack_node_count feature for ML).

---

### AM-Q-02 — FADE Direction on Sideways Days: One-Sided or Two-Sided?

**Question:** On apr-23 you took both a top-short (7172 → 7107, ~65 points) AND a bottom-long (7092 → 7140, ~48 points) on the same sideways day where the 200-SMA was up-sloping. You said in the closing recap, "You can go in both directions. You can go long, you can go short. So you look for the old high, you short it. You look for the old low, you take it long." But the slope-up bias suggests the bottom-long should be the higher-conviction trade. What's the rule for the counter-slope side — full size, half size, quarter size, or skip entirely?

**Why it matters:** V2_4 today fires FADE only in the slope direction (slope up → only longs eligible). If you trade both edges, half of all FADE setups are blocked. The apr-23 top-short was the larger of your two trades that day; V2_4 would have skipped it. The transcript supports half-size or less for the counter-slope side, but the exact sizing needs confirmation. This is likely the largest single source of "missed valid setups" Afshin reports.

**Default assumption (until answered):** Wire two-sided FADE with full size on slope-side, half size on counter-slope. Document this as a working assumption.

**Source:** `wave1_extracts/transcript_apr-23_extract.md` §2.5 (the one-sided vs two-sided ambiguity), lines 79-80 vs line 154 of the transcript. Also `wave3_synthesis/gap_to_am.md` §GAP4.

**Blocks:** C-12 (FADE two-sided code change).

---

### AM-Q-03 — 200-SMA Slope-Magnitude Threshold (Flat vs Steep)

**Question:** In apr-24 you said the Fibonacci runner caps at 150% on a flat 200-SMA and runs to 200% (or 250%) on a steep 200-SMA, and that "machine learning will figure out the threshold." For the first version we need a starting number. Roughly: what 9:30-to-9:30 SMA200 delta (in points per session, on ES 30-min) separates "flat/dampening" from "steep/runaway"? Even a directional answer like "less than 5 ES points per day = flat" or "more than 10 = steep" is enough to ship. We can refine with ML later.

**Why it matters:** Without a starting threshold, the runner doctrine cannot be implemented. The team will either ship without the slope gate (treating all trends as if flat, capping at 150%) or hardcode an arbitrary value. Either is suboptimal. Your starting estimate is what gets shipped to ML for refinement.

**Default assumption (until answered):** Use a placeholder of 5 ES points per 6.5-hour RTH session as the flat/steep boundary. Document as placeholder. Plan to ML-tune.

**Source:** `wave1_extracts/transcript_apr-24_extract.md` §2 (Fibonacci targets), lines 252-253 of the transcript. Also `wave3_synthesis/gap_to_am.md` §GAP1.

**Blocks:** C-13 (level-to-level exit doctrine code), M-04 (Fibonacci runner label in Python pipeline).

---

## P1 — Ask Soon (Important for Encoding Completeness)

These six clarifications unblock the second tier of indicator fixes (P1 items in the roadmap). Aim to resolve them within 30 days.

---

### AM-Q-04 — 1:30 PM ET Candle: Always-Tracked or Conditional?

**Question:** You said in mar-6 that the 1:30 PM candle is a turn-around level "every day, by a couple of minutes." But in apr-16 you said it only matters on retracement events with validated MOC. Is the 1:30 candle a permanent named level we track every day on the chart (like the 4 AM and 3:30 candles), or is it a conditional level that only becomes a candidate when price has pulled back into it AND MOC is validated?

**Why it matters:** Implementation shape is different. Permanent tracking means it's always in the candidate pool with a touch latch — simpler to wire, more setups visible. Conditional tracking means it's gated behind a retracement-detector and MOC validation — a non-trivial detector to build. We want to ship the right shape from V1.

**Default assumption (until answered):** Track the 1:30 candle as a permanent level. Mar-6 conviction is stronger ("every day"). Gate to TREND candidate pool only.

**Source:** `wave1_extracts/transcript_mar-6_extract.md` lines 69-72; `wave1_extracts/transcript_apr-16_extract.md` lines 124-135. Also `wave3_synthesis/gap_to_am.md` §GAP11.

**Blocks:** C-15 (1:30 PM candle capture and tracking).

---

### AM-Q-05 — 50% Midpoint Add Geometry

**Question:** You've described two add-mechanics that may or may not be the same trigger. In apr-10 you said you add when the 50 SMA, the VWAP, and the 200 SMA all converge ("if the 50 converges with the VWAP and the 200 and the 200 is pointing up, it's going to rocket back to the top"). In apr-24 you said you add at the 50% midpoint of the entry candle and tighten the stop to the 50% line ("any bounces up we can add to that position and we could make our stop the 50% line"). Are those the same trigger expressed two ways, or two different add-mechanics? If different, when does each apply? A live chart walkthrough showing one of each would clarify the geometry.

**Why it matters:** The add-rule is the source of your biggest winners (the runners that get amplified by the second contract). Implementing the wrong geometry means missing the right setups or adding into noise. We are deferring this to V2 of the indicator if the geometry is unclear, but a live walkthrough now would let us include it in V1.

**Default assumption (until answered):** Defer the add-mechanic to V2. V1 stays single-entry, single-exit. Document the rule manually in the playbook so Afshin can practice it on sim.

**Source:** `wave1_extracts/transcript_apr-10_extract.md` line 39:30; `wave1_extracts/transcript_apr-24_extract.md` lines 134-143, 209. Also `wave3_synthesis/gap_to_am.md` §GAP16.

**Blocks:** C-20 (50% midpoint add-rule and stop tightening).

---

### AM-Q-06 — 2× Candle Width on Sideways Days: Confirm Provenance

**Question:** The V2_4 spec includes a rule "stop = 2× candle width on sideways days." This rule is not in the apr-23 or apr-24 transcripts that we have extracted. Is this a real rule from another session, or has it been superseded? On a sideways day with FADE entries, what is the actual stop sizing rule — 1× the entry candle width, 2× the entry candle width, or something else?

**Why it matters:** The stop sizing rule on sideways days affects roughly half the trading days. If the stop is too tight (1× on a noisy sideways day), trades get wicked out. If too wide, R-multiples deteriorate. We need to confirm this before the level-to-level exit doctrine is shipped (because the stop is the denominator for every R-calculation).

**Default assumption (until answered):** Use 1× candle width on FADE days, same as TREND. Document as a working assumption. Adjust to 2× if AM confirms.

**Source:** `wave1_extracts/transcript_apr-24_extract.md` §6 — "the 2× candle width rule is NOT in apr-24."

**Blocks:** C-13 (stop sizing on FADE entries).

---

### AM-Q-07 — Multi-Day 3:30 Volume Significance Threshold

**Question:** In apr-23 you compared today's 3:30 candle volume against yesterday's and two-days-ago: "two days ago the 3:30 had 250,000 contracts, which is almost twice the amount that it had yesterday. Today, check this out, 271,000." So the "almost twice" comparison made you call yesterday's level not significant. What's the threshold? Is "volume significant" a 1.5× multiplier, 1.8×, 2×, or just qualitative?

**Why it matters:** This is a level-quality filter. When we know that the prior-day 3:30 candle had outlier volume relative to recent days, the level it created is more likely to hold. Currently V2_4 treats all prior-3:30 levels equally. Encoding this multi-day comparison requires a numeric threshold.

**Default assumption (until answered):** Use 1.5× as the threshold for "volume significant" — flag levels whose origin candle volume exceeded 1.5× the average of the prior 3 days' same-window volumes. Document as placeholder.

**Source:** `wave1_extracts/transcript_apr-23_extract.md` §7.1, lines 41-44.

**Blocks:** C-17 refinement (news-candle wick detection); M-03 (multi-day volume features for ML).

---

## P2 — Batch Later (Refinements and Edge Cases)

These can wait for batch processing. Useful but not blocking the core V1 ship.

---

### AM-Q-08 — V-Shape Recovery: Is It a Long Trend or Sideways?

**Question:** Your apr-23 long-trend template (lines 13-15) describes a setup where "the GlobeEx is a dip and then the 4 a.m. is higher than the GlobeEx and later in the pre-market we're getting into that old 330 candle, then if the 9:30 opens and it breaks above, it's a long." This is a V-shape — B dips below A, C bounces above B, then D breaks above A. Does that count as a long-trend day, or is the B-dip enough to make it sideways? The strict "monotonic stair-step" interpretation says sideways. Your verbal example says long.

**Why it matters:** Closely related to AM-Q-01. If V-shapes count as long-trend, the 3-node interpretation (B<C<D) is correct and we don't need A to participate. If the strict interpretation is correct, V-shapes are sideways and we need the body to monotonically step.

**Default assumption:** If AM-Q-01 confirms 3-node, V-shapes are long-trend (B<C<D holds). If 4-node, V-shapes are sideways.

**Source:** `wave1_extracts/transcript_apr-23_extract.md` §1.3.

**Blocks:** C-11 (subsumed by AM-Q-01 answer).

---

### AM-Q-09 — First Scale-Out Fraction at 100% Fibonacci

**Question:** When the runner trade reaches the 100% Fibonacci extension (the "first target"), you take partial off — but is it always 50% of the position, or do you vary the fraction based on conviction (e.g. 33% on Cautious, 50% on Trend, 75% on Friday-full-size)?

**Why it matters:** The scale-out fraction directly affects the runner's effective size and therefore the right-tail amplification. A 50% fixed scale-out is the simplest implementation; a variable fraction is more nuanced.

**Default assumption:** 50% fixed scale-out at 100% Fib, then full remainder runs to 150% or 200% per slope state.

**Source:** `wave1_extracts/transcript_apr-24_extract.md` §2 (Fibonacci runner discussion).

**Blocks:** C-13 (level-to-level exit doctrine; refinement).

---

### AM-Q-10 — FADE Day Targets: First Reachable or Hold for Prior-3:30?

**Question:** On apr-23 you covered the bottom-long at the 4 AM close (~7142), not at the prior-day 3:30 high. You said "the longer it sits there, the more likely it is that it doesn't [run through]. So, I'm not waiting around. I'm getting my money and I'm leaving." Does that mean on FADE days you always take the first reachable structural level, or do you sometimes hold for the prior-3:30 level (the further target)?

**Why it matters:** V2_4's current FADE target is only the prior-3:30 level. We are planning to add a 3-target ladder (T1 = 4 AM close / pre-market, T2 = pre-market opposite, T3 = prior-3:30). The question is whether we always exit at T1 when it's reached, or whether T1 is a partial-exit point and we hold the rest for T2/T3.

**Default assumption:** Always exit at first reachable target on FADE days. No multi-stage scaling on FADE.

**Source:** `wave1_extracts/transcript_apr-23_extract.md` §2.4, lines 85-86. Also `wave3_synthesis/gap_to_am.md` §GAP6.

**Blocks:** C-14 (FADE target ladder implementation; refinement).

---

### AM-Q-11 — Day-of-Week Probability Table

**Question:** You said in apr-16 that "this shifts every day of the week. The statistical probability and the threshold size, what size you want to position it, it's now triggered by days of the week." You've explicitly told us Friday gets full-size escalation when bodies don't overlap and MOC is validated. What about Monday, Tuesday, Wednesday, Thursday? Is each day's "shift" something you can describe verbally, or is it intuitive enough that you'd rather have ML discover it from data?

**Why it matters:** Encoding day-of-week sizing logic explicitly is more transparent than letting ML discover it. But if the rules are too subtle to verbalize, ML is the right tool. We just want to make sure we're not missing a verbalizable rule.

**Default assumption:** Encode only the Friday full-size escalation (apr-24 §7e). Let ML discover the rest.

**Source:** `wave1_extracts/transcript_apr-16_extract.md` lines 148-150; `wave1_extracts/transcript_apr-24_extract.md` lines 290-303.

**Blocks:** C-21 (Friday full-size escalation; refinement). M-03 (day-of-week features for ML).

---

### AM-Q-12 — Pre-Place Limit vs Confirmation Entry: Which by Day-Type?

**Question:** In apr-24 you said confirmation entry (two 5-min candles trending back, bodies not overlapping) is the default, and pre-placed limits are the exception for full trend days. Today V2_4 is mostly pre-placed-limit (signals fire when a 1-min bar prints through the level). For a beginner like Afshin, we want to make this explicit: on which day-types do you place limits, and on which do you wait for confirmation?

**Why it matters:** Different entry mechanics mean different signals fire on different days. Our current implementation is closer to "limit at touch always," which over-fires on non-trend days and under-fires when the confirmation pattern (Pattern B) would have been the right entry. Once Pattern B is wired, this question essentially becomes: "which entry pattern is the default per day-type?"

**Default assumption:** Pattern A (pre-placed limit) is the entry on full-trend days (LongTrend / ShortTrend). Pattern B (look-below-and-fail) is the entry on Cautious days and on FADE days. Document this routing.

**Source:** `wave1_extracts/transcript_apr-24_extract.md` §7a, lines 49-66.

**Blocks:** None directly; informs the V1 design.

---

### AM-Q-13 — "Volume Significant" Qualitative Threshold

**Question:** When you flag a candle as "volume significant," what's the rough threshold? In apr-24 the 237k news candle vs 141k 9:30 vs 127k 3:30 was significant (1.7× the 9:30, 1.9× the 3:30). In the AVIS case study you said "not volume significant" without giving a number. Is this a 1.5× / 2× ratio rule, or pure pattern recognition?

**Why it matters:** The news-candle wick detection rule depends on this threshold. Currently we have "candle volume > max(prior 9:30 vol, prior 3:30 vol)" from apr-24, which gives roughly 1× as the threshold. If your actual threshold is 1.5× or 2×, the detection rate is much lower (only the truly outlier candles).

**Default assumption:** Use the apr-24 stated rule literally — "greater than max(prior 9:30, prior 3:30)" — which means 1× is enough. Document as the v1 implementation.

**Source:** `wave1_extracts/transcript_apr-24_extract.md` §5, lines 344-362.

**Blocks:** C-17 (news-candle wick detection; refinement).

---

### AM-Q-14 — Stop Sizing on Sideways Fades: Discretionary or Level-Anchored?

**Question:** On apr-23 you said you "give it a little room" for the top-short on the sideways day. You didn't specify points or candle width. Is the FADE stop discretionary (you eyeball it) or is there a level-anchored rule (e.g. "stop = 5 ticks above prior-3:30 H" for top-short, "stop = 5 ticks below prior-3:30 L" for bottom-long)?

**Why it matters:** For autonomous execution, "discretionary" is not implementable. We need a deterministic rule. If it's level-anchored, we just need the level reference and the tick offset.

**Default assumption:** Use 1× the FADE entry candle width as the stop, same as TREND. Document as working assumption.

**Source:** `wave1_extracts/transcript_apr-23_extract.md` §2.6.

**Blocks:** C-13 (stop sizing; refinement).

---

### AM-Q-15 — CL-Specific Rules

**Question:** You've tabled CL for now. When you do trade CL, do the same rules apply directly (master candles, MOC, body stack, slope, FADE)? Or are there CL-specific differences — different timing (CL opens at 9:00, not 9:30), different MOC computation (CL settles at 14:30), different level sets, different doctrine? When CL comes back into scope, what should we re-validate?

**Why it matters:** When you re-enable CL, we need to know whether our ES/NQ encoding can be extrapolated, or whether CL needs a from-scratch session walkthrough. This question is fully deferrable until CL becomes priority again.

**Default assumption:** Disable CL trading until you walk through CL specifically. Fix the CL `rthOpenHour` bug for hygiene (so the indicator doesn't corrupt CL data when active), but keep `AllowCLTrading=false` in production until you re-enable.

**Source:** Task brief; `wave3_synthesis/gap_to_am.md` §GAP10.

**Blocks:** None currently; CL is tabled.

---

## Summary Table

| ID | Title | Pri | Blocks |
|----|-------|-----|--------|
| AM-Q-01 | Body-stack 3-node vs 4-node | P0 | C-11 |
| AM-Q-02 | Two-sided FADE counter-slope sizing | P0 | C-12 |
| AM-Q-03 | 200-SMA slope-magnitude threshold | P0 | C-13, M-04 |
| AM-Q-04 | 1:30 PM candle tracking discipline | P1 | C-15 |
| AM-Q-05 | 50% midpoint add geometry | P1 | C-20 |
| AM-Q-06 | 2× candle width on sideways days | P1 | C-13 |
| AM-Q-07 | Multi-day 3:30 volume significance threshold | P1 | C-17 (refines), M-03 |
| AM-Q-08 | V-shape recovery interpretation | P2 | C-11 (subsumed by AM-Q-01) |
| AM-Q-09 | First scale-out fraction at 100% Fib | P2 | C-13 (refinement) |
| AM-Q-10 | FADE day target choice | P2 | C-14 (refinement) |
| AM-Q-11 | Day-of-week probability table | P2 | C-21 (refines) |
| AM-Q-12 | Pre-place limit vs confirmation entry default | P2 | None directly |
| AM-Q-13 | "Volume significant" qualitative threshold | P3 | C-17 (refines) |
| AM-Q-14 | Stop sizing on sideways fades | P3 | C-13 (refines) |
| AM-Q-15 | CL-specific rules | P3 | C-04, AM has tabled |

**Recommended conversation plan:**
- **Session 1 (rapid Q&A, 30 min):** AM-Q-01, AM-Q-02, AM-Q-03. These three answers unblock the highest-impact code work in the next 2 weeks.
- **Session 2 (live walkthrough, 60-90 min):** AM-Q-04, AM-Q-05, AM-Q-06. These benefit from chart examples.
- **Session 3 (batched Q&A, 30 min):** AM-Q-07 through AM-Q-12 in one pass.
- **Future:** AM-Q-13, AM-Q-14, AM-Q-15 — deferred until they become blocking.

---

*End of am_open_questions.md.*
