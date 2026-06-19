# Backtest Gap Analysis and Remediation Plan
**Author:** Wave-3 Backtest Gap Analyst
**Date:** 2026-04-27
**Input audits:** backtest_infra_audit.md, python_pipeline_audit.md, jsonl_data_analysis.md, v24_code_audit.md, version_diff_audit.md

---

## TL;DR

The conflict between Sharpe 9–10 and PF 0.94 is not ambiguous once you understand what each number measures. The Python pipeline measured a runner concept applied to every level-touch the model would tier-A-rank, with 100% fill assumed and no mode logic. The V2_4 indicator measured the actual live rule — mode-gated, signal-capped, cooldown-enforced, retrace-filtered — over a single 6-week window. They describe different strategies.

Sharpe 9 is not a credible forward production target. It requires every limit order to fill, it omits the indicator's FADE/TREND gating, it omits the signal cap and cooldown, and its SMA20 trail mechanically compresses volatility on the losing side in a way that overstates Sharpe by 2–4× even under ideal conditions. The spec authors acknowledge all of this in §6.1 of M2v2_runner_system.md and still report the inflated number. That number should not appear in any client-facing document.

PF 0.94 from the V2_4 backfill is a floor, not a ceiling. It reflects a 6-week window with a lockout set at $150/day (effectively one losing trade per day locks the system out), no cooldown in Historical, no daily-loss enforcement in Historical, and a stop rule (europe-4AM-width clipped to ADR) that is a known approximation of AM's per-trigger-candle rule. The indicator is also incomplete: Pattern B is scaffolded but not wired, the stop-distance function has dead-code branches, VWAP was recently removed from the candidate pool, and the CL opening-range window has a confirmed 30-minute timing bug. A system with this many known gaps underperforming AM's long-run track record is exactly what you would expect.

AM's 15-year track record is the prior: Sharpe 2–3, PF 2.5–4, WR 50–60%, with the right-tail coming from runners. Every defensible institutional-grade backtest claim must converge on that range or explain the deviation. A defensible target is AM's profile. Everything else is noise until the fill-rate is measured and the indicator's known bugs are fixed.

The following sections define what it would take to get from the current state to a defensible institutional claim.

---

## 1. The Two Existing Backtest Pipelines — Verdict on Each

### Python Pipeline (pattern_scorer_rt2_1 runner_backtest.py)

**What it does well:**
The Python pipeline has real engineering discipline behind it. The OOS split is clean — events strictly before 2024-01-01 are training data; events from 2024-01-01 onward are the holdout; the validation set (last 10% of training) is used only for early stopping and tier-cut quantile fitting. The walk-forward harness zero-fills Sharpe on no-signal days rather than computing over only trading days, which is a meaningful correction most retail backtests skip. Sub-period stability output exists. Monte Carlo drawdown exists. Slippage and commission overlays exist (1/2/1 ticks, $4.50 RT). The 2026-04-21 rt2_1 geometry-feature retrain specifically addressed the entry-zone vs target-zone confusion AM identified. These are legitimate engineering choices and the pipeline should be preserved as the basis for any forward work.

**What inflates the numbers — precisely:**

1. **100% fill rate.** Every event where `bar_low <= entry_price <= bar_high` is treated as filled at entry plus one tick. In a real market, limit orders at popular Baiynd levels (prior-day high, opening-range high, VWAP boundary) sit in a queue. The "biggest winners" AM describes — breakout through a level with no retest — are the ones where the limit order never fills because price punches through. The fills that do happen skew toward slow meanders into the level, which are statistically the weaker entries. The M2v2 spec itself quantifies this: if live fill rate on Tier-A is 50%, net drops from $775K to $380K and Sharpe from ~10 to ~3–4. That sensitivity analysis is in the spec and the spec still headlines the Sharpe-10 number. The 50% haircut scenario is the number that deserves emphasis.

2. **SMA20 trail mechanically compresses Sharpe.** The runner label uses a 30-min SMA20 ratchet with no first target. When a trade moves in the right direction, the SMA20 catches up and locks in a profit before it can erode. When price reverses immediately, the stop is hit before the SMA20 has moved meaningfully. This produces a distribution with clipped left tail and extended right tail — which looks excellent on Sharpe but does not reflect what a trader sees when waiting for SMA20 to arm (during which time the trade can come back to flat and then stop). The realized R-multiple on a trade where the SMA20 never armed is the same as a one-tick winner under the label convention. AM's actual management is more active than the mechanical trail implies.

3. **No mode logic.** The Python runner pipeline treats every tier-A event identically. V2_4 operates in TREND or FADE mode depending on the day-type classification from the four master candles. FADE days cap signals at 2 and target the prior institutional H/L rather than running the SMA trail. The Python pipeline never simulates a FADE day — it applies the runner policy to all events. This systematically over-trains on a regime the indicator does not execute.

4. **No signal cap, no cooldown, no daily-loss lockout.** The Python pipeline fires every tier-A event in the holdout regardless of how many signals fired that day, regardless of whether a stop occurred 10 minutes earlier, and regardless of whether the daily loss limit was reached. With a 3-signal-per-day cap and a $150/day lockout (as configured in the only captured run), a meaningful fraction of the Python tier-A events would never have been taken.

5. **M2_1 events ≠ V2_4 entries.** The Python event-builder generates "first qualifying touch per (session, level)" from 1-min bars. V2_4's `CheckEntry` uses a retrace-side filter (level must be below bar open for longs, above for shorts), a latch that fires once per level per session (with Pr30 keyed by timestamp), a per-mode candidate pool restriction (FADE has 3 candidates per side vs TREND's ~16), and a FADE-target sanity check that silently drops the trade if PrInst is not in the profit direction. The Python event tape does not replicate any of these. The tier-A signals the Python model would have taken over the Mar–Apr period are not the same signals V2_4 would have fired.

**Verdict on the Python pipeline:** Use it. It is the right foundation for any systematic ML claim. But re-run it with: (a) a realistic fill-rate haircut range (30%, 50%, 70%), (b) a FADE-mode simulation for appropriate days, (c) a signal-cap and cooldown filter, (d) the corrected daily-zero Sharpe calculation already in the pipeline. After those changes, the headline Sharpe will land in the 2–4 range, which is where it belongs.

### V2_4 NT8 Backfill (Mar 13 – Apr 22, 2026)

**What it does well:**
The V2_4 indicator backfill is the only test of the actual live rule. It applies the correct retrace-side filter, the correct latch logic, the correct FADE vs TREND routing (to the extent those are correctly classified), the correct signal cap, and the correct exit logic (SMA20 trail for TREND, PrInst H/L for FADE). The 6-week window is long enough to show regime variation (the Mar–Apr correction into the April low and the subsequent rally to ~7150 are both represented). The per-trade economics are plausible: avg win 19.24 points, avg loss 14.58 points, win/loss ratio 1.32 — not great but not fabricated.

**What makes the backfill unreliable as a definitive measure:**

1. **Daily-loss lockout is absent in Historical.** The lockout only accrues `realizedPnlDollarsToday` in `State.Realtime`. Historical-mode trades are evaluated without accumulating toward the lockout threshold. In the only captured run, the lockout triggered once (Mar 25) at $150 — which is so low that in live trading, a single losing trade on any typical day would trip it. The backfill saw no lockout on any other day despite multiple losing days, because the lockout gate was disabled. If the $150 limit had been enforced historically, many days would have been truncated after the first loss, dramatically changing both the trade count and the equity curve.

2. **Cooldown is absent in Historical.** `lastStopTime` is only set in `State.Realtime` (line 2609). In live operation, a stop triggers a `CooldownMinutes`-length (default 30-minute) block on new entries. The backfill can immediately fire the next signal on the bar after a stop. This is a real fidelity gap — in live trading the system cannot re-engage as quickly as the backfill suggests.

3. **No machine-readable trade export.** The 7,625-line text capture is not a backtester output. It is an NT8 `Print()` stream captured manually by the operator. Every trade requires regex parsing to extract entry, exit, mode, level, and PnL. The cumulative running counter means PnL attribution to specific days requires subtraction of consecutive totals. Line duplication (each print appears twice, likely because the indicator loaded twice on a multi-data-series chart) requires deduplication. This is not reproducible in any automated sense.

4. **Not reproducible across chart reloads.** `tradeHistory.Count` is a running counter from the chart load, not from session start. Changing "Days to Load" in NT8 produces a different start date and therefore different totals. File-lock errors visible in the capture (lines 5, 46, 47, 104, 3108, 3111) mean some events were dropped during the original run. A re-run of the same chart with the same settings on a different day may capture different events if the cockpit dashboard happens to be running.

5. **6 weeks is too short for anything beyond "the live system as currently implemented is not printing money immediately."** March–April 2026 was a specific regime: elevated volatility, a correction into an April low, and a sharp recovery. It is not a representative regime sample. AM's 15-year track record implies the strategy has profitable periods and drawdown periods; 6 weeks proves neither.

**Verdict on the V2_4 backfill:** It is the ground-truth probe. It is necessary but not sufficient. The correct use of the Mar–Apr result is to anchor expectation (the indicator as currently wired, with all known incomplete rules and the $150 lockout, broke even on a 6-week window) and to motivate the remediation plan in Section 4. It is not a production backtest and should not be presented as one.

### Which Pipeline to Use as the Forward Backtest Basis

Neither pipeline alone is suitable. The right basis is a new integrated pipeline that:
- Uses the 13.6-year 1-min CSV as its data source
- Synthesizes V2_4-equivalent entry events (implementing the correct TREND/FADE candidate pools, retrace-side filter, latch logic, signal cap, cooldown, and daily-loss lockout)
- Uses the `realized_R_runner` label from `label_builder.py` as the outcome metric
- Applies the rt2_1 tier filter to restrict events to the modeled subset
- Applies a parametric fill-rate at each sensitivity point (30%, 50%, 70%, 100%)
- Reports Sharpe using the zero-fill convention already in `walkforward.py`

This is not a from-scratch build — it is the Python pipeline with mode logic and guard rails added to the event-selection layer. Estimated effort: 3–4 weeks for a developer who knows both the C# V2_4 codebase and the Python pipeline.

---

## 2. Data Inventory — What We Have vs What We Need

### What We Have

**1-min CSVs, 2012-08-12 to 2026-04-22 (~13.6 years):**
Four instruments — ES, NQ, CL, GC — each approximately 4.7 million rows of OHLCV continuous-contract data. This is the foundation for any offline backtest and is sufficient for: event synthesis, label generation, ML training and walk-forward, regime stratification, and sub-period stability analysis. The data is useable. There are no critical gaps in this dataset.

**JSONL session captures, 2025-10-21 to 2026-04-27:**
103 session folders, 15,882 unique events after deduplication. Only 7 sessions (post-2026-03-17) have full V2_4 instrumentation including heartbeats, phase changes, bias changes, and bar_close events. Pre-2026-03-17 sessions contain only touch events. The corpus has 2 signal events in total (both March 2026), meaning it cannot be used for signal-level OOS validation without much more data collection. It can be used for: touch-detection recall comparison against the Python event-builder, fill-rate measurement (see Section 3), and day-type regime labeling across the 7 instrumented sessions.

**Pre-built parquet artifacts:**
Event, feature, label, and model parquets exist for all four instruments under `pattern_scorer_rt2_1/output/`. These are reproducible outputs of the offline batch pipeline. The walkforward summary, subperiod stability, and Monte Carlo drawdown outputs also exist. These are valid inputs for the forward remediation plan.

### What We Are Missing

**No tick data anywhere.** Every backtest runs on 1-min bars. This creates three concrete gaps:

1. **Fill rate cannot be measured from bar data alone.** A 1-min bar showing `low = entry_price` tells you price touched the level but not whether a limit order at that price filled. The fill could have been zero shares (price traded through without a resting order being present), partial (only some of a queue position filled), or full. The only way to measure fill rate from bar data is a conservative proxy: if the bar range extends meaningfully beyond the entry price (implying durable two-way trade at the level), the fill probability rises. If the bar touches the level on the low and immediately bounces (bar low = level, close well above), the fill probability is lower.

2. **Intra-bar stop-vs-target sequencing is unresolvable.** `label_builder.py` uses the "stop wins on contained bars" convention. When a 1-min bar has `low <= entry - stop_dist` and `high >= entry + target_dist` simultaneously, the label records a loss. This is conservative but wrong in the direction of pessimism about 15%–20% of events. Tick data would resolve the actual sequence.

3. **Slippage on market stop exits cannot be calibrated.** When a stop is hit and the indicator exits via a market order, the actual fill depends on the order book at that moment. During fast-market conditions (the moments when stops are most likely to be hit), spreads widen and slippage can exceed the assumed 2-tick figure. Without tick data, the 2-tick assumption is unjustified.

**What tick data would require:** A tick data subscription for ES and NQ from any of the standard vendors (CQG, Rithmic, DTN/IQ) costs $50–200/month at retail. Three months of paper trading with tick capture is more valuable than any tick data purchase from a historical vendor, because it measures fill rate under the actual current market microstructure rather than microstructure from prior years.

**T&S log capture and order book snapshots:** These would enable proper fill-rate modeling and slippage calibration. They are worth building in the paper-trading phase (next 90 days) but are not prerequisites for the first-iteration backtest remediation. Build what you need when you have live signal flow to capture.

---

## 3. Fill-Rate Validation — The Existential Question

This is the single question that determines whether the Python pipeline's edge is real. Nothing else matters as much.

### The Problem in Precise Terms

The Python runner backtest reported $805K net on the 2024–2026 holdout at $500/trade risk. The M2v2 spec explicitly states that if fill rate is 50%, that drops to approximately $380K — and if fill rate scales with level quality (better entries on slower-moving setups, worse entries on the cleanest breakouts), the marginal Tier-A event may have a materially lower fill rate than the average Tier-A event. At 30% fill rate, the pipeline would break even net of commissions at $500/trade risk. The fill-rate assumption is the difference between "this system has an institutional-grade edge" and "this system has a statistical artifact."

AM's direct observation: round-number pivots and opening-range highs are front-run. In a market of sophisticated participants, a limit order at the prior-day high is competing with every other algo and prop trader who knows AM's method or any similar Baiynd-style approach. Being filled at exactly the prior-day high means your order was at the back of the queue and the level held — which is the worst case for the subsequent trade. The fills you do not get are the clean breaks through the level, which are the setups AM teaches as the highest-quality moves.

### The Measurement Plan

**Step 1 — JSONL-based fill proxy (can be done today):**
Write a script that iterates over every V2_4-era `touch` event in the JSONL corpus where `retrace_side=true` and `already_latched=false`, extracts the `level_price` and `session_date`, joins against the 1-min CSV for the same instrument and date, and checks the next 5 bars after the touch bar for evidence of fill:
- **Probable fill:** The next bar or the bar after it has a range that extends at least 1 tick beyond the entry price in the trade direction AND the bar subsequently closes beyond the entry price. This confirms the market transacted through the level.
- **Probable no-fill:** Price touched the level on the wick of the touch bar and immediately reversed; the 5-bar forward range never exceeded the entry price by more than the spread.

The JSONL corpus has 741 qualifying touches across 103 sessions. Even at a 60% "probable fill / probable no-fill" classification rate, this gives ~445 data points — enough for a directional estimate of fill rate by level type.

**Step 2 — Level-type stratification:**
Break the fill-rate estimate by `level_touched` (GlobExH, EuropeH, ORH, Pr30H, VWAP, AnchVWAP, etc.). Levels like EuropeH and GlobExH are structural and are touched less frequently — these likely have higher fill rates because they require sustained directional moves to reach. Levels like Pr30H and ORH are touched multiple times per week — these likely have lower fill rates because they attract queue competition.

**Step 3 — Sensitivity analysis:**
After estimating fill rate by level type, apply a parametric sweep to the Python runner backtest:

| Fill Rate | Assumed Net (from spec baseline ~$800K) | Implied Sharpe |
|---|---|---|
| 100% (current baseline) | $805K | 10.06 |
| 70% | ~$550K | ~6–7 |
| 50% | ~$380K | ~3–4 |
| 30% | ~$200K | ~1.5–2 |
| Stratified by level type | TBD | TBD |

The 50% column is the defensible conservative estimate. The stratified estimate should be the headline number once the JSONL fill-rate analysis is complete.

**Step 4 — Paper trading confirmation (30–90 days):**
Log every entry signal from the live system with: the time the limit order was placed, the time a fill was confirmed (manually by AM or automatically if the broker API is connected), and whether a fill was received before the order was cancelled or the signal expired. After 30 trading days, compute: (fills received) / (limit orders placed). This is the only unimpeachable fill-rate estimate.

---

## 4. Replay Fidelity Gaps — What to Fix in V2_4 Historical Mode

The V2_4 indicator running in `State.Historical` has four known systematic differences from live operation. These are not speculative — they are confirmed by reading the code.

### Fix 1: Daily-Loss Lockout in Historical

**Current state:** `realizedPnlDollarsToday` accumulates only in `State.Realtime` (line 2754). Historical-mode trades never trip the lockout. The lockout was configured at $150/day in the only captured backfill run, which would trip on the first losing MES trade of any typical session.

**What to fix:** Add a `State.Historical`-compatible PnL accumulation path that resets on `ResetForNewDay()` and evaluates `CheckLockout()` after each `RecordAndDrawTrade()` call in Historical. The daily-reset logic already exists; the PnL accumulation just needs to be ungated from `State.Realtime`.

**Impact:** Potentially material. If the $150 lockout were enforced, many backfill days would have been single-trade days. The 41.7% WR and PF 0.94 result would likely change — the direction depends on whether the locked-out trades were winners or losers, which requires measuring. There are two defensible approaches: (a) enforce the lockout at the same $150 level as live and see what happens, or (b) re-run with the lockout at a more realistic value ($500 per ES contract, $50 per MES contract) and report both.

### Fix 2: Post-Stop Cooldown in Historical

**Current state:** `lastStopTime` is only set in `State.Realtime` (line 2609). Historical mode can take a signal on the bar immediately after a stop.

**What to fix:** Set `lastStopTime` in both states, or track a separate `historicalLastStopTime` variable that feeds `IsInCooldown()` during Historical replay.

**Impact:** Moderate. The cooldown is 30 minutes by default. In a session with multiple stops, the cooldown would suppress subsequent signals that the current backfill counts. The net effect on PnL is ambiguous but the direction of correction is clear: the backfill currently over-counts signals.

### Fix 3: Machine-Readable Trade Export

**Current state:** Every `RecordAndDrawTrade()` call appends to `tradeHistory` in memory and calls `Log()` to NT's Output window. No disk write occurs.

**What to fix:** On each `RecordAndDrawTrade()` call (or at `ResetForNewDay()` which runs at session close), append a structured CSV row to a file at `{JsonlLogFolder}/{YYYY-MM-DD}/trades.csv` with columns: `trade_id, entry_time, exit_time, entry_price, exit_price, direction, mode, level_name, stop_price, exit_reason, qty, pnl_points, pnl_dollars, win`.

**Impact:** This is the single change with the highest leverage for institutional credibility. A machine-readable trade file enables: automated PnL attribution, per-level and per-mode performance breakdown, reproducibility testing across chart reloads (compare two runs of the same date range), and cross-reference against the Python pipeline's expected signals for the same window.

### Fix 4: Reproducible Backfill State

**Current state:** `tradeHistory.Count` is a running cumulative counter from chart load. Two chart loads with different "Days to Load" settings produce different totals. There is no "start fresh from this date" reset.

**What to fix:** Add a `BacktestStartDate` parameter. On `State.Historical` entry, if `BacktestStartDate` is set, skip all `RecordAndDrawTrade()` logic for bars before that date. Reset all session-state counters (`signalsToday`, `realizedPnlDollarsToday`, `losingTradesToday`) on the first bar at or after `BacktestStartDate`. This ensures two runs of "2023-01-01 to 2026-04-22" produce identical results regardless of how many prior bars NT loads.

---

## 5. OOS Partitioning — Recommendation

### Why Naive Calendar Split Will Not Work

The JSONL corpus has a hard schema break on 2026-03-17. Before that date, sessions contain only `touch` events. After that date, sessions add `heartbeat`, `phase_change`, `bias_change`, `bar_close`, `signal`, and `lockout` events. Any model trained on pre-March data and tested on post-March data has training features that do not exist in the training period (day_type, bias, MOC, phase). The entire feature set would need to be reconstructed from the 1-min bars rather than the JSONL for the pre-March period, which is exactly what the offline `event_builder.py` does.

Additionally, there are only 7 V2_4-instrumented sessions total. A held-out "test set" of 2 sessions is not statistically meaningful for any signal-level validation. Forward collection must precede any JSONL-based OOS test.

### Recommended Three-Phase Partition

**Phase A — Entry-rule backtest using all 13 years of 1-min CSVs:**
The 1-min bar corpus is the right input for validating the entry setup statistics. Using `event_builder.py` to synthesize touches from raw bars, applying the correct V2_4 TREND/FADE candidate pools, running `label_builder.py` to compute outcomes, and filtering through the rt2_1 tier model gives a 13-year event tape. This is the core quantitative validation and should be the primary numerical claim.

The recommended OOS architecture for this phase:
- Training window: 2012-08-12 to 2023-12-31 (approximately 11.4 years)
- Validation window: within training, last 10% by event count (used only for LightGBM early stopping and tier-cut quantile fitting)
- Test window: 2024-01-01 to 2026-04-22 (approximately 2.3 years, ~585 trading days)

This is the existing split in `walkforward.py`. It is clean. Do not change it.

The additional work needed on top of the existing structure: (a) add FADE-mode event synthesis to the event builder so FADE-day events are labeled with FADE exit logic; (b) add a signal-cap and cooldown simulation to the backtest runner; (c) apply fill-rate sensitivity.

**Phase B — Day-type and MOC gating validation using V2_4-instrumented sessions:**
The 7 V2_4-instrumented sessions (post-2026-03-17) are the only data for validating the day-type classification, MOC state, and phase-gating logic that are unique to V2_4. These sessions are too few for any train/test split. Use all 7 as a calibration set and report per-session fits with no held-out data.

For real OOS validation of V2_4-specific rules, commit to collecting 30 additional sessions before any backtest is treated as out-of-sample for those rules. At the current cadence (roughly 5 sessions per week), that is 6 weeks of logging.

**Phase C — Forward walk-forward as sessions accumulate:**
Once the trades.csv export is implemented (Fix 3, Section 4), each live session produces a ground-truth trade record. Run the following rolling window walk-forward:
- Train: 6-month window of bar data
- Test: 1-month hold-out
- Roll forward monthly

This is the production cadence. After 6 months of live session data with the machine-readable export, the first institutional-grade rolling walk-forward claim becomes possible.

### Walk-Forward Window Specification

- 6-month train, 1-month test, roll monthly
- Minimum: 4 folds before any claim on the post-2024 slab (the existing single 2024-cutoff OOS is one fold — not enough for an institutional claim on stability of the walk-forward process)
- Regime stratification: for each test fold, verify the fold contains at least one TREND session, one FADE session (as labeled by V2_4 heartbeat `day_type`), and at least one high-volatility session (e.g., FOMC day, CPI day, or VIX > 25). If any fold is mono-regime, report it explicitly rather than aggregating.

### Instrument Hold-out

The current setup trains per-instrument with no cross-instrument generalization test. For institutional-grade reporting, hold out one instrument as a pure generalization test:
- Backtest ES and NQ (primary markets)
- Validate the rule structure on CL and GC (secondary markets with known V2_4 bugs in CL — the rthOpenHour hardcoding and volume threshold fallback)
- The CL result under the current indicator will underperform ES/NQ for documented reasons; this is useful precisely because it shows the model knows something instrument-specific rather than just fitting to market noise.

---

## 6. Performance Metrics — The Right Ones

### Primary Metrics (required in any institutional claim)

**Sharpe ratio (annualized, zero-filled):** Compute over all trading days in the test window, filling zero on days with no signal. The `walkforward.py` pipeline already does this — it is the right convention. Do not report Sharpe computed only over days with trades. Target range: 2.0–3.5 after fill-rate adjustment.

**Profit factor:** Sum of winning trades divided by absolute sum of losing trades. Target: 2.5–4.0. Note that the current V2_4 backfill produced PF 0.94 — substantially below target — under known-incomplete conditions. This is not a contradiction with the target range; it is a floor estimate from a broken implementation.

**Win rate:** Target 45–60%. This is compatible with AM's method, which generates frequent small wins and occasional large runners. A 94% win rate is inconsistent with AM's method; it implies the SMA20 trail is compressing loss magnitude in a way that does not reflect real trading. A 41.7% win rate from the V2_4 backfill is probably too low (the incomplete stop rule and over-restrictive lockout suppress wins), but it is directionally more believable than 94%.

**Average winner / average loser ratio:** This is the AM right-tail signal. If runners are working, the avg winner should be 2–3× the avg loser. The V2_4 backfill shows avg win 19.24 pts vs avg loss 14.58 pts — a ratio of 1.32, which is below the 1.5 floor of the target range. This suggests the trail exits are happening too early or the stop placements are too tight. Compare the 13-year Python simulation's distribution of `realized_R_runner` against this 1.32 ratio to see whether the gap is a regime effect or a structural rule failure.

**Maximum drawdown:** Report in three ways: dollar terms (per-instrument and per-portfolio), percentage of account (assuming a standard account size of $25K for MES, $50K for ES), and duration in trading days. Maximum drawdown matters more than Sharpe for evaluating whether AM will actually trade through the model's worst periods. Target: 5–12% of account.

### Secondary Metrics (required for the tail analysis)

**Sortino ratio:** Sharpe computed using only downside deviation (semi-deviation below zero). More informative than Sharpe when the return distribution is right-skewed, as AM's method should be. Target: Sortino > 3.0 given the right-tail runner thesis.

**Kelly fraction:** Estimate the full Kelly fraction and report it. Do not recommend trading at full Kelly. Use it to bound the "this system would survive at what position size" question. A Kelly fraction above 20% is a reasonable sanity check for a strategy with AM's claimed win rate and payoff ratio.

**Tail metrics — the institutional differentiator:** Report explicitly:
- 95th percentile loss (single trade)
- 99th percentile drawdown over any 20-day window
- Maximum consecutive losers (and the account drawdown that string produced at standard sizing)
- Drawdown distribution: what fraction of 20-day windows showed drawdown greater than 5%, 10%, 15% of account?

The Monte Carlo drawdown output in `robustness_checks.py` exists and found that realized drawdowns in the backtest are 1.5–7× worse than MC p99. This is because trades cluster — ES and NQ both pulling back at the same time means portfolio drawdowns are correlated. Report this finding explicitly. The institutional reviewer will ask about it and the answer ("trades cluster, our MC understates tail risk by 1.5–7×, here is the realized distribution") is more credible than silence.

### Metrics to Avoid or Flag

**Win rate without the payoff ratio:** A 45% win rate sounds bad in isolation. Report it always with the avg-winner/avg-loser ratio.

**Sharpe without the fill-rate sensitivity table:** Any Sharpe above 3.5 should carry an explicit footnote about the fill-rate assumption. The "base case is 70% fill, conservative case is 50% fill, stress case is 30% fill" framing is the right presentation.

**Net P&L in dollar terms without trade count and account size context:** $800K over 2 years sounds impressive until you note it assumes $500/trade risk on fractional contracts that round to 1 MES at production sizing, which produces ~$50/trade risk and actual realized P&L closer to $80K. Always normalize.

---

## 7. Slippage and Commission Realism

### Current Python Pipeline: 1/2/1 Ticks, $4.50 RT

The current slippage model: 1 tick adverse on entry, 2 ticks adverse on stop exit, 1 tick adverse on trail/timeout exit. Commission: $4.50 round-trip.

**Is $4.50 correct?** At retail broker rates for small accounts, $4.50 RT is reasonable. At pro-tier retail (over 500 contracts/month), RT is closer to $1.50–$2.50. CME exchange-fee floor is approximately $1.36 RT on ES/NQ, lower on micros. The $4.50 figure should be labeled as "retail commission assumption" and a sensitivity test at $2.00 RT should be reported.

### Per-Instrument Tick Economics

| Instrument | Tick Size | Dollar/Tick | 1-tick entry slip | 2-tick stop slip | Notes |
|---|---|---|---|---|---|
| ES | 0.25 pts | $12.50 | $12.50 | $25.00 | Standard |
| MES | 0.25 pts | $1.25 | $1.25 | $2.50 | Micro |
| NQ | 0.25 pts | $5.00 | $5.00 | $10.00 | Standard |
| MNQ | 0.25 pts | $0.50 | $0.50 | $1.00 | Micro |
| CL | 0.01 pts | $10.00 | $10.00 | $20.00 | Standard |
| GC | 0.10 pts | $10.00 | $10.00 | $20.00 | Standard |

For a $500/trade risk simulation, an ES trade with a 4-point stop is risking $200/contract. A 2-tick stop slip ($25) represents a 12.5% risk overrun per losing trade. On MES (same stop in points, $2.50/tick), the 2-tick slip is trivial. The slippage impact is instrument- and contract-size-dependent. The Python pipeline uses dollar-equivalent slippage consistently, which handles this correctly as long as the point value multiplication is right.

### Limit-Only Entry: No Slippage on Fills That Happen

This is the one legitimate advantage of limit-order execution. When a limit order fills, it fills at or better than the limit price by definition. The 1-tick adverse entry slip in the Python pipeline is actually conservative — in normal market conditions, a resting limit at a level fills at exactly the level price, not adverse. The 1-tick entry slip is a reasonable proxy for the occasional skip-ahead where price gaps the level by one tick, but in calm conditions it overstates entry cost.

The 2-tick adverse stop slip is appropriate. Stops are market orders placed when the hard-stop level is breached, and in fast markets this can be worse than 2 ticks. For ES in a trending sell-off, a stop fill 2 ticks through the stop level is optimistic. A better calibration would be: 2 ticks in normal conditions, 4–6 ticks on high-velocity bars (any bar with range > 1.5× ADR20 / 390). Until paper trading data is available, 2 ticks is the right conservative point estimate.

### The Slippage That Is Not Modeled: Round-Number Front-Running

At levels like prior-day high (a round number in many markets), the opening range high (psychologically significant), and VWAP (heavily watched), the spread widens on approach. This is not captured by any point-estimate slippage model. It is partly captured by the fill-rate haircut — the most competitively crowded levels are also the most likely to produce partial fills or no fills. Treating slippage and fill rate as separate phenomena is the right decomposition: fill rate handles "did the order transact," slippage handles "at what price."

---

## 8. AM's Actual Profile as the Reference

### Why the Prior Matters

AM has been trading this method for 15 years with documented consistency. "Small wins frequent, occasional big wins" describes a specific equity-curve shape: a rising step function with flat-to-slightly-negative periods followed by breakout runner trades. This is not compatible with a 94% win rate (which implies almost no losers) or a PF of 0.94 (which implies the strategy is essentially breakeven). Both extremes are artifacts of the measurement systems, not the underlying method.

The correct prior for any backtest of an encoding of AM's method is: the backtest should produce metrics within the range that would describe AM's known results. Any metric that falls significantly outside that range requires explicit explanation, not just reporting.

### Target Metric Ranges

These are the ranges a defensible backtest of AM's method should produce. Deviations outside these ranges should be explained, not reported as headline numbers.

| Metric | Defensible Target | Notes |
|---|---|---|
| Sharpe (annualized, zero-filled) | 2.0 – 3.5 | After fill-rate adjustment at 50–70% |
| Profit Factor | 2.5 – 4.0 | Consistent with "small wins, occasional big wins" |
| Win Rate | 45 – 60% | Not 94%, not 42% |
| Avg Winner / Avg Loser | 1.5 – 3.0 | Right-tail runners should skew this above 1.5 |
| Max Drawdown (% of account) | 5 – 12% | ~$2,500–$6,000 on a $50K ES account |
| Trades per Day | 1 – 4 | Signal cap is 3 TREND, 2 FADE |
| Sortino Ratio | > 3.0 | Right-tail skew should elevate Sortino vs Sharpe |
| Kelly Fraction | 15 – 30% | Healthy edge without over-leverage |

### What "This Is AM's Strategy Working" Looks Like Empirically

Three specific patterns in the trade record would constitute evidence that the backtest is capturing AM's method:

1. **Right-tail runner trades at least 10% of events.** In any 100-trade sample, at least 10 should show `realized_R_runner > 2.0` (i.e., the SMA20 trail ran at least 2× the initial stop distance before exiting). If runners are absent, the strategy is being executed as a scalp, which is not AM's method.

2. **FADE-day performance modestly below TREND-day performance.** FADE days are lower-conviction environments by definition. If FADE trades outperform TREND trades, something is wrong with the mode classification. If they severely underperform, the FADE logic needs revisiting.

3. **Level hierarchy makes intuitive sense.** GlobExH/L and EuropeH/L should show higher average R than ORH/ORL (which are noisier due to the 30-minute formation period). PrInstH/L, as AM's primary levels, should be near the top of the per-level performance ranking. If SMA50_30 or Pr30H are the top-performing levels, the model is capturing something structural but not necessarily AM's method.

---

## 9. The Gap Punchlist — Ranked by Institutional Impact

### Tier 1: Would Force a "No Go" at Any Institutional Review

**Gap 1 — No fill-rate measurement (effort: 2 weeks)**
Write the JSONL-to-bar fill proxy script described in Section 3. Apply the resulting fill-rate stratification to the Python backtest as a sensitivity analysis. Publish the 50% fill-rate headline Sharpe. Until this exists, every backtest number carries an asterisk.

**Gap 2 — No machine-readable trade export from V2_4 Historical (effort: 1 day)**
Add the trades.csv write to `RecordAndDrawTrade()`. This is one function call to a file write. It is the cheapest high-impact fix on this list. Every subsequent claim about the indicator's performance depends on it.

**Gap 3 — Two independent ground truths that disagree (effort: 3 weeks)**
The Python pipeline and the V2_4 indicator produce different "wins" for the same nominal signal. Pick one canonical metric — `realized_R_runner` — and ensure the V2_4 trade record can be compared against it. Specifically: re-score the 84 Mar–Apr backfill trades through the rt2_1 model by matching each V2_4 signal's (date, level, direction) against the Python event parquet and comparing the Python-labelled outcome against the V2_4-recorded outcome. This is the "how different are they" measurement.

**Gap 4 — Sharpe 9–10 stated as a production target anywhere in documentation (effort: 1 hour)**
Remove or explicitly disclaim this number in every document it appears. Replace with "Sharpe 2–3 defensible at 50% fill rate; Sharpe ~5 at 100% fill rate; 100% fill rate is unvalidated." This is a documentation change but it matters enormously for institutional credibility.

### Tier 2: Would Force a "Conditional" at Institutional Review

**Gap 5 — Daily-loss lockout absent in Historical (effort: 1 day)**
Fix as described in Section 4, Fix 1. Re-run the Mar–Apr backfill with the lockout enforced at a realistic threshold ($500/MES contract).

**Gap 6 — Cooldown absent in Historical (effort: 4 hours)**
Fix as described in Section 4, Fix 2. Re-run and compare.

**Gap 7 — No FADE-mode simulation in Python (effort: 1 week)**
The Python runner pipeline applies the runner policy to all events. FADE-day events should use the first-target-only label (`realized_R_first_target_only` with `target = PrInstH/L`) rather than the runner label. Add a day-type classification step to the event builder that uses the 30-min bar data to synthesize an approximate V2_4 body-stack classification, then route events to the appropriate label.

**Gap 8 — Single walk-forward cut (2024-01-01) is one fold, not a rolling walk-forward (effort: 1 week)**
Add a 4-fold rolling window to the existing Python pipeline. Roll monthly over the 2024-2026 test period. Report per-fold Sharpe and profit factor. If performance is stable across folds, the single-cut claim is confirmed. If it degrades, the single-cut was optimistic.

**Gap 9 — No regime-stratified sub-group analysis (effort: 3 days)**
Use the VIX daily data (already in `data/csv/INDX/`) to partition the 2024-2026 test period into: low-vol (VIX < 18), medium-vol (VIX 18–25), high-vol (VIX > 25). Report Sharpe and PF in each bucket. High-vol periods are when AM's method is most valuable and most risky — they should be reported explicitly.

**Gap 10 — CL rthOpenHour bug (effort: 2 hours)**
Fix the hardcoded `rthOpenHour=9, rthOpenMinute=30` for CL (V2_4 lines 853–854). CL opens at 9:00 ET; every time-gated function in V2_4 is 30 minutes off for CL. This is a confirmed code bug.

### Tier 3: Worth Building in v1.1

**Gap 11 — JSONL write-failure due to file lock contention (effort: 4 hours)**
Switch the JSONL logger to open with `FileShare.ReadWrite` or log to a per-process buffer with end-of-session merge.

**Gap 12 — Holiday and early-close calendar absent in both pipelines (effort: 1 day)**
Integrate `pandas_market_calendars` or a static holiday CSV into both the Python event builder and the V2_4 date arithmetic. Early-close days and FOMC/NFP/CPI blackouts should be explicit, not implicit.

**Gap 13 — Indicator loading twice on multi-data-series chart (effort: 1 day)**
The duplicate log lines in the Mar–Apr capture (every Print appears twice) suggest the indicator loaded twice. Investigate whether `BarsInProgress` logic causes double-execution on the primary series. Fix the source to deduplicate before it causes more serious double-counting in the trades.csv export.

**Gap 14 — Fractional contract sizing in Python sim (effort: 4 hours)**
The Python sim uses `contracts = $500 / (stop_dist × point_value)`, producing fractional contracts. Live trading rounds to 1 contract minimum, increasing per-trade risk on tight stops. Add a `round_up=True` flag to the dollar simulation and report the haircut.

**Gap 15 — Pattern B is scaffolded only (effort: 2 weeks)**
`LevelWatchState` and `CheckPatternBEntry` are declared but never wired. This is the "look-below-and-fail" entry pattern that is 43% of all JSONL touch events by count. Wiring Pattern B would approximately double the candidate signal pool. This is a strategy development item, not a backtest remediation item, but its absence means the current indicator is testing only one of AM's two primary entry patterns.

---

## 10. The 30-Day Plan

### Week 1: Fix the Measurement Infrastructure

**Day 1–2:** Add the `trades.csv` export to `RecordAndDrawTrade()` in V2_4 (Gap 2). Add the daily-loss lockout to Historical mode (Gap 5). Add cooldown to Historical (Gap 6). These three changes take less than two days combined and immediately make the indicator a reproducible measurement instrument.

**Day 3–4:** Run a fresh chart backfill over the full 2025–2026 period (as far back as NT8 loads reliably) with the three fixes active. Capture the machine-readable trade file. This is the first honest V2_4 performance measurement.

**Day 5:** Write and run the JSONL fill-rate proxy script (Gap 1). Estimate fill rate by level type. Apply the 50%/70% sensitivity to the Python backtest's headline Sharpe numbers. Update any documentation that shows Sharpe > 4 with the corrected ranges.

### Week 2: Reconcile the Two Pipelines

**Day 6–8:** Match the 84 Mar–Apr V2_4 trades against the Python event parquet (Gap 3). For each V2_4 trade, find the corresponding Python event by (instrument, session_date, level_touched) and compare: did the Python model tier-A this event? What did `realized_R_runner` say the outcome should be? What did V2_4 actually record? Build a table of these comparisons. The disagreements will show exactly where the two pipelines diverge and what the realistic distribution of ML-filtered trades looks like.

**Day 9–10:** Fix the CL `rthOpenHour` bug (Gap 10) and test CL-specific performance against known CL events in the JSONL.

### Week 3: Strengthen the Python Walk-Forward

**Day 11–13:** Add 4-fold rolling walk-forward to the Python pipeline (Gap 8). Roll monthly over the 2024–2026 test period. Confirm that Sharpe and PF are stable across folds. If they degrade, investigate whether the model is overfitting to the 2024 initial holdout.

**Day 14–15:** Add FADE-mode simulation to the event builder (Gap 7). Use a simplified body-stack classifier from the 30-min bars (close-above-open alignment of the four master candles) to partition events into TREND and FADE. Apply first-target-only labels to FADE events. Re-run the walk-forward and compare FADE vs TREND performance.

### Week 4: Regime Analysis and Documentation

**Day 16–18:** Add VIX-stratified regime analysis (Gap 9) to the Python walkforward. Report per-regime Sharpe and PF.

**Day 19–20:** Write the updated performance summary. Replace every instance of "Sharpe 9–10" with the corrected range (Sharpe 2–3 after fill-rate adjustment, Sharpe 5–6 at 100% fill before mode/cap adjustments). Explicitly label the V2_4 Mar–Apr result as a floor from an incomplete implementation.

**Day 21–22:** Begin systematic paper trading with tick-level fill logging. Log every signal: the level, the direction, the time the limit was armed, the time it was filled or cancelled, and the subsequent trade outcome. This forward collection is the only path to a fill-rate estimate that will satisfy an institutional reviewer.

**Day 23–30:** First review checkpoint. After one full month of data with the fixes in place, evaluate: does the machine-readable V2_4 trade file show improving performance? Does the Python pipeline's fill-rate-adjusted Sharpe fall in the 2–3 range? Are the 7 V2_4 sessions now growing to 12–15 sessions with full instrumentation? If yes, the credibility trajectory is correct and the longer walk-forward cycle (Section 5, Phase C) can begin.

---

## Cross-Reference Notes

| Finding | Source | Action item |
|---|---|---|
| Sharpe 9–10 from Python pipeline — source and inflate factors | python_pipeline_audit.md §7, M2v2_runner_system.md §6.1 | Apply fill-rate haircut, FADE exclusion, signal cap; cite in documentation |
| PF 0.94 from V2_4 backfill — specific limitations | backtest_infra_audit.md §9, v24_code_audit.md §1.4 | Fix lockout/cooldown in Historical; add trades.csv export; re-run |
| JSONL has only 2 signals in 6 months; 0.27% conversion rate | jsonl_data_analysis.md §Q3 | Cannot use JSONL for signal-level OOS without 30+ new sessions |
| Schema break at 2026-03-17 | jsonl_data_analysis.md §Q9 | OOS partition must respect schema boundary |
| Day-type vocabulary mismatch (JSONL emits "congestion", not "Sideways") | jsonl_data_analysis.md §Q4, v24_code_audit.md §TL;DR | Confirm whether "congestion" = "Sideways" and update FADE gate or emitter |
| CL rthOpenHour bug — 30-minute offset on all time-gated functions | v24_code_audit.md §9 | Fix lines 853–854 in V2_4 |
| Pattern B is 43% of touches but scaffolding only | jsonl_data_analysis.md §Q5, v24_code_audit.md §2 | Strategy development milestone; not blocking current backtest remediation |
| Stop rule uses europe-4AM-width, not per-trigger-candle width | v24_code_audit.md §4 | Labels in Python pipeline also use europe-width clipped to ADR — consistent approximation; but AM's actual rule is not implemented |
| Daily-loss lockout configured at $150 in the only captured live run | backtest_infra_audit.md §9, §3 | Confirm intended production threshold and use same value in Historical |
| 100% fill assumption is acknowledged in M2v2 spec §6.1 | python_pipeline_audit.md §5 | The spec is honest about this; the headline number should reflect the conservative scenario |
| PrInstH/L bug in V2_0–V2_2 (used prior day's close330 instead of current) | version_diff_audit.md §3 | Fixed in V2_3; any backtest data from before V2_3 era should be treated with this caveat |
| VWAP removed from candidate pool in V2_4 | version_diff_audit.md §removed-at-V2_3-V2_4 | The 2 JSONL signals both fired off VWAP when VWAP was still in the pool (V2_3 era). Post-V2_4, VWAP signals will not appear. |
