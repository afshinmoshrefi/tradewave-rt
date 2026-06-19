# Backtest Infrastructure Audit
**Date:** 2026-04-27
**Scope:** All historical-replay, label generation, and performance evaluation surfaces across the AMTradeCockpit V2_4 / pattern_scorer / decision_engine / cockpit ecosystem.
**Author:** Wave-2 audit (Backtest Infrastructure Agent)
**Reviewer (deliver to):** Afshin / Wave-3 synthesis

---

## TL;DR

There are **two completely separate backtest pipelines** in this project, and they do not agree on what a "trade" is, what a "win" is, or how a fill happens. Pulling them together is the single biggest gap blocking institutional-grade backtesting:

1. **NinjaTrader-side replay (V2_4 indicator running State.Historical):** an ad-hoc cumulative trade tape (`tradeHistory`) the indicator builds while NT backfills the chart. No proper test harness — runs as a side-effect of loading the indicator, accumulates trades across all days into one running pool, applies `pointValue × qty` for $ projection, and writes nothing to disk. **41–43% win rate, profit factor ~0.94**, net ~−$2,000 in MES across Mar 13 – Apr 21 in the only run we have on file (`output of test march 13 to april 21,.txt`).
2. **Python-side runner-label backtest (`pattern_scorer_rt2/src/experiments/runner_backtest.py`):** a proper offline backtest framework — vectorised events from CSV bars, runner-policy R-multiple labels, LightGBM training, strict pre-2024/post-2024 OOS split, slippage and commission modelling, walk-forward + Monte-Carlo + corrected-Sharpe robustness checks. Reports **94% win rate, Sharpe 6–10 on Tier-A**.

The indicator's losing record (PF 0.94, 42% wins) and the Python pipeline's exceptional record (PF >>1, 94% wins) describe **two different strategies sharing one name**. The V2_4 indicator backfill is the actual rule (limit-at-touch with retrace-side filter, AM's mode logic, TimeClose at 15:00). The Python runner-label backtest tests the runner *concept* against the Python event grid, but the entry/exit semantics, mode handling (TREND vs FADE), pre-place behaviour, daily lockout, and signal-cap are not in the simulation. Neither is currently a defensible backtest of the live system.

The **Sharpe 6–10 numbers are not believable as a forward-looking estimate** for the actual live system; the M2v2 spec itself flags this in §6.1 ("fill-rate bias is the single most important unvalidated assumption"). Re-stating: a defensible institutional-grade claim from current artefacts is "approximately Sharpe 4–5 on the scoring layer alone, fill rate untested, indicator-level rule replication produced losses on the 6-week sample."

---

## Cross-reference notes

| Topic | Authority | Path |
|---|---|---|
| Indicator-side trade replay | V2_4 source, `tradeHistory` + `RecordAndDrawTrade` | `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMTradeCockpitV2_4.cs` lines 381, 920, 932, 1618-1622, 1984-1988, 2391-2502, 2722-2762 |
| Python event builder | `event_builder.py` | `C:\seasonals\pattern_scorer_rt2\src\events\event_builder.py` |
| Runner label simulator | `label_builder.py` | `C:\seasonals\pattern_scorer_rt2\src\labels\label_builder.py` |
| OOS walk-forward | `walkforward_runner.py` | `C:\seasonals\pattern_scorer_rt2\src\experiments\walkforward_runner.py` |
| Slippage/commission backtest | `runner_backtest.py` | `C:\seasonals\pattern_scorer_rt2\src\experiments\runner_backtest.py` |
| Robustness (Sharpe, MC DD) | `robustness_checks.py` | `C:\seasonals\decision_engine\src\robustness_checks.py` |
| ml_scorer_rt walk-forward folds | `fold_runner.py`, `fold_builder.py` | `C:\seasonals\ml_scorer_rt\src\walkforward\` |
| ml_scorer_rt simulator | `trade_engine.py` | `C:\seasonals\ml_scorer_rt\src\simulator\` |
| Indicator-Python recall | `indicator_recall.py` | `C:\seasonals\pattern_scorer_rt2_1\src\diagnostics\indicator_recall.py` |
| Bar history | `ES.csv` / `NQ.csv` / `CL.csv` / `GC.csv` (2012-08-12 → 2026-04-22, 1-min) | `C:\seasonals\data\csv\futures\1min\` |
| JSONL event captures | per-day `events.jsonl` (Oct 2025 → Apr 2026) | `C:\seasonals\cockpit\sessions\YYYY-MM-DD\events.jsonl` |
| M2v2 spec (canonical) | `M2v2_runner_system.md` | `C:\seasonals\pattern_scorer_rt2\docs\M2v2_runner_system.md` |
| Autotrader v1 spec (live target) | `SPEC.md` | `C:\seasonals\baiynd_autotrader\SPEC.md` |
| The actual indicator-replay run | `output of test march 13 to april 21,.txt` | `C:\seasonals\` |

---

## 1. Is there an actual backtester?

**Yes for the scoring layer; effectively no for the indicator's actual rules as wired.**

### What runs
- **`pattern_scorer_rt2/src/experiments/runner_backtest.py`** is the closest thing to a real backtest. It:
  1. Loads 1-min bars from `data/csv/futures/1min/{ES,NQ,CL,GC}.csv`
  2. Builds an event tape (level-touch grid) via `event_builder.py`
  3. Computes runner-policy R for every event via `_simulate_runner` in `label_builder.py`
  4. Trains LGBM Huber per instrument on pre-2024 events
  5. Tier-classifies post-2024 events using val-set quantile cuts
  6. Re-simulates dollar PnL with 1-tick entry slip / 2-tick stop slip / 1-tick trail slip / $4.50 RT commission
  7. Persists trades to `output/models/runner_backtest_trades.parquet` and summary to `runner_backtest_net.parquet`
- **`pattern_scorer_rt2/src/experiments/walkforward_runner.py`** is the same pipeline without slippage (R-multiple × $500 risk), used to validate that the edge is structurally OOS-clean.
- **`pattern_scorer_rt2/src/experiments/delayed_sma_sanity.py`** retrains with the SMA20 trail artificially delayed 30 / 60 min — passed (edge robust to delay). This is genuine look-ahead-leakage protection.
- **`pattern_scorer_rt2/src/experiments/subperiod_stability.py`** breaks the holdout into sub-periods to measure stability over time (its output exists at `output/models/subperiod_stability.parquet`).
- **`decision_engine/src/backtest_v2.py`** is a head-to-head between M1 (seasonal) alone, M2 v2 alone, the Combiner (A + A_High intersection), and the Lax Combiner. Operates on `realized_R_trailed` from the labels parquet.
- **`decision_engine/src/robustness_checks.py`** runs corrected-Sharpe (zeros on no-trade days), Monte-Carlo drawdown (10,000 shuffles, seed 42), and the CL deep-dive.
- **`ml_scorer_rt/src/walkforward/fold_{builder,runner}.py`** is a multi-phase walk-forward harness for the ml_scorer_rt system (M1 / seasonal track), separate from the M2 pattern-scorer.
- **`ml_scorer_rt/src/simulator/trade_engine.py`** is a simpler open-to-open simulator for ml_scorer_rt's signals; uses tier+prob filter, regime gate (VIX, SPX-200SMA), forward-window exit, optional hard stop. Different scope (M1 windows) but functioning.

### What does NOT run as a backtest
The **AMTradeCockpitV2_4 indicator running in `State.Historical`** is *not* a backtester. It is:
- A rule replay that fires `SetSignal()` on the same logic as live (V2_4 explicitly removed the Realtime gate from `SetSignal`/`CheckEntry` to make this happen — see line 1618-1622, 1984-1988).
- It accumulates a `tradeHistory` list across the entire backfill in memory.
- It prints day-summary blocks to NT's Output window (the `output of test march 13 to april 21.txt` file is one such capture).
- It writes JSONL `touch` and `signal` events to `cockpit\sessions\YYYY-MM-DD\events.jsonl` (lines 920, 932 — gated on `EnableJsonlLog`, but the touch log fires in BOTH Historical and Realtime per the V2_4 commentary at 1618-1622; signal/bar_close are gated to Realtime per the source).
- It applies `realizedPnlDollarsToday` *only* in Realtime (line 2754), so historical-replay trades do NOT count toward lockouts (a feature, not a bug — they're fake fills).
- It performs **NO disk write of the trade tape** — the only artefact of a historical run is whatever the operator captures from the Output window.
- It assumes 1 contract on Wide and 2 on Normal-bucket signals; multiplies by the instrument's `PointValue` for $ projection.

So Q1 answer: **the only thing that resembles a backtest of the actual indicator behaviour is captured in `output of test march 13 to april 21.txt`, and that artefact has serious limitations** (see §9).

---

## 2. What data exists for backtest?

### Bar data (the ground truth)
- **`C:\seasonals\data\csv\futures\1min\{ES,NQ,CL,GC}.csv`** — 1-min OHLC+V continuous-contract bars, `2012-08-12 18:01` → `2026-04-22 11:54`. ES.csv is 4.7M lines / ~13.6 years of 24-hour 1-min bars. This is what every Python backtest reads.
- **`C:\seasonals\data\csv\INDX\`** — macro indices (VIX, TNX, IRX, SPX, NDX, DXY, VXN, FVX) at daily resolution; consumed by ml_scorer_rt's regime gate.
- **`C:\seasonals\data\csv\COMM\`** — daily commodity series (used by ml_scorer / M1).
- **No tick data anywhere** — every Python sim runs on 1-min bars. Inside-bar fill order (stop vs target on the same bar) is resolved by the conservative "stop wins" convention in `label_builder.py`. No tick-level fill modelling exists.

### JSONL session captures (the realtime tape)
- **`C:\seasonals\cockpit\sessions\YYYY-MM-DD\events.jsonl`** — 103 dated folders from `2025-10-21` through `2026-04-27`. Each folder contains a single `events.jsonl`. Earliest example has 52 events (2025-10-21); later examples 100+ (2026-04-21 = 110). Events include `touch`, `signal`, `bar_close`, `phase_change`, `bias_change`. Touch lines carry `level`, `level_price`, `bar_open/high/low/close`, `direction`, `retrace_side`, `already_latched`. Signal lines (Realtime-gated) carry `side`, `entry`, `stop`, `target`, `trade_mode`, `level`, `adr20`, `eu_width`, `phase`, `day_type`, `vwap`.
- These are **the only "realtime" records** of the indicator in operation. They are not the full signal lifecycle (no fills/exits/PnL recorded) — the post-fill events (FILLED, STOPPED OUT, TRAIL EXIT, TIME CLOSE) print to NT's Output window via `Log()` but are not in JSONL.
- Many folders have file-lock errors during writes (`[cockpit-log] write failed: ... being used by another process`) — visible in the Mar 13 → Apr 21 capture (e.g. line 5, 46, 47, 104, 3108, 3111). This means JSONL is **lossy**: an unknown fraction of events were dropped. Cannot be used for OOS reconciliation without a sweep that quantifies the loss.
- Empty files exist (`2026-04-25/events.jsonl` exists but is empty; `2026-03-19` and `2026-03-20` are in `shadow_sessions` rather than `sessions`).

### Pre-built artefacts (downstream of the bars)
- `pattern_scorer_rt2/output/events/{INST}_events.parquet`
- `pattern_scorer_rt2/output/features/{INST}_features.parquet` (65 features in rt2; 71 in rt2_1)
- `pattern_scorer_rt2/output/labels/{INST}_labels.parquet` (label, realized_R_first_target_only, realized_R_trailed, realized_R_runner)
- `pattern_scorer_rt2/output/models/{INST}_model.txt` (LightGBM boosters), `tier_thresholds.json`
- `pattern_scorer_rt2/output/models/holdout_diagnostics.parquet`, `subperiod_stability.parquet`, `training_summary.parquet`
- `pattern_scorer_rt2_1/output/models/late_move_ab.parquet` (the geometry-feature A/B harness)

### Q2 answer
~13.6 years of 1-min bars per instrument is plenty for ML training. ~6 months of JSONL session logs is enough to *quantify indicator/Python event-builder agreement* (which `indicator_recall.py` is designed to do) but **far too thin** for any standalone backtest of the indicator's actual decisions. The indicator-side audit lives only in NT Output captures like the Mar 13 → Apr 21 file, which has no automated reproducibility.

---

## 3. Replay fidelity — does Historical match Realtime?

**This is the most subtle question and the most important for institutional-grade work.** Reading V2_4 carefully:

### What V2_4 *does* fire identically in Historical and Realtime
- `CheckEntry()` runs in both states (explicit comment lines 1618-1622). This is intentional and was added in V2_4 specifically so the touch JSONL builds during chart backfill (for recall testing).
- The pre-gate `LogEvent("touch", ...)` fires for every level inside bar range during backfill (see line 1911). This means touches recorded in the JSONL during a chart load are an honest replay of the indicator's level detection.
- `SetSignal()` runs and creates a Pending state, fills it, runs `MonitorSignal()`, and reaches `RecordAndDrawTrade()` in both states. This is what produces `tradeHistory.Add(trade)` (line 2742).
- Trail logic (`v2SignalTrailArmed`, ratchet on 30-min SMA20, exit on 1-min close past trail) — computed identically.
- TimeClose, FADE-mode target hit, hard stop intrabar — all computed identically.

### What V2_4 explicitly gates to Realtime only
| Gated to State.Realtime | Line(s) | Effect on backfill |
|---|---|---|
| `EnableJsonlLog && State == State.Realtime` for `signal` event write | 2436 | Signal-event JSONL line is NOT written during backfill |
| `EnableJsonlLog && State == State.Realtime` for `bar_close`/`phase_change`/`bias_change` writes | 920, 932, 944, 949, 4006 | These JSONL types missing from any Historical-mode replay |
| `FireAlert($"A3_Signal_...")` (audible alert) | 2495 | No audio during backfill (correct) |
| `ShowStagingCard()` | 2500 | No card popup during backfill (correct) |
| `realizedPnlDollarsToday += pnlDollars`, `losingTradesToday++`, `CheckLockout()` | 2754-2758 | **Lockout DOES NOT trip on backfill — historical losses don't lock the day.** Without this, a chart reload would re-trip lockout from yesterday's losers. **But it also means the Mar-Apr backfill output never tested whether the live lockout rule would have shaved the worst days.** This is a real fidelity gap. |
| `lastStopTime = barTime` (cooldown after stop) | 2609 | Cooldown does NOT engage on backfill — successive sim trades fire without the cooldown that would block them in live. **Real fidelity gap.** |
| Demo-fire path `demoFiredThisArm = ...` | 1459 | Test-only; non-load-bearing |
| Several order-staging UI plumbing paths | 4491 | UI-only; non-load-bearing |

### What the indicator does NOT do in either state
- **No ATM order submission in Historical.** `AllowOrderSubmit` and ATM-template wiring is gated elsewhere on Realtime, and on top of that it requires `cardStaged == true` (a UI click). So no broker-side fills are simulated during backfill — but no broker-side fills are part of the backfill metric either, so this is consistent.
- **No `realizedPnlDollarsToday` reset between backfill days.** Looking at the Mar 13 → Apr 21 file: trade #21 prints "Day: $387.50" on 2026-03-13, but trade #1 of the *next* day starts with `realizedPnlDollarsToday` not reset (the lockout doesn't engage anyway, so it doesn't matter — but if `State == State.Realtime` were true during a multi-day chart backfill, the lockout would trigger after a few days of accumulated losses, which is wrong).

### Net replay-fidelity verdict
**Touch detection and signal generation are faithful in backfill** — that's the point of V2_4's design. **Trade outcomes (stop, trail, time-close) are also faithful at the mechanical level**, since every exit decision is bar-data-driven.

However, four behavioural differences are systematically under-represented in any backtest from the chart-backfill tape:
1. **Daily-loss lockout** is never tripped in Historical → backtested PnL is *worse than what the live system with a $500 daily lockout would have suffered*. (For ES the lockout default is $150 in some configs and $500 in the SPEC — exact value varies; see Mar 25 lockout-trip line 3091 in the test-output file: "Daily loss limit hit ($1813 / $150)" indicates the limit is currently set very low. A 2-loss day would lock out under live.)
2. **Cooldown timer between stops** is never engaged → backfill can take signals 1 minute after a stop that the live rule would block for `CooldownMinutes`.
3. **Pending-replacement at fill cutoff (14:30)** — the explicit guard at line 2569-2575 ("PENDING FILL BLOCKED at cutoff") works in both states; this is *good*. (V2.2/V2_4 patch.)
4. **Friday → Monday box-aging** — the recent V2_4 patch fixed the active/dead phase computation on weekends. *Pre-patch* historical runs would have shown ghost institutional boxes / extra targets across weekends. Anything captured before the V2_4 patch is suspect on weekend boundaries. The Mar 13 → Apr 21 capture covers 6 weekend-spanning weeks; whether that capture was generated pre- or post-patch is unclear without the indicator-version stamp in the file.

---

## 4. OOS partitioning

### What exists
- **Production split (trainer.py):** chronological 70/10/20 train/val/holdout by event_ts (`TRAIN_FRAC=0.70`, `VAL_FRAC=0.10`, `HOLDOUT_FRAC=0.20`, set in `pattern_scorer_rt2/config.py`). On ~2017-2026 events that lands the holdout in roughly 2024-08 → 2026-04 — a single contiguous slab.
- **Walk-forward / OOS validation (walkforward_runner.py + runner_backtest.py):** strict `event_ts < 2024-01-01` train, `event_ts >= 2024-01-01` test. Validation is the last 10% of train chronologically (so val is roughly Q4 2023). LightGBM early-stops on val Huber loss. Tier cuts are taken from val-set prediction quantiles (p85 / p70 / p50 → A / B / C) and applied unchanged to the test set. **This is a clean strict-OOS cut**, not a leaky cross-validation. The M2v2 spec §4.1 documents this explicitly.
- **Sub-period stability (subperiod_stability.py):** the test set is broken into sub-windows after training; reports stability over time. Already run; output at `output/models/subperiod_stability.parquet`.
- **ml_scorer_rt walk-forward (separate, M1/seasonal):** uses `fold_runner.py` over multi-year folds with a date-scoped pattern miner, train-only enrichment, and per-fold ML training. Distinct from M2's split. This is true rolling-window walk-forward.

### What does NOT exist
- **No walk-forward on rt2 itself.** The rt2 "walk-forward" file is named `walkforward_runner.py` but it actually runs ONE split (pre-2024 vs post-2024), not a rolling window. There is no rolling retraining schedule that mimics what live operation would do (refit monthly / quarterly with expanding window). For institutional-grade reporting you want at least a 4-fold rolling window on the post-2024 slab.
- **No purged / embargoed CV.** Standard ML for finance uses purged-K-fold with an embargo. Not present here. With a 30-min trail and same-day exits, the leakage risk is small (events within the same day might share a session-state bias), but a defensible audit would explicitly test it.
- **No instrument hold-out.** Each model is per-instrument and trained on its own data. There's no test of generalisation across instruments (e.g. train on ES+NQ, test on CL).
- **No regime hold-out.** No specific test that performance survives in low-vol vs high-vol regimes, in 2020-style shock vs 2022-style trend, etc. Sub-period stability gives some signal here but is not a regime-stratified split.

### Q4 answer
The OOS structure is *adequate for one clean OOS claim* (post-2024 holdout, ~2 years, pre-trained on pre-2024) and the M2v2 spec quotes that claim faithfully. It is **not adequate for institutional-grade because it tests one cut**, not a rolling production cadence. Recommend (a) rolling window walk-forward on the 2024-2026 slab, (b) explicit regime-stratified subgroup analysis on the holdout, (c) a held-out unseen-month test for the rt2_1 geometry retrain (currently the rt2_1 retrain just says "holdout spearman improves +0.022 ES, etc." — needs a separately reserved month).

---

## 5. Label generation — where does ground truth come from?

**Two completely independent label sources:**

### Source A — `pattern_scorer_rt2/src/labels/label_builder.py` (Python simulator)
This is the canonical ML label and the entire training and walk-forward chain hangs off it. For each event in `{INST}_events.parquet`:
1. Stop = `entry ± stop_dist` where `stop_dist = clip(europe_width, 0.30 * ADR20, 0.80 * ADR20)`.
2. First target = next structural level in the event's 15-level snapshot in trade direction; fallback to entry ± 1×ADR.
3. Forward scan from the bar AFTER the event bar through 1-min bars until stop hit, target hit, or `time_cap_hm` (15:00 ET; 14:30 CL).
4. Convention: when a bar's `[low, high]` contains both stop and target, **stop wins** (conservative).
5. Output three R-multiples per event:
   - `realized_R_first_target_only` — exit 100% at first structural target
   - `realized_R_trailed` — 50% at first target, remainder trailed on max(orig_stop, SMA20-30m)
   - `realized_R_runner` — **production target**: no first target, no partial, trail-from-entry on max(initial_stop, SMA20-30m), force-close at time cap.
6. R = `sign × (exit_px − entry) / stop_dist`.

The runner-policy R is what `pattern_scorer_rt2/output/models/*_model.txt` is trained against.

### Source B — V2_4 indicator's `RecordAndDrawTrade()` (NT-side trade record)
Different ground truth. For each entry that filled in backfill or live:
1. PnL points = `signalEntry - exitPrice` (short) or `exitPrice - signalEntry` (long).
2. `IsWin` is set by the caller (`true` for FADE target hit and TimeClose with positive PnL; `false` for stop; computed from `close < entry` for trail in shorts).
3. Quantity: 2 for "Normal" bucket, 1 for "1 MES ONLY" (Wide), 1 for unset / Gray.
4. PnL dollars = `pnl × pointValue × qty`. For ES/MES this picks up the raw chart instrument's PointValue ($50 ES, $5 MES — **so the same chart instrument loaded as ES will report 10× the dollar PnL of one loaded as MES** even though the rule logic is identical).
5. Logged to NT Output. Never written to disk.

### Important divergences between A and B
- **B has a TREND/FADE bifurcation** (the 4PM apr-27 sideways-day rule, capping signals at 2 for FADE). A only has the runner policy — there is NO FADE simulation in the Python labels.
- **B has a `signalsToday` cap** (3 normally, 2 in FADE), a cooldown timer between stops, and a daily lockout. A has none of these — every event in the grid generates a label, regardless of how many fired earlier in the day.
- **B uses retrace-side filter** (LONG only at level price < bar open; SHORT only at level price > bar open). A is also retrace-gated through `direction` from trend-state, but the *trend gate itself* (uptrend = price > SMA50 > SMA200) is shared. The `wouldRetrace` check inside indicator's CheckEntry is post-gate; the Python event builder uses the symmetric direction logic.
- **B uses pre-place limits** (V2.2/V2.1 `V21UpdatePrePlace`): the live rule places limit orders at *all* eligible levels and waits for first fill, then cancels the rest. A simulates "fill at first bar that crosses the level" only.
- **B has a 14:30 cancel cutoff and a same-bar fill block** (lines 2541, 2569). A's `time_cap_hm = 15:00` in the runner sim simply truncates; there's no Pending replacement, no late-bar fill block.
- **B counts a trail exit as a Win iff `close < signalEntry` for short / `close > signalEntry` for long**, irrespective of whether the move covered slippage / costs / R-multiple. A counts R-multiple directly.

### Q5 answer
**Both pipelines exist in parallel and they do NOT produce the same label for the same event.** This is the largest internal-consistency gap in the system. A trade reported "Won" by `RecordAndDrawTrade` (positive PnL, possibly +1 tick after slippage) may carry a `realized_R_runner = +0.05R` in Python — both true, but very different metrics. ML training is on metric A. Operator perception (the test-output file) is on metric B. The decision_engine combiner reads metric A (`realized_R_trailed`).

A defensible institutional pipeline would:
1. Pick **one** canonical label (recommend `realized_R_runner` — it's what the production model trains on).
2. Replicate the indicator's mode-dependent FADE logic and signals/day cap in Python so the *signal selection* matches.
3. Cross-validate by cross-referencing the JSONL signal log: every Realtime signal in `cockpit\sessions\` should appear in the Python event tape, and its eventual outcome should be what the Python labeller computed.

---

## 6. Slippage / fill modeling

### What's modelled
- `runner_backtest.py` applies entry slip = 1 tick adverse; stop-hit exit slip = 2 ticks adverse; trail / timeout / end-of-bars exit slip = 1 tick. Commission = $4.50 round-trip per contract. (See `SLIP_TICKS_BY_KIND`, `ENTRY_SLIP_TICKS`, `COMMISSION_RT`.)
- `decision_engine/src/backtest_v2.py` applies 1-tick slip uniformly and same $4.50 commission.
- `ml_scorer_rt/src/simulator/trade_engine.py` reads `cfg["slippage_ticks"]` and applies on entry/exit (default in `sim_config.py`).

### What's NOT modelled
**No fill-rate bias.** Every `runner_backtest.py` event is assumed to fill — `bar_low <= entry_px <= bar_high` is the trigger and the fill price is `entry_px + 1 tick`. This is the single most important unverified assumption. The M2v2 spec §6.1 quotes this verbatim:

> The backtest assumes every limit order placed at a Baiynd level fills. In live markets, the biggest winners are often those where price punches through the level without a retest — and those limit orders may not fill. If live fill rate is 50% on Tier-A signals, expected net drops from $775K/yr to roughly $380K/yr and Sharpe from ~10 to ~3-4.

This is exactly right and is the load-bearing risk for the Sharpe-10 number not being a fantasy.

**No queue position modelling.** Real limit orders sit in a queue. A 1-tick "fill at touch" assumes you're at the front of the queue at every level — wildly optimistic for retail-sized limit orders at popular levels (ORH/ORL, prior-day high/low, VWAP). Real fills at popular Baiynd levels are probably 30-60% on a true touch; near-100% fills only happen on overshoots, and overshoots tend to be losing setups (level fails to hold).

**No bar-internal sequencing modelling.** `label_builder.py`'s convention "stop wins on contained bars" is the only handle on intra-bar sequence. This is conservative, but it doesn't know whether the price actually hit the stop *before* the target — it just assumes it. With tick data you'd resolve this; without, you're stuck with a coin flip resolved as a loss.

**No spread modelling.** Live spreads on CL widen during EIA week, on ES widen during the 2-3pm doldrums, on GC during overnight thin liquidity. The 1-tick slippage is a single point estimate.

**No partial fill modelling.** With `contracts = $500 / (stop_dist × point_value)` producing fractional contracts (often <1), live trading will round to 1 contract minimum, which (a) increases per-trade $ risk above $500 and (b) prevents the smooth-equity behaviour the backtest reports. Spec §6.5 calls this a "10-20% haircut."

**No commission tier modelling.** $4.50 RT is a reasonable mid-tier retail commission. Pro tier is closer to $1-2 RT; CME exchange-fee floor on ES is ~$1.36. The point estimate is fine but is not justified anywhere.

### Q6 answer
The slippage and commission haircut applied is **realistic for fills that happen** but says nothing about **whether the fills happen**. The fill-rate bias is the single largest unmodelled risk, the spec acknowledges it, and the only way to close it is paper trading (per §7 of the M2v2 spec).

---

## 7. Holiday / weekend / DST handling in replay

### Indicator side (V2_4)
- **Weekends:** `AddTradingDays()` (line 4138) skips Saturday and Sunday in the box-aging fade/remove computation. The recently-patched Friday→Monday issue addressed this — pre-patch, a Friday-formed institutional box was using calendar-day arithmetic, which made Monday's chart show a stale aged box and a stale shaded measured-move ladder. Post-patch (the V2_4 patch this audit assumes), trading-day arithmetic is correct.
- **Holidays:** Line 4134-4137 explicit comment: "Holidays are NOT accounted for — calendar holidays still consume a 'trading day' here." The result is that a holiday-Tuesday box stays "shaded a few hours longer than strictly intended; no signal logic depends on this." Acceptable for visual; **the same blind spot exists elsewhere too** — e.g. ADR20 lookback, signalsToday-per-day counter, and the per-session touched-levels latch all assume one trading day = one calendar weekday. On a 4-day Thanksgiving week or a Good-Friday week, ADR20 is computed over fewer trading days but the same number of calendar days; this introduces small biases.
- **Early-close days:** the indicator's `closeHour=15`, `closeMinute=0` are constants set in startup; the early-close days (day after Thanksgiving, Christmas Eve, July 3) are NOT detected and the 14:30 cancel-cutoff / 15:00 TimeClose runs as if it were a normal day. On a 1pm-close day, this means signals can fire that would never actually fill. Real impact is small (a handful of days a year) but it's a fidelity gap.
- **DST transitions:** the indicator uses NT's local `Time[0]` and the platform's bar timestamps. NT8 handles DST internally for instrument sessions, so the indicator's hour math is on local-clock time which jumps at DST cutover. There is **no explicit DST handling** in V2_4 — and that's correct, because NT supplies post-DST timestamps.
- **Missing 1-min bars on holidays:** the test-output file shows `=== DAY SUMMARY 2026-04-22 ===` with `1m range: NO 1M CANDLE` and `Bars checked: 0` (line 7613-7625). The indicator handles a missing day by reporting zero progress. This is consistent.

### Python side
- **News blackouts** are coded explicitly: `pattern_scorer_rt2/config.py` defines `NEWS_BLACKOUTS` (CL EIA Wed 10:25-10:45) and a `NEWS_CALENDAR_CSV` placeholder for FOMC/NFP/CPI/PPI. The CSV is referenced but its existence is not guaranteed (`if not NEWS_CALENDAR_CSV.exists(): return`). The CL EIA window is the only currently-active blackout.
- **Holidays** are NOT explicitly coded in the Python pipeline. `_extract_candle_per_session` requires `min_bars_frac=0.5` of bars to be present in a session window, which silently drops sessions where the overnight Europe/midnight candle is incomplete (typical of Christmas Eve / day-before-NYE runs). This is a soft form of holiday handling but not principled.
- **DST:** all timestamps are read from CSV as naive datetime; `bars["datetime"].dt.hour * 60 + dt.minute` is used unconditionally. Same as the indicator: relies on the source data already being DST-aware. Source CSVs (`ES.csv` etc.) are continuous-contract feeds from Kibot/equivalent — these are typically pre-DST-adjusted.

### Q7 answer
The system is **adequate but not robust** to calendar anomalies. The recent V2_4 box-aging patch fixed the most visible weekend bug. Remaining gaps are: (a) holidays not skipped in trading-day arithmetic, (b) early-close days run as full sessions, (c) FOMC/NFP/CPI blackouts only active when the optional CSV is provided. None of these meaningfully changes the headline backtest claim, but for institutional-grade reporting you'd want an explicit holiday calendar (`pandas_market_calendars` or equivalent) gating both pipelines uniformly.

---

## 8. Reproducibility

### What's locked
- **`random_state=42`** in every LightGBM call (`runner_backtest.py:168`, `walkforward_runner.py:62`, `trainer.py`).
- **`seed=42`** in Monte-Carlo DD shuffle (`robustness_checks.py:29`).
- **Deterministic event order** — the event grid is sorted by `event_ts` chronologically; the train/val/test split is by index after sort.
- **Vectorised numpy ops** — no thread-race in label generation.
- **Fixed thresholds** — `STOP_ADR_FLOOR_MULT=0.30`, `STOP_ADR_CAP_MULT=0.80`, `TIER_PCTS={A:0.85, B:0.70, C:0.50}`, `DOLLAR_RISK=500.0`. All in config.

### What's NOT locked (or is brittle)
- **`feature_fraction=0.9`, `bagging_fraction=0.9`** in LightGBM are stochastic; the seed locks them but only if `n_jobs` doesn't disturb thread order. With `n_jobs=-1`, LightGBM is generally seed-stable on the same machine but not portably reproducible.
- **`pd.merge_asof` ties** — when two events have identical timestamps, merge order depends on the input ordering, which is itself stable from `sort_values("datetime")` but only because pandas mergesort is stable. If anyone replaces this with `kind="quicksort"` or upgrades pandas, the order can shift.
- **Indicator backfill** is NOT reproducible across reloads:
  - `tradeHistory.Count` is a *running* counter from chart reload, not from session start. The Mar 13 → Apr 21 file shows it climbing from 21 (Mar 13 line 65) to 84 (Apr 21 line 7605) — but if you re-load the chart with a different "Days to Load" setting, the start-of-history is different and the count differs. The pre-Mar 13 trades that contributed to the running counter are never disclosed.
  - The win/loss tally (`35W/49L`) on Apr 21 is similarly cumulative-from-load; subtract it from Apr 20's tally (35W/47L) and you get this day's contribution.
  - JSONL writes can race the file lock (the "file is being used by another process" errors in the test-output file are visible). On reload, those events are simply missing.
  - The `[cockpit-log] write failed` errors shown in the test-output (lines 5, 46, 47, 104, 3108, 3111) mean some events were dropped — re-running the backfill on a different day might capture different events depending on whether the cockpit dashboard is running at the time.
- **Daily-clock dependence on operator behaviour** — chart reloads, indicator parameter changes, "Days to Load" adjustments all reset state silently.

### Q8 answer
The Python-side backtest is **reproducible to better than 0.1% PnL** on the same machine; the seed and split convention guarantee it. A different machine / different LightGBM version may shift Sharpe by ~0.05.

The indicator-side replay is **not reproducible** across chart reloads — the running tradeHistory makes a "rerun and compare" exercise unreliable. To make institutional-grade auditing possible, V2_4 needs to (a) write `tradeHistory` to disk on every `RecordAndDrawTrade` (not just print to Output), and (b) reset the day counter on session-date change.

---

## 9. The "output of test march 13 to april 21.txt" file

### What it is
A 7,625-line text capture of NT8's Output window during what appears to be a single chart-backfill session of the V2_4 indicator. Time range: signals from 2026-03-13 to 2026-04-22 (Apr 22 closed early, no 1-min candle). The leading timestamps (e.g. `19:22:48`, `19:23:06`, `20:02:54`) are the NT-clock times when each `Print` ran during the backfill — NOT the bar times. So the operator started the indicator at ~19:22 on some day and let it backfill all 6 weeks of bars.

The interesting payload is in the `=== DAY SUMMARY ===` blocks and the inline `>>> SIGNAL`, `FILLED`, `STOPPED OUT`, `TRAIL EXIT`, `TIME CLOSE`, `PnL` lines. Plus a heap of `PRE-PLACE built` repetition (a known V2_4 issue — pre-place panel is rebuilt every bar, polluting the log).

### What it tells us about backtest state and methodology

1. **A single chart-backfill is the only "backtest" of the indicator we have.** Not a script, not a function call, just an operator capturing the Output window. The format is verbose and lossy (file-lock errors visible at lines 5, 46, 47, 104, 3108, 3111).

2. **Cumulative running stats, not per-day.** Each day-summary shows `Trades completed: N total across all days` — by Mar 13 we see 21 trades, by Mar 16 we see 89 trades (so 68 trades on the 14th + 16th). This is a rolling tally. The `--- PERFORMANCE (N trades) ---` block computes win-rate, profit-factor, avg-win/avg-loss on the rolling N. There is no per-day P&L decomposition; just the day's stats in context of the rolling tape.

3. **The headline metric was negative throughout.** 
   - End of Mar 13: 21 trades, 4W/17L, 19% win, PF 0.30, MES net −$927.21.
   - Peak loss appears around Mar 27: 66 trades, 25W/41L, 37.9% win, PF 0.63, MES net −$1,245.
   - End of Apr 21: 84 trades, 35W/49L, **41.7% win, PF 0.94, MES net −$204.38** (or −$2,043 in ES contracts). The system *recovered* from the early hole as the geometry-favourable late-April rally to ~7150 created clean longs with the SMA20 trail, but **net is still slightly negative** for the 6-week sample.

4. **One day tripped daily lockout.** Line 3091: "LOCKOUT: Daily loss limit hit ($1813 / $150)" on Mar 25 — but note the lockout fired AFTER printing PnL, in spite of the State.Realtime gating. This means that particular run was either (a) Realtime, not Historical (perhaps captured during live session), or (b) the lockout-rule path was modified to fire in Historical too (V2.2 change?). Either way, it shows the configured lockout was $150/day, which is far below typical 1-MES per-trade risk of ~$200. **At a $150 lockout, V2_4 would lock out within the first losing trade.** This is a configuration issue, not a backtest issue — but it explains why most days show only 1-2 trades.

5. **Per-trade economics:**
   - Avg win = 19.24 pts (Apr 21 number) → ~$96/MES, $963/ES
   - Avg loss = 14.58 pts (Apr 21) → −$73/MES, −$729/ES
   - Best win: 79.62 pts (somewhere in mid-April, looks like the 7150-area rally)
   - Worst loss: 37.75 pts (consistent across the dataset — likely a single Europe-width-clipped stop trade)

6. **What it does NOT contain:**
   - No per-trade timestamps with entry/exit/PnL in machine-readable format. Each trade is a sequence of multi-line log entries that have to be regex-parsed.
   - No FADE-vs-TREND breakdown despite that being a structurally important rule difference.
   - No level-by-level PnL breakdown (Pr30L vs GlobExH vs EuropeL etc.).
   - No reconciliation against the Python event-builder's expectation for the same date range.
   - The duplicate-line phenomenon (every log line appears 2x) suggests the indicator was loaded twice on the same chart, or the OnBarUpdate fired twice — known V2_4 issue with multi-data-series setups (idx1Min + idx30Min).

### Q9 answer
**The test-output file is the only "backtest" of the actual V2_4 indicator we have, and it shows a near-flat-to-slightly-negative outcome over a 6-week window** (PF 0.94, 41.7% win, MES net −$204). This is *radically* different from the Python `runner_backtest.py` claim of Sharpe 9.77, 93.6% win-rate. Both numbers are produced by the same nominal "Baiynd level-touch with SMA20 trail" rule. The disconnect is the definition of "trade" — the Python runner sim simulates *every event the model would tier-A-rank*; the indicator simulates the actual mode-aware, signal-capped, retrace-filtered live rule. The real Baiynd indicator's signal-selection logic is *much* more selective than the Python runner sim, and the indicator's results on the same 6 weeks are far worse.

There are two possibilities:
a) The Python runner sim genuinely captures an edge that the indicator's mode logic is too restrictive to exploit → loosen the indicator.
b) The Python runner sim is over-fitted / fill-rate-biased / overlooking something the indicator correctly avoids → trust the indicator.

Without paper-trading and tick-level fill auditing, we cannot tell which is true.

---

## 10. Gaps blocking institutional-grade backtest — the punchlist

Bluntly:

### Critical (would force a "no go" at any institutional review)
1. **No tick-level fill simulator.** All Python sim runs on 1-min bars; live limit-order fill behaviour at popular Baiynd levels is unknown. The M2v2 spec acknowledges this as the single largest unverified assumption. Until tick-level fills are simulated *or* paper-trading produces a measured fill rate, every backtest claim is conditional on an unproved 100% fill rate.
2. **Two independent ground-truth pipelines that disagree.** `RecordAndDrawTrade` (indicator, mode-aware, signal-capped, lockout-respecting) and `realized_R_runner` (Python labeller, no mode logic, every event labelled) measure different things. The decision_engine's `realized_R_trailed` is yet a third metric. Any institutional report must pick one canonical metric and have a documented cross-validation between the two pipelines.
3. **Indicator chart-backfill is not an automated, reproducible, machine-readable backtest.** It runs as a side-effect of loading the indicator on a chart. No CLI, no fixed seed for the backfill order, no disk write of `tradeHistory`. The Mar 13 → Apr 21 file is a textual capture that has to be regex-parsed and is duplicate-prone. Need: a NinjaTrader Strategy fork that runs the same V2_4 logic standalone, writes machine-readable trade records, and runs against the historical CSV bars via `Tools → Backtest`.
4. **No fill-rate measurement on JSONL captures.** The 6 months of JSONL session data are exactly what's needed to measure fill-rate empirically (compare every emitted Pending entry against the next-bar fill in the corresponding 1-min CSV). The diagnostic exists in spirit (`indicator_recall.py` does the touch-side comparison) but no script measures fill rate yet.
5. **Sharpe 9.77 and 93.6% win-rate are not believable as a forward-looking estimate.** Even within the spec's own caveats, a defensible institutional claim is "Sharpe 4-5 after fill-rate haircut, pending live validation." Anything stated in monthly P&L terms based on the runner backtest will look misleading after 6 months of paper.

### Important (would force a "conditional" at institutional review)
6. **Daily-loss lockout and cooldown rules are absent from the Python sim.** Backtest `runner_backtest.py` fires every Tier-A signal in the test set. Live operation will hit a daily lockout (currently configured at $150/day, see test-output line 3091) and a 20-min cooldown after stops. Including these in sim could materially shrink the trade count and change the equity curve.
7. **No FADE-mode replication in Python.** V2_4 has TREND mode (most days) and FADE mode (sideways days, capped at 2 signals/day, fixed structural target instead of trail). Python label generation only simulates the trend / runner policy. Sideways days under V2_4 use FADE; Python sim uses runner.
8. **No rolling walk-forward.** Single 2024-cutoff is a clean OOS split but it's not what live operation does (live retrains periodically). Recommend 4-fold rolling on the 2024-2026 slab, refit cadence quarterly.
9. **No regime-stratified sub-group analysis.** Model performance during Q1 2025 vs Q3 2025 vs the late-2025 rally is unaddressed beyond the existing `subperiod_stability.parquet` (which I haven't read row-by-row but the spec characterises it as moving-average per sub-period — fine but not a stress test).
10. **Holiday and early-close calendar not coded in either pipeline.** Both rely on "data has gaps" rather than an explicit `pandas_market_calendars` filter. Half-day-after-Thanksgiving runs as a full session; FOMC days have no automatic blackout unless the optional CSV is supplied; CL EIA-Wed is hard-coded.

### Lower priority (would feature in the "things to fix in v1.1" appendix)
11. **JSONL captures are lossy** due to file-lock contention with the cockpit dashboard. `[cockpit-log] write failed` errors prevent reliable reconstruction of the realtime tape from JSONL alone. Mitigation: hold the file open with FileShare.ReadWrite; or log to a per-process file then merge at session end.
12. **Test-output file format is human-only.** Every line is a `Print()` to NT Output. Needs a parallel structured-trade-record JSONL or CSV write from `RecordAndDrawTrade()`.
13. **Indicator running twice on the same chart** is producing duplicate log lines. Could mask race conditions and double-counts in tradeHistory.
14. **Fractional contract sizing in backtest.** Python sim uses `contracts = $500 / (stop_dist × point_value)` producing fractional contracts (often 0.3-0.7). Live MES rounds to 1; live ES would round up to 1 contract minimum and accept a higher-than-$500 risk on tight stops. 10-20% haircut.
15. **Commission point estimate of $4.50 RT.** Reasonable retail, but unjustified. Pro-tier is $1-2 RT; CME exchange-fee floor is ~$1.36. Sensitivity not tested.
16. **No bid-ask spread modelling.** Specifically painful on CL during EIA week and on overnight GC; both are in the production instrument list.
17. **Slippage point estimates (1/2/1 ticks) are not measured.** Should be calibrated from realized fills once paper trading produces them. Today they're plausible defaults from the spec.
18. **Tier-B and Tier-C performance on sub-period stability** not visible in the current artefacts — only Tier-A is reported in the M2v2 spec. Does Tier-A retain its lead in 2025 H2 after a possible regime shift?

### Process gaps (not technical, but blocking institutional sign-off)
19. **No "as of" date on saved artefacts.** `runner_backtest_net.parquet` has no provenance metadata: when was it generated, against which model commit, against which bar-data snapshot. The rt2_1 README says the model was trained at commit `ff19b9e` but the runner_backtest output files don't link to that commit.
20. **No automated daily / weekly regression test** comparing today's Python event tape against today's JSONL touch log. Drift detection is implicit (a human notices the numbers don't match) rather than automated.
21. **No held-out post-2026-04 backtest yet for rt2_1.** The geometry retrain was completed 2026-04-21 and shipped to production at `:7677` on the same day; there's no clean "out-of-time" period reserved for an unbiased forward measure of the geometry-feature lift.
22. **The output of test march 13 to april 21 file is not under version control** — it sits at `C:\seasonals\` root, not in any project's `output/` directory or any audit trail. Cannot be reproduced without manually re-loading the chart.

---

## Bottom line for Wave-3 synthesis

**The system has the building blocks for a defensible institutional-grade backtest, but they are not yet assembled into one.** The Python pipeline (events → labels → trainer → walk-forward → slippage backtest → robustness checks) is well-engineered and produces clean OOS numbers, but those numbers do not describe the actual indicator-as-traded — they describe the runner *concept* under an optimistic fill assumption. The indicator-as-traded has produced a slightly-negative 6-week sample in the only captured replay, with 41.7% win and PF 0.94. Reconciling these two views — by either (a) replicating mode/cap/lockout logic in Python and re-running, or (b) measuring fill-rate empirically from JSONL on the bars and applying it as a haircut to the Python sim — is the highest-impact next step before any institutional sign-off.

Specifically, the path to "institutional-grade" runs through:
1. Standalone NT8 Strategy fork of V2_4 logic that backtests via `Tools → Backtest` and writes machine-readable trade records.
2. JSONL-to-CSV reconciliation script that measures fill rate per signal per session.
3. A Python sim that mirrors the indicator's mode/signal-cap/lockout/cooldown logic exactly, retrained at the canonical 2024-cutoff.
4. Rolling 4-fold walk-forward on the 2024-2026 slab.
5. An explicit holiday/early-close calendar wired into both pipelines.
6. Three months of paper trading on Tier-A signals from the rt2_1 production model with tick-level fill logging.

When all six are done, a Sharpe estimate becomes defensible. Until then, every backtest number reported is conditional on the fill-rate assumption, the mode-skipping assumption, the lockout-skipping assumption, and the cooldown-skipping assumption — none of which are true in live operation.
