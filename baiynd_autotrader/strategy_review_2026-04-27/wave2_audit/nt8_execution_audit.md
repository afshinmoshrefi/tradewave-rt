# NT8 Execution Audit — AMTradeCockpit V2_4

**Auditor:** Wave 2 agent, NT8 execution path
**Date:** 2026-04-27
**Subject:** `AMTradeCockpitV2_4.cs` (4627 lines) and companions
**Scope:** how a signal becomes (or fails to become) a real broker order

---

## TL;DR

**AMTradeCockpit V2_4 is a signal-only indicator. It does not submit orders to NT8 or any broker. Period.**

- The indicator computes signals, draws a Staging Card with a "STAGE" button, and *logs a ticket string* when STAGE is clicked. That's it.
- The author was honest about this: line 3962 explicitly states *"AllowLiveOrderSubmit=true but live submission from an indicator requires Account.CreateOrder + Submit wiring (deferred). Ticket logged only for now."*
- The companion `AMShadowObserverV1` strategy hosts V2_3 (not V2_4) and is a *pure observer* — its banner comment says *"NO ORDERS ARE SUBMITTED. Stage 1 is observe-only."*
- `C:\seasonals\TradeWave_auto_trading\` is a Tradier *options* broker — completely unrelated to NT8. No NT8 bridge exists.
- Order fills, P&L, daily-loss lockout are all simulated against the indicator's bar-data assumptions. There is **zero** broker-state awareness — no `Account.Positions` checks, no `MarketPosition` reads, no `ConnectionStatus` handling, no `OrderState` callbacks.

**Verdict:** Today the system is a coach + alert + ticket-logger. To go autonomous live, the entire execution layer must still be built. The hardest piece (signals) is done; the second-hardest (order management, broker-state reconciliation, restart recovery) is missing in its entirety.

---

## File inventory

| Path | Role |
|---|---|
| `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMTradeCockpitV2_4.cs` | The indicator under audit (242 KB, 4627 lines) |
| `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Strategies\AMShadowObserverV1.cs` | Pure observer strategy (513 lines). Hosts **V2_3**, not V2_4. NO orders. |
| `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMTradeCockpit*.cs` | Older versions: V2_1, V2_2, V2_3, Dev, baseline. All same signal-only architecture. |
| `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMSystemsCoach.cs` | Sibling coach indicator (98 KB). Out of scope but same author. |
| `C:\seasonals\TradeWave_auto_trading\` | Python options trader (Tradier broker). **NOT an NT8 bridge.** No `NinjaTrader/NT8/cockpit` references anywhere. |

There is no AddOn (AddOns folder exists but contains no `.cs` files), no Python→NT8 bridge, no socket server, no DLL handshake. NT8 talks to itself only.

---

## 1. Where does V2_4 actually submit orders?

**Answer: it doesn't.** A focused search across the indicator for the standard NT8 submission verbs returned **zero matches**:

- `EnterLong` / `EnterShort` / `ExitLong` / `ExitShort`: 0 hits (those are Strategy-only methods anyway; indicators can't call them).
- `SubmitOrderUnmanaged`: 0 hits.
- `AtmStrategyCreate`: 0 hits.
- `SetStopLoss` / `SetProfitTarget` / `SetTrailStop`: 0 hits.
- `Account.` / `Account.CreateOrder` / `MarketPosition`: 0 hits anywhere — the file imports `NinjaTrader.Cbi` (line 35) but never instantiates anything from it.

What the indicator *does* on signal:

1. `SetSignal(...)` (line 2391) — computes entry/stop/target, stamps `signalDirection`, `signalEntry`, `signalStop`, `signalTarget`, sets `currentSignalState = SignalState.Pending` (line 2454), and writes a JSONL `signal` event for the dashboard pipeline.
2. Fires the `OnSignal` event (line 2412) — for a hosting Strategy that subscribes (none of the strategies in the user's `Strategies/` folder hosts V2_4; only `AMShadowObserverV1` hosts V2_3).
3. Calls `ShowStagingCard()` (line 3795) — paints the 280×180 STAGE/SKIP card on the chart.
4. Fires `FireAlert("A3_Signal_..."` (line 2496) — beep + log line.

**The order plumbing stops at the chart.** A human (Afshin) is required to read the ticket and place the limit + ATM bracket in NT8 ChartTrader manually.

---

## 2. The Staging Card UI — what does STAGE actually do?

`OnStageClicked()` (line 3947–3969) is the entire body of the click handler. The flow:

1. If `cardSizeBucket == "Gray"` (risk > $100) — refuse to stage and return.
2. Compute `qty` from bucket (1 for Orange, 2 for Green) and pick the ATM template.
3. Build a string like `"TICKET: LONG 2x via ATM 'AM_Normal_2MES' | Entry 5234.50 | Stop 5230.00 | Tgt 0.00 | Acct Sim101"` — call `Log(ticket)` and `FireAlert(...)`.
4. **Branch on `AllowLiveOrderSubmit`:**
   - **True branch (line 3961–3962):** Log *"AllowLiveOrderSubmit=true but live submission from an indicator requires Account.CreateOrder + Submit wiring (deferred). Ticket logged only for now."* — i.e., the property exists but is non-functional.
   - **False branch (line 3963–3964):** Log *"AllowLiveOrderSubmit=false -> ticket logged only. Submit manually in ChartTrader."*
5. Set `cardStaged = true`. Repaint card (border switches teal → dim gold; text becomes *"TICKET LOGGED - submit ATM in ChartTrader NOW"* — line 3940).

That's the entire STAGE workflow. **STAGE is advisory.** SKIP just hides the card (`OnSkipClicked`, line 3971).

The Staging Card is genuinely useful UX — it computes risk/reward dollars, the size bucket, the ATM template name, and ticks-to-target — but the user remains the order router.

---

## 3. ATM templates — `AM_Normal_2MES` and `AM_Wide_1MES`

**Defaults set at lines 745–746:**
```
AtmTemplateNormal = "AM_Normal_2MES";
AtmTemplateWide   = "AM_Wide_1MES";
```

These are template *names* only. The indicator never opens, parses, or instantiates them. The names are passed to:
- `Log(...)` (the ticket string).
- `RenderStagingCard(...)` (line 3902–3903) — the size-label text.
- `V21UpdatePrePlace(...)` (line 2123, 2128) — the Pre-Place panel header text.

**The strings have to exist as actual ATM templates inside NT8 (Control Center → Tools → ATM Strategies), and the trader has to remember to apply them by hand in ChartTrader.** The indicator does not validate that they exist, does not load their parameters, and has no way of knowing whether the user fat-fingered the template name.

**What the templates are *expected* to contain** (inferred from the ticket text and the V2_4 signal model — `signalEntry`, `signalStop`, `signalTarget`, no fixed target in TREND mode, SMA20 trail):

- `AM_Normal_2MES`: Quantity 2, MES contract, presumably a stop-loss + target bracket. The indicator passes a stop price but **the SMA20 trail is implemented in C# inside V2_4, not in the ATM template**. So the ATM template's stop should be the *hard structural stop*, not a trail. There is a fundamental mismatch: V2_4's TREND-mode "exit on 1-min close past 30m SMA20" cannot be expressed in an ATM template, which only supports static stops, fixed targets, and broker-side trailing-stop ticks. **The trail is C#-only — if NT8 dies or V2_4 unloads, the trail stops trailing.**
- `AM_Wide_1MES`: Quantity 1, same shape, used when openRange > MaxOpeningRange (line 2459).

The indicator never calls `AtmStrategyCreate` (the actual NT8 SDK call to fire an ATM bracket) — that's a Strategy-only API anyway. Even if STAGE were wired up, it could not submit an ATM directly.

---

## 4. Pending → Active state transition — fill assumption

V2_4 lifecycle (line 2509):
> *Pending → assume fill when price returns to entry level on next bar*

`MonitorSignal(...)` (line 2513) runs every 1-min bar close. The fill check (line 2560):
```csharp
bool filled = isShort ? high >= signalEntry : low <= signalEntry;
if (filled) { currentSignalState = SignalState.Active; ... }
```

**This is a bar-data simulation, not a real broker fill.** The indicator decides the trade is filled because the bar's high/low touched the entry price. In reality:

- The trader may not have placed the limit yet (V2_4 just told them to).
- The limit may not have actually filled at that price (queue position, partial fills, ES 0.25-tick mid trades).
- The trader may have placed the limit at a *different* price.
- The broker may be disconnected.
- The user may have manually skipped this trade.

So `signalEntry` becomes a **virtual fill**: P&L counters (`realizedPnlDollarsToday`, `losingTradesToday`), the lockout check, and the trade history (`tradeHistory`) all key off this assumption. **The cockpit's notion of "today's P&L" can drift arbitrarily far from reality** — both directions: the user might not have even placed the trade, or might have closed it manually mid-trade for a different price. There is no reconciliation pass.

Defensive features that *do* exist:

- **No same-bar fill** (line 2542): the bar that *created* the Pending cannot also fill it — prevents a 14:29 signal from racing through a 14:30 cancel.
- **Cutoff guard** (line 2526–2533, 2569–2575): Pending expires automatically at `closeMinute - 30` (14:30 ET ES, 14:00 ET CL), and a defense-in-depth check at the fill site refuses to flip Pending → Active past the cutoff.
- **Pending replacement** (line 2395–2399): a new SetSignal supersedes a still-Pending one — `ClearSignalDrawings()` and a log line; no real cancel goes to a broker because there's no broker order.

**What NT8 does for the real fill:** The user's limit (placed manually) sits in the broker's order book. NT8 receives the fill notification asynchronously, updates the Account window, and triggers any ATM bracket the user attached. The indicator is blind to this entire sequence.

---

## 5. Shadow-observer events — OnTouch, OnSignal

V2_4 publishes two events (lines 295–296):
```csharp
public event Action<TouchEventArgs>  OnTouch;
public event Action<SignalEventArgs> OnSignal;
```

- `OnTouch` fires *pre-gate* on every level inside a bar's range (line 1926), regardless of latch/retrace filters.
- `OnSignal` fires on every accepted signal (line 2412), once per `SetSignal`.

**Hosting strategies:**

- `AMShadowObserverV1.cs` exists but hosts `AMTradeCockpitV2_3` (line 134 of that file: `cockpit = AMTradeCockpitV2_3(...)`). Its handlers `HandleTouch` / `HandleSignal` POST to the rt2_1 scoring service and write `shadow_touches.jsonl`. **No order submission** (banner: *"NO ORDERS ARE SUBMITTED. Stage 1 is observe-only"* — line 11).
- **Nothing else in the user's `Strategies/` folder subscribes to V2_4's events.** The four NT8 sample strategies (`@SampleAtmStrategy`, `@SampleMACrossOver`, `@SampleMultiInstrument`, `@SampleMultiTimeFrame`) are stock NinjaTrader code unrelated to AM.

**Conclusion:** V2_4's `OnTouch` and `OnSignal` events fire *to nobody* in production today. If the user runs V2_4 directly on a chart (no host strategy), the events evaluate `null` (cheap null-check at the call site) and return. The shadow-observer pipeline is wired to V2_3.

This is an architectural tell: V2_3 was the version intended to run as a hosted indicator under a strategy. V2_4 evolved on the chart (Staging Card, FADE mode, sideways-day rules) but the host has not been updated to V2_4. Re-pointing AMShadowObserverV1 from V2_3 to V2_4 would be a small constructor-signature swap — but doing so still produces no orders, just observation.

---

## 6. Order types currently implemented

**On the indicator side: zero. The only "orders" are:**

| Visual | What it represents | Broker reality |
|---|---|---|
| White line `Sig_Entry` | Where a limit *should* be placed | None — trader places it |
| Red dashed `Sig_Stop` | Hard stop level | None — ATM template attaches it |
| Lime dashed `Sig_Target` (FADE only) | Structural target | None |
| Gold dotted `Sig_Trail` | 30-min SMA20 trail | None — C#-only check |
| Up/down arrows `Sig_ArrowUp/Dn` | Direction marker | None |

AM's rule per the comments is **limits only** — no market entries, no stop-market entries. The "fill" assumption in V2_4 mimics a limit fill (low reaches entry on a long, high reaches entry on a short).

The only stop-related concept is the **hard structural stop** (price level, intrabar check at line 2601: `bool stoppedOut = isShort ? high >= signalStop : low <= signalStop;`). No OCO bracket exists in code — OCO would be a property of the user's manually-placed ATM template, invisible to V2_4.

In short: **everything is just visual lines.**

---

## 7. One position per instrument — robustness

V2_4 enforces "one signal at a time" via `currentSignalState` (line 1630):
```csharp
&& (currentSignalState == SignalState.None || currentSignalState == SignalState.Pending)
&& signalsToday < effSignalCap
```

This is a **state-machine self-guard**, not a broker-position check.

**What V2_4 does NOT do:**

- Read `Account.Positions[Instrument]`.
- Check `Position.MarketPosition` or `Position.Quantity`.
- Subscribe to `Account.OrderUpdate` / `Account.PositionUpdate`.
- Call `GetMarketPosition()` (Strategy-only, but the indicator could query the Account directly via `NinjaTrader.Cbi.Account`).

**Failure modes:**

1. **Manual NT8 position open when signal fires:** V2_4 will happily fire and the Staging Card will pop. The user could double up. State machine has no idea.
2. **Manual close mid-trade:** V2_4 still considers itself in `SignalState.Active`, keeps trailing, and at TimeClose records a "win/loss" against a position that was already flat. P&L ledger drifts.
3. **Hung Pending:** if the user *did* place the limit but it never fills (price never came back), V2_4's bar-data check will *also* never flip Active. The Pending self-cancels at `closeMinute - 30`. So this case is at least bounded.
4. **NT8 Pending-Active mismatch:** V2_4 thinks it's Active (bar-data fill) but the broker limit was never placed → V2_4 trails a phantom position.

The author's defense-in-depth comments (line 2562–2575: "no Pending may transition to Active on a bar whose close time is at or past the 14:30 ET cancel cutoff") show awareness of *time*-based race conditions but not *broker*-state mismatches. The latter cannot be solved without reading `Account.Positions`.

---

## 8. Account / instrument risk — PointValue math

PointValue is read in three places, all with a defensive `?? 50.0` fallback (the ES per-point dollar value):

- Line 2115 / 2749 / 3332 / 3807:
  ```csharp
  double pointValue = Instrument != null && Instrument.MasterInstrument != null
      ? Instrument.MasterInstrument.PointValue : 50.0;
  ```

**Per-instrument expected PointValue (NT8 contract specs):**

| Symbol | PointValue ($/pt) | TickSize | TickValue |
|---|---|---|---|
| ES | 50 | 0.25 | $12.50 |
| MES | 5 | 0.25 | $1.25 |
| NQ | 20 | 0.25 | $5.00 |
| MNQ | 2 | 0.25 | $0.50 |
| CL | 1000 | 0.01 | $10.00 |

**P&L compute** (line 2750): `pnlDollars = pnl * pointValue * qty` where `qty` is *2 for Normal, 1 for Wide* (line 2746). **The qty assumes the user placed `qty` MES contracts.**

**Hidden mismatch risk #1: ES vs MES.** The indicator computes stop-distance dollars using `Instrument.MasterInstrument.PointValue` (line 2114, V21UpdatePrePlace). If the chart is **ES**, PointValue = 50 — but the ATM templates are named `AM_Normal_2MES` (MES, PointValue 5). The risk math will be **10× too large** because PointValue is read off the chart's instrument, not the contract specified in the ATM template.

This is verifiable in the source: there is no MES override anywhere, no instrument-redirect, no `tradedInstrument` field. So if a user runs V2_4 on the ES chart but trades MES manually, the Staging Card's "Risk $XXX" and "Reward $XXX" will be 10× the real P&L.

This is *defensible if* the user runs V2_4 on a MES chart and trades MES — but the seasonal/audit context is "ES on sim with micros" which strongly suggests **chart = ES, trades = MES**. That makes today's risk display systematically wrong.

**Hidden mismatch risk #2: stop-dollar gate.** Line 2120: `if (risk_q2 <= 100.0) { v21Qty = 2; ... }`. If chart is ES (PointValue 50), an 8-pt stop is `8 × 50 × 2 = 800` and the bucket flips Gray ("NO TRADE"). On MES the same 8-pt stop is `8 × 5 × 2 = 80` and the bucket is Green. The indicator can therefore reject perfectly tradeable MES setups simply because the chart is ES.

**Hidden mismatch risk #3: TickValue is never read.** The indicator uses `TickSize` (a number of points) for visual offsets only. NT8 exposes `Instrument.MasterInstrument.TickSize` and computes `TickValue = TickSize × PointValue`. V2_4 has no use of `TickValue`, so all dollar math goes through PointValue alone — fine for ES/NQ/MES/MNQ but it would silently mis-size CL (multiplier 1000, not the default-fallback 50) only because the early `?? 50.0` fallback fires when `Instrument.MasterInstrument` is briefly null during state transitions.

---

## 9. Connection / data feed failures — robustness

**OnBarUpdate** (line 897) is wrapped in a single try/catch (line 956–963):
```csharp
catch (Exception ex)
{
    if (State != State.Historical)
        Print($"AMTradeCockpitV2_4 OnBarUpdate error (BIP={BarsInProgress}, bar={CurrentBar}): {ex.Message}");
}
```

The catch is broad, prints once, and swallows. Comment: *"Never let one bar's exception kill the indicator. NT will otherwise stop calling OnBarUpdate, leaving the chart blank except for the OnRender text panel."*

**This is reasonable defensive coding for a UI indicator** — a transient null on one bar does not blank the chart. But for autonomous trading, swallowing exceptions silently is **dangerous**: a NaN propagating through SMA200 reads, or a race between data series, would just print one line per bar to NT's Output window — no alert, no telemetry.

**What it does NOT handle:**

- **`ConnectionStatus` change** (NT8 fires events on `Connection.StatusUpdate`). V2_4 has no subscriber — if the live data feed drops, OnBarUpdate simply stops being called (NT pauses bars), and when data resumes, the indicator picks up at the next bar like nothing happened. There is no banner, no alert, no log entry telling the trader *"data feed dropped at 11:42 ET."*
- **`State.Realtime` ↔ `State.Connection*` transitions:** V2_4 only checks `State == State.Realtime` to gate alerts and JSONL writes. NT8 also has `State.Connection`, `State.Historical`, `State.Terminated`. There is no `OnConnectionStatusUpdate` override.
- **Data gap mid-session:** if 30-min and 1-min series desync after a feed restart, the `BarsInProgress` indices may produce one-sided updates. The defensive `if (CurrentBars[BarsInProgress] < 2) return;` guard at line 899 prevents under-2-bar errors, but a missing 30-min bar could leave SMA20/50/200 reads stale until the next 30-min close. No staleness check.
- **`ConnectionStatus.Connected` checks before "filling":** because there's no real fill, this is moot today, but for any future order-routing layer it must be added.

The robustness story is: **good for indicator survival, blind to connectivity.**

---

## 10. What's NEEDED to take this to autonomous live execution on NT8

This is the long answer. The Sim → Live promotion is non-trivial because today nothing is actually executed — every promotion item is also a *new build* item.

### 10.1 Order routing — pick a mechanism

Four candidate paths, ordered by NT8-idiomatic risk:

| Mechanism | Pros | Cons |
|---|---|---|
| **a) NinjaScript Strategy hosting V2_4** | Native NT8, full lifecycle, EnterLong/ExitLong/SetStopLoss/SetProfitTarget, OCO via SubmitOrderUnmanaged. Disabled in Sim, enabled in Live, same code. | Need to write the strategy from scratch. Cannot run the same V2_4 instance on chart for visual + as a strategy host — would double-fire signals unless V2_4's ShowTrades flag is rigorously honored. |
| **b) NinjaScript AddOn with custom Account.CreateOrder + Submit** | Full control, runs alongside indicator (no host needed), can survive chart removal. | More NT8 SDK complexity. Bracket logic must be hand-rolled (no SetStopLoss in AddOn context). Less commonly used path. |
| **c) ATM template fired from a Strategy** | Reuses the trader's existing ATM templates (AM_Normal_2MES etc.) so target/stop/trail are broker-side. | ATM strategies are auto-generated objects — programmatic submission is `AtmStrategyCreate` in a Strategy. Same Strategy-host requirement as (a). The indicator's TREND-mode SMA20 trail is **not expressible** in an ATM template. |
| **d) External bridge** (Python sends orders via NT8 ATI / DTC / OIF socket) | Decouples signal from execution. | Highest latency, biggest failure surface, requires running an extra process, and NT8's ATI is ASCII-text and not encrypted. |

**Recommendation: (a) — NinjaScript Strategy hosting V2_4.** The shadow-observer pattern is the right shape; just promote it from observer to executor. Reuse `AMShadowObserverV1` as the skeleton, swap `cockpit = AMTradeCockpitV2_3(...)` for V2_4, and replace `HandleSignal` body with order-submission logic.

### 10.2 Stop-loss / target placement at the broker (not just on chart)

A signal must result in a **bracket order at the broker**, *not* a hope that the chart trail will catch it. Specifically:

- **Entry**: `EnterLongLimit(qty, signalEntry, "AM_signal_<n>")` — limit order, named for cancel-by-name.
- **Stop**: `SetStopLoss("AM_signal_<n>", CalculationMode.Price, signalStop, false)` — broker-side stop. Must be placed *immediately on entry submission*, not on fill, so a flash crash between submit and fill still has a hard stop.
- **Target (FADE only)**: `SetProfitTarget("AM_signal_<n>", CalculationMode.Price, signalTarget)`.
- **TREND trail**: This is the tricky one. NT8's `SetTrailStop` takes a fixed *currency* trail or a trailing-stop *ticks* offset. The 30-min SMA20 cannot be expressed natively. Two options:
  - **Soft trail in C# + hard structural backstop in broker:** Keep V2_4's bar-close SMA20 check, but the broker holds the *initial structural stop* — the strategy modifies it (`SetStopLoss(...)` again on each ratchet) when SMA20 crosses entry-favorably. This means each 30-min bar potentially sends an order modification to the broker. Volume should be fine (≤13 modifications a session).
  - **Convert trail to broker trail-stop on first ratchet:** When v2SignalTrail first exceeds entry, snap to `SetTrailStop` with a fixed tick offset = current SMA20 → price. Then the broker handles tightening on each tick. This loses the "wait for 1-min CLOSE past trail" semantics — V2_4 currently does close-based trail not tick-based — so this would change behavior.

The first option is correct.

### 10.3 Cancel-pending workflow

Today the comment in `MonitorSignal` is honest: *"CANCEL all OTHER pre-placed limits in broker NOW — one fill invalidates the rest"* (line 2595, alert A9). The user is asked to do this manually.

In autonomous mode:
- The Pre-Place Panel writes a list of resting limits at multiple structural levels. If the strategy implementation pre-places them all (so the trader doesn't have to pick at the moment of touch), then on first fill *all other* AM-named limits must be canceled — `CancelOrder(...)` keyed by tag prefix `"AM_pre_<level>"`.
- Pending expiry at `closeMinute - 30`: on tick-by-tick, the strategy must call `CancelOrder` for all unfilled AM_signal_* limits at the cutoff.
- Connection drop with pending limits live: NT8 will resync at reconnect and surface OrderState updates. The strategy must reconcile (next item).

### 10.4 Restart recovery — NT8 crashes mid-session

This is the **single biggest sim-to-live gap.** Today V2_4 has no persistence:

- `signalEntry`, `signalStop`, `signalTarget`, `signalDirection`, `signalEntryBar`, `currentSignalState`, `realizedPnlDollarsToday`, `losingTradesToday`, `tradeHistory`, `lockoutActive`, `firewallActive` are all **member fields**, lost on indicator unload.
- On restart, the strategy would re-arm fresh, with `signalsToday = 0`, `realizedPnlDollarsToday = 0` — losing all daily-loss tracking. **Lockouts evaporate** on a crash.

**Required:**

1. **Periodic state snapshot** (e.g., on each `SetSignal`, each `RecordAndDrawTrade`, each lockout flip) to a JSON file under `JsonlLogFolder`/`state.json`. Contents: today's date, signalsToday, realizedPnlDollarsToday, losingTradesToday, lockoutActive, currentSignalState, signal* fields, an ordered list of `tradeHistory`.
2. **State restore on `State.DataLoaded`** (V2_4's earliest in-bar state): if `state.json` exists and its date matches today's session, re-hydrate the fields. Especially `realizedPnlDollarsToday` and `losingTradesToday` — without them, a crash bypasses the lockout.
3. **Order reconciliation**: query `Account.Orders` for any AM_*-tagged orders. For unfilled limits, ensure they're still where state.json claims; for filled-and-active brackets, attach the strategy's local position back to the order tag. NT8's `OnOrderUpdate` callback is the right hook for this.
4. **Daily reset gate**: if `state.json.date != today`, blank everything out cleanly (existing `ResetForNewDay()` body, line 4499).

### 10.5 Daily loss kill-switch enforcement at the broker level

**Today the kill-switch is C#-only** (line 3989: `if (MaxDailyLossDollars > 0 && realizedPnlDollarsToday <= -MaxDailyLossDollars)`), and `realizedPnlDollarsToday` is computed against simulated bar fills (see Q4). Three failures stack:

1. **Wrong P&L baseline**: bar-data simulation, not broker fills.
2. **Indicator-only enforcement**: `lockoutActive` only blocks `canTrade` (line 1632) — i.e., it stops *new V2_4 signals*. It does NOT cancel resting limits, does NOT close open positions, does NOT prevent the human from clicking buttons in NT8.
3. **No persistence (see 10.4)**: a crash resets the lockout to false.

**Required at the broker level:**

- Use **NT8's built-in Account-level "Auto Close at Daily Loss"** (Tools → Options → Trading → Account. Each Account can have a Daily Loss Limit that hard-flattens on breach). This is the only enforcement that survives indicator/strategy crashes.
- Set this *equal to* MaxDailyLossDollars so the broker is the source of truth.
- The C# code should *track and pre-empt* (stop sending new orders) but never be the sole defense.
- Same for max daily losing trades — easier to enforce in code (count is reliable) but should also have an account-level circuit breaker if the broker offers one (NT8 does not natively offer "max losing trades" — Tradovate, Topstep do).
- For a Topstep/funded account, the broker's own Trailing Drawdown is the ultimate kill — V2_4's $150 daily loss will fire well before that.

### 10.6 Sim → Live promotion checklist

Concrete items, in order:

**A. Plug holes in V2_4 itself (signal correctness):**

1. **Verify PointValue math against the actual traded instrument**, not the chart instrument. Add an `OverrideTradedSymbol` property (e.g., "MES 06-26") and use `Instrument.GetInstrument(...)` to fetch the real PointValue for risk display and bucket gating. (Today: line 2114 reads chart instrument's PointValue → wrong if chart=ES, trades=MES.)
2. **Add a `ConnectionStatus` watcher.** On `Disconnected`, fire an audible alert and a `connection_drop` JSONL event. On `Connected`, fire a `connection_resumed` event. Don't try to fill anything until reconnected for ≥30 s.
3. **Tighten the OnBarUpdate catch** — keep the swallow, but add a counter `obuExceptionsToday` and surface it in the panel + JSONL. A single null is fine; ten in five minutes is a problem.
4. **Persist state to disk** (10.4) — even before live trading, do this for sim so a crash doesn't lie about today's P&L.

**B. Build the executor strategy:**

5. Write `AMExecutorV1.cs` (Strategy). Skeleton: copy `AMShadowObserverV1` body. Swap V2_3 host for V2_4. Replace `HandleSignal` to call `EnterLongLimit` / `EnterShortLimit` + `SetStopLoss` + (FADE only) `SetProfitTarget`.
6. Implement TREND trail in the strategy (10.2 first option): subscribe to V2_4's 30-min bar event or query `sma20_30min` directly via the hosted indicator reference, then `SetStopLoss(...)` on each ratchet.
7. Implement Pre-Place pre-emption: on a fill (`OnExecutionUpdate`), `CancelOrder` for all other AM_pre_* tags.
8. Implement order reconciliation in `OnOrderUpdate` — match by tag, log every state change to JSONL.
9. Implement state persistence + restore.
10. Implement broker-level lockout: cancel all AM_* orders on `lockoutActive` flip; refuse to submit new ones.

**C. Configure NT8 / broker:**

11. Create the actual ATM templates `AM_Normal_2MES` and `AM_Wide_1MES` (or remove them from V2_4 and rely entirely on EnterLongLimit + SetStopLoss in the strategy — recommended).
12. Set the NT8 account's **Daily Loss Limit** in Tools → Options to match `MaxDailyLossDollars`.
13. Set the account's **Max Position Size** to the same maximum the strategy will request (qty 2 MES).
14. If Topstep / funded account: confirm trailing drawdown limit is well above $150.

**D. Run-in (sim, before live):**

15. **Two weeks of paper-trading the executor strategy in NT8 sim** with V2_4 hosted, ShowTrades=true on chart, AllowLiveOrderSubmit=true, AccountName=Sim101. Compare daily JSONL `signal` events to actual `OrderUpdate` callbacks — every signal should produce exactly one limit, one stop, optionally one target. **Reconciliation: for each signal, read `Account.GetExecutions(...)` and verify entry/stop/target prices.**
16. **One week of intentional crashes** — `Strategy → Disable` mid-trade and re-enable, kill NT8 from Task Manager, pull network. State must restore. Pending must be reconciled.
17. **One full simulated lockout day** — set MaxDailyLossDollars to a value the day will breach. Verify all open orders are canceled, position is flattened, no new signals fire.
18. **Latency log**: timestamp signal generation → order submit → broker ack. P50 < 200 ms, P99 < 1000 ms. Anything slower means the SubmitOrderUnmanaged path is contended.

**E. Live promotion (one-way door — no rollbacks):**

19. **Switch to a single MES contract** (not 2). One contract = ~$5/pt; a worst-case 8-pt stop = $40. Loss-bound the live trial.
20. Run **one week, one trade per day max**. After each session, compare the JSONL ledger to the broker statement. Any reconciliation mismatch → halt promotion.
21. Run **one week with two trades per day max**. Same reconciliation gate.
22. Run **one week at full 2 MES qty**. Same gate.
23. **Promote to ES (1 contract)** only after MES is rock-solid.

### 10.7 Hidden risks the checklist alone won't catch

Thinking through the failure modes that don't show up in a clean test:

- **Bar-close vs realtime semantics:** V2_4 runs `Calculate.OnBarClose` (line 726). All signal logic only fires at 1-min and 30-min bar closes. Real-time bracket modifications (ratchet trail) on a `SetStopLoss` call happen at next bar close, not on each tick — that's a 30 s blind window where price can run past the in-progress trail. Mitigation: explicitly `Calculate.OnEachTick` for the strategy and `Calculate.OnBarClose` for V2_4; have the strategy poll `cockpit.sma20_30min` each tick. Or, accept the latency — for a swing-style 30m-SMA trail, 30 s of close-to-close blindness is small.

- **Same-bar fill-then-stop:** in fast markets, a limit can fill and the stop can hit on the same bar. V2_4's MonitorSignal has a guard against same-bar Pending → fill (line 2542) but no guard for fill → stop on the same bar. With broker-side stops this is the broker's problem (atomic), but the C# trade record will show `EntryBar == ExitBar` and `pnl` could be exactly the stop distance — fine, but the dashboard category logic (TREND/FADE/win/loss) should handle it.

- **Holiday session length:** `closeHour`/`closeMinute` is per-instrument (15:00 ET ES, 14:30 ET CL — line 2705) but does the indicator handle Friday early close days, day-after-Thanksgiving short sessions? Grep for `closeHour` shows it's a static field. **Risk:** on shortened sessions the cutoff math is wrong, and a trade can fill within minutes of the broker's actual close, with no time to manage. This is *already* a sim-mode issue but only becomes real money when live.

- **NT8 license / connection auto-disconnect:** Rithmic, CQG, Continuum each have idle disconnect policies. A strategy left running through midnight may disconnect and reconnect at session resume — the strategy must handle `OnConnectionStatusUpdate` cleanly. Today V2_4 doesn't, and the executor strategy (built per 10.1) must.

- **Multi-instance footgun:** if the user adds the indicator to *both* a 1-min ES chart and a 1-min MES chart, two sets of signals fire, two staging cards pop, two state machines run. The strategy host must have an instrument-instance singleton check and refuse to run two AMExecutor strategies on the same Account simultaneously.

- **Sim-mode fills are too good:** NT8 sim fills at the limit price 100% of the time when the bar's high/low touches it. Live, queue position matters. **Live fills will be worse than sim** — bake this into expectations. Consider running sim with `Slippage = 1 tick` to bias against the strategy.

---

## Cross-reference notes for Wave 3

For the synthesis layer:

- **Signal correctness vs execution correctness are separable.** The Wave 3 question "is the trading edge real?" is answered by the offline backfill against shadow_touches.jsonl (rt2_1 scoring). The Wave 3 question "can we deploy autonomously?" is answered by the build list above and is *largely independent* of edge.
- **The shadow-observer pattern is the right architecture** for Stage-2 autonomy — a strategy hosting V2_4 with AllowLiveOrderSubmit gating execution. Re-pointing AMShadowObserverV1 from V2_3 to V2_4 is one line; turning it from observer to executor is the next 200–400 lines (the strategy body in 10.1–10.5).
- **The biggest gap is *not* signal logic** — it's restart recovery (10.4) and broker-state reconciliation (10.5/10.6). These belong in the Wave 3 risk register as **highest severity, highest probability** for the live phase.
- **PointValue chart-vs-traded mismatch** (Q8) is a *current* live-relevant bug even before autonomous: today the trader reads the Risk $XXX off the staging card — if the chart is ES and the trade is MES, that number is 10× wrong and the trader is making sizing decisions on bad data.
- **Daily loss enforcement must move to NT8 account-level** (10.5). C# can pre-empt; the broker must be the hard line. This is non-negotiable for funded accounts.
- **Sim → Live ordering** (10.6 step E): MES first, ES last. Topstep/Apex traders skip MES entirely because their accounts are micros-only or full-only depending on plan — confirm what Afshin's live plan actually allows before assuming MES is a step.

End of audit.
