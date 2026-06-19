#!/usr/bin/env python3
"""
test_pattern_b_state_machine.py  --  Pattern B State Machine Spec + JSONL Validator
=====================================================================================
Architecture ref: architecture_spec_v25.md §2.1 TEST-L1-2, §6.x Pattern B spec.

Pattern B (look-below-and-fail / look-above-and-fail) drives a per-level state machine:

    Untouched → Breached → Armed → Consumed  (success path)
                         → Invalidated       (failure path)

This module does two things:
  1. SPEC MODE (--spec):  Print the human-readable bar sequences and expected state
     transitions. Used as a reference checklist when preparing NT8 replay data.
  2. VALIDATION MODE (default):  Given a JSONL file produced by V2_5 on synthetic or
     replay data, verify that the observed `pattern_b_state_change` events follow
     the correct transition rules for each scenario.

State machine rules (from spec §2.1):
  - Untouched → Breached  : a 1-min bar has low < level_price AND close >= level_price
                             (LONG direction). Inverse for SHORT.
  - Breached  → Armed     : the bar immediately after the breach bar has a higher-low
                             (for LONG) or lower-high (for SHORT) vs the breach bar.
  - Armed     → Consumed  : any subsequent bar's price touches the level (entry trigger
                             crosses the breach-bar high for LONG / low for SHORT).
                             L1 emits a `candidate` event with pattern_type="B".
  - Armed     → Invalidated: a bar closes below the breach-bar's low (LONG) or above the
                              breach-bar's high (SHORT).

Event types parsed:
  - `pattern_b_state_change`  : emitted by L1 on every state transition.
  - `candidate` with pattern_type="B" : emitted when state reaches Armed and entry fires.

Usage:
  # Print the spec scenarios (no JSONL required)
  python test_pattern_b_state_machine.py --spec

  # Validate JSONL from a V2_5 replay run
  python test_pattern_b_state_machine.py \\
      --jsonl "C:/seasonals/cockpit/sessions/2026-04-27/events.jsonl"

  # Validate and filter to a specific level
  python test_pattern_b_state_machine.py \\
      --jsonl "C:/seasonals/cockpit/sessions/2026-04-27/events.jsonl" \\
      --level "Close330"

  python test_pattern_b_state_machine.py --help
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# State machine constants
# ---------------------------------------------------------------------------

VALID_STATES = {"Untouched", "Breached", "Armed", "Consumed", "Invalidated"}

VALID_TRANSITIONS = {
    ("Untouched", "Breached"),
    ("Breached",  "Armed"),
    ("Armed",     "Consumed"),
    ("Armed",     "Invalidated"),
    # Resets (new session or explicit reset)
    ("Consumed",    "Untouched"),
    ("Invalidated", "Untouched"),
    # Partial: breach without arm if session ends
    ("Breached",    "Untouched"),
}

# ---------------------------------------------------------------------------
# Scenario definitions (spec mode)
# ---------------------------------------------------------------------------

@dataclass
class BarSpec:
    """Synthetic bar description for a scenario."""
    bar_num: int
    description: str
    open: float
    high: float
    low: float
    close: float
    expected_state_after: str
    notes: str = ""


@dataclass
class Scenario:
    name: str
    level_price: float
    direction: str  # LONG or SHORT
    bars: List[BarSpec]
    final_expected_state: str
    expects_candidate: bool
    description: str


SCENARIOS: List[Scenario] = [
    Scenario(
        name="S1_long_clean_breach_and_arm",
        level_price=5610.0,
        direction="LONG",
        description=(
            "Clean LONG Pattern B: bar dips below level then closes above it (breach). "
            "Next bar holds higher-low vs breach bar (arm). "
            "Following bar touches level from above (entry trigger = candidate emitted)."
        ),
        bars=[
            BarSpec(1, "Setup bar: price above level", 5612.0, 5614.0, 5611.0, 5613.5,
                    "Untouched", "No interaction with level yet."),
            BarSpec(2, "Breach bar: low < level, close >= level",
                    5613.0, 5613.5, 5609.5, 5611.5,
                    "Breached",
                    "low(5609.5) < level(5610) AND close(5611.5) >= level → BREACH."),
            BarSpec(3, "Arm bar: higher-low vs breach (breach low=5609.5, this low=5611.0)",
                    5611.5, 5613.0, 5611.0, 5612.5,
                    "Armed",
                    "low(5611) > breach_low(5609.5) → ARM. Candidate may be emitted here."),
            BarSpec(4, "Entry trigger: bar touches level from above (low <= level_price)",
                    5612.5, 5613.0, 5609.8, 5611.0,
                    "Consumed",
                    "Bar interacts with level while Armed → CONSUME + candidate emitted."),
        ],
        final_expected_state="Consumed",
        expects_candidate=True,
    ),
    Scenario(
        name="S2_long_breach_then_invalidated",
        level_price=5610.0,
        direction="LONG",
        description=(
            "LONG breach but next bar fails to hold — closes below the breach-bar's low. "
            "State transitions Breached → Armed → Invalidated."
        ),
        bars=[
            BarSpec(1, "Setup", 5612.0, 5614.0, 5611.5, 5613.0,
                    "Untouched", ""),
            BarSpec(2, "Breach bar (low=5609, close=5611)",
                    5613.0, 5613.5, 5609.0, 5611.0,
                    "Breached", ""),
            BarSpec(3, "Arm bar (low=5610.5 > breach low 5609)",
                    5611.0, 5612.5, 5610.5, 5612.0,
                    "Armed", ""),
            BarSpec(4, "Invalidation bar: closes BELOW breach low (5609)",
                    5611.5, 5612.0, 5607.0, 5607.5,
                    "Invalidated",
                    "close(5607.5) < breach_low(5609) → INVALIDATED."),
        ],
        final_expected_state="Invalidated",
        expects_candidate=False,
    ),
    Scenario(
        name="S3_short_clean_breach_and_arm",
        level_price=5620.0,
        direction="SHORT",
        description=(
            "Clean SHORT Pattern B: bar pops above level then closes below it. "
            "Next bar holds lower-high vs breach bar. Entry trigger candidate emitted."
        ),
        bars=[
            BarSpec(1, "Setup bar: price below level", 5616.0, 5618.5, 5615.0, 5617.0,
                    "Untouched", ""),
            BarSpec(2, "Breach bar: high > level, close <= level",
                    5617.0, 5621.5, 5616.5, 5618.5,
                    "Breached",
                    "high(5621.5) > level(5620) AND close(5618.5) <= level → BREACH SHORT."),
            BarSpec(3, "Arm bar: lower-high vs breach (breach high=5621.5, this high=5619.5)",
                    5618.0, 5619.5, 5617.0, 5618.5,
                    "Armed",
                    "high(5619.5) < breach_high(5621.5) → ARM."),
            BarSpec(4, "Entry trigger: bar touches level from below",
                    5618.5, 5620.5, 5617.5, 5619.0,
                    "Consumed",
                    "Bar high >= level_price while Armed → CONSUME + candidate emitted."),
        ],
        final_expected_state="Consumed",
        expects_candidate=True,
    ),
    Scenario(
        name="S4_breach_no_close_back_no_arm",
        level_price=5610.0,
        direction="LONG",
        description=(
            "Bar dips below level AND closes below level (full breakdown). "
            "This is NOT a Pattern B breach — it is a failed retest (no close back). "
            "State should remain Untouched OR transition to a rejected-breach state. "
            "No candidate should be emitted."
        ),
        bars=[
            BarSpec(1, "Setup", 5612.0, 5614.0, 5611.5, 5613.0,
                    "Untouched", ""),
            BarSpec(2, "Failed close: low < level AND close < level",
                    5613.0, 5613.5, 5609.0, 5608.5,
                    "Untouched",
                    "close(5608.5) < level(5610) → not a breach; state stays Untouched."),
        ],
        final_expected_state="Untouched",
        expects_candidate=False,
    ),
    Scenario(
        name="S5_armed_reset_on_new_session",
        level_price=5610.0,
        direction="LONG",
        description=(
            "Level reaches Armed state. Session ends (no entry trigger fires). "
            "On next session, state should reset to Untouched. "
            "Spec §2.1 INV-L1: 'State persisted via state.json' — after session rollover "
            "a stale Armed state must NOT carry over as a live candidate trigger."
        ),
        bars=[
            BarSpec(1, "Breach bar", 5613.0, 5613.5, 5609.5, 5611.5,
                    "Breached", ""),
            BarSpec(2, "Arm bar", 5611.5, 5613.0, 5611.0, 5612.5,
                    "Armed", "Session ends here."),
            # Simulated new session bar
            BarSpec(3, "[NEW SESSION] first bar after overnight reset",
                    5614.0, 5615.0, 5613.5, 5614.5,
                    "Untouched",
                    "Session rollover resets LevelWatchState to Untouched for all levels."),
        ],
        final_expected_state="Untouched",
        expects_candidate=False,
    ),
]

# ---------------------------------------------------------------------------
# Spec printer
# ---------------------------------------------------------------------------

def print_spec():
    print("="*70)
    print("Pattern B State Machine — Scenario Specification")
    print("Architecture ref: architecture_spec_v25.md §2.1 TEST-L1-2")
    print("="*70)
    print()
    print("These scenarios describe bar sequences and expected transitions.")
    print("Use them to construct NT8 replay data, then validate with --jsonl.")
    print()

    for sc in SCENARIOS:
        print(f"Scenario: {sc.name}")
        print(f"  Level: {sc.level_price}  Direction: {sc.direction}")
        print(f"  Description: {sc.description}")
        print(f"  Expects candidate: {sc.expects_candidate}")
        print(f"  Final expected state: {sc.final_expected_state}")
        print()
        print(f"  {'Bar':>4}  {'O':>8}  {'H':>8}  {'L':>8}  {'C':>8}  {'Expected State After':<22}  Notes")
        print(f"  {'-'*4}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*22}  -----")
        for b in sc.bars:
            print(
                f"  {b.bar_num:>4}  {b.open:>8.2f}  {b.high:>8.2f}  {b.low:>8.2f}  "
                f"{b.close:>8.2f}  {b.expected_state_after:<22}  {b.notes}"
            )
        print()

    print("Validation checklist for each scenario:")
    print("  [ ] `pattern_b_state_change` events appear in events.jsonl")
    print("  [ ] Transitions follow the valid transition table:")
    for (frm, to) in sorted(VALID_TRANSITIONS):
        print(f"        {frm:15} → {to}")
    print("  [ ] No invalid transitions (e.g., Untouched → Armed skipping Breached)")
    print("  [ ] For scenarios expecting a candidate: a `candidate` event with")
    print("      pattern_type='B' and lws_state='Armed' exists in the same minute.")
    print("  [ ] For scenarios NOT expecting a candidate: no such event.")
    print()


# ---------------------------------------------------------------------------
# JSONL event parsing
# ---------------------------------------------------------------------------

@dataclass
class StateChangeEvent:
    level_name: str
    level_price: float
    direction: str
    from_state: str
    to_state: str
    bar_time: Optional[datetime]
    source_file: str


@dataclass
class CandidateBEvent:
    candidate_id: str
    level_name: str
    level_price: float
    direction: str
    lws_state: str
    bar_time: Optional[datetime]
    source_file: str


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def load_state_changes(jsonl_path: str, level_filter: Optional[str] = None) -> List[StateChangeEvent]:
    events = []
    if not os.path.exists(jsonl_path):
        return events

    with open(jsonl_path, "r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if evt.get("type") != "pattern_b_state_change":
                continue
            p = evt.get("payload", {})
            level_name = p.get("level_name", "")
            if level_filter and level_filter.lower() not in level_name.lower():
                continue
            events.append(StateChangeEvent(
                level_name=level_name,
                level_price=float(p.get("level_price", 0.0)),
                direction=p.get("direction", ""),
                from_state=p.get("from_state", ""),
                to_state=p.get("to_state", ""),
                bar_time=_parse_dt(p.get("bar_time", "") or evt.get("t", "")),
                source_file=jsonl_path,
            ))
    return events


def load_pattern_b_candidates(jsonl_path: str, level_filter: Optional[str] = None) -> List[CandidateBEvent]:
    events = []
    if not os.path.exists(jsonl_path):
        return events

    with open(jsonl_path, "r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if evt.get("type") != "candidate":
                continue
            p = evt.get("payload", {})
            if p.get("pattern_type") != "B":
                continue
            level_name = p.get("level_name", "")
            if level_filter and level_filter.lower() not in level_name.lower():
                continue
            events.append(CandidateBEvent(
                candidate_id=p.get("candidate_id", ""),
                level_name=level_name,
                level_price=float(p.get("level_price", 0.0)),
                direction=p.get("direction", ""),
                lws_state=p.get("lws_state", ""),
                bar_time=_parse_dt(p.get("bar_time", "") or evt.get("t", "")),
                source_file=jsonl_path,
            ))
    return events


# ---------------------------------------------------------------------------
# JSONL validation
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    severity: str  # CRITICAL | WARN
    level_name: str
    direction: str
    message: str


def validate_transitions(
    state_changes: List[StateChangeEvent],
    candidates_b: List[CandidateBEvent],
    verbose: bool = False,
) -> Tuple[List[ValidationIssue], int]:
    """
    Validate the observed state machine transitions in JSONL events.

    Returns (issues, total_transitions_checked).
    """
    issues: List[ValidationIssue] = []
    total_checked = 0

    # Group state changes by (level_name, direction)
    groups: Dict[Tuple[str, str], List[StateChangeEvent]] = {}
    for sc in state_changes:
        key = (sc.level_name, sc.direction)
        if key not in groups:
            groups[key] = []
        groups[key].append(sc)

    # Sort each group by time
    for key in groups:
        groups[key].sort(key=lambda e: e.bar_time or datetime.min)

    for (level_name, direction), transitions in groups.items():
        for t in transitions:
            total_checked += 1
            edge = (t.from_state, t.to_state)
            if edge not in VALID_TRANSITIONS:
                issues.append(ValidationIssue(
                    severity="CRITICAL",
                    level_name=level_name,
                    direction=direction,
                    message=(
                        f"Invalid transition {t.from_state!r} → {t.to_state!r} "
                        f"at {t.bar_time}. "
                        f"Valid transitions from {t.from_state!r}: "
                        f"{[b for (a,b) in VALID_TRANSITIONS if a == t.from_state]}"
                    ),
                ))

            if t.from_state not in VALID_STATES:
                issues.append(ValidationIssue(
                    severity="CRITICAL",
                    level_name=level_name,
                    direction=direction,
                    message=f"Unknown from_state {t.from_state!r} at {t.bar_time}",
                ))
            if t.to_state not in VALID_STATES:
                issues.append(ValidationIssue(
                    severity="CRITICAL",
                    level_name=level_name,
                    direction=direction,
                    message=f"Unknown to_state {t.to_state!r} at {t.bar_time}",
                ))

        # Verify Breached always precedes Armed
        states_seq = [t.to_state for t in transitions]
        if "Armed" in states_seq and "Breached" not in states_seq:
            # Armed with no preceding Breached — either a data gap or bug
            issues.append(ValidationIssue(
                severity="WARN",
                level_name=level_name,
                direction=direction,
                message=(
                    f"'Armed' state observed but no 'Breached' transition in event log. "
                    f"Either the breach occurred before JSONL recording started, "
                    f"or a state was skipped."
                ),
            ))

    # Verify every Consumed state has a matching Pattern B candidate
    consumed_keys = set()
    for (level_name, direction), transitions in groups.items():
        for t in transitions:
            if t.to_state == "Consumed":
                consumed_keys.add((level_name.lower(), direction.upper()))

    candidate_keys = set()
    for c in candidates_b:
        candidate_keys.add((c.level_name.lower(), c.direction.upper()))

    for key in consumed_keys:
        if key not in candidate_keys:
            issues.append(ValidationIssue(
                severity="CRITICAL",
                level_name=key[0],
                direction=key[1],
                message=(
                    "State reached 'Consumed' but no Pattern B candidate event found "
                    "for this level/direction. "
                    "Spec requires a `candidate` event with pattern_type='B' on Armed→Consumed."
                ),
            ))

    return issues, total_checked


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    if args.spec:
        print_spec()
        return 0

    if not args.jsonl:
        print("[ERROR] Either --spec or --jsonl must be provided.")
        print("Run with --help for usage.")
        return 1

    if not os.path.exists(args.jsonl):
        print(f"[ERROR] JSONL file not found: {args.jsonl}")
        print("Run V2_5 in Historical Replay mode to generate events.jsonl, then re-run this test.")
        return 1

    print(f"Loading Pattern B events from: {args.jsonl}")
    if args.level:
        print(f"Filtering to level: {args.level}")

    state_changes = load_state_changes(args.jsonl, level_filter=args.level)
    candidates_b = load_pattern_b_candidates(args.jsonl, level_filter=args.level)

    print(f"  pattern_b_state_change events: {len(state_changes)}")
    print(f"  Pattern B candidate events:    {len(candidates_b)}")

    if not state_changes:
        print(
            "[WARN] No pattern_b_state_change events found. "
            "Either EnablePatternB=false, or replay data had no Pattern B activity."
        )
        return 0

    issues, total = validate_transitions(state_changes, candidates_b, verbose=args.verbose)

    print(f"\nTransitions validated: {total}")

    if issues:
        critical = [i for i in issues if i.severity == "CRITICAL"]
        warnings = [i for i in issues if i.severity == "WARN"]
        print(f"\n  [CRITICAL issues]: {len(critical)}")
        for iss in critical:
            print(f"    [{iss.level_name} {iss.direction}] {iss.message}")
        if warnings:
            print(f"\n  [WARNINGS]: {len(warnings)}")
            for iss in warnings:
                print(f"    [{iss.level_name} {iss.direction}] {iss.message}")

        status = "FAIL" if critical else "WARN"
    else:
        print("\n  No transition violations detected.")
        status = "PASS"

    print(f"\nResult: [{status}]")
    return 0 if status in ("PASS", "WARN") else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="test_pattern_b_state_machine.py",
        description=(
            "Pattern B state machine spec + JSONL validator.\n"
            "Use --spec to print scenarios. Use --jsonl to validate JSONL output."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--spec",
        action="store_true",
        help="Print the Pattern B scenario spec document and exit (no JSONL needed).",
    )
    p.add_argument(
        "--jsonl",
        metavar="PATH",
        help="Path to V2_5 events.jsonl to validate.",
    )
    p.add_argument(
        "--level",
        metavar="LEVEL_NAME",
        help="Filter to events for a specific level (case-insensitive substring match).",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print all matched events, not just violations.",
    )
    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))
