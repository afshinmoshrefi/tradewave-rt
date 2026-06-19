# Improvement Roadmap — Baiynd AutoTrader Stack
## Master Action Plan, Sequenced and Prioritized

**Author:** Final Synthesis Writer (Agent 22 of 22)
**Date:** 2026-04-27
**Companion documents:** `strategy_synthesis.md` (the framing), `am_open_questions.md` (the AM clarifications queue), `wave3_synthesis/manual_playbook.md` (Afshin's daily playbook).

---

## 1. Goals and Success Criteria

Two distinct end-states:

### Goal A — A beginner-friendly indicator that lets Afshin trade AM's method manually without doubt.

This is the immediate-term objective. The indicator must:
- Display the body-stack diagnostic clearly (single GO/WAIT/STOP imperative verdict).
- Show MOC state, 200-SMA slope, and signal budget in a single panel without ambiguity.
- Fire signals on AM's actual entry patterns (Pattern A and Pattern B) with the correct stop sizing and target ladder.
- Provide unambiguous staging cards that distinguish ticket-logged from ticket-submitted.
- Suppress beginner traps: VWAP-as-permission labels, demo-mode tagging, signal-cap counter, no-fire banners on Pre-Place panels during NO FIRE days.

**Success criterion:** Afshin can run sim for 30 days with the playbook, recognize valid setups, and either take them via the indicator's signals or take them manually with full confidence about the rules. No "did I miss a setup?" doubt at session end.

### Goal B — An institutional-grade autonomous stack: indicator → ML scorer → OOS-validated backtest → NT8 execution.

This is the longer-term objective. The system must:
- Generate signals consistent with AM's method (target candidate count: 60-90 per 6-month period across ES/NQ).
- Score signals through an ML pipeline trained on the correct exit doctrine (Fibonacci runner, not SMA20 trail) and a feature set that includes AM's stated context (1:30 PM candle, pivots, slope magnitude, body-stack node count, news-candle wicks).
- Produce defensible OOS backtest numbers: Sharpe 2.0-3.5, Profit Factor 2.5-4.0, Win Rate 45-60%, Max DD 5-12% of account — anchored to AM's documented profile.
- Submit orders autonomously via NT8 with state persistence, position-state reconciliation, watchdog monitoring, and a five-layer kill-switch stack.
- Pass the sim-to-live promotion gates before any real money goes in.

**Success criterion:** After 3 months of paper trading on the autonomous stack with tick-level fill logging, the realized fill-rate-adjusted Sharpe lands in the 2.0-3.5 range and the Profit Factor in the 2.5-4.0 range. All five kill-switch layers have been tested individually. Live promotion is a single decision gate, not a systems-engineering project.

---

## 2. The Master Punchlist

Every action item from every Wave 3 report, organized as a single ranked list. Format: ID / Title / Source-report / Priority / Effort / Dependencies / Success Criterion.

**Priority key:**
- **P0:** Blocking the main goal. Ship in next 2 weeks.
- **P1:** Important for the second goal (institutional-grade). Next 1-2 months.
- **P2:** Worth doing for completeness. Next 2-4 months.
- **P3:** Nice-to-have polish. Defer to v1.1 or later.

**Effort key:** S (under 1 day), M (1-5 days), L (1-3 weeks), XL (1+ months).

### 2.1 Indicator Code — V2_4 Bug Fixes

| ID | Title | Source | Pri | Effort | Dependencies | Success criterion |
|----|-------|--------|-----|--------|--------------|-------------------|
| C-01 | Fix JSONL day-type vocabulary mismatch (emit `v2_day_type` alongside `day_type`) | gap_to_am §GAP9, jsonl_data §Q4 | P0 | S | None | FADE mode actually fires on sideways days; JSONL `v2_day_type` strings appear |
| C-02 | Wire MOC state into `effSignalCap` and qty selector | gap_to_am §GAP8 | P1 | S | C-01 | Gray = 1 MES (cap 1), Orange = 1 MES (cap 1), Green = 2 MES (cap 2-3) |
| C-03 | Pass anchor argument at every `V2ComputeStopDistance` call site | gap_to_am §GAP5, v24_audit §4 | P1 | M | None | Per-trigger stop distance reflects entry-trigger candle width; bigger-candle exception fires when anchor is contained |
| C-04 | Fix CL `rthOpenHour=9, rthOpenMinute=0` for CL instrument | gap_to_am §GAP10, v24_audit §9 | P1 | S | None | CL 9:00-9:29 setups visible to indicator; opening-range lock fires at 9:30 for CL |
| C-05 | Stop counting cancelled pendings against `signalsToday` budget; track `fillsToday` separately | gap_to_am §GAP19, v24_audit §10 | P2 | S | None | A cancelled pending does not consume a slot toward the 3-cap; afternoon setups remain eligible after morning misses |
| C-06 | Fix file-lock contention on JSONL writes (use `FileShare.ReadWrite` or per-process buffer with merge) | jsonl_data §Q9, backtest_infra §10.11 | P2 | S | None | No `[cockpit-log] write failed` errors in 6+ months of cockpit-side dashboard concurrent operation |
| C-07 | Fix indicator-running-twice double-execution (deduplicate `OnBarUpdate` in multi-data-series case) | backtest_infra §9.6, failure_modes §1.1 | P2 | M | None | Each Print line appears once in NT Output during backfill |
| C-08 | Add bounds check on volume cast (line 1232 `(long)Volumes[idx30Min][0]`) | failure_modes §1.3 | P3 | S | None | MOC overflow logged and capped; no negative volume values in MOC ratio |
| C-09 | Add VWAP spike filter for tick-error contamination | failure_modes §1.4 | P3 | S | None | VWAP doesn't drift permanently from a single corrupted bar |

### 2.2 Indicator Code — V2_4 Feature Additions

| ID | Title | Source | Pri | Effort | Dependencies | Success criterion |
|----|-------|--------|-----|--------|--------------|-------------------|
| C-10 | Wire Pattern B (`CheckPatternBEntry` driving the `LevelWatchState` lifecycle) | gap_to_am §GAP2, v24_audit §2 | P0 | L | None | LevelWatchState instances created per candidate level per session; `Armed` state transitions to `SetSignal` on breach-bar high cross; 43% of historical touches now eligible to fire |
| C-11 | Change body-stack from 4-node (A<B<C<D) to 3-node (B<C<D); retain A as context | gap_to_am §GAP3, transcript_apr-23 | P0 | S | AM-Q-01 (escalation A) | LongTrend day count expands by ~20-30% in 6-month corpus; V-shape recovery days correctly classified as trend |
| C-12 | Make FADE two-sided (counter-slope candidates at half-size) | gap_to_am §GAP4, transcript_apr-23 | P0 | S | AM-Q-02 (escalation B) | Sideways days with up-slope fire both bottom-long (full) and top-short (half); apr-23-style sessions produce 2 signals not 1 |
| C-13 | Replace SMA20 trail with level-to-level exit doctrine: scale-out at 100% Fib, runner to 150% (flat slope) or 200% (steep) | gap_to_am §GAP1, transcript_apr-24 | P0 | L | AM-Q-03 (slope threshold), C-11 | TREND mode exit no longer mechanical trail; right-tail runners realized; PF moves from 0.94 toward AM's 2.5+ range |
| C-14 | Add FADE target ladder: T1 = 4 AM close / pre-market H-L, T2 = pre-market opposite, T3 = prior-3:30 | gap_to_am §GAP6, transcript_apr-23 | P1 | M | C-01 | FADE entries have 3 target levels checked in priority order; silent-drop on PrInst-not-profitable removed |
| C-15 | Add 1:30 PM ET candle capture and tracking | gap_to_am §GAP11, transcript_mar-6 | P1 | S | AM-Q-04 (1:30 discipline) | `Pr130H/Pr130L` levels appear in candidate pool; drawn on chart with legend chip; touch events fire on 1:30 level visits |
| C-16 | Add multi-day master-candle tracking: prior-day-1, -2, -3 institutional candle H/L | gap_to_am §GAP13 | P2 | S | None | Apr-23-style 2-days-ago levels available as candidates (e.g. 7085 = 2-day-old prior 30-min low) |
| C-17 | Add news-candle wick auto-detection (volume > max(prior 9:30, prior 3:30)) | gap_to_am §GAP14, transcript_apr-24 | P2 | M | None | Outlier-volume bars register their wick as a level; level persists as long as it is highest-volume in recent days; visible on chart |
| C-18 | Add R4/S4 to pivots; wire `price > R3` as no-fresh-longs hard gate; `price > R2` as soft warning | gap_to_am §GAP12, transcript_apr-8 | P2 | M | None | LongTrend signals blocked when above R3; PP/R1/R2 in TREND candidate target pool |
| C-19 | Re-enable V1 failed-retest of 1-min RTH range (subsumed in C-10) | gap_to_am §GAP7 | P1 | (subsumed) | C-10 | 1-min open candle re-enters Pattern B state machine; setup class recovered |
| C-20 | Add 50% midpoint add-rule and convergence-add trigger | gap_to_am §GAP16, transcript_apr-24 | P2 | L | AM-Q-05 (add geometry) | Active TREND trade can fire a second entry on 50% midpoint pullback or VWAP-50-200 convergence; stop tightens to 50% line |
| C-21 | Add Friday full-size escalation when bodies don't overlap, MOC validated, above prior 3:30 close | transcript_apr-24 §7e | P2 | S | C-02 | `effSignalCap` and qty raise to 3 / 2 MES on Fridays meeting all three conditions |
| C-22 | Add volume-priority ranking for clustered levels (within X ticks) | gap_to_am §GAP18, transcript_apr-24 | P3 | M | None | Tie-break logic prefers highest-volume origin candle when multiple levels cluster within 5 ticks |
| C-23 | Add cautious-mode sizing/stop-widening (currently routes through TREND with no differentiation) | version_diff §added-but-unwired | P2 | M | None | Cautious-Long / Cautious-Short fire at half size with widened stops |

### 2.3 Indicator Code — UX Changes (from indicator_ux_critique.md)

| ID | Title | Source | Pri | Effort | Dependencies | Success criterion |
|----|-------|--------|-----|--------|--------------|-------------------|
| U-01 | Redesign verdict line to GO/WAIT/STOP imperative format with size and risk inline | ux §1.1 | P0 | M | None | Verdict starts with action verb; size, stop pts, target level visible in one block |
| U-02 | Rename STAGE button "CONFIRM" to "LOG + PLACE MANUALLY"; rename post-click "TICKET LOGGED" to "LOGGED — OPEN CHARTTRADER NOW (not auto-submitted)" | ux §4.2 | P0 | S | None | First-time user does not believe CONFIRM submits an order |
| U-03 | Add signal budget counter to Pre-Place panel ("Signals today: 1 of 3 used") | ux §8.4 | P0 | S | None | Beginner sees how many slots remaining before silent cap |
| U-04 | Label VWAP and AnchVWAP chart lines with "(permission only)" suffix | ux §8.2 | P0 | S | None | Beginner does not expect a VWAP touch to fire |
| U-05 | Add countdown timer to Staging Card (60s → 0:00) | ux §4.1 | P1 | S | None | Beginner sees how long they have to act |
| U-06 | Move legacy 30m SMA stack to Detail Level == Full | ux §1.3 | P1 | S | None | Two competing day-type displays no longer visible by default |
| U-07 | Add "INFORMATIONAL — Do not place" banner on Pre-Place panel when verdict is NO FIRE or WAIT | ux §8.1 | P1 | S | None | Beginner not confused by candidate prices on no-fire days |
| U-08 | Tag all demo-signal elements with "[DEMO]" prefix | ux §5.3 | P1 | S | None | Demo signal cannot be mistaken for live setup |
| U-09 | Show TRAIL price on TREND staging card (current SMA20 value) | ux §4.5 | P1 | S | After C-13, this is a runner-target display | Beginner has a monitoring anchor for TREND trades |
| U-10 | Replace "LOCKOUT" wording with "TRADING STOPPED TODAY"; replace "COOLDOWN" with "SYSTEM PAUSED" | ux §6 | P2 | S | None | Banner wording is unambiguous and not error-state-suggesting |
| U-11 | Add stop-preview per-trade dollar amount (FULL size: $X, REDUCED: $Y) | ux §1.4 | P1 | S | None | Beginner knows actual dollar risk per trade at each size |
| U-12 | Rename "PRE-PLACE" header to "LIMIT CANDIDATES" | ux §3.1 | P2 | S | None | Header is self-explanatory without prior vocabulary |
| U-13 | Label TOUCHED levels with timestamp ("USED — signal fired 10:17") | ux §3.2 | P2 | S | None | Beginner knows why a level is greyed out |
| U-14 | Replace "Prior inst 3:30" label with "FADE TARGET range: ... (yesterday 3:30 PM candle)" | ux §1.5 | P2 | S | None | Beginner connects label to the FADE target |
| U-15 | Add "Next setup window opens at: 10:00 AM" line on info card | ux §1.6 | P3 | S | None | Beginner knows when limits go live |
| U-16 | Increase green brush brightness to match amber visual weight | ux §7.2 | P3 | S | None | "Full size" GO signal feels confident not dimmer than reduced |

### 2.4 Indicator Code — JSONL Schema Additions

| ID | Title | Source | Pri | Effort | Dependencies | Success criterion |
|----|-------|--------|-----|--------|--------------|-------------------|
| J-01 | Add `v2_day_type` to heartbeat and signal payloads | gap_to_am §GAP9, jsonl_data §recommendations | P0 | S | C-01 | JSONL strings LongTrend/ShortTrend/Sideways/etc. appear in heartbeats |
| J-02 | Add `moc_state` and `moc_ratio` to heartbeat payload | jsonl_data §Q6 | P0 | S | None | MOC reconstructable from logs offline |
| J-03 | Add `fill` event when Pending → Active transition fires | nt8_safety §B7, gap_to_am §GAP19 | P0 | S | None | Signal-to-fill latency measurable; outcome reconstructable |
| J-04 | Add `stop`, `target`, `trail_exit`, `timeclose` exit events | nt8_safety §B7 | P0 | S | None | Trade outcome reconstructable from JSONL alone (no need to parse NT Output) |
| J-05 | Add `cancel` event when Pending expires at 14:30 cutoff | nt8_safety §B7 | P0 | S | None | Cancelled pendings distinguishable from filled ones in logs |
| J-06 | Add `canTrade_denied` event with reason when canTrade is false on a qualifying touch | nt8_safety §B7 | P0 | M | None | "Why didn't I get a signal?" answerable from JSONL; reasons categorized (lockout / cap / cooldown / mode-null / RTH window) |
| J-07 | Add `box_capture` event for each master-candle capture (GlobEx/Midnight/Europe/RTH/Close330) | nt8_safety §B7, v24_audit §8 | P1 | S | None | Master-candle H/L/StartTime in JSONL for offline replay |
| J-08 | Add `Sma200SlopeDelta` and `priorSma200At930` to signal payload | gap_to_am §GAP9 | P1 | S | None | Slope context available at signal-fire time for ML re-scoring |
| J-09 | Add `lockout_reset` event on `ResetForNewDay` | nt8_safety §B7 | P2 | S | None | Lockout activation and clearance correlate cleanly across sessions |
| J-10 | Add `divergence` event when hosting Strategy detects position-state mismatch | nt8_safety §B7 | P1 | S | After hosting Strategy build (NT-04) | Divergence visible in JSONL |
| J-11 | Add `heartbeat_gap` event (written by external watchdog) | nt8_safety §B7 | P1 | S | After watchdog build (NT-05) | Heartbeat outages visible in alert stream |

### 2.5 Backtest Infrastructure (from backtest_gap_analysis.md, backtest_infra_audit.md)

| ID | Title | Source | Pri | Effort | Dependencies | Success criterion |
|----|-------|--------|-----|--------|--------------|-------------------|
| B-01 | Add machine-readable `trades.csv` export to `RecordAndDrawTrade` | backtest_gap §4 Fix 3 | P0 | S | None | Each completed trade appended to `{date}/trades.csv` with structured columns |
| B-02 | Enable daily-loss lockout in `State.Historical` | backtest_gap §4 Fix 1 | P0 | S | None | Backtest replays enforce $500/MES lockout; equity curve reflects lockout-truncated days |
| B-03 | Enable post-stop cooldown in `State.Historical` | backtest_gap §4 Fix 2 | P0 | S | None | Backtest cannot fire signal on bar after stop-out |
| B-04 | Add `BacktestStartDate` parameter for reproducible backfill | backtest_gap §4 Fix 4 | P0 | S | None | Two runs of "2023-01-01 to 2026-04-22" produce identical totals |
| B-05 | Write JSONL fill-rate proxy script (5-bar forward classification) | backtest_gap §3 Step 1 | P0 | M | None | Each qualifying touch classified as probable-fill / probable-no-fill; per-level fill rate estimate |
| B-06 | Apply parametric fill-rate sensitivity (30/50/70/100%) to Python backtest | backtest_gap §3 Step 3 | P0 | S | B-05 | Reported Sharpe range bracketed by fill-rate scenarios; documentation updated |
| B-07 | Reconcile V2_4 84-trade backfill against Python event parquet | python_pipeline §10.7, backtest_gap §1 | P1 | M | B-01 | Per-trade comparison table: V2_4 outcome vs Python `realized_R_runner` outcome on same (date, level, direction) |
| B-08 | Add 4-fold rolling walk-forward (monthly roll over 2024-2026 test window) | backtest_gap §5, backtest_infra §10.8 | P1 | M | None | Per-fold Sharpe and PF reported; stability assessed |
| B-09 | Add VIX-stratified regime analysis to walk-forward | backtest_gap §9, backtest_infra §10.9 | P1 | S | B-08 | Per-regime Sharpe (low/medium/high vol) reported |
| B-10 | Add FADE-mode simulation to event builder + label generator | backtest_gap §7 | P1 | L | C-11, C-12 | Sideways-classified events use first-target-only label; TREND/FADE per-mode stats reported separately |
| B-11 | Add holiday/early-close calendar (`pandas_market_calendars` integration) | backtest_infra §10.10, backtest_infra §7 | P2 | M | None | Both pipelines respect holiday blackouts and early-close days; FOMC/NFP/CPI flagged |
| B-12 | Build standalone NT8 Strategy fork of V2_4 logic for reproducible backtest | backtest_infra §10.3 | P1 | L | None | `Tools → Backtest` runs V2_4 rule replay over historical CSVs; deterministic, machine-readable |
| B-13 | Round-up fractional contracts in Python sim; report 10-20% haircut | backtest_infra §10.14 | P3 | S | None | Live-equivalent contract sizing reflected in backtest economics |
| B-14 | Add commission-tier sensitivity ($1.50, $4.50 RT) to Python sim | backtest_gap §7 | P3 | S | None | Sensitivity table in performance summary |

### 2.6 ML Pipeline (from ml_opportunities.md)

| ID | Title | Source | Pri | Effort | Dependencies | Success criterion |
|----|-------|--------|-----|--------|--------------|-------------------|
| M-01 | Re-label M2 from `realized_R_runner` to `realized_R_first_target_only` (existing label) | ml_opps §3.1 step 1 | P1 | S | None | M2 trains on level-to-level exit; Sharpe drops from 9 to realistic range; this is correct |
| M-02 | Re-score V2_4's 84 backfill trades through re-labeled M2 | ml_opps §3.1 step 2 | P1 | S | M-01, B-01 | First defensible "ML helps AM" data point; tier-A subset performance reported |
| M-03 | Add 10 transcript-derived features (1:30 candle, pivots, slope magnitude, body stack count, first-1m volume, etc.) | ml_opps §3.2 | P1 | M | None | Spearman OOS improvement +3-8%; new features in importance ranking |
| M-04 | Implement `_simulate_fibonacci_runner` in `label_builder.py` | ml_opps §3.4 | P1 | M | C-13 | Multi-target label `R_fib_first_target` + `R_fib_runner_conditional` available; M2 retrain on correct exit |
| M-05 | Add abstain head (binary classifier P(abstain | feature_vector)) | ml_opps §3.3 | P2 | M | M-04 | M2 outputs abstain probability; abstain > 0.6 suppresses scoring |
| M-06 | Add sizing head (continuous risk-fraction regression) | ml_opps §3.4 | P2 | L | M-04 | Sizing multiplier output modulates Green/Orange/Gray within tier |
| M-07 | Add regime classifier (7-class multinomial) | ml_opps §3.5 | P2 | M | After 30+ V2_4 sessions collected | Per-regime calibration of M2 confidence |
| M-08 | Add anomaly detector (Mahalanobis distance or autoencoder reconstruction error in feature space) | ml_opps §3.6 | P2 | M | None | OOD score per bar; trades suppressed when score > p99 of training |
| M-09 | Build live feature engine (streaming `feature_builder.py` with 200-bar 1-min cache) | ml_opps §3.7 | P2 | XL | After hosting Strategy NT-04 | M2 callable in real-time at touch event; 200ms response |
| M-10 | Add PSI drift monitoring per high-importance feature; quarterly retrain automation | ml_opps §5 | P3 | M | M-04 | Drift alerts fire when PSI > 0.2 on key features for 3+ sessions |
| M-11 | Fix `combine_v2.py` so M1-silence does not produce `agree=0` (use M2 alone in v1) | ml_opps §2.4, python_pipeline §10.5 | P2 | S | None | Tier-A M2 signals not blocked by M1 absence; combiner logic for v1 disabled |
| M-12 | Add isotonic calibration for M2 `predicted_R` output | ml_opps §5.3 | P3 | S | None | Calibrated expected-R values for sizing-head consumption |

### 2.7 NT8 Execution Stack (from nt8_safety_review.md)

| ID | Title | Source | Pri | Effort | Dependencies | Success criterion |
|----|-------|--------|-----|--------|--------------|-------------------|
| NT-01 | Update `AMShadowObserverV1.cs` to host V2_4 (currently hosts V2_3) | nt8_safety §A2 | P1 | S | None | Observer subscribes to V2_4 OnTouch/OnSignal; shadow_touches.jsonl populated |
| NT-02 | Confirm Sim101 NT8 account-level loss limits configured | nt8_safety §B5 Phase 0 | P0 | S | None | Sim101 account has max-daily-loss and max-drawdown gates set |
| NT-03 | Implement state JSON persistence (`{date}/state.json` written atomically on each significant event) | nt8_safety §B2 | P1 | M | None | Restart mid-session restores `signalsToday`, `realizedPnlDollarsToday`, `lockoutActive`, `currentSignalState` |
| NT-04 | Build hosting Strategy: subscribes to V2_4 OnSignal, queries Python `/decide`, submits via `AtmStrategyCreate` | nt8_safety §A3 Option A | P1 | L | M-09, NT-01, NT-03 | Strategy auto-submits tier-A signals to Sim101; manual override in ChartTrader does not corrupt state |
| NT-05 | Build Python watchdog (heartbeat-gap monitor; SMS/push alerts) | nt8_safety §B3, B7 | P1 | M | J-04, J-06 | Watchdog detects 2-min heartbeat gap during RTH; SMS/push fired |
| NT-06 | Implement order-state reconciliation (per-bar comparison of V2_4 state vs Account.Positions) | nt8_safety §B3 | P1 | M | NT-04 | Position-vs-state divergence fires alert and halts new submissions |
| NT-07 | Configure manual kill-switch hotkey ("Flatten and Cancel All") in NT8 keyboard config | nt8_safety §B4 L5 | P1 | S | None | Hotkey tested; flattens all positions and cancels all orders for the account |
| NT-08 | Add `/decide` HTTP endpoint to Python decision engine | nt8_safety §A3, python_pipeline §10.5 | P2 | M | M-11 | Flask wrapper around `combine_v2.py`; NT8 callable in production |
| NT-09 | Wire `Account.CreateOrder + Submit` in `OnStageClicked` (currently logs ticket only) | nt8_safety §A1 Step 3 | P3 | M | After NT-04 (Strategy is the order path) | If Strategy is unavailable, indicator can submit directly with `AllowLiveOrderSubmit=true` |

### 2.8 Risk Architecture (from risk_architecture.md)

| ID | Title | Source | Pri | Effort | Dependencies | Success criterion |
|----|-------|--------|-----|--------|--------------|-------------------|
| R-01 | Set `MaxDailyLossDollars` to $500 for sim, $200 for live $10K, $400 for live $25K | risk_arch §2.1 | P0 | S | None | Lockout no longer fires on first MES loss; lockout becomes useful protection |
| R-02 | Validate cancelled-pending slot consumption rule does not double-count within-bar replacements | risk_arch §1.4 | P1 | S | None | Same-bar level replacement consumes 1 slot, not 2 |
| R-03 | Document and resolve the lockout-without-signal anomaly behavior | risk_arch §"Lockout-Without-Signal" | P1 | S | After AM clarifies the apr-23 case | Trader has a documented procedure for this scenario |
| R-04 | Add `MaxConsecutiveStops = 2` → mandatory pause (in code or manual rule) | risk_arch §2.3 | P2 | S | None | After 2 consecutive stops, signals suppressed for 60 minutes |
| R-05 | Add weekly drawdown limit (5% of account) tracker (manual or Python monitor) | risk_arch §3.2 | P2 | M | None | Trading stops at 5% weekly DD; resumes Monday |
| R-06 | Add account-peak drawdown circuit breaker (5% from most recent peak) | risk_arch §3.3 | P2 | M | None | Trading pauses on cumulative DD breach; manual review required to resume |
| R-07 | Document daily profit soft-cap of $300/day MES; integrate into manual playbook | risk_arch §2.1 | P2 | S | None | Soft profit-target cap visible in playbook; trader practices "done for the day" |

### 2.9 AM Clarifications (escalation queue)

These are tracked in `am_open_questions.md`. Listed here as IDs for cross-reference with code work.

| ID | Title | Pri | Blocks |
|----|-------|-----|--------|
| AM-Q-01 | Body-stack 3-node vs 4-node | P0 | C-11 |
| AM-Q-02 | Two-sided FADE counter-slope sizing | P0 | C-12 |
| AM-Q-03 | 200-SMA slope-magnitude threshold (flat vs steep) | P0 | C-13, M-04 |
| AM-Q-04 | 1:30 PM candle tracking discipline (every-day vs retracement-only) | P1 | C-15 |
| AM-Q-05 | 50% midpoint add geometry (entry-candle midpoint vs VWAP convergence) | P1 | C-20 |
| AM-Q-06 | 2× candle width on sideways days (transcript provenance) | P1 | C-13 |
| AM-Q-07 | Multi-day 3:30 volume significance threshold | P2 | C-17 (refines), M-03 |
| AM-Q-08 | V-shape recovery interpretation (does B-dip-then-C-recovery count as long trend) | P2 | C-11 |
| AM-Q-09 | First scale-out fraction at 100% Fib (always 50% or variable) | P2 | C-13 |
| AM-Q-10 | FADE day target choice (first reachable vs hold for prior-3:30) | P2 | C-14 |
| AM-Q-11 | Day-of-week probability table (beyond Friday) | P3 | C-21 (refines) |
| AM-Q-12 | Pre-place limit vs confirmation entry default per day-type | P3 | None |
| AM-Q-13 | "Volume significant" qualitative threshold | P3 | M-03 |
| AM-Q-14 | Stop sizing on sideways fades — discretionary or level-anchored | P3 | C-13 |
| AM-Q-15 | CL-specific rules (timing, levels, doctrine) | P3 | C-04, AM has tabled |

### 2.10 Documentation and Process

| ID | Title | Source | Pri | Effort | Dependencies | Success criterion |
|----|-------|--------|-----|--------|--------------|-------------------|
| D-01 | Update strategy documentation to remove Sharpe 9-10 as a production target; replace with AM's profile | backtest_gap §1.1 Tier 1 Gap 4 | P0 | S | None | All references to Sharpe 9 carry caveat or are replaced |
| D-02 | Maintain LEVEL_MAP CI test ensuring V2_4 emitted level names match Python event-builder expectations | python_pipeline §10.1 | P1 | S | None | CI test fails if V2_4 emits a level name not in LEVEL_MAP |
| D-03 | Document the per-tier exit semantics so live and offline use the same `realized_R_runner` definition | python_pipeline §10.3 | P1 | S | After M-04 | Spec documents the production exit policy explicitly |
| D-04 | Document tier cuts as quantile-based (not constant); contract requires fetching `tier` from service, not hardcoded threshold | python_pipeline §10.4 | P2 | S | None | No hardcoded `predicted_R >= 0.318` style logic in any consumer |
| D-05 | Add provenance metadata to all backtest outputs (model commit hash, data snapshot date, run timestamp) | backtest_infra §10.19 | P2 | S | None | Each `*.parquet` artifact carries reproducibility metadata |
| D-06 | Move `output of test march 13 to april 21,.txt` and similar artifacts under version control | backtest_infra §10.22 | P3 | S | None | All capture files reproducible from a known commit |

---

## 3. Sequencing — The 30/60/90 Day Plan

### 3.1 Days 1-30 (the "Now" horizon)

**Goal:** Afshin starts sim-trading the manual playbook. The team closes P0 indicator gaps and instruments backtest infrastructure.

**Week 1:**
- **Afshin:** Print the manual playbook morning one-pager. Set MaxDailyLossDollars=$500 in sim. Begin sim-trading with the playbook. Target 5-10 trades by end of week 1.
- **Indicator:** C-01 (vocab fix), C-02 (MOC gating), J-01/J-02/J-03/J-04/J-05/J-06 (JSONL schema additions), B-01 (trades.csv export), B-02/B-03 (Historical lockout/cooldown), B-04 (BacktestStartDate). U-01 (verdict redesign), U-02 (CONFIRM rename), U-03 (signal counter), U-04 (VWAP labels) — the four highest-impact UX fixes.
- **AM:** Schedule the next conversation. Bring escalations AM-Q-01 (3-node vs 4-node), AM-Q-02 (two-sided FADE), AM-Q-03 (slope threshold) prepared.

**Week 2:**
- **Afshin:** Continue sim. Complete the morning checklist consistently. Begin journaling missed setups vs taken setups to validate the gap analysis.
- **Indicator:** C-10 (Pattern B wiring) — the single highest-leverage change. C-11 (3-node body stack, pending AM confirmation). C-12 (two-sided FADE, pending AM confirmation).
- **Backtest infra:** B-05 (JSONL fill-rate proxy script), B-06 (parametric fill-rate sensitivity).
- **Risk:** R-01 (loss-limit defaults).

**Weeks 3-4:**
- **Afshin:** Sim continues. Aim for 25-30 trades total by end of week 4. Begin the weekly performance review.
- **Indicator:** C-13 (level-to-level exit doctrine, pending AM-Q-03). C-14 (FADE target ladder).
- **Backtest:** B-07 (reconcile 84-trade backfill against Python events). Document the disagreements.
- **NT8:** NT-02 (Sim101 NT8 account loss limits), NT-07 (manual kill-switch hotkey), NT-01 (update shadow observer to V2_4).
- **Documentation:** D-01 (remove Sharpe 9 as target).
- **End of month checkpoint:** Review Afshin's sim trades. Confirm Pattern B is firing correctly. Confirm FADE is two-sided. Confirm the corrected verdict line is unambiguous. Quantify the change in signal count vs the pre-fix 0.27% conversion rate.

### 3.2 Days 31-60 (the "Next" horizon)

**Goal:** Indicator-side rebuild complete. Honest backtest numbers measured against AM's profile. AM clarifications resolved.

**Weeks 5-6:**
- **Indicator P1:** C-03 (per-trigger stops), C-04 (CL bug), C-15 (1:30 PM candle), C-16 (multi-day master candles), J-07/J-08 (additional JSONL events).
- **UX P1:** U-05 through U-11.
- **Backtest:** B-08 (4-fold rolling walk-forward), B-09 (VIX regime stratification), B-10 (FADE-mode simulation in Python), B-12 (standalone NT8 Strategy backtest fork).
- **NT8:** NT-03 (state JSON persistence), NT-04 (hosting Strategy v1 — observe only against Sim101).
- **AM:** Resolve all P0 escalations (AM-Q-01 through AM-Q-03) and most P1 (AM-Q-04 through AM-Q-06).

**Weeks 7-8:**
- **Indicator P2:** C-17 (news-candle wicks), C-18 (R4/S4 + exhaustion gates), C-19 (V1 failed-retest re-enable, subsumed in C-10).
- **Backtest:** B-11 (holiday calendar). Walk-forward extended through the latest available data.
- **NT8:** NT-05 (Python watchdog). NT-06 (order-state reconciliation).
- **ML:** M-01 (re-label on `realized_R_first_target_only`). M-02 (re-score V2_4 backfill through corrected M2). M-03 (add transcript features).
- **Risk:** R-02 (validate cancelled-pending counting). R-03 (resolve lockout-without-signal anomaly).
- **Sim:** Afshin at 50+ trades. Performance review against gates. Decision: are sim metrics trending toward the live-promotion gates?
- **End of month checkpoint:** Honest backtest Sharpe should land in the 2-3 range with realistic fill assumptions. PF should be in the 2.0-2.5 range. If not, diagnose before proceeding to ML retraining.

### 3.3 Days 61-90 (the "Later" horizon)

**Goal:** ML pipeline retrained. NT8 execution stack scaffolded. Sim performance gates met or red-flagged.

**Weeks 9-10:**
- **ML:** M-04 (Fibonacci runner label + retrain). M-05 (abstain head). M-06 (sizing head — depends on M-04). M-08 (anomaly detection).
- **Indicator:** C-20 (50% midpoint add-rule, pending AM-Q-05), C-21 (Friday escalation), C-22 (volume-priority ranking).
- **NT8:** NT-08 (`/decide` HTTP endpoint). NT-04 hardening — full Sim101 auto-submission with reconciliation.
- **Backtest:** B-13/B-14 (sensitivity polish).
- **Sim:** Continued forward collection. 30+ V2_4-instrumented sessions accumulated.

**Weeks 11-12:**
- **ML:** M-07 (regime classifier — depends on 30+ sessions accumulated). M-09 (live feature engine — XL effort, may extend into month 4). M-10 (PSI drift monitoring).
- **NT8:** NT-04 fully tested. All five kill-switch layers exercised individually. State JSON persistence proven through simulated outages.
- **Sim:** Final review against sim-to-live promotion gates: 50+ trades, 30+ sessions, WR >=50%, PF >=2.0, max single-session drawdown <1.5x daily limit, 95th-percentile single-trade loss < daily limit.
- **End of month checkpoint:** Decision point for live promotion. If sim gates are met, plan live first-day at MaxSignalsPerDay=1. If not met, diagnose before considering live.

---

## 4. What to NOT Do (Yet) — Explicit Deferrals

These items are deliberately deferred. Do not get distracted by them.

- **Cautious-mode mechanics with full sizing/stop differentiation.** Cautious-Long and Cautious-Short are scaffolded as classifications but route through TREND with no special treatment. AM has not given specific cautious-mode mechanics. Defer until V1.5 or when AM walks through cautious-mode trades specifically.

- **CL rules revamp.** AM has tabled CL. Fix the `rthOpenHour` bug for hygiene (C-04) but do not attempt to encode CL-specific rules until AM walks through CL setups. Disable CL trading in production until then.

- **Complex Fibonacci ladder for V1.** The full ladder (100/150/200/250% with slope-magnitude threshold ML-tuned) is the V2 target. For V1, ship the simpler version: scale at 100%, runner to 150% (flat slope) or 200% (steep), with a placeholder slope threshold pending AM. Do not wait for the full ML-driven version before shipping the basic doctrine.

- **Day-of-week probability table beyond Friday.** AM has stated only the Friday-full-size-escalation rule explicitly. Encoding a full Mon-Tue-Wed-Thu-Fri probability table requires either AM data or ML discovery. Do not invent it. Encode Friday only and let ML find the rest later.

- **Live trading until sim gates met.** The promotion checklist in `risk_architecture.md` and `nt8_safety_review.md` is non-negotiable. No live trades until 50+ sim trades, 30+ sessions, win rate >=50%, profit factor >=2.0, all kill-switch layers tested individually, and DST transition navigated cleanly. The temptation to "start small in live to validate" is exactly the trap. Sim is real practice; sim metrics are the gate.

- **Multi-instrument autonomous trading (NQ + ES + GC simultaneously).** First version of the autonomous stack should run on a single instrument (ES or MES) with clean discipline. Multi-instrument adds correlation, fill-queue competition, and order-management complexity. Defer to V2.

- **The "decision engine" agreement combiner.** `combine_v2.py` is currently more selective than M2 alone because M1-silence produces `agree=0`. For V1, bypass the combiner entirely (M-11) and use M2 tier directly. The combiner is a V2 feature.

- **Tick-data subscription.** $50-200/month for ES/NQ tick data from CQG/Rithmic/DTN. Defer until paper trading produces enough fill-rate data to justify the spend. Three months of paper trading with tick capture is more valuable than purchasing historical tick data from prior years.

- **Complex options-on-equities integration.** `TradeWave_auto_trading` (the Tradier options engine) is unrelated to the futures stack. Do not entangle them. Keep the futures architecture clean.

---

## 5. Decision Points and Tripwires

Concrete numerical gates with prescribed actions.

**Tripwire 1 — Sim performance gate after 50 trades.**
- If PF < 1.5 after 50 sim trades, halt and reassess. Either the encoding is still off, the discipline is failing, or the regime is unfavorable. Do not proceed to live promotion.
- If PF >= 1.5 and WR >= 45%, continue toward 30-session / promotion-gate completion.
- If PF >= 2.0 and WR >= 50%, the trajectory is correct.

**Tripwire 2 — AM clarifies 3-node body stack.**
- If AM confirms 3-node (B<C<D), retroactively re-evaluate the historical FADE filter. Some "Sideways" days in the JSONL corpus reclassify as Long Trend. Run the corrected classification on the 7 V2_4 sessions and document the population shift.
- If AM confirms 4-node (A<B<C<D), keep V2_4 as-is. Remove the open question and document.

**Tripwire 3 — JSONL fill-rate proxy estimate.**
- If fill rate at popular levels (ORH, Pr30) is below 35%, flag this as a strategy-quality concern. The actual realized P&L on autonomous execution will be materially below the bar-fill assumption. Reduce sizing accordingly until tick-level paper trading confirms.
- If fill rate is 50-70%, proceed with the standard plan.
- If fill rate is above 70%, the spec is approximately correct.

**Tripwire 4 — V2_4 backfill PF after C-10/C-11/C-12/C-13 (P0 fixes).**
- Run a fresh backfill over the same Mar 13 - Apr 22 window with the four P0 indicator fixes active.
- If new PF >= 1.5, the gap analysis is correct, the fixes are working, proceed.
- If new PF is still below 1.0, escalate. Either there is an additional unknown gap, or AM's method does not work in the recent regime.

**Tripwire 5 — Sharpe at 50% fill rate after Python pipeline corrections.**
- After M-01 (re-label on first-target-only) and B-06 (fill-rate haircut), the headline Python pipeline Sharpe should land in the 2.0-3.5 range.
- If significantly above, there are still unmodeled inflators (e.g. selection bias, regime overfit) and the pipeline is not yet honest.
- If significantly below, the entry method is not actually edge-positive in the holdout window — diagnose before retraining further.

**Tripwire 6 — 30 days of V2_4 sim with zero JSONL anomalies.**
- Pre-promotion to live, the system must run 30 sim days with no heartbeat gaps, no divergence events, no unexplained lockouts.
- One anomaly = investigate but do not block. Three anomalies = halt and rebuild the affected component.

**Tripwire 7 — First live week at MaxSignalsPerDay=1.**
- Live Day 1-7: exactly one signal max per day. After 7 successful days at 1-signal-max with no infrastructure issues, increase to 2.
- If any infrastructure issue surfaces in week 1, revert to sim immediately, fix the issue, restart the live timer.

**Tripwire 8 — 100 sim trades with PF < 1.2.**
- After 100+ sim trades with PF consistently below 1.2 despite disciplined execution, the strategy as currently implemented has negative expectancy. Escalate to AM for a fundamental rules review.
- This is unlikely if the gap analysis and fixes are correct, but it is the appropriate fallback if the sim performance is structurally underwhelming.

---

## 6. Cross-Reference Summary Table

For quick reference, the highest-leverage P0 actions and the dependency chain:

| What | Why | Effort | Blocks |
|------|-----|--------|--------|
| C-01 (JSONL day-type fix) | Unblocks FADE mode entirely | S | Everything FADE-related |
| C-10 (Pattern B wired) | 43% of qualifying touches recover signals | L | Doubles candidate pool |
| C-11 (3-node body stack) | Recovers V-shape trend days | S | After AM-Q-01 |
| C-12 (two-sided FADE) | Recovers half of FADE setups | S | After AM-Q-02 |
| C-13 (level-to-level exit) | Right-tail runner restoration | L | After AM-Q-03; biggest PF lift |
| J-01..J-06 (JSONL schema) | Observability for debugging | S | Backtest infrastructure |
| B-01 (trades.csv) | Machine-readable measurement | S | Reproducible testing |
| U-01 (verdict redesign) | Beginner-clear decisions | M | Confidence in manual sim |
| U-02 (CONFIRM rename) | Prevents catastrophic UX miss | S | Order safety |
| R-01 (loss-limit defaults) | Lockout becomes useful | S | Useful sim data |

The single highest-leverage 2-week sprint, ordered:
1. **C-01** (one line, unblocks FADE)
2. **B-01** (trades.csv export, enables measurement)
3. **U-01 + U-02 + U-03 + U-04** (the four UX fixes that prevent beginner traps)
4. **R-01** (loss-limit defaults so sim produces useful data)
5. **C-10** (Pattern B wiring — the single largest signal-pool expansion)
6. **B-02 + B-03** (Historical mode lockout/cooldown — for honest backfill numbers)
7. **C-11 + C-12** (after AM-Q-01 and AM-Q-02 are answered)

If the team can complete just the above seven items in two weeks, the system goes from "0.27% conversion, breakeven, beginner traps everywhere" to "actually firing AM's setups, measurable, beginner-readable, FADE alive, Pattern B alive."

That is the target for the next 14 days.

---

*End of improvement_roadmap.md.*
