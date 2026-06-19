# AMTradeCockpit V1 → V2_4 Evolution Audit

Author: Wave 2 audit, 2026-04-27.
Scope: seven sequential C# files in `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\`.
Evidence is cited as `<file>:<line>` for the production V2_4 file unless otherwise noted.

---

## TL;DR

1. The single **biggest behavioral break** in the indicator's history is V1/Dev → V2: V1's only entry mechanism (failed-retest of the first 1-minute RTH candle's high/low) was **deleted wholesale** and replaced with a level-touch retracement scorer over ~15 candidate levels. The 1-minute candle is still drawn (`RTH1Min_H` / `RTH1Min_L`) and its width still feeds the "1 MES ONLY" sizing note (`AMTradeCockpitV2_4.cs:2458`), but **no entry rule reads `rth1MinHigh`/`rth1MinLow`** in V2 onward.
2. V2 went live **without a retrace-side filter** (`AMTradeCockpitV2.cs:1391-1399` — pick closest level to bar open, period). That meant V2 fired continuation trades, e.g. LONG at ORH on a bullish breakout. V2_1 (`AMTradeCockpitV2_1.cs:1557-1558`) added the filter `bool retraceSide = isLong ? (px < barOpen) : (px > barOpen)`. The filter is structural — it eliminates an entire class of trades that V2 would have taken.
3. V2 / V2_1 / V2_2 silently used **stale `priorDay.Close330`** for the PrInst (prior-institutional) candidate. V2_3 corrected this to `currentDay.Close330` (the inst-candle that closed *before* today's RTH started), explicitly labelled in V2_3 and again in V2_4 as "the source of chronic PrInst under-detection in V2_1/V2_2" (`AMTradeCockpitV2_4.cs:1843-1847`). PrInst is one of AM's most-cited levels, so this single bug suppressed many would-be signals for three versions.
4. The trend-gate moved from **SMA-stack price > SMA50 > SMA200** (V2/V2_1/V2_2/V2_3) to **body-stacking of the four master candles** (V2_4) in a function `ClassifyAMDayType()` (`AMTradeCockpitV2_4.cs:4388-4427`). The two gates can disagree in either direction: an SMA-stacked day with body-overlap classifies as Sideways under V2_4 (FADE-only or no trade), and a Sideways-classified day where price is above SMA50>SMA200 still trades under V2_3 but only the FADE path under V2_4. Cautious-Long / Cautious-Short are NEW classifications in V2_4 — they trade through the same TREND pipeline today (sizing/stop-widening "tabled" per AM Q2, comment at `:1590-1593`).
5. Several **scaffolds are unwired** in V2_4:
   - `LevelWatchState` / `LevelWatchStatus` (`AMTradeCockpitV2_4.cs:177-200`) — class is declared, never instantiated, never referenced. Per the in-file comment "Class scaffolding placed here in this batch so the storage and refactor surface are agreed-upon before the entry-mechanism rewrite," this is a pre-staged Pattern-B retest container that the entry rewrite never followed up on.
   - `MOCValidation` is computed (`:1232-1241`) and displayed in the verdict UI (`:3431-3527`) but **does not enter the canTrade gate** — verdicts mention "REDUCED size" but `effSignalCap`, position-size, or stop math are not modified by `MocState`.
   - `DetermineDayType()` (Congestion/Trending/Extended) still computes and stores `currentDayType` from V1 onward (`AMTradeCockpitV2_4.cs:1712-1760`), but V2_4 ignores it for entry — `AMDayType` is the gate, not `DayType`.
6. **Filters that block legitimate setups in V2_4** (in priority order of likely impact on Afshin's "missing setups" sense):
   - First-touch-per-session latch (`v2TouchedThisSession.Add(bestName)` `:1978`). If the first wick into a level happens during pre-market chop and is a non-tradeable touch, the level is dead for the session.
   - `signalsToday < effSignalCap` (FADE caps at 2, TREND at MaxSignalsPerDay=3). After 3 retests of any combination of levels, no further signals fire — even if the third trade was a stop-out and the day still has hours.
   - Cooldown after a stop-out (`CooldownMinutes`, default 30) blocks even valid retests during cooldown.
   - 14:30 cancel cutoff (V2_4-specific — earlier versions used 15:00 close as cutoff). Pending limits expire at 14:30 ET; this is correct per AM but means a pristine 14:31 setup is silently discarded.
7. **Exit logic was completely rewritten between V1 and V2** and split again in V2_4. V1 had a fixed-target exit (VWAP/inst-edge/pivot/measured-move waterfall) with an "SMA flipped + price inside range" invalidation rule. V2 replaced both with a 30-min SMA20 ratchet trail (no target). V2_4 routes FADE trades to a fixed PrInst H/L target while keeping TREND on the SMA20 trail. There has **never been a level-to-level exit** as AM's stated doctrine implies.
8. Filters appeared progressively. `MaxSignalsPerDay`, `CooldownMinutes`, `lockoutActive` all existed in V1 (`AMTradeCockpit.cs:215, 289, 293, 346, 362`) but per the V2 header comment (`AMTradeCockpitV2.cs:17-18`) "Firewall (MaxSignalsPerDay / CooldownMinutes / lockout) now ENFORCED in canTrade (v1 rendered banners but didn't block entries)" — V1 displayed the lockout banner but did NOT actually block trades on the count. V2 first wired them into `canTrade`. This means V1 in production may have over-fired versus its own banner.

---

## Removed-features timeline (chronological)

### Removed at V1 → V2 (the big rewrite)

- **Failed-retest setup** (V1's only entry).
  - V1 logic: a 1-min bar breaks below `rth1MinLow` (with a 5-bar `BREAK_EXPIRY_BARS` window), then a subsequent bar wicks back into the range and closes back outside → SHORT at `rth1MinLow` (`AMTradeCockpit.cs:1183-1198`). Symmetric for LONG.
  - Status in V2_4: rule does not exist. The 1-min candle is captured and drawn (`AMTradeCockpitV2_4.cs:1474-1511`) but `rangeBrokenDown` / `rangeBrokenUp` / `BREAK_EXPIRY_BARS` are gone (Grep confirms no matches in V2_4).
  - Removal disposition: silent — no comment in V2 explains it. The V2 header (`AMTradeCockpitV2.cs:8-21`) calls it "SIGNAL LOGIC REPLACED with v2 rules" but does not justify dropping the failed-retest entirely.
  - Why this likely matters for Afshin: failed-retest is a Baiynd-style fade-the-failed-break setup that V2_4's level-touch scorer cannot reproduce. Even with the FADE branch added in V2_4, the entry is a passive limit at the level, not a confirmed-rejection trade after a break-and-rebound.

- **Institutional-candle bias gate** (`currentBias`).
  - V1 logic: shorts only fire when price closes below institutional candle (`Bias.Short`); longs only above (`Bias.Long`) (`AMTradeCockpit.cs:1150-1151`).
  - Status in V2_4: `currentBias` is still computed (`DetermineBias`, `AMTradeCockpitV2_4.cs:1767-1786`) but is not consulted in `CheckEntry`. The trend gate is `v2TrendDir` from `AMDayType`, which has no concept of institutional bias.
  - Removal disposition: silent. Comment-equivalent: V2 simply moved on.

- **Profit target waterfall** (VWAP → institutional edge → pivot → measured move → opening range fallback).
  - V1 logic in `SetSignal` (`AMTradeCockpit.cs:1216-1265`).
  - Status in V2_4: not in TREND mode. FADE mode has only one target (PrInst H/L) and no fallback — if PrInst is on the wrong side of entry the trade is *skipped* rather than fired with a different target (`AMTradeCockpitV2_4.cs:1965-1976`).

- **Pivot levels (PP/R1-R3/S1-S3)** as targets.
  - V1: computed and used as target candidates (`AMTradeCockpit.cs:1071-1086, 1238-1252`).
  - V2_4: `CalculatePivots` removed (Grep: no matches in V2_4). Loss of pivot-target structure.

- **Measured-move targets** from institutional candle.
  - V1: `target = institutionalBox.Low - institutionalBox.Range` (line 1257).
  - V2_4: `DrawMeasuredMoves` is still called for chart drawing (`AMTradeCockpitV2_4.cs:4324`), but no entry/exit consults the projected level.

- **"SMA flipped + price inside range = INVALIDATED" exit.**
  - V1: `AMTradeCockpit.cs:1362-1378`. After fill, if `smaDirection1` no longer agrees with the trade direction AND `close >= rth1MinLow && close <= rth1MinHigh`, exit at close, fire `A4_Invalid`.
  - V2_4: removed. The only exit reasons are `Stopped`, `Trail` (TREND), `Target` (FADE), `TimeClose`. There is no rule to bail out of a slow-bleeding trade that's gone sideways.

### Removed at V2 → V2_1

- **No retrace-side filter** (it didn't yet exist).
  - V2: `CheckEntry` picks closest level to bar open, period (`AMTradeCockpitV2.cs:1389-1399`).
  - V2_1 onwards: filter added (lines 1557-1558 in V2_1, line 1908/1946 in V2_4). This *removed* continuation trades from the eligible set.

### Removed at V2_1 → V2_2

- **`State.Realtime` block on canTrade.**
  - V2_1 line 1318: `&& State == State.Realtime; // no replay signals`.
  - V2_2 line 1327: still has `&& State == State.Realtime`. Survives V2_2.
  - V2_3 (and on): removed. Per V2_3 comment: "CheckEntry runs in BOTH State.Historical and State.Realtime so the pre-gate 'touch' event log builds during chart-backfill." `SetSignal` is gated to Realtime for audible/staging-card side effects; the touch log fires in both. This means V2_3+ produces backfilled trade arrows in chart history that V2/V2_1/V2_2 did not.

- **Pre-10:00 entry block (`!v2OpenRangeLocked` early return).**
  - V2: `if (!rth1MinComplete) return;` (`AMTradeCockpitV2.cs:1328`) — only requires the first minute, much weaker.
  - V2_1: `if (!v2OpenRangeLocked) return;` (`AMTradeCockpitV2_1.cs:1474`) — full 30-min OR lock required.
  - V2_2 onward removed this entirely with comment "AM does NOT impose a hard pre-10:00 entry gate" (`AMTradeCockpitV2_2.cs:1315`). ORH/ORL are individually gated (only added as candidates after lock) but pre-existing structural levels (GlobEx/Europe/Midnight/PrInst) are valid from RTH open. V2_1's gate blocked legitimate early-session retests like a 9:40 bounce off prior-institutional-high.

### Removed at V2_3 → V2_4

- **Session VWAP and AnchVWAP as entry-level candidates.**
  - V2_3 line 1625-1627: `AddLevel(cands, "VWAP", currentVWAP); ... AddLevel(cands, "AnchVWAP", v2AVWAP);`
  - V2_4: explicitly removed with the comment block at `AMTradeCockpitV2_4.cs:1872-1881` — "Per AM's method (see AM_strategy_summary.md: 'VWAP/AVWAP are permissions, not limit-order destinations' and apr-10: 'you can't just buy VWAP — it gets retested all day'). They remain on the chart and in heartbeat/signal logs as diagnostics, but CheckEntry must never pick them as bestName."
  - Disposition: documented removal. Whether AM's method is correct is outside the scope of code audit, but this is the largest *behavioral* removal in V2_4.

- **30-min SMA-stack trend gate.**
  - V2_3 lines 1370-1376: `bool trendLong = trend30Valid && close30 > sma50_30min && sma50_30min > sma200_30min;` defines `v2TrendDir`.
  - V2_4: replaced by `ClassifyAMDayType()` body-stack classifier. The SMA-stack is no longer the gate; it is "retained as a diagnostic only" (`AMTradeCockpitV2_4.cs:1567-1599`). 50 SMA reduced to a "risk/chop estimator" and 200 SMA reduced to its slope direction.

- **`AnchVWAP` from pre-place** (was already static-only-rule in V2_1+, but is worth noting).
  - V2_1 already pre-place excluded VWAP/AnchVWAP (the comment on `AMTradeCockpitV2_1.cs:1634-1635` says "Static levels only — dynamic ones (VWAP, AnchVWAP, SMAs, rolling 30m) cannot be pre-placed as limits"). What changed in V2_4 is *aligning the signal path with the pre-place path* — the comment at `AMTradeCockpitV2_4.cs:1878-1881` explicitly notes "Pre-place was already correct (static-levels-only per the comment in V21UpdatePrePlace); this removes the parallel bug in the signal path."

---

## Added-but-unwired (V2_4)

- **`LevelWatchState` / `LevelWatchStatus`** (`AMTradeCockpitV2_4.cs:177-200`).
  - Status: 5-state enum `{Untouched, Breached, Armed, Consumed, Invalidated}`. Class has `LevelName`, `LevelPrice`, `Direction`, `Status`, breach-bar capture (`BreachBarHigh/Low/Time/Index`), confirmation tracking (`HoldHigherLow`, `ArmedAtTime`, `ArmedAtBarIndex`), and `AnchorCandle` for stop calc.
  - Wiring: zero. Grep confirms `LevelWatchState` is referenced only at the class declaration. No `new LevelWatchState()`, no field of type `LevelWatchState` in the indicator class. The in-file comment is unambiguous — "Class scaffolding placed here in this batch so the storage and refactor surface are agreed-upon before the entry-mechanism rewrite."
  - Implication: V2_4 is *one batch short* of a Pattern-B retest model. The current `CheckEntry` is still the V2-era closest-level-to-bar-open scorer, gated by `wouldRetrace`. There is no breach-then-retest sequencing today.

- **`MOCValidation` size adjustment.**
  - Computed and displayed: `:1232-1241` and `:3431-3527`.
  - **Not used to gate, size, or modify trades.** `effSignalCap` is computed without MOC (`:1626`). `MaxSignalsPerDay` is the only signal cap input. Stop and target math (`V2ComputeStopDistance`, `:2174`) does not consult `MocState`. The verdict UI says "REDUCED size" but the actual ATM template / sizing path is not bound to MOC.
  - Implication: V2_4 advertises MOC-aware sizing in its UI but the runtime is MOC-blind.

- **Cautious-Long / Cautious-Short.**
  - Classification exists (`:4410-4411, 4424-4425`).
  - Treatment: routes through TREND pipeline same as full Long/Short trend (`:1581, 1585-1586`). Comment at `:1590-1593` says sizing/stop-widening for cautious-mode "will be wired in a subsequent change once the Q13 walk-through with AM is done." So they trade today, but the cautious-ness is a label only.

- **Shadow-observer events** (`OnTouch`, `OnSignal` `:295-296`).
  - These ARE wired (`:1926-1942` for touches, `:2412-2430` for signals). Listed here because they're V2_4-new and worth being aware of for the institutional-grade autonomous stack — a hosting Strategy can subscribe.

- **`signalTradeMode` storage** (`:370`). Wired in V2_4 only. Persists the trade-mode through the pending → active → exit lifecycle so MonitorSignal can route to FADE-target vs TREND-trail correctly (`:2623, 2642`).

---

## Bug-fix patterns (what comments tell us)

These are the explicit "fix" comments in V2_4 / V2_3 / V2_2 / V2_1. Each tells us what *was* wrong; the implication is a question of whether other versions still ship the bug.

| Comment site | Fix label | What was broken | Implication |
|---|---|---|---|
| `AMTradeCockpitV2_4.cs:1843-1847` | "V2_4 fix" (also as "V2_3 fix" in V2_3:1595-1599) | Used `priorDay.Close330` which was *two institutional candles stale*. Source of chronic PrInst under-detection in V2_1/V2_2. | V2/V2_1/V2_2 were silently skipping most PrInst retests for ~3 versions. |
| `AMTradeCockpitV2_4.cs:1158-1167` | "Bug found by code-review 2026-04-24" | `sma200_30min` was carrying the prior bar's value at the 9:30 capture site — slope baseline was 30 min stale. Fix refreshes from `sma200Ind30[0]` directly at the capture point. | New in V2_4. Indicates SMA200 slope direction (used by V2_4 FADE-mode direction selection) was off-by-one bar before the fix. |
| `AMTradeCockpitV2_4.cs:1438-1444` | "V2.2 fix" | Prior formula `(rthOpenHour + 1) * 60` for OR-lock cutoff was wrong. Fix uses `closeHour * 60 + closeMinute - 30` (the cancel cutoff). | V2 / V2_1 had the wrong OR-lock time. |
| `AMTradeCockpitV2_4.cs:2521-2523` | (no version label, V2_4-only) | "Was using closeHour/closeMinute (15:00 ET) which let pending limits fill up to the flat time, violating the cancel-30-min-before-close discipline." Pending now expires at 14:30 cutoff. | V2 / V2_1 / V2_2 / V2_3 let pending limits ride to 15:00 = could fill 14:35 then immediately TimeClose. |
| `AMTradeCockpitV2_4.cs:2562-2576` | "Defense-in-depth" (V2_4-only) | Even with the cutoff above, a fill could slip through if `barTime <= signalTime`. Same-bar fill on the bar that just created the Pending was possible. Fix: `if (barTime <= signalTime) return;` at line 2542. | V2 / V2_1 / V2_2 / V2_3: same-bar fills (Pending created at bar X close, fill checked at bar X close) were possible. |
| `AMTradeCockpitV2_1.cs:1309-1310` | "V2.1 fix" | `canTrade` used `rth1MinComplete` (flips at 9:31) instead of `v2OpenRangeLocked` (10:00). Trades fired 29 minutes early. | V2 was firing pre-10:00 trades on whatever levels happened to be in-range; V2_1 over-corrected with the gate; V2_2 settled on no gate but per-level (only ORH/ORL gated to OR-lock). |
| `AMTradeCockpitV2_4.cs:1872-1881` | (V2_4-only) | "Pre-place was already correct (static-levels-only); this removes the parallel bug in the signal path." | V2 through V2_3 *did* fire VWAP/AnchVWAP signals while pre-place correctly excluded them — pre-place ↔ signal divergence for ~4 versions. |
| `AMTradeCockpitV2_4.cs:1167` | "Bug found by code-review 2026-04-24" | Same SMA200 staleness bug noted above — the comment explicitly attributes the find to a code review. | Implies AMTradeCockpitV2 family had a track record of staleness bugs, two of which (PrInst, SMA200) silently suppressed signals. |

**Stale-data pattern (worth flagging for further audit).** Three of the documented fixes are the same shape — a `_30min` cached field carries the prior bar's value at a moment-of-capture call site, and the consumer reads it before the per-bar refresh runs. The `sma20_30min` consumed by `MonitorSignal` (`:2646`) shares this pattern: it's set to `sma20Ind30[0]` in `Process30MinBar` (`:1271`), but `MonitorSignal` runs on every 1-min bar. Whether SMA20 trail uses the *intended* SMA20 reading (the one as of the last completed 30-min bar close) or a slightly stale intra-period value is not currently asserted by a comment. Suggest spot-check.

---

## Trend-gate evolution (V1 → V2_4)

| Version | Gate | Code |
|---|---|---|
| V1 / Dev | `smaDirection1` (1-min SMA-stack: price > SMA50 > SMA200) AND `currentBias` (price vs institutional) | `AMTradeCockpit.cs:1139-1151` |
| V2 / V2_1 / V2_2 / V2_3 | `trendLong/trendShort` (30-min SMA-stack: close30 > SMA50_30 > SMA200_30) | `AMTradeCockpitV2_3.cs:1370-1376` |
| V2_4 | `AMDayType` body-stack of four master candles (prior 3:30, 6 PM Globex, 4 AM Europe, 9:30 RTH) → `LongTrend / ShortTrend / CautiousLong / CautiousShort / Sideways / Unknown` | `AMTradeCockpitV2_4.cs:4388-4427` |

**V2_3 (SMA-stack) vs V2_4 (body-stack) — disagreement cases.**

You requested specific cases where they'd disagree without backtest data. Case classification:

1. **V2_3 fires LONG, V2_4 says Sideways/no-fire (or FADE).** Price is above SMA50 above SMA200 (a textbook bullish stack), but the 6 PM Globex body and 4 AM Europe body and 3:30 PM prior-inst body do NOT stair-step cleanly. This is common when overnight markets are choppy but the cumulative drift is up — V2_3 took these; V2_4 either skips entirely (Sideways + flat 200-SMA slope = `null` mode, `:1583`) or routes to FADE-only with a structural-extreme entry instead of a continuation entry.

2. **V2_3 says no-fire (SMA stack not aligned), V2_4 fires CautiousLong/CautiousShort.** Body-stack of the first three candles aligns up, but the 9:30 RTH candle breaks against (not down). V2_3 declines; V2_4 fires LONG with the same TREND pipeline. This is genuinely new territory in V2_4 — Cautious days are V2_4-additive trade volume.

3. **V2_3 fires LONG, V2_4 fires LONG (same direction) but FADE-mode** when the day classifies as Sideways with up-sloped 200-SMA. Different exit (target vs trail), different stop math (same `V2ComputeStopDistance`), different cap (FADE caps at 2 vs TREND at 3). Net: V2_4 gets fewer signals on these days but each has a structural target.

4. **Pre-9:30 / data-cold-start period.** V2_3 fires the moment SMA50/SMA200/close30 are valid (which can be quite early in a chart load). V2_4 returns `Unknown` until all four master candles are captured (`:4395`), which can defer the first eligible signal to 9:30+. Net: V2_4 quieter at session start.

The two gates are **not nested** — neither implies the other — so each can fire trades the other declines.

**Diagnostic SMA stack still running.** `smaDirection30` and `smaDirection1` are still computed in V2_4 (`:953-957` and the 30-min equivalent), used in legend rendering and A1 alerts. They no longer gate. If a caller (e.g. AMShadowObserverV1) wants to compare what the SMA-gate would have done, the data is there — but as a diagnostic, not a trade trigger.

---

## Exit logic evolution

| Version | Exit rules |
|---|---|
| V1 / Dev | Stop (intrabar). Target (waterfall: VWAP → inst-edge → pivot → measured move → 1-min range fallback). "SMA flipped + price inside range" invalidation → close at bar close, marked Invalidated. No time-close hard exit on the indicator side (relies on broker discipline). |
| V2 | Stop (intrabar). 30-min SMA20 trail, ratchet-only, exit on 1-min close past trail. Hard time-close at 15:00 ET (14:30 CL). No fixed target. No invalidation rule. |
| V2_1 / V2_2 / V2_3 | Same as V2. Plus 30-min stop-update alert at each 30-min close (`AMTradeCockpitV2_1.cs:1079-...`). Plus 14:30 cancel cutoff for *pending* limits (`AMTradeCockpitV2_3.cs:2197-2200`). |
| V2_4 | TREND mode → same as V2_3 trail. FADE mode → fixed structural target = PrInst H (longs) / PrInst L (shorts), intrabar exit on touch. No trail in FADE. Both modes still hit Time-close at 15:00. |

**Has SMA20 trail been the exit since V2?** Yes. V1 was target-based; V2 introduced the trail and dropped fixed targets entirely. V2_4 is the first version to bring back a fixed target, and only for FADE.

**Was there ever a level-to-level exit (matching AM's stated doctrine)?** No. The closest V1 came was the target waterfall picking VWAP → inst-edge → pivot → measured-move → range, but that was *fixed at SetSignal*, not "exit at next level encountered." V2's SMA20 trail is the closest thing to a level-following exit, but SMA20 isn't a structural level — it's a moving average. AM's doctrine of "exit at the next level on the chart" is **not implemented** in any version.

---

## Filter evolution

| Filter | V1 | Dev | V2 | V2_1 | V2_2 | V2_3 | V2_4 |
|---|---|---|---|---|---|---|---|
| `MaxSignalsPerDay` | exists, banner-only | exists, banner-only | enforced in canTrade | enforced | enforced | enforced | enforced (FADE caps at 2) |
| `CooldownMinutes` | exists, not enforced | exists, not enforced | enforced | enforced | enforced | enforced | enforced |
| `MaxDailyLossDollars` lockout | enforced | enforced | enforced | enforced | enforced | enforced | enforced |
| `MaxDailyLosingTrades` lockout | enforced | enforced | enforced | enforced | enforced | enforced | enforced |
| Pre-OR (10:00) entry gate | n/a (1-min logic) | n/a | none beyond `rth1MinComplete` | hard `!v2OpenRangeLocked` block | per-level (only ORH/ORL gated) | per-level | per-level |
| Pre-RTH session block | not applicable | not applicable | implicit via `inRthWindow` | yes | yes | yes | yes |
| Last-30-min entry block | none | none | yes (`inRthWindow`) | yes | yes | yes | yes |
| 14:30 pending-cancel cutoff | n/a | n/a | n/a (used 15:00) | n/a | n/a | n/a | yes (V2_4-new) |
| Same-bar fill block | no | no | no | no | no | no | yes (V2_4-new) |
| `State == State.Realtime` block on entries | n/a | n/a | implicit (no event log) | yes | yes | no (Historical fires touch+signal) | no |
| Per-level first-touch latch | no | no | yes (`v2TouchedThisSession`) | yes | yes | yes | yes |
| Retrace-side filter | not needed (1-min logic) | not needed | **no** (continuation trades possible) | yes | yes | yes | yes |
| Body-stack classifier (`AMDayType`) | no | no | no | no | no | no | yes (gates entry) |
| MOC-Validation gating | no | no | no | no | no | no | computed but **not gating** |

**Net trend.** Filter set has grown monotonically since V2. The two largest behavior-narrowing additions are:
1. V2_1 added the retrace-side filter — eliminates continuation trades.
2. V2_4 added the AMDayType gate AND the 14:30 pending cancel cutoff AND the same-bar fill block. Each independently reduces signal count vs V2_3.

The progression is one of *increasing strictness* — V2_3 → V2_4 is the strictest version yet on entries, and the strictest on pending lifecycle. If Afshin's intuition is that V2_4 declines trades that earlier versions took, the audit confirms the direction of travel: each version since V2 has added gates faster than it has loosened them. The *only* loosening was V2_2 dropping the V2_1 hard pre-10:00 gate.

---

## Lost setups (the "missing setups" question)

Three concrete categories of trades that V1 / V2 took and V2_4 will not:

### 1. The failed-retest of the 1-min RTH range (V1-only).

V1's signature setup. After the first 1-min bar prints (9:30:00→9:31:00 ET), if a subsequent bar pushes through `rth1MinLow` then a follow-up bar wicks back into the range and closes outside again, V1 fires SHORT at `rth1MinLow`. This is a confirmed-rejection setup.

V2_4 has no equivalent. The closest analog is "ORL added as a candidate level after 10:00 lock, and price retraces back up through ORL from below" — but that's a 30-min OR-Low level, not the 1-min open candle. The 1-min candle is a much faster trigger and on choppy-open days it produced setups in V1 that V2_4 simply cannot fire.

If Afshin is seeing "valid trade setups have been missed" on chop days where price tagged the open-1-min boundary and rejected, **this is the most likely loss**.

### 2. VWAP and AnchVWAP retests (V2 / V2_1 / V2_2 / V2_3).

V2 through V2_3 fired signals on `currentVWAP` and `v2AVWAP` touches. V2_4 explicitly removed these (`:1872-1881`) per AM's "VWAP is permission, not a destination" rule.

If AM's rule is right, this is correctly removed. If it's wrong on certain days (e.g. a clean inst-anchored AVWAP on a low-noise day), V2_4 will skip what V2_3 took. The empirical question (does AnchVWAP retest profit in our data?) is unanswerable from code review.

### 3. Continuation trades (V2-only).

V2 with no retrace-side filter fired LONGs on bullish breakouts above ORH and SHORTs on bearish breakouts below ORL. V2_1+ block these.

This is *probably* a good removal — Baiynd's playbook is mean-reversion, not breakout. But if Afshin is comparing his manual trades to V2_4 and his manual book includes continuation entries, V2_4 will not match. The retrace-side filter is structural — there is no parameter to disable it.

### 4. Pre-10:00 retests of pre-existing structural levels (V2-only and V2_2+).

V2_1 (with `!v2OpenRangeLocked` gate) blocked these. V2_2 onwards allow them. So if comparing V2_4 to V2_1, V2_4 is *more* permissive in this dimension. Unlikely to be the source of "missing" trades unless Afshin is comparing against V2_1.

### 5. Pattern-B retest sequence (everywhere — never implemented).

The `LevelWatchState` scaffold suggests a planned sequence: level breached on bar X, "armed" by a hold-higher-low on bar X+1 (longs) or hold-lower-high (shorts), then triggered by reclaim into the level on bar X+2. None of V1 → V2_4 implements this. If AM's stated method matches Pattern-B, every version of the indicator misses these setups.

### 6. Trades after the 3rd / 2nd cap (TREND / FADE).

Soft cap. V2_4 stops at 3 signals on TREND days, 2 on FADE. V1 had the cap but didn't enforce. If the day produces 4+ legitimate retests and the first two are stop-outs, the indicator is silent for the rest of the session. Cooldown after a stop further suppresses.

### 7. PrInst retests during the V2/V2_1/V2_2 era.

The stale `priorDay.Close330` bug suppressed PrInst retests for three versions. V2_3 and V2_4 fix this — meaning V2_4 now *gets* trades that V2/V2_1/V2_2 missed. If the user's intuition is "I used to see this signal," consider whether V2_4 is now correctly firing or whether the comparison is to a buggy V2_1 baseline.

---

## Cross-reference notes (suggested for other audit waves)

- **Pattern-B implementation gap.** Wave-3 (or whatever audit covers the strategy spec) should compare `AM_rules_v2_spec.md` to `AMTradeCockpitV2_4.cs:177-200` and decide whether `LevelWatchState` is a TODO or an abandoned design. Either close it out or wire it.
- **MOC sizing gap.** The MOC verdict UI promises "REDUCED size" but no sizing path consults `MocState`. If reduced sizing is expected, audit the ATM-template selection (`v21AtmTemplate`, `AMTradeCockpitV2_3.cs:2141-2142`) — is there a half-size template that should be selected when MOC is Orange/Gray? If not, this is a feature gap, not just a wiring gap.
- **SMA20 trail freshness.** Same staleness pattern as the documented PrInst and SMA200 fixes. Consumer `MonitorSignal:2646` reads `sma20_30min` cached field; producer `Process30MinBar:1271` updates it. Worth a code review specifically asking "does the trail use the intended bar's SMA20?"
- **`signalsToday < effSignalCap` interaction with stop-outs.** Per `AMTradeCockpitV2_4.cs:1455`, `signalsToday++` happens at SetSignal (Pending), not at fill. A Pending that expires at 14:30 cutoff has incremented the counter. So a stopped-out trade and an expired-Pending both count toward the cap equally. If AM's intent is "you get N attempts that *trade*," the counter is over-counting expired Pendings.
- **Cooldown counts from `lastStopTime`.** Not from `lastFlatTime` or `lastSignalTime`. So a Trail exit (TREND win) does not reset cooldown — only stops do (`AMTradeCockpitV2_4.cs:2609`). After a winning TREND exit there is *no* cooldown wait. After a stopout, there is. This may be intended, but worth flagging.
- **Mod-set diff for an autonomous-stack rebuild.** The institutional-grade autonomous stack should re-derive the entry rule from `AM_rules_v2_spec.md` rather than translating V2_4's entry path verbatim — the path through V1 → V2 → V2_4 has accumulated patches without removing pre-existing assumptions (e.g., the level-touch scorer with first-touch latch is itself a V2-era invention not justified by AM's doctrine; LevelWatchState is the planned alternative).
- **Beginner-friendly indicator.** The audit suggests a beginner-friendly fork should pick *one* setup type (probably either V1 failed-retest, *or* V2_4 level-touch retracement, not both). Mixing modes (TREND vs FADE) is already V2_4's complexity tax and the cautious-mode and MOC scaffolds add more without delivering size differentiation.

---

## Quick file-level reference

```
AMTradeCockpit.cs        2517 lines  V1.0  — failed-retest of 1-min RTH range, target waterfall
AMTradeCockpitDev.cs     2690 lines  V1.2  — V1 + JSONL event logger
AMTradeCockpitV2.cs      2963 lines  V2.0  — level-touch scorer, SMA20 trail, no retrace filter, stale priorDay PrInst
AMTradeCockpitV2_1.cs    3705 lines  V2.1  — adds retrace-side filter, pre-10 gate, Pre-Place panel
AMTradeCockpitV2_2.cs    3781 lines  V2.2  — drops pre-10 gate, fixes OR-lock cutoff formula, still uses priorDay PrInst
AMTradeCockpitV2_3.cs    3942 lines  V2.3  — fixes PrInst (currentDay.Close330), adds shadow-observer events, drops State.Realtime block, OnTouch/OnSignal
AMTradeCockpitV2_4.cs    4627 lines  V2.4  — body-stack AMDayType gate, FADE mode, SMA200 capture fix, 14:30 pending cancel, same-bar fill block, removes VWAP/AnchVWAP from candidates, MOC scaffold, LevelWatchState scaffold (unwired)
```
