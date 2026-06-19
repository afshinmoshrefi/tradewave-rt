# V2_4 Indicator Code Audit (Wave 2)

**File:** `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\AMTradeCockpitV2_4.cs` (4627 lines)
**Author of audit:** Wave 2 — code-review pass
**Date:** 2026-04-27

---

## TL;DR (5 bullets)

1. **The day-type gate the indicator advertises (V2_4 body-stack: LongTrend / ShortTrend / CautiousLong / CautiousShort / Sideways) is wired to a SECOND, parallel state (`currentDayType` — Congestion/Trending/Extended/Unknown) that is computed but never gates anything**, only logged in JSONL. The legacy `currentBias` (Long/Short/Neutral vs institutional) is in the same boat: cosmetic. The real gate is the inline `tradeMode`/`v2TrendDir` derivation in `Process1MinBar` at line 1579-1589.

2. **`V2ComputeStopDistance` was refactored to accept a `CandleBox anchor` (Pattern A = 9:30 candle, Pattern B = breach candle), but every caller passes nothing.** All three call sites (1954, 2113, 3330) invoke it with `()`, so the function falls back to europe-4AM-width clipped to `[0.30, 0.80] * ADR20`. The "stop = entry-trigger candle's width" rule AM teaches is **not implemented at all**. The `LevelWatchState` Pattern-B class (line 179) and `CheckPatternBEntry` are pure scaffolding — never invoked.

3. **Trend-mode exit is a 30-min SMA20 ratchet trail** (line 2646-2688), which contradicts AM's "level-to-level exits, NOT trailing." Fade-mode exits at a fixed `PrInst H/L` target (closer to AM's structural exit, but only one level deep — no scaling out, no level-to-level reassessment).

4. **CL has a real `rthOpenHour`/`rthOpenMinute` bug:** lines 853-854 hardcode `9 / 30` for *every* instrument including CL, but comments at lines 1428 and 1440 explicitly state CL opens at 9:00 ET. So CL's opening-range window, OR-lock cutoff, RTH window check, and 9:30 candle capture are **all running on ES/NQ-correct timing for CL** — i.e., CL gets a 30-minute OR starting at 9:30 instead of 9:00.

5. **JSONL "signal" event (line 2437-2452) is missing the actual fields that drove the trade:** day_type comes from `currentDayType` (the cosmetic enum), and `v2DayType` (the AM body-stack), `mocState`, `mocRatio`, `sma200SlopeDelta`, `tradeMode` (FADE vs TREND, **though `trade_mode` IS logged**) and the master-candle bodies are absent. Master-candle box H/L only land in `Log()` → NT Output window, never JSONL. Wave 3 dashboard analysts will see the wrong day-type next to each fired signal.

---

## 1. What V2_4 actually DOES — execution paths

### 1.1 Bar routing (`OnBarUpdate`, line 897)

- Refuses to act before `CurrentBars[BarsInProgress] >= 2`.
- On `BarsInProgress == 0` (primary) it only updates the two SMA plots from the **30-min** SMA50/SMA200 cached at lines 836-838. This means even on a 1-minute primary chart, the visual SMA lines reflect the 30-min trend gate (line 904-913).
- On `BarsInProgress == idx30Min`: calls `Process30MinBar()` (line 919), then logs a `bar_close` JSONL event in Realtime only.
- On `BarsInProgress == idx1Min`: calls `Process1MinBar()` (line 931), logs `bar_close`, and emits `phase_change` / `bias_change` deltas plus `MaybeHeartbeat` when subscribed (line 952).
- The whole `OnBarUpdate` body is wrapped in `try/catch` (line 956-963) — exceptions in non-historical state print, but otherwise silently swallow. **A bar-level bug never kills the indicator, which makes silent failures hard to detect by visual inspection.**

### 1.2 Process30MinBar (line 970) — box capture, MOC, SMA200 slope

The 30-min processor handles:

- **VWAP slope sample** (line 988-998). Just snapshots the live `currentVWAP` (computed in `Process1MinBar`) at 30-min boundaries; first 30-min bar after RTH open is forced to "Flat" because there's no comparable prior window.
- **RTH session H/L tracking** for next-day pivots (line 1001-1016).
- **Box archive at session close** (`closeHour:closeMinute` = `15:00` / `14:30 CL`, line 1021-1120). At session close: if `currentDay.Close330` exists, archive into `dayHistory`, run a daily diagnostic + performance summary (line 1046-1100), `ResetForNewDay()`, then re-init `currentDay` for the *new* trading day (Date+1).
- **GlobEx 6PM** capture at `h==18 && m==0` (line 1122).
- **Midnight** at `h==0 && m==0` (line 1131).
- **Europe 4AM** at `h==4 && m==0` (line 1140).
- **RTH 9:30** at `h==rthOpenHour && m==rthOpenMinute` (line 1149). Also captures `Sma200At930` and computes `Sma200SlopeDelta = today - priorSma200At930` (line 1168-1187). On a fresh session the slope is `NaN` and emits a "no prior baseline" log, deferring to next session.
- **Institutional-candle capture** (line 1207). Independent `if`, so on ES/NQ/GC it fires on the same bar as session-close (both at 15:00); on CL it fires earlier in the day (10:00, before the 14:30 close). Sets `Close330` (named "Close 3:30" or "Close 10:00") and unconditionally promotes it to `institutionalBox` (line 1215). `RunContainmentCheck` may later reassign institutionalBox to a wider enclosing box.
- **MOC validation** at the same time (line 1224-1243): `ratio = thisBarVol / priorBarVol`. `>1.20 → Green`, `>1.00 → Orange`, else `Gray`. Only `currentDay.MocState` and `currentDay.MocRatio` are populated. There's also a *legacy V2 MOC* at lines 1305-1313 that compares `15:00-15:30` vs `15:30-16:00` volumes and stuffs into `v2PriorInstValidated`; this V2 result **is never consumed by entry logic**. So MOC state is effectively *informational* even though there's a UI surface for it.
- **30-min SMA50/SMA200 direction** (line 1247-1267). Computes `slope50 = sma50 - sma50[5]`, `slope200 = sma200 - sma200[5]` and labels Up/Down/Flat. Used only for `DetermineDayType`, the diagnostic SMA-stack panel, and the legacy A1 alert.
- **30-min SMA20** for the trail (line 1270-1271).
- **Stop-update alert** (line 1274-1286) — when an Active trade's trail ratchets, fires `A8_StopUpdate_*` so the trader can move broker stop manually.
- **Rolling Pr30 H/L** (line 1293-1303). RTH-only — overnight 30m bars are skipped because the comment notes they don't align with visible bars on RTH-only charts. **Important: this means the first valid Pr30 candidate is the 9:30→10:00 bar, available from 10:00 onward.**
- **`UpdatePhase / DetermineDayType / DetermineBias`** (line 1316-1318). All three populate state that does *not* gate any V2_4 entry.
- **`RedrawActiveBoxes` + `UpdateCoachMessage`** at the end.

### 1.3 Process1MinBar (line 1362) — the live signal pipeline

Step-by-step:
1. **VWAP** (line 1374-1396). RTH-only session VWAP, reset on the first RTH 1-min bar of each day. Comment at lines 1374-1380 explicitly notes earlier versions reset at 18:00 and accumulated 24/7, baking 15h of overnight TP*vol into the 9:30 VWAP — that bug was fixed.
2. **Daily H/L tracking** for ADR20 (line 1398-1426). `v2DailyRanges` is a 20-deep queue of yesterday's `H-L`. On the day-rollover (when `barOpen.Date != v2TodayDate`), enqueues yesterday's range and recomputes `v2Adr20 = mean`. Resets `v2OpenRangeLocked`, `v2TouchedThisSession.Clear()`. **Note this `Clear()` is the canonical reset point for the per-session touched-level latch.**
3. **Opening range** (line 1429-1447). Tracks max/min over the first 30 min after `rthOpenHour`/`rthOpenMinute`; locks at exactly `rthOpenHour*60 + rthOpenMinute + 30`. **Bug for CL** — see §9.
4. **Demo signal** (line 1449-1467). One-shot synthetic LONG, gated to Realtime + RTH window.
5. `UpdatePhase`.
6. **9:30 RTH 1-min capture** (line 1472-1501). Captures `rth1MinHigh/Low/Volume`, decides "low vol → wait for 2nd min" via `ESVolumeThreshold` / `NQVolumeThreshold`. Also captures `currentDay.RTH930OpenPx` (the price at 9:30:00 ET) — this is the preliminary day-type proxy used by `ClassifyAMDayType` between 9:30 and 10:00.
7. **2nd-minute confirmation** (line 1504-1512). If 9:30 was low-vol, expand the 1-min range with the 9:31 bar.
8. **1-min SMA direction** (line 1517-1559) — diagnostic only, plus a 50/200 cross-detection that draws a green/red diamond.
9. **Anchored VWAP** (line 1561-1565). `V2UpdateAnchoredVWAP` — TPV/Vol since the institutional candle's `StartTime`, re-anchors when `RunContainmentCheck` promotes a different box.
10. **Day-type & trade-mode derivation** (line 1567-1599) — the actual gate:
    ```
    AMDayType v2DayType = ClassifyAMDayType();
    string tradeMode = ...;   // "TREND" / "FADE" / null
    string v2TrendDir = ...;  // "LONG" / "SHORT" / null
    ```
11. **canTrade** (line 1627-1633): `v2TrendDir != null && tradeMode != null && inRthWindow && (None|Pending) && signalsToday < effSignalCap && !lockoutActive && !IsInCooldown()`.
12. **CheckEntry** (line 1635-1636) when `canTrade`.
13. **Pre-Place panel update** (line 1639) — `V21UpdatePrePlace`.
14. **MonitorSignal** (line 1645-1646) when `Pending` or `Active`.
15. **CheckPriceAlerts** (line 1649-1650) when 9:00–16:00.
16. `UpdateCoachMessage`.

### 1.4 Signal lifecycle

- `SetSignal` (line 2391) → `Pending` + `signalsToday++`. Draws Sig_Entry / Sig_Stop / Sig_Target (FADE only) / arrow. Fires `OnSignal` event, logs JSONL "signal", shows Staging Card in Realtime only.
- `MonitorSignal` (line 2513):
  - **Pending phase** (2519-2598): cancel-at-cutoff (`closeMinute - 30`) → set `None`; ignore same-bar fills (line 2542); approach-hint at 25% of stop distance (line 2549-2558); fill check `low<=entry` (long) or `high>=entry` (short); on fill double-checks the cutoff (line 2569) before transitioning to Active; arms firewall, hides staging card, fires "cancel others" alert.
  - **Active phase** (2600+):
    - **Hard-stop intrabar** (2601-2617). Records "Stopped", goes `None`, sets `lastStopTime` (Realtime only), fires A6, calls `CheckDayDone`.
    - **FADE target** (2623-2641). Intrabar touch of `signalTarget` records "Target", `None`.
    - **TREND trail** (2643-2689). Arms when `sma20_30min` is on the favorable side of entry, then ratchets monotonically. Exit on **1-min CLOSE past trail** (not intrabar poke).
    - **Hard time-close** at `closeHour:closeMinute` (2691-2719). Includes a T-60s warning alert.
- `RecordAndDrawTrade` (2722) appends to `tradeHistory`, computes per-contract qty (Gray=0 forced to 1, "1 MES ONLY"=1, else 2), accumulates `realizedPnlDollarsToday`/`losingTradesToday` **only in Realtime** (line 2754-2759), then `CheckLockout`.

---

## 2. Wired vs scaffolded

### `LevelWatchState` and `CheckPatternBEntry`

- Class declared at line 179-200 with full lifecycle (Untouched/Breached/Armed/Consumed/Invalidated), breach-candle capture, hold-higher-low confirmation, and an `AnchorCandle` field.
- Comment at line 174 says "Implementation lands in the next batch (CheckPatternBEntry on Process1MinBar). Class scaffolding placed here in this batch so the storage and refactor surface are agreed-upon before the entry-mechanism rewrite."
- **No `CheckPatternBEntry` method exists in the file** (grep at line 174 is the only hit on that name). No method instantiates `LevelWatchState`. No code path uses the breach detection.
- Net effect: V2_4 has no Pattern B "look-below-and-fail" entry. The only entry pattern wired is **Pattern A: limit at level on retracement** in `CheckEntry`.

### `V2ComputeStopDistance(CandleBox anchor = null)`

- Signature accepts an anchor, with thoughtful logic (line 2174-2213):
  - If anchor is contained by today's `Close330` (prior 3:30) → promote to `Close330`.
  - Else if contained by today's `RTH930` → promote to `RTH930`.
  - Width = effective box's `High - Low`.
  - Clip to `[0.30, 0.80] * ADR20`.
  - Fallback: if no anchor and ADR is NaN, use europe-width unclipped.
- **All three call sites pass nothing** (line 1954 in `CheckEntry`, line 2113 in `V21UpdatePrePlace`, line 3330 in `RenderComingUpTimeline`). Therefore:
  - `effective = anchor = null` always.
  - The bigger-candle-exception block (2178-2193) is dead code in production.
  - Width = `currentDay.Europe4AM.High - currentDay.Europe4AM.Low` always (the `else if` branch on line 2198), then clipped to `[0.30*ADR, 0.80*ADR]`.
- **AM's stated rule "stop = the width of the entry-trigger candle, 2× on sideways"** is *not* implemented anywhere. The V2_4 stop is europe-4AM-width-with-ADR-clip — a fixed-per-day stop shared across all signals, regardless of which candle triggered.

### `currentDayType` and `currentBias`

- `DetermineDayType` (line 1739) maps `(smaDirection30, vwapSlope, pivot extension)` → Congestion/Trending/Extended/Unknown. Called every 30-min bar (line 1317).
- `DetermineBias` (line 1767) maps price vs institutional box High/Low → Long/Short/Neutral.
- **Neither value gates entry, sizing, or any signal logic.** They appear in:
  - Coach messages (`BiasStr` for the A1 alert, `DayTypeStr` is unused in any alert wording grepped).
  - JSONL logs ("day_type" in heartbeat/signal events; "bias" in heartbeat/bias_change).
  - The `currentDayType = Congestion` set inside `RunContainmentCheck` (line 1712) when partial overlaps ≥ 2 — also informational only.
- **This is a confusing-for-Wave-3 footgun**: the `day_type` field in JSONL signal records is the legacy enum, NOT the AM body-stack `v2DayType` that actually drove the trade. Anyone correlating fired signals to day-types in the JSONL stream will be reading the wrong axis.

### Other deferred items

- Live ATM submission: `OnStageClicked` (line 3947) logs the ticket; `AllowLiveOrderSubmit=true` only emits a "deferred" log (line 3962). No `Account.CreateOrder + Submit` exists. STAGE is a logging surface only — the trader manually places the ATM via ChartTrader.
- `IsBoxChipOn` (line 3747): always returns `true`. The chip-toggle UI was removed in "Step 1 rebuild" but the call site is preserved.
- The **legacy V2 MOC** (`v2MOCFirstHalfVol`/`v2MOCSecondHalfVol`/`v2PriorInstValidated`, lines 487-489, 1305-1313) is computed but never read.
- The plot outputs (`Values[0]`, `Values[1]`) are written but represent 30-min SMA50/200, which most users would not realize (line 904-913 comment).
- ML hook is mentioned in the file header (line 19-20) but not present.

---

## 3. Trade selection logic — TREND vs FADE

### Candidate pool

`CheckEntry` (line 1787) only runs when `tradeMode != null && v2TrendDir != null`. The candidate list depends on `tradeMode`:

**FADE mode** (line 1802-1817): ONLY structural extremes, on the trend-correct side of slope. Exactly 3 candidates (per direction):
- `GlobExL` / `GlobExH` (today's GlobEx 6PM box)
- `EuropeL` / `EuropeH` (today's Europe 4AM box)
- `PrInstL` / `PrInstH` (today's prior-3:30 institutional candle)

Note FADE explicitly excludes ORH/ORL, Pr30, SMA50/200, VWAP/AnchVWAP, MidMid (comment at line 1804-1807 says these are continuation tools, not for fades).

**TREND mode** (line 1818-1885): Up to ~16 candidates per direction:
- `GlobExH/L` (line 1822-1826)
- `MidMid` — midpoint of the Midnight box (1828-1831)
- `EuropeH/L` (1832-1836)
- `OR30H/L` — high/low of the 30-min RTH 9:30 box (1837-1841) — only available after 10:00
- `PrInstH/L` — today's `Close330` H/L (1843-1852)
- `ORH/ORL` — opening-range high/low, only added after `v2OpenRangeLocked` (1855-1859)
- `Pr30H/L@HHmm` — rolling prior-30-min H/L, with bar-close stamp baked into the latch key so each new 30m roll is a fresh candidate (1864-1870)
- `SMA50_30`, `SMA200_30` — 30-min SMAs (1883-1884)
- **VWAP and AnchVWAP intentionally excluded** (1872-1880). Per AM "VWAP/AVWAP are permissions, not limit-order destinations." They are drawn as horizontal lines but never act as candidates.

### Filter chain inside `CheckEntry`

For each candidate `(name, px)` (line 1899-1948):
1. **Range filter**: `if (px < low || px > high) continue;` — only levels inside the 1-min bar's H–L are scored.
2. **Pre-gate touch JSONL** is emitted for every level inside the bar range (1911-1921) — BEFORE the filters. This is the recall feed for the Python event-builder comparison.
3. **Pre-gate `OnTouch` event** is also fired here (1926-1943), so a hosting Strategy can see all touched levels.
4. **Latch filter**: `if (latched) continue;` — `v2TouchedThisSession` is a per-session HashSet; once a level fires, it's done for the day.
5. **Retrace-side filter**: `wouldRetrace = isLong ? (px < barOpen) : (px > barOpen)`. Continuation breakouts are dropped — long entries must pull DOWN to support, shorts must pull UP to resistance.
6. **Tie-break**: closest to bar open wins (`bestDist = Math.Abs(px - barOpen)`).

After best-level pick:
7. **Stop computation**: `stopDist = V2ComputeStopDistance()`. If `<=0`, return without firing (1955).
8. **FADE target sanity check** (1965-1976): if PrInst H/L is not in the profit direction from entry, *skip the trade entirely* (Log "FADE skip"). This means an AM-perfect setup at an extreme can be silently dropped if today's prior-inst happens to be on the wrong side of entry — a quiet "missing setup" path.
9. Latch the level, strip the `@HHmm` suffix, increment `diagRetestCount`.
10. `SetSignal` (also runs in Historical, but `Realtime`-gated side effects are inside).

### Where a valid AM setup can get DROPPED

| Step | Filter | Possible miss |
|---|---|---|
| `canTrade` outer gate | `v2TrendDir != null && tradeMode != null` | Sideways + flat 200-SMA produces null `tradeMode` → silent no-fire all session. Pre-RTH the day-type is `Unknown` → also no-fire (correct). |
| `inRthWindow` | `nowTotalMin < lastEntryTotalMin = closeHour*60+closeMinute - 30` | Last 30 min of session not eligible for new entries. Late legitimate setups dropped. |
| `signalsToday < effSignalCap` | FADE caps at `Min(2, MaxSignalsPerDay)`, TREND at full `MaxSignalsPerDay` (default 3) | A 4th valid setup is silently ignored. Counter-intuitive: pending counts toward cap (line 588-590 explicit), so a cancelled limit still consumed budget. |
| `lockoutActive` | Daily-loss / losing-trades lockout | Trades blocked rest of session (correct). |
| `IsInCooldown()` | Last stop within `CooldownMinutes` | If user took a sim stop, real entries may be blocked. Note: `lastStopTime` is set Realtime-only (line 2609), so historical replays don't pollute. |
| `currentSignalState != None && != Pending` | One position at a time. A pending replaces an older pending (line 2395-2399). |
| Range filter | `px ∈ [low, high]` | Only fires on the 1-min bar that prints through the level. If price gaps the level, it's missed (no closing-bar scoring). |
| Latch filter | First-touch-per-session per-name | Re-tests of a level after the first touch will not fire. **For Pr30, the bar-close stamp (`@HHmm`) is appended so each fresh 30m roll resets the latch — but for static levels (PrInstH, GlobExH, etc.) one touch ends them for the day.** |
| Retrace-side filter | `wouldRetrace = isLong ? px<barOpen : px>barOpen` | Perfectly valid retest from the *same side as bar open* (e.g., a 1-min bar opening below the level then touching it from above) is dropped because `px < barOpen` would be false. **Edge case: a level touched at exactly bar open is also dropped** (`<` is strict). |
| Best-pick (closest to open) | A bar with multiple in-range candidates picks one and latches *all* … no — it only latches `bestName` (line 1978). The OTHER in-range levels remain non-latched and can fire on subsequent bars. **But:** the JSONL pre-gate "touch" event fires for every in-range level, so recall data still flows. |
| FADE target check | `if (!profitable) return` | Drops valid AM fade setups when PrInst is on wrong side of bar (silent). |
| `V2ComputeStopDistance() <= 0` | Returns 0 if no Europe box AND no ADR | Pre-Europe-capture (i.e., before 4 AM) entries cannot fire — but this is during `EuropeOpen` phase before RTH so unlikely to hit. |

A high-impact source of missed setups: **TREND-mode ORH/ORL only enter the candidate pool after `v2OpenRangeLocked = true`** (line 1855), which happens at exactly RTH+30min. So a touch of the OR mid-formation (still extending the OR) won't fire — but neither would AM trade it. More subtle: **VWAP and AnchVWAP are explicitly removed from the candidate pool** (line 1872-1880). If AM's actual rule treats VWAP retests as valid trade triggers (the user asked about this), V2_4 will not fire on VWAP touches. The only VWAP visibility is the chart line + JSONL heartbeat field.

Another quiet drop path: **In `Process30MinBar`'s rolling-Pr30 block, only RTH bars set Pr30 H/L** (line 1297). The very first bar of the new RTH session (9:30→10:00) has no prior Pr30 — that level isn't available until 10:00 onward. The first 30 minutes after RTH open also have no `OR30H/L` (the 30-min 9:30 box is null until 10:00). So **the first 30 min of RTH only have GlobEx/Europe/Midnight/PrInst as candidates**, and ORH/ORL aren't even available until exactly 10:00.

---

## 4. Stop computation vs AM's rule

### What V2_4 actually does (`V2ComputeStopDistance`, line 2174)

Effectively, due to all callers passing no anchor:
```
width = europe4AM.High - europe4AM.Low
if ADR20 valid:
    return clip(width, 0.30*ADR20, 0.80*ADR20)
else:
    return width  (or 0)
```

This is **a single fixed stop distance for the whole day**, used for every TREND or FADE signal. ADR20 only updates at the day rollover.

### What AM teaches

- "The stop is always the width of the entry-trigger candle." — apr-16, apr-24
- "On sideways, use 2× width." — implication
- For Pattern B: "Stop = breach candle's full range." — line 168 self-comment
- Bigger-candle exception: when the trigger candle is contained by a larger structural candle (Close330 or RTH930), use the bigger candle's range — line 2156-2173 self-comment.

### Discrepancies

1. **Per-trigger stop is not implemented.** The function signature supports it but no caller passes an anchor. Every trade gets europe-4AM-width clipped to ADR.
2. **Sideways 2× rule is not implemented.** FADE mode (which is the sideways path) computes the same stop as TREND.
3. **The bigger-candle exception is dead code** — only applies if anchor is non-null.
4. **`europe4AM` may be smaller than the true entry candle** (e.g., the 9:30 RTH bar may be much wider) — the resulting stop can be illogically tight for trades anchored on a wider 9:30 candle.
5. **`europe4AM` may be much wider than the entry candle** — yielding an over-large stop on a tight retracement. ADR clip mitigates but doesn't replicate the per-trigger rule.

### Display side-effects

- The Pre-Place Panel displays `v21StopPts = V2ComputeStopDistance()` at panel-build time (line 2113). All listed levels share that one stop, which lines up with a "europe-width" mental model but not with "per-candle width." If the user reasons about risk per setup, the panel under-states variation.
- The Staging Card uses the same stop-distance mid-trade (`Math.Abs(signalEntry-signalStop)`), so what the trader sees matches the indicator's actual stop, just not AM's intent.

---

## 5. Exit logic vs AM's rule

### TREND mode exit (`MonitorSignal` line 2643-2689)

- Wait for `sma20_30min` (30-min SMA20) to be on the favorable side of entry → `v2SignalTrailArmed = true`, `v2SignalTrail = sma20_30min`.
- Each subsequent 30-min bar: if SMA20 moved further in trade direction, ratchet the trail.
- Exit when **1-min bar closes past the trail** (line 2671). NOT intrabar.
- Recorded as "Trail" win/loss, draws "Sig_Trail" line in gold dotted.

### FADE mode exit (`MonitorSignal` line 2623-2641)

- `signalTarget` is the opposite side of `currentDay.Close330` (PrInst H/L), set in `CheckEntry` line 1968.
- Intrabar touch of target → "Target" win, exit.
- No trailing.

### Hard exits (both modes)

- Intrabar hard stop (line 2601-2617).
- Hard time-close at `closeHour:closeMinute` (15:00 ET / 14:30 CL) — line 2705-2719. Result tagged "TimeClose."
- T-60s warning alert one bar earlier (line 2697-2703).

### Discrepancies vs AM "level-to-level exits"

AM's stated rule (per project docs) is to take partials at the next major level, then re-assess. V2_4 has:
- **No scaling out.** A position is fully open until trail/stop/target/timeclose, all-or-nothing.
- **TREND uses a continuous trail** (SMA20 ratchet), not "exit at next level then reassess." Comments throughout the file refer to "level-to-level" but the implementation is a moving-average trail.
- **FADE uses a one-and-done structural target** (PrInstH or PrInstL). This is closer to AM's structural exit but only one level deep — there's no concept of "partial at PrInst, then reassess at the next level above."
- **No mid-trade level-exit logic anywhere.** Once Active, the indicator only watches the trail (or fixed FADE target) and the hard stop.

A beginner reading "trail at SMA20" may be misled into thinking they shouldn't exit early — when AM in fact teaches active management.

---

## 6. State that gates trades

| Variable | Set where | Read where | Effect |
|---|---|---|---|
| `institutionalBox` | `Process30MinBar` line 1215, `RunContainmentCheck` line 1708 | `DetermineBias` 1769, `DrawInstitutionalBox`, `V2UpdateAnchoredVWAP` 2223, anchored-VWAP anchor | If null, AnchVWAP → NaN; bias → Wait. **But bias is not a gate, so this doesn't block trades directly.** |
| `currentDayType` | `DetermineDayType` line 1739, `RunContainmentCheck` 1712 | JSONL only | Cosmetic. |
| `currentBias` | `DetermineBias` line 1767 | A1 alert text, JSONL only | Cosmetic. |
| `currentPhase` | `UpdatePhase` line 2992 | JSONL only | Cosmetic. |
| `v2DayType` (local in Process1MinBar) | Inline at line 1571 via `ClassifyAMDayType()` | Sets `tradeMode` and `v2TrendDir` | **THE actual day-type gate.** |
| `tradeMode` | Line 1579 | `canTrade` line 1628, `CheckEntry`, `effSignalCap` line 1626 | Decides whether candidates come from FADE pool or TREND pool; null → no-fire. |
| `v2TrendDir` | Line 1584 | `canTrade` line 1627, `CheckEntry` line 1792 | Required non-null to trade. |
| `signalsToday` | `SetSignal` line 2455 | `canTrade` line 1631, `CheckDayDone` 2846 | When ≥ effective cap, no new signals. |
| `lockoutActive` | `CheckLockout` line 3993, 3998 | `canTrade` line 1632, render banner 3068 | Permanent block once tripped. |
| `lastStopTime` (cooldown) | After stop in Realtime line 2609 | `IsInCooldown` line 4014 | `(barNow - lastStopTime).TotalMinutes < CooldownMinutes` blocks. |
| `currentSignalState` | `SetSignal`, `MonitorSignal`, etc. | `canTrade` requires `None` or `Pending` | Active blocks new pending. |
| `inRthWindow` | Inline 1609 | `canTrade` line 1629 | Last 30 min before close blocks new entries. |
| `v2TouchedThisSession` | `CheckEntry` 1978, cleared in day-rollover 1420 + ResetForNewDay 4520 | `CheckEntry` 1907 | Per-session per-level latch. |
| `v2OpenRangeLocked` | After OR-window 1446 | `CheckEntry` 1855 | OR levels not candidates until locked. |
| `firewallActive` | After fill 2579 | `DrawLabeledLine` 4355 | Hides non-signal drawings; doesn't gate entries directly (Active state already does that). |

What blocks a trade (in priority order during `canTrade`):
1. `v2TrendDir == null` or `tradeMode == null` (Sideways+flat 200 slope, or pre-9:30 Unknown).
2. Outside RTH window.
3. Already Active (Pending allowed for replacement).
4. Hit `effSignalCap`.
5. Lockout.
6. Cooldown.

Inside `CheckEntry`, additional drops: range/latch/retrace-side filters, and FADE-target-not-profitable.

---

## 7. Drawing / UI surfaces

### Static drawings (per session)

- **Box rectangles + H/L lines** — `DrawBoxLines` (line 4164), 3-stage age cycle: active (shaded) → fade (dashed H/L only) → dead. Institutional box has +1 extra trading day of life. Tags include trading-day key to prevent prior/current-day collisions.
- **Institutional box** — `DrawInstitutionalBox` (line 4260): tinted rectangle + horizontal H/L + corner label "INSTITUTIONAL: <name>". Only one institutional at a time; old tag is removed.
- **Midnight lines** (line 4316): dashed MID H / MID L only.
- **Measured moves** (line 4324): MM±1 / MM±2 from institutional. Only at RTH 9:30 capture, only if DetailLevel == Full and institutionalBox exists.
- **Pivot lines** (line 4334): PP/R1-R3/S1-S3 dotted, drawn only on 30-min processor session-close.
- **VWAP_Line, AnchVWAP_Line** drawn each bar.

### Live signal drawings

- `Sig_Entry`, `Sig_Stop`, `Sig_Target` (FADE), `Sig_Trail` (TREND once armed), `Sig_ArrowUp`/`Sig_ArrowDn`. All gated by `ShowTrades`.

### Historical trade arrows

- `Hist_{n}_entry`, `_entryLbl`, `_exit`, `_exitLbl`, `_line`. Drawn by `DrawTradeOnChart` (line 2764). Time-based positioning via `Bars.GetBar(EntryTime)` for 30-min charts.

### OnRender panels

- **Top legend chips** (`RenderChartLegend`, line 4043): color key for INSTITUTIONAL / 3:30 CLOSE / GLOBEX 6PM / MIDNIGHT / EUROPE 4AM / RTH 9:30. Position user-tunable via `LegendXOffset`/`LegendYOffset`. Pushed down 30px when lockout, 26px when cooldown.
- **Lockout banner** red across top (line 4022) when `lockoutActive`.
- **Cooldown banner** amber (line 4096) when `IsInCooldown()`. Shows minutes remaining.
- **Pre-Place Panel** dual-mode (line 3212):
  - "PRE-PLACE — DIR" with stop pts/dollars, size bucket (Green/Orange/Gray), ATM template, per-trade risk, book risk, then sorted level table with TOUCHED tags.
  - "COMING UP — INST HH:MM ET" timeline with V2_4 STATE block (day type, MOC ratio, 200-SMA slope, verdict), body-stack diagnostic (A/B/C/D), legacy 30m SMA stack diagnostic, stop preview, prior-inst range.
- **Staging Card** (line 3855): 280×180 modal at top center on signal fire. Shows entry/stop/target/risk/size bucket, CONFIRM/SKIP buttons, transitions to "TICKET LOGGED" strip on stage.

### Anything visually misleading or potentially confusing for a beginner

1. **Two day-types on screen at once.** The "Coming Up" panel renders the V2_4 body-stack day-type (LONG TREND / SIDEWAYS / etc., line 3411) AND the legacy 30m SMA stack (LONG / SHORT / WAIT, line 3326-3327). These two can disagree — and the SMA-stack labels are colored green/amber (line 3327) which makes them look authoritative. A beginner can easily think the SMA stack is the gate when it's actually the body-stack.
2. **`day_type` in JSONL signal** is the *legacy* enum (Congestion/Trending/Extended), not the AM body-stack. If a beginner ever opens the cockpit-dashboard data, the day-type next to a fired signal will look bizarre.
3. **STAGE button text says "CONFIRM" / "TICKET LOGGED"** but `AllowLiveOrderSubmit=true` does NOT actually submit — it only logs (line 3961). A beginner could believe a CONFIRM click submits an ATM order. The card text "TICKET LOGGED - submit ATM in ChartTrader NOW" mitigates this but only after staging.
4. **VWAP and AnchVWAP are drawn full-width** (line 1322, 1564) but excluded from candidate pool (line 1872). A beginner sees the live VWAP line and might expect a touch of it to fire an entry — it never will.
5. **Sig_Target line is drawn only in FADE mode** (line 2476-2479). In TREND mode the staging card row 3 reads "Target TRAIL (30m SMA20, ratchet only)" — if someone scrolls back to a historical chart they'll see no target line at all and may think the indicator is missing data.
6. **"Bias: LONG (pullbacks are buys)"** in the A1 alert (BiasStr) is based on price-vs-institutional-box, which is the legacy `currentBias`. This is unrelated to the actual `v2TrendDir` that gates trades. Beginner may receive an A1 saying "bias LONG" while the V2_4 trend dir is short or null.
7. **`MOC: pending (computed at 3:30 close)`** — this is correct, but for CL the MOC actually fires at 10:00 ET (the institutional capture for CL). The wording "3:30 close" is hardcoded in the panel (line 3441), which is misleading on CL charts.

### Firewall side-effect

`ActivateFirewall` (line 2874) removes ALL non-`Sig_*` and non-`InstitutionalBox*` drawings while a trade is Active. This is intentional — focus mode — but a trader who reloads a chart mid-trade may see a stripped chart. `DeactivateFirewall` doesn't redraw immediately; it relies on the next 30-min bar to call `RedrawActiveBoxes`. So immediately after exit, the chart can look bare for up to 30 minutes.

---

## 8. JSONL logging

### What IS logged (LogEvent calls)

| Event type | Where | Payload |
|---|---|---|
| `bar_close` (30m) | line 921 | tf, o, h, l, c, v |
| `bar_close` (1m) | line 934 | tf, o, h, l, c, v |
| `phase_change` | line 944 | from, to |
| `bias_change` | line 949 | from, to |
| `heartbeat` | line 2380 | phase, bias, day_type, signal_state, price, vwap, in_lockout |
| `touch` (pre-gate) | line 1911 | session_date, level (no @stamp), level_price, bar_open, bar_high, bar_low, bar_close, direction, retrace_side, already_latched |
| `signal` (post-gate) | line 2437 | side, entry, stop, target, trade_mode, level, trend_dir, adr20, eu_width, phase, day_type, vwap, inst_hi, inst_lo |
| `lockout` | line 4007 | reason, pnl, losers |

### What is NOT logged (but probably should be)

1. **Master-candle box H/L**. Only emitted via `Log()` to NT Output (e.g., line 1126 `"GLOBEX captured"`). No JSONL `box_capture` event with `name, high, low, body_top, body_bottom, start_time`.
2. **`v2DayType` (the AM body-stack)**. The "signal" event's `day_type` field is `currentDayType.ToString()` (line 2449) — Congestion/Trending/Extended/Unknown. The actual day-type that drove the trade decision (`LongTrend / Sideways / etc.`) is not in the payload.
3. **MOC validation**. `MocState`, `MocRatio`, the prior-bar volume comparison — none in JSONL. The signal event has `eu_width` but not `moc_ratio` or `moc_state`.
4. **200-SMA slope**. `Sma200SlopeDelta`, `Sma200At930`, `priorSma200At930` — none in JSONL. The signal event has no slope context, even though slope direction is what selects FADE direction in sideways.
5. **Pattern type**. With Pattern B unimplemented, the only pattern is "limit-on-retracement," but if Pattern B ever lands the JSONL payload has no field for it.
6. **Pending state transitions**. There's no JSONL event for fill, cancel-at-cutoff, trail-arm, target-hit, or stop-out. Only the entry signal is logged. The dashboard cannot reconstruct trade outcome from JSONL alone — it has to read NT's Output stream.
7. **Lockout deactivation / day reset**. `ResetForNewDay` clears state (line 4499) but emits no JSONL.
8. **Containment-check institutional reassignment**. When `RunContainmentCheck` promotes a different box to institutional (line 1708), no JSONL event fires. The anchored VWAP re-anchor is consequently invisible to the dashboard.
9. **Demo signal fires**. Goes through `SetSignal` and gets a "signal" event in Realtime (line 2436), but the demo path itself isn't tagged.
10. **Pre-place panel build**. `V21UpdatePrePlace` log is text-only (line 2141).
11. **`canTrade` denial reasons**. When `canTrade` is false, no event explains why (was it `lockoutActive`? `tradeMode==null`? `signalsToday>=cap`?). For "missing setup" debugging this is the single biggest hole.

### JSONL path

`{JsonlLogFolder}/{YYYY-MM-DD}/events.jsonl`, default `C:\seasonals\cockpit\sessions` (line 758). One JSON per line, lazy directory creation on first event of the day. Failures are swallowed via try/catch (line 2362).

---

## 9. Per-instrument variations (ES/NQ/GC vs CL)

### Detection (line 847-849)

```
isCL = Instrument.MasterInstrument.Name == "CL"
```
Only "CL" is special-cased. ES, NQ, GC, MES, MNQ, MGC all fall through as the default.

### Confirmed CL adjustments

| Aspect | Default | CL | Line |
|---|---|---|---|
| `closeHour:closeMinute` | 15:00 | 14:30 | 851-852 |
| `instCloseHour:instCloseMinute` | 15:30 | 10:00 | 859-860 |
| Institutional label | "Close 3:30" | "Close 10:00" | 1210 |
| Hard time-close in MonitorSignal | uses `closeHour/Minute` | inherits 14:30 correctly | 2705 |
| Pending-cancel cutoff | uses `closeHour-30` | inherits 14:00 correctly | 2525 |
| Pre-Place panel cancel cutoff | same | same | 2021 |

### Bugs / inconsistencies for CL

1. **`rthOpenHour=9, rthOpenMinute=30` is hardcoded for ALL instruments** (line 853-854). Comments at lines 1428 and 1440 explicitly say "For CL (opens 9:00)." So:
   - The 9:30 box capture (line 1149) fires at 9:30, not 9:00. CL's actual open is at 9:00 ET, so the "9:30 box" is the wrong half-hour bar.
   - `currentDay.RTH930OpenPx` is captured at 9:30, not 9:00. Day-type preliminary classification will use the wrong bar.
   - Opening-range lock at `rthOpenHour*60+rthOpenMinute+30 = 10:00` — for CL this is 30 min late.
   - `inRthWindow` lower bound is `h==9 && m>=30` — early CL setups (9:00-9:29) cannot fire.
   - The VWAP RTH reset is at 9:30 (line 1385) — wrong on CL.
   - The 1-min RTH reset for VWAP (line 1395-1396) — same bug.
   - The session-tracking `isRTH` (line 1002) — same.
   - The `else if` `currentPhase = TradingPhase.RTHOpen` (line 3007) — same.
   - The "Coming Up" panel timeline (line 3309) shows `RTH opens — 1st 1-min bar` at 9:30 — wrong on CL.

2. **MOC validation timing**. For CL the institutional bar is the 10:00→10:30 bar; the prior bar would be the 9:30→10:00 bar. Line 1219-1243 does compare `Volumes[idx30Min][0]` vs `[1]`, which is correct *if* the call happens on the right bar. The `if (h == instCloseHour && m == instCloseMinute)` at line 1207 fires at 10:00 for CL — so the comparison is correct. **However:** for CL, the 9:30→10:00 bar has only the first 30 minutes of "RTH" volume (since CL opens at 9:00 in our config, but `rthOpenHour` is hardcoded 9:30, so volume tracking for that window is also off — see bug #1).

3. **MOC display label** says "computed at 3:30 close" hardcoded (line 3441). On CL it should say "10:00 close" or similar.

4. **Verdict logic and the `OR LOCKS` event on the panel** (line 3315) fires at `rthOpenHour+1 = 10:00` — for CL this is 1 hour late.

5. **The legacy V2 MOC** at line 1305-1313 hardcodes `h==15` for the "yesterday's" 15:00-16:00 comparison. For CL this never fires (CL doesn't trade at 15:00 the same way). But this code path is dead anyway (`v2PriorInstValidated` is never read) — still, it's misleading commentary.

6. **`v2DailyRanges` enqueue on day rollover** uses `barOpen.Date` (line 1399). For CL, the calendar-date rollover may not cleanly align with the 14:30 session-close logic — the queue may double-count or skip days during the transition window. This is a soft bug (ADR is approximate) but worth flagging for Wave 3.

### GC

GC is handled identically to ES/NQ — no special-case. AM's spec presumably treats GC the same; if not, this is silent.

### Instrument-specific volume thresholds

`ESVolumeThreshold` and `NQVolumeThreshold` are user-tunable (lines 573-580). The decision logic at line 1489-1492 picks NQ threshold if FullName contains "NQ" else ES. **CL, GC have no dedicated volume threshold and silently use the ES threshold of 12000** — likely wrong for CL (lower turnover than ES).

### Instrument-specific point value

`pointValue` is read from `Instrument.MasterInstrument.PointValue` everywhere (lines 2748, 3332, 3806). NT supplies the right value per instrument. Fallback is `50.0` (ES). **MES would correctly resolve to 5; MNQ to 2; MGC to 10; CL micro to 100** — assuming NT's metadata is correct.

### `qty` and dollar-risk math

The Staging Card hardcodes `qty = signalSizeNote == "1 MES ONLY" ? 1 : 2` (line 3822). On CL this produces a confusing "2 contracts" interpretation that doesn't relate to MES — the bucket logic was authored for ES/MES. This is cosmetic since the trader manually places the ATM, but the `cardDollarsRisk` figure on a CL chart will be off.

---

## 10. Hidden / non-obvious behaviors

### Reset-and-redraw on `State.DataLoaded`

Line 802-829: aggressively `RemoveDrawObject` on every Sig_*, Hist_1..500_*, and a hardcoded list of legacy box names. Comment notes NT persists `Draw.*` tags across reloads. **Side effect:** if the user has > 500 trades in history, `Hist_501+` are not removed and become permanent ghost arrows on the chart.

### Box-tag date-keying

`DrawBoxLines` (line 4164) keys tags as `Box_{name}_{tradingDay}_{Rect|Top|Bot|DashTop|DashBot}`. The trading-day normalization (StartTime.Hour >= 18 → next day) is matched in `ComputeBoxFadeMidnight` (line 4120). If these two ever drift, ghost rectangles appear across the 6 PM boundary — comment at 4178-4184 documents the past bug.

### Anchored-VWAP backfill

Line 2245-2267: `V2UpdateAnchoredVWAP` walks back through 1-min history and replays accumulation from the institutional anchor forward. **Cost:** O(N) per bar where N can be up to a full session of 1-min bars. On a fresh institutional promotion mid-session, this triggers a re-walk. Performance-acceptable but worth knowing if backtesting on a long history.

### `firewallActive` filters drawings

Line 4355: `if (firewallActive && !tag.StartsWith("Sig_")) return;` — silently drops drawing requests during an Active trade. Comment at line 2877-2890 notes non-`Sig_*` and non-`InstitutionalBox*` are removed at firewall activation. If a developer adds a new drawing during a trade and doesn't prefix `Sig_`, it'll be invisible.

### `signalsToday` counts pending budget, not fills

Line 588-590 explicit comment: "Caps the number of PENDING signals armed per session, not the number of fills. A cancelled pending still counts. Intentional: this is a decision-budget guardrail against over-engagement." A beginner using `MaxSignalsPerDay=3` who has a pending cancel at 14:30 cutoff can find themselves locked out of subsequent setups even though no fill ever happened. Documented but unintuitive.

### Latch clear logic

`v2TouchedThisSession.Clear()` happens in TWO places:
- Day-rollover detected by `barOpen.Date != v2TodayDate` in `Process1MinBar` (line 1420).
- `ResetForNewDay` (line 4520).

`ResetForNewDay` is triggered by the 30-min processor at session close (line 1102). The 1-min day-rollover trigger fires at the calendar-date boundary which for ES is midnight ET — *between* the prior 30-min session close and the new session's opening. Either could fire first depending on bar arrival order. The double-clear is defensive but means the latch is reset twice per day on ES.

### `Process30MinBar` else-chain not exhaustive

Line 1021 (close), 1122 (6PM), 1131 (midnight), 1140 (4AM), 1149 (9:30) are an `if/else if` chain. Line 1207 (institutional) is a SEPARATE `if`, intentionally — comment at line 1203-1206 explains it must fire on the same bar as session-close for ES/NQ/GC. **But:** if a future change accidentally moves line 1207 into the chain, ES institutional capture stops working.

### "Diagnostic blocked" counters

`diagBarsChecked`, `diagSmaBlockCount`, `diagSmaLastSeen`, `diagRetestCount` are incremented in CheckEntry / 30m processor and printed in the daily summary. They're for debugging "why didn't a setup fire?" but the logic doesn't bucket why exactly — only `diagSmaBlockCount` (which is unused in V2_4 because the SMA stack gate was removed) and `diagBarsChecked` (every CheckEntry call) increment. **These counters are stale relative to the current entry path** and can mislead the trader.

### `IsInCooldown` uses chart bar-time

Line 4014-4020: `var barNow = idx1Min >= 0 && CurrentBars[idx1Min] >= 0 ? Times[idx1Min][0] : DateTime.Now;` — bar-time when available, wall-clock when not. In Realtime live trading these are equivalent at bar close; during historical replay only bar-time fires (lastStopTime is Realtime-only so historical never enters cooldown).

### `currentDay = new DayBoxes { Date = barTime.Date.AddDays(1) }`

After session-close (line 1114). The new day's `Date` is set to the NEXT calendar day. So the FRIDAY 15:00 close creates a day with Date=Saturday — which means Sunday's GlobEx 6PM will land in the Saturday `currentDay`. Comments don't address this; the date is largely informational, but if anything (e.g., `dayHistory` queries) ever relies on `Date` matching the trading day, this is a footgun.

### `Process30MinBar` SMA200 refresh bug-fix

Line 1158-1187 explicitly notes a 2026-04-24 code-review bug: the 30-min SMA200 cache (`sma200_30min`) is updated by a SEPARATE block lower in `Process30MinBar` (line 1252), so when the 9:30 capture block runs, the cache holds the prior bar's value. Fix is to read `sma200Ind30[0]` directly inside the capture block. Without this, slope calc was 30-minutes stale.

### CheckEntry Historical+Realtime split

Line 1618-1622: `CheckEntry` runs in Historical so the pre-gate touch JSONL log builds during chart backfill (recall feed). `SetSignal` is gated to `Realtime` for ATM submit, audible alert, and staging card. **But:** `RecordAndDrawTrade` and `tradeHistory.Add` run in BOTH Historical and Realtime. Historical replay populates the trade history, including arrows on the chart, even though those weren't real fills. The lockout/PnL accounting is correctly Realtime-only (line 2754-2759).

### `signalTradeMode` is set by SetSignal but NEVER reset on signal teardown

Line 2408 sets it; ResetForNewDay clears (line 4506). Between signals within a day, after a stop-out, it retains the prior trade's mode until the next SetSignal. This is fine because it's only read inside `MonitorSignal` while a signal is active. Still, mildly fragile if someone reads it during the None state.

### Mouse subscription leak on reload

Line 887-889: `ChartControl.PreviewMouseLeftButtonDown -= OnChartMouseDown` is attempted on Terminated. If the chart was destroyed before the indicator state hits Terminated, this throws and is swallowed by the catch. No actual leak in NT8 but worth noting for stability.

---

## Behavior summary table

| Rule (AM intent) | Code location | Status |
|---|---|---|
| 4 master candles (3:30 / 6PM / 4AM / 9:30) | `Process30MinBar` 1122/1131/1140/1149/1207 | WIRED |
| Institutional candle = widest containing | `RunContainmentCheck` 1661 | WIRED |
| Day-type = body-stack of master candles | `ClassifyAMDayType` 4388 | WIRED |
| MOC validation 3:30 vs 3:00 (CL: 10:00 vs 9:30) | line 1224-1243 | WIRED — display only, does NOT block trades |
| 200-SMA slope sticky-for-day | line 1168-1187 | WIRED — slope used for sideways FADE direction |
| TREND day: limit on retracement at structural level | `CheckEntry` TREND branch 1818 | WIRED |
| FADE day: limit at structural extreme on slope side | `CheckEntry` FADE branch 1802 | WIRED |
| Stop = entry-trigger candle's width | `V2ComputeStopDistance` w/ anchor 2174 | NOT WIRED — anchor never passed; falls back to europe-4AM-width clipped to ADR |
| 2× width on sideways | none | NOT WIRED |
| Bigger-candle exception (anchor contained by 3:30/9:30) | line 2178-2193 | DEAD CODE — anchor always null |
| Pattern A: limit at level on retrace | `CheckEntry` 1787 | WIRED |
| Pattern B: look-below-and-fail | `LevelWatchState` 179 | SCAFFOLDING ONLY — no `CheckPatternBEntry` exists |
| Level-to-level exits with reassessment | `MonitorSignal` 2513 | NOT WIRED — TREND uses SMA20 ratchet trail; FADE uses fixed PrInst H/L |
| Cancel pending limits 30 min before close | line 2521-2536 | WIRED |
| Hard close at 15:00 (CL 14:30) | 2705-2719 | WIRED |
| First-touch-only per session per level | `v2TouchedThisSession` 492 | WIRED — per-name latch (Pr30 stamp-keyed) |
| ORH/ORL only after OR locks | line 1855 | WIRED |
| Retrace-side filter (no breakouts) | line 1908, 1946 | WIRED (strict `<`/`>`, drops touches AT bar open) |
| VWAP/AnchVWAP excluded from candidates | line 1872-1880 | WIRED (intentional) |
| MaxSignalsPerDay decision-budget cap | line 1631 | WIRED — pending counts |
| FADE cap = min(2, MaxSignalsPerDay) | line 1626 | WIRED |
| Daily-loss lockout | `CheckLockout` 3981 | WIRED — Realtime only |
| Post-stop cooldown | `IsInCooldown` 4014 | WIRED — Realtime stops only |
| Staging-card live ATM submit | `OnStageClicked` 3947 | NOT WIRED — logs ticket only, manual submission required |
| CL session times (open / inst / close) | 851-860 | PARTIALLY — `closeHour/Minute` and `instCloseHour/Minute` correct; `rthOpenHour/Minute` BUG (hardcoded 9:30 ignores CL's 9:00 open) |
| JSONL touch event (pre-gate) | line 1911 | WIRED |
| JSONL signal event | line 2437 | WIRED — but day_type field is the legacy enum, not v2DayType |
| JSONL master-candle box capture | none | NOT WIRED — only `Log()` to NT Output |
| JSONL fill / exit / cancel transitions | none | NOT WIRED |
| JSONL canTrade-denial reason | none | NOT WIRED |

---

## Cross-reference notes for Wave 3 specialists

**For the dashboard / JSONL-recall analyst:**
- The `signal.day_type` field is the legacy `currentDayType` (Congestion/Trending/Extended/Unknown), not the actual gate (`v2DayType`). Don't slice signals by this field expecting AM-style buckets.
- `signal.trade_mode` IS correct (TREND/FADE) — use that as the day-type proxy until v2DayType is added to JSONL.
- Master-candle box H/L are NOT in JSONL. If you need them, parse the NT Output `Print` stream or add a `box_capture` event yourself. The user's prior finding is correct.
- No JSONL events for fill/cancel/stop/target/timeclose. To compute trade outcomes from JSONL alone, you must combine the signal entry with the next day's tradeHistory rollup — but tradeHistory has no JSONL. Currently outcome is only Print()-text and chart visuals.
- `canTrade=false` paths produce no event. "Why didn't I get a signal?" is currently unanswerable from JSONL.
- `touch` events fire before the latch+retrace filter, so JSONL recall data (matching against Python event_builder) sees the full set of in-range levels. Latched/retrace data is in `already_latched` and `retrace_side` fields.

**For the strategy / reproducibility analyst:**
- The actual stop in production is europe-4AM-width clipped to `[0.30, 0.80] * ADR20` — a fixed-per-day stop. Not per-trigger-candle. This affects PnL distribution analysis: trades on the same day share stop magnitude. If you're computing per-trade R-multiples assuming AM's per-candle rule, you'll misattribute risk.
- `signal.eu_width` in JSONL captures europe-4AM raw width (pre-clip). `signal.adr20` is the ADR. You can reconstruct the actual stop as `clip(eu_width, 0.30*adr20, 0.80*adr20)`.
- TREND exits use 30-min SMA20 ratchet; the JSONL has no record of when the trail armed, where it ratcheted to, or when it triggered exit. To reproduce TREND exits you must replay 30-min SMA20 against bar history yourself.
- FADE target = `currentDay.Close330.High` (long) or `Close330.Low` (short). Not in JSONL. To reproduce, extract today's institutional candle H/L from box_capture events that you'd have to add.
- `effSignalCap = Math.Min(2, MaxSignalsPerDay)` for FADE. Default `MaxSignalsPerDay=3`, so FADE caps at 2 in production.

**For the per-instrument / CL specialist:**
- CL has a real bug: `rthOpenHour=9, rthOpenMinute=30` is hardcoded for CL, but CL opens at 9:00 ET. Affects: 9:30 box capture, RTH930OpenPx, opening-range window, OR-lock time, in-RTH gate, VWAP RTH reset, RTH session tracking, phase derivation, "Coming Up" timeline label. **Every time-of-day gate that uses `rthOpenHour/Minute` is 30 minutes off on CL.**
- CL volume threshold falls through to ES's `ESVolumeThreshold` (default 12000). This is wrong for CL.
- CL `pointValue` resolves correctly via NT metadata; `qty` math in StagingCard assumes ES/MES contract semantics (1 vs 2) and dollar-risk display will be off on CL.
- GC is treated identically to ES — no special handling. If GC differs from ES in AM's method, V2_4 doesn't reflect it.

**For the UX / beginner-experience specialist:**
- The Coming Up panel renders TWO day-type indicators that can disagree (V2_4 body-stack and legacy 30m SMA stack). The legacy SMA-stack labels are colored — beginners can mistake them for authoritative.
- VWAP and AnchVWAP draw full-width but are NOT entry candidates. A beginner expecting a touch of VWAP to fire will be confused. Consider whether this is intentional — the comment says yes, AM says VWAP is "permission, not destination."
- The "FADE skip: PrInst not in profit direction" log path silently drops valid setups. No alert, no panel update — only a Print() line. This is one source of "I saw a setup, why didn't it fire?"
- The `Sig_Target` line only draws in FADE mode. TREND signals show "Target TRAIL (30m SMA20)" in the staging card but no chart line. Visual gap that may confuse a beginner who expects a target marker on every trade.
- `STAGE button = log only`. `AllowLiveOrderSubmit=true` does NOT submit. The staged-state strip says "submit ATM in ChartTrader NOW" but a beginner might miss that wording on the first encounter.
- Firewall mode strips drawings — chart looks bare during an active trade. Some users report this as "indicator stopped working." It's by design.

**For the entry-method specialist:**
- Pattern B (look-below-and-fail) is scaffolded only. `LevelWatchState`, `CheckPatternBEntry` — neither is wired. Currently V2_4 is single-pattern (limit-at-level retrace).
- Retrace-side filter uses `<` / `>` (strict). A level touched exactly at bar open is dropped (`px == barOpen` → not retrace). Edge-case but worth documenting.
- The Pr30 candidate uses `@HHmm` stamp in the latch key, so each new 30m roll resets that level's first-touch latch. Other levels (PrInstH, GlobExH, etc.) are static-name-keyed — one touch ends them for the day.
- VWAP and AnchVWAP excluded from CheckEntry candidates by explicit choice (line 1872). If AM teaches VWAP retests as valid, V2_4 will not honor that.
- Range filter is `px ∈ [low, high]`. Gap-throughs (level inside the gap, neither bar bracketed it) are silently missed.

**For the sizing / risk specialist:**
- `cardDollarsRisk` thresholds for Green/Orange/Gray are hardcoded: Gray > $100, else Orange if "1 MES ONLY", else Green. The `2 MES` Green target gives `risk_q2 <= $100` test; the `1 MES` Orange gives `risk_q1 <= $100`; else Gray. See lines 2118-2134 in `V21UpdatePrePlace` for the same logic.
- `MaxOpeningRange` (default 10 ES points) is used to decide "1 MES ONLY" vs "Normal" via `signalSizeNote`. On CL/NQ this cutoff is in ES points and may not be appropriate.
- `qty` in `RecordAndDrawTrade` uses `signalSizeNote == "1 MES ONLY" ? 1 : 2`. A `Gray` bucket is forced to 1 (line 2747) for PnL accounting, even though the trader may have skipped the trade entirely.
- `MaxDailyLossDollars` and `MaxDailyLosingTrades` lockouts run AFTER `RecordAndDrawTrade`. The `cardSizeBucket` field is used for qty inference in PnL — but `cardSizeBucket` is set in `ShowStagingCard` (line 3833), which runs at SetSignal in Realtime. If a signal fires Historical, `cardSizeBucket` is null/empty and the qty inference falls back to `signalSizeNote` (line 2746).

**Final note for Wave 3 coordinators:**

The single highest-leverage finding for "why are setups being missed?" is the silent-drop list in §3 above — particularly:
1. FADE-target-not-profitable (no log surface).
2. Retrace-side strict-inequality (touches exactly at bar open dropped).
3. VWAP/AnchVWAP excluded from candidates.
4. CL's `rthOpenHour` bug (CL setups 9:00–9:29 entirely invisible).
5. `signalsToday` counting cancelled pendings.
6. 30-min Pr30 unavailability before 10:00.

A "missed-setup audit" pass against the JSONL touch stream (which DOES capture pre-gate touches) could quantify each of these without further code changes.
