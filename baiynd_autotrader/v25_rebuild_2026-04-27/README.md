# V2_5 Rebuild — 2026-04-27

## What this folder contains

This folder is the design home for the AMTradeCockpit V2_5 rebuild. It contains:

- **`architecture_spec_v25.md`** — the master architecture specification. All V2_5 implementer agents wrote code against this document. It defines the L1/L2/L3 layer contracts, event schemas, NinjaScript-specific design choices, detection spec, scoring spec, safety spec, test strategy, migration path, and AM ambiguity handling. Read time: 60–90 minutes. Reference it section-by-section for any V2_5 work.

- **`tests/`** — test suite for contract compliance validation. The central test: replay 6 months of JSONL through L1+L2+L3 and assert that every `candidate` event is followed by either a `signal` or an `abstain`. Zero violations allowed. See `tests/manual_smoke_test_checklist.md` for pre-live validation steps.

- **This README** — orientation and cross-reference guide.

## Relationship to strategy_review_2026-04-27

The `strategy_review_2026-04-27` folder (`C:\seasonals\baiynd_autotrader\strategy_review_2026-04-27\`) contains the 22-agent review that diagnosed V2_4's failures and produced the design brief for V2_5. Key files:

- `wave2_audit/v24_code_audit.md` — line-by-line audit of V2_4; identified silent drops, dead code paths, and conflated layers.
- `wave3_synthesis/gap_to_am.md` — gap analysis between V2_4's behavior and AM's actual method.
- `wave3_synthesis/failure_modes.md` — classified failure modes, including the 0.27% conversion rate finding.
- `strategy_synthesis.md` and `improvement_roadmap.md` — the prioritized brief that became this architecture spec.

The relationship is: the review produced the diagnosis; this folder contains the architecture that addresses it. Do not modify the review folder — it is the historical record.

## Relationship to the V2_5 indicator and strategy files

The implementation lives in the NinjaTrader 8 Custom directory:

- **L1 (detection):** `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMTradeCockpitV2_5.cs`
- **L2/L3 (scoring + safety):** `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Strategies\AMTradeStrategyV1.cs`

V2_4 (`AMTradeCockpitV2_4.cs`) is retained in the same Indicators directory as legacy/fallback. It is untouched. Do not modify it.

The spec in this folder is the canonical contract. If the code diverges from the spec, the spec is authoritative unless there is a documented reason for the divergence.

## How to validate the rebuild

**Before promoting from sim to live, the following must pass:**

1. **Contract compliance test** (see `architecture_spec_v25.md` §9 and the test harness in `tests/`):
   - Replay 6 months of V2_4 JSONL through V2_5.
   - Assert: every `candidate` event is followed by either a `signal` or an `abstain` for the same candidate identity.
   - Assert: V2_5 emits a `candidate` for 100% of the levels that V2_4 actually signaled (recall check).
   - Assert: zero NaN values in any `features` struct across 1,000+ candidate events.
   - Assert: two identical replay runs produce identical event sequences (determinism).

2. **Manual smoke test checklist** (`tests/manual_smoke_test_checklist.md`):
   - Confirm box capture events fire at the correct master-candle times.
   - Confirm Pattern B state machine transitions are logged.
   - Confirm L3 abstain events fire and are visible in JSONL when a safety gate triggers.
   - Confirm heuristic scorer abstain events fire with reason and candidate identity.
   - Confirm state.json is written on termination and restored on reload.

3. **AM rules alignment check:**
   - Run one full sim session and verify `abstain` events explain every non-signal candidate.
   - Cross-check against `AM_rules_v2_spec.md` §11 to confirm IMPLEMENTED items are actually firing correctly.

**The central regression standard:** the question "why did the system not take that setup?" must be answerable for every candidate in the JSONL stream. If it cannot be answered, there is an unlogged drop somewhere — find it before live promotion.

## AM rule specifications

The canonical rules-as-code reference for V2_5:
`C:\seasonals\baiynd_autotrader\video transcripts\AM_rules_v2_spec.md`

The top section "CURRENT IMPLEMENTATION: V2_5 architecture" is the condensed summary. Section §11 shows the status of every priority item (IMPLEMENTED / DEFERRED V1.1 / OPEN).
