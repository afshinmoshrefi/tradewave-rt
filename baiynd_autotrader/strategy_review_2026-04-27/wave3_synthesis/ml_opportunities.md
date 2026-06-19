# ML Opportunities and Reframing — Wave 3 Synthesis

**Author:** ML Opportunities Analyst (Wave-3 agent)
**Date:** 2026-04-27
**Inputs:** python_pipeline_audit.md, backtest_infra_audit.md, jsonl_data_analysis.md, all six wave1 transcript extracts
**Deliver to:** Strategy synthesis lead / Afshin

---

## TL;DR

The current framing — "use ML to capture AM's discretion" — is both too narrow and mis-aimed. Too narrow because there are at least six distinct places ML can add value that have nothing to do with encoding nuance. Mis-aimed because the model is currently trained on a label (SMA20 ratchet trail) that AM explicitly said is "terrible" and contradicts her actual exit doctrine (level-to-level, Fibonacci ladder). Every enhancement ranked below is conditional on fixing the label first. A Sharpe 9–10 trained on a broken target is not a model of AM's strategy — it is a model of a mechanical trailing policy that AM does not use. Re-labeling must happen before any other ML investment is meaningful.

**Priority sequence: (A) Re-label → (B) Add missing features → (C) Add abstain/sizing heads → (D) Regime classifier → (E) Anomaly detection → (F) Real-time inference engine.**

---

## Section 1. Where ML Actually Fits in AM's Strategy

### 1.1 Setup-Quality Scoring (current M2 regressor's intended role)

Given a candidate level-touch, what is the probability this setup is a winner, and at what expected R-multiple?

This is the role `pattern_scorer_rt2_1` (M2) was built for. The concept is right. The execution has two problems: the training target does not match AM's exit doctrine (Section 2.1), and a significant fraction of the features AM actually uses are not in the feature set (Section 2.2). Once those are fixed, a setup-quality scorer is the highest-leverage single ML component in the stack.

The scorer's output should be a per-touch predicted R-multiple under AM's actual exit doctrine, not a trailing-policy R-multiple. Tier cuts (A/B/C) then gate which setups are worth taking.

Practical scope: M2's current 71-feature LightGBM Huber regressor per instrument is an appropriate architecture. The training data (2012–2024 pre-cutoff, ~tens of thousands of qualifying touch events per instrument) is large enough. The walk-forward methodology (strict 2024-01-01 cutoff) is sound.

### 1.2 Regime Detection (current calendar features touch this but incompletely)

What type of day is this? The answer gates everything: which setups are eligible, which sizes are appropriate, which targets apply.

AM's day-type system is a four-candle body-stacking classifier. V2_4 attempts to encode it as an enum (LongTrend, ShortTrend, CautiousLong, CautiousShort, Sideways, Unknown). The JSONL audit found that the indicator has never in six months emitted the spec-vocabulary strings — it emits `congestion / extended / trending / unknown` instead. That is a pre-ML problem. The ML stack cannot learn on labels that don't exist in the data stream.

Beyond AM's own day-type framework, ML can produce a richer regime classifier. The 7-class version recommended in Section 3.5 extends AM's 4-candle heuristic with quantitative features (200-SMA slope magnitude, prior-3-day inventory build, VWAP slope, opening-range width normalized to ADR) and produces a probability distribution over regimes rather than a hard class. The hard class is what AM codes manually; the probability distribution is what ML adds on top.

Current gap: the `day_of_week`, `hour`, and `month` calendar features in the 71-feature set are rudimentary proxies. The transcript evidence (apr-16: "this shifts every day of the week"; apr-23: "congestion vs. trending determines trade type") shows that regime is the single most important setup gate. ML can learn this relationship from data far more completely than a lookup table.

### 1.3 Sizing (NOT currently done by ML)

How much to risk on this trade? AM's rule framework produces three outcomes: Green (full size), Orange (reduced), Gray (no trade). These are currently determined by rule-based MOC validation (3:30 vs 3:00 volume ratio >= 1.20 = Green, etc.). ML is not in this loop.

There is a clean sizing opportunity: given the full 71-feature vector at touch time, train a regression head that predicts optimal risk fraction given the setup's expected-R distribution. This is not replacing the Green/Orange/Gray traffic light — it is adding a continuous sizing signal that can modulate the discrete tier. A Tier-A setup on a high-confidence day should get more size than a Tier-A setup on the edge of the A/B threshold with low feature agreement.

The apr-10 transcript is explicit: "I want to see the institutional flow validated AND the 50 SMA aligning before I add." That is a multi-condition gate for size-up. ML can learn which feature combinations historically correlate with larger winner R-multiples and thus deserve larger position sizing.

### 1.4 Exit Timing (NOT currently done by ML — SMA20 trail is mechanical, not ML)

When to take partial, when to run, when to cut early?

This is the most contested dimension. AM is clear: level-to-level, Fibonacci 100/150/200/250% targets, no trailing stops. She says "trailing stops are terrible" twice in the apr-9 session. The SMA20 trail in the current label simulator is not AM's exit policy.

However, even within AM's level-to-level framework, there are ML opportunities:

- **Which Fibonacci level to target?** AM says 150% when 200-SMA is flat, 200% when steep, 250% when non-overlapping candle bodies and strong continuation. The 200-SMA slope magnitude that separates these states was explicitly left as "ML will figure that out" (apr-24, lines 252-253). This is a direct invitation.
- **When to exit at T1 vs. hold for T2?** The apr-23 transcript says "the longer it sits there at the target, the more likely it is that it doesn't go through — take the money." That decay-time signal is a regressor output.
- **Early exit on invalidation:** If price action at the level starts failing Pattern B conditions, exit early. ML can learn that feature state.

An exit-timing model is a Medium-effort module once the re-labeling (Section 3.1) is done and Fibonacci targets are wired as the label.

### 1.5 Filter / Abstain (NOT currently done — ML has no abstain output)

When NOT to trade is at least as important as when to trade. The decision engine currently has three tiers (A/B/C) and a no-signal bucket. But the no-signal state is purely a function of whether the model's predicted R is below the C tier threshold. It is not a dedicated "the market is in a state where AM would sit on her hands" classifier.

From the transcripts, AM's abstain conditions include: opening range > 10 points (reduced-size or no-trade); first 1-min volume below 12k ES / 5k NQ (wait for wick-out); MOC Gray (no trade); flat VWAP slope = chop; divergence in sideways moving averages (explicitly told to ignore); day after a news shock (re-evaluate thesis). None of these are modeled as abstain features.

An abstain head — a binary classifier P(abstain | feature_vector) — trained on historical "days when even Tier-A signals underperformed" would be a significant addition. Its output thresholds a "stand down" signal that overrides any positive scoring.

The JSONL data makes the case empirically: 0.27% conversion rate from qualifying touches to signals over six months. Even if 90% of that gap is pre-ML (V2_4 was not fully wired), the remaining gap suggests that a meaningful fraction of qualifying touches occur on days when AM would not trade. ML can learn which feature combinations characterize those days.

### 1.6 Anomaly / Kill-Switch (NOT currently done)

Detect when the system is operating outside its training distribution — when market microstructure, volatility regime, or news context is so unusual that the model's predictions are not trustworthy.

This is the safety net for the autonomous trading loop. Examples from the transcripts: the Iran news shock on apr-10 (AM says "check the news feed, don't react to price"), the apr-9 week where price was above R3/R4 in a short-covering rally (AM diagnoses this as short-cover, not trend — completely different dynamics than the training data), the early April 2025 geopolitical tape bomb in the JSONL.

An anomaly detector does not need to be sophisticated: an out-of-distribution (OOD) score per bar based on Mahalanobis distance in feature space, or an autoencoder reconstruction error, is sufficient to flag "this bar's feature vector is far from the training distribution." If the OOD score exceeds a threshold, the system halts scoring and falls back to "no trade" until the anomaly resolves.

This is the ML component that prevents the system from confidently placing trades during black swans. It belongs in the live inference stack, not just the backtest.

---

## Section 2. Diagnosis of the Existing Pipeline's Biggest Issues

### 2.1 Wrong Target Label — SMA20 Trail vs. AM's Actual Exit Doctrine

This is the most critical problem. The model is trained on `realized_R_runner`, defined as: entry at level price, no first target, no partial exits, ratchet trail to `max(initial_stop, SMA20_30min)`, force-flat at 15:00 ET.

AM's actual exit doctrine, stated verbatim in the apr-9 transcript: *"I don't trail any stops. I go level A to level B and I'm done."* She says "trailing stops are terrible" twice. The apr-24 transcript is more specific: first target = Fibonacci 100% extension of the trigger candle; second target = 150% (flat 200-SMA) or 200% (steep 200-SMA) or 250% (non-overlapping continuation bodies).

The consequences of training on the wrong label are:

1. **The model optimizes for a different exit than the one being traded.** Feature importance is distorted. Features that predict whether a trade runs cleanly to a Fibonacci level are different from features that predict whether a trade can be mechanically trailed on SMA20 for a long time. A model optimized for the latter may actually hurt performance under the former.

2. **The Sharpe 9-10 number is measuring the SMA20 trail policy, not AM's level-to-level policy.** The SMA20 ratchet trail has the mechanical property of smoothing exits — it never takes profits too early on strong trends and it never holds through sharp reversals (because the trail tightens). That mechanical smoothing inflates Sharpe directly. The backtest infra audit notes this explicitly: "SMA trail mechanically inflates Sharpe." AM's level-to-level exit does not have this smoothing property. Wins are discrete and bounded. The actual realized Sharpe under AM's doctrine is unknown — it may be significantly lower.

3. **Two auxiliary labels already exist but are not used for training.** `realized_R_first_target_only` (100% exit at first structural target) and `realized_R_trailed` (50% partial at first target + 50% trailed) are computed and stored in the parquet. Neither is the training target. `realized_R_first_target_only` is the closest existing approximation to AM's level-to-level rule. Re-training M2 on this label requires approximately zero new engineering — the data already exists.

4. **The correct AM label would be a multi-target regression.** AM's actual exit is: take partial at Fibonacci 100%, hold the remainder conditional on 200-SMA slope, target 150%/200%/250% for the runner. This is a two-head label: `R_first_target` and `R_runner_conditional_on_slope`. The slope-conditional branching can be approximated by training separate models for flat-200 sessions vs. steep-200 sessions, or by including slope magnitude as a feature with sufficient range in the training data. Neither approach is architecturally complex.

### 2.2 Feature Gaps vs. AM's Transcripts

The following features are directly described in transcripts and are absent from the current 71-feature set:

**High priority (directly cited as entry gates):**
- `dist_to_1pm_candle_high`, `dist_to_1pm_candle_low`: The 1:30 PM prior-day candle. Mar-6 says "every day, Afshin, every day, by a couple of minutes" — it is a primary reversal level. The Python event builder knows about 15 levels; the 1:30 PM candle is not one of them.
- `dist_to_woody_pivot_R1` through `R4`, `S1` through `S4`: Woody's pivots. Apr-8 says "First things first, where's the pivot?" The pivot is AM's daily bias anchor. None of the 71 features contain pivot distance.
- `dist_to_news_candle_wick`: News candle level. Apr-24 gives the precise rule: any intraday candle whose volume exceeds both prior-day 9:30 and prior-day 3:30 volume creates a wick-level. Not in the feature set.
- `day_of_week_friday_flag`: Apr-24 says Friday gets full-size escalation when bodies don't overlap + MOC validated. `day_of_week` exists as a categorical feature but the Friday-specific conditional logic is not encoded.
- `opening_range_width_pts`: Apr-8 gives the specific rule: 9:30 1-min candle range > 10 points forces single-contract sizing. The `opening_range_width_pct` feature exists (normalized) but the 10-point threshold is instrument-specific and requires absolute point value, not percent.
- `first_1min_volume_ratio`: Apr-8 and apr-9: 9:30 1-min volume benchmark (>15k ES = conviction, <12k = tentative, >20k directional = strong signal). No volume feature for the opening 1-minute candle exists.
- `pattern_b_state_at_touch`: The V2_4 indicator tracks look-below/above-and-fail state via a per-level state machine (Untouched → Breached → Armed → Consumed). The JSONL data confirms 43% of all touches are Pattern B touches (1,271 of 2,956). This state variable is not fed to M2.
- `body_stack_node_count`: How many of the four master candles are strictly stacked in the trade direction? A count 0-4 captures day-type quality continuously rather than as a discrete class.
- `sma200_slope_magnitude_30m`: The 200-SMA slope as a continuous variable, not just its sign. Apr-24 explicitly leaves the threshold for "flat vs. steep" as a machine learning problem. This is the single most important missing feature for Fibonacci target selection.

**Medium priority (cited as permission or context):**
- `dist_to_r3_r4_extension`: Price relative to R3/R4 pivot. Apr-8: "above R3 = extended, watch for exhaustion." This is a regime gate that prevents fresh longs at extremes.
- `vwap_slope_sign`, `vwap_slope_magnitude`: Apr-8/9: "flat VWAP = chop; VWAP slope AND side both matter." The current feature set has VWAP distance but not VWAP slope.
- `dxy_intraday_correlation`: Apr-8 describes a rolling ES-DXY correlation as a size-up eligibility gate. The cross-market features in the 71-feature set are EOD proxies (`daily_dxy_direction`), not intraday rolling correlations.
- `multi_day_3pm30_volume_ratio`: Apr-23 uses the comparison of today's 3:30 volume vs. yesterday's vs. two days ago ("two days ago the 3:30 had 250k, which is almost twice yesterday's — it's volume significant"). The MOC feature (`moc_volume_ratio`) is within-day only.
- `prior_3day_box_width_pct`: The three-day inventory-build framing from mar-6. Wide prior-3-day range means inventory accumulating → distribution pending. Not currently computed.
- `confluence_level_count`: Number of reference levels within N ticks of the touch price. Apr-23 describes 5 levels stacking at the floor as high-conviction. Not computed.
- `moc_state` (actual): MOC field is absent from every JSONL payload. It cannot be used as a real-time feature in the live system until the indicator emits it in the heartbeat payload.

### 2.3 The Sharpe 9 Inflation Problem

The walk-forward backtest reports Tier-A ES Sharpe of 6.74, Portfolio Sharpe of 10.06. The robustness module corrects this to 6.62 standalone after zero-fill. The backtest infra audit documents why these numbers should be treated with skepticism:

1. **The SMA20 trail mechanically smooths equity curves.** A ratchet trail that only moves in one direction (tightening) produces smooth equity because losing trades get cut before they become large losers. This is a structural property of the label, not of AM's edge. The smoothing inflates Sharpe independently of whether there is any real alpha.

2. **Fill rate bias is unmodeled.** Every event in the training set and backtest is assumed to fill at the level price. Real limit orders at popular Baiynd levels (ORH, VWAP, prior 3:30 H/L) have estimated 30-60% fill rates for retail-sized limits. The spec's own documentation says: "If live fill rate is 50% on Tier-A signals, expected net drops from $775K/yr to roughly $380K/yr and Sharpe from ~10 to ~3-4." That is a 60-75% Sharpe haircut from fill rate alone.

3. **Signal clustering.** Monte Carlo drawdown analysis shows realized DDs are 1.5-7× worse than MC p99 under a random-shuffle assumption, because trades cluster intra-day and across instruments (when ES fires, NQ likely fires the same session). Clustered signals mean the portfolio Sharpe is not achieved by independent coin flips — it is achieved by correlated bets on correlated instruments during similar market conditions. In a bad patch, all four instruments underperform simultaneously.

4. **The V2_4 indicator's own ledger is 41.7% win rate, PF 0.94 over the same period.** The Python runner backtest claims 94% win rate and Sharpe 10. Both claim to describe "the Baiynd method." The 54-percentage-point win-rate discrepancy is not noise. The indicator includes mode logic (FADE vs TREND), signal caps, cooldown timers, and retrace-side filters that the Python runner sim ignores. The Python runner sim fires every event the model tiers. The indicator fires 1 in 741 qualifying touches. The right comparison does not exist yet — re-scoring the indicator's actual 84 trades through the M2 model is the single most important missing analysis.

The implication for any ML enhancement: validate against realized Sharpe 2-3 and Profit Factor 2.5-4 (AM's stated profile target), not against the current backtest's Sharpe 9. Any ML improvement that cannot demonstrate improvement against the indicator's actual signal stream is producing theater, not results.

### 2.4 Decision Engine: Simple 2-of-2 Agreement Combiner

The current `combine_v2.py` answers exactly one question: does M2's tier and direction agree with M1's best-across-windows tier and direction? The output is `agree ∈ {0, 1, 2}`. There is no confidence weighting, no soft vote, no output for "M1 and M2 disagree strongly, therefore abstain."

Issues with this design:

1. **M1 and M2 are architecturally incommensurable.** M1 (`ml_scorer_rt`) is a pre-computed signal library with time-window labels and king-bar matching. M2 (`pattern_scorer_rt2_1`) is a per-touch regression on runner R-multiple. They are measuring different things. Forcing them into a binary agree/disagree treats fundamentally different signal types as if they were equivalent votes.

2. **M1 downgrades via absence.** If M1 has no matching rule for a given (slot, direction, date), the combiner returns `agree=0` regardless of M2 tier. This means the combiner is more selective than M2 alone — but for the wrong reason. A valid M2-tier-A setup gets blocked by M1's silence, not by M1's active disagreement. In a live system without a `/decide` HTTP endpoint, the spec recommends bypassing the combiner entirely for v1 and using M2 tier directly.

3. **The combiner has no uncertainty output.** The most valuable signal from ensemble disagreement is not "they agree" but "they disagree significantly." When M1 says strongly short and M2 says strongly long, that is not a 0 — it is a risk signal that should trigger abstain or halve-size. The current combiner maps this to `agree=0` (no action), which is correct behavior but discards the information that could drive the abstain head.

4. **The combiner is a Python module, not a network service.** There is no `/decide` HTTP endpoint. NT8 cannot query it. The combiner is offline-only.

A better design for v2: a trained meta-model that takes (M1 score, M2 predicted_R, feature vector subset, disagreement delta) as inputs and outputs a combined probability of success and a sizing recommendation. This is an effort-L item and should come after the label fix and feature additions.

---

## Section 3. Concrete Enhancements — Ranked

### 3.1 Re-label M2 with AM's Correct Exit Doctrine (MUST DO FIRST)

**Effort: M. Prerequisite for everything else.**

Replace `realized_R_runner` (SMA20 trail) as the training target with a Fibonacci-level-based label that matches AM's actual exit doctrine.

The minimum viable re-label: use `realized_R_first_target_only` (already computed and stored in the labels parquet) as the primary training target. This approximates AM's level-to-level exit at the first structural level in the trade direction. It is already available. A full pipeline retrain on this label can be run without any new label generation code.

The full correct re-label: implement a `_simulate_fibonacci_runner` function in `label_builder.py` that:
- At entry, compute the 4 AM candle height → derive Fibonacci 100%, 150%, 200%, 250% extension targets
- Gate which level to target based on 200-SMA slope magnitude (to be thresholded by ML — start with a continuous slope feature and let the model learn it)
- Simulate exit: 50% at 100%, hold remainder, exit at 150% or 200% depending on slope class, with a time cap at 15:00 ET
- Return `realized_R_fib_exit` as the new training label

This re-label work is approximately 2-3 days of engineering, dependent on prior discussion with AM to confirm the slope threshold. It invalidates all current model weights and tier thresholds.

Expected consequence: the Sharpe will drop from 9-10 to something more realistic (estimated 3-5 before fill-rate correction, 2-3 after). This is the correct outcome. It means the model is now trained on what AM actually does.

### 3.2 Add Transcript-Derived Features

**Effort: M.**

The 10 highest-priority features to add from the transcript analysis:

1. `dist_to_1pm_candle_wick_high / _low` — 1:30 PM prior-day candle H/L (5 lines in event_builder, 2 lines in feature_builder)
2. `dist_to_pivot_P / R1 / R2 / R3 / S1 / S2 / S3` — Woody's pivots (requires a pivot calculator using prior-day H/L/C; standard formula, ~30 lines)
3. `news_candle_wick_present` + `dist_to_news_candle_wick` — intraday volume-outlier detection (volume > max(prior 9:30 vol, prior 3:30 vol)); requires volume data per 1-min candle, which is in the CSV
4. `sma200_slope_magnitude_30m_pct` — 30-min 200-SMA delta 9:30 → 9:30, normalized by ADR20 (already computed as a sign; adding magnitude requires storing the prior day's 9:30 SMA200 value, ~10 lines)
5. `body_stack_node_count` — count of strictly stacked master candle body pairs in the trade direction (0-3); approximates day-type quality as a continuous feature
6. `pattern_b_armed` — boolean: is the current touch at a level that has a Pattern B state of Armed or Consumed? (requires parsing the JSONL PatternB state, or approximating from the JSONL `direction` + bar geometry)
7. `opening_range_pts` — 9:30 1-min candle range in absolute points (existing `opening_range_width_pct` converts to this trivially given the entry price)
8. `first_1min_volume_fraction` — 9:30 1-min volume / 20-day average 9:30 1-min volume (requires building a per-session 9:30 1-min volume lookup from the 1-min bars)
9. `confluence_level_count_5tick` — number of tracked reference levels within 5 ticks of the touch price (computed from the 15 existing distance features)
10. `price_above_r3_flag` — binary: is the entry price above R3 (Woody's)? (trivial once pivots are computed)

### 3.3 Add an Abstain Head

**Effort: M.**

Train a binary classifier P(abstain | feature_vector) as a second output head alongside the regression target. The abstain label can be constructed retrospectively:

- Label a touch as "should have abstained" if: (a) the realized R under the correct exit doctrine is negative AND the pre-touch features include any of: MOC Gray, first-1-min volume below threshold, opening range > 10 pts, no body stacking, flat VWAP, or above R3.
- The threshold for what "should have abstained" means can be tuned — start with "bottom-decile outcomes" per regime class.

At inference time, if `P(abstain) > 0.60`, suppress the scoring output regardless of predicted R. This is the ML equivalent of AM's "if everything doesn't line up, I'm not trading."

The abstain head does not need to be a separate model — it can be added as a second output to the existing LightGBM Huber regressor using a multi-output approach, or trained as a separate LightGBM binary classifier using the same feature set.

### 3.4 Add a Sizing Head

**Effort: M-L.**

Train a regression `f(features) → optimal_risk_fraction` where the target is not a simple function of AM's rules but is derived from calibrated historical outcomes. The idea: given a feature vector, what fraction of normal risk (1.0 = full Green, 0.5 = Orange) would have maximized risk-adjusted return over the training set?

In practice, this is a quantile regression trained on `realized_R / max_R_possible` as the dependent variable, with features as inputs. The output maps to a [0.0, 1.0] sizing multiplier. Combined with the rule-based Green/Orange/Gray (which enforces hard floors), the sizing head provides a continuous modulation.

The apr-10 transcript gives the conceptual anchor: "if the 50 converges with the VWAP and the 200 and the 200 is pointing up, it's going to rocket back to the top — that's going to be my sweet spot, place where I potentially add." That convergence state is a high-sizing signal. ML can learn which feature combinations historically co-occur with large winner R and thus deserve larger sizing.

### 3.5 Add a Regime Classifier

**Effort: M.**

Train a multinomial classifier over a 7-class regime taxonomy:
- LongTrend (body stack 3/3, steep 200-SMA up, MOC Green)
- ShortTrend (body stack 3/3, steep 200-SMA down, MOC Green)
- CautiousLong (partial stack, 200-SMA up, cautious signals)
- CautiousShort (partial stack, 200-SMA down, cautious signals)
- SidewaysUp (no stack, 200-SMA flat-to-up, range edges trade)
- SidewaysDown (no stack, 200-SMA flat-to-down, range edges trade)
- SidewaysFlat (no stack, 200-SMA flat, reduced size or no trade)

Training labels come from V2_4's `ClassifyAMDayType` output (after the vocabulary mismatch is fixed — the JSONL audit found `congestion/extended/trending/unknown` rather than the spec strings). The JSONL data shows that 7 of 103 sessions have heartbeats; forward collection of 30-50 more V2_4 sessions is needed before this is a meaningful training corpus.

For now, this classifier can be bootstrapped by labeling the historical 1-min bar sessions using a deterministic rule (body-stack computation on historical data) to generate pseudo-labels, then refining with the JSONL ground-truth sessions as a calibration set.

The regime classifier outputs feed into M2's confidence calibration: Tier-A signals on a SidewaysFlat day deserve lower trust than Tier-A signals on a LongTrend day. This creates a two-dimensional signal quality space (regime x M2 tier) that is more expressive than either dimension alone.

### 3.6 Anomaly Detection

**Effort: M.**

An out-of-distribution score per bar using an autoencoder or Mahalanobis distance in the 71-feature space. Training: the pre-2024 historical bar-level feature distributions. At inference time, compute the OOD score for each candidate touch event's feature vector. If the score exceeds a threshold (e.g., p99 of training-set reconstruction errors), suppress the M2 scoring output and flag the session as "anomalous — do not trade."

Practical implementation: a shallow autoencoder (3-layer: 71 → 32 → 16 → 32 → 71) trained on the pre-2024 feature set in unsupervised mode. Reconstruction error as the anomaly score. The training is independent of the label fix and can be done in parallel.

This component matters most for the autonomous trading loop: it is the system's ability to recognize when it is in unknown territory and halt rather than extrapolate.

### 3.7 Real-Time Inference Engine

**Effort: L. Gating item for any live use of M2.**

The DEPLOY.txt file explicitly states: "KNOWN LIMITATION (planned phase 2): `/score` requires the caller to compute features. Without a live feature engine, V2_4 cannot call M2 in real time." The only working scoring path today is `/score_lookup` — a post-hoc identity join into pre-computed parquet.

A live feature engine must:
1. Maintain a 1-min bar cache per instrument (at least 200 bars for SMA200 computation)
2. Compute the 71 features (+ new features from 3.2) from the bar cache at touch time
3. Accept a touch event payload from V2_4 (instrument, session_date, event_ts, level_touched, entry_px)
4. Return `{predicted_R, tier, abstain_prob, regime_class}` within 200ms

The six new overnight geometry features added in rt2_1 (globex_open, europe_high/low, entry_extension_from_overnight_low_adr, etc.) all require state that V2_4 already holds — the gap is purely that nobody assembles and sends these values to the Flask service.

Until this exists, M2 cannot be used in live trading. It can only score retrospectively. This is the item that converts M2 from a research tool into a trading tool.

---

## Section 4. Beyond AM's Discretion — Uses She May Not Have Considered

### 4.1 Adversarial Robustness: Detecting Stop-Runs and Front-Running

AM manually recognizes when the market is "shaking the trees" (mar-6) and running stops at round-number pivots (apr-8: "they're front running that right now"). She handles this with the "second prettiest girl" entry style — waiting for the second probe, staging limits away from the round number.

ML can quantify this. An adversarial pattern classifier trained on "how often does the first wick fail vs. become a real break at a given level type?" would generate a level-specific "shake probability" feature. At a round-number pivot (6800, 6900), the shake probability is high — reduce size or require a confirmed reclaim before entry. At a structural overnight candle level (4 AM low), the shake probability is lower.

This is not replacing AM's judgment — it is operationalizing and scaling it across all four instruments simultaneously.

### 4.2 Cross-Instrument Signal Encoding

The current cross-market features are EOD proxies: `daily_dxy_direction`, `daily_spy_direction`, `daily_bond_direction`. These are yesterday's directional signals, not today's intraday co-movement.

AM actively uses intraday CL-ES and DXY-ES correlation (apr-8: "when DXY/CL correlate strongly → size up; when correlation breaks → ignore"). She also uses SPY pre-RTH as a direction confirmation (apr-9: "SPY carries more volume than ES futures and positions differently because of zero-DTE flows").

A rolling 30-minute ES-DXY correlation feature, computed from the same 1-min bar data, would be a significant addition. The 1-min CSVs for DXY and SPY are not in the current data set (it has VIX, TNX, IRX, SPX, NDX, DXY, VXN, FVX at daily resolution only). Acquiring intraday DXY and SPY data at 1-min resolution is the infrastructure prerequisite.

### 4.3 Time-of-Day Microstructure

The calendar features in the 71-feature set include `hour` and `minutes_since_rth_open`. But the microstructure differences are more nuanced than a continuous hour variable captures.

Apr-10 names specific algo windows: "9:04, 9:02, then 9:14 to 9:18, and then 9:24 to 9:27 — for some reason the algos pick those places up." Apr-8: "23,000 contracts at 9:30 and it was directional straight down." Apr-16: "3:30 PM to 4:00 PM is where institutional flow is dramatically important."

An ML model with sufficient training data can learn these time-of-day patterns better than manual bins. A cyclic time encoding (sin/cos of minute-of-day) combined with session-phase indicators (pre-RTH / RTH-open / RTH-midday / RTH-close) would capture these patterns more cleanly than the current `hour` integer feature.

The specific 9:30-9:45 window has demonstrably different fill dynamics and signal quality than 12:00-13:30. ML can learn this empirically.

### 4.4 Economic Event Context

The Python pipeline has a placeholder for a `NEWS_CALENDAR_CSV` that covers FOMC, NFP, CPI, and PPI. The file is referenced in `config.py` with a graceful fallback when absent. Only the CL EIA Wednesday window (10:25-10:45) is actively coded as a blackout.

An automated economic calendar integration — downloading a machine-readable event calendar weekly and flagging event-proximity features (`minutes_to_next_fomc`, `is_nfp_week`, `is_cpi_day`) — would give M2 the ability to reduce scoring confidence during high-uncertainty news windows without requiring manual configuration.

AM's volume analysis (apr-23: "that 8 PM candle had a ton of volume — the SEC news") shows she uses volume spikes as news proxies. The ML complement is to feed this as a structured feature rather than relying on pattern recognition.

### 4.5 Volume Profile / Market Depth (Specifically for AM)

The apr-16 session has the most definitive statement on this: *"Value area high/low — it's freaking bananas. Every platform gives you a different number. That's why Edgeful doesn't use it."* AM explicitly de-recommends platform-native value area computation for automation.

However, she does not dismiss the concept of volume concentration — she uses 3:30 candle volume for MOC validation, news-candle volume for level significance, and first-1-min volume for opening conviction. What she rejects is the platform-computed value area, not the underlying idea.

A custom pipeline-built volume profile, computed directly from the same 1-min bars used for everything else, would be self-consistent and platform-independent. Features like `distance_to_volume_node_below` (nearest price level with above-average volume concentration to the downside) and `volume_gap_size_above` (price distance to the nearest low-volume zone above) approximate what market depth provides without depending on any platform's proprietary VAH/VAL computation.

This is a medium-priority enhancement for the feature set, not a prerequisite for the label fix.

### 4.6 Behavioral State: Session-Level "Stickiness"

How trendy has the current session been up to this point? AM reads this viscerally — "today is a trend day, dips are buys" vs. "today is a mosh-pit, fight at the edges." ML can quantify this as a rolling session feature:

- `autocorrelation_1m_close_lag5` — is recent 1-min price movement positively autocorrelated (trending) or negatively (mean-reverting)?
- `session_atr_ratio` — today's realized ATR (close-to-close, last N bars) relative to the 20-day average ATR; above 1 = expanding range, below 1 = contracting
- `session_high_low_trend_slope` — linear slope of the sequence of 30-min highs and lows since the RTH open; positive and steep = trend in progress

These three features together approximate the "what kind of day is this becoming?" read that AM makes at each decision point. They update as the session progresses, making them genuinely intraday-regime-sensitive.

### 4.7 Regime Change Detection: Identifying Mid-Session Shifts

AM's OODA loop framing (apr-9) is explicit: "the orientation says which way is the current moving and who has the power." She updates her thesis on each new 30-min print. A trend day can become a sideways day at any time.

ML can detect regime transitions as they happen: a change-point detection model running on the rolling session features (4.6) that signals "the session microstructure has shifted from trend to range." This is a complement to the regime classifier (3.5), which classifies the session's starting regime; the change-point model updates the regime estimate intraday.

This enhancement is relevant for the runner-target decision: if the session regime shifts from LongTrend to SidewaysFlat at 11:00 AM, the 200% Fibonacci runner target should downgrade to 150% or first-target-only. The existing pipeline has no concept of intraday regime change.

---

## Section 5. ML for the Autonomous Trading Loop Specifically

### 5.1 Online Learning: Do Not Update Intraday

The model should NOT update intraday. The training set has thousands of events per instrument; any single intraday session produces at most 2-5 qualifying touches. Online learning on such thin data would rapidly overfit to the most recent session's outcome, catastrophically in an adversarial market.

The appropriate update cadence is offline retrain: weekly or monthly, with a rolling window (e.g. expanding window from 2012, or a 3-year rolling window refit quarterly). AM herself describes this cadence (apr-16): "intraday models: 3-6 week retraining cycle with weekly drift check." The walk-forward methodology already validates this pattern; the missing piece is automating the retrain and deployment pipeline.

### 5.2 Model Monitoring: Distribution Drift Detection

The walk-forward uses a hard 2024-01-01 cutoff. We are now in April 2026 — over two years of held-out data with no refit. The model may have drifted. The appropriate monitoring approach:

- Track per-feature rolling mean and variance over the last 20 trading sessions
- Compare to training-set feature distributions using Population Stability Index (PSI) per feature
- Alert when PSI > 0.2 on any high-importance feature (the six overnight geometry features added in rt2_1, sma200_slope_magnitude, body_stack_node_count)
- Trigger a scheduled refit when PSI alert is active for more than 3 consecutive sessions

This monitoring infrastructure is an effort-M item that should be part of the production deployment, not an afterthought.

### 5.3 Confidence Calibration

The current M2 regressor outputs `predicted_R` on an uncalibrated scale. The tier cuts (A=p85, B=p70, C=p50 of validation-set predictions) convert continuous scores to discrete tiers. The Spearman correlations on the OOS set (0.46 ES, 0.47 NQ, 0.41 CL, 0.33 GC) confirm rank-order is correct — high-predicted-R events do outperform low-predicted-R events. But the absolute magnitude of `predicted_R` is not calibrated to actual realized R.

Calibration matters for the sizing head (Section 3.4): if `predicted_R = 1.5` means the model expects a 1.5R win but the actual historical 90th-percentile for that score is 0.8R, the sizing model would over-allocate.

Isotonic calibration (already used in M1) applied to M2's output would convert `predicted_R` to a calibrated expected-R estimate. Brier score decomposition (reliability, resolution, uncertainty) would quantify calibration quality. Both are 1-day engineering tasks.

### 5.4 Ensemble Disagreement as a Risk Signal

When M1 and M2 disagree strongly, that disagreement is itself informative. The current combiner maps disagreement to `agree=0` (no action). A better use of disagreement:

- Strong M2 long + strong M1 short = conflicting signals = abstain or reduce size to 25%
- Strong M2 long + M1 silent = M2-only signal = use M2 tier at face value (no penalty for M1 silence)
- Strong M2 long + strong M1 long = high-confidence signal = full-size permitted

Quantifying M1-M2 disagreement as a feature in the meta-model (Section 2.4) operationalizes this. The signal is: disagreement is a risk indicator, not just absence of agreement.

---

## Section 6. The rt2_1 → rt2_2 (or V3) Recommended Path

This is the ordered sequence of work units that converts the current pipeline from "impressive but mis-aimed" to "correctly aimed at AM's actual strategy":

**Step 1 — Re-label (MUST BE FIRST)**
Retrain M2 on `realized_R_first_target_only` immediately (existing label, zero new engineering). This removes the SMA20 trail distortion. Accept that Sharpe will drop to a realistic range. Validate against the indicator's 84-trade ledger.
- Effort: S (use existing label)
- Unblocks: everything below

**Step 2 — Run the missing measurement**
Re-score the 84 indicator trades (Mar 13–Apr 21 2026) through the re-labeled M2. Report: what would Tier-A have kept, what were those trades' actual outcomes, what is the Sharpe of that filtered subset vs. the unfiltered indicator?
- Effort: S
- Output: the first defensible "ML helps AM" data point

**Step 3 — Add transcript-derived features**
Add the 10 features from Section 3.2 starting with: 1:30 PM candle levels, Woody's pivots, sma200_slope_magnitude_30m_pct, body_stack_node_count, first_1min_volume_fraction.
- Effort: M
- Expected: +3-8% Spearman on OOS set; new regime-sensitive feature importances

**Step 4 — Implement the Fibonacci label**
Build `_simulate_fibonacci_runner` in `label_builder.py`. Re-label using the multi-target R approach: `R_fib_first_target` + `R_fib_runner_conditional`. Retrain M2 on the correct exit doctrine.
- Effort: M (requires AM confirmation of slope threshold, or treat as a continuous feature)
- Unblocks: sizing head (the sizing model needs a correctly-labeled reward signal)

**Step 5 — Add abstain head**
Binary classifier P(abstain | features) as a second output. Training label derived from rule-based abstain conditions (MOC Gray, opening range > 10 pts, etc.) intersected with negative outcome events.
- Effort: M

**Step 6 — Add sizing head**
Continuous sizing multiplier regression. Target: `optimal_risk_fraction` derived from Fibonacci-label realized R distribution.
- Effort: M-L

**Step 7 — Rolling walk-forward retrain schedule**
Automate quarterly retrain with expanding window, drift check weekly. Add PSI monitoring per high-importance feature.
- Effort: M
- This converts the pipeline from "trained once in 2024" to "continuously adapted"

**Step 8 — Build the live feature engine**
Port `feature_builder.py` into a streaming engine that holds a 200-bar 1-min cache per instrument and computes the feature vector at touch time. Wire to the Flask `/score` endpoint.
- Effort: L
- This converts M2 from a backtest tool to a live trading tool

**Step 9 — Validate against AM's profile target**
Run the fully re-labeled, re-featured model through the indicator's actual signal stream. Report Sharpe, Profit Factor, win rate against the target of Sharpe 2-3, PF 2.5-4. If not met, diagnose before proceeding to autonomous execution.
- Effort: S (analysis only)

---

## Section 7. What ML Cannot Solve

This is the most important section.

**The fundamental constraint: ML is a multiplier, not a substitute for missing rules.**

If V2_4 is not generating signals for a class of setup AM trades, no ML scoring of the signals V2_4 does generate will recover those missed setups. ML can filter a signal stream; it cannot create signals from nothing.

The specific missing rules that ML cannot fix:

- **Fibonacci exit targets.** V2_4 has no Fibonacci exit layer. M2 is trained on SMA20 trail exits. Even after re-labeling, if V2_4 does not place limit orders at the Fibonacci levels, the autonomous system will not execute at those levels. This is an indicator code change, not an ML change.

- **Pattern B (look-below-and-fail).** V2_4 has Pattern B scaffolding but the JSONL data shows 43% of qualifying touches are Pattern B events that currently produce zero signals. ML cannot score events that V2_4 never emits as signals. Pattern B must be wired in V2_4 first.

- **Bidirectional FADE mode.** V2_4 currently fires FADE in one direction (slope direction only). The apr-23 transcript says AM trades both edges on sideways days. Until V2_4 fires both-directional FADE, ML will never see the other direction's signals.

- **Woody's pivots as levels.** These are not in V2_4's level tracking. ML can weight a pivot-distance feature, but if V2_4 never fires a touch event when price hits a Woody's pivot, M2 will never score it.

- **The 1:30 PM candle.** Same issue. V2_4 tracks the 3:30 candle; the 1:30 candle is absent. ML cannot compensate.

- **MOC field in the JSONL.** The data audit found MOC is absent from every heartbeat and signal payload. Until V2_4 emits `moc_state` in the heartbeat, any ML model that needs MOC as a real-time feature must infer it from offline pre-computed data rather than live state.

- **The 0.27% signal conversion rate.** The JSONL data shows 741 qualifying touches and 2 signals in six months — a 0.27% conversion rate. Even if ML perfectly scores every qualifying touch, the system can only trade signals V2_4 has decided to emit. The signal suppression is almost entirely pre-ML, at the V2_4 rule-gating layer.

The strategic principle: fix the rules before scaling the ML. Every developer hour spent on ML enhancements while V2_4 silently suppresses 99.73% of qualifying touches is an hour that cannot recover those suppressed setups. The indicator's missing rules must be added first. ML then multiplies whatever the indicator produces.

AM herself stated this explicitly (apr-24, lines 269-273): *"if we can create our first successful auto-iteration that actually works, then we can use multiple machine learning models to actually start adding nuances that would improve it... find a lot of trades and then have machine learning veto some of them."* The prescription is: indicator generates a broad candidate set, ML vetos the bad ones. Today the indicator generates almost no candidates, and ML vetos that almost-nothing.

---

## Recommended Sequence Summary

```
DO FIRST (blocker for all ML work):
  A. Fix V2_4 rule gaps: Pattern B, bidirectional FADE, Fibonacci exit targets,
     1:30 PM candle, Woody's pivots → expand signal universe from 2 signals/6mo
     to an operationally meaningful candidate set

DO SECOND (fix the ML foundation):
  B. Re-label M2 on realized_R_first_target_only (existing label, no new code)
  C. Run the missing measurement: re-score indicator's 84 trades through re-labeled M2

DO THIRD (improve the ML inputs):
  D. Add 10 transcript-derived features (1:30 candle, pivots, slope magnitude,
     body stack count, first-1-min volume, Pattern B state)
  E. Implement Fibonacci label with multi-target regression

DO FOURTH (expand ML capabilities):
  F. Add abstain head
  G. Add sizing head
  H. Add regime classifier (requires 30-50 more V2_4 sessions with correct vocab)
  I. Add anomaly detection

DO FIFTH (production hardening):
  J. Build live feature engine (stream 1-min bar cache → feature vector at touch time)
  K. Wire live feature engine to Flask /score endpoint
  L. Add PSI drift monitoring and quarterly retrain automation

VALIDATE CONTINUOUSLY against AM's profile targets:
  Sharpe 2-3, Profit Factor 2.5-4, not Sharpe 9
```

The current pipeline is well-engineered. Its architecture is sound. Its target label is wrong, its features are incomplete, and its headline metrics reflect a mechanical policy AM explicitly rejects. Fix those three things, in that order, and the ML stack becomes a genuine expression of AM's strategy rather than a statistically impressive approximation of something she would never trade.
