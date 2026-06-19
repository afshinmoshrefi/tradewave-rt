# AM Codex Architecture Memory

Last updated by Codex: 2026-04-29

Purpose: persistent Codex memory for Anne-Marie Baiynd rule synthesis, NT8 indicator state, and ML scorer integration. Read this before future AM/V6/pattern_scorer_rt2 work.

This is engineering/process documentation, not financial advice. Treat all trading changes as simulation/paper-trading work until explicitly validated.

## Source Paths

- Transcript folder: `C:\seasonals\baiynd_autotrader\video transcripts`
- Codex transcript synthesis: `C:\seasonals\baiynd_autotrader\video transcripts\AM _rules_by_codex.md`
- Current NT8 indicator under discussion: `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMTradeCockpitV2_6.cs`
- Claude/V5 original copied to V6: `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMTradeCockpitV2_5.cs`
- Current scorer repo/service: `C:\seasonals\pattern_scorer_rt2`
- Old shadow observer strategy: `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Strategies\AMShadowObserverV1.cs`
- Quarantined L2/L3 strategy draft: `C:\seasonals\baiynd_autotrader\v25_rebuild_2026-04-27\quarantine\AMTradeStrategyV1.cs`

## User Architecture Intent

Afshin wants:

1. An NT8 indicator that selects most or all plausible AM strategy candidates.
2. A machine-learning layer that scores those candidates and filters lower-quality trades.
3. Possible ML outputs:
   - Binary accept/reject filter.
   - Target points or target class.
   - Stop-loss distance or stop recipe.
4. Separation from Claude work by using V6 for Codex work.
5. Codex memory files must include `_codex_` in the filename.

This architecture is directionally sound if the indicator remains high-recall and the ML/strategy layer owns precision, ranking, stops, targets, sizing, and safety gates.

## Minimal AM Rules From Codex Transcript Pass

The Codex rule file was built from all eight transcript files and intentionally ignored prior Claude rule docs for the first pass.

Core rules:

- Use 30-minute structure and 1-minute execution.
- Build the day map from key time boxes: prior 3:30-4:00 p.m. institutional close, 6:00-6:30 p.m. Globex open, 4:00-4:30 a.m. Europe open, 9:30-10:00 a.m. RTH open, and 9:30-9:31 a.m. 1-minute open.
- Decide day type first: trend up, trend down, sideways/congested, or no-trade.
- Clean trend means box bodies stair-step in the trade direction. Overlap/inside behavior means sideways or mixed.
- In trend, trade pullbacks/bounces in the direction confirmed by boxes, 50/200 SMA, VWAP slope, and momentum.
- In sideways, trade only edges, not the middle.
- Use limit orders. Do not chase.
- Default entry is a touch, brief break, recover/fail, and proof at a known level.
- Every trade needs known risk and known destination before entry.
- Beginners should use hard protective stops.
- Do not treat trailing stops as the default AM method. The transcript-based doctrine is level A to level B, then reassess.
- One to three good trades is enough; no-trade days are valid.

Important AM levels/features to keep in system design:

- Prior institutional close high/low/body and MOC validation.
- Globex high/low/body.
- Europe high/low/body.
- RTH opening range and 1-minute 9:30 opening candle.
- Midnight high/low/mid, especially for NQ.
- VWAP and anchored VWAP as context/permission, not blind entry reasons.
- 50 SMA and 200 SMA on 30-minute and 1-minute charts.
- Woody/standard pivots including R3/R4 extension/exhaustion context.
- News wick levels from unusual high-volume candles.
- Pattern A: level retest.
- Pattern B: look below/above and fail.

## Current V6 Indicator Facts

As of 2026-04-29 after Codex isolation pass:

- `AMTradeCockpitV2_6.cs` is no longer byte-for-byte identical to `AMTradeCockpitV2_5.cs`.
- `AMTradeCockpitV2_6.cs` now declares class `AMTradeCockpitV2_6`.
- Generated NinjaScript wrappers now expose `AMTradeCockpitV2_6(...)` factories and `cacheAMTradeCockpitV2_6`.
- `NinjaTrader.Custom.csproj` now includes both `Indicators\AMTradeCockpitV2_5.cs` and `Indicators\AMTradeCockpitV2_6.cs`.
- V6 display/log identity was changed to V2_6, JSONL schema version `v26.0`, state key `v2_6_version`, and candidate drawing tags `V26Cand_`.
- V5 was left untouched; its SHA256 stayed `5AA0A9052ECC197BC0D908669E82F25313DAFFD1AED751CCA7D4DBE8427BC897` during the isolation pass.
- Command-line compile could not be run because no .NET SDK or MSBuild executable is installed in the shell environment.
- Afshin confirmed on 2026-04-29 that V6 compiles in NinjaTrader and displays on both 30-minute and 1-minute charts.
- Runtime output check on `C:\seasonals\cockpit\sessions\2026-04-29\events.jsonl` found `v26.0` lines with candidates, box captures, heartbeats, Pattern B state changes, and abstains.
- When V6 is loaded on both 30-minute and 1-minute ES charts with JSONL logging enabled, the shared daily JSONL gets duplicate candidate IDs. On 2026-04-29, Codex counted 1,475 `v26.0` candidate lines but only 740 unique candidate IDs. For validation, either log from only one V6 instance or add an explicit chart-instance/log-owner policy.
- On 2026-05-01 Codex added pre-touch watch rendering to V6: nearest key levels above/below price are labeled `SELL WATCH` / `BUY WATCH` before price arrives. This is chart-only and does not emit `candidate` events until price actually touches the level.
- The 9:30 one-minute opening high/low/mid (`RTH1MinH`, `RTH1MinL`, `RTH1MinMid`) were added to `BuildAllLevels()` so the opening one-minute low/high can be watched and emitted as candidates. This directly supports Afshin's "standing order on day open low" workflow.

V5/V6 design:

- It is explicitly an L1 pure-detection indicator.
- It emits `OnCandidate` with `CandidateEventArgs`.
- Legacy `OnTouch` and `OnSignal` are retained only for compile compatibility and are not fired by V5/V6.
- It intentionally does not make final trade decisions, issue exact signals, submit orders, or stage trades.
- Pattern A and Pattern B are both surfaced as candidates.
- It emits both LONG and SHORT interpretations around levels where applicable so L2 can choose.
- It logs candidates to JSONL and emits box_capture, heartbeat, abstain, error, and Pattern B state-change events.

Candidate feature vector currently includes many AM-rich fields:

- Day type 3-node and 4-node.
- Body overlap flags and large wick flags for master boxes.
- SMA200 slope delta/sign and SMA50 context.
- MOC ratio/state.
- VWAP and anchored VWAP context.
- Distances to master boxes, OR, pivots, prior days, VWAP/AnchVWAP.
- Bar shape, time-of-day, volume, ADR/europe width, phase/bias.
- Stop-distance proposal and target proposals.
- Institutional box and news-wick context.

Key gap: V6 features are not the same schema as `pattern_scorer_rt2` expects. They are AM-rich but not directly POST-compatible with the current Flask `/score` endpoint.

## Current pattern_scorer_rt2 Facts

Repo path: `C:\seasonals\pattern_scorer_rt2`

Packaged service path:

- `pattern_scorer_rt2\app.py`
- `pattern_scorer_rt2\scorer.py`
- `pattern_scorer_rt2\config.py`
- `pattern_scorer_rt2\models\*.txt`
- `pattern_scorer_rt2\models\*_meta.json`

Current live endpoint checked by Codex on 2026-04-29:

- `http://104.238.214.253:7677/health`
- Status: `ok`
- Service: `pattern_scorer_rt2`
- Version: `1.0.0`
- Instruments loaded: `CL`, `ES`, `GC`, `NQ`
- `lookup_enabled`: `false`
- `/info` reports target `realized_R_runner` and `n_features = 71`

Endpoints:

- `GET /health`
- `GET /instruments`
- `GET /tiers`
- `GET /info`
- `POST /score`
- `POST /score_lookup`

Important current limitation:

- `/score` requires a complete precomputed feature vector matching the model schema.
- `/score_lookup` is historical/replay style and depends on features parquet being present on the server. The live service currently reports `lookup_enabled=false`, so the old `/score_lookup` path is not usable live on that server state.
- A true live feature engine that computes the full model schema from raw 1-minute bars is not built in the packaged service.

Model:

- One LightGBM Huber regressor per instrument.
- Target is `realized_R_runner`.
- Direction is rule-gated by trend, not learned by the model.
- Tiers are based on predicted R:
  - A = top validation band.
  - B = next band.
  - C = next band.
  - `-` = below C.

Current live tier cuts:

- ES: A >= 0.3181344821696253, B >= 0.15320275038680187, C >= 0.04385634227132344
- NQ: A >= 0.393826474687523, B >= 0.22291249537764374, C >= 0.10075246921438719
- CL: A >= 0.28019447954862825, B >= 0.1552529432349777, C >= 0.06621300301088649
- GC: A >= 0.2635900954996955, B >= 0.12839204359981987, C >= 0.06359102964389098

Current required feature schema:

- 66 numeric columns plus 5 categorical columns, 71 total.
- Categorical: `level_touched`, `direction`, `trend_state`, `gap_category`, `approach_direction`.
- Numeric schema includes candle shape, 15 level distances and above flags, multi-timeframe direction, opening/gap context, MOC fields, EOD cross-market proxies, cluster/approach/volume fields, calendar fields, `europe_width`, `adr_20d`, and 6 overnight geometry fields:
  - `globex_open_vs_europe_high`
  - `globex_open_vs_europe_low`
  - `europe_high_vs_prior_inst_high`
  - `europe_low_vs_prior_inst_low`
  - `entry_extension_from_overnight_low_adr`
  - `pattern_6pm_below_4am_and_inst_long`

Big ML caveat:

- The current trained target is not the transcript-pure AM exit doctrine.
- It is a runner label: no first target, no partial exit, trail from entry using 30-minute SMA20, force-close at time cap.
- AM transcript synthesis says default AM method is level-to-level, not trailing stops.
- Therefore this model can still be useful as a setup-quality/rank filter, but it is not yet a model of exact AM entries/exits.

## Current NT8 Integration State

`AMShadowObserverV1.cs`:

- Lives in NT8 `Strategies`.
- Hosts `AMTradeCockpitV2_3`, not V5/V6.
- Subscribes to old `OnTouch` and `OnSignal`.
- Posts to `/score_lookup` at `http://104.238.214.253:7677`.
- Writes shadow JSONL.
- Does not submit orders.
- Forces live order submission off.

This observer is obsolete for V6 because V6 emits `OnCandidate` and does not fire `OnTouch`/`OnSignal`.

`AMTradeStrategyV1.cs`:

- Exists only in `v25_rebuild_2026-04-27\quarantine`.
- It is not present in `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Strategies`.
- It is intended as L2/L3 host for V5.
- It subscribes to `OnCandidate`, ranks candidates, applies heuristic/HTTP scorer, applies safety gates, and can submit orders.
- Its HTTP scorer request/response contract is not compatible with current `pattern_scorer_rt2` `/score`:
  - Quarantine strategy sends candidate identity-style JSON.
  - Current Flask `/score` expects full `instrument` plus `features` dict and returns a `results` list with `predicted_R`, `tier`, and `cuts`.
  - Current Flask `/score_lookup` is not enabled on the live endpoint.

## Recommended Architecture

Keep the layered architecture.

L1 - Candidate detector:

- V6 should remain high-recall and fail-open.
- It should surface every plausible AM candidate with rich context.
- It should not decide final entry/stop/target.
- It should not submit orders.

L2 - Scoring and selection:

- A strategy should host V6 and subscribe to `OnCandidate`.
- It should dedupe/rank candidates per bar, zone, and thesis.
- It should map V6 candidate/context into the scorer schema or call a new live feature engine.
- It should choose exact entry, stop, target, size, and abstain reason.
- It should emit explicit `signal` or `abstain` for every candidate.

L2.5 - AM trade-plan builder:

- Converts chosen candidate to a trade plan:
  - entry price
  - stop price or stop distance
  - T1/T2 target
  - target type: next level, Fibonacci 100/150/200/250, fade target, time exit
  - invalidation condition
  - size bucket
- This layer should be deterministic and explainable even if ML supplies the score.

L3 - Safety and execution:

- RTH/cutoff gate.
- Daily loss gate.
- Max losing trades.
- Cooldown.
- Position state and reconciliation.
- Margin/account guard.
- Manual kill switch.
- Connection/heartbeat guard.
- No live orders without explicit user confirmation and proven sim validation.

L4 - Telemetry and validation:

- Log every candidate, score, abstain, signal, fill, exit, slippage, and realized R.
- Measure fill rate for limit orders at AM levels.
- Compare live/paper outcomes to backtest on the same dates.
- Track feature drift and bad-day clustering.

## ML Roadmap

Best near-term use:

- Use ML as an accept/reject and ranking layer for V6 candidates.
- Start with Tier A only in sim/paper, then evaluate A+B after sufficient data.
- Keep the model as advisory until fill rates and realized R are measured.

Required before live ML execution:

1. Fix V6 version/class/project wiring.
2. Build a V6-to-RT2 schema adapter or real-time feature engine.
3. Replace old `score_lookup` integration with current `/score` or deploy lookup parquet if replay-only.
4. Align model labels with the traded exit policy.
5. Paper trade and log every candidate/score/fill/outcome.

Suggested model heads:

- Setup-quality regression: expected R under the actual execution policy.
- Binary veto/classifier: probability of stop-before-target or probability realized R > 0.
- Target head: next structural level vs fib 100/150/200/250 vs fade target.
- Stop head: Europe width, trigger candle width, box width, ADR-clipped stop, or learned multiplier.
- Size head: full/reduced/skip or continuous risk multiplier.
- OOD/anomaly head: stand down when features are outside training distribution.

Top risks:

- Current model target uses SMA20 runner, not AM level-to-level doctrine.
- Backtest assumes level-touch fills; live limit fill rate is the major unknown.
- Fractional contract sizing in backtests does not match live futures sizing.
- Trades cluster by day and across correlated instruments.
- Candidate explosion can overtrade unless L2 dedupes by thesis/zone.
- Service/docs drift exists: local docs mention 65 features; live `/info` reports 71 features.

## Open Engineering Questions

- V6 has been made a true separate class `AMTradeCockpitV2_6`; future Codex work should edit V6 and leave V5 as the Claude baseline unless Afshin says otherwise.
- Should the first ML integration use current `realized_R_runner` model only as a filter, or retrain first on AM-style level-to-level/fib labels?
- Should live inference compute features in NT8, in a local Windows Python sidecar, or in the remote Flask service?
- What exact AM exit policy should be modeled first:
  - first structural target only,
  - fib 100/150/200/250 ladder,
  - partial at T1 then runner,
  - or current SMA20 runner for continuity?
- What is the hard limit on trades per day and per correlated group (ES/NQ especially)?
- Should VWAP/AnchVWAP be candidates, permission/context features only, or both with strong L2 penalty?

## 2026-05-01 V6 Direction Filter Note

- Afshin identified direction as a key AM filter: Long, Short, or Sideways.
- Codex added this to V6 as an explicit L1 context signal, not as a hard candidate gate.
- `AMTradeCockpitV2_6` now exposes public enum/property `AMDirectionFilter` / `CurrentDirectionFilter`.
- Direction is derived from the AM day-type stack first:
  - `LongTrend` and `CautiousLong` -> `Long`
  - `ShortTrend` and `CautiousShort` -> `Short`
  - `Sideways` -> `Sideways`
  - if day type is unknown, fall back to institutional-box bias (`Long`, `Short`, `Neutral` -> `Sideways`)
- JSONL now records `direction_filter_change`; heartbeat and candidate feature vectors include `direction_filter`.
- Candidate feature vectors also include `direction_filter_allows_candidate` so L2/ML can penalize or reject off-filter trades without L1 hiding them.
- The diagnostic panel displays `Direction filter: Long/Short/Sideways/Unknown`.
- Pre-touch watch labels use the filter visually:
  - `Long` shows buy-watch levels only.
  - `Short` shows sell-watch levels only.
  - `Sideways` or `Unknown` shows both sides.
- This preserves the high-recall L1 architecture: raw candidate detection still emits both long and short touches; the filter is visible context and L2 input.

## 2026-05-01 V6 Codex Review Note

- Review artifact: `C:\seasonals\baiynd_autotrader\AMTradeCockpitV2_6_codex_review.md`.
- Codex patched the generated NinjaScript wrappers so `ShowPreTouchCandidateLevels` is included consistently in indicator, Market Analyzer, and Strategy helper methods.
- Static checks passed:
  - V6 class/name/project include checks.
  - brace balance.
  - NinjaScript property wrapper coverage.
  - direction-filter source contract.
  - no order-routing tokens in V6.
  - V5 SHA256 unchanged: `5AA0A9052ECC197BC0D908669E82F25313DAFFD1AED751CCA7D4DBE8427BC897`.
- Local compile could not be completed from shell: the machine has no .NET SDK/MSBuild capable of loading the SDK-style NT8 custom project; old .NET Framework MSBuild returns MSB4041.
- High-priority remaining limitation: `PersistStateJson()` writes state, but `TryRestoreStateJson()` only logs that state exists and does not rebuild Pattern B `levelWatchStates`. Do not rely on Pattern B continuity across NT restarts until restore is implemented and replay-tested.
- Operational data note: if V6 is loaded on both 30-minute and 1-minute charts with logging enabled, telemetry duplicates are expected. Use one logging owner instance; set visual-only instances to `EnableJsonlLog = false`.

## Future Codex Working Rules

- Read this memory file first.
- Do not modify Claude-authored V5 unless the user explicitly asks.
- Avoid silent changes to live/order-routing code.
- Prefer a high-recall L1 and explicit abstain at L2/L3.
- Before coding, verify the exact compiled NT8 class names and project includes.
- Before integrating ML, verify the live `/info` schema from the scorer endpoint.
- Treat `/score_lookup` as unavailable for live unless `/health` shows `lookup_enabled=true`.
- If adding a scorer client, make the request/response contract match the actual Flask service, not the quarantined draft.
- Keep all trading automation disabled or sim-only unless user explicitly requests live order capability.
