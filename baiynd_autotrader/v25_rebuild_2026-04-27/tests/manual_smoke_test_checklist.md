# V2_5 Manual Smoke Test Checklist

**Version:** V2_5 architecture rebuild  
**Date template:** Fill in actual date when running  
**Tester:** Afshin  
**Purpose:** Confirm V2_5 compiles, loads, and behaves correctly before sim-trade promotion.

---

## How to use this checklist

Work through each stage in order. Each stage has a PASS/FAIL gate — do not proceed to the next stage until the current stage passes. Note results and timestamps as you go. If anything fails, stop and record the full error message.

**Before starting:** Ensure you have a recent build of both files:
- `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMTradeCockpitV2_5.cs`
- `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Strategies\AMTradeStrategyV1.cs`

---

## Stage 1 — Compile

**Goal:** Both files compile with no errors.

- [ ] Open NinjaTrader 8.
- [ ] Go to **Tools → NinjaScript Editor**.
- [ ] Click **Compile** (or press F5).
- [ ] **Verify zero compile errors.**  
      Record any output here: `_________________________`
- [ ] Acceptable warnings (these are OK to ignore):
  - `CS0169` — unused private field warnings on internal state
  - `CS0414` — field assigned but value never used
  - `CS0618` — obsolete member usage from NT8 internal APIs
  - Any warning that says "unreachable code" in a `catch` block
- [ ] **Any error message → STOP. Do not proceed.** Record full error:  
      `_________________________`
- [ ] Go to **Control Center → Indicators** tab. Verify both of the following appear:
  - [ ] `AMTradeCockpit` (the V2_4 indicator — should still be there)
  - [ ] `AMTradeCockpitV2_5` (the new indicator)
- [ ] Go to **Control Center → Strategies** tab. Verify:
  - [ ] `AMTradeStrategyV1` appears in the list.

**Stage 1 result:** [ ] PASS  [ ] FAIL  
Notes: `_________________________`

---

## Stage 2 — Load V2_5 Indicator Alone on a Chart

**Goal:** V2_5 draws correctly and writes JSONL without the strategy loaded.

- [ ] Open a new chart: **ES JUN26, 30-minute timeframe, ~30 days of data**.
- [ ] Apply indicator: right-click chart → **Indicators** → add **AMTradeCockpitV2_5**.
- [ ] Use default parameters. Click OK.
- [ ] **Wait 30 seconds** for `State.DataLoaded` to complete (watch NT Output window).
- [ ] Verify boxes draw on the chart:
  - [ ] Close330 box (prior 3:30 PM candle — appears on prior days)
  - [ ] GlobEx box (6 PM globex candle)
  - [ ] Europe box (4 AM Europe open candle)
  - [ ] RTH box (9:30 AM candle — if RTH data available)
  - [ ] Note: some boxes may not appear if the bar is in the future (today).
- [ ] Verify **info card panel** renders in the top-left corner of the chart.  
  - [ ] Panel shows day_type (Sideways/LongTrend/etc.)
  - [ ] Panel shows MOC state (Green/Orange/Gray/Pending)
  - [ ] Panel shows slope status
  - [ ] Panel shows candidate count
- [ ] Open **NT Output window** (Control Center → Output). Verify:
  - [ ] Log line containing `AMTradeCockpit V2_5 initialized` (or similar startup message)
  - [ ] No `NullReferenceException` or `IndexOutOfRangeException` in the log
- [ ] Check JSONL output:
  - [ ] Navigate to `C:\seasonals\cockpit\sessions\<today's date>\`
  - [ ] Verify file `events.jsonl` exists and is being written to.
  - [ ] Open the file in a text editor. Verify it contains valid JSON lines.
  - [ ] Verify at least one `box_capture` event is present.
  - [ ] Verify at least one `bar_close` event is present.
  - [ ] Verify the `schema_version` field is `"v25.1"` (or matches current spec version).

**Stage 2 result:** [ ] PASS  [ ] FAIL  
Notes: `_________________________`

---

## Stage 3 — Historical Replay and Contract Compliance

**Goal:** V2_5 passes the prime-directive contract compliance test on replay data.

- [ ] In NT8, open the **Replay engine** (Control Center → Replay, or the replay toolbar on the chart).
- [ ] Select instrument: **ES JUN26** (or nearest front-month).
- [ ] Select date: **April 23, 2026** (or the most recent date with known activity — use a day you know had price action near levels).
- [ ] Set replay speed: 1x or fastest (for Historical mode validation, speed doesn't matter).
- [ ] **Run the replay through the full session** (9:30 AM to 3:00 PM ET minimum).
- [ ] After replay completes, confirm the session JSONL was written:
  - [ ] `C:\seasonals\cockpit\sessions\2026-04-23\events.jsonl` exists and is non-empty.
- [ ] Run the contract compliance test:
  ```
  cd C:\seasonals\baiynd_autotrader\v25_rebuild_2026-04-27\tests
  python test_contract_compliance.py --date 2026-04-23
  ```
- [ ] **Expected result: `[PASS]` with zero orphan candidates.**
- [ ] If orphan candidates are found, note the candidate_ids:  
      `_________________________`
- [ ] Run the feature-completeness spot check (manual): open `events.jsonl`, find any `candidate` event, and verify:
  - [ ] `features` dict is present and non-empty.
  - [ ] No field value is `NaN` (null is OK; NaN is not — see INV-L1-3).
  - [ ] `candidate_id` follows format: `<INSTR>_<DATE>_<TIME>_<LEVELNAME>_<DIR>_<SEQ>`.

**Stage 3 result:** [ ] PASS  [ ] FAIL  
Notes: `_________________________`

---

## Stage 4 — Load Strategy on Top of V2_5

**Goal:** AMTradeStrategyV1 loads, hosts V2_5, and writes its own JSONL.

- [ ] Apply **AMTradeStrategyV1** to the same or a new ES JUN26 chart.
- [ ] In strategy properties, confirm:
  - [ ] **L3 safety gates appear as toggleable parameters.** You should see:
    - `EnableRthWindowGate` (bool, default true)
    - `EnableDailyLossKill` (bool, default true)
    - `MaxDailyLossDollars` (double, default 500)
    - `EnableCooldownAfterStop` (bool, default true)
    - `CooldownMinutes` (int, default 30)
    - `EnableMaxSignalsPerDay` (bool, default true)
    - `MaxSignalsPerDay` (int, default 5)
    - *(and remaining gates per spec §2.3)*
  - [ ] `ScorerMode` parameter appears (Heuristic default).
  - [ ] `MinWinProbability`, `MinExpectedR`, `MinConfidence` appear.
- [ ] Click **OK** to apply the strategy with defaults.
- [ ] In NT Output, verify:
  - [ ] `AMTradeStrategyV1 initialized` log line (or similar).
  - [ ] No `NullReferenceException`.
- [ ] **Verify no double-instance issue:** The strategy should host V2_5 internally.
  - [ ] If V2_5 indicator is also manually on the same chart: check NT Output for warnings about duplicate indicator instances. If present, remove the manually-added V2_5 from the chart — the strategy provides it.
- [ ] Check JSONL output:
  - [ ] `C:\seasonals\cockpit\sessions\<today>\strategy_events.jsonl` is being written.
  - [ ] Open it and verify valid JSON lines with `schema_version`.

**Stage 4 result:** [ ] PASS  [ ] FAIL  
Notes: `_________________________`

---

## Stage 5 — Smoke Test L2 Decisioning

**Goal:** L2 produces signals or abstains (not silence) for candidates.

- [ ] Run a Historical Replay of a recent active day (e.g., April 23, 2026) with **AMTradeStrategyV1** active.
- [ ] After replay, run contract compliance over BOTH JSONL files:
  ```
  python test_contract_compliance.py --date 2026-04-23
  ```
  *(The script automatically picks up both `events.jsonl` and `strategy_events.jsonl` from the same session directory.)*
- [ ] **Expected: zero orphan candidates across both files.**
- [ ] Manually inspect `strategy_events.jsonl` for:
  - [ ] At least some `abstain` events with `layer="L2"` or `layer="L3"`.
  - [ ] If zero signals and zero abstains: **FAIL** — L2 is not receiving candidates from L1.
  - [ ] If signals exist: confirm signal has `candidate_id`, `direction`, `entry_price`, `scorer_decision`.
- [ ] Check L3 gate behavior manually:
  - [ ] Find an `abstain` with `layer="L3"`. Verify `gate_name` is one of the 12 known gates.
  - [ ] Verify `recoverable_until_time` is present.
- [ ] Run safety gate schema validation:
  ```
  python test_safety_gates.py --jsonl C:\seasonals\cockpit\sessions\2026-04-23\strategy_events.jsonl
  ```
  - [ ] Expected: `[PASS]` (zero schema violations, even if some gates not yet triggered).

**Stage 5 result:** [ ] PASS  [ ] FAIL  
Notes: `_________________________`

---

## Stage 6 — Side-by-Side V2_4 vs V2_5

**Goal:** Both indicators coexist on the same chart without interfering with each other.

- [ ] Apply **both** indicators to the same chart:
  - [ ] `AMTradeCockpit` (V2_4 — the original indicator)
  - [ ] `AMTradeCockpitV2_5` (new)
- [ ] Wait for both to load (observe NT Output — no errors from either).
- [ ] Compare visually:
  - [ ] V2_4 still shows its original verdict/signal line and staging card UI.
  - [ ] V2_5 shows its new info card and diagnostic panel (they should be distinct UI elements).
  - [ ] Both draw boxes. If box colors overlap, that is acceptable — the boxes should agree on level prices from the same underlying data.
- [ ] Confirm no interference in NT Output:
  - [ ] No `NullReferenceException` referencing the other indicator.
  - [ ] Both emit their respective JSONL files independently.
- [ ] Run compile again (F5 in NinjaScript Editor) with both files open. Confirm no namespace conflicts.

**Stage 6 result:** [ ] PASS  [ ] FAIL  
Notes: `_________________________`

---

## Go / No-Go Summary

Fill in after completing all stages:

| Stage | Description | Result | Blocker? |
|-------|-------------|--------|----------|
| 1 | Compile | | Yes — must pass |
| 2 | V2_5 indicator alone | | Yes — must pass |
| 3 | Replay + contract compliance | | Yes — must pass |
| 4 | Strategy loads | | Yes — must pass |
| 5 | L2 decisioning smoke test | | Yes — must pass |
| 6 | V2_4 / V2_5 coexistence | | Recommended |

**Sim-trade readiness:** Stages 1–5 must all be PASS before sim-trading.

---

## Known acceptable discrepancies

The following are not bugs and do not require a STOP:

1. **V2_4 boxes extend past the right edge of the chart.** V2_4 does this for its staging card. V2_5 does not. This is visual-only.
2. **V2_5 surfaces many more candidates than V2_4 produced signals.** This is by design (fail-open architecture). V2_4 silently dropped most candidates; V2_5 surfaces them all. Expect hundreds or thousands of candidates per session vs V2_4's near-zero signals.
3. **`strategy_events.jsonl` contains many L2 `abstain` events with `reason="scorer_min_p_win"`.** This means L2's heuristic scorer is rejecting most candidates. This is expected in V1 — the heuristic is conservative. It is more important that the abstains are being logged than that signals are being produced.
4. **`events.jsonl` contains `warning` events for missing SMA200 history at the start of a replay.** The 200-bar warmup period means the slope is unavailable for the first ~200 1-minute bars. This is expected and logged correctly.
5. **Pattern B `Armed` state carries over from a prior session via `state.json`.** This is intentional. The state machine persists across restarts. If a level was breached and armed before session end, it stays armed until consumed or invalidated.

---

## If a stage fails

1. **Stage 1 compile error:** Copy the full error from NinjaScript Editor Output. Check that the .cs file was saved. Try a clean compile (delete NinjaTrader's `bin` folder compile cache if necessary).
2. **Stage 2 / boxes don't draw:** Check NT Output for exceptions. Verify the session date has data loaded.
3. **Stage 3 orphan candidates:** Run `python test_contract_compliance.py --date <date> --verbose` for details. Look for the orphan `candidate_id` in `events.jsonl` and verify there is no corresponding entry in `strategy_events.jsonl`.
4. **Stage 4 strategy fails to load:** Check NT Output for "strategy not enabled" or parameter serialization errors. Try removing and re-adding the strategy.
5. **Stage 5 zero signals and zero abstains:** The `OnCandidate` event subscription between L1 and L2 may not be wired. Check that `cockpit.OnCandidate += HandleCandidate` runs in `OnStateChange(State.DataLoaded)`.
