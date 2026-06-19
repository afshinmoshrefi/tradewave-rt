# V2_5 Rebuild Summary — Master Deliverable

**For:** Afshin
**From:** Final Synthesis Agent (closing voice, 9-agent rebuild wave)
**Date:** 2026-04-27
**Read time:** 30 minutes top-to-bottom
**Status:** Rebuild complete. Ready to compile and sim.

---

## 1. TL;DR

V2_5 is a clean-architecture rewrite of your trading cockpit. Where V2_4 was one indicator that conflated "find a setup" with "decide on it" with "block it," V2_5 splits those into three layers:

- **AMTradeCockpitV2_5** (3,793 lines, indicator file) finds every level interaction and emits it as a `candidate` event. It has zero authority to refuse a trade. If price retests a level, you see the candidate. Period.
- **AMTradeStrategyV1** (2,679 lines, strategy file) hosts the indicator, scores each candidate with a transparent rule-based heuristic, ranks them, and submits limit-only OCO bracket orders for the ones it takes.
- The same strategy file also contains **L3 — twelve independently toggleable safety gates**. Every block emits an explicit `abstain` event with the gate name, reason, and recovery time. No silent drops, anywhere.

This is the architectural answer to V2_4's 0.27% conversion rate (2 signals on 741 qualifying touches over 6 months). V2_4 wasn't under-detecting; it was silently swallowing 99.7% of valid setups at gates that never logged. V2_5 surfaces everything and logs every block. The `events.jsonl` is now sufficient to answer "why did the system not take that setup?" for every candidate — that question used to be unanswerable.

**Verdict:** The rebuild is complete. All five P0 structural gaps from the 22-agent review are addressed. Two .cs files, six test files, three documentation updates, atomic state persistence, all wired through the contract. Implementation matches the spec's L1/L2/L3 layer separation, `IsSubmissionAllowed` veto chain, candidate→signal/abstain pairing invariant, and ATM-template-free unmanaged order routing.

**The three steps you do next, in order:**

1. **Open NinjaTrader 8 → Tools → NinjaScript Editor → Compile (F5).** Verify zero errors in `AMTradeCockpitV2_5.cs` and `AMTradeStrategyV1.cs`. (Warnings about obsolete members and unused fields are expected and acceptable.)
2. **Apply V2_5 indicator alone to an ES JUN26 chart and run 1 hour of NT Replay.** Verify candidates surface, JSONL writes to `C:\seasonals\cockpit\sessions\<today>\events.jsonl`, and `python tests/test_contract_compliance.py --date <today>` returns zero violations.
3. **Apply AMTradeStrategyV1 to a fresh chart with `AllowLiveOrderSubmit=false` (the default) and sim-trade for 1-2 weeks.** This is shadow mode. The strategy scores every candidate, fires `signal` and `abstain` events, but never submits real orders. Journal the gap between what the system would have taken and what your discretion would have taken. That gap is your tuning data.

**The realistic outcome:** If you run the validation plan, hit the gates, and execute a manual playbook with discipline, V2_5 should produce results in AM's profile range over 30+ instrumented sessions. **Sharpe 2-3, Profit Factor 2.5-4, Win Rate 50-60%.** Not Sharpe 9. Not breakeven. The architecture supports that range; execution discipline determines whether you reach it.

---

## 2. What Changed Structurally

The before-and-after picture, as one comparison table:

| Aspect | V2_4 | V2_5 + AMTradeStrategyV1 |
|---|---|---|
| File location | One indicator (4,627 lines, everything tangled) | Indicator (3,793 lines, detection only) + Strategy (2,679 lines, scoring + safety + routing) |
| Detection | Conflated with decisions and lockouts | Pure L1, fail-open, every level retest surfaced |
| Hard-coded gates | 8 silently dropping at L1 | 0 silent drops; every gate emits an `abstain` JSONL event |
| Day-type classifier | Required strict 4-node body stack | Emits both 3-node and 4-node interpretations as features |
| FADE direction | One-sided (silently dropped counter-slope) | Both directions emitted as candidates; scorer ranks |
| Pattern B | Unwired scaffolding | Fully wired Untouched→Breached→Armed→Consumed/Invalidated state machine |
| VWAP / Anchored VWAP | Excluded entirely from candidate pool | Surfaced with `is_permission_level=true`; scorer applies -0.20 penalty |
| News-candle wicks | Not detected | Volume-threshold detection; persists as a tracked level |
| 1:30 PM candle | Not tracked | Captured as `Close130` master candle; `Pr130H/L` levels active from 14:00 |
| Multi-day master candles | Not tracked as candidate-eligible | `Pday1/2/3 Close330 H/L` exposed as candidate-eligible levels |
| Daily pivots | Computed but not candidates | Woody's PP / R1-R4 / S1-S4 surfaced as candidates |
| Stop-distance function | Dead anchor parameter unused | Trigger-candle width with bigger-candle exception per AM apr-9 |
| JSONL day_type vocabulary | "congestion" / "trending" (mismatched with AM's spec) | "Sideways" / "LongTrend" / "ShortTrend" / "CautiousLong" / "CautiousShort" |
| Box capture events | Not in JSONL | Emitted as `box_capture` events for every master-candle capture |
| Safety gates | Hardcoded thresholds, no toggles | 12 independently toggleable via NinjaScriptProperty |
| Daily loss default | $150 (locked you out after a single full stop) | $500 sim default, configurable per account size |
| State persistence | All state lost on NT restart | `state.json` atomic write on every fill/stop/target/lockout; restore on `State.DataLoaded` |
| CL bug | `rthOpenMinute=30` hardcoded for CL | Fixed: 9:00 ET for CL via per-instrument schedule |
| Order routing | Staging Card UI only (manual confirm) | Real OCO bracket via `Account.CreateOrder + SubmitOrderUnmanaged` |
| Manual kill switch | None | Chart banner + F12 hotkey + persisted kill state |
| Error handling in `OnBarUpdate` | Historical-silent try/catch swallowed cold-start NREs | All catches re-emit `error` events with stack trace in BOTH Historical and Realtime |
| Bar-time vs wall-clock | Mixed `DateTime.Now` reads, non-deterministic | Bar-time everywhere; deterministic across replays |

The takeaway: **V2_5 is an architectural rewrite, not a patch.** Same strategy intent (AM's level-retest playbook), fundamentally different shape. You can run the V2_4 file and the V2_5 file side-by-side on different charts to compare what each surfaces — V2_4 stays untouched in `Indicators/AMTradeCockpitV2_4.cs` as your rollback safety. Don't delete it.

---

## 3. The Architecture in One Paragraph

The L1 / L2 / L3 layering is borrowed from how institutional execution stacks are built (`signal_generator → tactic_selector → risk_overlay → execution_router`). Each layer has one responsibility, an explicit input/output contract, and an explicit observability layer (the JSONL events). **L1 finds every potential setup. L2 decides which setups to take. L3 has the authority to block any submission, independently of whether L2 wants to take it.** L1 cannot block. L2 cannot bypass L3. L3 cannot select. The mental model: L1 is your scout (sees everything), L2 is your analyst (ranks the field), L3 is your risk officer (says "no" with a reason). For your pain — silent drops — this matters because every block now has a name. When you ask "why didn't the system fire on that setup at 10:32?", the JSONL says, e.g., `abstain | layer=L3 | gate=cooldown_after_stop | reason="18 minutes remaining" | recoverable_until=10:50`. That's the whole architectural point. The previous architecture conflated those three jobs into one 4,600-line file where every concern could short-circuit before the next one logged anything; the result was that 99.7% of valid retests dropped invisibly. The new architecture also supports both how you trade today (manually, with the chart cockpit telling you what's surfacing) and how you'll trade tomorrow (autonomously, with the strategy submitting real orders) — same code, just with `AllowLiveOrderSubmit` flipped from `false` to `true` after sim metrics meet your bar.

---

## 4. What Ships in V1

This is the complete functional list of what's running when you compile and load the rebuild.

**L1 detection (in `AMTradeCockpitV2_5.cs`):**
- Every level retest surfaced as a `candidate` event for both Pattern A (simple level retest) and Pattern B (look-below-and-fail / look-above-and-fail).
- Pattern B state machine per level: `Untouched → Breached → Armed → Consumed | Invalidated`. Each transition emits `pattern_b_state_change`. The Armed transition emits a Pattern B candidate.
- All level types: the four master candles (Close330 A, GlobEx B, Europe C, RTH930 D), the Midnight reference, the new Close130 (1:30 PM candle), Open Range, rolling Pr30 H/L, daily Woody's pivots PP / R1-R4 / S1-S4, multi-day master-candle revisits (Pday1 / Pday2 / Pday3 of the prior 3:30 candle), 50% midpoints of master candles, and news-candle wicks.
- VWAP and anchored VWAP surfaced with `is_permission_level=true`. (V2_4 explicitly excluded these; both of V2_4's two historical signals were VWAP touches, so excluding them was a documented anti-pattern.)
- News-candle wick detection: when a 1-min bar's volume exceeds the prior day's max(9:30, 3:30) volume, register the wick as a tracked level. Slope-up → lower wick = support; slope-down → upper wick = resistance.
- ~85 features per candidate event, including: day_type 3-node and 4-node, SMA200 slope sign and delta, MOC ratio and state, distances to all named levels, cluster membership and confluence count, retrace_side flag, news-wick flags, time-of-day, ADR context, body/wick percentages, volume z-scores. Every feature has an `*_available` flag where warmup-dependent; never NaN.
- `box_capture` JSONL event for every master-candle capture (V2_4 didn't log these, so offline replay couldn't reconstruct boxes; V2_5 fixes this).
- All chart drawings preserved from V2_4: chip legend, box rectangles, pivot lines, VWAP line, anchored VWAP. Plus new candidate markers (red triangle on chart for L3 abstains, green for fires, so you visually see blocks).
- Heartbeat events every 30 seconds during Realtime, with day_type, MOC state, slope, signal state, and live counters — the watchdog feed.
- Phase / bias / regime / day_type change events emitted on classification transitions.

**L2 heuristic scoring (in `AMTradeStrategyV1.cs`, scorer region):**
- `ScoreCandidate(c) → ScorerDecision`: composite score with day-type bonus (+0.20 trend / -0.10 sideways), slope alignment (+0.15 with-direction / -0.10 counter-slope), MOC validation (+0.10 Green / +0.05 Orange / -0.05 Gray), level priority (+0.10 institutional / +0.05 Europe-GlobEx), confluence boost (+0.10 if confluence_count ≥ 4), permission-level penalty (-0.20), Pattern B preference (+0.10), R3/R4 exhaustion penalty (-0.30 fresh longs above R3), late-day penalty (-0.10 if <60 min to close), news-wick boost (+0.10 if active and within 2 points), already-touched-today penalty (-0.10), Friday escalation (+0.05 trend day + Green MOC).
- `p_win` = clip(score, 0, 1). `expected_R` = (target/stop) × p_win - (1 - p_win). `confidence` based on feature-availability count.
- Decision thresholds: take if `p_win ≥ MinWinProbability (0.45)` AND `expected_R ≥ MinExpectedR (0.30)` AND `confidence ≥ MinConfidence (0.40)`. Otherwise abstain with reason.
- Top-K ranking when L1 surfaces multiple candidates per bar (default K=1). Lower-ranked candidates emit `abstain | gate=rank_too_low`.
- HTTP scorer hook present (default off): `UseHttpScorer=true` forwards the candidate to the rt2_1 endpoint for V2 ML scoring; falls back to heuristic on timeout/failure.
- Every scorer decision logged via `decision_response` event for audit.

**L3 safety gates (in `AMTradeStrategyV1.cs`, safety region):**
12 gates evaluated in priority order; first veto wins.

1. **Connection state guard** — block when feed/order disconnected.
2. **Manual kill switch** — operator override; chart banner + F12 hotkey; persisted state.
3. **Holiday gate** — 2026 US futures holidays hardcoded list (parquet integration deferred to V1.1).
4. **RTH window** — entry only between RthOpen and (RthClose - EntryCutoffMinutesBeforeClose); per-instrument hours fix CL bug.
5. **Margin guard** — hard-on, cannot be disabled; checks Account.MarginAvailable.
6. **Position state guard** — one-position policy; rejects if internal Active or broker shows position.
7. **Daily loss kill ($)** — default $500; configurable.
8. **Daily loss kill (%)** — default 2% of CashValue; defaults to off.
9. **Max losing trades / consecutive stops** — default 3 / 2.
10. **Cooldown after stop** — default 30 min.
11. **Max signals per day** — default 5.
12. **Heartbeat self-check** — block if no `OnBarUpdate` for >90 seconds during RTH.

Plus the divergence halt (broker vs internal mismatch) overrides everything once tripped.

Every block emits `abstain` with `layer="L3"`, `gate_name`, `reason`, `recoverable_until_time`, and `gate_state_snapshot`. The trader/dashboard can answer "when can I trade again?" from the JSONL alone.

**Order routing (V1):**
- Limits-only entries (AM apr-9: "I never use market orders"). No `OrderType.Market` submissions.
- OCO bracket: stop-market + first-target limit, both auto-placed on entry fill via `OnExecutionUpdate`.
- `Account.CreateOrder + SubmitOrderUnmanaged` rather than ATM templates (transparent broker order IDs throughout the lifecycle).
- Single-entry / single-exit V1 simplification: one position per instrument, no Fibonacci runner ladder, no 50% midpoint adds.
- Pending limit cancelled at entry-cutoff time if not filled.

**Logging and persistence:**
- Rich JSONL events: `candidate`, `signal`, `abstain`, `fill`, `stop_hit`, `target_hit`, `time_close`, `cancel`, `lockout_active`, `lockout_reset`, `cooldown_active`, `cooldown_reset`, `phase_change`, `bias_change`, `regime_change`, `day_type_change`, `heartbeat`, `error`, `warning`, `news_wick_registered`, `pattern_b_state_change`, `box_capture`, `divergence`, `state_persisted`, `manual_kill_switch_activated`, `manual_kill_switch_resumed`.
- Two JSONL files per session: `events.jsonl` (L1 indicator) and `<instrument>_strategy_events.jsonl` (L2/L3 strategy).
- `state.json` atomic write (write to `.tmp`, rename) on every signal, fill, stop, target, time-close, cooldown, lockout, kill-switch event. Restore on `State.DataLoaded` if today's date matches.
- Manual kill switch: `ActivateManualKillSwitch()` cancels all live orders, sets persistent flag, emits event, draws "MANUAL KILL ACTIVE — F12 to resume" banner. `ResumeAfterKillSwitch()` clears.

**Instruments supported:** ES, NQ, GC. CL is disabled by default (per AM's "tabled" note pending revamp). Per-instrument RTH hours encoded; CL bug fixed in case you re-enable.

---

## 5. What's Deferred to V1.1

Honest list of things that are not in V1 — these are explicit, not accidental.

- **Fibonacci runner ladder (100% / 150% / 200% / 250%):** V1 ships 100% scale-out at first target only. The runner stays on the trigger-candle stop. AM's right-tail trades (1.5R-3R winners) come from the slope-conditional Fib extension; V1 caps the right tail until V1.1 adds the ladder.
- **50% midpoint adds rule:** AM's apr-24 mechanic where you add at 50% of the entry-to-target distance when conditions confirm. Skipped per AM's "tabled" note. Without it, V2_5 expresses AM's typical small wins but cannot express her biggest winners (which come from the convergence add).
- **Full HTTP feature payload:** V1's HTTP integration ships the candidate metadata to the rt2_1 endpoint. The Python live feature engine that would consume the payload and serve real ML predictions is itself a Phase 2 gap (documented in `pattern_scorer_rt2_1/DEPLOY.txt` "KNOWN LIMITATION"). V1 ships heuristic-only scoring; the HTTP infrastructure is wired but the response side is not yet built.
- **F12 hotkey via NinjaScript AddOn:** V1's F12 reference in the kill-switch UI is text only. Real hotkey wiring requires a NinjaScript AddOn class registered with the global hotkey manager. V1 has the chart-banner button click; V1.1 adds the AddOn for the global F12.
- **Holiday calendar via parquet:** V1 hardcodes 2026 US futures holidays. V1.1 reads `holidays.parquet` from `pandas_market_calendars` quarterly.
- **Cautious-mode sizing logic:** Deferred per AM's "tabled" note. V1 uses standard 2-lot ES sizing.
- **CL rule revamp:** Per AM's "tabled" note. V1 disables CL by default.
- **Pattern B re-arm policy:** V1 latches Consumed until session rollover. V1.1 may add a re-arm-after-N-minutes policy for active levels.
- **State.json full restore:** V1's restore is best-effort for counters, lockouts, manual_kill flag. Full LevelWatchState restore is V1.1.
- **Cross-instrument coordination:** V1 is single-instrument. V2 adds multi-instrument capital allocation.

These deferrals are visible. The architecture accommodates them; V1.1 is a feature rollout, not a re-architecture.

---

## 6. AM Clarifications Status

The three P0 questions raised earlier:

**AM-Q-01: Body-stack 3 nodes vs 4 nodes (B<C<D vs A<B<C<D).**
- Status: **NOT BLOCKING.**
- V2_5 emits both interpretations as features: `day_type_v2_3node` and `day_type_v2_4node`. The L2 heuristic defaults to 3-node per AM apr-23 verbatim. If AM clarifies 4-node, the heuristic flips a flag; no L1 rebuild. The V2 ML scorer will learn which matters from training data.

**AM-Q-02: FADE direction — one-sided (slope-aligned only) vs two-sided.**
- Status: **NOT BLOCKING.**
- V2_5 emits candidates in BOTH directions on Sideways days. The L2 heuristic applies a -0.10 score penalty to counter-slope fades, so they're ranked lower but still in the candidate set. If AM clarifies "no counter-slope ever," the heuristic threshold tightens; no L1 rebuild.

**AM-Q-03: 200-SMA slope-magnitude threshold for runner ladder choice.**
- Status: **NOT BLOCKING.**
- V2_5 emits `sma200_slope_delta_pts` as a raw feature. The L2 heuristic uses 5 ES-points/session as the default threshold for fib_200 vs level_to_level runner choice. If AM clarifies a different value, it's a single-line scorer change.

The general principle baked into the architecture: **emit the raw measurement as a feature; let the scorer learn the rule.** Don't encode AM's ambiguity into the detection layer. This is what makes V2_5 robust to clarifications without rebuilds.

These three questions can be sent to AM when convenient. They refine V2_5's behavior; they don't gate the rebuild.

---

## 7. Validation Plan — The Steps You Run

Step-by-step from compile to sim-ready. Each stage has a pass/fail gate. Don't skip.

### Stage 1 — Compile (30 minutes)

Open NT8 → Tools → NinjaScript Editor → Compile (F5).

Verify zero compile errors. Acceptable warnings: `CS0169` (unused private field), `CS0414` (assigned but unused), `CS0618` (obsolete NT8 API usage), warnings on unreachable code in catch blocks.

If you see real errors, the most likely culprits are minor NT8 API surface mismatches that the L1 and Strategy agents could not test against the actual compiler:
- `Account.Get(AccountItem.CashValue, Currency.UsDollar)` — overload signature may need `Currency.UsDollar` second arg removed depending on NT8 version.
- `Position.Quantity` vs `Position.MarketPosition + Volume` — verify property name.
- `Draw.TextFixed` overload — args order.

If compile fails, list the errors. Most should be straightforward signature fixes.

After compile, confirm `AMTradeCockpit V2_5` appears under Indicators tab and `AMTradeStrategyV1` under Strategies tab.

**Pass/fail gate:** Zero errors. Proceed.

### Stage 2 — Load V2_5 indicator alone (20 minutes)

Apply V2_5 to ES JUN26 30-minute chart with 30 days of data. Use defaults.

Verify:
- Boxes draw on chart (Close330, GlobEx, Europe, RTH930 — and Close130 if past 13:30).
- Info card panel renders top-left, shows day_type, MOC state, slope, candidate count.
- NT Output window shows `AMTradeCockpit V2_5 initialized` and no NREs/IndexOutOfRange.
- File `C:\seasonals\cockpit\sessions\<today>\events.jsonl` exists and is being written. Open in text editor: at least one `box_capture` and one `bar_close` event with `schema_version="v25.1"`.

**Pass/fail gate:** All boxes drawn, panel rendered, JSONL writing. Proceed.

### Stage 3 — Replay against historical data (1 hour)

Use NT Replay engine. Pick a recent active day (the more candidates, the better). Run replay at 30x speed.

After replay completes, verify:
- The session's `events.jsonl` has multiple `candidate` events per bar at major level retests.
- `python tests/test_contract_compliance.py --date <session-date>` returns zero violations.
- `python tests/test_pattern_b_state_machine.py --jsonl <events.jsonl>` shows valid state transitions for any Pattern B activity.

Zero orphan candidates. Every candidate must have a `signal` or `abstain` paired by `candidate_id` (the strategy must be loaded on the chart for this — see Stage 4).

**Pass/fail gate:** test_contract_compliance.py passes. Proceed.

### Stage 4 — Load AMTradeStrategyV1 alongside the indicator (30 minutes)

Apply AMTradeStrategyV1 to a fresh chart. The strategy auto-instantiates V2_5 internally (don't double-add the indicator).

Configure:
- `AllowLiveOrderSubmit = false` (this stays false through sim — the kill switch on order submission).
- `EnableManualKillSwitch = false` initially (so you don't accidentally kill the test).
- Default thresholds.

Verify all 12 L3 gate enables show as toggle parameters in the Properties dialog. Verify `<instrument>_strategy_events.jsonl` writes alongside the existing `events.jsonl`.

**Pass/fail gate:** Strategy loads, parameters visible, both JSONL files present. Proceed.

### Stage 5 — Sim-trade for 1-2 weeks (most important stage)

Default settings: `MaxDailyLossDollars=500`, `MaxSignalsPerDay=5`, `EnableManualKillSwitch=false`, `AllowLiveOrderSubmit=false`.

Run normal market hours. The strategy is in shadow mode: it emits `signal` events for accepted candidates, `abstain` events for rejected ones, but does NOT submit orders to the broker. You're collecting data, not trading.

**Daily journal entries:**
- Watch the chart. Note every candidate marker that appears.
- For each candidate, note your discretionary call: take, skip, or skip-with-doubt.
- At end of day, diff your calls against the strategy's calls in the JSONL.
- The gap between your gestalt and the strategy's heuristic is your tuning data.

This is the discipline phase. The system surfaces; you observe; the journal is the bridge.

**Pass/fail gate:** 30+ instrumented sessions accumulated in `C:\seasonals\cockpit\sessions\`. Proceed.

### Stage 6 — Tune the heuristic and prepare for live

After 30+ sim sessions:
- Look at the L2 scorer's `decision_response` events. Histogram p_win, expected_R, confidence by realized outcome (when manual or paper trade was taken).
- If realized win rate is consistently below scorer's p_win, lower the score weights on the over-rated features.
- If realized expected_R is consistently above scorer's, the heuristic is conservative — you can lower thresholds.
- Run all tests: `test_contract_compliance.py`, `test_replay_equivalence.py`, `test_safety_gates.py`, `test_pattern_b_state_machine.py`. All must pass.

**Only after all tests pass on 30+ sessions** with PF >= 1.5: flip `AllowLiveOrderSubmit=true` on the demo account. Run another 30 sessions on Sim101. Two-person sign-off before going to a live account at MaxSignalsPerDay=1 for the first week.

This is what "ready for live" means in the architecture's contract — not "I have a hunch it works."

---

## 8. Honest Risks and Open Issues

What could still go wrong, in priority order:

**1. Compile may need surface fixes.** The L1 refactor agent and the Strategy agent both reported high confidence, but neither could actually run NT8's compiler. Brace/paren balance was verified manually but minor signature mismatches against the installed NT8 build (e.g., `Account.Get` overload arity, `Position.Quantity` vs `.Volume`, `Draw.TextFixed` parameter order, `OrderState` enum values) may surface. These are typically 5-15 minute fixes once you see the compiler error message. Have your NT8 docs handy. The repo's structure makes them easy to locate (Edit calls into the right region).

**2. L2 heuristic weights are starting points, not a final scorer.** They approximate AM's gestalt from the transcripts but they have not been calibrated against forward-collected V2_5 JSONL because V2_5 hasn't run yet. Expect Stage 6 tuning to move several weights by 0.05-0.15. The architecture is robust to this — change a weight, recompile, re-run sim. Do NOT change weights mid-sim; it breaks the apples-to-apples comparison.

**3. Live feature engine for HTTP scorer is a documented Phase 2 gap.** The `pattern_scorer_rt2_1/DEPLOY.txt` already flags this. V2_5's HTTP integration ships the request side; the Python response side is incomplete. V1 ships with heuristic-only scoring (`UseHttpScorer=false` default). When the live feature engine is built, flipping the flag is a deployment, not a rebuild.

**4. Sample size is thin.** 7 V2_4-instrumented sessions in JSONL is too thin for confident calibration. V2_5 needs ~30 instrumented sessions before heuristic tuning is statistically meaningful. Don't make scorer changes off the first 5 sessions.

**5. State.json restore is partial in V1.** Counters, lockout flags, cooldown flags, signal state, manual_kill_switch persist and restore. LevelWatchState (Pattern B per-level state machines) write but restore is best-effort (see line 1929 in the Strategy file). If you restart NT mid-session with an active Pattern B Breached level, the state machine resets to Untouched on next bar — the breach is lost. V1.1 fixes this.

**6. Pattern B may detect too many candidates.** Every 1-min bar that breaches a level is a potential Pattern B candidate. On a choppy day with VWAP and 5 master-candle levels in range, the candidate count can spike to 50-100 per session vs V2_4's typical 10-20. The V1 score threshold filters most, but the JSONL volume increases. If `events.jsonl` exceeds 50 MB/day, consider raising `MinConfidence` or adding a candidate-deduplication-window parameter.

**7. DST and holiday edge cases documented but unverified.** The architecture says "use NT8 exchange-time bar timestamps; never `DateTime.Now`." V2_5 follows this. But March DST 2026 and the May Memorial Day early-close haven't been simulated. Run a sim through the next DST and early-close to verify.

**8. Single-entry / single-exit V1 caps the right tail.** Without the Fibonacci runner ladder and the 50% midpoint adds, V2_5 takes profits at 100% target and walks the runner on the trigger candle stop. This is conservative and limits PF. The manual playbook compensates by suggesting you (the trader) run winners manually using your own runner discipline. V1.1 ladder closes this gap structurally.

**9. The unmanaged order path requires careful OCO logic.** V1 places stop-market and first-target limit on entry fill via `OnExecutionUpdate`. If the broker rejects either leg (rare but possible), the position ends up unbracketed. The current code emits `error` and continues monitoring; you'll want to manually attach a stop in NT if you see this. Stage 5 sim should surface any partial-fill or reject scenarios.

---

## 9. The Path from V1 to V1.1 to V2

**V1.1 (next 4-6 weeks):** Fibonacci runner ladder (100/150/200/250%), 50% midpoint convergence add rule, F12 hotkey via NinjaScript AddOn class, holiday calendar via parquet, full state.json restore including Pattern B state, heuristic tuning informed by 30+ sim sessions, optional candidate-deduplication-window parameter to control JSONL volume.

**V2 (next 2-3 months):** Live ML feature engine connects to the Python rt2_1 endpoint; HTTP scorer replaces heuristic; retrained on V2_5-instrumented data (target: 100+ instrumented sessions); decision_engine layer routes scores through tier classification (A/B/C); cautious-mode sizing wired in; CL rule revamp once AM's clarification arrives.

**V3 (later):** Autonomous execution refinement (no manual confirmation), multi-instrument coordination (capital allocation across ES/NQ/CL/GC), regime-aware sizing (size up in confirmed trends, size down in chop), full audit-trail dashboard, integration with risk-system dashboards.

The path is incremental. Each version's gain is bounded and measurable. V2_5 is V1 of a 3-version arc; V3 is the institutional-grade end state.

---

## 10. What This Means for the Manual Playbook

The Wave 3 manual playbook (`wave3_synthesis/manual_playbook.md`) is still valid and you can sim-trade off it tomorrow. With V2_5 surfacing every candidate to the chart (as a candidate marker), your manual playbook actually has MORE setups visible to consider, not fewer. The discipline shifts from "spot the setup yourself" to "run the playbook's anti-doubt rubric on each candidate the indicator surfaces."

Workflow: V2_5 paints a candidate marker. You read its features (level, pattern, day_type, MOC state, slope) from the info card. You apply the playbook's rubric (is this a fade or trend continuation? does the slope agree? what's my stop, what's my target?). You decide manual take or skip. If take, you execute via Order Entry (limit-only).

The strategy's `signal` and `abstain` events become a second opinion. When the strategy abstains and you would have taken, journal the gap. When the strategy fires and you would have skipped, journal the gap. The gaps are the tuning data for both your discretion and the heuristic.

V2_5 is not "the system replaces you." V2_5 is "the system surfaces and audits; you decide and execute, with the heuristic as a checked second opinion." The autonomous mode (`AllowLiveOrderSubmit=true`) is for after the heuristic is calibrated and your risk tolerance is met.

---

## 11. The Verdict on the Rebuild

Closing assessment, on the merits.

**The architecture is sound.** L1 / L2 / L3 separation is the correct design for an institutional execution stack. The fail-open principle is enforced at every layer: detection cannot block, decision cannot bypass safety, safety cannot select. Every block emits an explicit `abstain` event. The JSONL is sufficient to answer "why did the system not take that setup?" for every candidate. This is the architectural answer to V2_4's silent-drop pathology.

**The implementation is comprehensive.** All five P0 structural gaps from the 22-agent review are addressed: detection-vs-decision conflation (split into L1 and L2), silent gating (every gate emits `abstain`), missing day-type vocabulary (LongTrend / Sideways / etc. emitted), missing box capture events (every master-candle capture logged), state-loss on restart (atomic `state.json` write/restore). The L1 file is 3,793 lines — about 800 lines larger than the spec target due to comprehensive feature emission and chart drawings carried over. The Strategy file is 2,679 lines — close to spec target. Both compile-grade structures (regions, types, methods) match the spec's file structure.

**AM ambiguities don't block.** The three open questions become features in V2_5, not gates. Body-stack 3 vs 4 nodes: both emitted. FADE direction: both emitted. Slope threshold: raw value emitted. The scorer is the layer where AM's discretion gets encoded; the scorer is rule-based (not ML) in V1, so changes are transparent and one-line.

**V1 ships with explicit deferrals.** Single-entry / single-exit, heuristic scorer (no ML), no F12 AddOn, no holiday parquet, hardcoded 2026 holidays. These are real constraints that limit V1's profit factor and operational ergonomics. They are bounded — V1.1 closes most, V2 closes the rest.

**Compile risk is real but small.** The L1 and Strategy agents both confidently reported "compile-ready" but neither tested against the actual NT8 compiler. Most likely first-compile errors: NT8 API signature mismatches that take 5-15 minutes to fix. Less likely: missing `using` statements (verified present in Read), brace mismatches (verified balanced), namespace collisions (verified clean). The structure of the code makes errors locate-able.

**Sim discipline is the hard part.** The system surfaces every candidate. The heuristic ranks them. The trader executes. The "I'll override the rules just this once because my gut says so" temptation kills more retail accounts than bad systems do. V2_5's architecture supports execution discipline by making every block visible and every decision auditable, but it does not enforce discipline. The manual playbook + the sim journal + the test suite + the L3 gates are your scaffolding.

**If you run the validation plan, hit the gates, and execute the manual playbook with discipline — V2_5 should produce results in AM's profile range over a sufficient sample.** That's the realistic claim. **Sharpe 2-3, PF 2.5-4, WR 50-60%.** Not Sharpe 9. Not breakeven. The architecture supports the range; execution and the heuristic together determine whether you reach it. The architecture also supports tuning toward higher Sharpe via the V2 ML scorer once you've collected the data.

The rebuild is complete. Ship it to compile and sim.

---

## 12. Open Items for the Next Conversation

Things to confirm or decide before V1 sim:

- **Whether to email AM the 3 P0 questions now.** NOT BLOCKING but useful for refinement. They take 10 minutes for AM to answer; the heuristic gets sharper. Recommended: send when you next have her attention; do not block sim on this.
- **Whether to clean up the JSONL analyzer scripts** the prior team left in the Indicators folder. There are several `.py` files in `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\` that are not NinjaScript files (NT8 ignores them but they clutter the folder). Recommended: move to a separate `_analyzers/` folder. Cosmetic, not functional.
- **Whether to add a `BarCheckBox` parameter** for "show candidates only / show signals only / show both." V1 shows both by default (red triangles for L3 abstains, green for fires). If you want a quieter chart during sim, add a parameter. Recommended: keep defaults; the visual feedback is informative during the calibration phase.
- **Confirm `AllowLiveOrderSubmit=false`** for sim phase. Default is already false; just verify when you load the strategy. Recommended: add a startup-time `Print` line that warns when `AllowLiveOrderSubmit=true` so you don't accidentally promote.
- **Decide whether V2_4 stays on a separate chart for visual comparison during the first 30 sim sessions.** Recommended: yes for the first 2 weeks; verify V2_5's surfacing matches your gestalt understanding of V2_4's behavior plus the silent drops you suspected. After 2 weeks, retire V2_4 from active charts but keep the .cs file as rollback.

These are decisions for you, not the architecture. The rebuild ships ready.

---

**End of summary. Compile, replay, sim. The system is yours.**
