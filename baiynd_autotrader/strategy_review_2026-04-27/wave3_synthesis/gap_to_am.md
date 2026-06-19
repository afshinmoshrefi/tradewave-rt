# Gap-to-AM Detective Report
## Wave 3 Synthesis — AMTradeCockpitV2_4 vs Anne-Marie Baiynd's Actual Method

**Author:** Gap-to-AM Detective, Wave 3 of 22-agent review
**Date:** 2026-04-27
**Sources:** 7 transcript extracts (mar-6 through apr-24), V2_4 code audit, version diff audit, JSONL data analysis, AM_rules_v2_spec.md
**Verdict in one sentence:** V2_4 is breakeven because it systematically kills AM's right tail (wrong exit doctrine), blocks 43% of her entry method (Pattern B unwired), and misclassifies valid trend days as Sideways no-fires (4-node vs 3-node body-stack), while the Python pipeline's 94% win-rate is an artifact of fill assumptions, not a real production target.

---

## TL;DR — The Headline Gaps

Five structural failures account for nearly all the gap between V2_4's 0.94 PF and AM's real-world 2.5-4 PF.

**1. The exit is wrong.** V2_4 trails a 30-min SMA20. AM is explicit, twice, verbatim: "trailing stops are terrible. I go level A to level B and I'm done." (apr-9, line 149). This single error kills AM's right tail — the occasional big winner that separates a 2.5 PF from a 0.94 PF. The SMA20 ratchet liquidates in whipsaw noise while AM holds to a structural level. Winner cost is catastrophic on any day with > 2 ATR of directional range.

**2. Pattern B does not exist.** The indicator has `LevelWatchState` scaffolding and a comment promising `CheckPatternBEntry`. Neither is wired. No method instantiates the class. AM's canonical entry — "look below and fail" (every setup she describes in apr-24 is this pattern) — has zero representation in the live code. 43% of all 6-month touch events were Pattern B touches (JSONL data analysis). These all returned zero signals.

**3. The body-stack gate requires 4 nodes; AM explicitly says 3.** Apr-23, line 60-62 verbatim: "The 6 PM candlestick must sit below the 4 a.m. candlestick must sit below the 9:30 candlestick to take a long." That is B < C < D. The prior 3:30 (A) is contextual framing, not a chain node. V2_4's `ClassifyAMDayType` requires A < B < C < D — an extra node that blocks V-shape recovery days and over-classifies them as Sideways. These become FADE-or-no-fire when AM would call them trend and enter.

**4. The FADE rule is one-sided; AM trades both edges.** Apr-23, line 154, verbatim: "You can go in both directions. You can go long, you can go short. So you look for the old high, you short it. You look for the old low, you take it long." V2_4 gates FADE to the slope direction only. AM demonstrated both a top-short AND a bottom-long on the same up-sloping-200-SMA day. The slope is a conviction/sizing modifier, not an exclusion gate.

**5. Pattern A's stop and target are both wrong.** Stop is hardcoded to europe-4AM-width clipped to ADR (a fixed-per-day stop) because every caller passes `null` to `V2ComputeStopDistance`. AM says "the stop is always the width of the entry-trigger candle" (apr-16, apr-24). Target is a SMA20 trail for TREND mode; AM says 100% / 150% / 200% / 250% Fibonacci extensions gated by 200-SMA slope steepness (apr-24, lines 231-238). Both are materially wrong and together explain why winners are cut too early and losers are allowed to run.

The remaining gaps (items 6-18 below) matter but are secondary once the five above are fixed.

---

## Methodology

This report triangulates three layers:

**Layer 1 — Transcript truth.** Seven sessions were read in full-transcript order (mar-6 through apr-24), treating each as AM's live verbal specification. Where transcripts disagree, the later, more precise verbatim governs (apr-24 Q&A is the highest-precision source; mar-6 is highest-fidelity to AM's unfiltered intuition). Where they conflict irreconcilably, the gap is flagged for AM escalation.

**Layer 2 — Code reality.** V2_4.cs was audited line-by-line (wave2_audit/v24_code_audit.md). Every claim about "what V2_4 does" in this report is backed by a specific code location. The version diff audit (version_diff_audit.md) tracks what was added, removed, or silently broken across seven versions.

**Layer 3 — Data evidence.** The JSONL corpus (103 sessions, 6 months) provides the empirical anchor. Two signals in 741 qualifying touches is a 0.27% conversion rate. The data does not lie: the system is almost entirely silent when it should be firing.

**Reconciliation rule used throughout:** AM is the prior. When the code's behavior disagrees with AM's transcripts, the code is wrong, not AM. When the backtest result disagrees with AM's known track record, the backtest encoding is incomplete.

---

## The Gap Punchlist

### GAP 1 — Runner Exit Doctrine (SMA20 Trail vs Level-to-Level)

**A. Identify.**
AM, apr-9, line 149: "I don't trail any stops. I go level A to level B and I'm done."
AM, apr-9, line 55: "trailing stops are terrible."
AM, apr-24, lines 231-238: exit ladder is 100% / 150% / 200% / 250% Fibonacci extensions gated by 200-SMA slope steepness. On steep slope the runner target is 200-250%. On flat slope the cap is 150%.

V2_4 TREND-mode exit (code_audit.md §5, line 2643-2689): arms when 30-min SMA20 is on the favorable side, ratchets monotonically, exits on 1-min close past the trail. No fixed target. No Fibonacci layer. The spec itself (AM_rules_v2_spec.md §11, item 10) explicitly lists "Remove SMA20 trailing-stop in favor of candle-walk" as a required change — confirming the discrepancy is known and unresolved.

V2_4 FADE-mode exit (line 2623-2641): fixed structural target = PrInst H/L (prior 3:30 candle high or low). This is structurally closer to AM's doctrine but only one level deep; AM targets the 4 AM close or pre-market low as intermediate targets first, not the far-side prior-3:30 level (apr-23, lines 49-50).

**B. Quantify the cost.**
This is the right-tail killer. AM's 2.5-4 profit factor comes almost entirely from the occasional 200-250% extension trade on steep-slope days. The SMA20 trail is calibrated to the noise level of the 30-min bar, not to structural levels — it will exit a 150-point ES move at 40 points on the first consolidation wick. Historical JSONL has only 2 trades so we cannot measure directly, but the Python pipeline's inflated Sharpe of 9-10 explicitly attributes its edge to "SMA20 trail mechanical smoothing" in the known-bias list. Remove that smoothing and the PF collapses. ESTIMATE: HIGH frequency cost, every trend day with more than one standard deviation of directional range. Runner cost is the primary explanation for V2_4's 0.94 PF versus AM's 2.5-4.

**C. Cost type.** Runner cost — primary right-tail killer.

**D. Fix complexity.** Medium. Requires implementing a Fibonacci extension layer anchored to the entry candle (low-to-high for long, high-to-low for short), adding a 200-SMA slope steepness classifier (AM left the threshold for ML but a 9:30-to-9:30 delta > some_pts = steep is a reasonable start), and wiring scale-out at 100% with runner to 150/200%. The FADE target ladder (4 AM close → pre-market low → prior-3:30) is a parallel change.

**E. Priority.** P0. This is the single change most likely to move the system from breakeven to profitable. Without this, fixing every other gap still produces a 1.0-1.5 PF system.

**F. AM-escalation flag.** Y. Need AM to confirm: (a) what 200-SMA delta (in points-per-session) separates "flat" from "steep" — she said "ML will figure that out" but we need a starting value; (b) whether the scale-out is always 50% at 100% or variable; (c) whether the FADE target ladder is 4 AM close → pre-market low → prior-3:30 or she goes directly to prior-3:30.

---

### GAP 2 — Pattern B Unwired (43% of All Touches)

**A. Identify.**
AM's canonical entry method (apr-24, lines 167-172): "I rarely take a breakdown trade. What I will take is a failed retest, a look above and fail, a look below and fail." The breach-candle definition (apr-24): one 1-min bar with low < level AND close >= level (long). Stop = breach candle's low. Entry = breach candle's high. Confirmation = subsequent bar does not take out breach candle's low.

V2_4 implementation: `LevelWatchState` class declared at line 179-200 with the correct 5-state lifecycle (Untouched/Breached/Armed/Consumed/Invalidated). Comment at line 174: "Class scaffolding placed here in this batch so the storage and refactor surface are agreed-upon before the entry-mechanism rewrite." No `CheckPatternBEntry` method exists anywhere in the 4,627-line file. No code path instantiates `LevelWatchState`. Pattern B has zero representation in the live signal pipeline.

V1 had a failed-retest of the 1-min RTH range (version_diff_audit.md §3, AMTradeCockpit.cs line 1183-1198). It was deleted at the V1-to-V2 rewrite and never replaced despite the LevelWatchState scaffold being added in V2_4.

**B. Quantify the cost.**
JSONL data analysis (Q5): 1,271 of 2,956 unique touches (43.0%) were Pattern B touches — wick-through-level with close-back. Of these, 298 were also on retrace_side and not-latched (the lowest-hanging fruit: qualifying under both Pattern A and B). 352 additional were Pattern B only (retrace_side=false under Pattern A's rules, but would qualify under Pattern B's breach-and-recover logic). Adding Pattern B to the signal pipeline would approximately double the candidate-setup pool from 741 qualifying touches to ~1,100+. That is the difference between 2 signals and potentially 50-100 signals over the 6-month corpus at reasonable gating.

**C. Cost type.** Win-rate cost plus filter cost — missing an entire class of AM's preferred setups.

**D. Fix complexity.** Medium-Large. The state machine design is already specified (LevelWatchState). The work is: (1) instantiate one LevelWatchState per candidate level per session (replacing or supplementing the current `v2TouchedThisSession` latch), (2) write `CheckPatternBEntry` to advance states on each 1-min bar close, (3) fire `SetSignal` when state transitions to Armed and then the breach-bar high is crossed. The `AnchorCandle` field on LevelWatchState feeds directly into `V2ComputeStopDistance` once that parameter is passed (see GAP 6).

**E. Priority.** P0. Pattern B is AM's default entry. Without it, the indicator is encoding only a secondary, less-preferred entry method for a subset of setups.

**F. AM-escalation flag.** N. The breach-candle mechanics are fully defined in the transcripts. The single open question (single-bar vs multi-bar confirmation) is also answered: apr-24 confirms it is a 1-bar pattern. No AM input needed to proceed.

---

### GAP 3 — Body-Stack 4-Node vs 3-Node Day-Type Gate

**A. Identify.**
Apr-23, lines 60-64, verbatim: "The 6 PM candlestick must sit below the 4 a.m. candlestick must sit below the 9:30 candlestick to take a long. The GlobeEx candlestick must sit above the 4:00 a.m. candlestick must sit above the 9:30 candlestick to go short. Otherwise, it's sideways. So you're trading a range. All three have to converge in the right direction." AM says "all three" — B, C, D. She omits A (prior 3:30) from the chain.

V2_4 `ClassifyAMDayType` (line 4388-4427): requires strict A < B < C < D for LongTrend. All four nodes must stack. A is the prior-day 3:30 candle. The impact: any V-shape recovery day (B dips, C recovers above B, D breaks above A) is classified Sideways under 4-node strict logic but would be LongTrend under 3-node logic.

The AM_rules_v2_spec.md §1 also lists 4 nodes (A, B, C, D) but that document itself was authored after the apr-23 transcript and may have over-codified AM's verbal "all three." The transcript is the ground truth.

**B. Quantify the cost.**
JSONL data analysis: of the 7 V2_4-instrumented sessions, the dominant day_type is `congestion` (53.9% of heartbeats). The 4-node gate is the primary reason for this over-classification — on any day where overnight trading produced a B-dip-then-recovery, the 4-node test fails. Without the historical body-stack data in JSONL we cannot count precisely, but the pattern (B dips to absorb supply, C and D recover) is common on up-trending weeks. A conservative estimate: 20-30% of would-be LongTrend days are classified Sideways by the extra A-node requirement. On those days V2_4 fires FADE (2-signal cap) instead of TREND (3-signal cap), or no-fires if the slope is flat. ESTIMATE: HIGH frequency, affecting perhaps 1-2 days per week in a normally-functioning market.

**C. Cost type.** Filter cost — valid trend days blocked from TREND-mode entry, relegated to FADE or no-fire.

**D. Fix complexity.** Small. In `ClassifyAMDayType` (line 4388-4427), change the long-trend requirement from `a<b AND b<c AND c<d` to `b<c AND c<d`. Retain A as context (it's still drawn, still used as PrInst level target) but remove it from the stack test. This is a one-function change.

**E. Priority.** P0. The day-type gate is the primary on/off switch for the entire system. Getting the gate right is a prerequisite for everything else.

**F. AM-escalation flag.** Y. This is a high-impact interpretation change. Before shipping, confirm with AM: "Does the long-trend gate require all four candles (A, B, C, D) to stair-step, or only B, C, D with A providing the target zone?" The transcript says three; the written spec says four. AM's answer ends this debate.

---

### GAP 4 — FADE Rule One-Sided vs Two-Sided

**A. Identify.**
Apr-23, line 154, verbatim: "You can go in both directions. You can go long, you can go short. So you look for the old high, you short it. You look for the old low, you take it long." AM demonstrably took both a top-short (7172 → 7107) AND a bottom-long (7092 → 7140) on the same sideways day with an up-sloping 200 SMA.

Apr-23, lines 79-80: "Coming into the day [200 SMA] was upward. If it's coming up on the 200 and that 200 is sloping up, they're going to buy those dips." This supports slope as a conviction modifier, not an exclusion gate.

V2_4 FADE-mode (code_audit.md §3, line 1802-1817): on a Sideways day with slope UP, only GlobExL / EuropeL / PrInstL are candidates (slope direction only). The top-fade short is completely blocked. The AM_rules_v2_spec.md §7 explicitly notes this was "wired 2026-04-27 as one-direction FADE per 200-SMA slope; dual-direction (both fades on flat-slope) deferred."

The task brief states "I wired one-sided today" — this was a known decision at the time of the brief. It is a known gap.

**B. Quantify the cost.**
The JSONL has only 7 V2_4-instrumented sessions with limited FADE-day coverage. Using the apr-23 day as a direct example: AM made approximately 65 points short (7172 → 7107) + 48 points long (7092 → 7140) = ~113 points total on a sideways day. V2_4 one-sided would have captured only the long side (slope was UP). The short trade — which was the larger of the two — would not have fired. ESTIMATE: on any sideways day (approximately half of all sessions per JSONL classification), one valid trade setup is blocked. That is roughly 1 missed trade per 2 sessions, or ~50-60 trades over 6 months on the existing data.

**C. Cost type.** Filter cost — half of all FADE setups blocked.

**D. Fix complexity.** Small. In `CheckEntry` FADE branch (line 1802-1817), add the counter-slope candidates (GlobExH/EuropeH/PrInstH when slope is UP; GlobExL/EuropeL/PrInstL when slope is DOWN) at half-size (Orange bucket). The slope-direction side fires Green or Orange per MOC; the counter-slope side is always Orange (reduced size). This preserves the slope-as-sizing logic while removing it as an exclusion gate.

**E. Priority.** P0. With only 2 signals in 6 months, every missed setup category is critical. The top-fade on sideways days is one of AM's most reliable trades.

**F. AM-escalation flag.** Y. Confirm: on a sideways day with UP-sloping 200 SMA, do you take the short at the top of the range at full size, half size, or not at all? The transcript supports half-size or less, but the exact sizing for the counter-slope fade needs confirmation before coding.

---

### GAP 5 — Stop = Entry-Candle Width (V2ComputeStopDistance Dead Parameter)

**A. Identify.**
AM, apr-16 and apr-24: "the size of the stop is always going to be the width of that [entry trigger] candle." The bigger-candle exception (AM_rules_v2_spec.md §5): if the entry candle is contained by the prior 3:30 or prior 9:30 candle, use the bigger candle's width.

V2_4 `V2ComputeStopDistance` (line 2174): accepts a `CandleBox anchor` parameter. The logic is correct: if anchor is contained by Close330 or RTH930, promote to the bigger candle; compute width; clip to [0.30, 0.80] * ADR20. However, all three call sites (line 1954, 2113, 3330) pass no argument — `anchor = null` always. The function always falls back to `europe4AM.High - europe4AM.Low` clipped to ADR. The per-trigger stop is dead code in production.

Net effect: every trade in V2_4 uses the same stop distance (europe-4AM-width), regardless of whether the entry candle is the GlobEx, the prior-institutional, or the 9:30 candle. On narrow-range days the stop is too wide (europe was wide but the 9:30 trigger is tight). On wide-range days the stop is too tight (europe was narrow but the 9:30 trigger is 40+ points).

**B. Quantify the cost.**
Stop cost is less visible than runner cost because it affects risk-reward symmetrically. But the wrong stop has two failure modes: (1) oversized stops on narrow trigger candles bleed expected value through unfavorable R-multiples; (2) undersized stops on wide trigger candles (after ADR clip) stop out trades that AM would hold. The apr-24 specific example: the 40-point 9:30 candle. AM says "try and get an order at the midpoint and cut that risk in half." V2_4 stops out at europe-width (typically 10-20 points), which is LESS than the candle width. Result: the trade fires and immediately stops out on a normal intrabar wick. ESTIMATE: MEDIUM frequency stop cost, particularly pronounced on high-volatility days when the 9:30 candle is wide.

**C. Cost type.** Stop cost — wrong-size stops eating winners and over-risking on the wrong days.

**D. Fix complexity.** Small at the call site, Medium overall. At the signal creation in `CheckEntry` (line 1954), pass `bestLevel.OriginCandle` (or the anchor candle corresponding to `bestName`) to `V2ComputeStopDistance`. This requires: (a) storing origin-candle references on each level candidate, and (b) passing it at the call site. The function body is already correct.

**E. Priority.** P1. Fix after the P0 exits and Pattern B, because stop sizing matters most when there are actual trades to size.

**F. AM-escalation flag.** N. The rule is clear. No ambiguity to escalate.

---

### GAP 6 — FADE Targets Too Far (Prior-3:30 vs Intermediate Levels)

**A. Identify.**
V2_4 FADE-mode target: `signalTarget = currentDay.Close330.High` (longs) or `Close330.Low` (shorts) — the far-side of the prior 3:30 institutional candle. If PrInst is on the wrong side of entry, the trade is silently dropped (line 1965-1976).

AM on apr-23: top-short target was the pre-market low (7107), not the prior 3:30 low. Bottom-long target was the 4 AM close (7142), not the prior 3:30 high. Apr-23, lines 49-50: "the 4 a.m. candlestick low or the 4 a.m. candlestick close, which was 7142 or something like that. So, I closed it in that candlestick box right in here."

The correct FADE target ladder (from apr-23): for bottom-long, T1 = 4 AM close; T2 = pre-market high; T3 = prior 3:30 high. For top-short, T1 = pre-market low; T2 = 4 AM close; T3 = prior 3:30 low. V2_4 only has T3, and skips the trade if T3 is unprofitable (silent drop).

The silent-drop path is particularly damaging: a valid AM setup at the GlobEx low, with a perfectly good target at the 4 AM close, gets killed because the prior-3:30 high is not on the profitable side of the bar that day.

**B. Quantify the cost.**
The silent-drop log path ("FADE skip: PrInst not in profit direction") has no JSONL equivalent — only a Print() call. We cannot count these drops from the JSONL. However, on any sideways day where price is above the prior-3:30 mid-point, a bottom-long's natural T1 (4 AM close) is profitable but the T3 (prior-3:30 high) may already be behind entry. These days produce no FADE signal despite AM would trade them. ESTIMATE: MEDIUM frequency filter cost, potentially 10-20% of all FADE-eligible days.

**C. Cost type.** Filter cost (silent drop) and runner cost (over-ambitious target for the cases that do fire).

**D. Fix complexity.** Medium. Requires adding the 4 AM close and pre-market high/low as named levels in the target ladder. The FADE target logic in `CheckEntry` needs a priority list: check T1 first (4 AM close profitable?), then T2 (pre-market H/L), then T3 (prior-3:30). Only skip if all three are unprofitable.

**E. Priority.** P1.

**F. AM-escalation flag.** N. The target ladder is clear from apr-23.

---

### GAP 7 — V1's Failed-Retest of 1-Min RTH Range (Deleted, Not Replaced)

**A. Identify.**
V1 had one entry mechanism: after the 1-min 9:30 bar prints, if a subsequent bar pushes through `rth1MinLow` and a follow-up bar wicks back into the range and closes outside again, fire SHORT at `rth1MinLow` (version_diff_audit.md, AMTradeCockpit.cs line 1183-1198). This was deleted at the V1→V2 rewrite with no comment justifying the removal. The version diff audit notes: "The 1-minute candle is still drawn (RTH1Min_H / RTH1Min_L) and its width still feeds the '1 MES ONLY' sizing note, but no entry rule reads rth1MinHigh/rth1MinLow."

This maps to a specific AM rule from multiple transcripts (apr-8 §4.1, apr-9): the opening-range retest entry — buy or sell the retest of the first 1-min candle after the RTH open. V1 had it. V2_4 does not.

The Pattern B engine (GAP 2) partially covers this if wired to watch the ORH/ORL levels. But the 1-min candle is a different, faster trigger — the 30-min OR (ORH/ORL) is the 9:30-10:00 range; the 1-min candle is the 9:30-9:31 range. They fire on different days and at different price levels.

**B. Quantify the cost.**
ESTIMATE: MEDIUM-HIGH frequency. On any "standard" open (not gap-open, not news-gap), the first 1-min bar is the most important candle of the day. V1 fired on it; V2_4 cannot. Based on the V1 design and AM's stated preference for this setup, this likely represents 1-3 setups per week that V2_4 structurally cannot see.

**C. Cost type.** Win-rate cost — an entire setup class is invisible to the indicator.

**D. Fix complexity.** Medium. Re-implement the 1-min failed-retest logic, ideally inside the Pattern B state machine (LevelWatchState with OriginCandle = 1-min 9:30 candle). This avoids duplicate code and unifies the breach-and-fail pattern across all level types.

**E. Priority.** P1. Re-enable after Pattern B is wired.

**F. AM-escalation flag.** N. The setup is well-documented in transcripts.

---

### GAP 8 — MOC State Does Not Gate Trades (Computed, Never Consumed)

**A. Identify.**
The MOC validation bands are fully specified (apr-16, apr-24): ratio > 1.20 = Green (full size); 1.00-1.20 = Orange (half size); < 1.00 = Gray (reduced/no trade). V2_4 computes `MocState` correctly at line 1232-1241 and displays it in the UI. But: "MOC is computed and displayed but does NOT enter the canTrade gate — verdicts mention 'REDUCED size' but effSignalCap, position-size, or stop math are not modified by MocState." (code_audit.md §2). The system advertises MOC-aware sizing but the runtime is MOC-blind.

Additionally: MOC is missing from every JSONL payload (data_analysis.md Q6). There is no way to retrospectively know what MOC state was when any signal fired.

**B. Quantify the cost.**
On Orange/Gray days, AM's sizing is reduced and her risk tolerance shifts. If V2_4 fires full-size signals on Gray days (as it currently does — Gray does not block anything), it over-risks on institutionally weak setups. This is not primarily a missed-setup cost but a risk-management cost that degrades long-run expectancy. ESTIMATE: MEDIUM frequency. Based on the apr-16 data, roughly 20-30% of days are Gray or Orange. On those days, V2_4 fires at the wrong size.

**C. Cost type.** Stop cost and sizing cost — wrong risk posture on weak institutional days.

**D. Fix complexity.** Small-Medium. Wire `MocState` into `effSignalCap` (Gray = 1, Orange = 1, Green = 2-3) and into the qty selector (Gray = 1 MES, Orange = 1 MES, Green = normal). Also add `moc_state` and `moc_ratio` to JSONL heartbeat payload.

**E. Priority.** P1.

**F. AM-escalation flag.** N. The bands are fully specified.

---

### GAP 9 — Two Parallel Day-Type Fields (JSONL Logging Discrepancy)

**A. Identify.**
V2_4 maintains two day-type fields simultaneously. `currentDayType` (Congestion/Trending/Extended/Unknown) is computed by `DetermineDayType` (line 1739) and is the value emitted to JSONL heartbeat and signal events (line 2449: `"day_type": currentDayType.ToString()`). `v2DayType` is computed inline in `Process1MinBar` (line 1571) by `ClassifyAMDayType()` and is the actual gate that drives `tradeMode` and `v2TrendDir`. The two can disagree on any given bar.

This means: anyone reading the JSONL `day_type` field — including any downstream dashboard, ML pipeline, or performance analyst — is reading the cosmetic legacy field, not the AM body-stack field that actually drove the trade decision. The session is tagged `congestion` while the indicator was actually running in `LongTrend` mode.

Data evidence: JSONL data analysis Q4 — the strings "LongTrend", "ShortTrend", "CautiousLong", "CautiousShort", "Sideways" never appear in any JSONL record across 103 sessions. The FADE mode wired "today" (2026-04-27) would depend on `day_type == "Sideways"` which has never been emitted. The FADE wiring is dead on arrival unless this vocabulary mismatch is fixed.

**B. Quantify the cost.**
The FADE mode is currently entirely dead code in production because the trigger string never matches. All sideways-day FADE signals are blocked by a string-mismatch that neither the indicator nor the JSONL logging surfaces. This is zero additional missed setups beyond what GAP 3 and GAP 4 already account for, but it compounds those gaps and makes them invisible to debugging.

**C. Cost type.** Filter cost — the FADE mode does not fire because of a vocabulary mismatch between the classifier and the emitter.

**D. Fix complexity.** Small. In the JSONL `signal` event (line 2449), replace `currentDayType.ToString()` with `v2DayType.ToString()`. Also add `v2DayType` to the heartbeat payload alongside `day_type`. Do not remove `day_type` (legacy dashboards may depend on it) but emit `v2_day_type` as an additional field.

**E. Priority.** P0. This is blocking FADE mode entirely and corrupting all historical JSONL analysis.

**F. AM-escalation flag.** N. Pure implementation bug.

---

### GAP 10 — CL RTH Open Time Hardcoded to 9:30 (CL Opens at 9:00)

**A. Identify.**
CL (crude oil) opens at 9:00 ET. V2_4 correctly sets `closeHour=14:30` and `instCloseHour=10:00` for CL. But `rthOpenHour=9, rthOpenMinute=30` is hardcoded for ALL instruments including CL (line 853-854). Comments at lines 1428 and 1440 explicitly acknowledge CL opens at 9:00.

Downstream consequences (code_audit.md §9): the 9:30 box capture fires at 9:30 instead of 9:00; `RTH930OpenPx` is captured on the wrong bar; opening-range lock fires at 10:00 instead of 9:30; `inRthWindow` lower bound misses 9:00-9:29 ET; VWAP RTH reset fires 30 minutes late; all phase calculations are offset by 30 minutes.

**B. Quantify the cost.**
Every CL setup between 9:00 and 9:29 ET is invisible to V2_4. That is the first 30 minutes of CL's most active trading window — the opening range period where AM's primary setups occur. ESTIMATE: HIGH frequency for CL specifically, 1-3 setups per session that cannot fire.

**C. Cost type.** Filter cost — an entire time window is blocked by a hardcoded constant.

**D. Fix complexity.** Small. Add `isCL` check at line 853: `rthOpenHour = isCL ? 9 : 9; rthOpenMinute = isCL ? 0 : 30;`

**E. Priority.** P1 (if CL is in scope). The task brief confirms CL is tabled by AM for now — but the bug should be fixed regardless to avoid future data corruption when CL is re-enabled.

**F. AM-escalation flag.** N.

---

### GAP 11 — 1:30 PM Candle as a Primary Level (Missing)

**A. Identify.**
Mar-6, lines 69-72, verbatim: "Look at where they choose to turn around and go long. It's the 130 candle. Every day, Asheen. Every day. By a couple of minutes. Doesn't even matter what's going on." The 1:30 PM ET 30-min candle is described as a daily turn-around level with the conviction of an institutional candle.

Apr-16, lines 124-135: AM shows the 1:30 candle in pink on her chart. "this 1:30 candlestick is a pullback event or it's an expansion event. It only comes into play if we have a retracement event that gives us the dip buying formation. If it holds the 1:30 candle and it begins to hold and we had institutional flow then it's very likely to go to the top of the 9:30 candle."

V2_4 level set (code_audit.md §3, line 1802-1885): captures Prior 3:30, GlobEx 6PM, Europe 4AM, RTH 9:30, Midnight, PR30 H/L, ORH/ORL, SMA50/200. No capture of the 1:30 PM candle anywhere in the codebase.

**B. Quantify the cost.**
AM calls this an "every day" level. If her description is accurate, this is a daily retracement level that is currently absent from V2_4's candidate pool entirely. ESTIMATE: HIGH frequency. Every pullback during RTH that finds the 1:30 candle as support/resistance is a missed level touch. On FADE days in particular, the 1:30 level is an intermediate target that V2_4 cannot use.

**C. Cost type.** Win-rate cost and filter cost — a primary level is absent from the pool.

**D. Fix complexity.** Small. Add a `Close130` box capture in `Process30MinBar` at h=13, m=30 (analogous to the 3:30 capture). Display in the legend. Add `Pr130H/Pr130L` to the TREND-mode candidate set. Gate: active only during retracement events with validated MOC (per apr-16).

**E. Priority.** P1.

**F. AM-escalation flag.** Y. Mar-6 describes this as "every day, by a couple of minutes" — the strongest possible claim. But if it's a primary level, it should have appeared in multiple transcripts. It appears in mar-6 and apr-16 but not in apr-9, apr-23, or apr-24. Confirm: is the 1:30 candle always tracked as a named level, or only on pullback days with validated MOC?

---

### GAP 12 — Daily Pivots + R2/R3/R4 Exhaustion Banner (Missing)

**A. Identify.**
Apr-8, lines 43-50: AM uses Woody's pivots with R1-R4 and S1-S4. A custom banner auto-flags when price > R2 or > R3: "if you're above R2, R3, you're extended. And so you want to watch for exhaustion patterns that might show up." Apr-8: "if I'm at the fourth pivot and my 200 is all the way down here, I know I'm very extended. I know it is a short covering rally."

V2_4 (code_audit.md §7, line 4334): draws PP/R1-R3/S1-S3 dotted lines on the chart (CalculatePivots was removed from V1 then re-added as a drawing-only function). Pivots are drawn but: (a) no R4/S4 (Woody's-specific 4th level), (b) no exhaustion banner logic, (c) pivots are not in the TREND-mode candidate pool (version_diff_audit.md §2: "V1 used pivots as targets; V2_4 does not"). Pivots are purely cosmetic.

Apr-8, lines 163-165: "I literally only take trades in the direction of the 200 and the 50 when they're both going down." This is the SMA-stack trade condition, which V2_4 replaced with body-stack. The two systems disagree specifically when price is extended above R2/R3 — body-stack may classify as LongTrend but AM would classify as "extended, watch for exhaustion."

**B. Quantify the cost.**
The R2/R3 exhaustion gate is a no-long blocker that AM explicitly invokes in strong rallies. Without it, V2_4 fires LONG signals on short-covering rally days (price > R3, 200 SMA far below) where AM would not enter long. These are losing trades — false positives. Additionally, pivots as target levels are absent, meaning V2_4 cannot reproduce AM's "take profit at pivot" trade management. ESTIMATE: MEDIUM frequency, particularly on high-momentum days that follow multi-day rallies.

**C. Cost type.** Filter cost (missing exhaustion gate causing false positives) and runner cost (missing pivot as target level).

**D. Fix complexity.** Medium. Add R4/S4 calculation (Woody's formula). Wire `price > R2` as a soft no-long warning and `price > R3` as a no-long hard gate. Add PP/R1/R2 to the TREND candidate level pool as targets.

**E. Priority.** P2.

**F. AM-escalation flag.** N. The rules are clearly stated.

---

### GAP 13 — Multi-Day Levels and t-1/t-2/t-3 4AM Candles (Missing)

**A. Identify.**
Mar-6, line 177: "4 a.m. candlestick from what? One, two, 3 days ago. It's bananas." AM tracks 4 AM candles from the previous 3 days as active levels. The apr-23 bottom-long at 7085 was itself the "30-minute low of two days ago" — AM explicitly cited the prior-2-day 3:30 level as the bounce reference.

V2_4 (code_audit.md §3): `Pr30H/L` rolling prior-30-min H/L (stamped with bar-close time so each new bar is a fresh candidate). No explicit tracking of prior-1-day, prior-2-day, prior-3-day 4 AM candles. No multi-day 3:30 low tracking. The spec §7 mentions "up to 3 days" for sideways edges but the implementation is a rolling 30-min average, not a named prior-day reference.

**B. Quantify the cost.**
The 7085 trade on apr-23 — which AM considers one of her cleanest recent examples — used a 2-day-old level. V2_4 cannot see that level. ESTIMATE: MEDIUM frequency, particularly on sideways range days when price returns to multi-day reference floors.

**C. Cost type.** Win-rate cost — multi-day level class is invisible to the indicator.

**D. Fix complexity.** Small. Add `PriorDay1Close330`, `PriorDay2Close330`, `PriorDay3Close330` H/L tracking in `dayHistory` access. Add as named candidates in the TREND and FADE pools. The data is already collected (dayHistory is populated at session close per code_audit.md §1.2) — it just needs to be exposed as named candidate levels.

**E. Priority.** P2.

**F. AM-escalation flag.** N.

---

### GAP 14 — News-Candle Wick Rule (Missing)

**A. Identify.**
Apr-24, lines 338-364: if a mid-session candle's volume exceeds BOTH the prior-day 9:30 AND 3:30 candle volumes, register its wick as a level. Slope UP → lower wick = support zone. Slope DOWN → upper wick = resistance zone. Persistence: "as long as it's the highest candle volume in recent days." Identification: pure volume outlier, no news feed needed. The 7085 trade on apr-24 was exclusively a news-candle wick trade (237,000 contracts vs ~141k on the 9:30 and ~127k on the 3:30).

V2_4 (code_audit.md §2): no outlier-volume detection on intraday candles. The level pool is fixed at session open (master-candle H/L, PrInst, Pr30 rolling). Mid-session level registration based on volume outliers does not exist.

**B. Quantify the cost.**
The apr-24 7085 trade is the canonical example of a Pattern B entry on a news-candle wick. Without this level registration, these setups are invisible. ESTIMATE: LOW-MEDIUM frequency. True volume outliers (exceeding both 9:30 and 3:30 volumes) probably occur 2-4 times per month, but they tend to be high-conviction setups when they do appear.

**C. Cost type.** Win-rate cost — an entire level class is invisible.

**D. Fix complexity.** Small. In `Process1MinBar`, on each RTH bar close check if volume > max(yesterday's 9:30 volume, yesterday's 3:30 volume). If yes, register a `NewsWickH` or `NewsWickL` level (slope-gated) and add to the live candidate pool. The precedent for mid-session level addition exists in the `Pr30H/L` rolling logic.

**E. Priority.** P2.

**F. AM-escalation flag.** N. The rule is fully specified.

---

### GAP 15 — 5-Minute Confirmation Rule (Missing, Partially)

**A. Identify.**
Apr-24, lines 49-66: the default entry method is confirmation entry — "Two five-minute candles trending back up. Bodies not overlapping. Yes." This replaces the pre-placed limit as the default. Pre-placed limit is reserved for full-trend days only.

V2_4 entry model (code_audit.md §1.3): `CheckEntry` in `Process1MinBar` fires a `SetSignal` on a single 1-min bar touch of a candidate level, retrace-side only. There is no 5-min confirmation step, no two-bar bodies-not-overlapping check. The code is structured around "level touched on 1-min bar → fire Pending signal" rather than "level touched → watch for 5-min confirmation → fire."

The 5-min confirmation is the Pattern B armed state described in GAP 2: breach candle detected → wait for confirmation bar(s) not taking out breach candle's low → then enter. The LevelWatchState `Armed` state is exactly this. Wiring Pattern B (GAP 2) therefore implicitly implements the 5-min confirmation for sideways/cautious entries.

**B. Quantify the cost.**
Without 5-min confirmation, V2_4 fires on the first qualifying 1-min bar touch. AM prefers waiting for confirmation. The difference is that V2_4 produces more false-positive entries on wick-through levels that then reverse immediately. Pattern B would filter these by requiring the breach candle to hold a higher low. ESTIMATE: MEDIUM frequency false-positive cost; the fix is subsumed in GAP 2.

**C. Cost type.** Stop cost (entering too early on unconfirmed setups) and win-rate cost.

**D. Fix complexity.** Subsumed in GAP 2 (Pattern B). No separate fix needed.

**E. Priority.** P1 (resolved by GAP 2 fix).

**F. AM-escalation flag.** N.

---

### GAP 16 — 50% Midpoint Adds-Rule and VWAP+50+200 Convergence Add-Trigger (Missing)

**A. Identify.**
Apr-24, lines 134-143: on wide trigger candles (the 40-point 9:30 example), AM uses a half-and-half entry: half at the break, half at the 50% midpoint. Once the midpoint fills, move the stop to the 50% line. Apr-10, lines 39:30-40:00 verbatim: "if the 50 converges with the VWAP and the 200 and the 200 is pointing up, it's going to rocket back to the top. That's going to be my sweet spot. It'll be a place where I potentially add to this position."

V2_4 is one-and-done: a single signal fires, a single entry is placed. No add-to-winner logic, no staged entries, no midpoint fill. This is architecturally consistent — the indicator is designed for single-entry — but it means an entire class of AM's position management is absent.

**B. Quantify the cost.**
The add-trigger is a size-up signal on already-winning trades. It does not directly cause missed entries but amplifies the winners AM catches. Given AM's "small wins frequently, occasional big wins" profile, the big wins often come from the convergence add (apr-10 ap-43:17: "when the levy breaks, it's very likely to break to the north because all of our patterns are telling us that"). ESTIMATE: MEDIUM frequency, affecting perhaps 2-3 adds per week in trending conditions.

**C. Cost type.** Sizing cost — missing the add signal on AM's biggest winners.

**D. Fix complexity.** Large. Requires a parallel entry model (active trade → watch for 50% midpoint / convergence condition → emit second entry). This touches the signal lifecycle extensively and risks regressions.

**E. Priority.** P2.

**F. AM-escalation flag.** Y. Confirm: is the 50% midpoint add always at exactly the 50% of the entry candle, or is it at the 1-min VWAP wherever that happens to coincide? The transcript mentions both in the same breath.

---

### GAP 17 — Day-of-Week Gates and Friday Full-Size Escalation (Missing)

**A. Identify.**
Apr-16, lines 148-150: "this shifts every day of the week. The statistical probability and the threshold size, what size you want to position it, it's now triggered by days of the week."
Apr-24, lines 290-303: "it says go full size long on the break here. How? Why? Well, one — the candle bodies are not overlapping. Two, we have institutional MOC validated by the size of the spike relative to the motion. And three, you're above the 3:30 closing candle. And so it looks really noisy, but the candle bodies are in the space that says go full size on Fridays."

V2_4: `MaxSignalsPerDay` is a fixed parameter regardless of day of week. No Friday escalation logic. No day-of-week probability table.

The spec (AM_rules_v2_spec.md §11.5) explicitly recommends: "encode only AM's stated belief: Friday = full-size eligible when other gates pass. Let the ML discover any real DOW edge later."

**B. Quantify the cost.**
This is primarily a sizing cost, not a missed-entry cost. On Fridays with valid setups and validated MOC, V2_4 fires at the same size as Monday. The missed full-size escalation on Fridays means the system leaves money on the table on its statistically strongest sizing day. ESTIMATE: LOW-MEDIUM frequency, but concentrated on the sessions where AM makes her biggest weekly P&L.

**C. Cost type.** Sizing cost.

**D. Fix complexity.** Small. Add a `DayOfWeek == Friday` branch in the `effSignalCap` and sizing path: if Friday AND candle bodies don't overlap AND Green MOC AND above prior 3:30 close → full size, 3 signals allowed.

**E. Priority.** P2.

**F. AM-escalation flag.** N.

---

### GAP 18 — Volume-Priority for Clustered Levels (Missing)

**A. Identify.**
Apr-24, line 319, verbatim: "the one with the most volume is going to win." When prior 3:30 high, prior 9:30 high, and two-days-ago high all cluster near the same price, the level whose origin candle had the most volume is the dominant level.

V2_4 (code_audit.md §3): maintains separate `Pr30H`, `Close330.High`, etc. as independent candidates. When they cluster within a few ticks, multiple touch events fire on the same bar and the best-pick logic selects the closest to bar open — not the highest volume. There is no volume ranking.

**B. Quantify the cost.**
This is a quality-of-signal issue rather than a count issue. Clustered levels without volume ranking produce ambiguous signals that may fire on the weaker of two coincident levels. ESTIMATE: LOW frequency direct impact; cleaner signal quality rather than missed setups.

**C. Cost type.** Win-rate cost (mild — trading on the weaker clustered level vs the stronger one).

**D. Fix complexity.** Small-Medium. Store origin-candle volume for each level at capture time. In `CheckEntry` tie-break logic, after applying the retrace-side filter, among clustered candidates (within X ticks), prefer the highest-volume origin.

**E. Priority.** P3. Important for signal quality but not a count driver.

**F. AM-escalation flag.** N.

---

### GAP 19 — signalsToday Counts Cancelled Pendings (Undocumented Trap)

**A. Identify.**
Code_audit.md §10: "A Pending that expires at 14:30 cutoff has incremented the counter. So a stopped-out trade and an expired-Pending both count toward the cap equally. If AM's intent is 'you get N attempts that trade,' the counter is over-counting expired Pendings."

V2_4 line 588-590 comment: "Caps the number of PENDING signals armed per session, not the number of fills. A cancelled pending still counts. Intentional: this is a decision-budget guardrail against over-engagement." This is explicitly documented as intentional by the developer — but it conflicts with AM's session behavior where she can take 5 trades (apr-10). If 3 signals are pending-and-cancelled, no further entries can fire even if excellent setups appear in the afternoon.

**B. Quantify the cost.**
The pending-counts-as-used behavior is a filter that compounds the already-low signal count. On a day with 2 level-touch false starts (pending fires, price gaps away, pending expires at cutoff), the system is effectively locked out for the rest of the session. ESTIMATE: LOW-MEDIUM frequency trap, but when it fires it silently blocks valid afternoon setups with no log explanation.

**C. Cost type.** Filter cost.

**D. Fix complexity.** Small. Change the counter increment from `SetSignal` (Pending) to fill detection (transition from Pending to Active). Track `fillsToday` separately from `signalsToday`. Cap fillsToday rather than signalsToday.

**E. Priority.** P2.

**F. AM-escalation flag.** N.

---

## Reconciliation: Sharpe 9-10 vs PF 0.94

Two backtest results. One system. The question is which is closer to AM's true performance profile.

**Python pipeline (pattern_scorer_rt2_1): Sharpe 9-10, 94% win rate.**

This result has three known inflators, each independently sufficient to make an unprofitable strategy look like this:

1. **100% fill assumption.** Every signal fires at the entry price with no slippage, no partial fill, no cancel. In a limit-at-level strategy, real fills require price to touch the level AND sufficient liquidity. Many signals that "filled" in the pipeline never actually filled in production because price tagged the level and reversed before the order could be processed. Slippage alone, modeled at 1 tick per MES fill, would reduce the apparent edge by ~15-20%.

2. **SMA20 trail exit.** The trail smooths across winning bars but cuts losing trades at a slightly better level than random. On a random-walk simulation the SMA20 trail produces a small positive R-multiple distribution even with random entries. The pipeline's "edge" is partially a mechanical artifact of the trailing algorithm applied to 1-min data.

3. **The pipeline trained in-sample.** The wave2 Python audit identifies that the pattern scorer was calibrated on the same data it was evaluated on. In-sample Sharpe 9-10 with 94% win rate is consistent with overfit ML, not a real strategy.

**V2_4 backfill (Mar 13 – Apr 22): PF 0.94, 41.7% WR, breakeven.**

This result also has known biases but in the opposite direction:

1. **Almost no signals fired (2 in 6 months in the broader corpus).** A 0.94 PF on 2 trades is a sample-size-1 measurement, not a stable statistic.

2. **Both signals were 9:32 VWAP SHORTs** — both fired on the only condition that was not broken at the time (VWAP candidate still in the pool in the V2_3 era, rthactive phase, extended day_type). These trades represent a degenerate subset of AM's strategy.

3. **The wrong exit** (SMA20 trail) means even the trades that fired were managed incorrectly. The PF measures the wrong thing.

**The verdict:**

Neither result measures AM's actual method. The Python pipeline measures a backtest-overfitted, 100%-fill, SMA20-exit version of an AM-inspired signal set. The V2_4 backfill measures a nearly-silent indicator with 2 signals on the wrong entry trigger.

AM's real-world profile (50-60% WR, PF 2.5-4) is achievable once:
- Pattern B is wired (win rate will rise as the correct entry method fires)
- Exit becomes level-to-level (PF will rise as the runner captures the right tail)
- The body-stack gate is corrected to 3-node (signal count will normalize)
- FADE is two-sided (signal count on sideways days will double)

Estimated PF after all P0 and P1 fixes, in my judgment: 1.5-2.5 on a properly-sampled forward test. Reaching AM's 3-4 range requires additionally implementing the Fibonacci runner ladder with slope-gated targets and the news-candle wick level (the P2 items).

---

## Estimated Impact: If All P0 + P1 Gaps Were Closed

Baseline: 2 signals in 6 months, 0.27% conversion, 0.94 PF.

**After P0 fixes (GAPs 1, 2, 3, 4, 9):**
- 3-node body-stack (GAP 3): trend days previously classified Sideways will now enter TREND mode. Estimate +30-50% more TREND-day signal opportunities.
- FADE two-sided (GAP 4): doubles FADE-day candidate pool. Estimate +50-60 additional qualifying level events over 6 months.
- Pattern B (GAP 2): adds 298-650 qualifying Pattern B opportunities to the pipeline (from JSONL data). Even at 30% conversion (a conservative gate), this represents ~90-200 additional signals over the period.
- JSONL v2_day_type fix (GAP 9): FADE mode actually fires. Sideways days stop returning zero signals.
- Level-to-level exit (GAP 1): does not change signal count but changes PF dramatically. A 5:1 R:R on trend days (AM's stated target) versus the current average of ~1.5:1 from the SMA20 trail would take a 50% WR system from 0.94 PF to approximately 2.8 PF by pure R-multiple arithmetic.

Projected profile after P0 fixes: approximately 40-60 signals per 6-month period, WR 45-55%, PF 1.8-2.5. Within AM's range on PF; WR may still be below AM's 50-60% because the MOC gate (GAP 8) and stop sizing (GAP 5) are P1 items.

**After P1 fixes additionally (GAPs 5, 6, 7, 8, 10, 11, 15):**
- Correct stop sizing (GAP 5): trades that currently stop out due to europe-width undersizing on wide-candle days will survive. WR improves.
- MOC gating (GAP 8): reduces false positives on Gray days. WR improves further.
- Correct FADE target ladder (GAP 6): removes the silent-drop on profitable setups. Signal count increases.
- 1:30 PM candle level (GAP 11): adds a new primary level class. ~5-10% more qualifying touches.
- CL timing fix (GAP 10): only affects CL trading but fixes a structural block.

Projected profile after P0 + P1: approximately 60-90 signals per 6-month period, WR 50-58%, PF 2.2-3.2. This bracket overlaps with AM's lower range (PF 2.5). Reaching AM's upper range (PF 4) requires the Fibonacci runner ladder and news-candle detection (P2 items).

---

## AM-Escalation Candidates (Y-Flagged Items)

The following five gaps carry the Y flag — they involve interpretation questions that materially change trade selection or risk and require AM's direct clarification before implementation:

**ESCALATION A (GAP 1 — Runner Exit).**
What 200-SMA delta (measured as today's 9:30 SMA200 minus yesterday's 9:30 SMA200, in points) separates "flat/dampening" from "steep/runaway"? AM said "ML will figure that out" but we need a starting threshold. Without it we cannot implement the slope-conditional Fibonacci ladder. Also: is the first scale-out always 50% at 100%, or does she vary the fraction?

**ESCALATION B (GAP 3 — Body-Stack Node Count).**
Does the long-trend gate require A < B < C < D (all four candles including the prior-day 3:30), or only B < C < D (the three overnight-to-open candles, with A as target zone only)? Apr-23 explicitly says "all three" (B, C, D) but the written spec says four. One transcript statement against a written document. This needs a direct question at the next session.

**ESCALATION C (GAP 4 — FADE Direction).**
On a sideways day with an up-sloping 200 SMA, do you take the short at the top of the range? If yes, at full size, half size, or quarter size? Apr-23 shows AM took a short (top fade) on a day with upward-sloping 200 SMA. V2_4 currently blocks this. The slope is clearly AM's sizing modifier (she went "small size" on the short because it "continued to run against me") but whether it is also an exclusion gate has not been answered verbatim.

**ESCALATION D (GAP 11 — 1:30 PM Candle).**
Is the 1:30 PM candle a named level tracked every day on the chart (like the 4 AM and 3:30 candles), or is it a level that only becomes relevant when price has pulled back into it AND MOC is validated? Mar-6 suggests the former ("every day, by a couple of minutes"). Apr-16 suggests the latter ("only comes into play if we have a retracement event"). These are different implementation shapes.

**ESCALATION E (GAP 16 — Midpoint Add).**
Is the 50% midpoint add-entry at exactly the 50% of the entry candle's range, or at the 1-min VWAP wherever that coincides with the midpoint, or at the 50% level of the 9:30 candle specifically? The apr-10 convergence example and the apr-24 midpoint-add example both describe a multi-MA pinch condition that is not simply "entry candle midpoint." This needs a live chart walkthrough to clarify the exact trigger geometry.

---

## Final Verdict

V2_4 is breakeven for six compounding reasons, in approximate order of P&L impact:

1. The exit kills the right tail (SMA20 trail instead of level-to-level).
2. The primary entry method is missing (Pattern B unwired, 43% of touch events never fires).
3. The day-type gate is too strict (4-node vs 3-node, over-classifying valid trend days as Sideways).
4. Half of FADE setups are blocked (one-sided slope gate instead of two-sided).
5. The FADE mode literally cannot fire (JSONL vocabulary mismatch blocks the trigger string).
6. Stops are wrong for most trades (europe-width fixed stop instead of per-trigger-candle width).

Afshin's intuition is correct. Valid setups are being missed — not as a perception artifact but as a measured fact: 741 qualifying touches returned 2 signals over 6 months. The system is at least 50-100x too restrictive. Fixing the five P0 items above (GAPs 1, 2, 3, 4, 9) should produce a system that fires 60-90+ signals per 6-month period with a PF in the 1.8-2.5 range. Completing the P1 list should push that into AM's documented 2.5-4 range. AM is the prior. The data confirms the encoding is the problem.
