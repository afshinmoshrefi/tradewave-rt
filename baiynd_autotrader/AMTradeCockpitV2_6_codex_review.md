# AMTradeCockpitV2_6 Codex Review

Date: 2026-05-01

## Scope

- Indicator reviewed: `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMTradeCockpitV2_6.cs`
- Baseline preserved: `AMTradeCockpitV2_5.cs`
- Trading posture: informational L1 cockpit only. No live order routing should exist in this indicator.

## Architecture Verdict

V6 is correctly shaped as an L1 detector/cockpit:

- It captures AM structural levels.
- It emits candidates and feature vectors.
- It displays pre-touch watch levels.
- It does not submit orders, stage orders, modify orders, or manage account state.
- L2 should score/filter candidates.
- L3 should own execution, risk, account state, lockouts, and kill-switch behavior.

The direction filter belongs in L1 as informational context only:

- Long day: visually anticipate long reversals only.
- Short day: visually anticipate short reversals only.
- Sideways day: visually anticipate both directions.
- Raw candidate emission should remain high-recall so L2/ML can learn from off-filter touches.

## Changes Made During Review

- Fixed the generated NinjaScript wrapper for `ShowPreTouchCandidateLevels`.
- The property now appears consistently in the indicator, Market Analyzer, and Strategy wrapper methods.
- Cache matching now includes `ShowPreTouchCandidateLevels`.
- New indicator instances created through generated wrappers now receive `ShowPreTouchCandidateLevels`.

## Static Tests Run

- V6 class/name/project include check: pass.
- V5 SHA256 unchanged: `5AA0A9052ECC197BC0D908669E82F25313DAFFD1AED751CCA7D4DBE8427BC897`.
- Brace balance: pass.
- NinjaScript property wrapper coverage: pass after patch.
- Direction contract checks: pass.
- No order-routing tokens found in V6: pass.
- Project compile attempted with local .NET Framework MSBuild: blocked because the project is SDK-style and this machine has no .NET SDK/MSBuild capable of loading it.

## High-Priority Trading Notes

1. `state.json` persistence is currently write-mostly.
   - `PersistStateJson()` writes level-watch state.
   - `TryRestoreStateJson()` only logs that state exists and does not rebuild `levelWatchStates`.
   - Do not rely on Pattern B continuity across a NinjaTrader restart until restore is implemented and tested.

2. Multiple chart instances can duplicate JSONL telemetry.
   - If V6 is loaded on both a 30-minute and 1-minute chart with logging enabled, both instances can write events.
   - For clean ML data, one instance should be the logging owner and other chart copies should be visual-only.

3. Compile still needs NinjaTrader validation.
   - The local shell cannot perform a real NT8 compile because no suitable .NET SDK/MSBuild is installed.
   - The next gate is NinjaTrader's own compile window.

## Next Safe Test Plan

1. Compile V6 in NinjaTrader.
2. Load V6 on one 1-minute chart with logging enabled.
3. Load V6 on any additional visual charts with `EnableJsonlLog = false`.
4. Verify the diagnostic panel shows `Direction filter`.
5. Confirm pre-touch labels:
   - Long: only `BUY WATCH`.
   - Short: only `SELL WATCH`.
   - Sideways: both `BUY WATCH` and `SELL WATCH`.
6. Confirm JSONL includes:
   - `direction_filter_change`
   - heartbeat `direction_filter`
   - candidate `f_direction_filter`
   - candidate `f_direction_filter_allows_candidate`

