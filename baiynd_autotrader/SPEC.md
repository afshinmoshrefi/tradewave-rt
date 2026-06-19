# Baiynd Autotrader — Specification

Version: 0.1 (draft, not yet approved for build)
Date: 2026-04-19
Owner: afshinmoshrefi

This spec defines a **fully hands-off, always-on** automated trading system that
executes Anne-Marie Baiynd's level-touch intraday futures strategy. The
indicator (`AMTradeCockpitV2.cs`) is the reference implementation of the signal
logic; this project turns those same rules into a production trading engine
with the safety-wall structure of a self-driving car: trade only inside a
well-defined operational domain, halt and alert the moment anything looks off.

Nothing in this document is final. Open questions are listed in section 17 and
must be closed before we start building.

---

## 1. Overview

**What it is:** a single-process service that runs during RTH, streams market
data, evaluates Baiynd's signal rules, submits bracket orders to a broker,
manages in-trade trail, flattens at the hard-close, and reconciles with the
broker continuously. No human in the loop during normal operation.

**What it is NOT:**
- not the V2 indicator (that is decision-support, draws on a chart, cannot place orders)
- not an options system (that was the `TradeWave_auto_trading` prototype, different scope)
- not an ML-driven discretionary system (ML gate is a later project; see §16)

**Guiding principle:** the operational design domain (ODD) is narrow and
explicit. Anything outside the ODD → halt, alert, do not trade. Losses are
bounded by hard risk caps that halt the system automatically.

---

## 2. Scope & Goals

**In scope (v1):**
- instruments: ES, NQ, GC, CL (one instance = one instrument)
- session: RTH only, single session per trading day
- position size: fixed 1 contract
- signal source: Baiynd rules from V2 indicator
- execution: entry + stop bracket, 30-min SMA20 ratchet trail, time-close

**Out of scope (v1):**
- options, equities
- overnight positions
- multi-instrument portfolio coordination
- dynamic position sizing based on signal quality
- ML meta-gate on top of rules (see §16)
- GUI dashboard (v1 is alerts + logs only)
- multi-broker failover

---

## 3. Operational Design Domain (ODD)

The system will ONLY place new entries when ALL of the following are true:

- RTH session is active: 09:30 ET ≤ now < (close_time − 30 min)
  - ES/NQ/GC: last entry at 14:30 ET (close 15:00)
  - CL: last entry at 14:00 ET (close 14:30)
- Account is flat at RTH open (verified by broker poll, not internal memory)
- Data feed heartbeat is healthy (tick received within last 10 sec during RTH)
- Broker connection is healthy (heartbeat < 10 sec)
- No economic-calendar blackout is active (see §6)
- Today's realized range ≤ 2.5× ADR20 at time of signal
- Bid/ask spread ≤ 2× this instrument's opening-window median spread
- Daily-loss, weekly-loss, consecutive-loss limits not hit
- Max signals/day not hit
- Cooldown timer expired
- 30-min trend regime defined (price, SMA50, SMA200 all aligned)
- State reconciler has not flagged divergence in last poll

Any ODD violation → block new entries, keep managing existing position if any.
If the violation is severe (data feed dead, broker disconnected, state
divergence), flatten existing position too.

---

## 4. System Components (platform-agnostic)

The system is logically separated into these components. Platform choice (NT
Strategy vs. standalone Python) determines how each is implemented, not what
they are.

1. **Data Layer** — subscribes to 1-min + 30-min bars plus tick stream for
   intrabar stop monitoring. Normalizes timestamps to ET.
2. **State Layer** — holds the 15 reference levels for today, trend regime,
   ADR20, europe-candle width, clip range, today's touched-levels latch set,
   current signal state (None / Armed / Active / Exiting).
3. **Signal Engine** — determines which levels are ELIGIBLE for a resting
   limit order today given the trend regime, not-yet-touched latch, RTH
   entry window, and other ODD gates. Re-evaluates continuously and emits
   events when eligibility changes (e.g., rolling 30m levels refresh,
   regime flip, vol halt tripped).
4. **Risk Engine** — gates every eligibility event against ODD + risk caps
   (§6). Also halts the system on threshold breaches.
5. **Order Manager** — maintains the book of resting limit orders at
   eligible levels. On eligibility: places limit + tracks. On fill: attaches
   stop bracket, starts trail. On ineligibility: cancels the limit. On every
   30-min close (for filled positions): recomputes trail and modifies broker
   stop (ratchet only). Handles time-close, partial fills, rejections, acks.
6. **State Reconciler** — polls broker every 60 sec during RTH. Compares
   actual position and account balance to internal state. Divergence → halt.
7. **Watchdog** — monitors component heartbeats, data feed, broker connection.
   Emits kill-switch triggers internally.
8. **Kill Switch Listener** — accepts external halt/flatten commands from a
   well-known interface (webhook, file-drop, or CLI — TBD §17).
9. **Observability** — structured JSONL log of every decision, gate eval,
   submit, ack, fill. Real-time alerts to the chosen channel. Daily summary.
10. **Persistence Layer** — writes today's state to disk every N sec so the
    process can resume after a crash without losing track of open position,
    trail level, or touched-levels latch.

---

## 5. Signal Logic (from V2 indicator)

**Trend gate (hard gate):** 30-min bar close vs. SMA50 vs. SMA200, all aligned.
No counter-trend or neutral-regime entries.

**The 15 reference levels:**
1. Prior-day RTH high
2. Prior-day RTH low
3. Prior-day RTH close
4. Globex (overnight) high
5. Globex (overnight) low
6. Europe session (03:00–04:00 ET) candle high
7. Europe session candle low
8. Rolling prior 30-min high (updated each 30-min bar)
9. Rolling prior 30-min low
10. Session VWAP
11. Pivot R1 (classic floor pivots)
12. Pivot S1
13. Pivot R2
14. Pivot S2
15. MOC-validated institutional candle range (15:30–16:00 ET previous day,
    only if volume ≥ 1.2× 15:00–15:30 candle — see memory
    `project_moc_validation_rule`)

Plus: midnight open (optional 16th reference, currently drawn by V2 but not
consumed as an entry trigger).

**Entry mechanic: pre-placed limit orders.** This matches Baiynd's actual
method and fixes V2's structural timing disadvantage. The engine does NOT
wait for a bar to touch a level before reacting — by then, price has moved
and the fill is compromised. Instead:

- Once the trend regime is set at RTH open (or as soon as it becomes defined
  intraday), the engine computes the **eligible level set**: every
  reference level that is trend-aligned, not yet touched this session,
  within the configured distance band, and not blocked by any ODD rule.
- For each eligible level, the Order Manager places a LIMIT order AT the
  level price, direction inferred from the level's position relative to
  current price and the trend (LONG for levels below in an uptrend; SHORT
  for levels above in a downtrend).
- Resting limits are managed continuously: canceled on eligibility loss,
  replaced on refresh (e.g., rolling prior 30m H/L recompute each 30m
  bar), latched after first fill.
- Fills are price-come-to-order, not order-chase-price.

**First-touch latch:** once a level fills (or is canceled for any reason
other than refresh), it is LOCKED for the remainder of the session. Do not
re-queue it even if price revisits.

**Stop distance:** width of the 04:00 ET europe candle (H − L), clipped to
[0.3 × ADR20, 0.8 × ADR20].

> **Provenance:** the europe-candle-width rule is Baiynd's, stated explicitly
> in her published material. The `[0.3, 0.8] × ADR20` clip is OUR enhancement
> — sanity bounds to prevent unusably tight stops on doji europe candles or
> insanely wide stops on news-spike bars. The values 0.3 and 0.8 are our
> choice, not quoted from her. On a median day the clip is inactive; only
> extreme-tail europe widths see any change.
>
> **ML dependency (important):** this exact rule propagates into the M2
> pattern-scorer's training labels. Every historical signal's win/loss
> label was simulated with europe-width clipped to `[0.3, 0.8] × ADR20`
> (see `pattern_scorer_rt2/src/labels/label_builder.py`). M2's weights
> encode this stop rule. Changing the clip values requires a full retrain
> pipeline: config → rebuild events → relabel → retrain M2 → evaluate. It
> is NOT a one-line backtest experiment. M1 (seasonal) does not use this
> rule; the combiner / `/decide` inherits it indirectly through M2.
> Config: `pattern_scorer_rt2/config.py` → `STOP_ADR_FLOOR_MULT`,
> `STOP_ADR_CAP_MULT`.

**Trail:** 30-min SMA20. On each 30-min bar close, recompute; if new trail is
tighter than current stop in favor of trade → modify stop order. Never loosen.

**Exits (any of):**
- Hard stop hit
- Trail hit
- Time-close: market-close at 15:00 ET (14:30 CL) if still open

**No target.** Baiynd rides trend with the ratchet trail.

---

## 6. Risk Limits (proposed defaults — confirm before build)

Defaults picked assuming 1 ES contract, ~$12.50/tick, typical stop ~10–16
ticks ≈ $125–200 per loss:

| Limit | Default | Behavior |
|---|---|---|
| Daily max loss | **$500** | halt for the day; positions flattened if open |
| Weekly max loss | **$1500** | halt for the week; requires manual restart |
| Max signals / day | **3** | already in V2 |
| Max consecutive losers | **3** | halt for the day |
| Cooldown between signals | **20 min** | matches V2 default |
| Volatility halt | realized range > 2.5× ADR20 by 10:30 ET | halt for the day |
| Spread guard | quoted > 2× opening-window median | skip this entry, not a halt |
| Slippage alarm | > 5 ticks from expected fill | log anomaly; 3× in a day → halt |
| Position size | 1 contract | fixed for v1 |

Manual restart for weekly halt is intentional — weekly losses mean something
in the environment changed and a human should look.

---

## 7. Order Management

**Resting-limit book (the core of this system):**
- The engine maintains a BOOK of resting limit orders at eligible levels.
  The book changes only when eligibility changes: a level becomes eligible
  → place limit; a level loses eligibility → cancel limit; rolling levels
  refresh → cancel old, place new.
- Limits are GTC-for-the-day (or the broker equivalent); they rest until
  filled, canceled by the engine, or hit the end-of-window cancel below.
- Maximum concurrent resting limits: **5** (safety cap; tunable). If more
  than 5 levels qualify, rank by proximity to current price and keep the
  closest 5.
- Order direction per level is inferred from level position vs. current
  price and trend: LONG at levels below in an uptrend; SHORT at levels
  above in a downtrend. Levels on the wrong side for the trend regime
  are never placed.

**Entry (limit fill at broker):**
- When the broker reports a fill on a resting limit, the engine immediately
  submits the stop-market order at `fill_price ± europe-clipped distance`.
- If stop acknowledgment is not received within 5 sec of fill → emergency
  market-flatten the position; we do not run naked.
- On the first fill of the session, CANCEL all other resting limits (one
  position at a time — Baiynd's method).

**Stop:** stop-market order, sized to the filled quantity, placed
immediately after fill confirmation. Never modified except by the trail
rule below.

**Trail:** on every 30-min bar close (while a position is open), recompute
SMA20. If the new SMA20 implies a stop strictly tighter than current stop
in favor of the trade → submit stop-modify. If broker rejects the modify,
log and retry once; on second reject, do nothing this cycle (original
stop still protects).

**End-of-window cancels:**
- close_time − 30 min (14:30 ET or 14:00 CL): cancel ALL resting limits.
  No new entries are allowed in the final 30 min.
- close_time (15:00 ET / 14:30 CL): if any position is open, submit market
  order to flatten.

**Partial fills:** if a limit partially fills, treat the position as the
filled quantity and scale the stop accordingly. Cancel the remainder of
that limit; do not wait for the rest (level moment has passed).

**Rejections:**
- entry-limit reject → log, skip that level for today, continue.
- stop reject after fill → emergency flatten + halt the session.
- stop-modify reject → retry once; then skip this update (see trail above).

---

## 8. State Reconciliation

**Poll frequency:** every 60 sec during RTH.

**Checks:**
- broker-reported position size == internal position size
- broker-reported average entry == internal entry (tolerance 1 tick)
- broker-reported working orders match expected entry + stop
- broker-reported account balance change since yesterday ≈ today's realized
  P&L ± a small unexplained-cash tolerance ($50)

**On divergence:** halt new entries immediately. If divergence is in position
size, emergency-flatten whatever the broker reports as open and alert. Do not
try to self-heal — ambiguous state is when humans should decide.

**Startup check:** at engine start (pre-open), account must be flat AND have
no working orders on the traded instrument. If either is false, refuse to
start, alert operator.

---

## 9. Failure Modes & Responses

| Failure | Detection | Response |
|---|---|---|
| Data feed gap | no tick received for 30 sec in RTH | halt new entries; if open, flatten at next tick |
| Broker disconnect | heartbeat missed 3× consecutive | alert; attempt reconnect; if open position, flatten on reconnect |
| Order rejection (entry) | broker NACK | abort signal; log; continue |
| Order rejection (stop after fill) | no stop ack in 5 sec | emergency market-flatten; halt session |
| Stop modify rejection | broker NACK on trail update | retry once; then skip this update; existing stop still valid |
| Slippage > 5 ticks | fill − expected > 5 ticks | log anomaly; 3× today → halt |
| State divergence | reconciler mismatch | halt new entries; alert; operator decides |
| Volatility outlier | realized > 2.5× ADR20 by 10:30 ET | halt day |
| Calendar blackout | economic event window | no new entries during blackout |
| Daily loss cap hit | realized P&L ≤ −$500 | halt day; flatten if open |
| Weekly loss cap hit | week-to-date ≤ −$1500 | halt week; require manual restart |
| Process crash | watchdog or systemd | auto-restart; persistence layer resumes state |

---

## 10. Kill Switch

**Interface:** single command, reachable from operator's phone, works even if
dashboard is down. Exact mechanism TBD (§17) — webhook, file-drop on a
monitored path, or authenticated CLI.

**Commands:**
- `halt` — stop accepting new signals; keep managing open position
- `flatten` — market-close any open position; cancel working orders; halt
- `halt-and-flatten` — combined (the big red button)

**Guarantees:**
- must execute within 2 sec of command received
- must log the invocation with source IP / sender
- must alert on all channels that kill switch fired

---

## 11. Observability

**Structured logs (JSONL, one file per session):**
- timestamp, event_type, signal_id, level_name, trend_state
- gate_evals: each gate + pass/fail + reason
- order events: submit, ack, fill, reject, modify, cancel
- state: position, balance, open_orders
- alerts: halt triggers with reason codes

**Real-time alerts** (Slack/SMS/email — channel TBD §17):
- any halt
- any emergency-flatten
- daily P&L crosses −50% of cap
- weekly P&L crosses −50% of cap
- state divergence
- kill-switch invoked
- process crash / restart

**Daily summary** (16:00 ET, to the alert channel):
- signals fired / entries filled / exits by type
- P&L, R-multiples
- slippage stats
- any anomalies

**Replay requirement:** given a session's JSONL log, we must be able to
reconstruct every decision the system made. No hidden state.

---

## 12. Startup Sequence (daily, pre-RTH)

- 08:00 ET: fetch prior-day data, compute today's 15 levels, ADR20, clip range
- 09:00 ET: connect broker, verify account flat, verify no leftover orders
- 09:15 ET: fetch economic calendar for today, identify blackout windows
- 09:25 ET: arm the engine, attach to data feed
- 09:30 ET: begin evaluating signals

Any step failure → do not start, alert operator.

## 13. Shutdown Sequence (daily, post-RTH)

- close_time: verify position flat (emergency-flatten if not)
- close_time + 1 min: cancel any lingering orders
- close_time + 5 min: pull broker trade history, reconcile
- close_time + 15 min: generate daily summary, send alert
- 16:00 ET: idle until tomorrow's startup

---

## 14. Deployment Model

**Hosting:** single VPS (location TBD §17 — prefer low-latency to CME).
**Process:** always-on service, auto-restart on failure (systemd or Windows
service equivalent).
**Persistence:** today's state (open position, trail level, touched-levels
set, P&L) flushed to disk every 10 sec.
**Config:** single YAML/JSON file per instrument instance (broker creds,
limits, alert endpoints, calendar source).
**Environments:** dev and prod on the same host is acceptable for v1. Split
later if it matters.

---

## 15. Rollout Plan

Self-driving-car-style ramp. No skipping stages.

1. **Parity-sim.** Strategy signals match V2 indicator bar-for-bar on a
   historical backtest set. Any divergence → fix before proceeding.
2. **Live-data sim.** Real market data feed, fake broker fills. Validates
   timing, gate latencies, state reconciliation against a simulated account.
   Run ≥ 10 sessions.
3. **Live broker, supervised.** 1 contract. Operator watches every session.
   Acceptance: 5 consecutive sessions with no manual intervention required.
4. **Live broker, unsupervised.** 1 contract. Tight daily loss cap. Alerts
   only. Acceptance: 20 consecutive sessions within spec.
5. **Scale contracts.** Gradually, with a sizing-up plan TBD.

---

## 16. Non-goals (v1)

- Multi-instrument portfolio management
- Dynamic position sizing based on signal quality or account equity
- ML meta-gate / `/decide` endpoint integration (v2 feature)
- Overnight positions
- Multi-broker failover
- GUI dashboard (v1 = alerts + logs)
- Regime-based rule adaptation

---

## 17. Open Questions (must be closed before build)

1. **Broker:** Rithmic, Tradovate, IBKR, something else? Drives order API.
2. **Hosting:** existing VPS (where?) or new? Latency to CME?
3. **Platform:** NT Strategy (reuses V2 C# code) vs. standalone Python. (See
   separate discussion.)
4. **Alert channel:** Slack webhook, SMS via Twilio, email, push, combo?
5. **Kill-switch interface:** phone webhook, SSH + CLI, file-drop in a
   monitored dir, Telegram bot?
6. **Calendar data source:** paid subscription (Econoday etc.), scraped, or
   hand-maintained YAML?
7. **Timezone handling:** server clock in ET, or UTC with conversions?
8. **Persistence format:** JSONL only, SQLite, or both?
9. **Backtest infrastructure:** reuse existing ml_scorer_rt / decision_engine,
   or rebuild for bar-level execution replay?
10. **Kill-switch auth:** shared secret, mTLS, IP allowlist?
11. **Disaster recovery:** if VPS dies mid-session with open position, how do
    we ensure the position is closed? (Second box with stop-only fallback?
    Broker-side auto-flatten at close?)
12. **Volatility outlier threshold:** is 2.5× ADR20 right, or should it be
    different per instrument?

---

## 18. Acceptance Criteria for v1

- Runs fully hands-off during RTH for 20 consecutive sessions without
  operator intervention.
- Daily realized loss never exceeds the cap.
- Every halt has a clear logged reason tied to a rule in this spec.
- Broker state matches internal state at every reconciliation point.
- No manual restart required except after weekly-loss halt.
- Any session is replay-able from its JSONL log.
- Parity with V3 indicator eligibility events on the same historical data
  (≥ 98% match, differences attributable to clock / fill modeling).

---

## 19. Revision Log

- 0.1 (2026-04-19): Initial draft. Open questions §17 outstanding.
- 0.2 (2026-04-19): §5 + §7 rewritten from reactive "wait for touch" model
  to proactive **pre-place limit orders at eligible levels** model. V2
  indicator's timing disadvantage does not carry forward to the autotrader.
  Aligned with V3 indicator spec (`ml_scorer_rt/ninjatrader/indicators/
  AMTradeCockpitV3_SPEC.md`). Parity acceptance criterion (§18) now
  references V3, not V2.
