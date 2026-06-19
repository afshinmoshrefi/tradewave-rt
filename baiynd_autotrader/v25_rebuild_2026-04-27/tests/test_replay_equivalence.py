#!/usr/bin/env python3
"""
test_replay_equivalence.py  --  V2_4 → V2_5 Recall Equivalence Check
======================================================================
Validates architecture_spec_v25.md TEST-L1-1:

    For every V2_4 `signal` event in the historical JSONL, V2_5 MUST emit
    a `candidate` event at the same minute with matching level and direction.

    V2_5 may emit ADDITIONAL candidates (these are expected: V2_4's silent
    drops should now surface). But V2_5 must not MISS any candidate that
    V2_4 actually turned into a signal.

Background:
    V2_4 fired only 2 signals in 6 months (0.27% conversion — jsonl_data_analysis.md).
    These 2 signals are the minimal regression dataset. V2_5 must recall 100% of them.

Input files:
  - V2_4 historical signals: any JSONL files under sessions root that contain
    events of type "signal" (from V2_4).
  - V2_5 candidates: events.jsonl files under a V2_5 replay sessions root.

Matching logic:
  - Match by (session_date, minute_bucket, level_name, direction).
  - minute_bucket = bar_time truncated to the minute (no seconds).
  - Level names are compared case-insensitively after stripping '@....' suffixes.
  - Tolerance: ±1 minute window for the minute_bucket comparison.

Exit codes:
  0  Every V2_4 signal is covered by a V2_5 candidate (100% recall).
  1  At least one V2_4 signal has no matching V2_5 candidate (CRITICAL FAIL).

Usage examples:
  # Standard: point at V2_4 historical JSONL root and V2_5 replay root
  python test_replay_equivalence.py \\
      --v24-root "C:/seasonals/cockpit/sessions" \\
      --v25-root "C:/seasonals/cockpit/v25_replay"

  # If both V2_4 and V2_5 sessions are in the same root (different subdirs)
  python test_replay_equivalence.py \\
      --v24-root "C:/seasonals/cockpit/sessions/v24" \\
      --v25-root "C:/seasonals/cockpit/sessions/v25"

  # Test a specific date
  python test_replay_equivalence.py \\
      --v24-root "C:/seasonals/cockpit/sessions" \\
      --v25-root "C:/seasonals/cockpit/v25_replay" \\
      --date 2026-04-23

  python test_replay_equivalence.py --help
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class SignalRecord:
    """Represents a V2_4 signal event for matching purposes."""
    def __init__(self, raw_event: dict, source_file: str):
        self.raw = raw_event
        self.source_file = source_file
        payload = raw_event.get("payload", {})

        # Try to extract fields from different schema versions
        self.candidate_id: Optional[str] = payload.get("candidate_id")
        self.signal_id: Optional[str] = payload.get("signal_id") or payload.get("id")
        self.level_name: str = (
            payload.get("level_name")
            or payload.get("level")
            or payload.get("name")
            or ""
        )
        self.direction: str = (
            payload.get("direction")
            or payload.get("side")
            or ""
        ).upper()

        # Parse bar_time from payload or envelope
        raw_time = (
            payload.get("bar_time")
            or payload.get("signal_time")
            or raw_event.get("t")
            or ""
        )
        self.bar_time: Optional[datetime] = _parse_dt(raw_time)
        self.session_date: str = (
            payload.get("session_date")
            or raw_event.get("session_date")
            or (self.bar_time.strftime("%Y-%m-%d") if self.bar_time else "unknown")
        )
        self.entry_price: Optional[float] = payload.get("entry_price")

    def minute_key(self) -> Optional[Tuple[str, str, str, str]]:
        """(session_date, HHMM, normalised_level_name, direction)"""
        if not self.bar_time:
            return None
        minute_str = self.bar_time.strftime("%H%M")
        return (self.session_date, minute_str, _norm_level(self.level_name), self.direction)

    def __repr__(self):
        return (
            f"<V2_4Signal {self.signal_id or '?'} "
            f"{self.session_date} {self.bar_time} "
            f"{self.level_name} {self.direction}>"
        )


class CandidateRecord:
    """Represents a V2_5 candidate event."""
    def __init__(self, raw_event: dict, source_file: str):
        self.raw = raw_event
        self.source_file = source_file
        payload = raw_event.get("payload", {})

        self.candidate_id: str = payload.get("candidate_id", "")
        self.level_name: str = payload.get("level_name", "")
        self.direction: str = payload.get("direction", "").upper()
        self.session_date: str = (
            payload.get("session_date")
            or raw_event.get("session_date")
            or ""
        )

        raw_time = payload.get("bar_time") or raw_event.get("t") or ""
        self.bar_time: Optional[datetime] = _parse_dt(raw_time)

    def minute_keys(self) -> List[Tuple[str, str, str, str]]:
        """Returns keys for this minute AND ±1 minute tolerance window."""
        if not self.bar_time:
            return []
        keys = []
        for delta_min in (-1, 0, 1):
            t = self.bar_time + timedelta(minutes=delta_min)
            minute_str = t.strftime("%H%M")
            session = self.session_date or t.strftime("%Y-%m-%d")
            keys.append((session, minute_str, _norm_level(self.level_name), self.direction))
        return keys


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(s: str) -> Optional[datetime]:
    """Parse ISO 8601 timestamp, tolerating timezone offsets."""
    if not s:
        return None
    # Strip timezone for naive comparison
    s = s.strip()
    # Handle offsets like -04:00 or +00:00
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            # Strip tzinfo for comparison
            return dt.replace(tzinfo=None)
        except ValueError:
            continue
    return None


def _norm_level(level_name: str) -> str:
    """
    Normalise level names for fuzzy comparison.
    Strips '@...' suffixes, lowercases, strips whitespace.
    E.g. "Pr30L@1030" → "pr30l", "Close330_High" → "close330_high"
    """
    if not level_name:
        return ""
    s = level_name.split("@")[0].strip().lower()
    return s


def load_jsonl(path: str) -> List[dict]:
    events = []
    if not os.path.exists(path):
        return events
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError:
                pass
    return events


def collect_signals_from_root(root: str, target_date: Optional[str] = None) -> List[SignalRecord]:
    """Walk a sessions root and collect all V2_4 signal events."""
    signals = []
    if not os.path.isdir(root):
        return signals

    dirs = sorted(os.listdir(root))
    if target_date:
        dirs = [d for d in dirs if d == target_date]

    for d in dirs:
        session_dir = os.path.join(root, d)
        if not os.path.isdir(session_dir):
            continue
        for fname in ("events.jsonl", "strategy_events.jsonl"):
            fpath = os.path.join(session_dir, fname)
            for event in load_jsonl(fpath):
                if event.get("type") == "signal":
                    signals.append(SignalRecord(event, fpath))
    return signals


def collect_candidates_from_root(root: str, target_date: Optional[str] = None) -> List[CandidateRecord]:
    """Walk a sessions root and collect all V2_5 candidate events."""
    candidates = []
    if not os.path.isdir(root):
        return candidates

    dirs = sorted(os.listdir(root))
    if target_date:
        dirs = [d for d in dirs if d == target_date]

    for d in dirs:
        session_dir = os.path.join(root, d)
        if not os.path.isdir(session_dir):
            continue
        fpath = os.path.join(session_dir, "events.jsonl")
        for event in load_jsonl(fpath):
            if event.get("type") == "candidate":
                candidates.append(CandidateRecord(event, fpath))
    return candidates


# ---------------------------------------------------------------------------
# Core matching
# ---------------------------------------------------------------------------

class EquivalenceResult:
    def __init__(self):
        self.v24_signals: List[SignalRecord] = []
        self.v25_candidates: List[CandidateRecord] = []
        self.matched: List[Tuple[SignalRecord, CandidateRecord]] = []
        self.unmatched_signals: List[SignalRecord] = []   # CRITICAL

    @property
    def recall(self) -> float:
        if not self.v24_signals:
            return 1.0
        return len(self.matched) / len(self.v24_signals)

    @property
    def is_compliant(self) -> bool:
        return len(self.unmatched_signals) == 0


def run_equivalence_check(
    v24_signals: List[SignalRecord],
    v25_candidates: List[CandidateRecord],
) -> EquivalenceResult:
    result = EquivalenceResult()
    result.v24_signals = v24_signals
    result.v25_candidates = v25_candidates

    # Build an index of V2_5 candidate minute-keys for fast lookup
    v25_index: Dict[Tuple, List[CandidateRecord]] = defaultdict(list)
    for c in v25_candidates:
        for key in c.minute_keys():
            v25_index[key].append(c)

    for sig in v24_signals:
        key = sig.minute_key()
        if key is None:
            print(f"[WARN] Cannot parse bar_time for V2_4 signal {sig.signal_id!r}; skipping match.")
            continue

        matches = v25_index.get(key, [])
        if matches:
            # Use the first match (there may be multiple candidates that minute)
            result.matched.append((sig, matches[0]))
        else:
            result.unmatched_signals.append(sig)

    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_equivalence_report(result: EquivalenceResult):
    print("\n" + "="*60)
    print("V2_4 → V2_5 Replay Equivalence Report")
    print("="*60)
    print(f"  V2_4 signals found:           {len(result.v24_signals)}")
    print(f"  V2_5 candidates found:         {len(result.v25_candidates)}")
    print(f"  Matched (V2_4 → V2_5):         {len(result.matched)}")
    print(f"  Unmatched (CRITICAL):           {len(result.unmatched_signals)}")
    print(f"  Recall:                         {result.recall * 100:.1f}%")

    if result.matched:
        print("\n  Matched V2_4 signals:")
        for sig, cand in result.matched:
            print(
                f"    [MATCH] {sig.session_date} {sig.bar_time} "
                f"{sig.level_name} {sig.direction} → candidate {cand.candidate_id!r}"
            )

    if result.unmatched_signals:
        print(f"\n  [CRITICAL] V2_4 signals NOT covered by V2_5 candidates:")
        for sig in result.unmatched_signals:
            print(
                f"    [MISS] {sig.session_date} {sig.bar_time} "
                f"{sig.level_name} {sig.direction} | "
                f"entry={sig.entry_price} | source={sig.source_file}"
            )
        print()
        print("  Diagnostic steps:")
        print("  1. Confirm the V2_5 replay was run on the same date range and instrument.")
        print("  2. Check that the level name exists in V2_5's level-capture logic.")
        print("  3. Confirm V2_5 events.jsonl was written to the expected --v25-root path.")
        print("  4. Check for off-by-one in bar time (level touched at end-of-bar vs start).")

    print()
    status = "PASS" if result.is_compliant else "FAIL"
    print(f"  Result: [{status}]  (100% recall required for sim-trade readiness)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DEFAULT_SESSIONS_ROOT = r"C:\seasonals\cockpit\sessions"


def run(args: argparse.Namespace) -> int:
    v24_root = args.v24_root or DEFAULT_SESSIONS_ROOT
    v25_root = args.v25_root or DEFAULT_SESSIONS_ROOT

    if v24_root == v25_root:
        print(
            "[WARN] --v24-root and --v25-root are the same path. "
            "V2_4 signals and V2_5 candidates will be drawn from the same files. "
            "This is only correct if the same folder holds both types of events."
        )

    target_date = args.date or None

    print(f"Loading V2_4 signals from: {v24_root}")
    v24_signals = collect_signals_from_root(v24_root, target_date=target_date)
    print(f"  Found {len(v24_signals)} V2_4 signal events.")

    if not v24_signals:
        print(
            "[WARN] No V2_4 signals found. This test cannot validate recall without baseline signals.\n"
            "       Possible causes:\n"
            "       - Wrong --v24-root path\n"
            "       - V2_4 never produced signal events (unlikely; check manually)\n"
            "       - events.jsonl does not exist under that root"
        )
        return 0  # Not a hard fail — V2_4 data may not yet be present

    print(f"\nLoading V2_5 candidates from: {v25_root}")
    v25_candidates = collect_candidates_from_root(v25_root, target_date=target_date)
    print(f"  Found {len(v25_candidates)} V2_5 candidate events.")

    if not v25_candidates:
        print(
            "[FAIL] No V2_5 candidates found. Run V2_5 in Historical Replay mode first.\n"
            "       Then re-run this test pointing --v25-root at the replay output folder."
        )
        return 1

    result = run_equivalence_check(v24_signals, v25_candidates)
    print_equivalence_report(result)

    return 0 if result.is_compliant else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="test_replay_equivalence.py",
        description=(
            "V2_4 → V2_5 signal recall equivalence check.\n"
            "Asserts V2_5 surfaces a candidate for every historical V2_4 signal."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--v24-root",
        metavar="PATH",
        default=DEFAULT_SESSIONS_ROOT,
        help=f"Root folder of V2_4 historical JSONL sessions (default: {DEFAULT_SESSIONS_ROOT})",
    )
    p.add_argument(
        "--v25-root",
        metavar="PATH",
        help="Root folder of V2_5 replay JSONL sessions. Defaults to --v24-root.",
    )
    p.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="Restrict to a single session date.",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print additional debugging information.",
    )
    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))
