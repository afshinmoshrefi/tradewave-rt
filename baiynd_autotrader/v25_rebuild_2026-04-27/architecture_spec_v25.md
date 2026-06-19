# AMTradeCockpit V2_5 — Master Architecture Specification

**Author:** Master Architect (Wave 1 of V2_5 rebuild)
**Date:** 2026-04-27
**Status:** Foundation document. All Wave 2/3 implementer agents write code against this contract.
**Audience:** L1 indicator implementer, L2 strategy implementer, L3 safety implementer, test agent, integrator. Indirectly: Afshin (the trader), and the institutional-grade audit reviewers who will eventually sign off on live promotion.
**Companion documents:** `strategy_synthesis.md`, `improvement_roadmap.md`, `wave3_synthesis/gap_to_am.md`, `wave3_synthesis/failure_modes.md`, `wave2_audit/v24_code_audit.md`, `AM_rules_v2_spec.md`, `wave1_extracts/transcript_*.md`.
**Read time:** 60-90 minutes; section-by-section reference for downstream implementers.

---

## Table of Contents

1. Architectural philosophy
2. Layer contracts (L1, L2, L3)
3. Event schemas
4. File structure and component layout
5. NinjaScript-specific design considerations
6. Detection (L1) precise specification
7. Strategy and scoring (L2) specification
8. Safety (L3) specification
9. Test strategy
10. Migration path
11. AM ambiguity handling
12. Implementation sequencing for downstream agents
13. Open issues and risks

---

## 1. Architectural Philosophy

### 1.1 The fail-open principle

V2_4 fired 2 signals in 6 months against 741 qualifying touches — a 0.27% conversion rate (`jsonl_data_analysis.md` Q3). The diagnosis (`gap_to_am.md`, `failure_modes.md`) is unambiguous: V2_4 is not under-detecting opportunities, it is silently swallowing them at the gating layer. Every silent drop has the same shape — a filter is too strict, or a vocabulary mismatch, or a dead code path, or a try/catch that hides a cold-start exception — and each silent drop is invisible from the JSONL. The dashboard sees a clean log; the trader sees a clean chart; the actual system blocks 99.7% of valid setups with no acknowledgement.

V2_5 inverts this posture. The first invariant of every layer is:

> **A bug that lets a trade through (recoverable, visible) is infinitely preferable to a bug that blocks one (silent, invisible).**

This translates to two concrete contracts:

1. **L1 detects everything that could conceivably be a trade.** Range, retrace-side, latch — these are filters that belong at L2 or L3, not L1. L1 emits a `candidate` event for every level inside the bar's [low, high] window. Multiple candidates per bar produce multiple events. Pattern A and Pattern B both surface candidates without rejection. There is no "best level" pruning at L1.

2. **Every block is logged.** When L2 declines to take a candidate (score below threshold, expected R below floor) it emits an `abstain` event with `layer="L2"`, the gate name, the reason, and the recovery condition. When L3 blocks a signal (RTH window closed, daily loss kill, cooldown, max signals reached) it emits an `abstain` with `layer="L3"`. There are no Print-only drops, no early-return-without-event, no dead code. The complete JSONL stream is sufficient to answer the question *"why did the system not take that setup?"* for every candidate ever surfaced.

### 1.2 Layered architecture rationale

V2_4 entangles three concerns into a single 4,627-line indicator: detection (find levels and touches), scoring (select the best candidate), and safety (lockouts, RTH window, cooldowns). Tangled concerns cause silent drops because every additional filter has the option to short-circuit before the next gate gets a chance to log its decision. Tangled concerns also make tests impossible: you can't unit-test "would Pattern B fire this bar?" without also instantiating the lockout, the MOC gate, the day-type gate, and the staging card UI.

V2_5 separates the concerns:

- **L1 (Indicator: AMTradeCockpitV2_5.cs).** Pure detection. Surfaces candidates. Knows about bar geometry, level geometry, breach state machines, and feature extraction. Knows nothing about trade decisions, scores, lockouts, or safety.
- **L2 (Strategy: AMTradeStrategyV1.cs, scorer region).** Decision logic. Receives candidates, calls a scorer (rule-based heuristic in V1; ML in V2), decides whether to take and at what size/target. Knows about scores, thresholds, and expected R. Knows nothing about lockouts or order routing.
- **L3 (Strategy: AMTradeStrategyV1.cs, safety region).** Independent gates. Each gate is an independently toggleable component with its own NinjaScriptProperty, default value, trigger condition, and recovery rule. Each gate logs an explicit `abstain` event with the layer, gate name, reason, recoverable_until_time. Knows about real account state, real positions, real time-of-day. Knows nothing about scoring.

The hosting structure (L2 strategy hosts L1 indicator and L3 safety) gives us:
- Replaceable scorer (heuristic → ML) without touching the indicator
- Independently toggleable safety gates (turn off RTH window for after-hours backtest, turn off cooldown for paper trading scenarios) without touching scorer or detection
- Direct testability at every layer (replay JSONL through L2; simulate gates against L3; inject candidates into the test harness)

This is the pattern used in institutional execution stacks — `signal_generator → tactic_selector → risk_overlay → execution_router` — where each component has a single responsibility, an explicit input/output contract, and an explicit observability layer.

### 1.3 The "explicit abstain over silent drop" contract — every layer's first invariant

Every layer's API surface includes a public `Abstain(reason)` method. Every code path that does not produce a downstream event ends in either (a) a `Signal` event (forward to next layer), (b) an `Abstain` event (block, with reason), or (c) an `Error` event (something unexpected). There is no fourth option of silently returning. Every gate-style filter is a function `Filter(candidate) → (passes: bool, reason: string)` — and if `!passes`, the caller emits the abstain. This is the V2_5 prime directive.

### 1.4 Institutional-grade design choices distinguishing this from V2_4

Six choices anchor V2_5 at institutional-grade rather than discretionary-tool grade:

1. **Schema-first event design.** Every event has a versioned schema with required and optional fields. Schemas are documented in this spec (Section 3) and enforced in code by a single `EventEmitter` helper that fails compile if a required field is missing. Compare to V2_4's ad-hoc `Dictionary<string,object>` event payloads, which produce inconsistent fields across event types and zero compile-time guarantees.

2. **State persistence and reconciliation as first-class concerns.** L3 owns a `state.json` written atomically on every significant event. On `State.DataLoaded`, L3 reads it and restores `signalsToday`, `realizedPnlDollarsToday`, `lockoutActive`, `currentSignalState`, `positionConfirmedAtBroker`. L3 reconciles `Account.Positions` against its own `currentSignalState` at every 1-minute bar and emits a `divergence` event on mismatch. Compare to V2_4 which loses all state on `Restart` (`failure_modes.md` §2.3).

3. **Determinism contract.** Same JSONL input → identical event output sequence. Achieved by (a) bar-time-based timestamps everywhere (no `DateTime.Now`), (b) explicit RNG seed for any stochastic component (the heuristic scorer does not use one in V1, but the contract is in place for V2 ML), (c) no Realtime-only side effects inside detection logic, (d) no `try/catch` swallowing exceptions in either Historical or Realtime mode.

4. **Test-first event contract.** Section 9 defines a contract compliance test: replay 6 months of JSONL through L1+L2+L3 and assert that every `candidate` event is followed by either a `signal` or an `abstain`. Zero violations allowed. This is the regression harness V2_4 lacks.

5. **AM ambiguity handled by feature emission, not by interpretation.** Where AM's rules are ambiguous (3-node vs 4-node body stack, FADE direction, slope threshold for runner ladder), V2_5 emits both interpretations as features and lets the scorer learn which matters. Architecture is shippable without AM clarifications. Section 11 details this.

6. **No try/catch swallowing in OnBarUpdate.** Every exception is logged to JSONL as an `error` event in both Historical and Realtime, with stack trace and bar context. Compare to V2_4's Historical-silent catch which hides cold-start NREs (`failure_modes.md` §1.2).

---

## 2. Layer Contracts

This section defines, for each of L1, L2, L3:
- Responsibility (what it MUST do, what it MUST NOT do)
- Inputs (with field-level schema)
- Outputs (with field-level schema)
- Invariants (properties that always hold)
- Failure modes and contracts (fail-open spec)
- Test conditions (observable behavior validating this layer)

The schema specifications below use C#-flavored pseudocode for clarity; actual implementation will use NinjaScript-compatible types.

---

### 2.1 L1 — Detection (AMTradeCockpitV2_5.cs)

#### Responsibility

L1 is responsible for:

1. **Capturing all named structural levels** — the four master candles (Close330 A, GlobEx B, Europe C, RTH930 D), Midnight, ORH/ORL, rolling Pr30, daily SMA50_30/SMA200_30, Pivots PP/R1-R4/S1-S4, the 1:30 PM candle, multi-day master candles (t-1, t-2, t-3 prior 3:30 H/L), VWAP and AnchVWAP (as permission-only levels with `is_permission_level=true`), and news-candle wicks (volume outliers).
2. **Detecting all level interactions per bar** — for every 1-minute bar's [low, high] window, every level inside that window becomes a candidate. Multiple per bar = multiple events. No first-touch latching at L1 (that's L2's job if it wants to enforce it).
3. **Classifying entry pattern type** — Pattern A (simple level retest, price touched the level and the bar closed on the side that supports the trade direction) vs Pattern B (look-below-and-fail or look-above-and-fail, breach candle confirmed by subsequent bar). Both emit candidates with `pattern_type` set.
4. **Pattern B state machine maintenance** — per-level LevelWatchState in `{Untouched, Breached, Armed, Consumed, Invalidated}`, transitioning on bar closes. Emits a candidate when state reaches `Armed` (breach candidate) and another when `Armed → fill` (entry-trigger crossing breach high/low).
5. **Feature vector extraction** — every candidate event carries a feature struct describing the bar context, the level metadata, the day type, slope, MOC ratio, distance to other levels, time of day, etc. This vector is the L2 scorer's sole input apart from candidate identity.
6. **Box capture events** — emit `box_capture` for each master-candle capture event (currently NOT logged in V2_4 — `v24_code_audit.md` §8). This is essential for offline replay, dashboard visualization, and the Python feature builder.
7. **Bar close events** — emit `bar_close` for both timeframes.
8. **Heartbeat events** — emit a `heartbeat` every 30 seconds during Realtime to validate the watchdog.
9. **Phase / bias / regime change events** — emit when the indicator's classification changes.

L1 MUST NOT:

1. Maintain or enforce trading session daily counters (`signalsToday`, `realizedPnlDollarsToday`, `lockoutActive`).
2. Maintain or enforce cooldowns or RTH windows for trade-blocking.
3. Score or rank candidates beyond extracting their feature vectors.
4. Submit, cancel, or modify any orders.
5. Fire any `signal` event. L1 fires `candidate`. L2 fires `signal`.
6. Apply retrace-side filters that block a candidate from being emitted. L1 may compute and tag `retrace_side: bool` as a feature, but it never short-circuits on it.
7. Apply latch filters that block a candidate. L1 may compute `already_touched_today: bool` as a feature, but it never short-circuits.
8. Have any try/catch that swallows exceptions in Historical or Realtime mode. Every exception is logged as `error` and re-thrown for the harness to handle (or dispatched to an explicit error counter visible in the panel).

#### Inputs

L1 subscribes to two NT8 data series:
- BarsArray[idx1Min] — primary 1-minute series for the instrument
- BarsArray[idx30Min] — secondary 30-minute series for box capture

Inputs from each bar event (NT8 native):
- `Time[barsAgo]`, `Open/High/Low/Close[barsAgo]`, `Volume[barsAgo]`, `BarsInProgress`, `CurrentBars[idx]`

Indicator parameters (NinjaScriptProperty, user-tunable, displayed in Properties pane):
- `MaxLookbackDaysForLevels` (default 3): how many days back to track t-1/t-2/t-3 master candles.
- `NewsVolumeMultiplierThreshold` (default 1.0): an intraday candle's volume must exceed `Threshold * max(yesterday_930_volume, yesterday_330_volume)` to register as a news-candle wick. Default 1.0 = AM's rule.
- `EmitVwapAsPermissionLevel` (default true): whether to surface VWAP/AnchVWAP touches as candidates with `is_permission_level=true`.
- `BoxFadeDays` (default 5): how many trading days before old boxes are dropped.
- `EnablePatternB` (default true): toggle Pattern B detection.
- `EnablePatternA` (default true): toggle Pattern A detection.
- `EnableErrorLogging` (default true): emit error events on caught exceptions (always true in production).
- `JsonlLogFolder` (default `C:\seasonals\cockpit\sessions`): root path for JSONL output.

L1 has internal state per session:
- `currentDay: DayBoxes` — today's master candles
- `dayHistory: List<DayBoxes>` — the last N days' master candles for multi-day reference
- `levelWatchStates: Dictionary<string, LevelWatchState>` — per-level Pattern B state machines, keyed by level name
- `currentVWAP, anchoredVWAP, pivots, smaCache` — computed permission/reference values
- `recentTouches: List<TouchRecord>` — for slope/cluster-detection features

#### Outputs

L1 emits the following event types (full schemas in Section 3):
- `candidate` — every level interaction (the central new event)
- `box_capture` — each master candle captured
- `bar_close` (1m and 30m)
- `heartbeat` (Realtime, 30s cadence)
- `phase_change` / `bias_change` / `regime_change` / `day_type_change`
- `error` / `warning`
- `news_wick_registered` — a news-candle wick added as a level
- `pattern_b_state_change` — when a LevelWatchState transitions

L1 also exposes two events for in-process subscribers (the L2 strategy):
- `event Action<CandidateEventArgs> OnCandidate` — fired on each candidate emission (in addition to JSONL)
- `event Action<BoxCaptureEventArgs> OnBoxCapture` — fired on each box capture

#### Invariants

The following must always hold after L1 processes any 1-minute bar:

**INV-L1-1:** For every 1-minute bar `b` where any tracked level `L_i` satisfies `b.Low <= L_i.Price <= b.High`, exactly one `candidate` event is emitted per (bar, level) pair. No skipping. No deduplication based on retrace-side or latch state.

**INV-L1-2:** For every `candidate` event with `pattern_type="A"`, the bar at `event.BarTime` had price interaction with the level. For every `candidate` event with `pattern_type="B"`, the breach candle exists in the bar history and the LevelWatchState reached `Armed` on this bar.

**INV-L1-3:** Every candidate carries a complete `features` struct with no NaN values. If a feature cannot be computed (e.g., 200-SMA slope before 200 bars of history), it is set to a sentinel `null` and a corresponding `*_available: bool` flag is `false`. Never emit NaN; always emit null + flag.

**INV-L1-4:** The `currentDay.Sma200At930` value, once captured at the 9:30 30-minute bar, is locked for the rest of the session. Re-reads of `Sma200SlopeDelta` after 9:30 always return the same value.

**INV-L1-5:** For every 30-minute master candle capture (Close330 A, GlobEx B, Midnight, Europe C, RTH930 D, Close130), exactly one `box_capture` event fires. Re-emission only on `RunContainmentCheck` reassignment, with `event.subtype="institutional_reassignment"` to distinguish from the original capture.

**INV-L1-6:** No `OnBarUpdate` exception is silently swallowed. All caught exceptions emit `error` events with stack trace, bar context, and exception type. Historical mode emits errors equally as Realtime.

**INV-L1-7:** Same JSONL input → same event sequence. No `DateTime.Now` reads anywhere in the detection path. No randomness.

#### Failure Modes and Contracts (fail-open spec)

| Failure mode | L1 response |
|---|---|
| 200-SMA not yet warmed up (< 200 bars) | Emit candidate with `sma200_slope_delta=null`, `sma200_slope_available=false`. Do not block emission. L2 decides whether to abstain. |
| MOC ratio cannot be computed (volume zero on either bar) | Emit `moc_ratio=null`, `moc_state="Unavailable"`. L2 decides. |
| Multiple levels inside a single bar | Emit one candidate per level. No deduplication by distance or "best." |
| Level coincides with bar open exactly (`px == barOpen`) | Emit candidate. The retrace_side feature is left `null` with `retrace_side_at_open=true`. (V2_4 silently dropped these per `gap_to_am.md` GAP/edge case.) |
| Pattern B breach candle observed but next bar has insufficient data (last 1-min bar of session) | LevelWatchState stays `Breached`, no `Armed` transition fires until next session. State persisted via `state.json`. |
| News-wick detection: today's volume exceeds yesterday's but yesterday's data is missing | Emit `news_wick_registered=false`, log `warning` with cause, do not block other detection. |
| `Volumes[idx30Min][0]` returns a value that fails the long-cast (overflow) | Clamp at `1e12`, log `warning`, continue. |
| 30-minute bar missing at 9:30 (data gap on holiday-thin days) | Use first available RTH bar as `RTH930OpenPx` proxy, emit `warning`, do not block day-type classification. |
| DST transition day | Use NT8's bar-time ET timestamps directly. Do not compare against wall-clock time. |
| User changes a parameter mid-session | Persist state to `state.json` before `State.Terminated` triggers. Restore on next `State.DataLoaded`. |

#### Test Conditions

L1 is validated by the following observable behaviors:

**TEST-L1-1 (Replay equivalence):** Replay V2_4's 6-month JSONL through V2_5 L1. For every V2_4 `signal` event in the historical log, V2_5 must emit a `candidate` event for the same (date, time, level, direction). V2_5 may emit additional candidates that V2_4 didn't (this is expected: V2_4's silent drops should now surface). 100% recall on V2_4's actual signals.

**TEST-L1-2 (Pattern B detection):** Synthetic bar sequences:
- A bar with `low < L`, `close >= L` (long breach) → candidate with `pattern_type="B"`, `lws_state="Armed"` after the breach is confirmed by the next bar holding higher than the breach low.
- A bar with `low < L`, `close < L` (failed breach, breakdown) → candidate with `pattern_type=null` (no Pattern B fires), `lws_state="Invalidated"`.
- A bar that touches L from above and reverses → Pattern A candidate emitted.

**TEST-L1-3 (Feature vector completeness):** For 1000 candidate events, every event's `features` struct has all required fields populated (or null with `*_available=false`). No NaN, no missing fields.

**TEST-L1-4 (Determinism):** Run L1 twice on the same data. Diff event sequences. Zero non-trivial differences (ignore wall-clock timestamps in heartbeat events; everything else identical).

**TEST-L1-5 (Box capture events):** Confirm that for every 30-min bar at master-candle times (15:00, 18:00, 00:00, 04:00, 09:30, 13:30 ET), a `box_capture` event fires with correct H/L/StartTime.

---

### 2.2 L2 — Scoring and Decision (AMTradeStrategyV1.cs scorer region)

#### Responsibility

L2 is responsible for:

1. **Subscribing to L1's candidate stream** — via the `OnCandidate` C# event interface in-process and/or by reading the JSONL stream.
2. **Calling the scorer for each candidate** — the scorer takes the candidate's feature vector and returns a structured decision: `(p_win, expected_R, recommended_size_bucket, target_choice, confidence, abstain_reason)`.
3. **Applying decision thresholds** — take the candidate if `p_win > MinWinProbability` AND `expected_R > MinExpectedR` AND `confidence > MinConfidence`. Otherwise emit `abstain` with `layer="L2"`, the gate name (e.g., "scorer_min_p_win"), and the candidate identity.
4. **Ranking multiple candidates per bar** — when L1 surfaces N candidates in a single bar, L2 ranks them by `expected_R * confidence` and either takes the top K (where K is a parameter, default 1) or evaluates each in priority order.
5. **Position management** — coordinate with L3 to determine if an entry is allowed (one position per instrument; pending limit replaces older pending limits).
6. **Order construction** — determine entry/stop/target prices and submit via NT8's order API (preferred: `AtmStrategyCreate` for ES/NQ/CL/GC live, `Account.CreateOrder + Submit` for testing/transparency).
7. **Order monitoring** — subscribe to NT8's `OnExecutionUpdate` for real fill detection (not bar-data inference). Update internal `currentSignalState` based on broker reality.
8. **Fill, stop, target, time-close events** — emit JSONL events for each (currently NOT logged by V2_4 per `v24_code_audit.md` §8 / `nt8_safety_review.md` §B7).
9. **Calling the scorer's runner-target update** — after a fill, the runner target depends on slope and Fibonacci extension; the scorer can be re-queried as price evolves.

L2 MUST NOT:

1. Re-implement detection logic (find levels, compute slope, etc.). All structural knowledge comes from L1's candidate features.
2. Apply hard safety gates (lockouts, RTH windows, daily-loss kills). Those are L3's responsibility.
3. Submit any order without first checking with L3 (L3 has the kill-switch authority).
4. Cancel orders without emitting a `cancel` event.
5. Log to NT Output `Print` for any decision-relevant information. All decisions are JSONL events.

#### Inputs

From L1 (per candidate):
- `CandidateEventArgs` struct with full feature vector (Section 3 defines the schema).

From L3:
- `IsKillSwitchActive() → bool` — synchronous query.
- `WhyBlocked() → string` — for diagnostic reporting in abstain reasons.
- `HasMaxSignalsReached() → bool`, `IsInCooldown() → bool`, etc.
- `CurrentBrokerPosition` — reconciled position state.

Configuration parameters (NinjaScriptProperty on the strategy):
- `ScorerMode: enum { Heuristic, MlHttp }` (default Heuristic)
- `MlHttpEndpoint: string` (default `"http://localhost:7677/score"`)
- `MlHttpTimeoutMs: int` (default 2000)
- `MinWinProbability: double` (default 0.45)
- `MinExpectedR: double` (default 0.30)
- `MinConfidence: double` (default 0.40)
- `MaxCandidatesPerBarToTake: int` (default 1)
- `RunnerTargetMode: enum { LevelToLevel, FibonacciSlopeGated }` (default LevelToLevel for V1)
- `EntrySubmitMode: enum { ATMTemplate, UnmanagedOrders }` (default ATMTemplate for V1)
- `AtmTemplateNormal: string` (default `"AM_Normal_2MES"`)
- `AtmTemplateWide: string` (default `"AM_Wide_1MES"`)

#### Outputs

L2 emits:
- `signal` — when scorer accepts a candidate AND L3 permits.
- `abstain` (with layer="L2") — when scorer rejects.
- `fill` — when broker confirms a position via `OnExecutionUpdate`.
- `stop_hit`, `target_hit`, `time_close`, `trail_exit`, `cancel` — exit events.
- `runner_target_update` — when the slope-conditional runner target changes mid-trade.
- `decision_request` / `decision_response` — for HTTP-mode ML scorer (lets us trace round-trip latency).

#### Invariants

**INV-L2-1:** Every L1 `candidate` event is followed by either an L2 `signal`, an L2 `abstain`, or an L3 `abstain` for the same candidate identity. Zero candidates are silently consumed.

**INV-L2-2:** The scorer (heuristic or ML) is a pure function of the candidate's feature vector. It does not read any L2 state outside its own deterministic computation. (For HTTP ML, the only impurity is network latency — handled via timeout + fallback to heuristic.)

**INV-L2-3:** When the scorer decides to take a candidate but the L3 kill-switch fires (cooldown, lockout, max signals), L3's abstain takes precedence. L2 does not emit a `signal` until L3 returns no-block.

**INV-L2-4:** Order submission to NT8 is atomic with respect to a single `OnBarUpdate` event. L2 does not initiate two separate submissions in the same bar event.

**INV-L2-5:** The scorer's output is logged on every call, even when below threshold (the `decision_response` event includes the predicted R, confidence, and the abstain_reason). This is the audit trail for "which scorer rejected which candidate."

#### Failure modes and contracts

| Failure mode | L2 response |
|---|---|
| HTTP scorer endpoint unreachable | Fall back to heuristic scorer. Log `warning`. Continue evaluation. |
| HTTP scorer returns malformed response | Use heuristic. Log `error`. |
| Heuristic scorer encounters a feature with `*_available=false` | Apply fallback rule (default: weight that feature as 0 in the heuristic). Continue evaluation. |
| Multiple candidates in same bar exceed `MaxCandidatesPerBarToTake` | Take top-K by `score * confidence`. Emit `abstain` for the rest with reason="rank_too_low". |
| Order submission fails (`AtmStrategyCreate` returns failure) | Set `currentSignalState = Failed`. Emit `error`. Reset to None. Do not retry on this bar. |
| `OnExecutionUpdate` reports a fill at a different price than the limit | Use broker price. Do not trust internal `signalEntry`. Emit `warning` if delta > 1 tick. |
| Pending limit not filled by 14:30 cutoff | Cancel the limit. Emit `cancel` event. Reset to None. |

#### Test conditions

**TEST-L2-1 (Contract compliance):** Replay 6 months of synthetic candidates through L2. For every candidate, exactly one of {signal, abstain (L2), abstain (L3)} fires. Zero violations.

**TEST-L2-2 (Heuristic scorer):** Given a known feature vector (constructed from a verified-historical-AM-trade), the scorer returns `p_win > MinWinProbability` AND `expected_R > MinExpectedR`. Verify the heuristic agrees with hand-computed expected values within tolerance.

**TEST-L2-3 (HTTP fallback):** Disable the HTTP endpoint. L2 must continue scoring via heuristic. Log shows `warning` events but no `error`s for transient unreachability.

**TEST-L2-4 (Ranking):** Inject 5 candidates in same bar. L2 takes top-1 by score (configurable) and emits 4 `abstain` events with reason="rank_too_low".

**TEST-L2-5 (Order lifecycle):** From `signal` event to `fill` event to either `stop_hit`/`target_hit`/`time_close`. Every exit produces a paired event.

---

### 2.3 L3 — Safety (AMTradeStrategyV1.cs safety region)

#### Responsibility

L3 is responsible for:

1. **Independent safety gates** — each gate is a self-contained component with its own toggle, parameter, trigger condition, and recovery rule. Each gate can be disabled independently for testing or special operations.
2. **Pre-submit veto** — L2 must call `L3.IsSubmissionAllowed(signal)` before submitting any order. L3 returns `(allowed: bool, reason: string)`. If `allowed=false`, L2 emits `abstain` with `layer="L3"`, gate name, and reason.
3. **Post-fill monitoring** — track real account position state via `OnExecutionUpdate` and `OnPositionUpdate`. Emit `divergence` event if the broker's position disagrees with L3's expected state.
4. **State persistence** — L3 owns `state.json`, written atomically on every signal, fill, stop, target, time-close, lockout, and reset event. On `State.DataLoaded`, L3 reads `state.json` and restores state before the first bar fires.
5. **Daily reset cycle** — at session boundary, archive yesterday's state and reset today's counters. Emit `lockout_reset` event when the daily lockout flag is cleared.
6. **Holiday and DST handling** — consult an external holiday calendar (default: bundled list updated quarterly; optionally fetched from `pandas_market_calendars` parquet at startup).
7. **Manual abstain/kill-switch interface** — expose a button or hotkey ("Halt All") that immediately cancels all pending orders, blocks new entries for the session, and emits a `manual_kill_switch_activated` event. Companion `Resume` button for the next session.

L3 MUST NOT:

1. Make scoring or trade-selection decisions. L3 only blocks. It does not select.
2. Modify a candidate's feature vector or the scorer's output.
3. Submit orders. L2 submits; L3 vetoes.
4. Fail silently. Every block emits an `abstain` event with reason.

#### Gates (each independently toggleable)

Each gate has `Enable*: bool` parameter, `*` configuration parameter, default value, trigger condition, abstain payload, and recovery rule.

**Gate 1: RTH Window**
- `EnableRthWindowGate: bool` (default true)
- `RthOpenHourEt: int`, `RthOpenMinuteEt: int`, `RthCloseHourEt: int`, `RthCloseMinuteEt: int` (default 9:30 / 15:00 ET for ES/NQ/GC; 9:00 / 14:30 for CL — fixes V2_4 CL bug)
- `EntryCutoffMinutesBeforeClose: int` (default 30)
- Trigger: `barTime < RthOpen` OR `barTime > (RthClose - EntryCutoff)`.
- Abstain reason: `"rth_window_closed"`. Recovery condition: `next_RthOpen`.

**Gate 2: Daily Loss Kill ($)**
- `EnableDailyLossKill: bool` (default true)
- `MaxDailyLossDollars: double` (default $500 for sim; configured per account size for live)
- Trigger: `realizedPnlDollarsToday <= -MaxDailyLossDollars`.
- Abstain reason: `"daily_loss_kill"`. Recovery: next session.

**Gate 3: Daily Loss Kill (% of account)**
- `EnableDailyLossPctKill: bool` (default false; supplements gate 2)
- `MaxDailyLossPctOfAccount: double` (default 2.0)
- Trigger: realized PnL ≤ −MaxDailyLossPct × account_value.
- Abstain reason: `"daily_loss_pct_kill"`. Recovery: next session.

**Gate 4: Max Losing Trades**
- `EnableMaxLosingTrades: bool` (default true)
- `MaxConsecutiveStops: int` (default 2)
- `MaxLosingTradesToday: int` (default 3)
- Trigger: either threshold breached.
- Abstain reason: `"max_losing_trades"`. Recovery: next session.

**Gate 5: Cooldown After Stop**
- `EnableCooldownAfterStop: bool` (default true)
- `CooldownMinutes: int` (default 30)
- Trigger: time since `lastStopTime` < `CooldownMinutes`.
- Abstain reason: `"cooldown_after_stop"`. Recovery: `lastStopTime + CooldownMinutes`.

**Gate 6: Max Signals Per Day**
- `EnableMaxSignalsPerDay: bool` (default true)
- `MaxSignalsPerDay: int` (default 5 — AM's "max max")
- `CountFillsOnly: bool` (default true — fix V2_4's pending-counts bug per `gap_to_am.md` GAP19)
- Trigger: `CountFillsOnly ? fillsToday >= Max : signalsToday >= Max`.
- Abstain reason: `"max_signals_per_day"`. Recovery: next session.

**Gate 7: Position State Guard**
- `EnablePositionGuard: bool` (default true; cannot be disabled in live)
- Trigger: `currentSignalState != None && currentSignalState != Pending`.
- Abstain reason: `"position_already_active"`. Recovery: position closes.

**Gate 8: Margin / Account Guard**
- `EnableMarginGuard: bool` (HARD ON — cannot be disabled)
- Trigger: `Account.MarginAvailable < EstimatedMarginRequired(signal)`.
- Abstain reason: `"insufficient_margin"`. Recovery: account replenished.

**Gate 9: Manual Kill-Switch**
- `EnableManualKillSwitch: bool` (default true)
- Trigger: button click or hotkey.
- Abstain reason: `"manual_kill_switch"`. Recovery: explicit `Resume` action by user.

**Gate 10: Holiday Schedule**
- `EnableHolidayGate: bool` (default true)
- `HolidayCalendarPath: string` (default `"./holidays.parquet"`)
- Trigger: today's date is a full-close holiday OR within early-close window.
- Abstain reason: `"holiday_blackout"` or `"early_close_window"`. Recovery: next non-holiday session.

**Gate 11: Connection State Guard**
- `EnableConnectionGuard: bool` (default true)
- Trigger: `ConnectionStatus != Connected` for primary data feed or order routing.
- Abstain reason: `"connection_error"`. Recovery: reconnection confirmed.

**Gate 12: Heartbeat Gap Self-Check**
- `EnableHeartbeatSelfCheck: bool` (default true)
- `HeartbeatStaleSeconds: int` (default 90)
- Trigger: time since last `OnBarUpdate` exceeds threshold during RTH.
- Abstain reason: `"heartbeat_gap"`. Recovery: next bar arrives.

#### Inputs

L3 receives:
- `IsSubmissionAllowed(SignalRequest)` calls from L2.
- NT8 `OnExecutionUpdate`, `OnPositionUpdate`, `OnConnectionStatusUpdate` callbacks.
- Manual kill button clicks via UI.
- Bar-time clock for cooldown/RTH window evaluation.

L3 reads `state.json` on initialization. L3 writes `state.json` on every state change.

#### Outputs

L3 emits:
- `abstain` with `layer="L3"`, `gate_name`, `reason`, `recoverable_until_time`.
- `lockout_active` / `lockout_reset` (state changes for daily loss / consecutive stops).
- `cooldown_active` / `cooldown_reset`.
- `divergence` (broker vs internal state mismatch).
- `manual_kill_switch_activated` / `manual_kill_switch_resumed`.
- `connection_error` / `connection_restored`.
- `state_persisted` — diagnostic, every time `state.json` is written.

#### Invariants

**INV-L3-1:** Every gate's trigger condition is an explicit, deterministic function of named state. No boolean flags whose meaning is "various reasons." Every block names a specific gate.

**INV-L3-2:** Every L3 abstain event includes `recoverable_until_time` (a `DateTime` or "next_session"). The trader/dashboard can answer "when can I trade again?" from the JSONL alone.

**INV-L3-3:** L3 state survives a NT8 restart. Specifically, after `Restart → State.DataLoaded`, the values of `signalsToday`, `fillsToday`, `realizedPnlDollarsToday`, `lockoutActive`, `cooldownActive`, `currentSignalState`, `positionConfirmedAtBroker` are restored from `state.json` if today's date matches.

**INV-L3-4:** Position-state reconciliation runs on every 1-min bar. If `currentSignalState` and `Account.Positions` disagree, an `divergence` event fires within 60 seconds and L3 immediately blocks new submissions.

**INV-L3-5:** No L3 gate has a Realtime-only side effect that breaks Historical replay. Cooldown, lockout, RTH window all evaluate identically in both states.

#### Failure modes and contracts

| Failure mode | L3 response |
|---|---|
| `state.json` missing or corrupt at `State.DataLoaded` | Initialize with defaults, log `warning`, continue. |
| `Account.Positions` query fails | Conservative posture: assume position exists, block all new submissions. Log `warning` and `divergence`. |
| Holiday calendar file missing | Fall back to bundled minimal holiday list. Log `warning`. |
| `OnConnectionStatusUpdate` fires `Disconnected` mid-trade | Block new submissions. Continue monitoring existing position via NT8 internals. |
| Manual kill-switch fired but cancellation of an order fails | Emit `error`. Continue blocking new submissions. Operator must manually reconcile. |
| DST transition produces ambiguous bar time | Use NT8's exchange-time bar timestamp. Log `warning` if hour is in 1:00-3:00 ET range on transition Sunday. |

#### Test conditions

**TEST-L3-1 (Each gate triggers):** For each of the 12 gates, set up its trigger condition and verify exactly one `abstain` event fires with correct payload (`gate_name`, `reason`, `recoverable_until_time`).

**TEST-L3-2 (State persistence):** After 5 fired signals and a stop, kill the strategy mid-session. Restart. Verify `signalsToday=5`, `fillsToday=N`, `realizedPnlDollarsToday=correct`, `lockoutActive=true_if_threshold_reached` are all restored.

**TEST-L3-3 (Divergence detection):** Inject a position into NT8's account that L3 didn't track. On next bar, L3 emits `divergence` event and blocks new submissions.

**TEST-L3-4 (Manual kill-switch):** Click the kill button. Verify all pending orders cancelled, `manual_kill_switch_activated` emitted, all subsequent submissions blocked until `Resume`.

**TEST-L3-5 (Independence):** Disable gate 1 (RTH window) but keep gate 2 (daily loss kill). Verify the strategy will fire signals at 03:00 ET (outside RTH) but still block on a daily loss. Verify each gate is independently controllable.

---

## 3. Event Schemas

This section specifies every JSONL event type with field-level schema. Every event has the following envelope:

```json
{
  "t": "2026-04-27T09:32:15.123-04:00",  // ISO 8601 with timezone
  "type": "<event_type>",
  "schema_version": "v25.1",
  "instrument": "ES 06-26",
  "session_date": "2026-04-27",
  "payload": { /* type-specific */ }
}
```

The `t` field is the bar-time of the bar that caused the event (for bar-driven events) or the wall-clock time of emission (for time-driven events like `heartbeat`). The `schema_version` field is bumped whenever any event schema changes incompatibly.

### 3.1 `bar_close`

Emitted on every 1-min bar close (`tf="1m"`) and every 30-min bar close (`tf="30m"`). Used for offline replay reconstruction and for ensuring data continuity in JSONL.

```json
{
  "type": "bar_close",
  "payload": {
    "tf": "1m",          // "1m" | "30m"
    "bar_time": "2026-04-27T09:32:00-04:00",
    "open": 5612.50,
    "high": 5615.25,
    "low": 5611.00,
    "close": 5614.75,
    "volume": 12534
  }
}
```

### 3.2 `box_capture`

Emitted on each master-candle capture. Currently NOT logged in V2_4 (per `v24_code_audit.md` §8 / `nt8_safety_review.md` §B7); essential for offline replay and Python event_builder reconciliation.

```json
{
  "type": "box_capture",
  "payload": {
    "name": "Close330",  // "Close330" | "GlobEx" | "Midnight" | "Europe" | "RTH930" | "Close130"
    "subtype": "primary", // "primary" | "institutional_reassignment"
    "instance_day_offset": 0, // 0 = today, -1 = yesterday, -2 = two-days-ago, -3 = three-days-ago
    "start_time": "2026-04-27T15:30:00-04:00",
    "high": 5615.50,
    "low": 5610.25,
    "open": 5614.00,
    "close": 5612.75,
    "body_top": 5614.00,
    "body_bottom": 5612.75,
    "wick_top_pts": 1.50,
    "wick_bottom_pts": 2.50,
    "volume": 124500,
    "is_institutional_now": true,    // is this currently the "institutional" box?
    "moc_ratio": 1.34,                // for Close330 only: today's vs yesterday's 3:30 volume
    "moc_state": "Green"              // for Close330 only
  }
}
```

### 3.3 `candidate` (THE central new event)

Emitted by L1 for every level interaction in every 1-min bar. This is the recall-level event that L2 receives for scoring. The schema is verbose because L2's heuristic and the future ML scorer both consume it without further L1 lookups.

```json
{
  "type": "candidate",
  "payload": {
    "candidate_id": "ES_2026-04-27_0932_Pr30L_long_001",  // unique within session
    "level_name": "Pr30L@1030",
    "level_price": 5611.25,
    "is_permission_level": false,         // true for VWAP/AnchVWAP
    "direction": "LONG",                   // "LONG" | "SHORT"
    "pattern_type": "B",                   // "A" | "B"
    "lws_state": "Armed",                  // null for Pattern A; "Untouched" | "Breached" | "Armed" | "Consumed" | "Invalidated" for Pattern B
    "bar_time": "2026-04-27T09:32:00-04:00",
    "bar_open": 5613.00,
    "bar_high": 5615.25,
    "bar_low": 5610.50,
    "bar_close": 5614.50,
    "bar_volume": 14200,
    "anchor_candle": {                    // the candle that triggered (Pattern A: this 1-min bar; Pattern B: the breach candle)
      "name": "1min_breach_at_0931",
      "high": 5613.50,
      "low": 5610.50,
      "body_top": 5612.50,
      "body_bottom": 5611.00,
      "volume": 11500
    },
    "features": {                          // the feature vector for the scorer
      // --- Day type ---
      "day_type_v2": "LongTrend",         // "LongTrend" | "ShortTrend" | "CautiousLong" | "CautiousShort" | "Sideways" | "Unknown"
      "day_type_v2_3node": "LongTrend",   // 3-node interpretation (B<C<D)
      "day_type_v2_4node": "Sideways",    // 4-node interpretation (A<B<C<D)
      "body_overlap_AB": false,
      "body_overlap_BC": false,
      "body_overlap_CD": false,
      "large_wick_flag_A": false,
      "large_wick_flag_B": false,
      "large_wick_flag_C": false,
      "large_wick_flag_D": false,

      // --- Slope and SMA ---
      "sma200_slope_delta_pts": 4.5,      // null if not yet computable
      "sma200_slope_available": true,
      "sma200_slope_sign": "Up",          // "Up" | "Down" | "Flat"
      "sma50_30_slope_pts": 2.1,
      "sma50_30_slope_available": true,

      // --- MOC ---
      "moc_ratio": 1.34,
      "moc_state": "Green",
      "moc_observed_today": true,         // false if before today's 3:30 close

      // --- VWAP/AnchVWAP context ---
      "vwap_price": 5612.80,
      "vwap_slope": "Up",
      "anchored_vwap_price": 5610.40,
      "anchored_vwap_slope": "Up",
      "dist_to_vwap_pts": 1.45,
      "dist_to_anchvwap_pts": 3.85,

      // --- Distance to other named levels (in points; null if level missing) ---
      "dist_to_close330_high": 4.25,
      "dist_to_close330_low": -2.00,
      "dist_to_globex_high": 6.00,
      "dist_to_globex_low": -1.50,
      "dist_to_midnight_high": 5.00,
      "dist_to_midnight_low": -3.00,
      "dist_to_europe_high": 8.50,
      "dist_to_europe_low": -0.75,
      "dist_to_europe_close": 2.00,
      "dist_to_rth930_high": 0.50,
      "dist_to_rth930_low": -3.50,
      "dist_to_close130_high": null,      // not yet captured today
      "dist_to_close130_low": null,
      "dist_to_or_high": null,            // before OR lock
      "dist_to_or_low": null,
      "dist_to_pp": 1.25,                 // PP / pivots
      "dist_to_r1": 4.50,
      "dist_to_r2": 9.00,
      "dist_to_r3": 14.25,
      "dist_to_r4": 19.50,
      "dist_to_s1": -3.75,
      "dist_to_s2": -8.25,
      "dist_to_s3": -13.50,
      "dist_to_s4": -19.25,
      "dist_to_pday1_close330_high": 8.50, // multi-day master candles
      "dist_to_pday1_close330_low": 2.25,
      "dist_to_pday2_close330_high": 12.75,
      "dist_to_pday2_close330_low": 6.50,
      "dist_to_pday3_close330_high": 18.00,
      "dist_to_pday3_close330_low": 11.25,
      "dist_to_news_wick_zone": null,      // null if no active news wick

      // --- Cluster and confluence ---
      "num_levels_in_cluster": 3,         // levels within 5 ticks of this one
      "cluster_max_volume_origin": 5613.00, // price of the highest-volume origin candle in cluster
      "is_highest_volume_in_cluster": true,
      "confluence_count": 4,               // VWAP+50+200+master near level

      // --- Geometry features (from rt2_1) ---
      "entry_extension_from_overnight_low_adr": 0.35,
      "globex_open_vs_europe_high_pts": -2.00,
      "globex_open_vs_europe_low_pts": 4.50,
      "europe_high_vs_prior_inst_high_pts": -0.50,
      "europe_low_vs_prior_inst_low_pts": 1.25,
      "pattern_6pm_below_4am_and_inst_long": true,

      // --- Bar shape ---
      "body_pct": 0.45,
      "candle_range_pct": 0.85,
      "upper_wick_pct": 0.20,
      "lower_wick_pct": 0.35,
      "candle_direction": "Up",

      // --- Latch and retrace state (informational) ---
      "retrace_side": true,                // null if px == bar_open
      "retrace_side_at_open": false,
      "already_touched_today": false,

      // --- Time and DOW ---
      "minutes_since_rth_open": 2,
      "minutes_until_rth_close": 328,
      "hour_et": 9,
      "day_of_week": "Monday",
      "month": 4,

      // --- Volume context ---
      "vol_zscore_vs_session": 1.85,
      "first_1min_volume_pct_of_normal": 0.95, // ES 12000-15000 is "normal"
      "approach_speed_pts_per_min": 3.50,

      // --- ADR / volatility ---
      "adr_20d_pts": 105.66,
      "europe_width_pts": 8.50,
      "candle_width_pct_of_adr": 0.080,

      // --- News-wick context ---
      "news_wick_active_today": false,
      "news_wick_distance_pts": null
    },
    "stop_distance_suggestion_pts": 3.00,  // computed via per-trigger candle width
    "first_target_pts": 3.00,              // 100% Fib of trigger candle
    "runner_target_options": {
      "level_to_level_next_pts": 6.50,
      "fib_150_pct_pts": 4.50,
      "fib_200_pct_pts": 6.00,
      "fib_250_pct_pts": 7.50
    }
  }
}
```

### 3.4 `signal`

Emitted by L2 when the scorer accepts a candidate AND L3 permits.

```json
{
  "type": "signal",
  "payload": {
    "signal_id": "sig_ES_2026-04-27_0932_001",
    "candidate_id": "ES_2026-04-27_0932_Pr30L_long_001",
    "direction": "LONG",
    "entry_price": 5613.50,
    "stop_price": 5610.50,
    "first_target_price": 5616.50,
    "runner_target_price": 5620.00,
    "pattern_type": "B",
    "level_name": "Pr30L",
    "scorer_decision": {
      "p_win": 0.58,
      "expected_R": 1.85,
      "recommended_size_bucket": "Green",
      "target_choice": "fib_200_pct",
      "confidence": 0.72,
      "scorer_mode": "Heuristic"
    },
    "size_qty": 2,
    "atm_template": "AM_Normal_2MES",
    "submit_method": "AtmStrategyCreate",
    "broker_order_id": null              // populated when AtmStrategyCreate returns
  }
}
```

### 3.5 `abstain`

THE central new event. Every block at every layer emits this. Currently NOT logged in V2_4 — `nt8_safety_review.md` §B7 lists `canTrade_denied` as the missing event that explains the 0.27% conversion rate.

```json
{
  "type": "abstain",
  "payload": {
    "candidate_id": "ES_2026-04-27_0932_Pr30L_long_001",
    "layer": "L3",                        // "L1" | "L2" | "L3"
    "gate_name": "cooldown_after_stop",
    "reason": "30 minutes since last stop; 18 minutes remaining",
    "recoverable_until_time": "2026-04-27T10:02:00-04:00",
    "scorer_decision": {                   // for L2 abstains
      "p_win": 0.32,
      "expected_R": 0.18,
      "scorer_mode": "Heuristic"
    },
    "gate_state_snapshot": {                // for L3 abstains
      "cooldown_active": true,
      "last_stop_time": "2026-04-27T09:32:00-04:00",
      "cooldown_minutes": 30
    }
  }
}
```

### 3.6 `fill`

Emitted by L2 on `OnExecutionUpdate` when the broker confirms entry.

```json
{
  "type": "fill",
  "payload": {
    "signal_id": "sig_ES_2026-04-27_0932_001",
    "broker_order_id": "ATM_xxxxx",
    "filled_at": "2026-04-27T09:33:15.234-04:00",
    "filled_price": 5613.50,
    "filled_qty": 2,
    "expected_price": 5613.50,             // from signal
    "slippage_pts": 0.0,
    "is_partial": false
  }
}
```

### 3.7 `stop_hit`

Emitted by L2 when broker reports stop fill.

```json
{
  "type": "stop_hit",
  "payload": {
    "signal_id": "sig_ES_2026-04-27_0932_001",
    "stopped_at": "2026-04-27T09:48:30-04:00",
    "stop_price": 5610.50,
    "filled_qty": 2,
    "realized_pnl_dollars": -300.00,
    "realized_R": -1.0
  }
}
```

### 3.8 `target_hit`

Emitted by L2 when broker reports target fill (full or partial).

```json
{
  "type": "target_hit",
  "payload": {
    "signal_id": "sig_ES_2026-04-27_0932_001",
    "target_kind": "first_target",        // "first_target" | "runner_target" | "level_to_level_step"
    "target_price": 5616.50,
    "filled_at": "2026-04-27T09:42:00-04:00",
    "filled_qty": 1,                       // partial
    "remaining_qty": 1,
    "realized_pnl_dollars": 150.00,
    "realized_R": 1.0
  }
}
```

### 3.9 `time_close`

Emitted by L2 at session close cutoff.

```json
{
  "type": "time_close",
  "payload": {
    "signal_id": "sig_ES_2026-04-27_0932_001",
    "closed_at": "2026-04-27T15:00:00-04:00",
    "close_price": 5618.25,
    "filled_qty": 1,
    "realized_pnl_dollars": 237.50,
    "realized_R": 1.58
  }
}
```

### 3.10 `cancel`

Emitted by L2 when a pending limit is cancelled (cutoff or replacement).

```json
{
  "type": "cancel",
  "payload": {
    "signal_id": "sig_ES_2026-04-27_0932_001",
    "reason": "cancel_at_cutoff",        // "cancel_at_cutoff" | "replaced_by_newer_pending" | "manual_cancel" | "kill_switch"
    "cancelled_at": "2026-04-27T14:30:00-04:00"
  }
}
```

### 3.11 `lockout_active` / `lockout_reset`

Emitted by L3 when daily-loss or consecutive-stops lockout triggers / resets.

```json
{
  "type": "lockout_active",
  "payload": {
    "trigger": "daily_loss_dollars",     // "daily_loss_dollars" | "daily_loss_pct" | "max_consecutive_stops" | "max_losing_trades"
    "value": -502.50,
    "threshold": -500.00,
    "expires_at": "next_session"
  }
}

{
  "type": "lockout_reset",
  "payload": {
    "trigger_that_was_active": "daily_loss_dollars",
    "reset_at": "2026-04-28T00:00:00-04:00",
    "reason": "session_rollover"
  }
}
```

### 3.12 `cooldown_active` / `cooldown_reset`

```json
{
  "type": "cooldown_active",
  "payload": {
    "stop_time": "2026-04-27T09:48:30-04:00",
    "cooldown_minutes": 30,
    "expires_at": "2026-04-27T10:18:30-04:00"
  }
}

{
  "type": "cooldown_reset",
  "payload": {
    "reset_at": "2026-04-27T10:18:30-04:00"
  }
}
```

### 3.13 `phase_change` / `bias_change` / `regime_change` / `day_type_change`

L1 classification changes. `day_type_change` is the new event for the AM body-stack classification (V2_4 only emits `bias_change` and `phase_change`; `day_type_v2` was never emitted, hence the 0.27% conversion rate via the FADE vocabulary mismatch).

```json
{
  "type": "day_type_change",
  "payload": {
    "from": "Unknown",
    "to": "LongTrend",
    "interpretation": "v2_3node",        // "v2_3node" | "v2_4node"; both interpretations emitted as separate events
    "ascertained_at": "2026-04-27T09:30:00-04:00"
  }
}

{
  "type": "phase_change",
  "payload": { "from": "EuropeOpen", "to": "RTHActive" }
}

{
  "type": "bias_change",
  "payload": { "from": "Neutral", "to": "Long" }
}

{
  "type": "regime_change",
  "payload": { "from": "Trending", "to": "Congestion" }   // legacy V2_4 day-type
}
```

### 3.14 `heartbeat`

Emitted every 30 seconds during Realtime to allow watchdog detection of stalls.

```json
{
  "type": "heartbeat",
  "payload": {
    "phase": "RTHActive",
    "bias": "Long",
    "day_type_v2_3node": "LongTrend",
    "day_type_v2_4node": "Sideways",
    "regime": "Trending",
    "signal_state": "None",
    "price": 5614.50,
    "vwap": 5612.80,
    "moc_state": "Green",
    "moc_ratio": 1.34,
    "sma200_slope_delta": 4.5,
    "in_lockout": false,
    "lockout_reason": null,
    "in_cooldown": false,
    "signals_today": 1,
    "fills_today": 1,
    "realized_pnl_dollars_today": 150.00,
    "open_position_qty": 1
  }
}
```

### 3.15 `error` / `warning`

Diagnostic events. Critical for observability — any `try/catch` in production code emits one of these.

```json
{
  "type": "error",
  "payload": {
    "msg": "NullReferenceException in Process1MinBar",
    "stack_trace": "...",
    "bar_time": "2026-04-27T09:32:00-04:00",
    "bar_in_progress": 0,
    "current_state": "Realtime"
  }
}

{
  "type": "warning",
  "payload": {
    "msg": "200-SMA not yet warmed up; emitting candidate with sma200_slope_available=false",
    "context": "first_session"
  }
}
```

### 3.16 `divergence` (L3, broker-vs-internal mismatch)

```json
{
  "type": "divergence",
  "payload": {
    "internal_state": "Active",
    "broker_position_qty": 0,
    "expected_qty": 1,
    "detected_at": "2026-04-27T10:15:00-04:00",
    "action": "halt_new_submissions"
  }
}
```

### 3.17 `news_wick_registered`

```json
{
  "type": "news_wick_registered",
  "payload": {
    "wick_kind": "lower",                  // "lower" | "upper"
    "level_price": 5605.00,
    "candle_time": "2026-04-27T11:15:00-04:00",
    "candle_volume": 237000,
    "yesterday_930_volume": 141000,
    "yesterday_330_volume": 127000,
    "ratio_to_max": 1.68,
    "active_until": "expires_when_higher_volume_observed"
  }
}
```

### 3.18 `pattern_b_state_change`

For Pattern B state machine debugging.

```json
{
  "type": "pattern_b_state_change",
  "payload": {
    "level_name": "Pr30L",
    "from_state": "Untouched",
    "to_state": "Breached",
    "breach_candle_high": 5613.50,
    "breach_candle_low": 5610.50,
    "breach_bar_time": "2026-04-27T09:31:00-04:00"
  }
}
```

### 3.19 `runner_target_update`

Emitted by L2 when the slope-conditional runner target changes mid-trade.

```json
{
  "type": "runner_target_update",
  "payload": {
    "signal_id": "sig_ES_2026-04-27_0932_001",
    "from_target_price": 5618.50,
    "to_target_price": 5620.00,
    "trigger": "slope_steepened",
    "fib_extension_pct": 200
  }
}
```

### 3.20 `decision_request` / `decision_response`

For HTTP ML scorer round-trip tracing.

```json
{
  "type": "decision_request",
  "payload": {
    "candidate_id": "ES_2026-04-27_0932_Pr30L_long_001",
    "endpoint": "http://localhost:7677/score",
    "feature_count": 71,
    "sent_at": "2026-04-27T09:32:00.500-04:00"
  }
}

{
  "type": "decision_response",
  "payload": {
    "candidate_id": "ES_2026-04-27_0932_Pr30L_long_001",
    "predicted_R": 1.85,
    "confidence": 0.72,
    "tier": "A",
    "round_trip_ms": 47,
    "received_at": "2026-04-27T09:32:00.547-04:00"
  }
}
```

### 3.21 `state_persisted`

Diagnostic. Every time `state.json` is written.

```json
{
  "type": "state_persisted",
  "payload": {
    "path": "C:\\seasonals\\cockpit\\sessions\\2026-04-27\\state.json",
    "trigger": "fill",
    "size_bytes": 2456
  }
}
```

---

## 4. File Structure and Component Layout

This section specifies the on-disk file structure, the regions/sections within each file, and the rationale for the split.

### 4.1 The two-file architecture

V2_5 lives in two files:

- `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMTradeCockpitV2_5.cs` — the L1 indicator. Target ~3500 lines after refactor (V2_4 was ~4600 with all the gating; we drop ~1100 lines of safety/scoring).
- `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Strategies\AMTradeStrategyV1.cs` — the L2/L3 hosting strategy. Target ~2500 lines including scorer, decision logic, all 12 safety gates, order routing, state persistence, and the abstain-event emitter.

### 4.2 Why two files (not three or one)?

NinjaScript's discovery and reload mechanics impose constraints. Each `.cs` file in `Indicators/` is compiled as a NinjaScript Indicator class (must inherit `Indicator`); each `.cs` file in `Strategies/` must inherit `Strategy`. The hosting Strategy needs to instantiate the Indicator (`AddDataSeries` + `Indicator(...)` factory pattern) and consume its events. This pattern is proven by `AMShadowObserverV1.cs` which already hosts V2_3.

Splitting L2 and L3 into separate files would mean creating a third `.cs` that inherits `Strategy` (only one Strategy can host an Indicator on a given chart instance). NinjaScript does not have a concept of "library .cs" that gets compiled in the same assembly without inheriting `Indicator` or `Strategy`. We could put L3 in a partial class `AMTradeStrategyV1.Safety.cs` if we want logical separation — and we do, see Section 4.5 — but the file remains a single compilation unit.

The two-file architecture also matches the Option A architecture from `nt8_safety_review.md` §A3 (the recommended path): "Build a NinjaScript Strategy that hosts V2_4, subscribes to OnSignal, makes a synchronous 2-second HTTP call, and submits via AtmStrategyCreate."

### 4.3 `AMTradeCockpitV2_5.cs` — top-level structure

```csharp
namespace NinjaTrader.NinjaScript.Indicators
{
    public class AMTradeCockpitV2_5 : Indicator
    {
        #region Properties (NinjaScriptProperty)
        // All user-tunable parameters
        #endregion

        #region Internal types
        // CandleBox, DayBoxes, LevelWatchState, CandidateEventArgs, FeatureVector
        #endregion

        #region State fields
        // currentDay, dayHistory, levelWatchStates, smaCache, ...
        #endregion

        #region Lifecycle (OnStateChange)
        // SetDefaults / Configure / DataLoaded / Realtime / Terminated
        #endregion

        #region OnBarUpdate dispatch
        // Bar routing for BarsInProgress; no try/catch swallowing
        #endregion

        #region Process30MinBar
        // Box capture, MOC, slope, multi-day master candles, news-wick detection
        #endregion

        #region Process1MinBar
        // VWAP, day-rollover, OR lock, day-type classification, candidate emission
        #endregion

        #region Detection — Pattern A
        // For each level inside [low, high], emit candidate with pattern_type="A"
        #endregion

        #region Detection — Pattern B (LevelWatchState lifecycle)
        // For each level, maintain Untouched → Breached → Armed → (Consumed | Invalidated) state
        // Emit candidate with pattern_type="B" on Armed transition
        // Emit pattern_b_state_change on every transition for debugging
        #endregion

        #region Feature extraction
        // BuildFeatureVector — computes the entire features struct for a candidate
        #endregion

        #region News-wick detection
        // Volume-outlier check; register and persist
        #endregion

        #region Box drawing and chart UI
        // RetainPRESERVE all V2_4 visual surfaces — chip legend, box rectangles,
        // pivot lines, VWAP line, anchored VWAP. UI is a separate concern from
        // the detection logic; do not delete chart drawings.
        // Pre-Place panel reused as "Candidate Visualizer" — shows recent candidates,
        // their classification, scorer decisions reported back from L2 via ChartObjects.
        #endregion

        #region Coach panel and verdict
        // The verdict line is informational only — driven by L1 day-type +
        // an optional handle to L2's most recent decision.
        #endregion

        #region JSONL logger
        // EventEmitter helper. All emit calls go through this single point.
        // Schemas enforced via per-event-type strongly-typed builders.
        #endregion

        #region Public events (in-process subscribers)
        // OnCandidate, OnBoxCapture, OnDayTypeChange, OnPhaseChange, OnBiasChange
        #endregion

        #region Properties exposing internal state to L2
        // Expose currentDay, dayHistory, sma200SlopeDelta, mocState as public read-only
        // for the hosting strategy that needs cross-layer access.
        #endregion
    }
}
```

#### Naming conventions in V2_5 indicator

- Public properties (NinjaScriptProperty): PascalCase, descriptive — e.g., `MaxLookbackDaysForLevels`, `EnablePatternB`.
- Internal state fields: camelCase, prefixed by area — e.g., `currentDay`, `levelWatchStates`, `vwapAccumulator`.
- Methods: PascalCase — e.g., `Process30MinBar`, `BuildFeatureVector`, `EmitCandidate`.
- Private helpers prefixed with verb — e.g., `BuildFeatureVector`, `EmitCandidate`, `ResetDailyLatch`.
- Event arg structs in CandidateEventArgs naming.

### 4.4 `AMTradeStrategyV1.cs` — top-level structure

```csharp
namespace NinjaTrader.NinjaScript.Strategies
{
    // Use partial class to logically separate L2 (decision) and L3 (safety)
    public partial class AMTradeStrategyV1 : Strategy
    {
        #region Properties (NinjaScriptProperty)
        // User-tunable parameters — scorer mode, thresholds, gate enables/configurations
        #endregion

        #region Internal types
        // SignalRequest, ScorerDecision, GateResult
        #endregion

        #region State fields
        // currentSignalState, signalEntry, signalStop, brokerPositionState
        #endregion

        #region Lifecycle (OnStateChange)
        // SetDefaults / Configure / DataLoaded (subscribe to indicator events here)
        #endregion

        #region OnBarUpdate (forward to L1, monitor signal lifecycle)
        // The hosting strategy receives bar events parallel to L1
        #endregion

        #region L1 event handlers
        // OnL1Candidate(args) — entry point for L2's per-candidate decision flow
        // OnL1BoxCapture(args) — for cross-layer state synchronization
        #endregion

        #region L2 — Decision flow (Score, Rank, Decide)
        // EvaluateCandidate(args) — the scoring + decision pipeline
        // ScoreHeuristic(features) — the rule-based scorer (V1)
        // ScoreHttp(features) — the ML scorer endpoint (V2)
        // RankCandidates(...) — when multiple candidates per bar
        // DecideTake(decision, candidate) — final yes/no
        #endregion

        #region L2 — Order construction and submission
        // BuildSignalRequest(candidate, decision)
        // SubmitOrder(request) — uses AtmStrategyCreate or Account.CreateOrder
        // OnExecutionUpdate / OnPositionUpdate handlers
        #endregion

        #region L2 — Order monitoring and exit
        // Hard stop, first target, runner target, time close, level-to-level exit
        // For L2's runner-target updates, reads live price + L1's published levels
        #endregion

        #region NT8 callbacks
        // OnExecutionUpdate, OnPositionUpdate, OnConnectionStatusUpdate, OnOrderUpdate
        // — all routed to L2 (for fill detection) and L3 (for divergence)
        #endregion
    }

    // Partial class continued in AMTradeStrategyV1.Safety.cs (logically)
    public partial class AMTradeStrategyV1
    {
        #region L3 — Safety gates
        // Each gate is a method: Evaluate{GateName}(SignalRequest req) → GateResult
        // GateRthWindow, GateDailyLossKill, GateMaxLosingTrades, GateCooldown, ...
        #endregion

        #region L3 — IsSubmissionAllowed orchestration
        // Calls each enabled gate in priority order. First veto wins. Emit abstain.
        #endregion

        #region L3 — State persistence (state.json)
        // PersistStateToJson() — atomic write
        // RestoreStateFromJson() — read on State.DataLoaded
        // Triggers: every fill, stop, target, lockout, reset, divergence
        #endregion

        #region L3 — Reconciliation
        // ReconcileBrokerVsInternal() — called on every 1-min bar
        // Emits divergence on mismatch
        #endregion

        #region L3 — Holiday and DST
        // LoadHolidayCalendar() — read parquet at startup
        // IsHolidayBlackoutToday()
        // IsEarlyCloseToday()
        // GetEffectiveCloseHourForToday()
        #endregion

        #region L3 — Manual kill switch
        // ManualKillSwitchClicked() handler (UI button)
        // ResumeAfterKillSwitch()
        #endregion

        #region L3 — JSONL emitter
        // Reuse the same EventEmitter helper as L1, with layer="L3" tag
        #endregion
    }
}
```

(In practice, NinjaScript's partial-class compilation across files is supported. We could put both partials in a single .cs to keep the code in one file. Either is acceptable; the L1/L2/L3 logical separation is the contract.)

#### Naming conventions in V2_5 strategy

- Public properties: PascalCase — e.g., `ScorerMode`, `MinExpectedR`, `EnableDailyLossKill`, `MaxDailyLossDollars`.
- Internal state: camelCase prefixed — `currentSignalState`, `signalEntry`, `realizedPnlDollarsToday`.
- Gates: `Gate{Name}` and `Evaluate{Name}` methods — e.g., `GateRthWindow`, `EvaluateGateRthWindow`.
- Event handlers: `OnL1Candidate`, `OnExecutionUpdate`.

### 4.5 NinjaScript discovery, namespace, and assembly compilation

NinjaScript compiles all .cs files under `Custom/` into a single assembly per category (Indicators, Strategies, AddOns). Discovery:

- All Indicator classes inherit `Indicator` and live in `Indicators/`. They are auto-detected and listed in NT8's Indicator selector.
- All Strategy classes inherit `Strategy` and live in `Strategies/`. They are auto-detected and listed in NT8's Strategy selector.
- Cross-class type references work freely within the same assembly. So `AMTradeStrategyV1` can reference `AMTradeCockpitV2_5` types directly.
- Namespaces: NT8 expects `NinjaTrader.NinjaScript.Indicators` and `NinjaTrader.NinjaScript.Strategies` respectively.
- Helper types (CandleBox, FeatureVector) defined inside the indicator class are accessible to the strategy via `AMTradeCockpitV2_5.FeatureVector`.

### 4.6 NinjaScriptProperty exposure rules

For both files: properties exposed via `NinjaScriptProperty` are user-tunable in the Properties pane and persist across NT8 restarts. We expose:

- All gate enables (`EnableRthWindowGate`, `EnableDailyLossKill`, etc.)
- All gate parameters (`MaxDailyLossDollars`, `CooldownMinutes`, etc.)
- Scorer parameters (`ScorerMode`, `MinExpectedR`, etc.)
- Detection toggles (`EnablePatternA`, `EnablePatternB`)
- Logging configuration (`JsonlLogFolder`)
- ATM template names

We do NOT expose:
- Internal feature vector field offsets
- Scorer model file paths (these go in the strategy's appsettings JSON)
- The 12 gates' priority order (hard-coded; safety-critical)

### 4.7 State machines (NinjaScript lifecycle)

`State.SetDefaults`: Set NinjaScriptProperty defaults. Initialize visual properties.
`State.Configure`: Add data series (`AddDataSeries(BarsPeriodType.Minute, 30)`, `AddDataSeries(BarsPeriodType.Minute, 1)`). Cache cross-instrument indicators.
`State.DataLoaded`: Locate `idx30Min`, `idx1Min` in BarsArray. L3 reads `state.json`. L1 initializes box captures from history. L1 instantiates LevelWatchStates. Subscribe to NT events.
`State.Realtime`: First live bar. Heartbeat starts. Manual kill button enabled.
`State.Terminated`: L3 persists final state.json. Unsubscribe events. Clean drawings.

---

## 5. NinjaScript-Specific Design Considerations

This section captures the NT8-specific gotchas that downstream agents must know. Most of these are documented in `failure_modes.md` and `v24_code_audit.md` — collected here as actionable rules for the implementers.

### 5.1 BarsInProgress routing for multi-timeseries

V2_5 uses two secondary series: 30-min and 1-min, both for the primary instrument. `OnBarUpdate` is invoked for each registered series. Always check `BarsInProgress` first:

```csharp
if (BarsInProgress == 0)        return;  // Primary series; we only use sec series
if (BarsInProgress == idx30Min) Process30MinBar();
else if (BarsInProgress == idx1Min) Process1MinBar();
```

**Race condition at simultaneous closes (10:00, 10:30, etc.):** when a 30-min and 1-min bar close on the same wall-clock time, NT8 dispatches both `OnBarUpdate` calls but the order is not guaranteed (`failure_modes.md` §1.1). Solution: cache reads of cross-series state with `volatile` keyword; on `Process30MinBar`, snapshot cached values into local fields at the top, mutate at the bottom. On `Process1MinBar`, prefer the cached values rather than re-reading `sma200_30min` directly.

### 5.2 `Times[idx][barsAgo]` indexing semantics

`Times[idx1Min][0]` is the bar-time of the just-closed 1-min bar. `Times[idx1Min][1]` is the previous bar. Always use barsAgo indexing; never `Bars.Items[i]` direct access. NT8 manages the bar buffer internally; bar indices shift on reconnects.

For `signalEntryBar` and similar absolute indices, prefer storing `signalTime` (DateTime) rather than `signalEntryBar` (int) — bar indices are non-persistent across reconnects (`failure_modes.md` §1.9).

### 5.3 Draw API tag conflicts and the prior-day box bug

V2_4 has known bugs where `Draw.Rectangle` tags collide between today's and yesterday's boxes (`v24_code_audit.md` §10.x). Solution: include the trading-day key in every drawing tag. Convention: `Box_{Name}_{TradingDayYYYYMMDD}_{Subtag}`. This is the V2_4 fix that we preserve in V2_5.

### 5.4 ATM template invocation patterns

L2 can submit orders via two NT8 paths:

- **`AtmStrategyCreate(...)` (preferred for live):** wraps a pre-configured ATM template. Stop and target are managed by NT internally. Pros: simplest, NT handles partial fills, OCO behavior. Cons: opaque to L2; we don't see the broker order IDs of the stop/target legs without `AtmStrategy*` callbacks.
- **`Account.CreateOrder(...) + SubmitOrderUnmanaged(...)` (preferred for transparency/testing):** L2 places entry and exits as separate orders. Pros: full visibility. Cons: L2 must implement OCO logic itself; partial-fill handling falls on us.

For V1, prefer ATM templates (it's what AM's pre-existing setup expects). Add `EntrySubmitMode` parameter to allow Unmanaged path for test/sim variants.

### 5.5 OnBarClose vs OnEachTick

V2_4 uses `OnBarClose`. V2_5 follows the same default. All evaluation logic happens at bar close. Tick-by-tick processing is not necessary because: (a) AM's rules are bar-level (5-min and 1-min), (b) NT8's bar-data fill inference matches bar-close semantics, (c) tick-level processing introduces non-determinism via tick ordering.

For Pattern B's "next bar must hold a higher low" check, we evaluate on the next 1-min bar's close — not intrabar.

The exception: order monitoring. `OnExecutionUpdate` fires on each broker execution event (not bar-level). L2 subscribes to it for fill detection.

### 5.6 State persistence across NT restarts

What survives a NT restart on its own: nothing in V2_4 (`failure_modes.md` §2.3). What survives in V2_5: everything in `state.json`, restored at `State.DataLoaded` if today's date matches. Specifically:
- `signalsToday`, `fillsToday`, `realizedPnlDollarsToday`, `losingTradesToday`
- `lockoutActive`, `lockoutReason`, `lockoutExpiry`
- `cooldownActive`, `lastStopTime`
- `currentSignalState`, `signalDirection`, `signalEntry`, `signalStop`, `signalTarget`
- `positionConfirmedAtBroker`, `positionQty`
- `levelWatchStates` (Pattern B state machines for in-progress breach setups)

State is written atomically: write to `state.json.tmp`, rename to `state.json`. This is essential — if NT crashes mid-write, the old state.json is unaffected.

### 5.7 Error handling philosophy

V2_4's `try/catch` in `OnBarUpdate` with Historical-silent (line 956-963) is a known defect (`failure_modes.md` §1.2). V2_5 inverts:

- All exceptions are caught at the top-level dispatch but re-thrown after logging.
- Every caught exception emits an `error` event with full stack trace.
- `error` events fire in BOTH Historical and Realtime.
- A daily counter of caught exceptions is exposed in the Pre-Place / Coach panel.
- The strategy decides how to react — a single error during cold-start may be acceptable; cumulative errors should escalate.

### 5.8 DST and holiday handling

DST: NT8 uses Exchange Time Zone for futures bar timestamps automatically. As long as we compare `Times[idx][barsAgo].Hour` to ET integers (9, 18, 0, 4, 9.5 = 9:30, 13:30, 15:00), DST is handled. Do NOT use `DateTime.Now.Hour` (which is wall-clock).

Holiday: NT8 has session templates that handle exchange close. V2_5 does not rely on NT8's session template — we read our own holiday calendar (parquet, updated quarterly via `pandas_market_calendars`). On full-close days, L3's holiday gate blocks all submissions. On early-close days, L3 overrides `RthCloseHourEt` to the early-close time for that day (e.g., 13:00 instead of 15:00).

### 5.9 BarsRequired and warmup periods

- 200-SMA on 30-min: requires 200 30-min bars (~ 4-6 trading days of NT history per `MaxLookback`).
- 50-SMA on 30-min: requires 50 30-min bars (~ 1-2 trading days).
- ADR20: requires 20 daily H-L computations.
- VWAP: starts fresh each session.

L1 emits candidates regardless of warmup state. The candidate's feature vector includes `*_available: bool` for each warmup-dependent feature. L2's heuristic can choose to skip-and-abstain on unavailable features (default for V1) or weight them as zero. The contract is: feature missing is signaled, not silently dropped.

### 5.10 ChartControl.Dispatcher for async UI updates

For the candidate visualizer panel updates (replacing V2_4's Pre-Place panel), use:

```csharp
ChartControl.Dispatcher.InvokeAsync(() => {
    // UI updates here — e.g., update candidate list, scorer decision badge
});
```

This avoids cross-thread access exceptions. NT8's UI thread is separate from the chart's data thread.

### 5.11 The two-layer event subscription (in-process and JSONL)

L1 emits each event two ways:
- **JSONL**: file write to `events.jsonl`. This is the audit log; consumed by dashboards, replay tools, downstream Python.
- **In-process C# event**: `OnCandidate` / `OnBoxCapture` / etc. This is for L2 to subscribe in real-time without the file-system round-trip.

Both must agree. The `EventEmitter` helper class is the single point where both happen, in this order: (1) build the structured payload, (2) write to JSONL, (3) fire the C# event. If either fails, log to the diagnostic counter.

### 5.12 Mid-session indicator load and warmup

User attaches V2_5 at 11:00 AM ET. NT8 replays history. L1 captures box events during replay (Historical mode). At `State.Realtime`, L1 has a complete `currentDay` already populated. JSONL events for backfill bars are emitted with `t` = bar-time (correct) but with a "replay" marker. State persistence ensures L3's safety counters are intact even if today's history wasn't loaded fresh.

### 5.13 NT8 Replay engine handling

NT8's Market Replay reports `State == State.Realtime` even though it's historical replay. To avoid logging replay events as live signals: V2_5 checks `IsInReplay` in addition to `State`. Replay-mode events tag `replay=true` in the JSONL payload. L3's manual kill-switch is also disabled in replay (cannot accidentally kill orders during testing).

### 5.14 Multiple charts of the same instrument

If the user opens two ES 1-min charts, V2_5 gets two independent indicator instances. Each writes to the same `events.jsonl` file. Solution: use a process-level named mutex around `File.AppendAllText`, and tag each event with `instance_id` so the dashboard can deduplicate.

---

## 6. Detection (L1) Precise Specification

This section is the L1 implementer's contract. Read in conjunction with Section 2.1 (the layer responsibility) and Section 3 (event schemas).

### 6.1 Master candle box capture timing

The 30-minute master candles, in time order:

| Code | Name | ET capture time | Notes |
|---|---|---|---|
| A | Close330 | 15:30-16:00 | "Prior-day institutional candle." For ES/NQ/GC. CL: 14:00-14:30 (CL close is 14:30). |
| B | GlobEx | 18:00-18:30 | Overnight session open. Same time for all instruments. |
| | Midnight | 00:00-00:30 | Reference/diagnostic (mid-Mid). |
| C | Europe | 04:00-04:30 | Overnight wrap; Europe session open. |
| D | RTH930 | 09:30-10:00 | Cash open. CL: 09:00-09:30 (fix CL bug). |
| E | Close130 | 13:30-14:00 | AM's "daily turn-around level." Add to V2_5. |

The capture happens when `Process30MinBar` fires for the bar at exactly h:m matching the instrument's ET schedule. The institutional box (`institutionalBox`) starts as Close330 (or Close130 if no Close330 yet) and may be promoted to RTH930 via `RunContainmentCheck` if RTH930 is wider.

Per-instrument adjustments (from `v24_code_audit.md` §9):

```
isCL = Instrument.MasterInstrument.Name == "CL"
rthOpenHour = isCL ? 9 : 9
rthOpenMinute = isCL ? 0 : 30
closeHour = isCL ? 14 : 15
closeMinute = isCL ? 30 : 0
instCloseHour = isCL ? 10 : 15
instCloseMinute = isCL ? 0 : 30
```

V2_4's CL bug (rthOpenMinute hardcoded to 30) is fixed in V2_5.

### 6.2 Pattern A — Simple level retest

V2_4's primary entry pattern. The mechanic:

For every 1-min bar at close, for every tracked level `L_i` whose price is inside `[bar.Low, bar.High]`:
- Compute `is_long_setup = bar.Close >= L_i.Price` (level held as support; price closed above)
- Compute `is_short_setup = bar.Close <= L_i.Price` (level held as resistance; price closed below)
- For each of (LONG, SHORT) where the setup holds, emit a `candidate` event with `pattern_type="A"`, the appropriate direction, and the full feature vector.

Note: a single bar can produce multiple candidates if multiple levels are in range. There is no first-touch latching at L1. The `already_touched_today` feature flag is computed and emitted, but L1 does not use it to suppress emission.

The retrace_side check (V2_4 used as a hard filter; we move it to a feature flag):
- `retrace_side = is_long_setup ? (L_i.Price < bar.Open) : (L_i.Price > bar.Open)`
- For touches at exactly `bar.Open`, `retrace_side = null` and `retrace_side_at_open = true` (V2_4 silently dropped these; V2_5 surfaces as a candidate with the flag).

### 6.3 Pattern B — Look-below-and-fail / Look-above-and-fail

The breach-and-confirm pattern. AM's verbatim rule (apr-24): *"I rarely take a breakdown trade. What I will take is a failed retest, a look above and fail, a look below and fail."*

Per AM's spec (apr-24 line 117-130):

```
Breach candle = ONE 1-minute bar with low < L AND close >= L (long setup; flip for short).
Confirmation = next 1-min bar must hold higher low (long) or lower high (short).
Entry trigger = breach candle's high (long) or low (short).
Stop = breach candle's low (long) or high (short).
```

This is a SINGLE-BAR pattern (not 2-bar). The breach and recovery happen within one bar.

**LevelWatchState — the state machine per level per session:**

```csharp
public enum LevelWatchStateValue {
    Untouched,    // no interaction yet
    Breached,     // just observed: low < level && close >= level (long); or high > level && close <= level (short)
    Armed,        // breach confirmed by next bar (or breach candle is the only bar; 1-bar pattern)
    Consumed,     // candidate emitted; waiting for entry
    Invalidated   // breach candle's low (or high) was taken out before confirmation
}

public class LevelWatchState
{
    public string LevelName;
    public double LevelPrice;
    public LevelWatchStateValue State = LevelWatchStateValue.Untouched;
    public CandleBox AnchorCandle;    // the breach candle, when Breached
    public DateTime BreachTime;
    public string Direction;          // "LONG" or "SHORT"
}
```

**Lifecycle on each 1-min bar:**

1. **Untouched → Breached:** if `bar.Low < L && bar.Close >= L`, transition to Breached; capture `AnchorCandle = bar`. (Long setup.)
2. **Breached → Armed:** the breach itself confirms (1-bar pattern per AM apr-24); on the next bar's close, if next.low > AnchorCandle.Low, mark Armed. Emit candidate with `pattern_type="B"`, `lws_state="Armed"`. The candidate represents an entry opportunity at AnchorCandle.High with stop at AnchorCandle.Low. *This is the firing event.*
3. **Breached → Invalidated:** if next.low ≤ AnchorCandle.Low, the failed-retest itself failed. State Invalidated. Emit `pattern_b_state_change`. No candidate emitted in either direction.
4. **Armed → Consumed:** if a subsequent bar's high crosses AnchorCandle.High, the entry "trigger" is hit. Emit a second candidate with `lws_state="Consumed"` and `pattern_type="B"` indicating the trigger crossed (informational; L2 may already have submitted on the Armed candidate).
5. **Re-entry:** state returns to Untouched only at session rollover (handled by L3's daily reset).

For the SHORT mirror: high > L && close <= L → Breached; next bar high < AnchorCandle.High → Armed; etc.

**Multi-day scope:** LevelWatchStates persist for `MaxLookbackDaysForLevels` sessions. Specifically, levels for the prior-day master candles get LevelWatchStates that re-arm at the next session's open. State is in `state.json`.

**Edge cases:**
- Breach candle is the last 1-min bar of session: state stays Breached; transition continues next session.
- Multiple breaches of the same level on the same day: latch the state (Consumed → reset to Untouched only at session rollover) so we don't fire a Pattern B candidate twice.
- Breach + Armed in same bar (rare; the bar both breaches and confirms via prior bar's prior context): emit single Armed candidate.

### 6.4 News-candle wick detection

AM's spec (apr-24 line 338-364): mid-session candle volume > max(yesterday 9:30 vol, yesterday 3:30 vol) → register the wick as a level. Slope-up days register the lower wick as support; slope-down days register the upper wick as resistance.

**Implementation:**

In `Process1MinBar` (RTH only), after each bar close:
```csharp
if (currentBarVolume > NewsVolumeMultiplierThreshold * 
    Math.Max(priorDay930Volume, priorDay330Volume))
{
    if (sma200SlopeSign == "Up")
        RegisterNewsWick(NewsWickKind.Lower, bar.Low, bar);
    else if (sma200SlopeSign == "Down")
        RegisterNewsWick(NewsWickKind.Upper, bar.High, bar);
    else
        // Slope flat: undefined per apr-24; emit warning, do not register.
        EmitWarning("News-wick detected but slope flat; skipping registration.");
}
```

**Persistence:** "as long as it's the highest-volume candle in recent days" — replace the registered wick when a higher-volume candle prints in the next N days (default N=3). Persist via `state.json`.

**Exposure:** registered news wicks become tracked levels for future bars. Each bar, if `bar.Low <= level <= bar.High` for the wick price, emit a candidate. Pattern A or Pattern B applies as for any level. Feature flag `news_wick_active_today=true` and `news_wick_distance_pts` populated.

### 6.5 1:30 PM candle as a level

AM apr-16 / mar-6: the 1:30 PM ET candle is tracked. V2_4 omits it (`gap_to_am.md` GAP11). V2_5 captures it via the standard 30-min processor at `h==13 && m==30`. Box code `Close130`. Levels `Pr130H` (high), `Pr130L` (low) added to the candidate pool from 14:00 onward.

### 6.6 Multi-day master-candle revisits

AM mar-6 line 177: she tracks 4 AM candles from t-1, t-2, t-3 (the last 3 days). V2_4 has `dayHistory` populated but does not expose multi-day levels as candidates (`gap_to_am.md` GAP13). V2_5 exposes:
- `Pday1Close330H`, `Pday1Close330L` — yesterday's 3:30 candle
- `Pday2Close330H`, `Pday2Close330L` — two-days-ago 3:30 candle
- `Pday3Close330H`, `Pday3Close330L` — three-days-ago 3:30 candle
- `Pday1Europe4AMH`, etc. — same for 4 AM candles

These add to the candidate pool as soon as they're available. `dayHistory` already contains the data; we just need to expose them.

### 6.7 VWAP and AnchVWAP — surfaced as permission levels

V2_4 explicitly excludes VWAP/AnchVWAP from the candidate pool with the comment "VWAP is permission, not destination." V2_5 surfaces them but with `is_permission_level=true`. L2's heuristic and ML scorer are expected to weight permission-level candidates much lower; they're emitted because:
- Some setups (per `jsonl_data_analysis.md` Q7) actually use VWAP — both of V2_4's 2 historical signals were VWAP touches.
- The data should not be silently lost.

### 6.8 Pivots — daily Pivot Points and Woody's

V2_4 draws PP/R1-R3/S1-S3 but does not use them as candidates. V2_5 adds them to the candidate pool with `level_name="PP" / "R1" / ... / "R4" / "S1" / ... / "S4"`. Woody's pivots use the prior-day H/L/C and a different formula than standard daily pivots; we use Woody's per AM apr-8.

R3 / R4 also feed an exhaustion gate that L2 may consume: a feature flag `is_above_r3=true` is set on candidates above R3. L2's heuristic weighs this as a strong negative signal for fresh longs (per AM apr-8: above R3 = "very extended, short-covering rally territory").

### 6.9 50% midpoint of master candles

Each master candle exposes its 50% midpoint as a derived level: `Close330Mid`, `GlobExMid`, etc. This is the "MidMid" level V2_4 already exposes for Midnight box; V2_5 generalizes to all master candles.

The 50% line is also AM's "tighten-on-add" reference (apr-24 line 209). Surface as a candidate level.

### 6.10 Rolling 30-min Pr30 H/L

V2_4 maintains `Pr30H@HHmm` and `Pr30L@HHmm` with timestamp suffix in the latch key, so each new 30-min roll resets the latch. V2_5 keeps this — Pr30 is fundamentally a continuous-rolling level.

### 6.11 Feature vector — the complete schema

Section 3.3's `features` block is the complete schema. The L1 implementer must:
1. Compute every field on every candidate emission.
2. Set `*_available: bool = false` for any field that cannot be computed.
3. Never emit NaN.

The feature vector is the L2 scorer's sole input. It is also the input to the Python ML scorer (`pattern_scorer_rt2_1`'s 71-feature schema), so V2_5's feature vector is a superset that maps 1:1 to the Python schema for ML interop.

### 6.12 Edge cases and what could go wrong

- **Multiple Pattern B candidates from the same level on the same day.** Solution: LevelWatchState transitions to Consumed on Armed-candidate emission; resets only at session rollover.
- **Pattern A and Pattern B simultaneously fire on the same level on the same bar.** Solution: emit both candidates with distinct IDs. L2 ranks them; usually Pattern B is preferred.
- **VWAP touch at exact bar open.** Solution: emit candidate with `retrace_side=null` and `retrace_side_at_open=true`. L2 decides.
- **Permission-level candidates dominating the rank.** Solution: L2's heuristic weights `is_permission_level=true` as a -0.20 penalty on `score`. (Tunable.)
- **First few sessions with 200-SMA not warmed up.** Solution: `sma200_slope_available=false`. L2 may skip with reason="warmup_incomplete" or take with reduced confidence.
- **Mid-session indicator attach.** Solution: L1 captures all box events during NT8's history replay. L3 reads `state.json` for prior session counters. State is consistent.
- **`Process30MinBar` and `Process1MinBar` race on simultaneous closes.** Solution: snapshot cross-series state at the top of each method into local fields; mutate at the end. Use volatile cache. (See Section 5.1.)

---

## 7. Strategy and Scoring (L2) Specification

This section is the L2 implementer's contract. Read in conjunction with Section 2.2 and Section 3.

### 7.1 Subscription to L1's candidate stream

L2 subscribes to L1's `OnCandidate` event in the strategy's `State.DataLoaded` block:

```csharp
private AMTradeCockpitV2_5 hostedIndicator;

protected override void OnStateChange()
{
    if (State == State.DataLoaded)
    {
        hostedIndicator = AMTradeCockpitV2_5(...);  // factory call
        AddChartIndicator(hostedIndicator);
        hostedIndicator.OnCandidate += OnL1Candidate;
        hostedIndicator.OnBoxCapture += OnL1BoxCapture;
    }
}

private void OnL1Candidate(CandidateEventArgs args)
{
    // Decision pipeline
    var decision = EvaluateCandidate(args);
    if (decision.ShouldTake)
    {
        var request = BuildSignalRequest(args, decision);
        var l3Result = SafetyL3.IsSubmissionAllowed(request);
        if (l3Result.Allowed)
            SubmitOrder(request);
        else
            EmitAbstain(args, "L3", l3Result.GateName, l3Result.Reason);
    }
    else
    {
        EmitAbstain(args, "L2", decision.AbstainGate, decision.AbstainReason);
    }
}
```

### 7.2 The heuristic scorer (V1)

The heuristic scorer is a function `Score(features) -> ScorerDecision`. It is rule-based; it approximates AM's gestalt. Output:

```csharp
public struct ScorerDecision
{
    public double PWin;             // [0, 1]
    public double ExpectedR;        // expected R-multiple
    public string SizeBucket;       // "Green" | "Orange" | "Gray"
    public string TargetChoice;     // "level_to_level" | "fib_150" | "fib_200" | "fib_250"
    public double Confidence;       // [0, 1]
    public string AbstainReason;    // null if accepted; "scorer_min_p_win" etc. if rejected
}
```

**Heuristic rules (V1 implementation):**

```
score = 0.50  // baseline

// Day-type strength
+ 0.20 if features.day_type_v2_3node == "LongTrend" || "ShortTrend"
+ 0.10 if features.day_type_v2_3node == "CautiousLong" || "CautiousShort"
- 0.10 if features.day_type_v2_3node == "Sideways"

// Slope alignment with direction
+ 0.15 if (features.sma200_slope_sign == "Up" && direction == "LONG")
+ 0.15 if (features.sma200_slope_sign == "Down" && direction == "SHORT")
- 0.10 if (counter-slope direction)

// MOC validation (sizing-relevant)
+ 0.10 if features.moc_state == "Green"
+ 0.05 if features.moc_state == "Orange"
- 0.05 if features.moc_state == "Gray"

// Level priority
+ 0.10 if level_name in {"PrInstH", "PrInstL", "Close330"}  // institutional candle
+ 0.05 if level_name in {"Europe", "GlobEx"}
+ 0.05 if features.is_highest_volume_in_cluster
+ 0.10 if features.confluence_count >= 4

// Permission level penalty
- 0.20 if features.is_permission_level

// Pattern B preference
+ 0.10 if pattern_type == "B"  // AM's preferred entry

// R3/R4 exhaustion (no fresh longs)
- 0.30 if direction == "LONG" && features.dist_to_r3 < 0  // price above R3

// Time-of-day
- 0.10 if features.minutes_until_rth_close < 60

// News-wick boost
+ 0.10 if features.news_wick_active_today && features.news_wick_distance_pts is small

// Already-touched penalty
- 0.10 if features.already_touched_today  // (latch warning, not block)

// Day-of-week (Friday escalation)
+ 0.05 if features.day_of_week == "Friday" && features.day_type_v2_3node not "Sideways" && features.moc_state == "Green"

p_win = clip(score, 0, 1)
```

For `expected_R`: a separate computation based on stop_distance and target_distance (level-to-level distance from the candidate's `runner_target_options`). Default formula:
```
expected_R = (target_distance / stop_distance) * p_win - (1 - p_win) * 1.0
```

`size_bucket`: from MOC state (Green = full, Orange = half, Gray = no/half).
`target_choice`: from slope sign and magnitude (steep slope → Fib 200; flat → level_to_level; ML refines).
`confidence`: based on how many features were available. Lower confidence when warmup incomplete.

### 7.3 The HTTP ML scorer (V2)

For V2: HTTP POST to the `pattern_scorer_rt2_1` `/score` endpoint. Request body:

```json
{
  "instrument": "ES 06-26",
  "session_date": "2026-04-27",
  "candidate_id": "ES_2026-04-27_0932_Pr30L_long_001",
  "features": { /* the entire feature vector */ }
}
```

Response:

```json
{
  "candidate_id": "ES_2026-04-27_0932_Pr30L_long_001",
  "predicted_R": 1.85,
  "tier": "A",
  "confidence": 0.72,
  "p_win": 0.58,
  "size_bucket": "Green",
  "target_choice": "fib_200",
  "abstain_reason": null
}
```

V2_5 emits `decision_request` and `decision_response` events for every HTTP call. Timeout: 2000ms (matches `AMShadowObserverV1`'s proven latency). On timeout: fall back to heuristic, emit warning. Note: the live feature engine for the rt2_1 endpoint is NOT YET BUILT (per `pattern_scorer_rt2_1/DEPLOY.txt`'s "KNOWN LIMITATION"). V2_5 makes the HTTP call work; the Python side remains a future feature.

### 7.4 Decision logic (take vs abstain)

```csharp
public bool DecideTake(ScorerDecision decision, CandidateEventArgs candidate)
{
    if (decision.PWin < MinWinProbability)         return false;  // abstain: scorer_min_p_win
    if (decision.ExpectedR < MinExpectedR)          return false;  // abstain: scorer_min_expected_r
    if (decision.Confidence < MinConfidence)        return false;  // abstain: scorer_min_confidence
    if (decision.AbstainReason != null)             return false;  // scorer explicitly opted out
    return true;
}
```

### 7.5 Multiple candidates per bar — ranking

When L1 emits N candidates in a single 1-min bar (multiple levels in range), L2 batches them and ranks by `score = (decision.PWin * decision.ExpectedR * decision.Confidence)`. L2 then takes top-K (where K = `MaxCandidatesPerBarToTake`, default 1). The remaining candidates emit `abstain` with `layer="L2"`, gate="rank_too_low".

This is *not* "best-only by distance" (V2_4's broken approach which silently dropped duplicates). It's "top-K by score." On a sideways day with 5 candidates ranking by score, the top 1 fires; the other 4 are explicit abstains (recoverable: never; they were beat).

### 7.6 Position management

V1 default: max 1 position per instrument. Pending limits replace older pending limits. This matches AM's "one position at a time" rule (apr-9 line 94-99: "limits only" + cancel-others-on-fill).

For V2: AM's 50% midpoint add-rule (apr-24 line 209) — when an Active position is in the green and a confluence-add condition fires, L2 emits a second `signal` for the add. L3 has a sub-rule that allows 1 add per Active position. Total position cap stays at 2 (the original + one add).

Justification: AM's biggest winners come from the convergence add. Without it, V2_5 caps at AM's typical small wins. With it, we can express the right tail. But V1 doesn't ship the add-mechanic (deferred per `improvement_roadmap.md` C-20); V2 does.

### 7.7 Order submission — ATM templates vs unmanaged

For V1: ATM templates via `AtmStrategyCreate(...)` with the templates `AM_Normal_2MES` and `AM_Wide_1MES`. The ATM template handles entry, stop, target. We rely on the template's pre-configured stop and target levels.

For limit-only entries: ATM template starts with a limit order at `signalEntry`. The stop-market and target-limit are pre-attached (OCO bracket). On `OnExecutionUpdate` for the entry fill, the stop and target are auto-placed.

For runner targets that change mid-trade (slope-conditional): use `AtmStrategyChangeStopTarget` or cancel and re-submit. Document the policy: V1 uses a single first-target close (50% partial at 100% Fib), runner stays on candle-walk per AM's apr-9 rule. V2 adds the slope-conditional runner via API calls.

Limit-only entries are AM's hard rule (apr-9 line 94: "I never use market orders"). V2_5 enforces this: no order submission with `OrderType.Market`. If the broker rejects the limit, L3 emits `error`; we do not market-fill.

---

## 8. Safety (L3) Specification

Section 2.3 already lists the 12 gates with their parameters and trigger conditions. This section deepens the specification with logging, recovery, and edge-case handling.

### 8.1 Gate logging discipline

Every gate has an `Evaluate{GateName}(SignalRequest req)` method returning `GateResult`:

```csharp
public struct GateResult
{
    public bool Allowed;
    public string GateName;
    public string Reason;
    public DateTime? RecoverableUntil;
    public Dictionary<string, object> StateSnapshot;
}
```

If `Allowed=false`, the calling orchestrator (`IsSubmissionAllowed`) emits an `abstain` event with:
- `layer="L3"`
- `gate_name`
- `reason`
- `recoverable_until_time`
- `gate_state_snapshot`

This is the audit trail for "why was the trade blocked?"

### 8.2 Gate priority and short-circuit

Gates are evaluated in this order:
1. Connection state guard (no point in anything if disconnected)
2. Manual kill switch (operator override)
3. Holiday gate (blackout day)
4. RTH window (outside trading hours)
5. Margin guard (must always check)
6. Position state guard (no double-up)
7. Daily loss kill ($)
8. Daily loss kill (%)
9. Max losing trades / consecutive stops
10. Cooldown after stop
11. Max signals per day
12. Heartbeat self-check

First veto wins. Subsequent gates do not run for that signal. The reason is the first-fired veto. (This is intentional — an operator who sees "rth_window_closed" knows to wait until 9:30; a multi-veto report would be confusing.)

### 8.3 The "explicit abstain" recovery contract

Every abstain event MUST include `recoverable_until_time`. Examples:

- `rth_window_closed` → next session's `rthOpen` time.
- `daily_loss_kill` → next session ("00:00 of next trading day" or null with `recovery_action="next_session"`).
- `cooldown_after_stop` → `lastStopTime + CooldownMinutes`.
- `max_signals_per_day` → next session.
- `position_already_active` → null with `recovery_action="position_closes"`.
- `manual_kill_switch` → null with `recovery_action="manual_resume"`.
- `connection_error` → null with `recovery_action="connection_restored"`.

The trader and dashboard can answer "when can I trade again?" from the JSONL alone — a critical observability requirement.

### 8.4 State persistence (state.json) — the schema

```json
{
  "session_date": "2026-04-27",
  "instrument": "ES 06-26",
  "v2_5_version": "v25.1",
  "schema_version": "v25.1",
  "last_updated": "2026-04-27T09:48:30-04:00",
  "counters": {
    "signals_today": 1,
    "fills_today": 1,
    "losing_trades_today": 0,
    "winning_trades_today": 1,
    "realized_pnl_dollars_today": 150.00,
    "consecutive_stops": 0
  },
  "lockout": {
    "active": false,
    "trigger": null,
    "expires_at": null
  },
  "cooldown": {
    "active": false,
    "last_stop_time": null,
    "expires_at": null
  },
  "signal_state": {
    "current": "None",
    "signal_id": null,
    "direction": null,
    "entry": null,
    "stop": null,
    "target": null,
    "broker_position_qty": 0,
    "broker_order_id": null
  },
  "level_watch_states": [
    {
      "level_name": "Pr30L@1030",
      "state": "Untouched",
      "anchor_candle_time": null,
      "anchor_candle_high": null,
      "anchor_candle_low": null
    },
    /* ... per-level state */
  ],
  "news_wicks_active": [
    {
      "wick_kind": "lower",
      "level_price": 5605.00,
      "candle_time": "2026-04-27T11:15:00-04:00",
      "candle_volume": 237000,
      "active_since": "2026-04-27T11:15:00-04:00"
    }
  ],
  "manual_kill_switch_active": false
}
```

Atomic write protocol: write to `state.json.tmp`, fsync, rename to `state.json`. On read failure or corruption: log `warning`, initialize with defaults, continue.

### 8.5 Reconciliation contract

Every 1-min bar, L3 calls `ReconcileBrokerVsInternal()`:

```csharp
public ReconciliationResult Reconcile()
{
    var brokerQty = GetBrokerPositionQty();
    var internalState = currentSignalState;
    var expectedQty = GetExpectedQtyFromState(internalState);
    
    if (brokerQty != expectedQty)
    {
        EmitDivergence(internalState, expectedQty, brokerQty);
        haltNewSubmissions = true;
        return ReconciliationResult.Divergence;
    }
    
    return ReconciliationResult.Aligned;
}
```

On divergence: halt new submissions, emit alert via SMS/push, manual operator action required.

### 8.6 Holiday and DST handling — implementation specifics

V3 (after launch) integration with `pandas_market_calendars`:
1. At startup: read `holidays.parquet` (a precomputed list of full-close and early-close days for ES/NQ/CL/GC).
2. Each session: check if today is in the list.
3. Full-close: gate fires from the start of the session. All entries blocked. Emit `holiday_blackout` abstain.
4. Early-close: override `closeHour:closeMinute` for today (e.g., 13:00 instead of 15:00). All time-relative computations (entry cutoff, time-close) use the override.

For V1 minimal: hard-code the major US holidays and early-closes as a List<HolidayEntry>. Update quarterly via a manual sync.

DST: as documented in Section 5.8. Rely on NT8's exchange-time bar timestamps.

### 8.7 Manual kill-switch interface

A button on the chart UI (replacing V2_4's STAGE → CONFIRM button area) labeled "HALT — CANCEL ALL & BLOCK NEW". On click:
1. Cancel all pending broker orders for the instrument.
2. Set `ManualKillSwitchActive = true` in state.
3. Emit `manual_kill_switch_activated` event.
4. Log to JSONL with operator name and timestamp.
5. Block all subsequent submissions until `Resume` is clicked.

Resume button: re-enable submissions.

For NT8 keyboard binding: configure F12 (or similar) as the "Halt" hotkey via NT8's keyboard configuration. This is a backup to the chart button.

---

## 9. Test Strategy

This section defines the test agent's deliverables. The test harness lives in `C:\seasonals\baiynd_autotrader\v25_rebuild_2026-04-27\tests\`.

### 9.1 Contract compliance test (the central test)

**Objective:** Verify INV-L1-1 + INV-L2-1: every `candidate` event is followed by either a `signal` or an `abstain`.

**Implementation:**
- Replay 6 months of V2_4 JSONL through V2_5 L1+L2+L3.
- Parse the resulting V2_5 JSONL.
- For every `candidate` event with `candidate_id=X`, check that:
  - At least one of {`signal` with `candidate_id=X`, `abstain` with `candidate_id=X`} exists.
- Assert: zero violations.

**Implementation language:** Python script `tests/contract_compliance.py`. Reads JSONL, builds a dict of candidate_id → (signal | abstain), verifies completeness. Pytest-runnable.

### 9.2 Smoke test

**Objective:** Verify V2_5 indicator + AMTradeStrategyV1 compile and load on a chart without errors.

**Implementation:**
- Manual: open NT8, attach V2_5 to a chart, attach AMTradeStrategyV1 hosting V2_5. Confirm: no compile errors, no load errors, indicator draws on chart, strategy starts.
- Automated: NT8 has no automated chart load capability for full integration. The smoke test is human-confirmed before each release.

### 9.3 Replay equivalence test

**Objective:** TEST-L1-1. For every V2_4 historical signal, V2_5 must emit a candidate.

**Implementation:**
- Parse V2_4's `signal` events from 6 months of JSONL.
- Replay the same date range through V2_5.
- For each V2_4 signal at (date, time, level, direction), verify V2_5 emitted a `candidate` for the same (date, time, level, direction).
- Allow V2_5 to emit additional candidates that V2_4 didn't (this is the expected behavior — V2_5 surfaces silent drops).
- Assert: 100% recall of V2_4's actual signals as V2_5 candidates.

### 9.4 Pattern B detection test

**Objective:** Verify INV-L1-2 (Pattern B emission) and the LevelWatchState transitions.

**Implementation:**
- Synthetic bar sequences in `tests/pattern_b_synthetics.py`:
  - Sequence 1: bar with `low < L && close >= L`, then bar with `low > prev.low` → expect Armed → expect candidate emitted.
  - Sequence 2: bar with `low < L && close >= L`, then bar with `low <= prev.low` → expect Invalidated → no candidate.
  - Sequence 3: ditto for short.
- Assert: state transitions match expected; `pattern_b_state_change` events fire on each transition.

### 9.5 Safety gate tests

**Objective:** Verify TEST-L3-1 — each gate triggers correctly.

**Implementation:** For each of the 12 gates:
- Set up the trigger condition (e.g., for gate 5 cooldown: set `lastStopTime` to 5 minutes ago, `CooldownMinutes=30`).
- Inject a candidate-of-interest.
- Expect the L2/L3 chain to produce an abstain with `gate_name=cooldown_after_stop`, `reason=...`, `recoverable_until_time` populated.
- Assert payload schema matches Section 3.5.

### 9.6 Determinism test

**Objective:** Verify INV-L1-7 + INV-L2-2.

**Implementation:**
- Run V2_5 twice on the same JSONL input.
- Diff the resulting event sequences.
- Allow only differences in `wall_clock` timestamps for non-bar-driven events (heartbeat).
- Assert: zero non-trivial differences.

### 9.7 State persistence test

**Objective:** Verify TEST-L3-2.

**Implementation:**
- Start L3 with empty state.
- Inject 5 signals, 1 stop. State now: `signalsToday=5, fillsToday=4, realizedPnlDollarsToday=-50, lastStopTime=...`.
- Kill the strategy mid-session (simulated via test harness).
- Restart. Verify state.json was written; verify L3 restores all counters.
- Assert: counters match pre-kill values.

### 9.8 Backtest harness

A separate test class for performance metrics:
- Replay 6 months JSONL.
- Run V2_5 with default heuristic scorer.
- Compute: signal count, fill count, realized PnL, Profit Factor, Win Rate, Sharpe.
- Compare to V2_4 baseline (PF 0.94, WR 41.7%, 84 trades).
- Expected V2_5 result: PF 1.5-2.5, WR 45-55%, 60-90 signals (per `gap_to_am.md` projection).
- Assert: PF >= 1.5 to confirm gap-fix efficacy. (Below this triggers Tripwire 4 from `improvement_roadmap.md`.)

---

## 10. Migration Path

V2_4 stays untouched in `Indicators/AMTradeCockpitV2_4.cs` as the rollback safety. V2_5 is built in `AMTradeCockpitV2_5.cs` as a new file (already class-renamed by the harness). Both can coexist on the chart for direct comparison during sim.

### 10.1 Phase 1: V2_5 detection (L1 only) parallel to V2_4

- V2_5 indicator on chart, no strategy yet. V2_5 emits candidate events to a separate JSONL file.
- V2_4 continues to drive trades.
- 30 days of parallel running. Compare candidate counts vs V2_4 signal counts.

### 10.2 Phase 2: V2_5 + AMTradeStrategyV1 in shadow mode

- Strategy attached to V2_5. Strategy is observe-only: it scores candidates and emits signals/abstains to JSONL but does not submit orders.
- V2_4 continues to drive trades.
- 30 days. Compare V2_5's intended trade list vs V2_4's actual trades.

### 10.3 Phase 3: V2_5 fully autonomous on Sim101

- V2_5 takes over from V2_4 on the demo account.
- V2_4 disabled (or moved to a separate chart for visual comparison).
- 30 days of sim with all 5 kill-switch layers tested per `nt8_safety_review.md` Phase 1.

### 10.4 Phase 4: V2_5 live promotion

- After sim metrics meet `Phase 2 / Phase 3 / Phase 4` checklist in `nt8_safety_review.md` §B5.
- V2_5 on live account at MaxSignalsPerDay=1 for first week.
- Two-person sign-off; daily review.

### 10.5 V2_4 archive

After V2_5 is validated for live, V2_4 stays in the Indicators folder as an archived reference. Do NOT delete. If a regression appears in V2_5, V2_4 is the rollback target. After 6 months of stable V2_5 live, V2_4 can be moved to `Indicators/_archive/`.

---

## 11. AM Ambiguity Handling

Three AM-clarification questions are currently pending (`am_open_questions.md`):
- AM-Q-01: Body-stack 3-node vs 4-node (P0)
- AM-Q-02: Two-sided FADE counter-slope sizing (P0)
- AM-Q-03: 200-SMA slope-magnitude threshold for runner ladder (P0)

**Architectural design benefit: V2_5 ships without these clarifications.**

### 11.1 Body-stack 3-node vs 4-node

V2_5 emits both interpretations as separate features:
- `day_type_v2_3node`: classifies based on B<C<D
- `day_type_v2_4node`: classifies based on A<B<C<D

L2's heuristic (V1) defaults to the 3-node interpretation (per AM apr-23 line 60-62 verbatim) but gives weight to the 4-node interpretation as a confidence modifier. The ML scorer (V2) learns which matters via training data.

**Architecture is shippable: the choice between 3-node and 4-node is a scorer parameter, not a detection-layer fact.**

### 11.2 FADE direction (one-sided vs two-sided)

V2_5 surfaces candidates BOTH sides of the range on Sideways days. L2's heuristic weights:
- Slope-side fade: full score (no penalty)
- Counter-slope fade: -0.10 to score (reduced confidence)

This implements AM apr-23 line 154 ("You can go in both directions") with slope as a sizing/conviction modifier rather than an exclusion gate. If AM later confirms one-sided, L2's threshold change tightens the counter-slope fade out of the take-set.

**Architecture is shippable: FADE direction is a scorer threshold, not a detection-layer fact.**

### 11.3 Slope threshold for runner ladder

V2_5 emits the raw `sma200_slope_delta_pts` as a feature. L2's heuristic for V1:
- `target_choice = "fib_200"` if `slope_delta > 5 ES points/session` (placeholder per AM apr-24)
- `target_choice = "level_to_level"` else

L2's V2 ML scorer learns the optimal threshold from training data.

**Architecture is shippable: slope threshold is a scorer hyperparameter, not a detection-layer fact.**

### 11.4 The general principle

Where AM's rules are ambiguous, V2_5's rule is: **emit the raw measurement as a feature; let the scorer learn the rule.** Do not encode the ambiguity into the detection layer. This is the architectural decision that makes V2_5 robust to AM clarifications without rebuilds.

This is institutional-grade discipline: detection is universal; interpretation is layered.

---

## 12. Implementation Sequencing for Downstream Agents

### 12.1 Wave 2 Agent: L1 Indicator Refactor

**File to edit:** `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMTradeCockpitV2_5.cs`

**Sections of this spec to read carefully:**
- Section 1 (philosophy)
- Section 2.1 (L1 contract)
- Section 3.1, 3.2, 3.3 (event schemas: bar_close, box_capture, candidate)
- Section 5 (NinjaScript-specific design)
- Section 6 (detection precise specification — all of it)
- Section 11 (AM ambiguity handling)

**Hard constraints:**
1. L1 emits `candidate` events with the exact schema in Section 3.3 — ALL fields, no NaN, with availability flags.
2. L1 emits `box_capture` events for every master-candle capture (Section 3.2).
3. L1 implements LevelWatchState per Section 6.3 — full 5-state lifecycle.
4. No retrace_side or latch filters at L1 — those are features, not gates.
5. No try/catch swallowing — error events emit in BOTH Historical and Realtime.
6. State persistence: L1's per-level LevelWatchState must round-trip through `state.json`.

**Done criteria:**
- L1 compiles without errors.
- Smoke test passes.
- Replay equivalence test (Section 9.3) shows V2_5 emits a candidate for every V2_4 signal.
- Pattern B detection test (Section 9.4) passes all 3 synthetic sequences.

### 12.2 Wave 2 Agent: L2 Strategy Decision Layer

**File to create:** `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Strategies\AMTradeStrategyV1.cs`

**Sections of this spec to read carefully:**
- Section 1 (philosophy)
- Section 2.2 (L2 contract)
- Section 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.19, 3.20 (signal, abstain, fill, exit events, decision events)
- Section 5 (NinjaScript-specific)
- Section 7 (L2 specification — all of it)
- Section 11 (AM ambiguity handling)

**Hard constraints:**
1. L2 subscribes to L1's `OnCandidate` event in `State.DataLoaded`.
2. L2 emits `signal` for taken candidates and `abstain` (layer="L2") for rejected ones. Zero candidates silently consumed.
3. The heuristic scorer is a deterministic function of feature vector (no Realtime-only state reads).
4. L2 calls `L3.IsSubmissionAllowed(signal)` before every submission. Respect L3's veto.
5. Order submission via ATM templates (V1) with limit-only entries.
6. `OnExecutionUpdate` subscription for real fill detection.
7. All exit types emit JSONL events: fill, stop_hit, target_hit, time_close, cancel.

**Done criteria:**
- L2 compiles.
- Contract compliance test passes (Section 9.1).
- L2 ranking test passes (TEST-L2-4).
- Order lifecycle test passes (TEST-L2-5) — sim trades end with paired event sequences.

### 12.3 Wave 2 Agent: L3 Safety Gates

**File to extend:** `AMTradeStrategyV1.cs` (partial class for L3, see Section 4.4).

**Sections of this spec to read carefully:**
- Section 1 (philosophy)
- Section 2.3 (L3 contract)
- Section 3.5, 3.11, 3.12, 3.16, 3.17, 3.21 (abstain, lockout, cooldown, divergence, news_wick_registered, state_persisted)
- Section 5 (NinjaScript-specific, especially state persistence)
- Section 8 (L3 specification — all of it)

**Hard constraints:**
1. All 12 gates implemented per Section 2.3.
2. Each gate independently toggleable via NinjaScriptProperty.
3. Every block emits an abstain with `layer="L3"`, gate_name, reason, recoverable_until_time.
4. State persistence to `state.json` on every state change.
5. Reconciliation runs on every 1-min bar; emits `divergence` on mismatch.
6. Manual kill-switch UI (button + hotkey).

**Done criteria:**
- All gate tests pass (Section 9.5).
- State persistence test passes (Section 9.7).
- Manual kill-switch test passes.

### 12.4 Wave 3 Agent: Strategy Integrator

**File to refine:** `AMTradeStrategyV1.cs` (full integration test).

**Sections of this spec:** entire spec; the integrator validates end-to-end.

**Hard constraints:**
1. Run all 7 tests in Section 9 against V2_5 + AMTradeStrategyV1 on the historical JSONL.
2. Confirm contract compliance (zero violations).
3. Run a 30-day sim parallel comparison vs V2_4. Document signal-count delta, fill-rate, PF.
4. Validate Phase 1 sim checklist from `nt8_safety_review.md` §B5.

**Done criteria:**
- All Section 9 tests pass.
- Sim PF >= 1.5 over a 30-day window (Tripwire 4).
- All 5 kill-switch layers tested individually.

### 12.5 Coordination points

Between L1 and L2:
- The candidate event schema in Section 3.3 is the contract. Any change requires L1 + L2 versioning.
- L1 emits all candidates regardless of L2's appetite. L2 ranks and decides.

Between L2 and L3:
- The `IsSubmissionAllowed(SignalRequest)` interface in Section 8 is the contract.
- L2 always calls L3 before submission. L3's veto is final.

Between V2_5 and external systems (Python, dashboard):
- The JSONL stream is the only interop. All events are documented in Section 3.
- Schema bumps require notice to dashboard maintainers.

---

## 13. Open Issues and Risks

Honest list of what I am not 100% sure about, where downstream agents may need to make judgment calls, and where AM/senior-quant review is desirable.

### 13.1 AM-clarification dependencies (deferred but pending)

- **Body-stack 3-node vs 4-node (AM-Q-01):** V2_5 architecture handles both via dual feature emission. But the L2 heuristic in V1 must default to one. Default 3-node (per AM apr-23 verbatim). If AM clarifies 4-node, L2's heuristic adjusts; no L1 rebuild.
- **Two-sided FADE (AM-Q-02):** V2_5 emits both directions; L2 weights counter-slope by -0.10. If AM clarifies "no counter-slope ever," tighten the heuristic; no L1 rebuild.
- **Slope-magnitude threshold (AM-Q-03):** V2_5 emits raw slope; L2 uses 5 ES points placeholder. If AM clarifies a different threshold, L2 hyperparameter update; no L1 rebuild.
- **1:30 PM candle discipline (AM-Q-04):** V2_5 captures and emits Pr130 levels every day. L2's heuristic does not gate on retracement. If AM clarifies "only on retracement events," L2 gating; no L1 rebuild.

### 13.2 Implementation-level uncertainty

- **NT8's `OnExecutionUpdate` callback ordering during DST:** I am 80% confident NT8 handles DST correctly via exchange-time bar timestamps, but I have not verified this on a March 2026 DST transition day. Implementer should test in sim before live.
- **`AtmStrategyChangeStopTarget` for runner-target updates:** I am uncertain whether NT8's ATM modification API gracefully handles concurrent stops/targets after a partial fill. Implementer should test the partial-fill + runner-update path in sim.
- **State.json atomicity on Windows:** I have specified atomic write via `tmp + rename`, but on some Windows filesystems (NTFS over network shares) this can have race conditions. Implementer should verify.
- **HTTP scorer fallback latency:** The 2000ms timeout for HTTP scorer is a placeholder. Production should measure actual round-trip and tune.

### 13.3 Where downstream agents may need to make judgment calls

- **L2's heuristic weights:** the score formula in Section 7.2 is a starting point, not a final scorer. Downstream agents should refine based on backtest results.
- **The `MaxCandidatesPerBarToTake=1` default:** AM apr-10 says "max 5 trades per day" but per-bar she's typically 1. The default is conservative; tuning may be needed.
- **News-wick proximity threshold:** what counts as "near" a news wick? Default 5 ticks; tuning needed.
- **Cluster proximity threshold:** what counts as "clustered"? Default 5 ticks; tuning needed.

### 13.4 Where senior-quant review is desirable

- **The fail-open principle in production:** institutional risk teams may want stricter controls. The contract is "safety gates have authority to block; everything else opens up." Risk team review should validate this is acceptable for the trader's risk profile.
- **State persistence atomicity guarantees:** for live trading, the state.json approach should be reviewed for transactional integrity. A more rigorous solution (SQLite with WAL) may be warranted at scale.
- **Reconciliation at 60-second cadence:** for high-frequency operations, this is too slow. For our 1-min bar interval, it's acceptable. Worth confirming with the risk team.
- **The HTTP scorer round-trip on the live path:** introduces a 2-second latency that may be unacceptable for some firms. We have a heuristic fallback but the architectural choice (HTTP at runtime vs embedded model) deserves review.

### 13.5 Sample size and statistical confidence

- 7 V2_4-instrumented sessions of historical JSONL is too thin for confident calibration of L2's heuristic thresholds.
- We need 30+ V2_5 sessions of forward-collected JSONL to tune.
- Initial heuristic thresholds are educated guesses; they will be refined by data.

### 13.6 What could surprise us

- The 0.27% conversion rate may be partially due to the level-touch detection itself being too strict (e.g., the retrace_side filter that's now a feature flag). After we surface all touches as candidates, the *candidate* count may explode by 100x. L2's heuristic then becomes the bottleneck. We will need to validate that the heuristic produces reasonable signal counts in practice (60-90 over 6 months per `gap_to_am.md` projection).
- The HTTP scorer's "live feature engine" gap (per `pattern_scorer_rt2_1/DEPLOY.txt` "KNOWN LIMITATION") means V2_5's HTTP integration tests won't have a real ML response in V1. The HTTP infrastructure ships; the ML response side is Phase 2.
- DST transitions and holiday early-closes may produce edge-cases we haven't anticipated. The `state.json` rollover on early-close days is the most fragile.

---

## End of Architecture Specification

This document is the foundation. Every subsequent implementer agent — L1 refactor, L2 scorer, L3 safety, integrator, test agent — writes against the contracts in this spec. Schema changes require versioning. Layer boundary changes require revision of this document.

The first invariant is: **never silently drop**.

The second invariant is: **detect everything; decide separately; block independently**.

Build accordingly.
