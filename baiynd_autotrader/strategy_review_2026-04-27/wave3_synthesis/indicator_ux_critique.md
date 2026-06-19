# Indicator UX Critique — AMTradeCockpitV2_4
## Beginner-First Lens for Afshin's Daily Trade Workflow

**Author:** Wave 3 / Indicator UX Critique Agent  
**Date:** 2026-04-27  
**Source files:** `AMTradeCockpitV2_4.cs` (4627 lines), `wave2_audit/v24_code_audit.md`, `wave2_audit/jsonl_data_analysis.md`

---

## 1. Info Card / Diagnostic Panel (RenderComingUpTimeline, ~line 3302)

### 1.1 The Verdict Line — Most Important Item on the Chart

The verdict line is designed to be the single-sentence answer to "should I trade today and in which direction?" In its current form, it fails a beginner in three ways.

**Current possible outputs:**

- `Verdict: WAIT — day-type pending`
- `Verdict: NO FIRE — Sideways + slope flat`
- `Verdict: pending MOC — Sideways FADE LONG`
- `Verdict: FADE LONG — Sideways + slope UP, target PrInstH`
- `Verdict: REDUCED FADE LONG — Sideways + MOC ORANGE`
- `Verdict: FULL size — Long Trend`
- `Verdict: REDUCED size — Long Trend + MOC ORANGE`
- `Verdict: pending MOC — Long Trend`

**Problem 1: The language describes reasons, not decisions.**  
A beginner's brain needs an imperative sentence, not a description. "FADE LONG — Sideways + slope UP, target PrInstH" still leaves three open questions: Where do I put the limit order? How much size? When is it too late to place it?

**Problem 2: REDUCED vs FULL communicates size but not whether to trade.**  
"REDUCED FADE LONG" and "FADE LONG" both mean "take the trade." But the word "REDUCED" carries ambiguity — a nervous beginner can read it as "only sort of tradeable" and hesitate.

**Problem 3: "NO FIRE" does not appear in most Sideways sessions.**  
From the code (lines 3486-3511), "NO FIRE" only shows when slope is flat AND day-type is Sideways. When slope is UP and MOC is Orange, the output is "REDUCED FADE LONG" — but there is no explicit signal that a trade IS expected. The green/amber coloring helps, but the word "REDUCED" undermines confidence in taking the trade.

**Recommended redesign.** The verdict should use a three-state imperative format: GO / WAIT / STOP, followed by a single line of context:

```
[GO]    LONG fade — enter limit at Europe or PrInst retrace
         Size: FULL (2 MES, ATM "NormalES")
         Stop: 3.75pt = $187/trade | Target: PrInstH 7199.00

[GO]    LONG fade — enter limit at retrace (MOC below ideal)
         Size: REDUCED (1 MES, ATM "WideES")
         Stop: 3.75pt = $187 | Target: PrInstH 7199.00

[WAIT]  Slope flat — no fade direction available yet
         Check back after 9:30 RTH open

[STOP]  Daily loss limit hit — no new trades today
```

The key improvements:
- GO/WAIT/STOP is an action verb at the start, visible before reading the rest.
- Size, stop, and target are on the same verdict — the beginner does not need to look elsewhere.
- The target level is named AND priced, removing any ambiguity about where to exit.
- WAIT explains why and gives a next step.
- STOP is used for lockout, distinguishing it from WAIT.

### 1.2 The A/B/C/D Body-Stack Section

The four rows showing candle body price ranges (lines 3541-3617) are the evidence behind the day-type classification. A beginner sees them and asks: "What do I do with these four numbers?"

The answer is: almost nothing in real-time. The body stack is the indicator's reasoning process made visible — useful for a student learning AM's method, but not useful as a daily trade aid. Its presence invites the beginner to second-guess the classification: "B is above A, C overlaps B, D is above C... so is that trend or sideways? The panel says FADE but I'm not sure."

**The core issue:** Afshin is reading the diagnostic reasoning and re-performing the classification himself. The panel should hide this section by default for beginners and reveal it optionally (behind a Detail Level toggle). For now, at minimum, each row should include a one-word relationship label:

```
A 3:30 : 7188.50 — 7194.25  [anchor]
B 6 PM : 7195.00 — 7200.50  [ABOVE A — bullish]
C 4 AM : 7199.75 — 7205.00  [ABOVE B — bullish]
D 9:30 : 7198.00 — 7203.25  [overlaps C — FINAL]
  -> Classification: LONG TREND
```

Without that one-word annotation, the four price ranges are uninterpretable to anyone who has not memorized AM's candle-stack rules.

**What should be pruned:** In a future iteration, the full A/B/C/D block should move to a Detail Level == Full gate. In Signal mode, only the verdict line and the stop/target values need to be visible.

### 1.3 Two Parallel Day-Type Displays

The panel currently shows (lines 3410-3641):

1. **V2.4 body-stack day type** ("Day type: Long Trend [FINAL]") in the V2.4 STATE section
2. **Legacy 30m SMA stack** ("30m SMA stack (legacy): LONG" in green) further down

The code audit (v24_code_audit.md §7) calls this out directly: "Two day-types on screen at once. These two can disagree — and the SMA-stack labels are colored green/amber which makes them look authoritative."

From Afshin's perspective, the first day-type says "Long Trend" while the SMA stack may say "WAIT" on a morning when the 30-min SMA stack hasn't aligned yet. He has no way to know which one to believe.

**What is actually true:** Only the V2.4 body-stack matters for entry decisions (`v2DayType` in `ClassifyAMDayType()`). The SMA stack (`sma50_30min`, `sma200_30min` comparison at lines 3324-3326) feeds the legacy gate that was removed in V2.4. It does not gate anything.

**Recommended fix:** Rename the section header to "30m SMA diagnostic (informational only)" and reduce it to a single line. Or move it entirely to Detail Level == Full. As it stands today, a beginner who sees "30m SMA stack: WAIT" in gray-amber will hesitate even when the V2.4 verdict says GO.

### 1.4 The Stop Preview Line

Current text (line 3673): `Stop preview: 3.75pt = $187/c`

Three problems for a beginner:

1. The label `/c` (per contract) is easily missed at small font size. The critical question Afshin needs answered is "how much money am I risking on THIS trade?" — which is the per-trade dollar amount, not the per-contract amount.
2. The stop preview uses the Europe 4AM box width regardless of which candle will trigger the trade. A beginner who looks at the current bar and thinks "this entry candle is huge — my stop should be bigger than $187" is correct by AM's rule but the panel will not change.
3. There is no dollar display for the scenario where the beginner accidentally uses full size versus reduced size.

**Recommended replacement:**
```
Stop preview: 3.75pt
  FULL size (2 MES): $375/trade  [Green bucket today]
  REDUCED (1 MES):   $187/trade
  Note: stop = Europe 4AM width, clipped to ADR range
```

This tells Afshin exactly how much real money per trade at each size. It removes the `/c` ambiguity. And the "Note" line explains why the stop may feel different from the candle-width rule AM teaches.

### 1.5 Prior Institutional Level

Current text (line 3681): `Prior inst 3:30: 7189.75 — 7199.00`

This is useful but the label is terse. A beginner reads "Prior inst 3:30" and may not know this refers to yesterday's 3:30 PM candle high and low — which in FADE mode is the target the indicator is pointing at.

**Recommended:** `FADE TARGET range: 7189.75 — 7199.00  (yesterday 3:30 PM candle)`

This makes the connection explicit: in a FADE LONG day, the target is the high of that range. In a FADE SHORT day, it is the low. That connection is currently only visible in the full verdict line and in the staging card, not in the data row itself.

### 1.6 What Should Be Removed or Demoted

**Can be removed from the default view:**
- The full SMA50/SMA200 numeric rows (`close30: 7203.00`, `SMA50_30: 7198.00`, `SMA200_30: 7191.00`) at lines 3632-3641. These are debugging numbers. The direction summary "30m SMA stack: LONG" captures the meaning for a trader.
- The 200 SMA slope delta in parentheses (line 3456): `(+0.42)` — the directional word UP/DOWN is sufficient; the delta number means nothing to a beginner without context.
- The MOC ratio number: `MOC: GREEN ratio 1.24` — the GREEN/ORANGE/GRAY label is actionable; the 1.24 is diagnostic.

**Must stay:**
- Verdict (ideally in the redesigned GO/WAIT/STOP format).
- MOC state in color.
- Stop preview in per-trade dollars.
- Prior inst range labeled as the FADE target.
- Day type with PRELIM/FINAL tag.

**Missing that should be added:**
- "Next setup window opens at: 10:00 AM" — the time when OR locks and Pre-Place goes live. Currently this is in the Coming-Up timeline section above, but it disappears once the PrePlace panel replaces the Coming-Up panel. A single line on the info card that says "Limits valid: 10:00 AM — 2:30 PM" would eliminate timing confusion.
- "Signals used today: 0 of 3" — currently there is no on-chart counter. A beginner has no way to know how many more setups the indicator will accept today before it silently caps.
- "VWAP and AnchVWAP are NOT entry levels" — a one-line note somewhere on the panel, because these lines dominate the chart visually and the natural assumption is that they are entry candidates (which they are not; see §7 of the code audit and the level-table analysis in the JSONL audit).

---

## 2. Box Rendering

### 2.1 Color Scheme Legibility

The six box colors on a dark NT8 theme:
- GlobEx 6PM — cyan (user-configurable, default teal-adjacent)
- Europe 4AM — orange
- RTH 9:30 — magenta
- Close 3:30 — hot pink
- Midnight — gray
- Institutional — gold overlay

On a pure black background these are generally distinguishable. The main risk is cyan vs magenta on dark — these two are frequently on opposite sides of the current price and can merge into a similar brightness. On a deuteranopia (red-green colorblind) display the hot pink and magenta can look very similar.

**The legend chips** (RenderChartLegend, line 4043) help significantly since they label each color by name. This is the right design pattern. The gap is that the legend chips are all the same font size and all horizontal in a row — a beginner cannot quickly scan which box color corresponds to which session marker without reading left to right. A small improvement would be to put the most important boxes (INSTITUTIONAL, 3:30 CLOSE) first in the chip row rather than the current order, and to make INSTITUTIONAL slightly larger since it is the primary structural reference.

### 2.2 Box Aging and the Weekend Fix

The code now uses trading-day counting (`AddTradingDays` at line 4138) rather than calendar-day counting to determine when a box transitions from active to fade to dead. The weekend skip logic (fixed per the code comment) means Friday's Close 3:30 will be visible and properly colored on Monday morning, which is when AM's method needs it most.

**One remaining confusion:** During the fade phase, the box rectangle disappears and only the dashed H/L lines remain. A beginner who saw a solid box on Friday morning and then sees only dotted lines on Monday morning may think the indicator has lost data. There is no on-chart explanation of what a dashed line means versus a solid box. Recommended: add a small label at the right edge of the dashed line reading "faded" or include a one-line explanation in the legend.

### 2.3 Detail Level: Signal vs Full

At Signal detail level, some box decorations are suppressed. The code comment at line 4043 references a "three-layer visual design" that is partially built. A beginner who has never seen the Full detail level will not know what they are missing. Recommended: when Detail Level == Signal, add a faint one-line message somewhere (perhaps the COMING-UP panel footer): "Chart simplified — switch to Full detail to see all reference levels."

---

## 3. Pre-Place Panel (RenderPrePlaceLevels, ~line 3227)

### 3.1 Header: "PRE-PLACE — LONG"

This is reasonably clear. Once the trader knows what "Pre-Place" means, the direction at the top is useful. The problem is that "PRE-PLACE" is insider jargon. A new user reading the panel for the first time does not know what pre-placing means. Recommended rename: **"LIMIT CANDIDATES — LONG"** or "PENDING LIMITS — LONG". This maps directly to what the panel shows (price levels to watch for limit orders) without requiring prior vocabulary.

### 3.2 The Level Table Itself

The sorted price level table is useful and well-organized. The TOUCHED tag correctly marks levels that have already fired this session. There are two improvements:

**First,** a TOUCHED level should visually indicate why it is greyed out. Current display:
```
PrInstH     7199.00  [TOUCHED]
```
A beginner may wonder: "Is this TOUCHED because the indicator fired, or because price crossed through it manually?" There is no distinction. The label should say:
```
PrInstH     7199.00  [USED - signal fired 10:17]
```
or simply indicate the direction: `[LONG signal @ 10:17]`.

**Second,** the levels currently have no priority rank. The AM method treats levels differently depending on the day type — in FADE mode there are only 3 candidates (GlobEx, Europe, PrInst); in TREND mode there are up to 16. The panel shows all current candidates in price order but does not distinguish primary from secondary levels. A beginner looking at a TREND day with 8 levels visible does not know that SMA50_30 and Pr30H are higher priority than MidMid. Recommended: add a simple indicator — perhaps a filled circle for primary candidates and an open circle for secondary — or group them under sub-headers "Primary (structural)" and "Secondary (dynamic)".

### 3.3 Pre-OR Lock vs Post-Lock

The panel is blank before 10:00 AM because the `v21PrePlaceBuilt` flag is false until OR locks. This is correct behavior — the OR levels are not yet available. However, the transition from the Coming-Up timeline to the Pre-Place panel is abrupt. One moment there is a diagnostics panel; the next moment it switches to a candidate table with no explanation of what changed.

Recommended: when the Pre-Place panel first becomes active, insert a one-time header row: "OR locked at 10:00 — limits now available" for one minute, then suppress it. This eliminates the "why did the panel change?" question.

### 3.4 Stop/Risk Display in the Pre-Place Header

Current display (line 3267-3275):
```
Stop 3.75pt = $187/contract
Size 2  [Green]  ATM: NormalES
Risk/trade $375   Book $750
```

This is actually well-structured. The per-trade and per-book dollar amounts are both visible. The main weakness is "Book $750" — a beginner does not know what "Book" means in this context. It appears to mean total risk if both allowed signals fire (2 trades × $375). This should be labeled explicitly: `Session max risk $750 (if both signals fill)`.

---

## 4. Staging Card (RenderStagingCard, ~line 3855)

### 4.1 The 60-Second Workflow Is Too Short for a Beginner

The staging card appears at signal time. The code shows it at `SetSignal` (line 2500) which fires on the 1-minute bar that prints through the entry level. Depending on what else the beginner is doing on the chart (checking the level, confirming the direction, looking at a second screen), 60 seconds to find the ChartTrader, place the ATM order, and confirm is extremely tight.

There is no on-card timer visible. The beginner does not know the 60-second window exists until the card disappears. Recommended: display a countdown timer on the card — a simple running "0:58... 0:57..." in the title bar or as a progress bar under the buttons. Even if the beginner cannot act fast enough, seeing the countdown manages expectations and does not leave them wondering why the card vanished.

### 4.2 The "CONFIRM" Button Implies Order Submission

This is the most dangerous UX misunderstanding possible for a live-money trader. The button label "CONFIRM" implies that clicking it places the order. It does not. After clicking, the display changes to:

`TICKET LOGGED - submit ATM in ChartTrader NOW`

A first-time user may click CONFIRM, see "TICKET LOGGED," and assume the order is placed. They may wait for fill confirmation that never comes. The order was never submitted.

The V2_4 code audit (§7 of v24_code_audit.md) explicitly flags this: "A beginner could believe a CONFIRM click submits an ATM order."

The JSONL data audit found that in 6 months of data, only 2 signals fired. This means Afshin has clicked CONFIRM at most twice in the entire history. He may not have internalized the manual-step requirement.

**Recommended button label changes:**

Before clicking: `LOG + PLACE MANUALLY` instead of "CONFIRM"  
After clicking: `LOGGED — OPEN CHARTTRADER NOW (not auto-submitted)`

The explicit phrase "not auto-submitted" removes any ambiguity on first encounter.

### 4.3 Sizing Traffic Light — Green/Orange/Gray

The colored dot and the sizeLabel at lines 3897-3910 communicate the size decision. This is conceptually correct. The problem is the Gray bucket behavior: when the card shows a gray dot and says "NO TRADE (risk > $100)", the CONFIRM/LOCK button label changes to "LOCKED" but is still present and still looks like a button. A beginner may click LOCKED and expect something to happen. Recommended: when Gray, replace both buttons with a single full-width panel in red that says "DO NOT TRADE — risk too high today. SKIP this setup."

### 4.4 "STAGED" Persistent Banner

After CONFIRM is clicked, the card stays visible with gold borders and the "TICKET LOGGED" strip. This is correct design — it reminds the trader that there is an active pending signal. However, once the trader has manually placed the order in ChartTrader and the position is filled, the card is still showing "TICKET LOGGED." The trader now has an open position and a staging card reminding them to place an order they already placed. This creates confusion.

The card should automatically transition when the signal moves from Pending to Active (which the code already tracks via `MonitorSignal`). The Active transition should hide the card immediately (which the code does at line 2579 in the fill-check path). Verify that `HideStagingCard()` is called in that path — if it is, then the confusion may be reduced in practice. The main gap is when there is a long delay between the CONFIRM click and the fill: the staging card sits there looking like an unresolved task.

### 4.5 The TREND "Target: TRAIL" Display

Line 3890 shows: `Target  TRAIL (30m SMA20, ratchet only)` in green.

For a TREND signal, there is no fixed target price. The exit is managed by a 30-minute SMA20 ratchet. This is the most confusing scenario for a beginner because they cannot see where they are getting out. When they look at the chart, there is no Sig_Target line (lines 2476-2481 only draw it in FADE mode). The staging card says "TRAIL" but does not say at what price the trail currently sits.

Recommended: add a line to the TREND staging card: `Trail arm: when SMA20 crosses above entry. Currently: 7195.50` This requires feeding the current `sma20_30min` value into the card rendering, which is straightforward. Without it, the beginner has no idea what they are monitoring.

---

## 5. Signal Lines and Arrows

### 5.1 Entry / Stop / Target Line Overlap

On a long signal, the indicator draws:
- `Sig_Entry` — white solid line
- `Sig_Stop` — red dashed line
- `Sig_Target` — lime green dashed line (FADE only)

On a dark chart with multiple box rectangles also drawn, these three lines can be hard to distinguish at a glance, especially if the entry level happens to coincide with a box boundary (which is the entire point — the entry IS at the box level). The entry line blends into the box H/L line.

Recommended: make the entry line slightly thicker (width 3 instead of 2) and add a small arrow label on the right edge — currently the label says `>> ENTRY LONG on retracement @ GlobExH` (line 2474) which is helpful, but at signal detail level on a busy chart it can be obscured.

### 5.2 Arrow Persistence

The code uses `Draw.ArrowDown` and `Draw.ArrowUp` with `bool isAutoScale = true` and `int barsAgo = 0` (line 2487-2489). These arrows paint on the current bar at signal fire. They are removed and redrawn at each `SetSignal` via `RemoveDrawObject`. For historical signals, arrows are drawn by `DrawTradeOnChart` with a different tag (`Hist_N_entry`). There is no mechanism to "fade" historical arrows — they remain at full brightness indefinitely.

The practical effect: on a chart with 20 days of history, the beginner sees a field of historical arrows that look as urgent as the current signal's arrow. Recommended: historical arrows should use a different color (gray or dim teal) and a smaller size. This makes the current signal's arrow immediately stand out.

### 5.3 Demo Signal Mode

The demo signal fires one synthetic LONG in Realtime at RTH open (lines 1449-1467). It goes through the full `SetSignal` path, fires the A3 alert, and shows the staging card. The purpose is presumably to familiarize the beginner with the workflow on days when no real signal fires.

The problem: the demo signal looks identical to a real signal on the chart. The staging card title says `CONFIRM TO STAGE - LONG on retracement` — it does not say "DEMO." The arrow, entry line, and stop line are drawn exactly as they would be for a live setup.

A beginner who has the demo mode on and does not know it may attempt to place this order in ChartTrader and take a real position on a synthetic trigger. Recommended: when the demo path fires, prefix all labels with "[DEMO]" — on the staging card title, on the arrow label, and on the entry line label.

---

## 6. Lockout and Cooldown Banners

### 6.1 Lockout Banner

The lockout banner (line 4022-4033) fills the top of the chart in red with the text "LOCKOUT — Daily loss limit hit ($375 / $300)." This is visible and correct. The implementation is solid. One gap: the banner does not say "no new trades for the rest of today." A beginner who does not know what lockout means may interpret the red banner as an error state and try to reload the indicator to clear it.

Recommended text: `TRADING STOPPED TODAY — Loss limit reached ($375). No new signals until tomorrow.`

The word "STOPPED" is clearer than "LOCKOUT" for a beginner, and "until tomorrow" eliminates the question of whether it ever clears.

### 6.2 Cooldown Banner

The cooldown banner (lines 4096-4107) shows in amber: `COOLDOWN — 14 min remaining after last stop`. This is good. The countdown minutes are visible.

Two minor issues:
- The cooldown applies to the strategy's signal engine, not to the trader's ability to manually enter. A beginner may think they cannot take any trade during cooldown. Consider adding: "Indicator paused — manual trading is your choice."
- The banner is 24px high and uses `dxTitleFormat` (Arial Bold 11). On a high-DPI monitor this is readable but barely. Consider 14-16px font for the banner body text.

### 6.3 Visibility Competition at the Top of the Chart

The legend chips, lockout banner, cooldown banner, and the staging card can all compete for space at the top of the chart. The code nudges panel Y positions down by 30px when lockout is active and 26px when cooldown is active (lines 3238-3239, 3342-3343). But if all three are present simultaneously (cooldown is active AND the staging card fires), the layout has not been tested for full overlap. A beginner in this scenario may see panels overlapping the banners with text clipped.

---

## 7. Color and Contrast

### 7.1 Brush Definitions

The core brush palette (line 3757-3766):
- Background: pure black `(0, 0, 0, 255)`
- Text: ivory `(241, 236, 216, 255)` — good contrast
- Teal border: `(26, 163, 154, 255)` — visible on black
- Amber: `(232, 154, 31, 255)` — visible on black
- Red: `(200, 40, 40, 255)` — acceptable on black
- Green: `(0, 160, 80, 255)` — visible on black but may be low contrast for some monitors
- Slate: `(107, 114, 128, 255)` — moderate contrast on black; gray-on-dark is often hard to read

The slate/gray color is used for "neutral" or "not yet determined" states. On a dark background, `(107, 114, 128)` text on `(0, 0, 0)` has a contrast ratio of approximately 4.5:1 — just at the WCAG AA minimum. On a chart with any screen glare or warm lighting, this becomes marginal.

### 7.2 The Green / Amber Distinction

Green (GO, trend up, full size) and amber (REDUCED, caution) are the two operative signals for whether to trade and at what size. On a dark background these are clearly different hues. However, the `dxGreenBrush` at `(0, 160, 80, 255)` is a dark forest green that sits noticeably lower in luminance than the amber at `(232, 154, 31, 255)`. The amber reads visually brighter and more urgent than green. For a trade-direction indicator, brighter = more urgent = "be careful," but "FULL size LONG TREND" in dim green may feel less confident than "REDUCED size LONG TREND" in bright amber.

Recommended: increase green brightness to approximately `(40, 200, 100, 255)` to match amber's visual weight. A "full go" signal should feel as confident as a "reduced" signal, not dimmer.

### 7.3 Color-Blind Safety

The indicator uses red/green to distinguish stop from target (red stop line, green target/entry lines). For protanopia (red-blind) users, the stop line and the background box rectangles can merge. The Sig_Stop line at `Brushes.Red` and institutional box drawn in gold provide separation, but this has not been validated against colorblind simulation.

The primary action colors — green for full-go, amber for reduced, red for lockout/stop, slate for neutral — span all three major red-green colorblind variants. The amber/slate distinction (orange vs gray) is safe for most colorblind profiles. The green/red distinction on signal lines (entry vs stop) is the highest risk point.

---

## 8. Beginner Traps — Silent Contradictions

These are situations where the on-chart information is internally consistent by design but creates false beliefs for a beginner.

### 8.1 Verdict Says "NO FIRE" But Pre-Place Panel Still Shows Levels

When the day-type is Sideways with flat slope (verdict = "NO FIRE"), the Pre-Place panel still builds and shows candidate levels once OR locks. The code does not gate the Pre-Place panel on the verdict. A beginner sees "NO FIRE" in the diagnostic panel and simultaneously sees a list of prices in the Pre-Place panel that look like orders to place.

This is a real source of confusion. The Pre-Place panel represents what the indicator would watch if conditions changed — it's a forecast, not an instruction. But there is no explanation of this distinction. Recommended: when the verdict is NO FIRE or WAIT, add a banner across the Pre-Place panel: "INFORMATIONAL — No trades expected today. Do not place these limits."

### 8.2 VWAP and AnchVWAP Lines Drawn but Not Entry Candidates

VWAP and AnchVWAP are drawn as full-width horizontal lines on every chart bar. They are visually identical in prominence to levels like GlobExH, EuropeH, PrInstH — all of which ARE entry candidates. But VWAP and AnchVWAP are explicitly excluded from the candidate pool (code lines 1872-1880, per the comment "VWAP/AVWAP are permissions, not limit-order destinations").

The JSONL data audit shows VWAP is the most-touched level by volume — 433 out of 2,956 unique touches (14.65%). The two signals that actually fired in 6 months BOTH fired from VWAP (March 19, March 20 — both 09:32 VWAP SHORT). This means in the current code state, VWAP actually IS a trigger, but only because those two signals appear to have fired in a historical code state where VWAP was not yet excluded.

From a beginner's perspective, the chart shows VWAP as a prominent line, they watch price come to it, they expect a signal — and no signal fires. This is a recurring source of the "missed setup" feeling.

**Minimum fix:** Label the VWAP and AnchVWAP chart lines with a small suffix "(permission only)" so the trader knows these lines are context, not triggers. Or add a one-line footnote to the Pre-Place panel: "VWAP and AnchVWAP are not limit candidates — they confirm direction only."

### 8.3 "TREND" Trail Says "TRAIL (30m SMA20)" But There Is No Target Line

In a TREND signal, the staging card shows "Target TRAIL (30m SMA20, ratchet only)" in green. The green color suggests this is a positive outcome, which is correct — but there is no Sig_Target line on the chart. A beginner stares at the chart looking for a green target line and finds nothing.

AM teaches to exit at the next structural level (level-to-level), not via a moving-average trail. The indicator uses SMA20 ratchet instead. Neither the staging card nor any on-chart element explains that the trail is where the indicator will auto-exit, not the next visible level. A beginner may take a partial exit manually at the first resistance level, then wonder why the indicator shows them still in a trade.

**Recommended:** Add a sentence to the staging card in TREND mode: `Exit: automatic when 30m SMA20 ratchets below price (closes past trail).`

### 8.4 "signalsToday" Counter Is Hidden — Silent Budget Exhaustion

The indicator caps signals at 2 (FADE) or 3 (TREND) per day. There is no on-chart display of how many signals have been used. On a day where the first two FADE signals hit their targets and a third valid setup appears, the indicator silently does nothing. The Pre-Place panel still shows the level as an active candidate (it is not removed from the table). The beginner watches price touch the level, waits for the signal that never fires, and concludes the indicator is broken or that the setup was not valid.

**Recommended:** Add a line to the Pre-Place panel header or the verdict section: `Signals today: 2 of 2 used (FADE cap reached)` or `Signals today: 1 of 3 used`. This is a single-line change that eliminates an invisible gate.

### 8.5 "Pending counts against the signal cap" — Invisible Budget Drain

Per the code audit (§10), a pending signal that is later cancelled (because it hit the 14:30 cutoff without filling) still counts against the signal cap. This is documented in the code comments but is invisible on the chart. A beginner who had a pending FADE signal that was auto-cancelled at 14:00 may find themselves capped out for the rest of the day with 0 filled trades.

The fix is simple: add "(1 cancelled)" or "(1 pending)" to the signals-today counter described above.

### 8.6 Firewall Mode — "Indicator Stopped Working"

When a signal goes Active, `ActivateFirewall()` removes all non-Sig_* drawings. Box rectangles, level lines, intermediate structural references all disappear. The chart looks stripped. The code audit notes (§7): "Some users report this as 'indicator stopped working.'"

After exit, `DeactivateFirewall()` does not immediately redraw — it waits for the next 30-min bar. The chart can look bare for up to 30 minutes after a trade closes.

**Recommended:** When firewall activates, show a small banner or label: `FIREWALL ACTIVE — chart simplified for active trade`. When deactivating, display: `Trade closed — levels will redraw on next 30m bar`.

---

## 9. The "Coming-Up" Timeline Panel

This panel shows future session events with countdown timers. The design is good — it answers "what happens next?" clearly. Two improvements:

**One:** The event label `OR LOCKS — Pre-Place goes live` at line 3315 would be clearer as `OR LOCKS at 10:00 — limit levels become available`. The current label assumes the user knows what "Pre-Place" means.

**Two:** There is no event in the timeline for "MOC computed" (3:30 PM). The MOC state is one of the key verdict determinants. A beginner watching the panel through the afternoon does not know that at 3:30 PM the verdict will update from "pending MOC" to a definitive GO or REDUCED. Adding the 3:30 PM event to the timeline would help: `+4h15m  15:30  MOC computed — verdict finalizes for TOMORROW's session`.

---

## 10. Top 10 UX Changes That Would Most Reduce Beginner Doubt

The following are prioritized by impact on the core failure mode: Afshin sees valid setups but hesitates or misses them due to chart confusion.

**Priority 1 — Redesign the Verdict Line to Lead with GO/WAIT/STOP.**  
The single highest-leverage change. Replace "Verdict: FADE LONG — Sideways + slope UP, target PrInstH" with a three-line block: [GO] LONG fade / Size: FULL (2 MES) / Stop: 3.75pt = $375/trade. The action word GO must come first. No other change on this list matters if the verdict does not clearly tell the beginner what to do.

**Priority 2 — Rename the CONFIRM Button to "LOG + PLACE MANUALLY."**  
A beginner clicking CONFIRM and believing their order is placed may take no further action, miss the fill, and watch price move through the level with no position. This is the most dangerous single-word ambiguity on the chart. The post-click "TICKET LOGGED" text should also change to "LOGGED — Go to ChartTrader and submit ATM NOW (not auto-submitted)."

**Priority 3 — Add a Signal Budget Counter to the Pre-Place Panel.**  
"Signals today: 1 of 3 used" — one line, but it eliminates silent signal-cap confusion. Include cancelled pendings: "1 fired, 1 cancelled, 1 remaining."

**Priority 4 — Label VWAP/AnchVWAP as Permission Lines, Not Entry Triggers.**  
Add "(permission only)" to both line labels on the chart, and add a note in the Pre-Place panel footer. The JSONL data confirms VWAP is the most-touched level. The beginner expects it to fire every time price comes to it.

**Priority 5 — Add a Countdown Timer to the Staging Card.**  
60 seconds is very short. A visible 0:59… 0:58… countdown at the top of the card tells the beginner exactly how long they have and sets the urgency appropriately. Without it, the card disappearing feels like a surprise every time.

**Priority 6 — Move the Legacy SMA Stack to Detail Level == Full.**  
The green/amber LONG/SHORT/WAIT label from the 30m SMA stack looks authoritative and can directly contradict the V2.4 day-type verdict. Beginners who are learning the method will latch onto it as confirmation and become paralyzed when the two disagree. It does not gate any entry in V2.4. It should not be visible by default.

**Priority 7 — Add "DO NOT TRADE" Banner When Verdict is NO FIRE and Pre-Place Is Visible.**  
The Pre-Place panel shows live levels even on NO FIRE days. The beginner needs an explicit "informational only — do not place these" message on the Pre-Place panel itself when the verdict says NO FIRE or WAIT.

**Priority 8 — Add a [DEMO] Tag to All Demo Signal Elements.**  
The demo signal produces a real-looking arrow, entry line, stop line, and staging card. Label every element "[DEMO]" so a beginner does not chase a synthetic trigger with real money.

**Priority 9 — Show TRAIL Price on the Staging Card for TREND Signals.**  
`Target TRAIL (30m SMA20, ratchet only)` with the current SMA20 price makes TREND signals manageable. Without a price, the beginner has no monitoring anchor and may exit manually at the wrong moment or not at all.

**Priority 10 — Improve the Lockout and Cooldown Banner Wording.**  
Replace "LOCKOUT" with "TRADING STOPPED TODAY" and explain that it clears the next morning. Replace "COOLDOWN — 14 min remaining" with "SYSTEM PAUSED — 14 min cooldown after stop. Indicator will resume at HH:MM." This directly addresses the "is my indicator broken?" question that firewall and lockout frequently trigger.

---

## Summary

The V2_4 indicator has sophisticated logic underneath a UI that was built incrementally and was never reviewed for beginner readability. The core diagnosis: the chart shows too many diagnostic numbers and not enough decision guidance. Afshin can see *what the indicator knows* but not *what to do with that knowledge*.

The verdict line is the single highest-leverage fix. Every other change on this list is additive; redesigning the verdict from descriptive language to imperative GO/WAIT/STOP with size and risk embedded would immediately address the "valid setups missed" feeling by converting information into instruction.

The VWAP issue is the second most impactful: 14.65% of all level touches in six months are VWAP touches, the two only signals in the dataset fired from VWAP, and yet VWAP is explicitly excluded from the candidate pool. Without labeling this clearly on the chart, every VWAP touch will feel like a missed signal.

The CONFIRM button rename and the signal budget counter together address the two silent failure modes that the JSONL data audit confirms are real: trades not placed because the beginner thought CONFIRM submitted them, and signals not taken because the cap was exhausted invisibly.

---

*Code line references are to `AMTradeCockpitV2_4.cs` (4627 lines). Section references such as "§7" refer to `wave2_audit/v24_code_audit.md`.*
