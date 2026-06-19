# Python ML / Analytics Pipeline Audit — Wave 2

Author: Wave-2 audit agent
Date: 2026-04-27
Scope: `C:\seasonals\` Python projects only. NT8 indicator C# code is in scope only as it produces inputs/outputs that touch the Python side.

## TL;DR

The Python pipeline is real, deployed, and well-engineered for its narrow scope, but the wiring between it and the V2_4 indicator that AM is actually trading is **not closed**. Specifically:

1. **There are two parallel "realtime" stacks that overlap in name but solve different problems.** `ml_scorer_rt` (M1, seasonal/EOD pattern engine on port 7676) and `pattern_scorer_rt2_1` (M2, intraday level-touch runner regressor on port 7677). They are combined by `decision_engine` into a `/decide` agreement signal. The frozen `pattern_scorer_rt` (M2 v1, 12-head classifier on ±0.2% touch labels) is dead.
2. **The active production scorer is `pattern_scorer_rt2_1` (M2 V2.1).** 71 features, one LightGBM Huber regressor per instrument (ES/NQ/CL/GC), target = `realized_R_runner`, tier cuts persisted, served via Flask+gunicorn behind nginx. Smoke tests pass; **paper trading has not started** and **no live NT8→Python bridge exists yet**.
3. **An `event_builder.py` does exist** at `pattern_scorer_rt2_1/src/events/event_builder.py`. It is the OFFLINE batch builder that walks 1-min CSV bars and emits "first-touch per (session, level)" events. It is NOT what the V2_4 indicator runs. V2_4 writes a richer raw-touch JSONL stream and the `bridge_from_events.py` adapter shims that into the offline-event schema.
4. **OOS methodology is solid.** Chronological 70/10/20 train/val/holdout, plus a strict walk-forward with hard cutoff `2024-01-01` excluding any post-cutoff data from training. Decile calibration, Spearman, Sharpe with zero-fill correction, slippage+commission overlay, MC drawdown — all are in code.
5. **The headline backtest numbers are spectacular and almost certainly inflated.** Tier-A walk-forward: 94% win rate, Sharpe ~10 portfolio, $775k net on the 2024–2026 holdout at $500/trade. The repo's own docs are explicit: this is fill-rate-bias unvalidated; SMA trail mechanically inflates Sharpe; trades cluster (MC p99 understates DD by 1.5–7×).
6. **The decision_engine `/decide` is wired ONLY between M1 and M2 v2 in the holdout backtester.** It has not been called by the V2_4 indicator at runtime — there is no recent JSONL evidence of NT8 → `/decide` round-trips, and the indicator-side `LogEvent`/JSONL writer was added for the *cockpit dashboard*, not for ML scoring.
7. **The "missed valid setups" complaint maps directly to a known bug closed by rt2_1.** rt2 could not distinguish entry-zone from target-zone level touches; `entry_extension_from_overnight_low_adr` and the 5 sibling overnight-geometry features were added 2026-04-21 and the model was refit. Holdout shows the bug profile is now re-ranked rather than blanket-suppressed. CL went slightly negative (−0.013 spearman), which is the only mild regression.
8. **`AMTradeCockpit` indicator-only backtest March 13 → April 21, 2026 shows 84 trades, 35W/49L, 41.7% win rate, profit factor 0.94, total −$204/MES (−$2,044/ES).** That is the *indicator's own ledger*, NOT ML-filtered; it is what AM is actually trading. The ML scorer is supposed to filter that set down to its tier-A subset (~15%). The ML stack has not been measured against the same window.

## 1. Architecture Map (end-to-end)

The system is best understood as four loosely-coupled layers and three data planes.

```
                         ┌─────────────────────────────────────────────┐
                         │           NinjaTrader 8 (Windows)           │
                         │   AMTradeCockpitV2.cs (a.k.a. V2_4 / new_lf)│
                         │   AMTradeCockpit.cs   (v1.1, daily chart)   │
                         │   AMTradeCockpitV3 -- spec only, not built  │
                         └────────────────────┬────────────────────────┘
                                              │ writes
                                              │ (LogEvent → JSONL)
                                              ▼
                ┌──────────────────────────────────────────────────────┐
                │  C:\seasonals\cockpit\sessions\YYYY-MM-DD\events.jsonl│
                │  Schema: {t, type, payload}                          │
                │  Types: touch | signal | phase | bias | heartbeat ...│
                └────────┬─────────────────────────────┬────────────────┘
                         │                             │
                         │ (read by)                   │ (read by)
                         ▼                             ▼
        ┌───────────────────────────┐     ┌─────────────────────────────┐
        │  cockpit/cockpit.py       │     │ pattern_scorer_rt2_1/src/   │
        │  (decision-support HTML)  │     │ shadow/bridge_from_events.py│
        │  pre/live/post pages      │     │ → shadow_touches.jsonl      │
        └───────────────────────────┘     └─────────────┬───────────────┘
                                                        │
                                                        ▼
                                          ┌─────────────────────────────┐
                                          │   src/shadow/enrich_shadow  │
                                          │   replays through label sim │
                                          └─────────────────────────────┘

                                    ┌───────────────────────────┐
                                    │    OFFLINE BATCH PIPELINE  │
                                    │       (Windows dev)        │
                                    └───────────────────────────┘
                C:\seasonals\data\csv\futures\1min\{ES,NQ,CL,GC}.csv
                                              │
        ┌─────────────────────────────────────┼────────────────────┐
        │                                     ▼                    │
        │   src/events/event_builder.py   →  output/events/*.parquet
        │   src/features/feature_builder.py → output/features/*.parquet
        │   src/labels/label_builder.py    →  output/labels/*.parquet
        │   src/train/trainer.py            → output/models/*.txt + meta + tier_thresholds
        │   src/train/walkforward.py        → walkforward_summary, walkforward_trades
        │   src/diagnostics/{indicator_recall, late_move_ab}.py
        └─────────────────────────────────────────────────────────────┘

                                    ┌───────────────────────────┐
                                    │    ONLINE INFERENCE        │
                                    │ (production VPS Linux)     │
                                    └───────────────────────────┘
        ml_scorer:7675   ── M1 daily seasonal scorer (calibrator + LGB + CAT + XGB)
                            served by C:\seasonals\ml_scorer\ → /home/flask/ml_scorer
        ml_scorer_rt:7676 ── intraday "pattern engine" (king-bar matched signals,
                            time-window labels). Pre-scored signals; refresh on king
                            bar confirmation. Endpoints: /signals, /signals/refresh,
                            /session/log, /debrief.
        pattern_scorer_rt2:7677 ── M2 v2.1 runner-label scorer.
                            Endpoints: /score, /score_lookup, /tiers, /info.
                            Models swapped in-place (rt2 → rt2_1); same service id.

                                    ┌───────────────────────────┐
                                    │   DECISION COMBINER        │
                                    └───────────────────────────┘
        decision_engine/run.py decide --v2 → combine_v2.py
            inputs : M2 v2 score + M1 best across {60,120,240}min windows
            output : agree ∈ {0,1,2}, direction, m1_tier, m2_tier
            harness: backtest_v2.py runs head-to-head on holdout grid
                                              │
                                              ▼
                              (no production /decide endpoint exposed
                               yet — combiner is a Python module called
                               by the local backtester only)

                                    ┌───────────────────────────┐
                                    │    BROKER EXECUTION        │
                                    └───────────────────────────┘
        TradeWave_auto_trading/  ── unrelated to futures. Tradier broker for OPTIONS,
                                    Anthropic/OpenAI/Grok scoring, dashboard.
                                    Reaches `ml_scorer:7675` for stock signals.
        ##  No code path exists in this repo that sends futures orders to NT8 via Python. ##
```

### Data planes

1. **Historical 1-min CSVs** — `data/csv/futures/1min/{INST}.csv`. Source of truth for offline training/labels and walk-forward.
2. **JSONL session logs** — `cockpit/sessions/YYYY-MM-DD/events.jsonl`. Source of truth for *what the indicator did at runtime*. The `bridge_from_events` script is the only thing that converts these into a feature-pipeline-compatible shape, and it is post-hoc, not online.
3. **Parquet artifacts under `output/{events,features,labels,models}`** — produced by the offline batch and consumed by both training and the Flask `/score_lookup` endpoint.

### Single-sentence summary of the dataflow today

Bars → offline `event_builder` → first-touch events → `feature_builder` (71 features, including the 6 new geometry features) → `label_builder` (3 R-multiples, runner is target) → `trainer` (LightGBM Huber per instrument) → `tier_thresholds.json` → Flask `/score` reachable on port 7677. The indicator does not call this service today; the only production output flow is parquet replay through `/score_lookup`.

## 2. Realtime vs Offline (and which `rt` is which)

| Folder | Role | Status | Where it runs |
|---|---|---|---|
| `ml_scorer\` | M1 seasonal / EOD scorer (100-yr patterns, daily). | PRODUCTION on `:7675`. | Linux VPS. |
| `ml_scorer_rt\` | "TradeWave Realtime" — pre-scored intraday signal *library* with king-bar matching. Time-window-based win/loss labels. NOT the same model as `pattern_scorer_rt2_1`. | PRODUCTION on `:7676`. | Linux VPS. |
| `ml_scorer_rt2_v1_experiment_archive\` | Failed experimental successor to `ml_scorer_rt`. Kept for `compare_v0_v1.py`. | ARCHIVED. Ignore. | Disk only. |
| `pattern_scorer_rt\` | M2 v1: 12-head classifier on ±0.2% touch labels. Most events were non-RTH (globex/midnight/europe) — known to be wrong vs. AM's actual method. | FROZEN. Do not run. | Disk only. |
| `pattern_scorer_rt2\` | M2 v2: per-instrument LightGBM Huber regressor on `realized_R_runner`. 65 features. | PRODUCTION baseline (snapshot). Models are still on the VPS but in-place file replacement happened on 2026-04-21. | Linux VPS. |
| `pattern_scorer_rt2_1\` | M2 v2.1: same architecture, +6 overnight-geometry features (now 71). Trained 2026-04-21 commit `ff19b9e`. | EVAL PASSED, models swapped into the rt2 service in-place; **paper trading pending**. | Linux VPS at `:7677`. |

There are **two real RT engines** (`ml_scorer_rt` for M1-flavored intraday, `pattern_scorer_rt2_1` for level-touch M2). They are **architecturally different**:

- `ml_scorer_rt` pre-computes a forward-looking prediction parquet and serves *lookup-with-filters*. The `/signals` endpoint accepts a king bar + regime flag and returns matching tier-A signals for the trade date. Models are CatBoost+LGB+XGB ensembles with isotonic calibrators (the heavyweight pkls in `output/ml/`). Labels are time-windowed win/loss probabilities. This is M1-style intraday.
- `pattern_scorer_rt2_1` is a true scorer-on-demand: caller posts a feature vector (or asks the service to look up the feature vector by identity), service returns `predicted_R` + tier. Single LightGBM Huber per instrument. This is M2 / Baiynd's actual method.

The combiner only knows `pattern_scorer_rt` v1 and `pattern_scorer_rt2_1` (latter via `M2_V2_PROJECT`). `ml_scorer_rt` is queried separately via `load_m1.py` but the combiner module assumes the M1 outputs are pre-computed in `output/ml/` parquets, NOT via the Flask service. So the live combiner is not actually a network-RPC system today; it is a Python module that reads parquet files that the M1 batch produces nightly.

## 3. event_builder — does it match V2_4?

There is exactly one canonical `event_builder.py`:

- `C:\seasonals\pattern_scorer_rt2_1\src\events\event_builder.py` (production)
- `C:\seasonals\pattern_scorer_rt2\src\events\event_builder.py` (frozen baseline; identical structure, missing the `globex_open` emit added in rt2_1)

**What it does:** For each instrument, load 1-min RTH bars, compute 30-min trend state (SMA50/SMA200 alignment), compute 15 reference levels per session (prior 30m H/L, opening range H/L, prior inst-close H/L, globex H/L, midnight mid, europe H/L, VWAP, anchored VWAP from inst-close, SMA50_30m, SMA200_30m), then for each (level, session) record the FIRST 1-min bar whose `[low, high]` brackets the level price. Trend gate is hard: only fires if uptrend OR downtrend, never neutral. News blackout vector applied (CL Wednesday EIA + FOMC/NFP/CPI/PPI placeholders).

**Output schema** per event:

```
instrument, session_date, event_ts, level_touched, level_price,
entry_px, direction, trend_state, approach_direction,
open_at_event, high_at_event, low_at_event, close_at_event, volume_at_event,
close_30m, europe_width, adr_20d, globex_open,
+ lvl_<name> for each of 15 levels
```

**Does it match V2_4 logs?** Partially. The V2_4 indicator's JSONL `touch` events carry roughly the same level taxonomy (after the `LEVEL_MAP` rename), but:

- V2_4 emits *every* qualifying touch including pre-trend-gate ones, with `retrace_side` and `already_latched` payload flags. Python event-builder dedupes to first qualifying touch per (session, level) and only after the trend gate. So V2_4 is verbose, Python is canonical.
- Additional V2_4-only events (`signal`, `staging card`, `pivot`, `sma_cross`, etc.) are dropped by the bridge.
- Per-level recall measurement exists: `src/diagnostics/indicator_recall.py` compares V2_4 JSONL touches to Python event keys per (session, level). Output is recall %, per-level breakdown, time-delta stats, plus python-only and indicator-only sets.
- The `bridge_from_events.py` filters V2_4 touches with `retrace_side==True AND already_latched==False` to mimic `event_builder`'s first-bar-containing-level semantics. Empirically this is approximately right, but not bit-identical.

**Critical implication:** The model was trained on the OFFLINE event stream (Python bar-walk). At runtime, when V2_4 fires a touch and the cockpit forwards it to the scorer, the feature vector must be re-computed on the fly to match what the offline pipeline produced — or the indicator has to feed a feature vector the model can score. Today, neither happens: there is no live feature engine in `pattern_scorer_rt2_1` (DEPLOY.txt §"KNOWN LIMITATION" explicitly states this). The only working scoring path is `/score_lookup` — POST `(instrument, session_date, event_ts, level_touched)` and the service does an identity join into the feature parquet that was *already built offline*. That works for backtest replay, not for live trading.

## 4. Feature set (rt2_1 production)

71 columns: 66 numeric + 5 categorical. Source of truth: `pattern_scorer_rt2_1/src/train/trainer.py` `NUM_COLS` + `CAT_COLS`. Grouped:

| Group | Count | Examples |
|---|---|---|
| Candle shape | 5 | `body_pct`, `candle_range_pct`, `upper_wick_pct`, `lower_wick_pct`, `candle_direction` |
| Level distance + position (15 × 2) | 30 | `dist_to_globex_high`, `above_europe_low`, ... |
| Multi-timeframe alignment | 4 | `tf_30m_direction_short`, `tf_30m_direction_long`, `tf_1m_direction`, `tf_alignment_score` |
| Opening range / gap context | 4 | `opening_range_width_pct`, `gap_from_prior_close_pct`, `minutes_since_rth_open`, `minutes_until_rth_close` |
| MOC validation (institutional close, prior session) | 4 | `moc_volume_ratio`, `moc_validated`, `moc_direction`, `moc_observed` |
| Cross-market EOD proxies | 3 | `daily_dxy_direction`, `daily_spy_direction`, `daily_bond_direction` |
| Event/cluster context | 5 | `first_level_touched_today`, `num_levels_in_cluster`, `cluster_width_pct`, `approach_speed`, `vol_zscore` |
| Calendar | 3 | `hour`, `day_of_week`, `month` |
| Size context | 2 | `europe_width`, `adr_20d` |
| Overnight geometry (NEW in rt2_1, 2026-04-21) | 6 | `globex_open_vs_europe_high/_low`, `europe_high_vs_prior_inst_high`, `europe_low_vs_prior_inst_low`, `entry_extension_from_overnight_low_adr`, `pattern_6pm_below_4am_and_inst_long` |
| Categorical (LightGBM-native) | 5 | `level_touched`, `direction`, `trend_state`, `gap_category`, `approach_direction` |

**Notes:**
- The 6 new geometry features close the entry-zone-vs-target-zone gap AM flagged on 2026-04-20. `entry_extension_from_overnight_low_adr` is the #1 importance feature on NQ and CL after retraining; the geometry block accounts for 23–31% of total model gain across the four instruments.
- `pattern_6pm_below_4am_and_inst_long` is hand-coded (one of AM's named setups), and the README flags it as the equity-specific feature most likely to ablate first if regression appears.
- All distance features are normalized as percent of `close_at_event`; ADR-normalized features divide by `adr_20d`. Sane scaling, no leakage flagged.
- "Above/below" columns are `Int64` with explicit NA where the level is missing — important for the LightGBM categorical handling that follows.

## 5. Target label

**Primary target (production):** `realized_R_runner`. Definition (from `label_builder.py:_simulate_runner`):

- Entry at the level price.
- Initial stop = entry ± `clip(europe_width, 0.30·ADR20, 0.80·ADR20)`.
- No profit target. No partial exits.
- After each 1-min bar, ratchet trail: long → `trail = max(trail, sma20_30min)`; short → `trail = min(trail, sma20_30min)`.
- Exit whichever first: stop hit (price = trail), time-cap (15:00 ET ES/NQ/GC, 14:30 ET CL).
- R = sign × (exit_px − entry) / |entry − stop_px|.

Two auxiliary labels are computed and stored (and used by the trailed/first-target backtest variants in `decision_engine/backtest_v2.py`) but **not** the training target:
- `realized_R_first_target_only` — 100% exit at first structural target (next reference level in trade direction, fallback +1·ADR).
- `realized_R_trailed` — 50% partial at first target + 50% trailed on max(orig_stop, SMA20-30m).

And a binary `label` (1 if first target hit before stop, else 0) is also computed for diagnostics.

The architectural choice — a "candle-walk runner" trained label on `realized_R_runner` — exactly matches the SPEC's "candle-walk runner" target. The "SMA20 trail" mentioned in the spec IS the candle-walk runner: it is a 30-min-SMA20 ratchet trail, no first target, time-capped at 15:00 ET. So spec and implementation agree here.

**Stop rule provenance:** `STOP_ADR_FLOOR_MULT=0.30`, `STOP_ADR_CAP_MULT=0.80` are exposed in `config.py` and the SPEC explicitly notes that changing them requires a full pipeline rebuild because labels were simulated under those clips. The 0.3/0.8 clip is the project's own enhancement on top of Baiynd's "europe candle width" rule.

## 6. OOS Methodology

Two distinct splits, both implemented:

1. **Default training split** (`trainer.py:_split`): chronological 70/10/20 train/val/holdout by `event_ts`, no shuffling. Val is used for LightGBM early stopping (`early_stopping(100)` on val Huber loss) and for tier cut quantile fitting (A=p85, B=p70, C=p50). Holdout is reported but not used for tuning.

2. **Strict walk-forward** (`walkforward.py`): hard cutoff `2024-01-01`. Train = events strictly before cutoff (with last 10% as inner val), test = events ≥ cutoff. Same hyperparameters. Reports per-instrument R², Spearman, decile calibration, tier-bucket P&L at $500 risk/trade, max DD, daily Sharpe over the union of trading days (zero-filled on no-signal days). Then a **portfolio walk-forward** that concatenates trades across all 4 instruments and computes Sharpe over the union of trading days.

Calendar awareness: `_trading_days(inst, start, end)` reads the raw 1-min CSVs to derive actual trading days for the calendar slice — not just days with trades — so Sharpe is honestly zero-fill-adjusted (rather than only counting days when a trade fired).

What is NOT done:
- No purged k-fold or embargoed combinatorial CV. The 2024-01-01 cutoff is the only "regime gap" guard.
- No anchor-walking refit (i.e. retrain monthly across the holdout). Single train, hold the test set static.
- No leave-one-instrument-out. Each instrument is independent.

For reference, `src/diagnostics/late_move_ab.py` is a *qualitative* diagnostic, not a separate OOS evaluation: it specifically inspects whether rt2_1 demotes the events that match AM's late-in-move target-zone profile *that rt2 had previously tier-A'd*. Demote rate, mean R demoted, mean R kept, by instrument and by 0.3/0.5/0.7 ADR extension thresholds.

## 7. Performance Metrics

### From `pattern_scorer_rt2_1/output/models/`:

- `tier_thresholds.json` (production cuts; lower numbers mean lower bar to pass — these are R-quantile cutoffs):
  - ES: A=0.318, B=0.153, C=0.044
  - NQ: A=0.394, B=0.223, C=0.101
  - CL: A=0.280, B=0.155, C=0.066
  - GC: A=0.264, B=0.128, C=0.064

- `training_summary.parquet` and `holdout_diagnostics.parquet` exist; `subperiod_stability.parquet` records out-of-time stability across calendar buckets.
- `late_move_ab.parquet` records the geometry-feature A/B (rt2 vs rt2_1) for the ext-thresh sweep.

### From `pattern_scorer_rt2_1/docs/M2v2_runner_system.md` (rt2 baseline numbers; rt2_1 is ≤ rt2 on aggregate by design — the change re-ranks within the bug profile):

Walk-forward (2024-01-02 → 2026-04-10, ~585 trading days), `$500/trade`, fractional contracts, no slippage:

| Inst / Tier | n | Win% | Total $ | MaxDD $ | Sharpe |
|---|---|---|---|---|---|
| ES Tier A | 743 | 95.4% | 226,126 | -1,000 | 6.74 |
| NQ Tier A | 700 | 95.7% | 228,578 | -3,000 | 6.45 |
| CL Tier A | 524 | 93.9% | 160,270 | -2,500 | 5.76 |
| GC Tier A | 634 | 91.0% | 190,688 | -1,568 | 5.61 |
| **Portfolio A** | **2,601** | **94.1%** | **805,662** | **-3,000** | **10.06** |
| **Portfolio A+B** | **5,117** | **85.3%** | **1,053,415** | **-3,100** | **11.46** |

With slippage + commission: Tier-A net haircut 3.6%, A+B 5.7%. Spearman per instrument on the test set: 0.46 (ES), 0.47 (NQ), 0.41 (CL), 0.33 (GC) — all positive, all monotonic-decile.

**Robustness adjustments (`decision_engine/src/robustness_checks.py`):**
- Zero-filled Sharpe corrected to **6.62** standalone (vs naive ~10).
- Monte Carlo DD: realized DDs are 1.5–7× worse than MC p99 — trades cluster, MC under-states tail risk.
- CL deep-dive: no weak slice found.

### rt2 → rt2_1 holdout deltas (Spearman):

ES +0.022, NQ +0.003, CL −0.013, GC +0.021. Aggregate near-noise. Within the bug profile (long+uptrend+high-side+ext≥0.3–0.5 ADR): ES +0.03 to +0.05, NQ +0.04 to +0.10. The change is *targeted re-ranking*, not blanket suppression.

### V2_4 indicator's own ledger (separate from ML stack):

`output of test march 13 to april 21,.txt` is a NinjaTrader Strategy Analyzer / Market Replay log of the V2_4 indicator running on what looks like an MES / ES feed from 2026-03-13 through 2026-04-22. **Final ledger (84 trades):**

- 35 wins / 49 losses → 41.7% win rate
- Total: −40.88 pts, per trade −0.49 pts
- Avg win +19.24 / avg loss −14.58
- Best +79.62, worst −37.75
- Profit factor 0.94
- $-204.38 on MES, $-2,043.85 on full ES

That is **the indicator without ML filtering** — the V2_4 fires every signal that passes its rules, no tier filter on top. It is what AM sees on her live chart. The ML scorer is supposed to take this signal stream and keep only the tier-A subset. There is no measurement in the repo of what the rt2_1 model would have done over this same window. That measurement is the most important missing artifact.

## 8. Decision Engine Layer

Code: `decision_engine/src/combine_v2.py` and `decision_engine/run.py decide --v2`.

The combiner answers exactly one question: **does M2's tier and direction agree with M1's best-across-windows tier and direction for this date?**

Algorithm:
1. M2 v2 produces `(predicted_R, tier ∈ {A, B, C, -}, direction ∈ {long, short})` for the event.
2. Combiner maps `direction → M1 direction code (L/S)` and queries `load_m1.lookup_date_aware(inst, slot, dir, window, date)` for each of `windows = [60, 120, 240]` minutes. Returns the M1 with the best `(tier_rank, prob)` tuple.
3. Agreement rank:
   - `2` = M2 tier A AND M1 tier A_High
   - `1` = (A,B) or (B,A) cross
   - `0` = otherwise (or no M1 match for the date)

What the combiner explicitly is NOT doing:
- It is not setting any sizing knob.
- It is not setting a confidence threshold beyond the discrete tier cut.
- It is not exposing a `/decide` HTTP endpoint. The combiner is a Python module called by the local `backtest_v2.py` harness that scores all holdout events offline. There is no production HTTP service built around it.

What the backtest harness *also* does (in `backtest_v2.py`): runs five strategies head-to-head on the same holdout events: `m2v2_alone_A`, `m2v2_alone_AB`, `combiner_A`, `combiner_lax` (agree≥1), and `m1_alone`. Same $500-risk sizing across all. Outputs `EVAL_DIR/backtest_v2_summary.parquet`, `backtest_v2_portfolio.parquet`, `backtest_v2_trades.parquet`.

So today, the *decision* in production is binary: did `predicted_R ≥ tier_A_cutoff` for this instrument? Anything richer (sizing, confidence weighting, M1+M2 agreement gate) lives in offline harnesses, not in the live serving stack.

## 9. NT8 Bridge — does any Python actually trigger NT8 orders?

**Short answer: no. Not for futures.**

What exists:
1. **`ml_scorer_rt/app.py:/session/log` (POST)** — accepts session events from NT8 (`level_touched`, `entry`, `exit`, `signal_fired`). Used by ml_scorer_rt for post-market debrief. This is one-way **NT8 → Python**, telemetry only.
2. **`ml_scorer_rt/app.py:/signals/refresh` (POST)** — NT8 can call this once the king bar is confirmed at 9:30. Returns the day's tier-A signal list. This is **Python → NT8 advisory**, NT8 can read the response and presumably pop alerts; nothing ties the response to order placement.
3. **`pattern_scorer_rt2_1/app.py:/score`, `/score_lookup`** — pure scoring. Caller posts a feature vector or identity tuple, receives `{predicted_R, tier}`. **Not connected to any NT8 callback.** The only "live" caller intended is the not-yet-built feature engine that DEPLOY.txt explicitly punts on (`KNOWN LIMITATION (planned phase 2)`).
4. **`cockpit/cockpit.py`** — reads NT8's JSONL output and renders three local HTML pages. Decision-support, advisory, no order routing.
5. **`TradeWave_auto_trading/`** — *broker* automation, but for **options on equities via Tradier API** (see `broker_tradier.py`, `options_evaluator.py`, `dashboard.py`). It calls `ml_scorer:7675` for stock signals and posts options orders to Tradier. **It does not touch NT8 and does not trade futures.** The README/repo confirms it is a different strategic project.

What does NOT exist:
- No `nt8_client.py`, no NT8 Webhook adapter, no DDE/.NET bridge on the Python side.
- No `broker_ninjatrader.py` in `TradeWave_auto_trading/`.
- No "place limit at level X" outbound call from any Python service.
- No background process that reads `events.jsonl` in real-time and posts orders anywhere.

The full chain of execution today is: V2_4 → trader's eyes → trader's hands in NT8 Chart Trader. The Python stack is **decision support** (cockpit dashboard), **scoring on demand** (rt2_1 service), and **post-hoc analytics** (debrief, late_move_ab). The Wave-3 design will need to fill the entire `Python → broker` arrow.

## 10. Gaps — spec vs reality

The `baiynd_autotrader/SPEC.md` defines a 10-component fully-hands-off engine: Data Layer, State Layer, Signal Engine, Risk Engine, Order Manager, State Reconciler, Watchdog, Kill Switch, Observability, Persistence. None of those components are implemented in any Python project on disk. Specifically missing:

- **Data layer** for live ticks. `pattern_scorer_rt2_1` reads CSV historical bars, full stop. There is no `tick_subscriber.py`, no `nt8_data_feed.py`, no broker quote streamer.
- **State layer** for the touched-levels latch, current signal state machine, daily P&L. The cockpit `schemas/session.py` has Pydantic stubs for SessionState/Blueprint, but they're consumed by the HTML renderer only — there is no live state machine writing those.
- **Signal engine** that emits eligibility-change events (level became eligible, lost eligibility, refresh needed). The offline event_builder is the closest analogue but it's batch.
- **Risk engine** with daily/weekly/loss caps, vol halt, spread guard, slippage alarm. Nothing on disk does this.
- **Order manager** — entirely missing for futures. None of the broker_*.py files in TradeWave touch CME instruments.
- **State reconciler** — missing. No 60-second broker poll loop.
- **Watchdog / heartbeat** — `ml_scorer_rt` has a heartbeat in the indicator-side JSONL, but no reciprocal liveness check from Python.
- **Kill switch** — missing. No webhook, no file-drop, no CLI, no SSH endpoint.
- **Persistence layer** — partially there: `output/models/` and parquet artifacts persist, but nothing flushes "today's open position, trail level, touched-levels latch" every 10 sec. That state is in the indicator's C# memory.
- **Operational design domain (ODD) gates** — RTH window, calendar blackouts, ADR threshold, volatility halt — all defined in spec; only news blackouts and time cap exist in `pattern_scorer_rt2_1/config.py` (and they apply to event generation, not order placement).
- **AMTradeCockpitV3** — the proactive pre-place redesign — is a SPEC only (`AMTradeCockpitV3_SPEC.md`). No `AMTradeCockpitV3.cs`. The acceptance criteria in `SPEC.md` reference V3 parity, which currently has nothing to be parity-tested against.

What IS half-done or experimental:

- **Live feature engine** for `pattern_scorer_rt2_1`. The DEPLOY.txt is explicit: `/score` requires the caller to compute features. That is OK for a backtester replaying events, terrible for a live system. Without it, V2_4 can't ask "score this touch right now" — there is no path from `(touch event, current bars)` to a feature vector.
- **`/decide` HTTP endpoint.** combine_v2 exists as a module; there is no Flask wrapper around it on the production VPS. NT8 would need that to be a real network call.
- **Shadow trading (`src/shadow/`).** `bridge_from_events`, `enrich_shadow`, `stage1_report` build a parallel "what would have happened" pipeline from V2_4 logs. Useful for paper-trade analysis, not order routing.
- **Indicator recall diagnostic** (`src/diagnostics/indicator_recall.py`) compares V2_4 JSONL touches to Python event keys. There is no recent saved output of this, so we don't know the current recall %. **This is the highest-leverage diagnostic AM should run before any wiring decision** — if recall is, say, 80%, then 20% of "missed setups" really are missed by the indicator (or by the offline pipeline) and the ML stack will never see them.
- **Walk-forward calendar drift.** Walkforward freezes on `2024-01-01`. We are now in late April 2026; there is over two years of held-out data the model has never been refit on. This is by design (strict OOS) but it also means any concept-drift since the last retrain is invisible.
- **CL geometry regression.** rt2_1 holdout Spearman regressed −0.013 on CL. The README flags this. If paper trading shows CL underperformance, the geometry features need to be ablated for CL specifically (per-instrument feature mask).
- **`ml_scorer_rt2_v1_experiment_archive`** is exactly what it says — an aborted intraday-pattern engine successor. Codepaths from there should not be re-entered.
- **Decision-engine v1 (`combine.py`, `load_m1.py`, `load_m2.py`)** still exists in `decision_engine/src/`. It assumes 12-head classifier outputs from the frozen `pattern_scorer_rt`. Calling it would silently use the wrong M2.

## Cross-reference notes for Wave 3

The other Wave-2 audit threads will care about the following load-bearing facts:

1. **Indicator → Python contract.** The only durable record of the V2_4 indicator's behavior is `cockpit/sessions/YYYY-MM-DD/events.jsonl`. Schema-level decisions (`type`, `payload`, level naming) are encoded in: `pattern_scorer_rt2_1/src/diagnostics/indicator_recall.py:LEVEL_MAP` and `pattern_scorer_rt2_1/src/shadow/bridge_from_events.py:LEVEL_MAP`. Any change to V2_4's emitted event types or level names breaks these maps silently — they fall back to `level_v23` passthrough and the feature-join misses, which would silently drop events from the shadow pipeline. **Wave-3 should make these two maps the canonical source for the indicator-side property names**, and add a CI test that asserts each map covers the full set of levels emitted by the latest indicator version.

2. **Stop-rule clip is load-bearing on the model weights.** `STOP_ADR_FLOOR_MULT=0.30` and `STOP_ADR_CAP_MULT=0.80` — the labels were simulated against this clip. Changing them invalidates the model. The ML stack and the (future) auto-trader must use the **same** clip values, or the live system will execute trades with stops the model has never been trained on.

3. **`realized_R_runner` is the trained target.** Any auto-trader simulator must implement *exactly* the runner exit policy: initial stop, no first target, ratchet trail to max(initial_stop, sma20_30min) per 1-min bar, force-flat at 15:00 ET (14:30 CL). This is the only definition of "what the model thinks a trade is worth." Other policies (first-target-only, 50/50 trailed) are *labels* in the parquet but are not what was trained on.

4. **Tier cuts are quantiles, not Sharpe-optimized.** `A=p85`, `B=p70`, `C=p50` of *validation-set predictions*. The cuts move whenever the model is retrained. They are not invariant. A live system that hardcodes `predicted_R ≥ 0.318` for ES will silently desync from the trained model after any refit. The right contract is "ask the service for `tier`" not "compare predicted_R to a constant."

5. **Combiner currently downgrades through M1.** If M1 has no rule matching a given (slot, dir, date), the combiner returns `agree=0` regardless of how strong M2 is. That is per-design but means the combiner is *more selective* than M2 alone. If Wave-3's autotrader v1 plans to use M2 alone (per the spec's §16 non-goals: "ML meta-gate / `/decide` integration is a v2 feature"), it should bypass `/decide` entirely and read tier directly off the M2 service. Don't let `agree=0` from a missing M1 rule kill an otherwise-valid M2-tier-A signal.

6. **No live feature engine ⇒ V2_4 cannot call M2 today even if it wanted to.** Wave-3 must either (a) port `feature_builder.py` into a streaming engine that holds a 1-min-bar cache and computes features at touch time, or (b) push enough state from the indicator's C# side that the Flask `/score` endpoint can compute features from it. (a) is cleaner and matches the existing offline code path. The 6 geometry features specifically need `globex_open`, prior-day inst close H/L, 4 AM europe H/L, ADR20, plus the live entry price — all of which V2_4 already knows; the gap is just that nobody assembles them and calls the service.

7. **`AMTradeCockpit` indicator backtest M13–A21 = 41.7% win rate, PF 0.94, slightly losing.** That is the ground truth of "what AM is trading right now." It is NOT what the ML stack predicts on the same window. Wave-3 should add as a deliverable: re-score those 84 indicator trades through `pattern_scorer_rt2_1` and report what tier-A would have kept, and what its realized R distribution would have been. Until that comparison exists, "ML helps AM" is an unverified claim.

8. **The "missed setups" complaint maps to the rt2 → rt2_1 fix.** AM flagged 2026-04-20 that M2 tier-A'd late-in-move target-zone touches. rt2_1 demonstrably re-ranks within that profile and didn't blanket-suppress. **However**, that fix is upstream of the ML scorer. If V2_4 also misses setups *before* the touch ever reaches the ML scorer (i.e. the indicator never logged a `touch` event for it, or `retrace_side==False` at the moment), then re-tuning M2 will not fix the user complaint. This is exactly what `indicator_recall.py` is designed to measure, and there is no recent saved output. **This is the single highest-leverage diagnostic to run before the next architecture decision.**

9. **No Python writes orders to NT8.** Closing this loop is in scope for the autotrader spec but out of scope for the current ML stack. Whatever Wave-3 designs, the production architecture will have to add: feature engine, score-on-touch RPC, decision policy (tier mapping → take/skip), broker adapter, state reconciler, kill switch. Python today does none of that for futures.

10. **Two backups of the same project exist on disk.** `pattern_scorer_rt2/` and `pattern_scorer_rt2_1/` are full clones with their own `.git`, identical `src/` layouts, and the rt2_1 `late_move_ab.py` script directly references the rt2 `output/models/` directory to score the holdout twice. Keeping both is correct (rt2 is the canonical baseline snapshot), but for a CI/CD design, a single repo with tagged releases would be cleaner. Both ship with `.gitignore` and `.git/`, and `pattern_scorer_rt2_1.zip` is shipped as a reproducible bundle; this is good hygiene.

## File path reference (key files)

- `C:\seasonals\readme_ml.txt` — top-level project map (most current source of truth on what each folder does).
- `C:\seasonals\pattern_scorer_rt2_1\README.md` — rt2 vs rt2_1 diff and deployment status.
- `C:\seasonals\pattern_scorer_rt2_1\config.py` — global config: stop multipliers, RTH windows, news blackouts, train/val/holdout splits, instrument list.
- `C:\seasonals\pattern_scorer_rt2_1\src\events\event_builder.py` — first-touch event generator (offline batch, 1-min bars).
- `C:\seasonals\pattern_scorer_rt2_1\src\features\feature_builder.py` — 71-feature builder including the new `_overnight_geometry_features`.
- `C:\seasonals\pattern_scorer_rt2_1\src\labels\label_builder.py` — runner / trailed / first-target R-label simulators.
- `C:\seasonals\pattern_scorer_rt2_1\src\train\trainer.py` — LightGBM Huber per instrument, default 70/10/20 split.
- `C:\seasonals\pattern_scorer_rt2_1\src\train\walkforward.py` — strict 2024-01-01 cutoff walk-forward + portfolio Sharpe.
- `C:\seasonals\pattern_scorer_rt2_1\src\score\scorer.py` — programmatic score_event / score_batch entry points.
- `C:\seasonals\pattern_scorer_rt2_1\src\diagnostics\indicator_recall.py` — V2_4 JSONL ↔ Python event recall diagnostic.
- `C:\seasonals\pattern_scorer_rt2_1\src\diagnostics\late_move_ab.py` — qualitative A/B for the geometry-feature retrain.
- `C:\seasonals\pattern_scorer_rt2_1\src\shadow\bridge_from_events.py` — JSONL → shadow_touches.jsonl converter.
- `C:\seasonals\pattern_scorer_rt2_1\pattern_scorer_rt2\app.py` — Flask serving service (port 7677). Endpoints: `/score`, `/score_lookup`, `/health`, `/tiers`, `/info`.
- `C:\seasonals\pattern_scorer_rt2_1\pattern_scorer_rt2\DEPLOY.txt` — VPS deployment runbook + the explicit `KNOWN LIMITATION` re: live feature engine.
- `C:\seasonals\pattern_scorer_rt2_1\output\models\tier_thresholds.json` — current production tier cuts.
- `C:\seasonals\pattern_scorer_rt2_1\docs\v2_spec.md` — design doc for the v2 rebuild.
- `C:\seasonals\pattern_scorer_rt2_1\docs\M2v2_runner_system.md` — full runner-system specification + validation tests + caveats.
- `C:\seasonals\decision_engine\config.py` — combiner paths and shared windows.
- `C:\seasonals\decision_engine\src\combine_v2.py` — M1+M2-v2 agreement combiner.
- `C:\seasonals\decision_engine\src\backtest_v2.py` — head-to-head backtest harness (5 strategies on holdout).
- `C:\seasonals\ml_scorer_rt\ml_scorer_rt\app.py` — M1 intraday signal-library service (port 7676). `/signals`, `/signals/refresh`, `/session/log`, `/debrief`.
- `C:\seasonals\ml_scorer_rt\ml_scorer_rt\config.py` — tier thresholds (A=0.72), king bar names, regime gates.
- `C:\seasonals\ml_scorer_rt\ninjatrader\indicators\AMTradeCockpitV3_SPEC.md` — proactive pre-place redesign spec (not yet implemented).
- `C:\seasonals\cockpit\README.md` and `cockpit\cockpit.py` — decision-support dashboard reading `sessions/YYYY-MM-DD/events.jsonl`.
- `C:\seasonals\cockpit\sessions\` — JSONL session log directory written by V2_4. Most recent dates in the audit window: 2026-04-14 through 2026-04-27.
- `C:\seasonals\baiynd_autotrader\SPEC.md` — full Wave-1 hands-off auto-trader spec. The components defined there (Risk Engine, Order Manager, State Reconciler, etc.) have **no Python implementation today**.
- `C:\seasonals\output of test march 13 to april 21,.txt` — V2_4 indicator's own ledger over a 6-week period: 84 trades, 41.7% win rate, profit factor 0.94, total −$2,043 on full ES. *This is the trade stream the ML stack should be filtering, but the comparison has not been run.*
- `C:\seasonals\TradeWave_auto_trading\config.py` — confirmation that the only existing broker-execution code in this repo is for **options on equities via Tradier**, not futures.
