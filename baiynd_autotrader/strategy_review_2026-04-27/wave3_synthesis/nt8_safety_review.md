# NT8 Automation Safety Review
## AMTradeCockpitV2_4 — Order Routing Audit and Safety Architecture

**Author:** NT8 Automation Safety Reviewer (Wave 3 — absorbing Wave 2 NT8 Execution audit)
**Date:** 2026-04-27
**Source files read:** AMTradeCockpitV2_4.cs (4627 lines), AMShadowObserverV1.cs, wave2_audit/v24_code_audit.md, wave2_audit/jsonl_data_analysis.md, wave2_audit/python_pipeline_audit.md, wave2_audit/backtest_infra_audit.md
**Target:** Sim phase now; institutional-grade autonomous futures trading path to live

---

## PART A — ORDER ROUTING AUDIT

---

### A1. Today's Actual Order Path — Step by Step

#### Step 1: Signal detection in CheckEntry

`Process1MinBar` calls `CheckEntry` when `canTrade` is true. `canTrade` requires: `v2TrendDir != null`, `tradeMode != null`, `inRthWindow`, `currentSignalState` is `None` or `Pending`, `signalsToday < effSignalCap`, `!lockoutActive`, and `!IsInCooldown()`. `CheckEntry` scores all level candidates against the current 1-min bar's high/low range, applies a retrace-side filter, picks the closest-to-bar-open level that passes all filters, and computes a stop distance via `V2ComputeStopDistance()`. If a valid level is found, it calls `SetSignal`.

Important: `CheckEntry` runs in BOTH `State.Historical` and `State.Realtime`. The pre-gate `OnTouch` event and the JSONL "touch" log also fire in both states. However, the audible alert, the JSONL "signal" event, and the Staging Card are gated to `State.Realtime` only.

#### Step 2: SetSignal arms PENDING and displays the Staging Card

`SetSignal` (line 2391) does the following in order:

1. If a prior `Pending` exists, clears its drawings and logs a replacement message.
2. Sets `signalDirection`, `signalEntry`, `signalStop`, `signalTarget`, `signalTime`, `signalTradeMode`.
3. Fires the `OnSignal` shadow-observer event immediately (pre-staging).
4. Logs a JSONL "signal" event (Realtime only).
5. Sets `currentSignalState = SignalState.Pending`.
6. Increments `signalsToday`. **This increment happens here, not on fill.** A cancelled pending still consumes budget.
7. Sets `signalSizeNote` based on the opening range vs `MaxOpeningRange`.
8. Draws `Sig_Entry`, `Sig_Stop`, `Sig_Target` (FADE only), and an arrow on the chart.
9. Fires an audible alert (Realtime only).
10. Calls `ShowStagingCard()` (Realtime only).

`ShowStagingCard` computes the sizing traffic-light bucket: if `cardDollarsRisk > $100` → Gray (no trade); if `signalSizeNote == "1 MES ONLY"` → Orange; otherwise → Green. It assigns `cardAtmTemplate` to either `AtmTemplateNormal` or `AtmTemplateWide` (or null for Gray). The card is rendered as a 280×180 DirectX overlay at top-center of the chart.

#### Step 3: The STAGE button click — what OnStageClicked actually does

This is the most consequential finding in the order routing audit. `OnStageClicked` (line 3947) does the following:

1. If `cardSizeBucket == "Gray"`, returns immediately with a log message. No further action.
2. Determines `qty`: 1 for Orange, 2 for Green.
3. Selects `template = cardAtmTemplate ?? AtmTemplateNormal`.
4. Constructs a log string: `"TICKET: {direction} {qty}x via ATM '{template}' | Entry {cardEntry} | Stop {cardStop} | Tgt {cardTarget} | Acct {AccountName}"`.
5. Calls `Log(ticket)` and `FireAlert(...)`.
6. Checks `AllowLiveOrderSubmit`. If `true`, it logs: `"AllowLiveOrderSubmit=true but live submission from an indicator requires Account.CreateOrder + Submit wiring (deferred). Ticket logged only for now."` If `false`, it logs: `"AllowLiveOrderSubmit=false -> ticket logged only. Submit manually in ChartTrader."`.
7. Sets `cardStaged = true`, which changes the card title to `"STAGED - {direction} on retracement"` and the border to dim gold.

**STAGE does not submit an order under any circumstances. It logs a ticket to the NT Output window, fires an audio alert, and updates the card appearance. That is the entirety of OnStageClicked. The ATM template name is displayed but never called. No `AtmStrategyCreate`, no `Account.CreateOrder`, no `SubmitOrderUnmanaged` — none of these NT8 order APIs are invoked.**

The `AllowLiveOrderSubmit=true` branch acknowledges that the wiring is deferred ("requires Account.CreateOrder + Submit wiring (deferred)"), meaning the developer intentionally left it unimplemented and flagged it as future work.

#### Step 4: ATM template — does V2_4 call AtmStrategyCreate?

No. The ATM template names (`AM_Normal_2MES`, `AM_Wide_1MES`) are stored as string parameters, displayed in the Staging Card UI, and echoed in the logged ticket. V2_4 never calls `AtmStrategyCreate` or any equivalent NT8 API. The templates are assumed to be pre-configured in NT's ATM strategy manager. After clicking STAGE, the operator must manually open NT's ChartTrader, select the correct ATM template, and submit the order at the displayed price.

#### Step 5: Order submission to broker

Order submission happens entirely at the NT application level, not in V2_4. The Staging Card communicates the intent (direction, size, entry, stop, target, ATM template name) via the card display and the logged ticket. The operator submits manually. There is no automation here today.

#### Step 6: Fill detection — V2_4 assumes fill from price action, NOT from the broker

`MonitorSignal` (line 2513) checks for a fill in the `Pending` phase with this logic at line 2560: for a LONG, `filled = low <= signalEntry`; for a SHORT, `filled = high >= signalEntry`. This is a price-action inference: "if the bar traded to or through the entry price, assume the limit was filled."

This is NOT broker fill detection. V2_4 has no connection to NT's account position feed, no `OnPositionUpdate` callback, no `OnExecutionUpdate` callback. If the actual broker limit was rejected (margin failure, connection drop, bad price), or if the limit was placed at a different price than `signalEntry`, V2_4 will still transition to `SignalState.Active` when price touches the level. Conversely, if the limit was cancelled manually in ChartTrader but price later revisits the level, V2_4 will falsely claim a fill.

This is the most fundamental gap between V2_4's internal model and broker reality.

#### Step 7: Broker stop and target placement

V2_4 draws `Sig_Stop` and `Sig_Target` lines on the chart as visual references for the operator. These are drawn at `signalStop` and `signalTarget` (FADE mode only). The ATM template is assumed to handle stop and target placement at the broker level when the operator submits through ChartTrader. V2_4 does not send stop or target orders. Whether the broker places stops at exactly `signalStop` depends entirely on the ATM template configuration, which is external to V2_4. If the ATM template places stops at a different price than `signalStop`, V2_4 will not know, and its internal trail and stop-hit detection will be based on wrong prices.

For TREND-mode signals, the SMA20 trail ratchets in `MonitorSignal` and fires an alert to "move broker stop manually" (via `A8_StopUpdate_*`). The broker stop must be moved by the operator based on the alert. This is a manual-update loop, not automated trailing.

#### Step 8: Cancel-others on fill

On the fill transition (line 2594), `MonitorSignal` fires alert `A9_CancelOthers_{sigId}`: "CANCEL all OTHER pre-placed limits in broker NOW — one fill invalidates the rest." This is an advisory alert only. V2_4 does not cancel other NT orders. Any other resting limit orders in the broker account must be cancelled manually by the operator.

V2_4 clears its own signal drawings (`ClearSignalDrawings`, line 4578 region) and hides the Staging Card. This is internal UI cleanup only — it does not touch any live broker orders.

---

### A2. The Shadow-Observer Pattern

#### OnTouch and OnSignal events

`OnTouch` and `OnSignal` are declared at lines 295-296 as `event Action<TouchEventArgs>` and `event Action<SignalEventArgs>`. `OnTouch` fires in `CheckEntry` at line 1926 for every level that passes the range filter (before the latch filter). `OnSignal` fires in `SetSignal` at line 2412 immediately after the signal parameters are set, before the card is shown.

Both events fire in both `State.Historical` and `State.Realtime` (no state gate on the event emission itself, unlike the audible alert and staging card).

#### The hosting Strategy file — it exists

A glob of `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Strategies\` reveals: `AMShadowObserverV1.cs` exists. This file hosts `AMTradeCockpitV2_3` (note: V2_3, not V2_4) and subscribes to `OnTouch` and `OnSignal`. Its purpose is Stage 1 shadow observation: it posts each touch to the `pattern_scorer_rt2_1` `/score_lookup` endpoint and writes a `shadow_touches.jsonl` per instrument per day. **No orders are submitted by this strategy.** `AllowLiveOrderSubmit` is forced to `false` in the hosted indicator's constructor call (line 153).

The shadow observer is wired to V2_3. If the current V2_4 indicator is used instead of V2_3, the observer would need to be updated to host `AMTradeCockpitV2_4`. At present, any chart running V2_4 directly has no strategy subscriber on its `OnTouch`/`OnSignal` events — those events fire to nobody from V2_4 in standalone use.

#### Plans for a hosting Strategy

The Stage 1 shadow observer is the first step. A Stage 2 or autonomous strategy would need to:
- Subscribe to `OnSignal` from a hosted V2_4 (or V2_5 equivalent).
- Query the Python scoring service for a tier classification before committing.
- If tier-A (or whatever the promotion threshold is), submit the actual NT8 order via `Account.CreateOrder` + `Submit` or via `AtmStrategyCreate`.
- Subscribe to NT8 `OnPositionUpdate` and `OnExecutionUpdate` callbacks to detect real fills.
- Monitor position state against V2_4's internal state and reconcile divergences.

No such Strategy file currently exists. AMShadowObserverV1 is observe-only.

---

### A3. The Python-to-NT8 Gap and Architectural Options

The Python pipeline audit confirms: no Python component currently submits orders to NT8 for futures. `TradeWave_auto_trading` is options-on-equities via Tradier and does not touch NT8. The Python scoring services (`ml_scorer_rt` port 7676, `pattern_scorer_rt2_1` port 7677, `decision_engine` `/decide`) are online inference endpoints with no NT8 write path.

Four architectural options for closing this gap:

**Option A — NT8 Strategy hosts V2_4, queries Python score before firing.**
The Strategy subscribes to `OnSignal`, makes a synchronous or async HTTP POST to `/decide` (or `/score_lookup`), receives a tier, and submits the order only if tier meets the threshold. All order management (fill detection, stop updates, reconciliation) lives in the Strategy. Python is read-only from NT8's perspective. No Python-side order submission.

*Pros:* Cleanest separation of concerns. NT8 handles all order state natively. Python scoring is an optional gate, not a required component for order safety. If Python is down, the Strategy can optionally fire without ML gating (fallback mode) or block all trades (safe mode). *Cons:* HTTP round-trip from NT8 to Python on a Windows machine during RTH must complete within the 1-min bar window. The existing `AMShadowObserverV1` already proves this is viable at ~2s timeout. *This is the recommended option.*

**Option B — Python publishes signals to a queue, NT8 Strategy consumes and submits.**
Python becomes the signal generator. An NT8 Strategy polls a queue (flat file, Redis, named pipe) and submits when a signal appears. Python must replicate all of V2_4's entry conditions.

*Pros:* Python has full control of signal timing and can integrate scoring seamlessly. *Cons:* Python must re-implement V2_4's full state machine (sessions, box captures, phase tracking, latch logic, canTrade gates) in Python — duplicating a 4600-line NinjaScript codebase in a different language with different bar-time semantics. The risk of divergence between Python's model and NT8's reality is high. Requires a robust IPC mechanism between processes on the same machine or across machines. Not recommended given the complexity and duplication risk.

**Option C — NT-internal-only (Python features embedded in NinjaScript).**
Port the feature engineering and model inference to NinjaScript within V2_4 (or a V3 successor). No Python call at trade time; the model is serialized to a format NinjaScript can run (e.g., LightGBM PMML or a hardcoded decision tree).

*Pros:* No inter-process dependency at runtime; zero latency. *Cons:* Porting a 71-feature LightGBM model to NinjaScript is a substantial engineering effort. Model updates require recompilation and NT reload. Python's training infrastructure cannot be easily replicated in C#. Not recommended.

**Option D — External broker bridge (Rithmic API direct).**
Python calls Rithmic (or CQG/IB) APIs directly, bypassing NT8 entirely. NT8 is chart-only.

*Pros:* Decouples from NT8 reliability; full programmatic control. *Cons:* Requires a separate Rithmic/FCM API agreement, a Python-side order management system, and a separate risk layer. V2_4's visual pipeline (boxes, staging card, alerts) is useful for monitoring. Abandoning NT8 means building an entirely new execution layer. Not recommended at Afshin's current stage.

**Recommendation: Option A.**
Build a NinjaScript Strategy that hosts V2_4, subscribes to `OnSignal`, makes a synchronous 2-second HTTP call to `/decide` (matching the pattern already proven in `AMShadowObserverV1`), and submits via `AtmStrategyCreate` if the decision passes. This builds directly on the existing architecture, keeps Python's role as a read-only scorer, and keeps NT8 as the authoritative order-management system. Stage progression is: Stage 1 (existing shadow observer, observe-only) → Stage 2 (auto-submit to Sim101, AllowLiveOrderSubmit=true in Strategy only) → Stage 3 (live account with all safety checks passing).

---

## PART B — SAFETY ARCHITECTURE FOR AUTONOMOUS RUNNING

---

### B1. Failure Modes — Enumerated and Addressed

**NT8 application crash mid-session.**
If NT8 crashes while a Pending signal exists: the limit order was not yet submitted (because STAGE is manual today, or a future Strategy would have submitted it). No open position at broker unless the operator had manually placed an order before the crash. On restart, V2_4 loads in `State.DataLoaded` and re-initializes all state to zero. `signalsToday`, `lockoutActive`, `realizedPnlDollarsToday` all reset to zero (see `State.DataLoaded` block at line 795 and `ResetForNewDay` at line 4499). The indicator treats the session as a fresh start. **If the operator had manually placed a limit that was not filled, that resting limit remains in the broker with no V2_4 awareness.** Risk: the broker limit fills after restart, V2_4 has no record of it and no stop/target in its state.

If NT8 crashes while an Active signal exists (a fill has occurred): the broker has an open position with stop and target orders (ATM template). NT8 restarting and V2_4 reloading will not detect the open position. V2_4 will treat the session as fresh, will not monitor the existing trade, and will potentially fire new signals. The broker-side ATM will manage the existing trade independently, but V2_4's PnL tracking and lockout logic will not see the exit. **This is the highest-severity scenario.**

Mitigation required: the hosting Strategy (Option A architecture) must read `Account.Positions` at `State.DataLoaded` / `State.Realtime` transition and determine if an open position already exists before arming V2_4 for new signals.

**NT8 data feed drops mid-bar.**
If the primary data feed drops, `OnBarUpdate` stops firing. V2_4 is frozen. An Active signal is not monitored — no trail updates, no stop-hit detection. The broker ATM continues to manage the trade independently. When the feed reconnects, NT may deliver a gap bar or replay missed bars. V2_4's `MonitorSignal` will process those bars in sequence on reconnect, potentially detecting a stop-hit or trail exit on a stale bar. The exit detection will use the reconnected bar data, which may not accurately reflect the actual fill price.

There is no feed-drop detection in V2_4. The heartbeat JSONL (every 30s) will gap, providing an external indicator that something stopped.

Mitigation: heartbeat gap detection (see B3). The hosting Strategy should subscribe to `ConnectionStatusUpdate` events and halt auto-submission if the data feed is in an error state.

**NT8 reconnects after gap — V2_4 state coherence.**
At reconnect, NT replays missed bars in `State.Historical` (for historical bars) then switches back to `State.Realtime`. V2_4's critical state variables are all in-memory: `signalsToday`, `realizedPnlDollarsToday`, `lockoutActive`, `lastStopTime`, `v2TouchedThisSession`, `currentDay` boxes, `currentSignalState`. These survive within the same process session. They do NOT survive if NT was restarted. If NT was only disconnected and reconnected without a process restart, state is intact.

The concern is a signal that was Pending when the feed dropped: V2_4 may detect a fill or a cancellation on the replayed bars, potentially in the wrong direction. If price on the replayed bars crossed both entry and stop, V2_4 will call both the fill transition and then immediately the stop-out. The `PnL` accounting for this phantom sequence will contaminate `realizedPnlDollarsToday` and potentially trigger lockout even though no real trade occurred.

**Power outage or OS crash.**
Equivalent to NT8 crash from V2_4's perspective — complete state loss. Any resting or active broker orders remain in the broker until they are executed or expire. On restart, V2_4 starts fresh and is not aware of any broker-side activity. If a position is open at the broker, it is unmonitored by V2_4 until the hosting Strategy reads account positions.

Mitigation: state persistence to a session JSON file (see B2). The hosting Strategy reads it at startup to determine prior session state.

**Broker connection drops with working orders.**
The broker may retain working stop and target orders even if NT8 loses its connection. The ATM template handles these at the broker level. On reconnect, NT8 should receive fill notifications for any orders that executed during the disconnection. V2_4 does not subscribe to `OnExecutionUpdate`, so even with reconnection, V2_4 will not detect fills from the notification stream. Its only detection mechanism is bar-price-action inference, which will work correctly on the replayed bars.

**Fill rejected by broker (margin, account issues).**
V2_4 has no awareness of rejection. If the operator clicks STAGE, manually submits an ATM order, and the broker rejects it, V2_4 still has `currentSignalState = Pending` and will detect a "fill" when price revisits the entry level on a subsequent bar. This creates a phantom Active state — V2_4 thinks it is in a trade when the broker is flat. All subsequent monitoring (stop alerts, trail updates, time-close alerts) will be for a non-existent position.

In the future automated path (Option A Strategy), the Strategy would receive an `OnOrderUpdate` with a rejected status and would need to cancel the pending signal in V2_4 (via a method call or by setting a flag).

**Partial fill (1 of 2 contracts).**
V2_4 has no concept of partial fills. It models a binary filled/not-filled state. The ATM template may handle partial fills at the broker level (filling some contracts while leaving others on the limit). V2_4's `RecordAndDrawTrade` will record the full intended qty (1 or 2 contracts) when it detects the price-action fill. PnL tracking will use the full qty. If only 1 of 2 contracts filled, V2_4 overstates risk, overstates exit PnL, and the lockout threshold may be hit or missed at the wrong level.

**Stop and target both fill within the same tick.**
V2_4's `MonitorSignal` checks hard stop first (line 2601), then FADE target (line 2623), then trail (line 2643), then time-close (line 2705). If both stop and target levels are within the same bar's range, V2_4 will always record a stop-out (loser) because the stop check precedes the target check. Whether the broker's ATM template handles this correctly depends on ATM order routing (buy-stop vs buy-limit ordering at the broker). V2_4 will never record a win from this scenario.

**DST transition mid-session.**
V2_4 uses hardcoded hour/minute integers for all time gates: `closeHour=15`, `closeMinute=0` for ES/NQ/GC; `rthOpenHour=9`, `rthOpenMinute=30`. NT8 uses Exchange Time Zone for bar timestamps on futures contracts, which handles DST automatically. If NT8's bar timestamps are in ET and the exchange correctly adjusts for DST, V2_4's hardcoded gates work correctly year-round. If NT8's bar timestamps are in UTC or local time, the gates are wrong on DST transition days.

The specific risk is the Sunday overnight transition: on the night the clocks change, the first Monday session open may be mis-classified by `inRthWindow` for the first 60 minutes if NT8's timestamp reflects the old offset. There is no DST-aware logic in V2_4. This requires verification on the first DST transition day with the actual NT8 configuration.

**Holiday — exchange early close.**
V2_4 hardcodes `closeHour:closeMinute`. On early-close days (e.g., Christmas Eve, day after Thanksgiving), the exchange may close at 13:00 ET. V2_4 will not know this. An Active signal will be monitored until 15:00 ET even though the market closed and the position was likely force-flat by the broker at 13:00. The time-close alert will fire at the wrong time. If the broker force-flattened the position at 13:00, V2_4 will continue to show Active state and issue stop/trail alerts for a position that no longer exists.

Mitigation: the hosting Strategy should include a holiday calendar check and override the session-close time accordingly. NT8 itself has session template support that can handle early-close days, but V2_4 does not read NT8's session template — it uses hardcoded times.

---

### B2. State Persistence

**What state is in-memory and reset on reload.**

The following state is entirely in-memory and resets to zero/null/default at `State.DataLoaded`:
- `signalsToday` (→ 0)
- `realizedPnlDollarsToday` (→ 0)
- `lockoutActive` (→ false)
- `lockoutReason` (→ "")
- `losingTradesToday` (→ 0)
- `lastStopTime` (→ `DateTime.MinValue`)
- `v2TouchedThisSession` (→ cleared)
- `currentSignalState` (→ `None`)
- `currentDay` (→ null until first bar fires)
- `dayHistory` (→ new empty list)
- `institutionalBox` (→ null)
- `firewallActive` (→ false)
- `signalEntry`, `signalStop`, `signalTarget` (→ 0)

`ResetForNewDay` also resets all of these at the session boundary, so an intraday restart AFTER the session boundary behaves identically to a fresh-day start. An intraday restart BEFORE the session boundary will reset all state including `realizedPnlDollarsToday` and `lockoutActive` — the session's prior loss is forgotten.

**What state survives a restart.**

Nothing survives a restart in the current implementation. All state is transient.

**Recommendation: session state JSON.**

At each significant event (fill, stop-out, trail-exit, target-hit, time-close, lockout fire, signal pending, signal cancel), V2_4 (or the hosting Strategy) should write a session state JSON to a fixed path such as `C:\seasonals\cockpit\sessions\{YYYY-MM-DD}\state.json`. The fields should include: `signalsToday`, `realizedPnlDollarsToday`, `losingTradesToday`, `lockoutActive`, `lockoutReason`, `lastStopTime`, `currentSignalState`, `signalDirection`, `signalEntry`, `signalStop`, `signalTarget`, `positionConfirmedAtBroker`, `positionQty`. At `State.DataLoaded`, read this file if it exists for today's date and restore the values before the first bar fires. This gives an intraday restart the ability to resume from a known state rather than starting cold. The file should be written atomically (write to a `.tmp` then rename) to avoid partial writes.

---

### B3. Watchdog and Monitoring

**Heartbeat gap detection.**

V2_4 emits a JSONL "heartbeat" event every 30 seconds during Realtime operation (gated by `MaybeHeartbeat`). An external Python process should monitor the current session's `events.jsonl` file and alert if no heartbeat event has appeared for more than 2 minutes during RTH (9:30–15:00 ET). A gap of 2 minutes means at least 4 missed heartbeat cycles, which is unambiguous system failure. This watchdog does not exist today.

The watchdog should:
- Read the current session's `events.jsonl` (or the last heartbeat from a shared state file).
- During RTH window, check heartbeat age.
- If age > 120 seconds, emit an alert (see B7 alert routing).
- Log the gap event itself to a separate watchdog log.

Note: the watchdog must be on the same machine as NT8 (to read the JSONL in real time) or use a network-accessible path. The Python services are on a VPS at port 7677, which is a different machine. The watchdog should be a lightweight local Python script running as a Windows scheduled task or service.

**Order-state reconciliation.**

The hosting Strategy (Option A) should, at each 1-minute bar, compare V2_4's `currentSignalState` and `signalDirection` against the NT8 account's actual position. Specifically:
- If `currentSignalState == SignalState.Active` and the account shows a flat position in the traded instrument, this is a divergence: V2_4 thinks a trade is running but the broker is flat (fill rejected, or position closed at broker without V2_4 detection).
- If `currentSignalState == SignalState.None` and the account shows an open position, this is the complementary divergence: V2_4 is flat but the broker has an open trade.

On any divergence, the hosting Strategy should: halt further auto-submission for the session, log the divergence event to JSONL (a new `"divergence"` event type), and fire an alert (see B7).

---

### B4. Kill-Switch Stack — Multiple Redundancy

The design calls for five layers of kill-switch, operating from innermost (fastest) to outermost (slowest but most reliable).

**L1 — V2_4 in-code gates (exists).**
`lockoutActive` (daily-loss and consecutive-loser lockout), `signalsToday >= effSignalCap`, `IsInCooldown()`, and the RTH window gate all prevent new signals from firing. These are the primary protection during normal operation. Limitation: they are intraday only, reset on reload, and only gate signal emission — they do not touch broker orders.

**L2 — NT8 Strategy supervisory layer (does not exist yet).**
The hosting Strategy (Option A) should have an independent kill-switch that can be triggered by: (a) position-vs-state divergence, (b) heartbeat gap from within the strategy itself (a wall-clock check in `OnBarUpdate`), (c) a daily P&L threshold measured against real account positions rather than V2_4's in-memory tracking. When L2 fires, the Strategy cancels all pending orders for the instrument, does not submit new orders for the remainder of the session, and logs a `"strategy_halt"` JSONL event.

**L3 — NT8 account-level loss limit (partially exists).**
NT8's account settings allow a "Max daily loss" and "Max day trade drawdown" at the account level. These are enforced by NT8 independently of V2_4 or the hosting Strategy. When tripped, NT8 will reject new order submissions for the account. This is the correct backstop for any logic failure above. Afshin should confirm these are configured for Sim101 before live running. For live, they should be set conservatively (e.g., at 1.5× the V2_4 `MaxDailyLossDollars` threshold so L1 fires first).

**L4 — External Python watchdog (does not exist yet).**
The Python watchdog (described in B3) can also serve as L4. On detecting a heartbeat gap or receiving a divergence event, it can: send alerts, and in a future iteration, call a REST endpoint on the hosting Strategy to force a halt. The REST endpoint within NinjaScript is non-trivial but achievable via a local TCP listener in the Strategy. Alternatively, the watchdog can write a flag file that the Strategy polls each bar (simple, platform-agnostic).

**L5 — Manual abort (partial).**
NT8 has a built-in "Close All Positions" button in the account monitor. This is a manual kill for broker positions. For the Strategy kill-switch, NT8 allows removing a strategy from a chart, which triggers `State.Terminated` and stops further submissions. A dedicated hotkey shortcut in NT8's keyboard configuration can be bound to "Flatten and Cancel All" — this should be configured and tested before live trading. A physical external kill-switch (a hardware button that triggers a key combination) is best practice for live autonomous trading but is not a blocker for sim.

---

### B5. Sim-to-Live Promotion Checklist

This checklist is ordered by phase. Nothing in a later phase should begin until all items in the prior phase are checked off.

**Phase 0 — Infrastructure prerequisites (before sim begins)**
- [ ] Hosting Strategy (Option A) is built, code-reviewed, and compiles cleanly in NT8.
- [ ] `AllowLiveOrderSubmit` in the Strategy is set to `true` for Sim101 only; live account name is not configured anywhere in code.
- [ ] NT8 account-level loss limits are configured on Sim101 (max daily loss at 2× `MaxDailyLossDollars`, max drawdown at 3×).
- [ ] Session state JSON persistence is implemented and tested: crash the indicator mid-session, restart, verify state is correctly restored.
- [ ] Order-state reconciliation check is implemented in the hosting Strategy and tested: manually cancel a working order in ChartTrader, verify the Strategy detects the divergence within 1 bar.
- [ ] Python watchdog script is running as a Windows scheduled task and is confirmed to send a test alert.
- [ ] Manual kill-switch hotkey ("Flatten and Cancel All") is configured in NT8 and tested.

**Phase 1 — Minimum sim run (30 trading days)**
- [ ] V2_4 + hosting Strategy running on Sim101 continuously during RTH for 30 trading days.
- [ ] Zero logging anomalies: no heartbeat gaps > 60s during RTH, no divergence events in JSONL, no unexplained lockout events (i.e., all lockouts correspond to actual logged signals and exits).
- [ ] At least 20 auto-submitted signals (not manually overridden) with corresponding broker-side fills on Sim101 confirmed via account monitor.
- [ ] All 5 kill-switch layers tested at least once: L1 by running to lockout naturally, L2 by simulating a position divergence, L3 by hitting the NT8 account limit (test sim), L4 by stopping the heartbeat and confirming the watchdog fires, L5 by pressing the manual kill hotkey.
- [ ] DST transition day (next occurrence) navigated without time-gate errors.
- [ ] At least one simulated outage test: kill NT8 mid-session with an Active signal, restart, confirm State file is read, confirm no duplicate orders are submitted.

**Phase 2 — Performance prerequisites (pass after 30+ days sim)**
- [ ] Sim-period Sharpe (realized, measured on actual Sim101 fills at MES sizing) >= 1.5.
- [ ] Sim-period profit factor >= 1.10.
- [ ] Maximum intraday drawdown in the sim period stays within the V2_4 `MaxDailyLossDollars` limit on all but zero exceptions.
- [ ] Win rate >= 40%.
- [ ] Positive expectancy per signal.
- [ ] No more than 3 missed-signal events per week where the JSONL shows a qualifying touch but no signal fires without a documented reason (i.e., the `canTrade=false` denial logging is working).
- [ ] Python `/decide` endpoint's tier-A calls are verified to outperform unfiltered calls on the sim sample (minimum comparison: filtered signals vs all signals by expectancy).

**Phase 3 — Manual playbook verification**
- [ ] Afshin runs through the complete manual playbook (as documented in `manual_playbook.md`) 5 times without error: pre-session checklist, staging card interaction, broker verification steps, post-session reconciliation.
- [ ] Manual override procedure (operator disagrees with auto signal, overrides by cancelling in ChartTrader) is tested and does not cause state corruption.
- [ ] Afshin can describe, from memory, what happens at each failure mode in B1 and the correct manual response.

**Phase 4 — Live promotion**
- [ ] CL-specific bugs (rthOpenHour hardcoded to 9:30) are either fixed or CL is explicitly excluded from live trading.
- [ ] Holiday calendar is integrated into the hosting Strategy or confirmed to be handled by NT8 session templates.
- [ ] Live account NT8 account-level risk limits are set conservatively (max daily loss <= 1× `MaxDailyLossDollars`).
- [ ] Live first-day risk cap: `MaxSignalsPerDay=1` for the first week of live trading.
- [ ] Two-person sign-off: Afshin reviews the system live for 1 full session before enabling auto-submission on the live account.
- [ ] Emergency contacts and alert routing are verified for all critical events (see B7).

---

### B6. Restart-Recovery Procedure

**Scenario A: NT8 crashes during the session with no pending or active signal.**

NT restarts → V2_4 loads → `State.DataLoaded` fires → all state resets to zero → historical bars replay and rebuild box state and VWAP → `State.Realtime` → normal operation resumes.

Without state JSON persistence: if any trades had occurred earlier in the session, `realizedPnlDollarsToday` is zero after restart. If the session had already hit the daily loss limit and locked out, the lockout is gone after restart. The system will accept new signals that should be blocked.

With state JSON persistence: at `State.DataLoaded`, read `state.json` for today's date, restore `signalsToday`, `realizedPnlDollarsToday`, `losingTradesToday`, `lockoutActive`. The lockout and signal budget are correctly restored. The hosting Strategy also reads the state and confirms the broker position is flat (expected for this scenario).

**Scenario B: NT8 crashes during a Pending signal (STAGE was clicked, limit order submitted to broker but not yet filled).**

The limit order is resting at the broker. The broker does not know NT8 crashed.

NT restarts → V2_4 loads → `State.DataLoaded` → all state including `currentSignalState` resets to `None`. The operator must:
1. Immediately check the broker account for any resting limit orders.
2. Decide whether to cancel the limit order manually (conservative) or leave it (risky — if it fills, no monitoring).
3. If cancelled, the session can resume normally.
4. If left and it fills, V2_4 has no awareness of the fill. The ATM template will manage stop/target, but V2_4 will be in a state-divergence condition.

The hosting Strategy with position-state reconciliation would detect the open position (or the filled limit) at the next bar and fire a divergence alert, preventing new signals from being submitted.

**Scenario C: NT8 crashes during an Active signal (broker has open position with stop and target).**

The broker has an open position. NT8 and V2_4 are restarting.

NT restarts → V2_4 loads fresh → hosting Strategy reads `Account.Positions` → finds an open position in the instrument → sets an internal flag: "pre-existing position detected at restart." The Strategy should NOT arm V2_4 for new signals until the pre-existing position closes. It should monitor the position via `OnPositionUpdate`/`OnExecutionUpdate` to detect the exit. On exit, it logs the result, updates PnL, and re-enables signal processing.

V2_4's internal `currentSignalState` will be `None` on restart. It will not monitor the broker position. The ATM template at the broker will manage the trade. The risk is that V2_4 fires a new signal while the broker has an open position in the same instrument — resulting in a doubled position. The hosting Strategy's pre-existing-position guard prevents this.

**What happens to the resting limit if NT was stopped during Pending state.**

If the operator (or future Strategy) had submitted the limit to the broker, that limit stays at the broker indefinitely until it fills, is cancelled, or expires. NT8 crashing does not cancel working orders on the broker. This is the correct default behavior for an attached order submitted via ATM. The risk is as described above — the limit may fill post-restart with no monitoring. The correct procedure is to cancel all resting limits as the first step before restarting NT8, unless the operator intends to let the trade run under ATM-only management.

---

### B7. Logging and Observability

**Current JSONL gaps identified.**

The v24_code_audit.md documents these missing events in full. For safety review purposes, the highest-priority gaps are:

1. `box_capture` — when GlobEx, Midnight, Europe, RTH, and Close330 boxes are captured. Without this, the Python pipeline cannot reconstruct which structural levels were available on a given session without replaying NT8 history. Required for offline fill-simulation accuracy.

2. `fill` — when `currentSignalState` transitions from `Pending` to `Active`. The current JSONL has no record of this transition. Any downstream analysis that wants to measure signal-to-fill latency, or confirm that fills occurred on expected sessions, cannot do so from the JSONL. The `signal` event is the entry intent; a `fill` event would be the entry confirmation.

3. `stop`, `target`, `trail_exit`, `timeclose` — the four exit types have no JSONL events. V2_4 records these in its `tradeHistory` list (in-memory only) and draws them on the chart, but they do not persist to any file. A session where V2_4 fired two signals, one was stopped and one hit a trail exit, is indistinguishable from a session with no signals in the JSONL — only the `lockout` event (if it fires) and the NT8 Output window captures contain outcome information.

4. `cancel` — when a Pending signal is cancelled at the 14:30 cutoff. The `A8_PendExpire` alert fires and is logged to the NT Output window, but no JSONL event is emitted. A cancelled pending should be distinguishable from an expired pending in the log.

5. `canTrade_denied` — when `canTrade` is false and a qualifying touch exists. This is the "missing setup" event. Without it, the JSONL audit cannot determine why setups were not taken. The JSONL data analysis found a 0.27% conversion rate from qualifying touches to signals, and no mechanism to explain the other 99.73%.

6. `lockout_reset` — when `ResetForNewDay` clears `lockoutActive` at session rollover. Without this, the lockout activation event and the next session's clean state are disconnected.

7. `divergence` — to be added by the hosting Strategy when a position/state mismatch is detected.

8. `heartbeat_gap` — to be added by the external watchdog when a heartbeat is missed.

**Alert routing.**

The current alert system is NT8 sound alerts (`FireAlert`) and NT8 Output window `Print` calls. For autonomous operation, this is insufficient. The following alert routing additions are required before live operation:

- SMS / push notification for critical events: lockout fired, hosting Strategy halt, divergence detected, heartbeat gap > 2 minutes, fill detected (confirmation), broker connection lost.
- Email for end-of-session summary: signals fired, fills, PnL, win/loss, lockout state, any anomalies from watchdog.
- A lightweight web dashboard (the Python cockpit already provides `cockpit.py`) that displays live session state from the JSONL heartbeat stream. This exists for offline analysis; a live refresh mode (polling `events.jsonl` every 5 seconds) would give Afshin a browser-based monitor.

Alert routing tools: the Python watchdog script can send SMS via Twilio, push notifications via ntfy.sh or Pushover, and email via SMTP. The NT8 Strategy can call the watchdog's endpoint to trigger alerts without managing delivery itself. This keeps alert routing logic in Python (maintainable) and out of NinjaScript.

---

## Sim-to-Live Promotion Checklist — Ranked by Risk Criticality

The following is the complete list ranked from highest-blocking risk to lower-blocking risk. Items marked HARD BLOCK must be resolved before live; items marked PREREQUISITE must be completed before the relevant phase begins.

| Priority | Item | Category | Block Level |
|---|---|---|---|
| 1 | Hosting Strategy (Option A) built, tested, submits to Sim101 | Architecture | HARD BLOCK (live) |
| 2 | Position-vs-state reconciliation implemented in hosting Strategy | Safety | HARD BLOCK (live) |
| 3 | State JSON persistence implemented; restart-with-prior-state tested | Safety | HARD BLOCK (live) |
| 4 | NT8 account-level loss limits configured (Sim101 and live) | Safety | HARD BLOCK (live) |
| 5 | Python watchdog monitoring heartbeat gaps, sending SMS/push | Monitoring | HARD BLOCK (live) |
| 6 | Fill / stop / target / cancel / canTrade_denied JSONL events added | Observability | PREREQUISITE (Phase 1 sim) |
| 7 | Manual kill-switch hotkey configured and tested | Safety | PREREQUISITE (Phase 1 sim) |
| 8 | 30+ trading days of sim with no logging anomalies | Performance | PREREQUISITE (live) |
| 9 | Risk-architecture performance targets met (Sharpe >= 1.5, PF >= 1.10) | Performance | PREREQUISITE (live) |
| 10 | All 5 kill-switch layers individually tested | Safety | PREREQUISITE (live) |
| 11 | Simulated outage test (kill mid-Active, restart, no duplicate orders) | Safety | PREREQUISITE (live) |
| 12 | DST transition day navigated without errors in sim | Correctness | PREREQUISITE (live) |
| 13 | Holiday early-close handling verified (manual override or calendar gate) | Correctness | PREREQUISITE (live) |
| 14 | Python `/decide` filtering verified to outperform unfiltered on sim sample | Performance | PREREQUISITE (live) |
| 15 | Manual playbook completed 5 times without error | Process | PREREQUISITE (live) |
| 16 | CL `rthOpenHour` bug fixed, or CL explicitly excluded from live trading | Correctness | HARD BLOCK for CL live |
| 17 | `box_capture` JSONL event added for Python offline analysis | Observability | PREREQUISITE (model update) |
| 18 | `moc_state` added to heartbeat JSONL | Observability | IMPORTANT (not blocking) |
| 19 | Live first-day `MaxSignalsPerDay=1` configured | Risk | PREREQUISITE (live Day 1) |
| 20 | Two-person live Day 1 review session | Process | PREREQUISITE (live Day 1) |

---

## Summary of Key Findings

**Order routing:** STAGE does not submit orders. The STAGE button logs a ticket and plays an alert. Under no configuration (`AllowLiveOrderSubmit=true` or false) does clicking STAGE cause a limit order to reach the broker. The ATM template is named but never invoked. Manual submission through ChartTrader is the only order path today. This is the design intent — it is labeled "deferred" in the code — but it means there is currently no automated order path at all.

**Fill detection:** V2_4 infers fills from price action (`low <= entry` for LONG), not from the broker. There is a permanent gap between V2_4's internal model and actual broker state. Any autonomous system built on top of V2_4 must close this gap via the hosting Strategy's `OnExecutionUpdate` subscription.

**Shadow observer:** `AMShadowObserverV1.cs` exists and hosts V2_3 for observe-only scoring. It is NOT wired to V2_4. Events from standalone V2_4 charts fire to no subscribers. The shadow observer proves the Option A architecture is viable and the 2-second HTTP round-trip to the Python scorer works.

**State persistence:** All V2_4 operational state (signals, PnL, lockout, position) is in-memory and resets to zero on any NT8 restart. An intraday restart loses all session accounting. This must be solved before autonomous operation.

**Python-NT8 gap:** Confirmed. The Python ML pipeline has no NT8 futures order path. Option A (hosting Strategy queries Python then submits via NT8) is the recommended closure.

**Logging gaps:** No JSONL events for fill, stop, target, cancel, or canTrade-denial. The session log cannot reconstruct what happened on a given day without the NT8 Output window text. This is the single most important schema addition before Phase 1 sim logging begins in earnest.
