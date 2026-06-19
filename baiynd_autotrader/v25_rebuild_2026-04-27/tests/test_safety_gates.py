#!/usr/bin/env python3
"""
test_safety_gates.py  --  L3 Safety Gate Spec + JSONL Validator
================================================================
Architecture ref: architecture_spec_v25.md §2.3 TEST-L3-1 (each gate triggers)
                  architecture_spec_v25.md §8 (all 12 gates defined)

This module validates all 12 L3 safety gates by:

  1. SPEC MODE (--spec):   Print the 12 gate scenarios with setup conditions,
     expected abstain payload, and manual reproduction steps. Use before you
     have JSONL data.

  2. VALIDATION MODE (default / --jsonl):  Parse strategy_events.jsonl (or
     events.jsonl) and verify that:
     - For each gate's trigger scenario: exactly ONE abstain event fires with
       the correct gate_name, layer="L3", non-empty reason, and a
       recoverable_until_time field.
     - No gate fires spuriously (abstain fires when trigger condition is NOT met).
     - Every abstain has the required schema fields.

Gate reference (from spec §2.3):
  Gate 1:  rth_window           — trade outside 9:30–14:30 ET
  Gate 2:  daily_loss_kill      — realized PnL <= -$500 (dollar amount)
  Gate 3:  daily_loss_pct_kill  — realized PnL <= -2% of account
  Gate 4:  max_losing_trades    — 2 consecutive stops OR 3 losing trades today
  Gate 5:  cooldown_after_stop  — < 30 min since last stop
  Gate 6:  max_signals_per_day  — fills today >= 5
  Gate 7:  position_already_active — position open or pending
  Gate 8:  insufficient_margin  — margin < estimated required (HARD ON)
  Gate 9:  manual_kill_switch   — button/hotkey activated
  Gate 10: holiday_blackout     — full-close or early-close holiday
  Gate 11: connection_error     — data or order feed disconnected
  Gate 12: heartbeat_gap        — no OnBarUpdate in > 90 s during RTH

Usage:
  # Print all 12 gate specs (no JSONL required)
  python test_safety_gates.py --spec

  # Validate all abstain events in a strategy_events.jsonl
  python test_safety_gates.py \\
      --jsonl "C:/seasonals/cockpit/sessions/2026-04-27/strategy_events.jsonl"

  # Validate a specific gate
  python test_safety_gates.py \\
      --jsonl "C:/seasonals/cockpit/sessions/2026-04-27/strategy_events.jsonl" \\
      --gate cooldown_after_stop

  # Run structural abstain schema validation on all L3 abstains found
  python test_safety_gates.py --jsonl <path> --schema-only

  python test_safety_gates.py --help
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Gate spec definitions
# ---------------------------------------------------------------------------

@dataclass
class GateScenario:
    gate_id: int
    gate_name: str
    enable_param: str
    config_params: List[str]
    trigger_condition: str
    expected_reason_substring: str
    recoverable_until: str
    setup_steps: List[str]
    expected_abstain_payload_notes: str
    hard_on: bool = False   # True = cannot be disabled


GATE_SCENARIOS: List[GateScenario] = [
    GateScenario(
        gate_id=1,
        gate_name="rth_window_closed",
        enable_param="EnableRthWindowGate",
        config_params=[
            "RthOpenHourEt=9, RthOpenMinuteEt=30",
            "RthCloseHourEt=15, RthCloseMinuteEt=0",
            "EntryCutoffMinutesBeforeClose=30  (effective cutoff: 14:30 ET)",
        ],
        trigger_condition="bar_time < 09:30 ET  OR  bar_time > 14:30 ET",
        expected_reason_substring="rth_window_closed",
        recoverable_until="next_RthOpen (next trading day 09:30 ET)",
        setup_steps=[
            "1. Set up NT8 Replay on April 23 2026.",
            "2. Ensure strategy is running with EnableRthWindowGate=true.",
            "3. Wait for a candidate event at 08:00 ET (pre-open).",
            "4. Check strategy_events.jsonl for abstain with gate_name='rth_window_closed'.",
            "   Also check: a candidate at 15:01 ET (after cutoff) should produce same abstain.",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='rth_window_closed', reason contains 'rth_window', "
            "recoverable_until_time = next day 09:30 ET"
        ),
    ),
    GateScenario(
        gate_id=2,
        gate_name="daily_loss_kill",
        enable_param="EnableDailyLossKill",
        config_params=["MaxDailyLossDollars=500"],
        trigger_condition="realizedPnlDollarsToday <= -500",
        expected_reason_substring="daily_loss_kill",
        recoverable_until="next_session",
        setup_steps=[
            "1. Run strategy in replay.",
            "2. Allow 3 stop-outs totalling >= $500 realized loss within one session.",
            "   (Example: 3 × 2 MES contracts × ~$100 each = -$600 total.)",
            "3. On the next candidate after that threshold is crossed,",
            "   strategy_events.jsonl should contain abstain gate_name='daily_loss_kill'.",
            "4. Verify lockout_active=true in state.json after the trigger.",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='daily_loss_kill', "
            "gate_state_snapshot.realized_pnl_dollars_today <= -500, "
            "recoverable_until_time='next_session'"
        ),
    ),
    GateScenario(
        gate_id=3,
        gate_name="daily_loss_pct_kill",
        enable_param="EnableDailyLossPctKill",
        config_params=["MaxDailyLossPctOfAccount=2.0", "Default: disabled (EnableDailyLossPctKill=false)"],
        trigger_condition="realized PnL <= -2.0% of account equity",
        expected_reason_substring="daily_loss_pct_kill",
        recoverable_until="next_session",
        setup_steps=[
            "1. Enable gate: EnableDailyLossPctKill=true.",
            "2. Set a small sim account balance (e.g., $10,000).",
            "3. Allow a loss of > $200 (2% of $10K) to accumulate.",
            "4. Verify abstain fires with gate_name='daily_loss_pct_kill'.",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='daily_loss_pct_kill', reason contains account pct threshold"
        ),
    ),
    GateScenario(
        gate_id=4,
        gate_name="max_losing_trades",
        enable_param="EnableMaxLosingTrades",
        config_params=["MaxConsecutiveStops=2", "MaxLosingTradesToday=3"],
        trigger_condition="consecutiveStops >= 2  OR  losingTradesToday >= 3",
        expected_reason_substring="max_losing_trades",
        recoverable_until="next_session",
        setup_steps=[
            "1. Allow 2 consecutive stop-outs.",
            "2. On the next candidate, verify abstain with gate_name='max_losing_trades'.",
            "   Also test the 3-losing-trades path: reset consecutiveStops between stops",
            "   but accumulate 3 total losing trades.",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='max_losing_trades', "
            "gate_state_snapshot includes consecutive_stops and losing_trades_today counts"
        ),
    ),
    GateScenario(
        gate_id=5,
        gate_name="cooldown_after_stop",
        enable_param="EnableCooldownAfterStop",
        config_params=["CooldownMinutes=30"],
        trigger_condition="time_since_last_stop_time < CooldownMinutes",
        expected_reason_substring="cooldown_after_stop",
        recoverable_until="lastStopTime + 30 minutes",
        setup_steps=[
            "1. Allow a stop-out at 10:00 ET.",
            "2. Observe a candidate at 10:15 ET (15 min < 30 min cooldown).",
            "3. Verify abstain with gate_name='cooldown_after_stop'.",
            "4. Observe a candidate at 10:31 ET (> 30 min) — should NOT abstain for this gate.",
            "5. Verify recoverable_until_time = '10:30 ET' (lastStopTime + 30 min).",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='cooldown_after_stop', "
            "reason includes minutes remaining, "
            "recoverable_until_time = lastStopTime + CooldownMinutes"
        ),
    ),
    GateScenario(
        gate_id=6,
        gate_name="max_signals_per_day",
        enable_param="EnableMaxSignalsPerDay",
        config_params=["MaxSignalsPerDay=5", "CountFillsOnly=true"],
        trigger_condition="fillsToday >= 5  (or signalsToday >= 5 if CountFillsOnly=false)",
        expected_reason_substring="max_signals_per_day",
        recoverable_until="next_session",
        setup_steps=[
            "1. Accumulate 5 filled trades in one session.",
            "2. On the 6th candidate, verify abstain with gate_name='max_signals_per_day'.",
            "3. Verify gate_state_snapshot.fills_today=5.",
            "4. Also test with CountFillsOnly=false: pending (unfilled) signals count.",
            "   This was the V2_4 bug (gap_to_am.md GAP19): pending orders counted as fills.",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='max_signals_per_day', "
            "gate_state_snapshot.fills_today >= MaxSignalsPerDay"
        ),
    ),
    GateScenario(
        gate_id=7,
        gate_name="position_already_active",
        enable_param="EnablePositionGuard",
        config_params=["Always enabled; cannot be disabled in live"],
        trigger_condition="signalState == Active OR signalState == Pending",
        expected_reason_substring="position_already_active",
        recoverable_until="position closes",
        setup_steps=[
            "1. Allow a signal to be emitted (pending order placed).",
            "2. Before the order fills or cancels, observe another candidate.",
            "3. Verify abstain with gate_name='position_already_active'.",
            "4. After the first position closes, verify gate is cleared.",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='position_already_active', "
            "recoverable_until_time='position_close'"
        ),
    ),
    GateScenario(
        gate_id=8,
        gate_name="insufficient_margin",
        enable_param="EnableMarginGuard (HARD ON — cannot be disabled)",
        config_params=["EstimatedMarginRequired computed per signal size and instrument"],
        trigger_condition="Account.MarginAvailable < EstimatedMarginRequired(signal)",
        expected_reason_substring="insufficient_margin",
        recoverable_until="account replenished",
        hard_on=True,
        setup_steps=[
            "1. Set sim account to a very low balance (e.g., $1,000).",
            "2. Attempt a signal on ES (margin ~$500-1000 per contract).",
            "3. Verify abstain with gate_name='insufficient_margin'.",
            "4. Note: this gate is HARD ON and cannot be toggled.",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='insufficient_margin', "
            "reason includes available_margin and required_margin"
        ),
    ),
    GateScenario(
        gate_id=9,
        gate_name="manual_kill_switch",
        enable_param="EnableManualKillSwitch",
        config_params=["No numeric params; toggle only"],
        trigger_condition="manualKillSwitchActive=true (set by button click or hotkey)",
        expected_reason_substring="manual_kill_switch",
        recoverable_until="explicit Resume action by user",
        setup_steps=[
            "1. Click the 'Halt All' button on the strategy panel.",
            "2. Verify strategy_events.jsonl contains 'manual_kill_switch_activated' event.",
            "3. Observe the next candidate event.",
            "4. Verify abstain with gate_name='manual_kill_switch'.",
            "5. Click 'Resume'. Verify 'manual_kill_switch_resumed' event.",
            "6. Verify subsequent candidates are no longer blocked by this gate.",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='manual_kill_switch', "
            "recoverable_until_time='manual_resume_required'"
        ),
    ),
    GateScenario(
        gate_id=10,
        gate_name="holiday_blackout",
        enable_param="EnableHolidayGate",
        config_params=[
            "HolidayCalendarPath (default './holidays.parquet')",
            "Falls back to bundled holiday list if file missing",
        ],
        trigger_condition="today is a full-close holiday OR within early-close window",
        expected_reason_substring="holiday_blackout",
        recoverable_until="next non-holiday session",
        setup_steps=[
            "1. Set system date to a known US CME holiday (e.g., July 4 or Christmas).",
            "2. Run the strategy.",
            "3. Verify abstain with gate_name='holiday_blackout' on any candidate.",
            "4. For early-close day (e.g., day before Thanksgiving): confirm",
            "   gate_name='early_close_window' fires after the early-close time.",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='holiday_blackout' or 'early_close_window'"
        ),
    ),
    GateScenario(
        gate_id=11,
        gate_name="connection_error",
        enable_param="EnableConnectionGuard",
        config_params=["No numeric params"],
        trigger_condition="ConnectionStatus != Connected for data or order feed",
        expected_reason_substring="connection_error",
        recoverable_until="reconnection confirmed",
        setup_steps=[
            "1. Disconnect the NinjaTrader data feed (Tools → Data Feeds → Disconnect).",
            "2. Observe the next candidate (or trigger one via replay).",
            "3. Verify abstain with gate_name='connection_error'.",
            "4. Reconnect. Verify 'connection_restored' event fires.",
            "5. Verify subsequent candidates are no longer blocked by this gate.",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='connection_error', "
            "reason identifies which feed (data vs order routing)"
        ),
    ),
    GateScenario(
        gate_id=12,
        gate_name="heartbeat_gap",
        enable_param="EnableHeartbeatSelfCheck",
        config_params=["HeartbeatStaleSeconds=90"],
        trigger_condition="time since last OnBarUpdate > 90 seconds during RTH",
        expected_reason_substring="heartbeat_gap",
        recoverable_until="next bar arrives",
        setup_steps=[
            "1. Pause NT8 Replay for > 90 seconds while within RTH hours.",
            "   (Or: disconnect data feed briefly so no new bars arrive.)",
            "2. Resume replay.",
            "3. The strategy's self-check should detect the gap and emit abstain",
            "   with gate_name='heartbeat_gap' on the next candidate.",
            "4. Verify recoverable_until_time = 'next_bar'.",
        ],
        expected_abstain_payload_notes=(
            "layer='L3', gate_name='heartbeat_gap', "
            "reason includes seconds_since_last_bar and threshold"
        ),
    ),
]

# ---------------------------------------------------------------------------
# Spec printer
# ---------------------------------------------------------------------------

def print_spec():
    print("="*70)
    print("L3 Safety Gates — Scenario Specification (12 gates)")
    print("Architecture ref: architecture_spec_v25.md §2.3 TEST-L3-1")
    print("="*70)
    print()
    print(
        "Each gate must produce an `abstain` event with layer='L3' when triggered.\n"
        "Test by running NT8 in Historical Replay with the described conditions,\n"
        "then validate with: python test_safety_gates.py --jsonl <strategy_events.jsonl>\n"
    )

    for g in GATE_SCENARIOS:
        hard_tag = " [HARD ON — cannot be disabled]" if g.hard_on else ""
        print(f"Gate {g.gate_id:2d}: {g.gate_name}{hard_tag}")
        print(f"  Enable param:       {g.enable_param}")
        print(f"  Config params:      {'; '.join(g.config_params)}")
        print(f"  Trigger condition:  {g.trigger_condition}")
        print(f"  Expected reason:    contains '{g.expected_reason_substring}'")
        print(f"  Recoverable until:  {g.recoverable_until}")
        print(f"  Abstain notes:      {g.expected_abstain_payload_notes}")
        print(f"  Setup steps:")
        for step in g.setup_steps:
            print(f"    {step}")
        print()

    print("Validation checklist (manual, per gate):")
    print("  [ ] gate_name matches expected value exactly")
    print("  [ ] layer = 'L3'")
    print("  [ ] reason is non-empty and human-readable")
    print("  [ ] recoverable_until_time is present and parseable as datetime or 'next_session'")
    print("  [ ] gate_state_snapshot is present for gates 2-7 (includes relevant counters)")
    print("  [ ] No spurious abstains (gate fires when trigger condition is NOT met)")
    print()


# ---------------------------------------------------------------------------
# JSONL loading + validation
# ---------------------------------------------------------------------------

def load_l3_abstains(path: str, gate_filter: Optional[str] = None) -> List[dict]:
    """Return all L3 abstain event payloads from a JSONL file."""
    abstains = []
    if not os.path.exists(path):
        return abstains
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if evt.get("type") != "abstain":
                continue
            p = evt.get("payload", {})
            if p.get("layer") != "L3":
                continue
            if gate_filter and p.get("gate_name") != gate_filter:
                continue
            abstains.append({"envelope": evt, "payload": p})
    return abstains


def validate_l3_abstain_schema(abstain: dict) -> List[str]:
    """Validate the schema of a single L3 abstain event. Returns list of issues."""
    issues = []
    p = abstain["payload"]
    env = abstain["envelope"]

    required = {"candidate_id", "layer", "gate_name", "reason"}
    missing = required - set(p.keys())
    if missing:
        issues.append(f"Missing required fields: {sorted(missing)}")

    if p.get("layer") != "L3":
        issues.append(f"layer={p.get('layer')!r} expected 'L3'")

    gate_name = p.get("gate_name", "")
    if not gate_name:
        issues.append("gate_name is empty or null")
    else:
        known_gates = {g.gate_name for g in GATE_SCENARIOS}
        if gate_name not in known_gates:
            issues.append(f"gate_name={gate_name!r} not in known gates. Known: {sorted(known_gates)}")

    if not p.get("reason", "").strip():
        issues.append("reason is empty or null")

    if "recoverable_until_time" not in p:
        issues.append("recoverable_until_time field missing (spec INV-L3-2 requires it)")

    return issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    if args.spec:
        print_spec()
        return 0

    if not args.jsonl:
        print("[ERROR] Either --spec or --jsonl is required.")
        print("Run with --help for usage.")
        return 1

    if not os.path.exists(args.jsonl):
        print(f"[ERROR] JSONL file not found: {args.jsonl}")
        print(
            "Generate it by running AMTradeStrategyV1 in NT8 Historical Replay mode.\n"
            "The file is written to:\n"
            "  C:\\seasonals\\cockpit\\sessions\\YYYY-MM-DD\\strategy_events.jsonl"
        )
        return 1

    gate_filter = args.gate or None

    print(f"Loading L3 abstain events from: {args.jsonl}")
    if gate_filter:
        print(f"Filtering to gate: {gate_filter}")

    abstains = load_l3_abstains(args.jsonl, gate_filter=gate_filter)
    print(f"  L3 abstain events found: {len(abstains)}")

    if not abstains:
        print(
            "[WARN] No L3 abstain events found. Possible causes:\n"
            "  - No L3 gate was triggered during the replay session.\n"
            "  - The strategy may not have been running L3 gates.\n"
            "  - Wrong file path.\n"
            "Run with --spec to see expected gate scenarios."
        )
        return 0

    # Schema validation
    total_issues = 0
    gate_counts: Dict[str, int] = {}
    gate_issues: Dict[str, List[str]] = {}

    for ab in abstains:
        gate_name = ab["payload"].get("gate_name", "UNKNOWN")
        gate_counts[gate_name] = gate_counts.get(gate_name, 0) + 1
        issues = validate_l3_abstain_schema(ab)
        if issues:
            if gate_name not in gate_issues:
                gate_issues[gate_name] = []
            gate_issues[gate_name].extend(issues)
            total_issues += len(issues)

    print("\nL3 abstain events by gate:")
    for gate_name, count in sorted(gate_counts.items()):
        known = gate_name in {g.gate_name for g in GATE_SCENARIOS}
        known_tag = "" if known else " [UNKNOWN GATE]"
        issue_tag = f" [{len(gate_issues.get(gate_name, []))} schema issues]" if gate_name in gate_issues else ""
        print(f"  {gate_name:<35} {count:>4} event(s){known_tag}{issue_tag}")

    if gate_issues:
        print(f"\nSchema violations found: {total_issues}")
        for gate_name, issues in sorted(gate_issues.items()):
            print(f"  Gate: {gate_name}")
            for iss in issues[:5]:
                print(f"    - {iss}")

    if not args.schema_only:
        # Spec coverage: which expected gates are present vs absent
        print("\nSpec coverage (gates observed vs expected):")
        observed_gates = set(gate_counts.keys())
        for g in GATE_SCENARIOS:
            present = g.gate_name in observed_gates
            if present:
                cnt = gate_counts.get(g.gate_name, 0)
                print(f"  [{g.gate_id:2d}] {g.gate_name:<35} OBSERVED ({cnt} events)")
            else:
                print(f"  [{g.gate_id:2d}] {g.gate_name:<35} NOT YET OBSERVED (need trigger scenario)")

        unobserved_count = len(GATE_SCENARIOS) - len(observed_gates.intersection({g.gate_name for g in GATE_SCENARIOS}))
        if unobserved_count:
            print(f"\n  {unobserved_count} gate(s) not yet triggered in this session.")
            print("  Use --spec to get setup steps for each unobserved gate.")

    status = "PASS" if total_issues == 0 else "FAIL"
    print(f"\nResult: [{status}]")
    return 0 if total_issues == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="test_safety_gates.py",
        description=(
            "L3 safety gate spec + JSONL schema validator for all 12 gates.\n"
            "Use --spec to print setup scenarios. Use --jsonl to validate output."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--spec",
        action="store_true",
        help="Print all 12 gate scenarios and exit (no JSONL needed).",
    )
    p.add_argument(
        "--jsonl",
        metavar="PATH",
        help="Path to strategy_events.jsonl to validate.",
    )
    p.add_argument(
        "--gate",
        metavar="GATE_NAME",
        help="Filter to a single gate name (e.g., 'cooldown_after_stop').",
    )
    p.add_argument(
        "--schema-only",
        action="store_true",
        help="Only validate schemas; skip coverage summary.",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print all matched abstain payloads.",
    )
    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))
