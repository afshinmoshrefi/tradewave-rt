#!/usr/bin/env python3
"""
test_contract_compliance.py  --  V2_5 Prime-Directive Contract Validator
=========================================================================
Validates the core invariant from architecture_spec_v25.md Section 1.3:

    For EVERY `candidate` event, there MUST exist EITHER a `signal` event
    OR an `abstain` event sharing the same `candidate_id`.
    Zero silent drops are allowed.

The test reads JSONL session files produced by:
  - L1 indicator  (AMTradeCockpitV2_5.cs)  → events.jsonl
  - L2/L3 strategy (AMTradeStrategyV1.cs)  → strategy_events.jsonl

Both files live under:
  C:\\seasonals\\cockpit\\sessions\\YYYY-MM-DD\\

Exit codes:
  0  All candidates have matching signal or abstain. Full compliance.
  1  One or more violations found. Details printed to stdout.

Usage examples:
  # Validate a single session date
  python test_contract_compliance.py --date 2026-04-27

  # Validate a date range
  python test_contract_compliance.py --start 2026-04-01 --end 2026-04-27

  # Validate a specific events.jsonl + strategy_events.jsonl pair
  python test_contract_compliance.py \\
      --l1-file "C:/seasonals/cockpit/sessions/2026-04-27/events.jsonl" \\
      --l2-file "C:/seasonals/cockpit/sessions/2026-04-27/strategy_events.jsonl"

  # Validate a whole folder tree (all dates found)
  python test_contract_compliance.py --sessions-root "C:/seasonals/cockpit/sessions"

  python test_contract_compliance.py --help
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Schema constants from architecture_spec_v25.md §3
# ---------------------------------------------------------------------------

VALID_LAYERS = {"L1", "L2", "L3"}

# Required fields on a `candidate` payload (spec §3.3)
CANDIDATE_REQUIRED = {
    "candidate_id",
    "level_name",
    "level_price",
    "is_permission_level",
    "direction",
    "pattern_type",
    "bar_time",
    "bar_open",
    "bar_high",
    "bar_low",
    "bar_close",
    "bar_volume",
    "features",
}

# Required fields on a `signal` payload (spec §3.4)
SIGNAL_REQUIRED = {
    "signal_id",
    "candidate_id",
    "direction",
    "entry_price",
    "stop_price",
    "first_target_price",
    "pattern_type",
    "level_name",
    "scorer_decision",
}

# Required fields on an `abstain` payload (spec §3.5)
ABSTAIN_REQUIRED = {
    "candidate_id",
    "layer",
    "gate_name",
    "reason",
}

# ---------------------------------------------------------------------------
# JSONL parsing helpers
# ---------------------------------------------------------------------------

def load_jsonl(path: str) -> List[dict]:
    """Load a JSONL file. Lines that fail to parse are collected as errors."""
    events = []
    parse_errors = []
    if not os.path.exists(path):
        return events  # caller handles missing file
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                parse_errors.append(f"  {path}:{lineno} → {exc}")
    if parse_errors:
        print(f"[WARN] {len(parse_errors)} JSON parse errors in {path}:")
        for e in parse_errors[:10]:
            print(e)
        if len(parse_errors) > 10:
            print(f"  ... and {len(parse_errors) - 10} more")
    return events


def get_type(event: dict) -> Optional[str]:
    return event.get("type")


def get_payload(event: dict) -> dict:
    return event.get("payload", {})


# ---------------------------------------------------------------------------
# Individual-event validators
# ---------------------------------------------------------------------------

def validate_candidate_schema(payload: dict, candidate_id: str) -> List[str]:
    issues = []
    missing = CANDIDATE_REQUIRED - set(payload.keys())
    if missing:
        issues.append(f"candidate {candidate_id!r}: missing required fields {sorted(missing)}")

    # direction must be LONG or SHORT
    direction = payload.get("direction")
    if direction not in ("LONG", "SHORT"):
        issues.append(f"candidate {candidate_id!r}: invalid direction {direction!r} (expected LONG|SHORT)")

    # pattern_type must be A or B
    pt = payload.get("pattern_type")
    if pt not in ("A", "B", None):
        issues.append(f"candidate {candidate_id!r}: unexpected pattern_type {pt!r} (expected A|B|null)")

    # features must not have NaN values (spec INV-L1-3)
    features = payload.get("features")
    if isinstance(features, dict):
        nan_fields = [k for k, v in features.items() if isinstance(v, float) and (v != v)]
        if nan_fields:
            issues.append(
                f"candidate {candidate_id!r}: NaN in features fields {nan_fields[:5]} "
                f"(spec INV-L1-3: emit null+flag, never NaN)"
            )

    return issues


def validate_signal_schema(payload: dict, candidate_id: str) -> List[str]:
    issues = []
    missing = SIGNAL_REQUIRED - set(payload.keys())
    if missing:
        issues.append(f"signal for candidate {candidate_id!r}: missing required fields {sorted(missing)}")

    direction = payload.get("direction")
    if direction not in ("LONG", "SHORT"):
        issues.append(f"signal for candidate {candidate_id!r}: invalid direction {direction!r}")

    scorer = payload.get("scorer_decision", {})
    if isinstance(scorer, dict):
        for sf in ("p_win", "expected_R", "confidence", "scorer_mode"):
            if sf not in scorer:
                issues.append(
                    f"signal for candidate {candidate_id!r}: scorer_decision missing field {sf!r}"
                )

    return issues


def validate_abstain_schema(payload: dict, candidate_id: str) -> List[str]:
    issues = []
    missing = ABSTAIN_REQUIRED - set(payload.keys())
    if missing:
        issues.append(f"abstain for candidate {candidate_id!r}: missing required fields {sorted(missing)}")

    layer = payload.get("layer")
    if layer not in VALID_LAYERS:
        issues.append(
            f"abstain for candidate {candidate_id!r}: layer={layer!r} not in {VALID_LAYERS}"
        )

    gate_name = payload.get("gate_name")
    if not gate_name or not str(gate_name).strip():
        issues.append(f"abstain for candidate {candidate_id!r}: gate_name is null/empty")

    reason = payload.get("reason")
    if not reason or not str(reason).strip():
        issues.append(f"abstain for candidate {candidate_id!r}: reason is null/empty")

    return issues


# ---------------------------------------------------------------------------
# Core compliance logic
# ---------------------------------------------------------------------------

class ComplianceResult:
    def __init__(self, session_label: str):
        self.session_label = session_label
        self.total_candidates = 0
        self.total_signals = 0
        self.total_abstains = 0
        self.orphan_candidates: List[str] = []      # candidate with NO follow-up (CRITICAL)
        self.invalid_candidates: List[str] = []     # schema violations on candidate itself
        self.invalid_signals: List[str] = []        # schema violations on signal
        self.invalid_abstains: List[str] = []       # schema violations on abstain
        self.orphan_signals: List[str] = []         # signal/abstain with no matching candidate (warning)

    @property
    def is_compliant(self) -> bool:
        """True only when zero CRITICAL violations (orphans, schema errors)."""
        return (
            len(self.orphan_candidates) == 0
            and len(self.invalid_candidates) == 0
            and len(self.invalid_signals) == 0
            and len(self.invalid_abstains) == 0
        )

    def print_summary(self, verbose: bool = False):
        label = self.session_label
        print(f"\n{'='*60}")
        print(f"Session: {label}")
        print(f"{'='*60}")
        print(f"  Candidates:       {self.total_candidates}")
        print(f"  Signals:          {self.total_signals}")
        print(f"  Abstains:         {self.total_abstains}")
        coverage = (
            (self.total_signals + self.total_abstains) / self.total_candidates * 100
            if self.total_candidates > 0 else 0.0
        )
        print(f"  Coverage:         {coverage:.1f}%")
        print()

        if self.orphan_candidates:
            print(f"  [CRITICAL] ORPHAN CANDIDATES (silent drops): {len(self.orphan_candidates)}")
            for cid in self.orphan_candidates[:20]:
                print(f"    - {cid}")
            if len(self.orphan_candidates) > 20:
                print(f"    ... and {len(self.orphan_candidates) - 20} more")
        else:
            print("  [OK] No orphan candidates.")

        if self.invalid_candidates:
            print(f"  [FAIL] Invalid candidate schemas: {len(self.invalid_candidates)}")
            for msg in self.invalid_candidates[:10]:
                print(f"    - {msg}")
        if self.invalid_signals:
            print(f"  [FAIL] Invalid signal schemas: {len(self.invalid_signals)}")
            for msg in self.invalid_signals[:10]:
                print(f"    - {msg}")
        if self.invalid_abstains:
            print(f"  [FAIL] Invalid abstain schemas: {len(self.invalid_abstains)}")
            for msg in self.invalid_abstains[:10]:
                print(f"    - {msg}")
        if self.orphan_signals:
            print(f"  [WARN] Signals/abstains with no matching candidate: {len(self.orphan_signals)}")
            if verbose:
                for msg in self.orphan_signals[:10]:
                    print(f"    - {msg}")

        status = "PASS" if self.is_compliant else "FAIL"
        print(f"\n  Result: [{status}]")


def check_session(
    l1_events: List[dict],
    l2_events: List[dict],
    session_label: str,
) -> ComplianceResult:
    """
    Run the contract compliance check for a single session.

    Combines L1 events (candidates, L1 abstains) with L2/L3 events
    (signals, L2/L3 abstains) and verifies every candidate has a disposition.
    """
    result = ComplianceResult(session_label)

    # Build candidate registry
    # key → candidate_id
    # value → dict with 'payload', 'signal', 'abstain' lists
    registry: Dict[str, dict] = {}

    all_events = l1_events + l2_events

    for event in all_events:
        etype = get_type(event)
        payload = get_payload(event)
        cid = payload.get("candidate_id")

        if etype == "candidate":
            cid = payload.get("candidate_id")
            if not cid:
                result.invalid_candidates.append(
                    "candidate event missing candidate_id entirely"
                )
                continue
            result.total_candidates += 1
            if cid not in registry:
                registry[cid] = {"payload": payload, "signals": [], "abstains": []}
            else:
                # Duplicate candidate_id — flag it
                result.invalid_candidates.append(
                    f"duplicate candidate_id {cid!r} emitted"
                )
            # Validate schema
            schema_issues = validate_candidate_schema(payload, cid)
            result.invalid_candidates.extend(schema_issues)

        elif etype == "signal":
            if not cid:
                result.invalid_signals.append("signal event missing candidate_id")
                continue
            result.total_signals += 1
            if cid not in registry:
                registry[cid] = {"payload": None, "signals": [], "abstains": []}
                result.orphan_signals.append(
                    f"signal for {cid!r} arrived before or without a matching candidate"
                )
            registry[cid]["signals"].append(payload)
            schema_issues = validate_signal_schema(payload, cid)
            result.invalid_signals.extend(schema_issues)

        elif etype == "abstain":
            if not cid:
                result.invalid_abstains.append("abstain event missing candidate_id")
                continue
            result.total_abstains += 1
            if cid not in registry:
                registry[cid] = {"payload": None, "signals": [], "abstains": []}
                result.orphan_signals.append(
                    f"abstain for {cid!r} arrived before or without a matching candidate"
                )
            registry[cid]["abstains"].append(payload)
            schema_issues = validate_abstain_schema(payload, cid)
            result.invalid_abstains.extend(schema_issues)

    # Walk registry: every candidate must have at least one signal or abstain
    for cid, entry in registry.items():
        if entry["payload"] is None:
            # signal/abstain appeared but candidate never showed up
            continue
        has_signal = len(entry["signals"]) > 0
        has_abstain = len(entry["abstains"]) > 0
        if not has_signal and not has_abstain:
            result.orphan_candidates.append(cid)

    return result


# ---------------------------------------------------------------------------
# Session discovery helpers
# ---------------------------------------------------------------------------

def sessions_in_range(root: str, start: date, end: date) -> List[Tuple[str, str, str]]:
    """
    Return list of (date_str, l1_path, l2_path) tuples for dates in [start, end]
    where at least the L1 events file exists.
    """
    sessions = []
    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        session_dir = os.path.join(root, date_str)
        l1_path = os.path.join(session_dir, "events.jsonl")
        l2_path = os.path.join(session_dir, "strategy_events.jsonl")
        if os.path.exists(l1_path):
            sessions.append((date_str, l1_path, l2_path))
        current += timedelta(days=1)
    return sessions


def discover_all_sessions(root: str) -> List[Tuple[str, str, str]]:
    """
    Walk the sessions root and return all (date_str, l1_path, l2_path) where
    events.jsonl exists.  Directories not matching YYYY-MM-DD are ignored.
    """
    sessions = []
    if not os.path.isdir(root):
        return sessions
    for entry in sorted(os.listdir(root)):
        session_dir = os.path.join(root, entry)
        if not os.path.isdir(session_dir):
            continue
        # Basic date-format check
        parts = entry.split("-")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            continue
        l1_path = os.path.join(session_dir, "events.jsonl")
        l2_path = os.path.join(session_dir, "strategy_events.jsonl")
        if os.path.exists(l1_path):
            sessions.append((entry, l1_path, l2_path))
    return sessions


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DEFAULT_SESSIONS_ROOT = r"C:\seasonals\cockpit\sessions"


def run(args: argparse.Namespace) -> int:
    sessions: List[Tuple[str, str, str]] = []

    if args.l1_file:
        # Single explicit file pair
        l2_path = args.l2_file or os.path.join(
            os.path.dirname(args.l1_file), "strategy_events.jsonl"
        )
        sessions.append(("explicit", args.l1_file, l2_path))

    elif args.date:
        try:
            d = date.fromisoformat(args.date)
        except ValueError:
            print(f"[ERROR] --date must be YYYY-MM-DD, got {args.date!r}")
            return 1
        l1_path = os.path.join(args.sessions_root, args.date, "events.jsonl")
        l2_path = os.path.join(args.sessions_root, args.date, "strategy_events.jsonl")
        sessions.append((args.date, l1_path, l2_path))

    elif args.start and args.end:
        try:
            start = date.fromisoformat(args.start)
            end = date.fromisoformat(args.end)
        except ValueError as exc:
            print(f"[ERROR] --start/--end must be YYYY-MM-DD: {exc}")
            return 1
        if start > end:
            print("[ERROR] --start must be <= --end")
            return 1
        sessions = sessions_in_range(args.sessions_root, start, end)
        if not sessions:
            print(f"[WARN] No sessions found in {args.sessions_root} for {args.start} to {args.end}")
            return 0

    else:
        # Default: discover all sessions under sessions_root
        sessions = discover_all_sessions(args.sessions_root)
        if not sessions:
            print(f"[WARN] No sessions found under {args.sessions_root}")
            print("       Run V2_5 in Historical or Realtime mode to generate events.jsonl files.")
            return 0

    total_result = ComplianceResult("ALL SESSIONS COMBINED")
    all_pass = True

    for date_str, l1_path, l2_path in sessions:
        if not os.path.exists(l1_path):
            print(f"[SKIP] {date_str}: L1 file not found at {l1_path}")
            continue

        l1_events = load_jsonl(l1_path)
        l2_events = load_jsonl(l2_path) if os.path.exists(l2_path) else []

        if not l2_events and os.path.exists(l2_path) is False:
            print(f"[INFO] {date_str}: No strategy_events.jsonl found. "
                  "L2/L3 may not be running. Checking L1-only invariants.")

        result = check_session(l1_events, l2_events, date_str)
        result.print_summary(verbose=args.verbose)

        # Accumulate
        total_result.total_candidates += result.total_candidates
        total_result.total_signals += result.total_signals
        total_result.total_abstains += result.total_abstains
        total_result.orphan_candidates.extend(result.orphan_candidates)
        total_result.invalid_candidates.extend(result.invalid_candidates)
        total_result.invalid_signals.extend(result.invalid_signals)
        total_result.invalid_abstains.extend(result.invalid_abstains)

        if not result.is_compliant:
            all_pass = False

    if len(sessions) > 1:
        print("\n" + "="*60)
        print("AGGREGATE ACROSS ALL SESSIONS")
        print("="*60)
        print(f"  Sessions processed:     {len(sessions)}")
        total_result.print_summary(verbose=args.verbose)

    if all_pass:
        print("\n[PASS] Contract compliance: FULL. Ready for sim-trade promotion.")
        return 0
    else:
        print("\n[FAIL] Contract violations detected. DO NOT promote to sim-trade.")
        return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="test_contract_compliance.py",
        description=(
            "V2_5 prime-directive contract validator.\n"
            "Asserts: every candidate event has a matching signal or abstain.\n"
            "Reads JSONL files produced by AMTradeCockpitV2_5 and AMTradeStrategyV1."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--sessions-root",
        default=DEFAULT_SESSIONS_ROOT,
        metavar="PATH",
        help=f"Root folder containing YYYY-MM-DD session subdirs (default: {DEFAULT_SESSIONS_ROOT})",
    )
    p.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="Validate a single session date.",
    )
    p.add_argument(
        "--start",
        metavar="YYYY-MM-DD",
        help="Start of date range (inclusive). Use with --end.",
    )
    p.add_argument(
        "--end",
        metavar="YYYY-MM-DD",
        help="End of date range (inclusive). Use with --start.",
    )
    p.add_argument(
        "--l1-file",
        metavar="PATH",
        help="Explicit path to L1 events.jsonl file (overrides date/range logic).",
    )
    p.add_argument(
        "--l2-file",
        metavar="PATH",
        help="Explicit path to strategy_events.jsonl. Defaults to same dir as --l1-file.",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print details of orphan signals / extra info.",
    )
    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))
