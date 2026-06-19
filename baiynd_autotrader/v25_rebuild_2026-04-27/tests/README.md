# V2_5 Test Suite — README

**Architecture ref:** `architecture_spec_v25.md` Section 9 (Test Strategy)  
**Created:** 2026-04-27  
**Python:** 3.x stdlib only — no third-party dependencies required.

---

## Overview

V2_5 cannot be unit-tested from Python in the traditional sense because NinjaTrader 8 does not expose a programmatic API to Python. The test suite therefore targets what IS available from Python: the JSONL event stream that V2_5 writes to disk during every Historical Replay or live session.

The core contract: every L1 `candidate` event must produce either a `signal` or an `abstain` event downstream. No silent drops. The test suite validates this contract and the schemas of all related event types.

---

## Files

| File | Lines | What it validates |
|------|-------|--------------------|
| `test_contract_compliance.py` | ~330 | Prime-directive contract: every candidate has a signal or abstain. Schema validation on all three event types. **This is the most critical test.** |
| `test_replay_equivalence.py` | ~280 | V2_4 → V2_5 recall: V2_5 surfaces every candidate that V2_4 historically signalled. |
| `test_pattern_b_state_machine.py` | ~350 | Pattern B state machine transitions (Untouched→Breached→Armed→Consumed/Invalidated). Includes a `--spec` mode that prints the scenario reference. |
| `test_safety_gates.py` | ~360 | All 12 L3 safety gates: expected abstain events, schema validation, coverage summary. Includes `--spec` mode. |
| `manual_smoke_test_checklist.md` | ~180 | Step-by-step manual checklist for compile, load, render, JSONL output, side-by-side coexistence. |
| `README.md` | (this file) | Suite overview, how to run, failure guidance. |

---

## How to Run

### Prerequisites

1. Python 3.8+ installed and on PATH.
2. V2_5 has been run in NT8 Historical Replay mode at least once, so JSONL files exist.
3. Default JSONL location: `C:\seasonals\cockpit\sessions\YYYY-MM-DD\`

### Quickstart — validate a single session

```cmd
cd C:\seasonals\baiynd_autotrader\v25_rebuild_2026-04-27\tests

:: Contract compliance (most important test)
python test_contract_compliance.py --date 2026-04-23

:: Replay equivalence (requires V2_4 historical JSONL in same folder)
python test_replay_equivalence.py --v24-root "C:\seasonals\cockpit\sessions" --v25-root "C:\seasonals\cockpit\sessions"

:: Pattern B state machine
python test_pattern_b_state_machine.py --jsonl "C:\seasonals\cockpit\sessions\2026-04-23\events.jsonl"

:: Safety gate schema validation
python test_safety_gates.py --jsonl "C:\seasonals\cockpit\sessions\2026-04-23\strategy_events.jsonl"
```

### Validate a date range

```cmd
python test_contract_compliance.py --start 2026-04-01 --end 2026-04-27
```

### Print specs (no JSONL needed)

```cmd
:: Print Pattern B scenarios
python test_pattern_b_state_machine.py --spec

:: Print all 12 safety gate scenarios
python test_safety_gates.py --spec
```

### Getting help for any test

```cmd
python test_contract_compliance.py --help
python test_replay_equivalence.py --help
python test_pattern_b_state_machine.py --help
python test_safety_gates.py --help
```

---

## Test Status: Runnable Now vs Spec Only

| Test | Runnable Now? | Requires |
|------|--------------|---------|
| `test_contract_compliance.py` | Yes — as soon as any replay produces JSONL | `events.jsonl` from V2_5 + (optional) `strategy_events.jsonl` from V2_5 strategy |
| `test_replay_equivalence.py` | Partially — V2_4 JSONL may already exist | V2_4 historical `events.jsonl` containing `signal` events + V2_5 replay output |
| `test_pattern_b_state_machine.py --spec` | Yes — no JSONL needed | Nothing |
| `test_pattern_b_state_machine.py --jsonl` | After first replay | `events.jsonl` from V2_5 with Pattern B activity |
| `test_safety_gates.py --spec` | Yes — no JSONL needed | Nothing |
| `test_safety_gates.py --jsonl` | After running strategy + triggering each gate | `strategy_events.jsonl` with L3 abstain events |
| `manual_smoke_test_checklist.md` | Anytime | NT8 running, V2_5 compiled |

---

## Contract Claims Validated vs Manual

### Automated (JSONL-based):
- Every `candidate` has a downstream `signal` or `abstain` (zero silent drops). — `test_contract_compliance.py`
- `candidate` schema: all required fields present, no NaN, valid direction and pattern_type. — `test_contract_compliance.py`
- `signal` schema: signal_id, candidate_id, direction, entry_price, scorer_decision all present. — `test_contract_compliance.py`
- `abstain` schema: layer in {L1,L2,L3}, gate_name non-null, reason non-null. — `test_contract_compliance.py`
- L3 abstain schema: recoverable_until_time present. — `test_safety_gates.py`
- Pattern B state machine transitions follow the valid-transition table. — `test_pattern_b_state_machine.py`
- Consumed state paired with a Pattern B candidate event. — `test_pattern_b_state_machine.py`
- V2_5 surfaces every candidate V2_4 historically signalled (100% recall). — `test_replay_equivalence.py`
- 12 L3 gate names match the spec. — `test_safety_gates.py`

### Manual only (cannot be automated from Python):
- NT8 compiles without errors (Stage 1).
- Boxes draw correctly at the right prices (Stage 2).
- Info card panel renders (Stage 2).
- L3 gate parameters appear in strategy Properties dialog (Stage 4).
- V2_4 and V2_5 coexist without interfering (Stage 6).
- `OnCandidate` event wire-up (L1→L2 in-process subscription) works — only verifiable by observing both candidates AND strategy abstains/signals in the JSONL together.
- State persistence after NT8 restart — manual verify: restart mid-session, check state.json values restored.

---

## Critical Tests (Must PASS Before Sim-Trade)

In order of priority:

1. **Stage 1 compile** (manual) — zero errors. Non-negotiable.
2. **`test_contract_compliance.py` on a full replay session** — zero orphan candidates. This is the prime-directive contract. If this fails, no sim-trade.
3. **Stage 5 smoke test** (manual + automated) — L2 is producing abstains (not silence). Verify `strategy_events.jsonl` has content.
4. **`test_replay_equivalence.py`** — 100% recall on the 2 known V2_4 historical signals.

Tests 3–4 (Pattern B state machine, safety gate scenarios) can be run iteratively during sim-trade without blocking the go-decision, as long as tests 1–4 above pass.

---

## If a Test Fails

### `test_contract_compliance.py` reports orphan candidates

An orphan candidate is the most serious failure. It means L1 emitted a candidate that L2/L3 never processed — a silent drop of the exact kind V2_5 was designed to prevent.

Diagnosis steps:
1. Note the orphan `candidate_id`.
2. Find it in `events.jsonl`. Note the `bar_time` and `level_name`.
3. Open `strategy_events.jsonl`. Search for that `candidate_id`. If not present: the `OnCandidate` event subscription between L1 and L2 may be broken. Check `cockpit.OnCandidate += HandleCandidate` in the strategy's `OnStateChange`.
4. If the strategy file is missing entirely: the strategy wasn't running during this replay session.

### `test_replay_equivalence.py` reports a missed V2_4 signal

V2_5 failed to surface a candidate that V2_4 took as a signal. This is a regression — V2_5 is detecting *less* than V2_4 for at least this level.

Diagnosis steps:
1. Note the missed signal's `session_date`, `bar_time`, `level_name`.
2. Check V2_5's `events.jsonl` for that session: is the level present at all? Is it present at a nearby time?
3. Compare the level name in V2_4 vs V2_5 — naming convention may have changed.
4. Confirm the replay covered that date and that date's `events.jsonl` was produced.

### `test_pattern_b_state_machine.py` reports an invalid transition

A transition like `Untouched → Armed` (skipping `Breached`) indicates a state machine bug in L1. Escalate to L1 implementer with the specific `level_name`, `bar_time`, and transition observed.

### `test_safety_gates.py` shows a gate never observed

This is not a test failure — it means you haven't yet run the scenario that triggers that gate. Use `python test_safety_gates.py --spec` to read the setup steps, then reproduce the trigger in replay and re-run.

---

## Open Issues (for synthesis agent)

1. **V2_4 signal JSONL format:** V2_4 may use different field names than the V2_5 schema (`level` vs `level_name`, `side` vs `direction`). The equivalence test has fallback field parsing but may need refinement once V2_4's actual JSONL schema is confirmed.
2. **`test_safety_gates.py` gate 8 (margin):** Margin calculation is instrument-specific and account-specific. The gate validation cannot numerically verify the margin threshold from JSONL alone — it can only check that an `abstain` fires. A more rigorous test would require access to account state at the time of the abstain.
3. **Pattern B scenario synthetic data:** The scenarios in `test_pattern_b_state_machine.py --spec` describe bar sequences but cannot be automatically fed into NT8. A future enhancement would generate a `.csv` or NT8-compatible replay file from these specs to enable fully automated Pattern B testing.
4. **Feature vector completeness (INV-L1-3):** The contract compliance test checks for NaN but does not verify that every field in the spec §3.3 feature list is present. A future enhancement would cross-reference the spec's feature list against the actual keys in each `candidate.features` dict.
