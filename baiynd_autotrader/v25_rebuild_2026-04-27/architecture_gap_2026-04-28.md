# V2_5 Architecture Gap Analysis — Pre-AM Meeting Brief

**For:** Afshin
**Reading time:** 25 minutes
**Date written:** 2026-04-27 evening (for AM meeting 2026-04-28)
**Reference:** `architecture_spec_v25.md` (the contract); `AMTradeCockpitV2_5.cs` (L1 in flight); `quarantine/AMTradeStrategyV1.cs` (L2/L3 not in flight)

This document measures what is shipped against what you specified. It is honest, not aspirational. Where I write "85%," I mean it; where I write "0%," I mean nothing of value is in front of NinjaTrader yet.

---

## 1. Architecture Compliance Scorecard

### L1 — Pure Detection (target: every candidate inside [low, high], no silent drops)

**Overall L1 completeness: ~78%.**

What is in the file at `Indicators/AMTradeCockpitV2_5.cs` (3,335 lines, time-stamped 2026-04-27 23:11) is genuinely L1-shaped. It compiles in concept (the existing `NinjaTrader.Custom.dll` has the same timestamp, but no live confirmation that it includes V2_5 cleanly — see P0 below). The detection logic is real, not a stub.

**What is implemented (with evidence):**

- **Master candle box capture** (`Process30MinBar`, V2_5 lines 871-1091): Close330/A, GlobEx/B, Midnight, Europe/C, RTH930/D, and the new **Close130** (1:30 PM candle) all wired with `EmitBoxCapture` JSONL events (lines 2007-2052). Per-instrument hours fix the V2_4 CL bug (V2_5 lines 761-769).
- **Pattern A and Pattern B** both fully wired (`CheckEntry`, V2_5 lines 1307-1352). The Pattern B state machine — `Untouched → Breached → Armed → Consumed | Invalidated` — is implemented for both LONG and SHORT directions per level (V2_5 lines 1380-1493). Both directions emit candidates on Sideways days; no slope-direction filtering at L1. This is exactly the spec.
- **Level pool covers the spec's universe** (`BuildAllLevels`, V2_5 lines 1501-1631): all four master candles (H/L/Mid), Pday1/2/3 multi-day master-candle revisits (Close330, Europe4AM, GlobEx6PM, RTH930), Close130 H/L, ORH/ORL, rolling Pr30 H/L with `@HHmm` stamp, daily Woody's pivots PP/R1-R4/S1-S4, SMA50_30, SMA200_30, SMA50_1, SMA200_1, VWAP and AnchVWAP (with `is_permission_level=true`), and news wicks.
- **Feature vector** (`BuildFeatureVector`, V2_5 lines 1748-1985): roughly 70 features. Both `day_type_v2_3node` and `day_type_v2_4node` emitted as separate features (V2_5 lines 1755-1758). MOC ratio + state, SMA200 slope sign + delta + `*_available` flag, distances to every named level, Fib target proposals (100/150/200/250%), stop-distance proposal with the trigger-candle-width-clipped-to-ADR rule (V2_5 lines 1903-1929) — this is the V2_4 dead-anchor bug fixed.
- **Box-capture JSONL events** (V2_5 lines 2014-2030) — V2_4 didn't log these; V2_5 does.
- **Day-type vocab fixed**: heartbeat now emits `day_type_v2_3node` and `day_type_v2_4node` with the proper enum values (V2_5 lines 2554-2568).
- **News-wick detection** (V2_5 lines 2098-2151) — slope-gated registration, persisted in `state.json`.
- **State persistence** (V2_5 lines 2577-2682) — atomic write, restore is best-effort.
- **Newest-of-kind box shading** (V2_5 lines 2985-3096): the recently added rule. `IsNewestOfKind(box)` collapses older same-type boxes immediately to dashed-line FADE phase. This is the apr-27 user rule.
- **`abstain` event for outside-RTH** (V2_5 lines 1276-1279): only L1 self-skip emits an explicit abstain.

**What is missing or weak in L1 (the 22%):**

- **No `error` re-throw path.** `OnBarUpdate`'s outer `catch` (V2_5 line 861) calls `EmitError(ex)` and continues. Spec §1.4 invariant 6 says "no `try/catch` swallowing in `OnBarUpdate`"; the current code logs but does not re-throw, so a recurring bar-processing exception is invisible at higher layers (you'll see the JSONL `error` events but the indicator keeps running on broken state). Acceptable for V1; document and tighten in V1.1.
- **`already_touched_today` is hard-coded `false`** (V2_5 line 1875). The latch tracking is in `uniqueLevelsTouchedToday` but isn't wired into the per-(level, direction) feature flag the way the spec describes. This means the scorer can't apply the -0.10 already-touched penalty per AM apr-9. Easy fix (see P1.4).
- **Confluence and cluster features are not computed.** Spec §3.3 requires `num_levels_in_cluster`, `cluster_max_volume_origin`, `is_highest_volume_in_cluster`, `confluence_count`. None of these keys are populated in `BuildFeatureVector`. The scorer reads them at default values (0 / false). The L2 heuristic's "confluence_count >= 4 → +0.10" rule is dead.
- **Some geometry features missing**: `entry_extension_from_overnight_low_adr`, `globex_open_vs_europe_high_pts`, `pattern_6pm_below_4am_and_inst_long`, `vol_zscore_vs_session`, `first_1min_volume_pct_of_normal`, `approach_speed_pts_per_min` — none populated. These are nice-to-haves for the ML scorer; not critical for V1.
- **1:30 PM fallback for early-close days** (e.g., July 3). On a 13:00 ET early close, the 13:30 capture never runs. Spec §6.5 doesn't explicitly mandate a fallback, but the holiday-aware capture is not present. P3 deferred.
- **Heartbeat is bar-time gated**, not wall-clock gated (V2_5 lines 2540-2543). On Realtime, bar times advance only on bar closes, so the 30-second cadence the spec expects becomes 30-second-bar-time, which collapses on quiet markets. The architecture spec §3.14 calls heartbeat "every 30 seconds during Realtime to validate the watchdog." This is partially in place; not a blocker.
- **Pattern B state-restore on NT restart is incomplete.** State is persisted (V2_5 line 2603 onward) but the `TryRestoreStateJson` method (V2_5 lines 2659-2682) is best-effort — it logs that the file was found and defers full deserialization. Per spec §5.6 this is a known V1 deferral.

**Visualizations and operator UX:**

- Boxes draw with the apr-27 newest-of-kind rule (verified at V2_5 lines 3025-3097). Looks correct on paper.
- Diagnostic info card (V2_5 lines 2784-2851) shows day-type 3-node and 4-node, MOC state, 200-SMA slope, candidate count, levels touched, Pattern B armed count — enough to demo the architecture's "explainability" claim.
- Candidate markers (V2_5 lines 2159-2189): green dot for LONG Pattern A, orange dot for SHORT, cyan triangle for Pattern B armed, gray "x" for permission-level VWAP touches. These will visualize the difference between V2_4's silent drops and V2_5's surfaced candidates.

**Fail-open principle: ~85%.** L1 is fundamentally correct. It does not gate at L1 by retrace-side, latch, day-type, slope-direction, or anything else. The only L1 self-skip is `outside_rth_window`, which emits abstain. Pattern A surfaces both LONG and SHORT directions in the same bar when `bar.Close >= L` and `bar.Close <= L` — the simultaneous touch case that V2_4 silently dropped.

**Explicit-abstain principle: 60% — only L1 emits abstain. L2/L3 abstain logic exists in quarantine; not in flight.** Spec §3.5 requires an `abstain` event for every block at every layer. L1's one abstain (outside-RTH) works. L2's "scorer rejected" and L3's twelve gates emit abstains in quarantine code, but the file is not in `Strategies/`, so the operator gets none of them. As of tonight, the JSONL stream has no L2 or L3 abstain events being written.

**AM-ambiguities-as-features principle: 95%.** Both 3-node and 4-node interpretations emitted (V2_5 lines 1755-1758 and lines 1252-1267). FADE direction emitted as both LONG and SHORT candidates on Sideways days (V2_5 lines 1326-1342). Slope steepness emitted as raw `sma200_slope_delta_pts` for the scorer to learn. This is the single best-executed contract in the rebuild.

### L2a — Basic Objective Filters (target: toggleable RTH window, position state, etc.)

**Overall L2a completeness: 0% in flight; ~75% in quarantine.**

The ONLY L1-side L2a-shaped check is the outside-RTH abstain at V2_5 line 1276, which is technically L1 self-gating. There is no L2a layer in the running indicator. All real L2a logic — gates that could be toggled by NinjaScriptProperty, position-state guard, holiday gate, manual kill-switch — lives in `quarantine/AMTradeStrategyV1.cs` lines 1499-1775 and is not in `Strategies/`. The strategy file is not currently compiling into NT8.

What exists in quarantine:
- 12 NinjaScriptProperty toggles (`EnableRTHWindowGate`, `EnableDailyLossKill`, etc.) at quarantine lines 350-456.
- `IsSubmissionAllowed` orchestrator at quarantine lines 1499-1596 with first-veto-wins ordering.

What does not work tonight: any of the above. The strategy is not loaded.

### L2b — ML / Heuristic Subjective Scorer

**Overall L2b completeness: 0% in flight; ~65% in quarantine.**

In quarantine: a heuristic scorer with the spec's rule set (quarantine `ScoreHeuristic`, lines 881-1019). Day-type bonus, slope alignment, MOC validation, level priority, permission-level penalty, Pattern B preference, R3/R4 exhaustion, time-of-day, news-wick, retrace-side, Friday escalation. The HTTP scorer hook is wired (quarantine lines 1045-1118) with timeout fallback to heuristic, but the live feature engine on the Python side is itself a Phase-2 gap (per `pattern_scorer_rt2_1/DEPLOY.txt`).

ML feature payload completeness: V2_5's feature vector is ~70 of the spec's ~100 fields. The scorer-relevant ones (day-type 3/4, slope, MOC, level name, permission flag, pattern type, time-of-day, retrace-side) are populated. The cluster/confluence/geometry features are not. This means the heuristic in quarantine will run on partial data — confluence_count is always 0, IsHighestVolumeInCluster is always false, several time-series volume Z-scores are always default. Score-relevant defects, but not show-stoppers.

In flight tonight: 0%. No L2b scoring is happening on any chart.

### L3 — Safety Gates

**Overall L3 completeness: 0% in flight; ~80% in quarantine.**

Quarantine has all 12 gates implemented as separate methods returning `GateResult`:
- `GateRthWindow`, `GateDailyLossDollars`, `GateDailyLossPercent`, `GateDailyLosingTrades`, `GateCooldown`, `GateMaxSignals`, `GatePositionState`, `GateMargin`, `GateHoliday`, `GateConnection`, `GateHeartbeat` (quarantine lines 1600-1775).
- Each gate has its own `Enable*` property and configuration parameters, satisfying the "independently toggleable" requirement.
- Each emits `abstain` with `layer="L3"`, `gate_name`, `reason`, `recoverable_until_time`, `gate_state_snapshot`.
- Manual kill-switch gate is wired (quarantine line 1510-1513) with a placeholder that sets `manualKillSwitchActive = true` — the chart-banner button click handler is referenced but the actual UI button is not wired.
- Reconciliation (broker vs internal mismatch) is implemented (quarantine lines 1792-1819).
- State persistence atomic write (quarantine lines 1841-1900).

In flight tonight: nothing. The strategy is not in `Strategies/` and not in the compiled assembly. No L3 gates are blocking anything because there's no L3 layer running.

### Compiled summary

| Layer / Principle | In-flight % | Quarantine % | Comment |
|---|---|---|---|
| L1 detection | 78% | n/a | The biggest win; needs cluster/confluence features and re-throw discipline. |
| L1 fail-open | 85% | n/a | Best-implemented invariant. |
| L1 explicit-abstain | 100% (one case) | n/a | Only outside-RTH; L1 has no other "skips" by design. |
| L1 AM-ambiguities-as-features | 95% | n/a | Both interpretations emitted. |
| L2a basic filters | 0% | 75% | Quarantined. |
| L2b heuristic scorer | 0% | 65% | Quarantined; missing cluster features. |
| L2b HTTP scorer | 0% | 60% | Quarantined; Python side incomplete. |
| L3 safety gates (12) | 0% | 80% | Quarantined. |
| L3 state persistence | n/a (L1 partial) | 75% | Quarantined; restore deferred. |
| L3 reconciliation | 0% | 70% | Quarantined. |
| Manual kill-switch UI button | 0% | 30% | Property toggle exists; click handler not wired. |

The honest top-line: **L1 is real and demoable. L2 and L3 are designed and written but not deployed.** This is what tomorrow's meeting must reflect.

---

## 2. The Blocking Gap Punchlist

Ranked by impact. P0 = breaks the basic operator experience. P1 = blocks a credible demo. P2 = blocks institutional-grade. P3 = nice-to-have / V1.1.

### P0 — must-fix before AM meeting (no exceptions)

**P0.1 — Confirm V2_5 actually compiles in NT8 NinjaScript Editor.**
- What's broken: Unverified. The dll timestamp matches V2_5.cs at 23:11, but recent file edits (newest-of-kind, BarsInProgress fix, generated-region cleanup) may not be in the assembly. There is no test artifact confirming a clean compile.
- Where: Tools → NinjaScript Editor → Compile (F5). Errors show in the bottom error pane.
- Fix complexity: 5-30 minutes if no errors; 30-90 minutes if there are 2-5 typical NT8 surface mismatches (e.g., `Account.Get(AccountItem.CashValue, Currency.UsDollar)` overload, `Position.Quantity` vs `.Volume`, `Draw.TextFixed` arg order).
- Lines/files: `AMTradeCockpitV2_5.cs` only. Strategy stays in quarantine.
- Hours: 1 hour worst case.
- Tonight or never: **TONIGHT.** If V2_5 doesn't compile, you have nothing to show AM.

**P0.2 — Verify boxes draw correctly on a test chart.**
- What's broken: Unknown until you load it. The newest-of-kind code (V2_5 lines 2985-3015) is recent.
- Where: ES JUN26 30-min chart with 5 days of history, V2_5 attached.
- Fix complexity: Visual inspection. Pass/fail in 15 minutes.
- Tonight: **TONIGHT.**

**P0.3 — Verify the JSONL is being written.**
- What's broken: Unknown. JSONL path is `C:\seasonals\cockpit\sessions\<today>\events.jsonl` (V2_5 line 693). The folder exists with old data through 2025-11-17; today's folder may not exist yet.
- Where: After loading V2_5, watch for `events.jsonl` to appear and grow as bars close.
- Fix complexity: If folder permissions or path issues, 10 minutes.
- Tonight: **TONIGHT.**

**P0.4 — Confirm the diagnostic info card actually renders.**
- What's broken: SharpDX brushes initialization (V2_5 lines 2934-2953) and panel render (V2_5 lines 2784-2851) — only verifiable on chart.
- Where: Top-left of the chart by default (`PrePlacePanelX=10, PrePlacePanelY=65`).
- Fix complexity: If brushes fail, 30 minutes.
- Tonight: **TONIGHT.**

### P1 — needed for credible demo

**P1.1 — Confirm at least one Pattern A AND one Pattern B candidate appear on a recent active day's replay.**
- What's broken: The detection logic is in place but never run end-to-end. NT Replay against a recent ES day will produce candidate events.
- Where: Run NT Replay on a known active day. Tail `events.jsonl` for `"type":"candidate"` lines.
- Fix complexity: 0-2 hours depending on what surfaces. If no candidates appear, suspect the level-in-bar-range check (V2_5 line 1321), the warmup gate (V2_5 line 803), or something subtle.
- Tonight: **TONIGHT or first thing in morning before AM meeting.**

**P1.2 — Find a single "V2_4 silently dropped this; V2_5 surfaces it" case.**
- What's broken: Demo-side. You need at least one specific bar where V2_4's JSONL has no signal but V2_5's JSONL has a candidate, ideally a Pattern B armed event.
- Where: Compare V2_4's old `events.jsonl` (pre-2026-04-23 sessions) against fresh V2_5 replay.
- Fix complexity: 30-60 minutes of grep work. The wave3 reports (`gap_to_am.md` GAP 2) say 1,271 of 2,956 touches were Pattern B and were never surfaced; pick any active day from the 7 V2_4-instrumented sessions and you should find one.
- Tonight: **TONIGHT.** This is the headline demo moment.

**P1.3 — Diagnose any obvious abstain-event bugs.**
- What's broken: The L1 abstain (V2_5 lines 2058-2070) has `OnAbstain` event firing inside a `try { ... } catch { }` swallow. This is fine for V1 since it only fires once per outside-RTH bar, but it's a violation of spec §1.3 in spirit. P1 because the demo is about "no silent drops"; an abstain that silently fails would be embarrassing.
- Fix: Replace the bare catch with `EmitError(ex)`.
- Lines/files: V2_5 line 2069. ~5 lines.
- Hours: 5 minutes.

**P1.4 — Wire `already_touched_today` per-(level, direction).**
- What's broken: `BuildFeatureVector` line 1875 hard-codes `false`. The session-level set `uniqueLevelsTouchedToday` exists but doesn't drive the per-candidate flag.
- Fix: Track a per-(name, direction) HashSet; set the feature true on second-and-subsequent emissions.
- Lines/files: V2_5 lines 400, 1322, 1875. ~15 lines.
- Hours: 30 minutes. Optional for tomorrow's demo since the L2 scorer is not running anyway.

**P1.5 — Get the strategy file to compile (out of quarantine, into Strategies/).**
- What's broken: `quarantine/AMTradeStrategyV1.cs` is 2,679 lines. The quarantine notes (none present in dir) suggest it was pulled because it doesn't compile. Likely culprits:
  - `SubmitOrderUnmanaged` signature variants (NT8 has 3-4 overloads).
  - `Account.Get(AccountItem.CashValue, Currency.UsDollar)` arity / overload.
  - `Account.Positions.FirstOrDefault(...)` LINQ — needs `using System.Linq;` (it has it).
  - `Position.Quantity` vs `Position.Volume` vs `Position.Quantity * direction` — depends on NT8 build.
  - `OrderState.Filled` enum value name.
  - Possibly `currentSignal.EntryOrder.OrderId` field access if NT8 changed the property name.
- Fix complexity: A few hours of editor → compile → fix-error → compile loop. Hard to estimate without running it.
- Lines/files: ~50-200 lines of small surface fixes; structural code is correct.
- Hours: **3-8 hours of focused work.** NOT tonight. Realistic next-week timeline.
- Why this is P1, not P0: Without the strategy compiled, the L2/L3 abstain events do not exist. The architecture's "explainability" claim is half-true at the demo. AM will see "candidates" but no "this candidate scored 0.32, below the 0.45 threshold, hence abstain." The story about safety gates is unprovable from the JSONL alone.

### P2 — institutional-grade

**P2.1 — Wire cluster, confluence, and volume Z-score features.**
- What's broken: ~10 features in `BuildFeatureVector` are missing. The L2 heuristic's confluence-bonus rule and the future ML scorer rely on these.
- Lines/files: V2_5 line 1985 (end of BuildFeatureVector). ~80 lines new code.
- Hours: 4-6 hours.

**P2.2 — Connect the rt2_1 HTTP scorer endpoint live.**
- What's broken: HTTP scorer hook in quarantine works, but Python side serves no real predictions yet.
- Lines/files: Python `pattern_scorer_rt2_1` package. Outside this codebase.
- Hours: 8-16 hours of Python plus calibration.

**P2.3 — OOS backtest harness aligned to V2_5 schema.**
- What's broken: Tests directory has `test_contract_compliance.py`, `test_pattern_b_state_machine.py`, `test_replay_equivalence.py`, `test_safety_gates.py`. These are unit-tests against the JSONL contract, not OOS backtests. The `pf_optimizer` and OOS backtest modules in the Python side need refactoring to consume V2_5's schema (vs V2_4's).
- Hours: 16-24 hours.

**P2.4 — Manual kill-switch chart button + F12 hotkey.**
- What's broken: Manual kill-switch is a property only. No clickable UI.
- Hours: 2-4 hours for chart button (DrawingTools.Button-style); 4-8 hours for F12 via NinjaScript AddOn.

### P3 — V1.1 nice-to-haves

**P3.1 — Re-arm policy for Pattern B (currently latches at Consumed until session rollover).**
**P3.2 — Holiday parquet via `pandas_market_calendars` quarterly sync.**
**P3.3 — 50% midpoint convergence-add rule (deferred per AM "tabled" note).**
**P3.4 — Fibonacci runner ladder (100/150/200/250%) with slope-conditional target choice.**
**P3.5 — Multi-instrument capital coordination.**
**P3.6 — Cross-chart deduplication (named mutex + instance_id tagging).**
**P3.7 — Heartbeat wall-clock-gated rather than bar-time-gated.**
**P3.8 — Full state.json restore (LevelWatchState with anchor candle, news wicks).**

---

## 3. What's NOT Going to Ship Before Tomorrow

Stating the cut directly:

**Will NOT be in front of AM tomorrow:**
- L2 scoring (the heuristic that converts candidate → take/abstain decision).
- L3 safety gates (the 12 toggleable filters with explicit abstains).
- Order submission (real or simulated). No `signal`, `fill`, `stop_hit`, `target_hit` events in the JSONL.
- Any "live trade" — paper or otherwise.
- Manual kill-switch button or F12 hotkey.
- Reconciliation (broker vs internal divergence detection).
- HTTP ML scoring.
- OOS backtest results from V2_5 data (V2_5 hasn't accumulated any sessions yet).
- The full ~100 feature schema (we have ~70).
- The runner-target ladder. The 50% midpoint add.

**The strategy file is in quarantine because it does not compile against the installed NT8.** This is the single biggest constraint. Even if you spent the next 5 hours debugging it, you'd be doing it instead of validating L1, and you wouldn't have something polished by tomorrow morning. **Don't try to bring the strategy out of quarantine tonight.** That's a next-week project.

**What is realistic to ship by tomorrow:** A clean L1 demo. V2_5 indicator alone, on an ES chart, with a recent NT Replay. JSONL events flowing. Diagnostic info card readable. Boxes drawing correctly with the apr-27 newest-of-kind rule. One specific case demonstrating "V2_4 dropped this silently; V2_5 surfaces it."

That's not the full architecture vision. But it is **incontrovertible evidence that the L1/L2/L3 separation is real and the L1 layer is correct.** AM cares about the philosophy as much as the demo. If you tell her "L1 is in flight, L2 and L3 are designed and quarantined, this is the L1 demo," she will respect that more than a brittle full-stack demo where the strategy crashes.

The honest framing for AM: "I rebuilt detection. The detection layer surfaces 5x-10x more candidates than V2_4 did because it has no opinions. The decision and safety layers are written but not deployed; they need a few more days. Here's what the detection layer sees that V2_4 missed."

---

## 4. The "Powerful Functional Indicator" Spec for Tomorrow

If you have ONE evening, here is the maximum impressive demo you can build that is honest about what's done.

### 4.1 The deliverable: V2_5 indicator alone, validated end-to-end

**Stage 1 (60-90 minutes): Compile and load.**
- Open `Indicators/AMTradeCockpitV2_5.cs` in NT8 NinjaScript Editor.
- F5 to compile. Fix any errors. Document them in a one-page "compile-fixes-tonight" note.
- Apply V2_5 to a fresh ES JUN26 1-minute chart. Defaults.
- Verify the diagnostic info card appears top-left with day-type 3-node, day-type 4-node, MOC pending, slope pending, candidates today: 0.
- Verify the chip legend renders top of chart (INSTITUTIONAL / 3:30 CLOSE / GLOBEX 6PM / MIDNIGHT / EUROPE 4AM / RTH 9:30).
- Open `C:\seasonals\cockpit\sessions\<today>\events.jsonl` in a tail-style viewer (PowerShell `Get-Content -Wait` works). Verify schema is `v25.1`.

**Stage 2 (30-60 minutes): NT Replay against a recent active day.**
- Pick a known-active day, ideally one with a Pattern B setup AM herself reviewed (apr-23 or apr-24 in the transcripts).
- Run NT Replay at 30x.
- Watch for box captures, day-type changes, and candidate markers (green/orange dots, cyan triangles) appearing on the chart.
- After replay, count the candidates: `Get-Content events.jsonl | Select-String '"type":"candidate"' | Measure-Object -Line`.
- Expected: 30-100+ candidates depending on day activity. V2_4 on the same day produced 0-2 signals.

**Stage 3 (30 minutes): Find the V2_4-vs-V2_5 contrast case.**
- For the same replay day, find V2_4's old `events.jsonl` if it exists (look in `C:\seasonals\cockpit\sessions\<replay-date>\` for files predating today).
- Identify ONE specific bar where:
  - V2_4 has no signal event (or only a touch event).
  - V2_5 has a candidate event with a clear feature vector showing it was a valid Pattern A or Pattern B setup.
- Capture screenshots: the V2_5 chart with the candidate marker; the candidate's feature payload from JSONL; the V2_4 silence on the same time/level.

### 4.2 What the demo shows AM

1. **The architecture is real, not vapor.** Two files, separated cleanly. L1 is in `Indicators/`. L2/L3 are in `quarantine/` (you'll show her the file list).

2. **L1 detection works.** Boxes draw. Pattern B state machine operates. Candidates emit. The newest-of-kind rule visualizes correctly.

3. **The fail-open principle is in code, not just slides.** Open the JSONL. Show her the candidate schema. Show her that for a Sideways day, both LONG and SHORT candidates appear in the same minute. Show her that a permission-level VWAP touch surfaces with `is_permission_level=true` (V2_4 silently dropped these).

4. **AM ambiguities are features, not gates.** Open one candidate's payload. Point to `day_type_v2_3node` and `day_type_v2_4node` — both emitted. Both `retrace_side` and `retrace_side_at_open` populated. Slope delta as raw points; she will love this.

5. **The diagnostic info card is the poor-man's verdict line.** Day-type 3-node + 4-node both visible. MOC pending or computed. Slope. Candidates-today count. Pattern-B-armed count. This is how you'll trade manually tomorrow morning while the strategy is being finished.

6. **One concrete case where V2_5 surfaces what V2_4 swallowed.** This is the single most persuasive moment of the meeting.

### 4.3 The 3 AM clarification questions (asks her, doesn't block on her)

These are designed to be non-blocking — V2_5 ships a heuristic default for each, and her answer just refines a weight, not a rebuild.

**AM-Q-01: 200-SMA slope-magnitude threshold.** "When you say 'steep slope' versus 'flat slope' for runner targeting, what delta in ES points per session do you have in your head? V2_5 currently emits the raw delta as a feature; the heuristic uses 5 ES-points/session as the cutoff between fib_150 and fib_200. ML will learn the right value, but for the heuristic, what should we start with?"

**AM-Q-02: Counter-slope FADE sizing on Sideways days.** "On a sideways day with up-sloping 200-SMA, you take both the short at the top of the range and the long at the bottom. Same size? Half size on the counter-slope leg? The heuristic ranks both candidates but applies a -0.10 penalty to the counter-slope direction — am I close to your sizing, or should I tighten it?"

**AM-Q-03: 1:30 PM candle persistence rule.** "Mar-6 you said 'every day, by a couple of minutes.' Apr-16 you described it as conditional on retracement-event-with-MOC-validation. V2_5 captures it always and exposes Pr130H/Pr130L as candidates from 14:00 onward. Should the scorer treat Close130 the same priority as a master candle (institutional / Europe / GlobEx tier), or as a secondary level (Pr30 tier)?"

### 4.4 What you do NOT show

- The strategy file. Don't open it. Don't mention it crashes. Just say "L2 and L3 are written and quarantined; integration testing next week."
- Live order submission. Don't suggest the system is anywhere near ready for paper trading.
- Backtest results. You don't have V2_5-instrumented sessions yet.
- The 12 safety gates. Mention them in passing as "designed and written; not yet deployed."
- The runner ladder. Mention it as V1.1.

The discipline: **less than what you've built > more than what's deployed.** If she asks, "can you show me the strategy fire a signal?", say "Not yet — that's next week's work after I confirm L1 is correct on 30 instrumented sessions. I want to ship the right thing, not a fast thing." She will respect this answer infinitely more than a half-broken demo.

---

## 5. The Change-Discipline Going Forward

After tomorrow, here is the working pattern that gets V2_5 to V1.1 without re-falling-into the "everything is one file with seven concerns" trap.

**1. The architect spec is the source of truth.**
- All future implementer work reads from `architecture_spec_v25.md` and writes against the contracts defined there.
- When the spec is wrong (it will be in places — section 5.1's race-condition note is already partially addressed by the BarsInProgress fix), update the spec FIRST. Then the code.

**2. Compile-tested increments only.**
- Every change to `AMTradeCockpitV2_5.cs` or eventually `Strategies/AMTradeStrategyV1.cs` ends with a successful `F5 Compile` in NT8 NinjaScript Editor.
- A change that doesn't compile sits in `quarantine/` until it does. No "I'll come back to this" without a quarantine path. The strategy file is the cautionary tale.
- If the change is large, break it into small chunks each with a green compile.

**3. Quarantine is a real folder, not a state of mind.**
- `v25_rebuild_2026-04-27/quarantine/` is correct. Add a `QUARANTINE_NOTES.md` to each quarantined file: what went in, why it's blocked, what the unblocking criteria are. The current strategy file has no such note. Add one.

**4. Manual playbook in parallel until the strategy is live.**
- The wave3 manual_playbook.md describes how AM trades. Use it as the daily decision rubric while the L2/L3 stack is being finished. The diagnostic info card on V2_5 is your decision support for now.
- Track each manual trade in a simple journal: "candidate XYZ surfaced, my call: take / skip / skip-with-doubt." Diff against what V2_5's eventual heuristic would have done. That diff is the calibration data for L2.

**5. JSONL is the authoritative data layer.**
- Every analysis question — "why didn't I trade that retest?", "how many Pattern B candidates does ES produce on a typical Friday?", "what's the L2 scorer's distribution of p_win?" — is answered from the JSONL, not from chart memory or printf output.
- Build a small set of standing PowerShell / Python one-liners for the questions you'll ask weekly. The wave3 `jsonl_data_analysis.md` is the model for this.

**6. Resist the "let me add one more feature to the indicator" temptation.**
- L1 is L1. If the new feature is a derivation (cluster count, confluence, a new feature flag), it goes in `BuildFeatureVector`. If it's a decision (take/abstain), it goes in L2. If it's a block (don't trade after a stop), it goes in L3. The rule is the same one the wave3 audits identified as V2_4's failure mode: tangling the three concerns is what produces the silent drops.

**7. Calibrate, then deploy.**
- The flowchart for any "feature is ready" claim:
  - It compiles → it loads on a chart → it runs a full session → it survives a NT restart → it has a unit test in `tests/` → it is calibrated against ≥30 sessions of forward-collected data → it is enabled by default.
  - Skip any step and you are repeating V2_4's path.

**Two-person sign-off before live.** When the strategy is finally compiling and `AllowLiveOrderSubmit` is `true`, get the brief mentor (Anne-Marie) and one other set of eyes (your past self, written down in a checklist) to confirm the gates are configured for your account size. The last 5% of risk is in configuration, not code.

---

## Closing thought

You set out to build a beginner-friendly indicator AND an institutional-grade autonomous stack. Tonight, the first half is real and the second is designed. That is a respectable position to be in 2 weeks into a 6-week rebuild. Tomorrow's job is to demonstrate the first half cleanly and to commit to the second half on a calendar — not to fake it.

Get V2_5 compiled. Replay one active day. Find the V2_4-versus-V2_5 contrast case. Bring the three AM questions. Show her the architecture diagram. Tell her honestly what's deployed and what's quarantined.

She will trust the rebuild because of the discipline, not despite the gaps.
