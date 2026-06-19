# Failure Mode and Edge-Case Analysis — AMTradeCockpit V2_4

**Author:** Wave 3 — Failure-Mode and Edge-Case Analyst
**Date:** 2026-04-27
**Subject:** `AMTradeCockpitV2_4.cs` (4627 lines)
**Evidence base:** V2_4 code audit, version diff audit, JSONL data analysis (103 sessions), NT8 execution audit, direct code reading.

---

## Framing

The headline finding from the JSONL corpus is 2 signals in 6 months against 741 qualifying touches — a 0.27% conversion rate. This document works backwards from that number. The team's question is not "is the edge real?" but "what is silently swallowing 99.7% of the valid setups?" The failure modes below are organized by section as specified. Each entry states the trigger, the wrong behavior, how to detect it, and how to fix it. Code lines reference V2_4 unless noted.

The adversarial posture here is: assume things WILL break in the worst-case timing, the worst-case data, and the worst-case user interaction. NT8 is a complex runtime. The indicator accumulates state over a six-hour session. Silent failures compound.

---

## Section 1 — Code-Level Edge Cases

### 1.1 Race condition: `OnBarUpdate` firing for multiple BarsInProgress

**Trigger:** NT8 calls `OnBarUpdate` sequentially for each registered series, but the order within a given wall-clock tick is determined by NT8 internals and can vary on market replay vs live. For V2_4, `BarsInProgress == 0` (primary 1-min), `BarsInProgress == idx30Min`, and `BarsInProgress == idx1Min` all share the same mutable state: `currentDay`, `institutionalBox`, `v2TouchedThisSession`, `sma20_30min`, `currentVWAP`, `currentSignalState`, and the entire `tradeHistory` list.

**Wrong behavior:** When a 30-min bar closes simultaneously with a 1-min bar (which happens at exactly 10:00, 10:30, etc.), NT8 can call the 30-min handler first or the 1-min handler first. The 30-min handler (`Process30MinBar`) may update `institutionalBox` via `RunContainmentCheck` (line 1708) and refresh `sma20_30min` (line 1271). The 1-min handler then reads these fields in `CheckEntry` and `MonitorSignal`. If the 1-min fires before the 30-min on a bar-close boundary, the trail-arm check at line 2651 reads the previous 30-min SMA20, not the just-completed one. The reverse ordering (30-min first) is the intended path, but NT8 does not guarantee it. On live data this is a 1-bar staleness issue; during replay it may differ from live.

**Detection:** Log the BarsInProgress sequence on 30-min-coincident 1-min bars. Compare `sma20_30min` at the start and end of each `OnBarUpdate` dispatch cycle. If the 30-min update changes the value mid-cycle, a race is confirmed.

**Fix:** Do not access `sma20_30min` in Process1MinBar until the 30-min has been confirmed closed for that bar. One defensive approach: snapshot `sma20_30min` in a local variable at the top of `Process30MinBar`, and only write it to the field at the very end of Process30MinBar, after all other processing is complete.

---

### 1.2 `try/catch` in `OnBarUpdate` silently swallows exceptions in Historical mode

**Trigger:** Lines 956–963 catch ALL exceptions thrown by either `Process30MinBar()` or `Process1MinBar()`, print to NT Output only in non-Historical state, and then allow the next bar to proceed.

**Wrong behavior:** A null-reference exception at any point inside either processor during Historical backfill produces zero output — not even a Print line, because `State != State.Historical` evaluates false and the catch body is silent. Bugs that exist only during cold-start state (e.g., `currentDay == null` on the very first bar, or `sma200Ind30[0]` throwing before the SMA has 200 bars of history) are completely invisible during chart load. The indicator continues and produces its startup drawings and JSONL events as if nothing happened, with corrupted intermediate state from the half-completed processing.

**Detection:** Temporarily remove the Historical guard (`if (State != State.Historical)`) from the catch body and reload the chart. Any new Print lines reveal hidden cold-start bugs.

**Fix:** Log every exception in every state to a dedicated counter. Surface `obuExceptionsToday` in the Pre-Place Panel. Even in Historical mode, write exceptions to the JSONL logger (a `{"type":"error","payload":{"msg":"..."}}` line costs nothing and is invaluable for remote debugging).

---

### 1.3 `Volumes[idx30Min][0]` cast to long — potential overflow on high-volume instruments

**Trigger:** Line 1232 (MOC capture): `long thisBarVol = (long)Volumes[idx30Min][0];`. NT8 stores bar volumes as `double`. For normal ES/NQ bars this is safe. For CL (crude oil), heavily traded instruments, or a data-feed spike that emits a corrupted volume, the double value could exceed `long.MaxValue` (9.2e18). This is an unrealistic case in normal trading, but a corrupted tick feed could produce it.

**Wrong behavior:** Overflow produces a negative `long`, making `ratio = thisBarVol / priorBarVol` a large negative number. `MocState` gets set to `Gray` (no MOC confirmation). Since MOC is display-only today (it does not gate entries), this is only a cosmetic error — but it will generate misleading MOC panel output and confuse any future MOC-gating logic.

**Detection:** Add a bounds check: `if (rawVol > 1e12) Log("MOC volume overflow: " + rawVol)`.

**Fix:** Use `Math.Min(rawVol, 1e12)` before the cast, or keep as double throughout.

---

### 1.4 VWAP accumulator: divide-by-zero guard present but subnormal float risk unchecked

**Trigger:** VWAP computation at line 1395: `currentVWAP = cumulativeVol > 0 ? cumulativeTPV / cumulativeVol : close;`. The guard prevents divide-by-zero on the first bar. However, over a long session (390 1-min bars), `cumulativeTPV` accumulates `(high + low + close) / 3 * volume` for each bar. If price is ~5000 and average volume is ~50,000 per bar, after 390 bars: `cumulativeTPV ≈ 390 × 5000 × 50000 = 9.75e10`. This is well within `double` range (max ~1.8e308), so overflow is not a practical concern.

**The real risk** is VWAP drift via accumulator contamination. If one corrupted bar contributes a `volume = 0` but `high = 99999` (a spike tick), `TPV = 99999 * 1.5 / 3 * 0 = 0` — no damage. But if volume is non-zero on the spike, VWAP jumps permanently until the next session reset. The VWAP reset at line 1385 only fires on the first RTH 1-min bar of the day; a spike mid-session is permanent.

**Wrong behavior:** VWAP line shows a value far from actual VWAP. Since VWAP is not an entry candidate in V2_4 (lines 1872–1880), this affects only the JSONL heartbeat `vwap` field and the drawn line, not trade decisions. But the AnchVWAP is computed similarly (lines 2245–2267) and also has no spike filter. If a future version restores VWAP as a candidate, this becomes a direct missed-setup generator.

**Detection:** Compare `currentVWAP` against NT's built-in VWAP indicator at each bar close.

**Fix:** Add a sanity check: if new TPV contribution moves VWAP by more than `2 * v2Adr20` in a single bar, log a warning and optionally clip the contribution.

---

### 1.5 `v2TouchedThisSession` HashSet growth — no cap on size

**Trigger:** `v2TouchedThisSession` (line 492) is a `HashSet<string>`. It is added to at line 1978 (`v2TouchedThisSession.Add(bestName)`) and cleared in two places: the 1-min day-rollover check (line 1420) and `ResetForNewDay` (line 4520). The Pr30 level uses time-stamped keys like `"Pr30H@1030"`, `"Pr30H@1100"`, etc. — a new key per 30-min roll. On a normal ES/NQ session that runs 6.5 RTH hours, there are 13 rolling Pr30 windows, producing 13 unique keys for Pr30H and 13 for Pr30L. Over DaysOfHistory=7, if the latch is not clearing on the day boundary but is accumulating (e.g., due to a session-close bug), the set could grow by 26+ entries per day.

**Wrong behavior:** Under normal operation the set stays small (max ~17 levels × 13 30-min windows = ~221 entries at worst per session, then cleared). Unbounded growth only occurs if `ResetForNewDay` fails to fire on the day boundary, which would be caused by a missing 3:30 PM 30-min bar (data gap at session close). In that case, Pr30 keys from the prior day remain in the set and a same-price Pr30 level on the next day would be treated as already-latched, silently blocking entry.

**Detection:** Log `v2TouchedThisSession.Count` in the daily summary.

**Fix:** Add a maximum-size guard: `if (v2TouchedThisSession.Count > 500) v2TouchedThisSession.Clear(); Log("WARN: latch set overflowed, cleared");`.

---

### 1.6 Box aging logic: holiday handling and DST

**Trigger:** Box age is computed in `ComputeBoxFadeMidnight` (referenced at line 4120) using a "weekend-skip" fix (noted in the version diff as a recent patch). The logic advances the age counter only on trading days. However, US market holidays (Christmas, New Year, Good Friday, Thanksgiving, July 4) are not in the code — there is no holiday calendar.

**Wrong behavior:** On the Tuesday after a Monday holiday, boxes that should have one additional "day of age" will have one fewer because Monday was not skipped. A box that V2_4 considers "2 days old" is actually 3 calendar days old. More importantly, boxes that should be expired (dead, drawn as nothing) may still show as "active" (drawn as solid rectangles). This is primarily a visual issue, but any future rule that uses box age in entry logic would misfire.

For DST, the spring-forward and fall-back transitions change the wall-clock mapping of bar timestamps by one hour. V2_4 hardcodes `rthOpenHour = 9`, `rthOpenMinute = 30`. On the DST transition day, the NT8 bars use the instrument's exchange timezone (ET), which NT handles internally. However, if the user's Windows system clock is in a different timezone and NT8's timestamp reporting diverges from exchange time on that day, the hour/minute comparison at lines 989, 1005, 1021, 1122, 1131, 1140, 1149, 1207 could all fire on the wrong bar.

**Detection:** Load a chart spanning the March 2026 DST transition date. Inspect the box capture times in NT Output. Check whether the GlobEx 6PM, Midnight, 4AM, and 9:30 captures fired on the correct bars.

**Fix:** Use NT8's `Bars.GetTradingDayBeginTime` or `TradingHours` API to advance box age rather than a manual day counter. For DST, rely exclusively on NT8's bar-time `DateTime` objects, which are in the instrument's exchange timezone (ET for ES), not wall-clock time.

---

### 1.7 `Bars.GetBar(box.StartTime.AddMinutes(1))` returning -1 on data gap

**Trigger:** Historical trade drawing in `DrawTradeOnChart` calls `Bars.GetBar(box.StartTime.AddMinutes(1))` to position an arrow on the 30-min chart. If there is no bar at that time (data gap, low-liquidity day, or the bar time is in overnight session that is not loaded), `GetBar` returns -1.

**Wrong behavior:** The code at the call site checks `if (barIdx < 0) barsAgo = 0` — setting `barsAgo = 0` draws the arrow at the most recent bar, not at the original signal time. This displaces historical trade arrows to the current bar, making them appear to be current-bar events when reviewing history.

**Detection:** Load a chart with a known data gap. Check whether historical trade arrows cluster at the current bar.

**Fix:** If `barIdx < 0`, suppress drawing the historical arrow entirely (log the skip) rather than misplacing it to `barsAgo = 0`.

---

### 1.8 Cached SMA indicators (`sma50Ind30`, `sma200Ind30`) null at access time

**Trigger:** Lines 836–838 create `sma50Ind30 = SMA(BarsArray[idx30Min], 50)` and similar during `State.Configure`. Between `State.Configure` and `State.DataLoaded`, these objects exist but have no data. If `OnBarUpdate` fires before `State.DataLoaded` (which NT8 does not guarantee will not happen in certain reload scenarios), the indicator reference may be non-null but its `Count` may be 0.

**Wrong behavior:** Line 1517 checks `sma50Ind1 != null && sma200Ind1 != null && CurrentBars[idx1Min] >= 210` before accessing the 1-min SMAs. The 30-min SMA access at lines 1247–1253 checks `CurrentBars[idx30Min] >= 50 + 5` before the slope math. These guards are adequate if `Count` and `CurrentBars` are always in sync. However, on a chart that is loaded mid-session (after the session has already started), `CurrentBars[idx30Min]` may be less than 50, meaning the SMA50_30 is not in the candidate pool and will never be added for that session regardless of actual bar history loaded.

**Detection:** Attach V2_4 to a chart at 11:00 AM ET. Inspect whether `SMA50_30` and `SMA200_30` appear in the Pre-Place Panel and JSONL touch stream.

**Fix:** The checks are correct for preventing null-access, but the behavior should be documented: mid-session loads will never use SMA50_30/SMA200_30 as candidates if fewer than 50 30-min bars are available on the loaded chart range.

---

### 1.9 `signalEntryBar` index shift on NT bar rebuild

**Trigger:** `signalEntryBar = CurrentBars[idx1Min]` is set at line 2456 (inside `SetSignal`). It stores an absolute bar index. If NT8 rebuilds bar data (e.g., after a reconnect or data correction), bar indices shift. Historical bars get renumbered. An `Active` signal whose `signalEntryBar` pointed to index 300 may now need to be index 302.

**Wrong behavior:** `signalEntryBar` is used in `DrawTradeOnChart` (line 2764) for positioning the entry arrow on a 30-min chart. An index shift causes the arrow to render on the wrong bar. This is purely a visual bug in the current implementation, since no exit logic reads `signalEntryBar`. However, if a future developer writes "exit if `CurrentBars[idx1Min] > signalEntryBar + N`" for a time-based exit, this becomes a logic bug.

**Detection:** Trigger a data reconnect while a signal is Active. Check arrow position.

**Fix:** Store `signalTime` (already stored at line 2404) for historical arrow positioning instead of a bar index. Bar indices are inherently non-persistent.

---

### 1.10 `institutionalBox` mid-session reassignment leaves stale gold rectangle

**Trigger:** `RunContainmentCheck` (line 1661) is called at the 10:00 RTH box capture and again (potentially) during `Process30MinBar`. It may reassign `institutionalBox` to a different `CandleBox` reference mid-session. The gold rectangle drawing uses a fixed tag `"InstitutionalBox"` (line 4262), so the old drawing is overwritten. However, the AnchVWAP re-anchor walkback (lines 2245–2267) replays from the new institutional candle's `StartTime`, discarding all prior TPV/Vol accumulation.

**Wrong behavior:** When `RunContainmentCheck` promotes a wider box to `institutionalBox` (e.g., the RTH930 box at 10:00 is wider than the prior 3:30 box), the AnchVWAP resets its cumulative sum and replays from scratch. This is the intended behavior per the comment, but it means that any FADE signal that fired between 9:30 and 10:00 was computed with the old anchored VWAP as context, and the 10:00 reassignment silently invalidates that context without re-evaluating or cancelling the pending signal.

If `institutionalBox` changes while a signal is `Active`, the FADE target (`currentDay.Close330.High/Low`) does not change — it was set at `SetSignal` time. But the drawn `InstitutionalBox` rectangle now represents a different candle. The trader sees an inconsistency: "my target is PrInst L but the gold box has shifted."

**Detection:** Log "INSTITUTIONAL BOX REASSIGNED: {old} -> {new}" in `RunContainmentCheck` whenever `institutionalBox != bestInstitutional`.

**Fix:** If a reassignment occurs while `currentSignalState == Active` and `signalTradeMode == "FADE"`, log a warning that the anchor changed mid-trade. No automatic fix — the trader should be aware.

---

## Section 2 — State Corruption

### 2.1 `ResetForNewDay` — what it misses

`ResetForNewDay` (lines 4499–4568) clears most per-session state. What is NOT cleared:

- **`priorSma200At930`**: There is no field with this exact name. `currentDay.Sma200At930` is set during the 9:30 capture (line ~1168). On session close, `priorDay = currentDay` (line 1038), and `priorDay.Sma200At930` carries forward. `ResetForNewDay` does not touch `priorDay`. If `priorDay` is never cleared, it holds the prior session's SMA200 baseline forever. On a Monday after a 3-day weekend, `priorDay` is Friday's DayBoxes. This is correct behavior (the code intends for `priorDay` to be the last completed session). However, if `ResetForNewDay` fires but `priorDay` was not properly populated (e.g., the session close bar was missed due to a data gap), `priorDay.Sma200At930` could be NaN or a stale value from two sessions ago. The slope delta `Sma200SlopeDelta` would then be computed against the wrong baseline, misclassifying the day type.

- **`v2DailyRanges` queue**: NOT cleared in `ResetForNewDay`. It is managed separately by the 1-min day-rollover detector (line 1408). If the day-rollover fires before `ResetForNewDay` (it can — the 1-min fires at midnight ET, the 30-min session-close fires at 15:00 ET the prior session), a partial overlap exists. This is not a bug per the current design but is fragile.

- **`tradeHistory` list**: NOT cleared in `ResetForNewDay`. It accumulates across all sessions. The daily summary at line 1052 prints total count across all days, not just today. If the user keeps the chart loaded for weeks, `tradeHistory` grows without bound. Performance impact is minimal but the PnL summary will mix days.

- **`logEntries` list**: NOT cleared in `ResetForNewDay`. Bounded at 5000 entries (line 4488) but not session-scoped. An all-day log scan would include prior sessions.

**Detection:** Load the chart, let it run through a session close, watch `ResetForNewDay`, then verify `priorDay.Sma200At930` is the correct value from the just-completed session.

---

### 2.2 Mid-session indicator load — in-progress state handling

**Trigger:** User attaches V2_4 to a chart at 11:00 AM ET, well after RTH open.

**Wrong behavior:**
- `currentDay.GlobEx6PM`, `currentDay.Midnight`, `currentDay.Europe4AM`, `currentDay.RTH930` are all captured in `Process30MinBar` as bars roll forward. On chart load, NT8 replays all bars from the start of loaded history. If `DaysOfHistory = 3`, NT loads 3 days of bars and replays them. All four candle boxes will be captured during the backfill as NT replays the prior midnight, 4AM, and 9:30 bars. So boxes ARE populated correctly before live trading begins.
- However, `currentVWAP` and `cumulativeTPV / cumulativeVol` are reset at the first RTH 1-min bar (line 1385). If the backfill includes today's session, the VWAP will be computed correctly. This is the correct behavior.
- The critical missing piece: `v2OpenRangeLocked` and `rth1MinComplete` are reset in `ResetForNewDay` and checked against `rthOpenHour/Minute`. If the chart loads after 10:00, the opening range lock fires correctly during backfill. Mid-session attach appears safe for state reconstruction.
- **The real risk**: `signalsToday`, `realizedPnlDollarsToday`, `losingTradesToday`, `lockoutActive` are all in-memory only. If the indicator was previously active and fired trades, those are lost on reload. The indicator starts fresh at 0. If the user was already locked out ($150 loss), V2_4 after reload thinks it can trade again.

---

### 2.3 NT8 chart reload while a position is active — state entirely lost

**Trigger:** User changes any indicator parameter (triggers `State.SetDefaults` → `Restart`) or opens Properties dialog mid-trade (lines 887–889 of the Terminated handler attempt cleanup but NT may have already destroyed the chart state).

**Wrong behavior:** `currentSignalState`, `signalEntry`, `signalStop`, `realizedPnlDollarsToday`, `lockoutActive` — all reset to defaults. V2_4 has no knowledge that a real broker position is still open. The next qualifying touch will generate a new signal, potentially doubling up. The P&L lockout check starts from $0, not from the current position's unrealized loss. If the current position is a loser and the user is supposed to be locked out, V2_4 will not enforce it after reload.

**Detection:** This is architectural. There is no runtime test that catches this; it is inherent in indicator-only state.

**Fix documented in NT8 audit (§10.4):** Persist `{signalState, realizedPnlDollarsToday, losingTradesToday, lockoutActive}` to a `state.json` file on each state change. Restore on `State.DataLoaded`.

---

### 2.4 Multiple charts of the same instrument — double-firing signals

**Trigger:** User has two chart windows open with V2_4, both on ES 1-min.

**Wrong behavior:** Each chart runs an independent indicator instance with independent state. Both will fire the same signal. Two staging cards appear. Two JSONL `signal` events are written to the same `events.jsonl` file (both compute the same path: `{JsonlLogFolder}/{date}/events.jsonl`). File writes are not synchronized; a race in `File.AppendAllText` (line 2364) can produce interleaved or truncated lines if both charts fire in the same millisecond.

**Detection:** Open two charts with V2_4 on ES. Verify whether signals appear in both.

**Fix:** The JSONL path uses a process-level `File.AppendAllText` which is not thread-safe if called from multiple indicator instances simultaneously. Add a machine-global named mutex around the file write, or use a single writer instance via a static field.

---

### 2.5 Switching chart TimeFrame mid-session

**Trigger:** User right-clicks the chart and changes the primary series from 1-min to 5-min while V2_4 is loaded.

**Wrong behavior:** V2_4 in `State.Configure` adds two secondary series: 30-min (`AddDataSeries(BarsPeriodType.Minute, 30)`) and 1-min. When the primary chart changes its period, NT8 rebuilds the bar tree. The `idx30Min` and `idx1Min` index fields (set in `State.DataLoaded` by scanning `BarsArray` for 30-min and 1-min period matches) may now resolve to different indices. If `idx1Min` ends up pointing at the old primary index (now 5-min), all `Closes[idx1Min]`, `Highs[idx1Min]`, `Times[idx1Min]` etc. produce 5-min bar data. The entry logic silently uses 5-min bar open/close for the "1-min" retrace check, producing incorrect `wouldRetrace` evaluations.

**Detection:** Switch time frame and observe whether `inRthWindow` timing behaves correctly (9:30 detection uses 1-min bar time; a 5-min chart would resolve this at 9:35 instead of 9:30).

**Fix:** In `State.DataLoaded`, verify that the resolved `idx1Min` series is actually 1-minute period. If not, log an error and set `idx1Min = -1` to disable 1-min processing.

---

## Section 3 — Data Anomalies

### 3.1 Bad ticks / price spikes — no filter

**Trigger:** A data feed error emits a tick at price 0 or 99999 on an ES bar. NT8's bar construction for that minute incorporates the spike as the High or Low. V2_4 has no sanity check on bar OHLC values.

**Wrong behavior:** If `high = 99999`, the range filter at line 1902 (`if (px < low || px > high)`) passes EVERY level in the candidate list as "in range." Multiple touch events fire. All of them fail the retrace-side check (bar open is ~5000; every level at ~5000 satisfies `px < barOpen` for LONG candidates). No signal fires, but 15+ spurious JSONL touch events are emitted. The day's JSONL touch count spikes. The VWAP accumulator absorbs the spike.

If the spike appears as the Low (`low = 0`), an Active trade would have `low <= signalStop` evaluate true for any positive stop price, causing an instant false stop-out. The recorded P&L loss would be the full stop distance.

**Detection:** This is visible in JSONL touch counts — a session with 50+ touches in a single bar is a spike indicator.

**Fix:** Add `if (high - low > 5 * v2Adr20 || low <= 0) return;` at the top of `Process1MinBar` to skip spike bars.

---

### 3.2 Stale data feed (timestamps stuck) — no detection

**Trigger:** Rithmic or Continuum feed delivers bars with identical timestamps for multiple consecutive bars (a known issue during connectivity degradation).

**Wrong behavior:** `barTime` and `barOpen` are computed from `Times[idx1Min][0]`. If two consecutive bars have the same timestamp, V2_4 processes both identically — same `h`, `m`, same `canTrade` evaluation, same VWAP accumulation. If the first bar already latched a level, the second bar's latch check blocks it. If the first bar did not latch (price was not in range), the second bar is effectively a duplicate scan. No signal double-fires due to the `barTime <= signalTime` same-bar guard (line 2542), but the state machine can stall (pending-bar-created but fill-checked on same timestamp, looping).

**Detection:** Log `Print("TIMESTAMP REPEAT: " + barTime)` when `Times[idx1Min][0] == Times[idx1Min][1]`.

**Fix:** At top of `Process1MinBar`, `if (barTime == lastProcessed1MinTime) return; lastProcessed1MinTime = barTime;`.

---

### 3.3 Missing bars at session boundaries — box capture silent failure

**Trigger:** On a low-liquidity holiday session (e.g., December 26), the 9:30 RTH 30-min bar may simply not exist in the data — the first bar of the day might be at 9:31 or later. Similarly, the session-close bar at 15:00 might be the last bar at 14:59.

**Wrong behavior:** The box capture logic (`Process30MinBar`) matches on `h == rthOpenHour && m == rthOpenMinute` (line 1149) for the 9:30 box. If the first available bar opens at 9:31, `m == 30` fires on the 9:31 bar's OPEN time (which is 9:30 from the bar's perspective — `barOpen = barTime.AddMinutes(-30)` puts the 9:31 close bar's open at 9:01, wait — actually the 30-min series bar that closes at 9:31 opens at 9:01, which is `h=9, m=1`, NOT `h=9, m=30`). So the 9:30 box capture does NOT fire on a 9:31-open bar because `m == 1 != 30`. The `RTH930` box is null for the entire session.

**Wrong behavior compounding:** `ClassifyAMDayType()` at line 4394 requires `d != null` for Stage 1 (final) classification and uses `RTH930OpenPx` for Stage 2 (preliminary). If `RTH930OpenPx` is never set (no 9:30 1-min bar), `currentDay.RTH930OpenPx == double.NaN`, and line 4418 returns `AMDayType.Unknown`. `v2TrendDir = null`. `canTrade = false` for the entire session. Zero signals on a day where valid setups existed.

**Detection:** Check JSONL for sessions where day_type never exits "unknown" in heartbeats.

**Fix:** If no 9:30 bar is available, use the first RTH bar as a proxy. The fallback should log a warning and set `RTH930OpenPx` to the first available RTH 1-min open price.

---

### 3.4 Daylight Savings Time — spring-forward (March 2026)

**Trigger:** On the spring-forward day (second Sunday of March, in 2026 this was March 8), clocks jump from 2:00 AM to 3:00 AM ET. This means 2:00–3:00 AM ET does not exist on that day. V2_4 captures the Midnight box at `h==0 && m==0` and Europe 4AM at `h==4 && m==0`. These are exchange-time captures (NT8 uses ET for CME instruments). On the spring-forward day, the bar labeled "4:00 AM ET" by NT8 is actually the first bar of the post-DST-shift session. The Europe box captures correctly because NT8 translates to ET.

**The real risk** is with the user's machine clock. If the Windows system time is UTC and NT8 internally works in ET but the user has set a custom timezone offset, the `barOpen.Hour` comparison (line 974: `h = barOpen.Hour`) may be off by one hour on the transition day. The 9:30 ET box would fire at 8:30 AM ET (one hour early), capturing the wrong bar.

**Detection:** Check whether `currentDay.RTH930` in the JSONL box data for March 8–9, 2026 has the correct High/Low values consistent with the actual 9:30 AM ET bar.

---

### 3.5 Holiday early-close (Black Friday, Christmas Eve, July 4 Eve)

**Trigger:** NYSE/CME holiday schedule includes early close days (1:00 PM ET on Black Friday, 1:00 PM ET on July 3 Eve if July 4 is a Friday, etc.). V2_4 hardcodes `closeHour = 15, closeMinute = 0` (line 851). On an early-close day, the exchange stops trading at 13:00 ET.

**Wrong behavior:** The `inRthWindow` gate (line 1609) keeps `canTrade = true` through 14:30 ET (15:00 - 30 minutes). An Active signal would not be closed until `barTime >= 15:00` — which never arrives because the exchange has no bars after 13:00. The signal remains `Active` forever. The next day (a long weekend), V2_4 starts fresh with `ResetForNewDay()` — but only if the 15:00 session-close bar triggers the archive/reset sequence in `Process30MinBar`. On an early-close day with no 15:00 bar, `ResetForNewDay()` never fires. State carries over to the next trading day: `currentSignalState = Active`, `signalsToday = 1+`, `v2TouchedThisSession` not cleared.

**Detection:** Load a chart spanning Black Friday 2025 (November 28). Inspect whether `ResetForNewDay()` fires.

**Fix:** Add a fallback session-reset trigger: if `barOpen.Date != v2TodayDate` in `Process30MinBar` (analogous to the 1-min day-rollover check at line 1402), force `ResetForNewDay()` even if the 15:00 bar was never seen.

---

### 3.6 Holiday full close (Christmas, New Year's Day, Good Friday)

**Trigger:** No bars exist on full-close holidays.

**Wrong behavior:** State from the prior session persists. The indicator does not reset until the first bar of the next trading day triggers a rollover. On a full-close day, `ResetForNewDay()` has no trigger. The `lockoutActive` flag, `signalsToday`, and the latch set all survive from the prior session into the next. A locked-out session on Wednesday December 24 (Christmas Eve) carries the lockout into Thursday December 26.

**Detection:** Systematic — check whether lockout from December 24 persists on December 26.

**Fix:** Same as 3.5 — use the date change on the first bar of the new session as the rollover trigger, independent of seeing the 15:00 close bar.

---

## Section 4 — Order / Broker Edge Cases

### 4.1 Limit fills between `OnBarUpdate` calls — V2_4 cannot detect

**Trigger:** V2_4's fill check (lines 2560–2579) only runs at `OnBarClose` for the 1-min bar. If the user's manually-placed limit fills intrabar (at any point within the minute) but closes far from the entry price, V2_4's bar-data check still correctly detects the fill at bar close (since `low <= entry` is evaluated against the bar's low, not the close).

**Wrong behavior:** Not a silent failure for entry detection. However, for exit timing, the hard-stop check is also bar-close: `low <= signalStop` (line 2601). If price spikes through the stop intrabar and recovers, the bar's low will be below the stop and V2_4 will record a stop-out. Actual broker behavior depends on order type — a limit stop would not fill if price recovered; V2_4 records a loss regardless. The P&L ledger diverges from broker reality.

**This is a fundamental architecture mismatch**: V2_4 uses bar-data simulation of order fills, not broker-confirmed fills. The NT8 execution audit documents this explicitly.

---

### 4.2 Stop and target both hit within the same bar

**Trigger:** In FADE mode, a signal has both a `signalStop` (below entry for long) and `signalTarget` (above entry). In a volatile bar, `low <= signalStop AND high >= signalTarget`.

**Wrong behavior:** `MonitorSignal` checks stop FIRST (line 2601), then target (line 2623). The stop branch fires first: `RecordAndDrawTrade(signalStop, ...)` records a loss, sets `currentSignalState = None`, and returns. The target is never checked. This is the conservative (correct-for-a-real-stop-order) assumption: if both levels were hit, the stop hit first because it is closer to entry for a limit-entry scenario.

**Edge case violation**: If the bar opened ABOVE the target (gap up) on a long trade, `high >= signalTarget` is true but `low <= signalStop` is false. Correct — target fires. But if the bar opened BETWEEN entry and target, both are reachable intrabar, and the sequence ambiguity is resolved by the code's "stop first" ordering. For a broker with proper OCO brackets, the actual fill depends on which order was triggered first tick-by-tick. V2_4's resolution will sometimes differ from the broker's.

**Detection:** Track sessions where both stop and target are hit on the same bar.

**Fix:** Document this known discrepancy in the code. For a real execution layer, use OCO brackets at the broker — the broker resolves the ambiguity correctly.

---

### 4.3 Partial fills — V2_4 assumes full fill

**Trigger:** If the user places the ATM order and only part of it fills (queue congestion, market impact), V2_4 has no concept of partial fills. It transitions from Pending to Active on the assumption that the full quantity entered.

**Wrong behavior:** V2_4's P&L math at line 2750 uses `qty` (1 or 2, derived from `signalSizeNote`) as the full fill quantity. If only 1 of 2 MES contracts filled, the P&L calculation overstates the actual trade by 2x. `realizedPnlDollarsToday` and `losingTradesToday` can both be wrong. A partial stop-out might not trigger the lockout when it should.

---

### 4.4 Margin call mid-trade — broker liquidates, V2_4 still thinks position is open

**Trigger:** User's account hits margin threshold; broker issues a margin call and force-liquidates the position.

**Wrong behavior:** V2_4 has no `Account.Positions` check, no `OnPositionUpdate` handler, no `OnExecutionUpdate` callback. It remains in `SignalState.Active` indefinitely, trails the SMA20, and eventually time-closes at 15:00 ET — recording a "TimeClose" result at `close` price as if the position had been held the entire time. The P&L record will not match the broker's actual liquidation price. `losingTradesToday` may not increment correctly depending on whether the recorded close price happened to be a win or loss vs entry.

---

### 4.5 Order rejected — V2_4 thinks it's pending forever

**Trigger:** User clicks STAGE, attempts to submit an ATM in ChartTrader, and NT8 rejects the order (margin, instrument not enabled for trading, connection issue).

**Wrong behavior:** V2_4 transitions from Pending to Active based on bar-data fill check (`low <= signalEntry`), entirely independent of whether the order was actually placed. If price touches the entry level, V2_4 assumes it is filled and starts trailing — while the broker has no position. The trailing stop update alerts (`A8_StopUpdate_*`) will fire, telling the user to move a stop that does not exist.

---

### 4.6 Connection drop while a pending signal is live

**Trigger:** NT8 loses data feed while V2_4 is in `SignalState.Pending`. No bars arrive. `OnBarUpdate` stops firing.

**Wrong behavior:** The pending signal does not expire. The 14:30 ET cancellation check (line 2526) only fires when `MonitorSignal` is called, which requires `OnBarUpdate` to fire. If no bars arrive, the pending state persists through reconnect. On reconnect, NT8 replays missed bars. If any of those bars had `low <= signalEntry` (long), V2_4 will detect a fill during the bar replay and transition to Active — even though the user had no actual position during the gap. After reconnect, V2_4 is in Active state with a phantom position.

**Detection:** Force a data feed disconnect while a signal is Pending. Observe state on reconnect.

---

## Section 5 — UI / Interaction Edge Cases

### 5.1 User clicks STAGE then immediately clicks SKIP

**Trigger:** `OnStageClicked` and `OnSkipClicked` are mouse-event handlers. In NT8, UI events fire on the UI thread. If both are clicked in rapid succession, NT8 may dispatch both events before V2_4's state machine has processed the first.

**Wrong behavior:** `OnStageClicked` sets `cardStaged = true` and fires the alert. `OnSkipClicked` hides the card (line 3971). Net result: the staging card is hidden, the JSONL ticket event fired, and the alert fired — but the card is not visible. The user may believe the trade was not staged (card is gone) while the JSONL contains a staged ticket. Whether this matters depends on the user's workflow, but it represents a UI state inconsistency.

---

### 5.2 User opens NT chart Properties dialog (causes Restart) mid-trade

**Trigger:** Right-clicking the chart and selecting Properties triggers `State.Configure` → `State.DataLoaded` → full rebuild. All in-memory state is lost.

**Wrong behavior:** Identical to Section 2.3 — active position forgotten, lockout reset, P&L reset.

---

### 5.3 User changes any indicator parameter mid-session

**Trigger:** Changing `MaxDailyLossDollars`, `CooldownMinutes`, or any parameter in the Properties pane while V2_4 is running triggers a `State.Transition` that rebuilds the indicator. All mutable state resets.

**Wrong behavior:** Same as 2.3. Particularly dangerous for `MaxDailyLossDollars`: changing this parameter during a losing session resets `realizedPnlDollarsToday = 0`, disabling the lockout for the rest of the session.

---

### 5.4 NT8 Replay engine running on same chart

**Trigger:** User enables NT8's Market Replay on a chart that has V2_4. Replay delivers bars as `State == State.Realtime` (NT8 reports `IsInReplay` but does not change `State`).

**Wrong behavior:** V2_4 checks `State == State.Realtime` for all live-only side effects: JSONL signal events, sound alerts, staging cards, lockout/PnL accounting. All of these fire during replay. Replay produces real staging card popups and audible alerts for setups that occurred in the past. If the user stages a replay signal and the JSONL is live, a historical replay signal appears in the daily session JSONL as if it were a real signal. The date in the JSONL would be the replay date (a past date), but the file path is today's date (`{JsonlLogFolder}/{today}/events.jsonl`). Past signals land in today's JSONL under wrong timestamps.

**Detection:** Run a replay on a prior date. Check today's events.jsonl for signals with yesterday's timestamps.

---

### 5.5 Firewall mode strips drawings — chart appears blank during an Active trade

**Trigger:** `ActivateFirewall` (line 2874) removes all non-`Sig_*` drawings while a trade is Active. `DeactivateFirewall` (called on any exit) re-enables drawing but does NOT immediately redraw the boxes — it relies on the next 30-min bar's `RedrawActiveBoxes` call.

**Wrong behavior:** Between a trade exit and the next 30-min bar (up to 29 minutes), the chart shows only the VWAP line and empty space where all structural boxes were. A new user may think the indicator crashed. They may then restart the indicator, triggering the state loss described in 2.3.

**Detection:** Exit a trade at 10:01 ET. The chart will be stripped until 10:30.

**Fix:** Call `RedrawActiveBoxes()` immediately in `DeactivateFirewall`.

---

## Section 6 — Logging Anomalies

### 6.1 Lockout-without-signal anomaly (2026-04-23: $2,316 loss with no logged signal)

**The JSONL data analysis confirmed**: on 2026-04-23, a `lockout` event exists recording a `$2316 daily loss / $150` limit, but the `signal` event stream for that day is empty.

**Four plausible causes, in order of likelihood:**

**Cause A (most likely) — manual trade, not a V2_4 signal.** The trader placed a manual order in ChartTrader without using V2_4's STAGE button. The position was filled, lost $2,316, and NT8's account-level P&L was recorded. V2_4's lockout fires if `realizedPnlDollarsToday <= -MaxDailyLossDollars`. But `realizedPnlDollarsToday` is computed only from `RecordAndDrawTrade` calls (line 2754), which only fire for V2_4-tracked signals. **A manual trade would NOT increment `realizedPnlDollarsToday`.** Therefore, if V2_4's lockout fires showing $2,316 loss, the only path is a V2_4-tracked signal that failed to write its JSONL `signal` event.

**Cause B — JSONL write failure.** The `LogEvent` call for the `signal` event at line 2436 is inside a `try/catch` that swallows write errors (line 2362–2368). If the JSONL file was locked (by the Python pipeline reading it), permissions changed, or disk was full, the write silently fails. The `signal` event exists in V2_4's state machine but never reaches the file. The subsequent `lockout` event (written separately) does succeed, producing the anomaly.

**Cause C — race between lockout and signal-emit.** `RecordAndDrawTrade` at line 2604 fires after a stop-out, then calls `CheckLockout` (line 2615 via `CheckDayDone`). `CheckLockout` writes the JSONL `lockout` event (line 4007). The JSONL `signal` event was written at `SetSignal` time (line 2436) — earlier. If the chart was reloaded between `SetSignal` and `RecordAndDrawTrade`, the `signal` write succeeded to a session directory, then the directory may have been reset or pointed to a different date. This is low-probability but possible during a mid-session indicator parameter change.

**Cause D — V2_4 crashed mid-signal.** The `OnBarUpdate` try/catch at line 956 means a crash inside `SetSignal` (which is not inside Process30MinBar/1MinBar's normal path — it's called from `CheckEntry` which IS inside the try/catch) would be swallowed. If `SetSignal` threw an exception after setting `signalDirection/Entry/Stop` but before writing JSONL, state is Active but no log event exists. However, `SetSignal` precedes the JSONL write (line 2436) only by the shadow-observer event (line 2412) — if the shadow-observer `onSignal?.Invoke` threw, the catch would swallow it and return, never reaching the JSONL write. **This is a confirmed code path for silent signal loss**.

**Detection:** For Cause D: wrap the `OnTouch`/`OnSignal` event invocations in their own try/catch and log separately. For Cause B: log write failures with timestamps.

---

### 6.2 Touch events double-firing in pre-V2_4 era (35.6% dedup rate)

**Root cause confirmed by JSONL analysis**: pre-2026-03-17 sessions show up to 8x duplication of touch events within the same minute. This is NT8 chart replay re-walking the bar history when the chart is scrolled or reloaded. `Process1MinBar` fires for each historical bar each time the chart re-processes them. The JSONL logger appends without checking for duplicates.

**Wrong behavior in downstream analysis**: any Python pipeline that consumes the raw JSONL without deduplication inflates touch counts by ~3-4x for pre-upgrade sessions. The touch frequency metrics are skewed toward January 2026 (the worst-offending period). Qualifying-touch counts per session are overstated by the same factor.

**Fix:** The V2_4 era appears to have improved this (low dedup rate post-2026-03-17). The fix was likely the `State == State.Realtime` gate on many event types. For the remaining Historical-mode touch events, deduplicate at the logger level using a `HashSet<string>` of the last N event payloads, keyed by `(bar_time, type, level)`.

---

### 6.3 Schema break at 2026-03-17 — incomparable eras

**Wrong behavior:** The 96 pre-upgrade sessions contain only `touch` events. No `heartbeat`, `phase`, `bias`, `bar_close`, `signal`, or `lockout` events. Any analysis that uses the full event set cannot use the pre-upgrade sessions. Specifically, day-type analysis (which day-type correlates with higher qualifying-touch density?) cannot be answered from historical data — there are no day-type labels before 2026-03-17.

**Impact on calibration:** The team identified "only 7 sessions with heartbeats." These 7 sessions are the only calibration data for any rule that depends on phase, day_type, bias, or MOC. 7 sessions is statistically insufficient for any validation.

---

### 6.4 JSONL write failures — silent (file lock, disk full, permissions)

**Trigger:** `File.AppendAllText(jsonlPathToday, sb.ToString())` at line 2364 is wrapped in a try/catch that only prints to NT Output on failure (line 2368). NT Output is not visible unless the user has it open.

**Wrong behavior catalog:**
- **File lock contention**: If the Python cockpit dashboard has the events.jsonl file open with exclusive lock, NT8's `AppendAllText` throws `IOException`. The catch prints one line to NT Output. ALL subsequent JSONL writes silently fail for that session.
- **Disk full**: Same behavior. The indicator continues to function, signals fire, staging cards appear, but zero logging occurs.
- **Directory not created**: `jsonlPathToday` is initialized with lazy directory creation (inferred from code pattern). If the parent directory path is wrong (user edited `JsonlLogFolder` to an invalid path), the first write attempt fails, and the JSONL session is empty for the day.
- **Multi-instance race**: Two V2_4 instances on two charts writing to the same file simultaneously. `File.AppendAllText` is not atomic on Windows for multi-process access (it opens, writes, closes). Interleaved writes from two processes can corrupt lines.

**Detection:** Add a startup test in `State.DataLoaded`: write a test line to the JSONL file, read it back, and log success/failure.

---

## Section 7 — Backtest vs Live Divergence

### 7.1 Historical mode skips lockout/cooldown → backfill overstates trade count

**Confirmed by code**: `lockoutActive` is only set in `CheckLockout` which fires after `RecordAndDrawTrade`. `RecordAndDrawTrade` runs in both Historical and Realtime (line 2750 accumulates PnL). However, `CheckLockout` at line 3993 checks `MaxDailyLossDollars > 0 && realizedPnlDollarsToday <= -MaxDailyLossDollars`. In Historical replay, `realizedPnlDollarsToday` IS accumulated (via line 2750 comment: "Historical path does not accumulate PnL for lockout/size analysis"). Actually checking the code: lines 2754–2759 gate PnL accumulation and lockout on `State == State.Realtime`. So in Historical, `realizedPnlDollarsToday` stays at 0, and `lockoutActive` never fires. Historical backfill can produce unlimited signals per day.

**Wrong behavior:** Historical replay of V2_4 can show 5+ signals in a day where live operation would have been locked out after signal #2. The backfill signal count systematically overstates what would actually fire in production.

### 7.2 Pending cancellation cutoff differs in Historical

**Confirmed by code**: The 14:30 ET pending cancel check at line 2526 runs based on `barTime` (bar-close time). In Historical replay, bars are replayed sequentially. The 14:30 bar fires at the correct time. The cutoff behavior is identical in Historical and Realtime — this is correctly implemented.

### 7.3 OnBarClose vs intrabar tick semantics

**Trigger:** V2_4 uses `Calculate.OnBarClose` (line 726). All entry and exit decisions are made at bar close. In live trading, the bar close for a 1-min bar is the last tick of that minute. Between bar closes (intrabar), V2_4 is blind.

**Wrong behavior:** A fill that happens at 9:30:05 ET (5 seconds into the 9:30 bar) is not detected until the 9:30 bar closes at 9:31. For the first 55 seconds of a minute, V2_4 does not know the trade has been filled. This means the hard-stop check is also delayed by up to 59 seconds. In a fast market, price can move 5+ points in 59 seconds — the difference between the stop price and actual stop-out is material.

---

## Section 8 — Calendar / Time Edge Cases

### 8.1 DST transition (covered in 3.4 above)

Additional note: the spring-forward transition in 2026 was March 8. The JSONL corpus has sessions from 2026-03-17 onward with heartbeats. The March 17 session is 9 days post-DST. Any DST-related box timing bugs would have been visible in March 8–16 sessions, but those sessions have no heartbeats and no day-type labels — the DST transition effect on box captures cannot be verified from existing JSONL data.

### 8.2 Friday → Monday state carryover (recently patched for box aging)

The weekend-skip patch in box aging was documented in the version diff. However, the `v2TouchedThisSession` latch set is cleared only by `ResetForNewDay` (triggered by the 15:00 close bar) and the 1-min day-rollover (midnight). Over a Friday → Monday transition, the 1-min day-rollover fires Saturday at midnight and again Sunday at midnight — each time clearing the latch. By Monday's RTH open, the latch is empty. No carryover issue here.

What remains unaddressed: `lockoutActive` is cleared in `ResetForNewDay`. On a Friday session that ends in lockout, `ResetForNewDay` fires at the 15:00 close bar, clearing the lockout. Monday starts clean. This is correct behavior.

### 8.3 Holiday full close — state carryover (documented in 3.6 above)

Critical finding: `ResetForNewDay` depends on seeing the 15:00 close bar. On a full holiday close (no bars), `ResetForNewDay` never fires. The session state from the prior day (Wednesday before Thanksgiving, for example) carries into the Friday session. This means:
- `signalsToday` is not reset — Friday starts with 1 or 2 already counted against the cap.
- `v2TouchedThisSession` is not cleared — Friday's first touch of any level that was touched on Wednesday is silently skipped as already-latched.
- `lockoutActive` from Wednesday persists — Friday cannot trade at all.

This is a confirmed, systematic source of missed setups for sessions following full-close holidays.

### 8.4 Sunday open at 18:00 ET (GlobEx) — `currentDay.Date` set to Saturday

At line 1114, after session close: `currentDay = new DayBoxes { Date = barTime.Date.AddDays(1) }`. The Friday 15:00 bar has `barTime.Date = Friday`. AddDays(1) = Saturday. The new `currentDay.Date` is Saturday. The GlobEx 6PM bar on Sunday evening has `barOpen.Date = Sunday`. In `Process30MinBar`, `EnsureCurrentDay(barOpen)` checks `if (currentDay == null)` — it is not null (it was created at Friday close). The GlobEx box is captured into the Saturday-dated `currentDay`. 

When Monday's 1-min day-rollover fires (`sessionDate = Monday's date != v2TodayDate = Saturday`), the latch is cleared and `v2TodayDate = Monday`. No harm done at runtime. But any downstream code that queries `currentDay.Date` and expects it to equal the trading day will find Saturday instead of Monday for all the boxes captured Sunday–Monday pre-RTH. For JSONL analysis where session dates are cross-referenced, this is a silent data-quality issue.

### 8.5 Year-end rollover

No specific year-end handling exists. The indicator processes the December 31 session normally (close at 15:00), resets for the next day, and the GlobEx bar on January 1 (if it exists — New Year's Day is a holiday) would be skipped. The `v2DailyRanges` queue accumulates a rolling 20-day ADR. Year-end is not special here.

The potential issue: `dayHistory` uses `List<DayBoxes>` with a maximum of `DaysOfHistory` entries. The `DayBoxes.Date` field uses `DateTime` which correctly handles year boundaries. No overflow or logic error expected.

---

## Section 9 — Silent Failures That Cause "Missing Setups"

This is the section directly answering Afshin's pain. Each mechanism is a silent drop path — no error, no alert, no log line, the setup simply does not fire.

### 9.1 `if (latched) continue` — re-touches of the same level after flat exit

**Code**: Line 1945: `if (latched) continue;` where `latched = v2TouchedThisSession.Contains(name)`.

**Mechanism**: Static-name levels (`PrInstH`, `GlobExH`, `EuropeL`, etc.) are latched with the exact level name. Once a level fires for the session, the latch persists until `ResetForNewDay`. Even if the signal was a stopped-out loss, the level is done for the day. A second, cleaner retracement to the same level in the afternoon is silently dropped. `Pr30` uses time-stamped keys (`Pr30H@1030`) so each 30-min roll re-enables the level — but structural levels get one chance.

**Evidence**: The JSONL touch data shows `already_latched = True` for 718 of 2,956 unique touches (24.3% of all touches). Each of those is a potential missed setup that was blocked by prior latch.

**Detection**: Add a JSONL `canTrade_blocked` event explaining the reason. Every `if (latched) continue` path should write `reason: "already_latched"`.

---

### 9.2 `if (!wouldRetrace) continue` — strict inequality drops touches exactly at bar open

**Code**: Line 1946: `if (!wouldRetrace) continue;` where `wouldRetrace = isLong ? (px < barOpen) : (px > barOpen)`.

**Mechanism**: If a level is exactly at the bar's open price (`px == barOpen`), `px < barOpen` is false (strict), and `wouldRetrace` is false for a long. The touch is dropped. In practice, ES ticks at 0.25 increments — a level at exactly 5000.00 and a bar open at exactly 5000.00 (common on round-number levels on the first bar after a level break) drops the signal.

**Evidence**: The JSONL data analysis notes this as a known edge case. No quantitative count is available since `retrace_side` is computed with the same strict comparison, so `already_latched=false, retrace_side=false` rows in the JSONL include both true non-retrace touches AND touches exactly at bar open.

**Detection**: Add logging for `px == barOpen` cases.

---

### 9.3 ORH/ORL: only candidates after OR-lock (first 30 min invisible)

**Code**: Lines 1855–1859: `if (v2OpenRangeLocked)` gates the addition of `ORH/ORL` to the candidate list.

**Mechanism**: For the first 29 1-min bars after RTH open (9:30–9:59 ET), ORH and ORL do not exist in the candidate pool. Any setup at the developing OR high or low before the lock is invisible. This is intentional per AM's method (the OR hasn't locked yet), but if price spikes to the eventual OR boundary at 9:40 and retraces cleanly — a valid AM-style setup — it fires with no signal.

---

### 9.4 Pr30: only available after 10:00 — first 30 minutes have no rolling Pr30

**Code**: Lines 1293–1303 in `Process30MinBar` only set `v2PriorRolling30High/Low` on RTH bars, starting after `rthOpenHour`. The first Pr30 bar closes at 10:00 ET (the 9:30 RTH bar). Before 10:00, no Pr30 level exists in the candidate pool.

**Mechanism**: The most active 30-minute window of the session (9:30–10:00) has the fewest structural candidates: only GlobEx, Europe, Midnight, and PrInst are available. Any valid retracement to the 9:30 bar's high or low is invisible until the next Pr30 rolls at 10:30.

---

### 9.5 VWAP/AnchVWAP intentionally excluded — but VWAP is the single most-touched level

**Code**: Lines 1872–1880 explicitly exclude `VWAP` and `AnchVWAP` from the candidate list.

**Evidence**: VWAP accounts for 433 of 2,956 unique touches (14.65%). AnchVWAP accounts for 190 (6.43%). Together they are 21.1% of ALL touches. The two signals in the 6-month corpus BOTH fired at VWAP. This is the single highest-volume level by touch count, and it is categorically excluded. AnchVWAP has the highest qualifying ratio of any level (36.8% — meaning when it fires it is very often on the retrace side and unlatched).

**The exclusion is documented as intentional** (per AM's "VWAP is permission, not destination"). But the empirical evidence suggests VWAP rejections in `rthactive` are the only category that actually fired signals in the V2_4 era. If this exclusion is wrong — or if it applies to certain day types but not others — removing it would be the single highest-leverage change for signal recovery.

---

### 9.6 MidMid only if `currentDay.Midnight != null`

**Code**: Lines 1828–1831: `if (currentDay?.Midnight != null) AddLevel(cands, "MidMid", ...)`.

**Mechanism**: The Midnight box is captured at `h==0 && m==0` in `Process30MinBar`. For instruments that do not trade during the GlobEx overnight session (rare for ES/NQ, but relevant for CL sessions with gaps), there may be no 0:00 bar. `currentDay.Midnight` is null. MidMid is never in the candidate pool for that session. This is correct defensive behavior, but it means any late-session retracement to the mid-Midnight level fires no signal without any explanation.

---

### 9.7 Sideways + flat 200-SMA slope → `tradeMode = null` → no fire all session

**Code**: Line 1582: `(v2DayType == AMDayType.Sideways && (slopeUp || slopeDown)) ? "FADE" : null`.

**Mechanism**: If `ClassifyAMDayType()` returns `Sideways` AND `currentDay.Sma200SlopeDelta` is NaN (not yet computed, or the baseline comparison is invalid), `slopeUp` and `slopeDown` are both false. `tradeMode = null`. `v2TrendDir = null`. `canTrade = false` for the entire session. No signal can fire regardless of how many qualifying touches occur.

**When does Sma200SlopeDelta remain NaN?**: On the very first session after the indicator is loaded on a new chart (no `priorSma200At930`). Line 1168 captures `currentDay.Sma200At930` using `sma200Ind30[0]` directly at the 9:30 bar. Line 1178: `currentDay.Sma200SlopeDelta = today - priorSma200At930`. `priorSma200At930` is populated from `priorDay.Sma200At930`. On the first session, `priorDay` may be null or may have `Sma200At930 = NaN`. The slope is NaN.

**Evidence**: The JSONL data shows `unknown` day_type dominating heartbeats at 32% of all heartbeat rows. A `Sideways + NaN slope` session would remain `unknown` in the heartbeat's `day_type` field (which uses `currentDayType`, not `v2DayType`). However, the session would show no signals, and the Pre-Place Panel would show "SIDEWAYS" with no direction.

---

### 9.8 FADE candidate filter — only slope-side levels

**Code**: Lines 1802–1817: FADE mode adds candidates only for the trend-direction side. `GlobExL` for LONG, `GlobExH` for SHORT, etc.

**Mechanism**: On a Sideways day with 200-SMA sloping up (LONG FADE direction), the candidate pool is restricted to the HIGH side of each structural box (the resistance levels above price) as potential short-side retrace entries. Wait — actually for LONG FADE with upslope, `isLong = true`, and FADE adds `GlobExL`, `EuropeL`, `PrInstL` — the LOW levels. These are support levels where price can retrace down to and bounce. This is correct: FADE long means fade the move down, entry at support.

The constraint is that FADE does NOT add both sides. A Sideways day with up-slope only trades from the long side (buying dips to support). The short side of the same day is not traded. If AM's method allows FADE trades in both directions on a Sideways day (sell resistance AND buy support), V2_4 misses half the potential signals.

---

### 9.9 `tradeMode == null` → Sideways + flat slope = no trade

Covered in 9.7. Summary: a Sideways day with flat or NaN 200-SMA slope is a complete no-trade session. The Pre-Place Panel shows the levels, qualifying touches fire in the JSONL, but `canTrade` is permanently false. This is the most common silent-drop state for new chart loads.

---

### 9.10 `canTrade` requires `currentSignalState == None || Pending` — Active blocks new candidates

**Code**: Line 1630.

**Mechanism**: While a signal is Active, V2_4 cannot set a new signal. `CheckEntry` is not called. If AM's method allows "add to position at the next level" on a strong trend day, V2_4 will miss those add signals entirely. No warning is issued — the Active signal simply blocks all subsequent candidate evaluation.

---

### 9.11 Cooldown: 30 min after a stop blocks valid retests

**Code**: Lines 4014–4020, `IsInCooldown()`.

**Mechanism**: After a stop-out, V2_4 blocks all new signals for `CooldownMinutes` (default 30). A clean retracement to a different structural level 10 minutes after the stop is silently blocked. No JSONL event or alert explains the block. With 2 or 3 signals per day cap and a 30-minute cooldown, the effective trading window is dramatically compressed: a 9:40 stop-out + 30 min cooldown = no new signals until 10:10. A 10:15 stop-out = no new signals until 10:45.

**Evidence**: The JSONL has no `canTrade_blocked` event. It is impossible to quantify from the current data how many valid setups were blocked by cooldown. The audit comments note `diagSmaBlockCount` was retained but is no longer incremented (the SMA gate it counted was removed). The cooldown block has no counter.

---

### 9.12 Lockout: triggers on dollar loss, silently blocks a valid third trade

**Code**: `CheckLockout` at lines 3981–4012.

**Mechanism**: Once `lockoutActive = true` fires, it cannot be reversed until `ResetForNewDay`. The lockout check fires after a stop-out. If the first two trades of the day are stops and the dollar sum exceeds `MaxDailyLossDollars`, the third trade — even a perfectly valid AM setup — cannot fire. The panel shows a red lockout banner, which is correct UX. But the JSONL `lockout` event (line 4007) is emitted once, and subsequent qualifying touches are silently discarded with no follow-on events.

---

### 9.13 `MaxSignalsPerDay`: cancelled pendings count against the cap

**Code**: Line 2455: `signalsToday++` fires at `SetSignal` — at Pending creation. If a pending signal expires at the 14:30 ET cutoff (line 2534), `signalsToday` is NOT decremented. The signal budget is consumed by a signal that never traded.

**Example**: Day has 3-signal cap. Signal 1 fires at 10:00, stops out. Signal 2 fires at 11:00, pending at 13:45, auto-expires at 14:30. `signalsToday = 2`. A valid 3rd setup at 13:55 (after signal 2's expiry) fires `CheckEntry`. `signalsToday = 2 < effSignalCap = 3` is still true, so `canTrade = true`. This case does NOT cause a missing setup here. The budget is correctly available.

BUT: if Signal 2 fired and never expired (filled intrabar, went Active, then stopped out), `signalsToday = 2`. A clean 3rd setup at 12:30 is blocked only if `signalsToday >= 3`, which is false. The FADE cap is more severe: `effSignalCap = min(2, 3) = 2`. After 2 FADE signals (regardless of outcome), no more FADE signals fire for the day.

---

### 9.14 Day-type vocabulary mismatch — JSONL never emits `Sideways`

**Critical finding from JSONL analysis**: The heartbeat `day_type` field uses `currentDayType.ToString()` (line 2383), which is the legacy `DayType` enum: `Congestion / Trending / Extended / Unknown`. The V2_4 AM body-stack classifier produces `AMDayType.Sideways`, but this is never emitted to JSONL. The heartbeat shows `congestion` while the actual gate is `Sideways`.

**Wrong behavior**: Anyone using the JSONL to determine whether FADE rules should have fired will see `congestion` and not know if FADE was active. The FADE gate checks `v2DayType == AMDayType.Sideways` (computed locally in `Process1MinBar`, never stored in a field accessible to JSONL). There is no way from the current JSONL to determine whether a session was a FADE-eligible session.

**Evidence**: 0 of 103 sessions show any of `LongTrend / ShortTrend / CautiousLong / CautiousShort / Sideways / Unknown` in heartbeat day_type. The spec strings never appear.

---

## Top 20 Failure Modes by Probability × Impact

Probability and impact are rated adversarially: probability = likelihood the condition occurs in a real trading session; impact = severity of the wrong behavior (signal loss, P&L error, or silent corruption).

| Rank | Failure Mode | Section | Probability | Impact | Combined |
|------|-------------|---------|-------------|--------|----------|
| 1 | **Day-type vocabulary mismatch: JSONL emits `congestion`, not `Sideways` / `LongTrend`** — FADE sessions are unidentifiable from JSONL; post-hoc analysis correlates wrong axis | 9.14 | Certain (100%) | Critical — invalidates all JSONL-based day-type analysis | **Critical / Confirmed** |
| 2 | **VWAP/AnchVWAP excluded from candidates** — 21.1% of all touches, both historical signals came from VWAP; every qualifying VWAP retrace silently drops | 9.5 | Certain (every session) | High — systematic suppression of the most common level | **Critical** |
| 3 | **Sideways + flat/NaN 200-SMA slope → no trade all session** — first session after load, sessions following holidays or data gaps produce NaN slope and zero signals | 9.7 | High (every first-load session, holiday-following sessions) | Critical — zero signals for entire sessions | **Critical** |
| 4 | **Missing setups due to static-level first-touch latch** — after first touch, level is dead for the day regardless of outcome | 9.1 | High (24.3% of touches in corpus are already-latched) | High — each latched re-touch is a potentially missed signal | **High** |
| 5 | **Holiday full-close: `ResetForNewDay` never fires, state carries forward** — `lockoutActive`, `signalsToday`, latch set persist into the next session | 3.6 | Medium (several times per year) | Critical — next session is locked out or under-budgeted before it starts | **High** |
| 6 | **`canTrade` lockout persists after chart reload / parameter change** — crash or parameter edit resets all state including `lockoutActive` to false; live position forgotten | 2.3 | Medium (any param change mid-session) | Critical — lockout bypass, P&L ledger reset | **High** |
| 7 | **Lockout-without-signal anomaly** — JSONL `lockout` event with no preceding `signal` event; logging gap or race in signal emit (confirmed 2026-04-23) | 6.1 | Low-medium (confirmed once in 103 sessions) | High — indicates signal events are being silently dropped | **High** |
| 8 | **CL `rthOpenHour` hardcoded at 9:30 instead of 9:00** — all time gates are 30 min late for CL; RTH930 box captures wrong bar; VWAP reset wrong; OR window wrong | 1.4 (CL) | Certain for CL users | Critical for CL — systematic wrong-bar captures all session | **High (CL-specific)** |
| 9 | **`try/catch` in `OnBarUpdate` swallows Historical exceptions silently** — cold-start null-refs, SMA initialization failures, first-bar state errors are invisible | 1.2 | Medium (cold-start paths) | High — can corrupt state silently, producing wrong day-type classification | **High** |
| 10 | **FADE mode: `effSignalCap = min(2, MaxSignalsPerDay)` — 2 FADE signals maximum; expired pendings count against cap** | 9.13 | Medium | Medium — limits valid FADE recovery trades after early stops | **Medium-High** |
| 11 | **AnchVWAP re-anchor walkback is O(N) — may run mid-signal** — ContainmentCheck promotion mid-session re-walks the VWAP history; silently changes anchored VWAP context for active signal | 1.10 | Low (mid-session RTH930 box captures) | Medium — changes FADE context after signal fired | **Medium** |
| 12 | **Pattern B entirely absent (43% of touches are Pattern B eligible)** — look-below-and-fail setups silently drop; `LevelWatchState` is scaffolding only | Version diff §5 | Certain (every session with wick rejections) | High — 43% of all touches qualify as Pattern B, all dropped | **High** |
| 13 | **Cooldown blocks valid retests for 30 minutes after stop** — no JSONL event explains the block; no way to quantify suppression | 9.11 | High (any session with an early stop) | Medium — valid 3rd or later setup missed | **Medium-High** |
| 14 | **PointValue chart-vs-traded instrument mismatch (ES chart + MES trades)** — staging card shows 10x actual risk; size-bucket gate may reject valid MES setups | NT8 audit §8 | High (user likely running ES chart + MES trades) | Medium — wrong risk display, possible trade rejection | **Medium-High** |
| 15 | **Retrace-side strict inequality drops touches exactly at bar open** — `px == barOpen` produces `wouldRetrace = false`, silent drop | 9.2 | Low (rare exact price coincidence) | Low — occasional individual setup miss | **Low-Medium** |
| 16 | **SMA20 trail staleness** — `sma20_30min` cached at 30-min bar; if 1-min fires before 30-min on coincident bar-close, trail uses prior bar's SMA20 | 1.1 | Low-medium (every 30-min boundary) | Low — 1-bar staleness on trail, rare exit timing error | **Low-Medium** |
| 17 | **Bad tick / spike — no filter** — corrupted high/low invalidates bar-level analysis; if spike is a Low, phantom stop-out fires | 3.1 | Low (occasional feed corruption) | High when triggered — phantom stop-out loses money | **Medium** |
| 18 | **JSONL write failure silent** — file lock, disk full, or permissions error produces no alert; JSONL is empty while indicator runs normally | 6.4 | Low (infrastructure issue) | Medium — entire session's data lost for audit | **Medium** |
| 19 | **Early-close day (Black Friday, July 3): Active signal not closed at 13:00, `ResetForNewDay` never fires** | 3.5 | Low (few times per year) | Medium — signal stuck Active into next session | **Low-Medium** |
| 20 | **Multiple V2_4 instances on same chart pair — double-fire and JSONL race** | 2.4 | Low (requires two charts) | Medium — doubled JSONL entries, duplicate signals | **Low-Medium** |

---

## Summary for Wave 3 Coordinators

The ranked list above groups into three tiers:

**Tier 1 — Confirmed systematic suppressors (items 1–4, 12)**: These produce zero or near-zero signals on entire sessions or entire setup categories. They account for the bulk of the 99.7% signal drop rate. Items 1 and 2 are definitionally certain every session. Item 12 (Pattern B gap) represents 43% of all touches by volume.

**Tier 2 — Environmental hazards (items 5, 6, 7, 9, 14)**: These trigger on specific events (holidays, reloads, CL usage, data cold-start) rather than continuously. When they trigger, the impact is session-scale. Item 5 (holiday carryover) and item 6 (reload state loss) are the most dangerous because they corrupt the lockout enforcement layer.

**Tier 3 — Precision failures (items 10, 11, 13, 15–20)**: These produce individual missed setups or minor P&L accounting errors. Important for a production system but not the primary source of the 0.27% conversion rate.

The single highest-leverage intervention for "missing setups" is to resolve the VWAP exclusion question empirically (item 2) and fix the JSONL day-type vocabulary (item 1) so that future sessions can be categorized correctly for analysis. Without item 1 fixed, any further data collection is analytically opaque.

---

*End of failure modes report. Approximately 5,200 words.*
