# Anne-Marie Baiynd — Comprehensive Rule Inventory

Source: 5 transcripts (mar-6, apr-8, apr-9, apr-10, apr_16) + AM_strategy_summary.md.
Compiled from 20 parallel extractions, one per topic.

Each rule is followed by a verbatim quote and source. Rules flagged **[PIPELINE GAP]** are cases where the current `pattern_scorer_rt2` / `AMTradeCockpitV2_3` pipeline diverges from or does not implement AM's stated method. Rules flagged **[NOT IN TRANSCRIPTS]** are in the summary doc only — likely inferences by the pipeline team.

---

## 1. INSTRUMENT UNIVERSE

- **Trades:** ES, NQ, CL, GC, RTY. Also micros MEES, MNQ for combines/small accounts.
- **Does NOT trade:** YM. *(mar-6: "I do ES, NQ, CL, RTY. I don't normally trade the YM.")*

---

## 2. INSTITUTIONAL CANDLE — THE CORE FRAME

Four candidate boxes (all ET):
- **3:30–4:00 PM close** — the MOC "institutional candle" (primary for ES, NQ, GC)
- **6:00–6:30 PM Globex open**
- **4:00–4:30 AM Europe open**
- **9:30–10:00 RTH open**

CL (crude oil) institutional candle = **10:00 ET**, not 3:30. *(apr-16: "The interestingly enough, it is the 10 a.m. candlestick formation… after the opening range formation of the regular trading hours, oil strategizes its position.")*

### Which box is "active/in charge" — containment hierarchy

- The largest-enclosing candle wins. *(apr-9: "with every box… how does that box compare to the box before it?… So now the 3:30 candle says, 'Hey, I'm in charge.'")*
- If 9:30 candle sits inside prior 3:30 → 3:30 is in charge.
- Box walkdown order when sideways: **3:30 → 6 PM → 4 AM → 9:30**.

### MOC validation (the 20% rule)

- 3:30 candle is "dramatically important" only if its volume ≥ **20% above** the 3:00 candle volume, over a **60-day lookback**.
- If NOT validated → **stops expand** and **size reduces**. *(apr-16)*
- If validated → full size; stop = width of that 3:30 candle.

### Rule: Entry is at the high/low of the *active* institutional candle on retrace from outside
*(apr-16: "If you have institutional flow, the trade becomes the high of the 30 minute candle to go long… you can do that at 4:00 a.m. because it really does hold the range.")*

**[PIPELINE GAP]** The pipeline does not compute MOC validation or implement the FULL/REDUCED/NO-TRADE state gate from the 20% volume rule.

---

## 3. TREND GATE — STACK + SLOPE (BOTH MATTER)

### Stack (confirmed in transcript)
- Bullish: price > SMA50 (30-min) > SMA200 (30-min). *(apr-8: "we're seeing is a very bullish day where dips are buys. Why? Because I'm above the 200 and I'm above the 50.")*
- Bearish: inverse.

### Slope (also required)
- *(apr-8: "I literally only take trades in the direction of the 200 and the 50 when they're both going down.")*
- *(apr-9: "I like to see my moving averages going straight up or straight down for me to do something like that.")*

### Counter-trend / cross-current = same direction, reduced size
- *(mar-6: "My 200 gives me a down to flat formation. My 50 gives me a down and then an up formation. So I have a cross-current here. So the trade that I would take would be the short. The exact same trade I took at the open.")*
- *(mar-6: "The size that you take of the trade depends on whether your trend or counter trend. So because I have a 30-minute chart that is going straight up like this, I can only take small size on the short until it breaks pattern.")*

### Flat moving averages — mathematical meaning
- *(apr-8: "I know the math of a flat moving average. It tells me I have as much behavior underneath the line as above the line.")* → no directional edge.
- Flat 50 + VWAP bounce: entry level is the flat 50 itself. *(apr-10)*
- Flat SMAs → ignore divergence signals. *(apr-9)*

### No numerical slope threshold
AM does not give any degrees-per-bar or tick-per-bar slope definition. Slope is **eyeballed** (up / down / flat / turning).

**[PIPELINE GAP]** The indicator's trend gate (AMTradeCockpitV2_3) uses only the stack check, not slope. It does not recognize the cross-current / weak-trend case. It has no flat-detection logic and therefore cannot detect sideways regime.

### 200 SMA additional weight
- *(apr-8: "The 200 moving average is the most highly significant statistically speaking technical indicator.")*
- *(apr-9: "This 200 line that you see right here is their make or break line.")*
- Fractal application: she uses 200-period SMA on both 30-min AND 1-min charts.

---

## 4. SIDEWAYS / FLAT DAY REGIME

### Detection
- Overlapping prior-day 3:30 + current 9:30 → inventory accumulation. *(apr-9)*
- 6 PM candle inside prior 3:30; 4 AM partially inside prior 3:30 → "we know it's a sideways day until the break" *(apr-9)*
- Flat VWAP + declining volume + flat momentum. *(mar-6, apr-8)*

### How to trade it
- Trade **the edges**: buy lower edge into upper edge, sell upper edge into lower edge. *(apr-9)*
- Use **pivots** that mesh with Globex shading boxes as the edge-confirmation levels. *(mar-6)*
- May trade the same range "five or six times a day" — max 5. *(apr-10)*
- Level-to-level exit (edge A → edge B). No trailing.

### Breakout from sideways
- **Breakout trigger = break of 3:30 candle H or L** *(apr-8: "what makes the break is the break of the high of that 3:30 candlestick from the prior day or the low…")*
- Or: **9:30–10:00 high breach** *(mar-6: "I'm really looking for is the breach of the 9:30 to 10:00 high.")*

**[PIPELINE GAP]** No sideways regime detection or trading in the indicator; the trend gate fires strong-trend entries even when AM would be trading range edges.

---

## 5. POSITION SIZING

### Baseline
- ES direct: 2–3 contracts max. *(mar-6: "I don't ever have more than two or three ES on at a time.")*
- TopStep 50K combine: MEES only (no ES bigs).
- MNQ: 1-min open volume benchmark ≈ 6,000.
- ES: 1-min open volume benchmark ≈ 15,000 (range 12K–15K).

### Hard size rules
- **1-min opening range > 10 ES points** → size down to **1 MEES ONLY**. *(mar-6)*
- **Counter-trend** → small size until it breaks pattern. *(mar-6)*
- **MOC NOT validated** → half or third size. *(apr-16: "Reduced size will be orange. No trade will be gray… full size will be green. So size needs to be reduced. So you'd want to use half size or a third.")*

### Per-contract hard stop
- MEES: **$50 max per contract**. *(apr-9: "your stop better not be more than $50 below for each contract.")*

### Daily caps
- **Max 5 trades/day.** *(apr-9: "my max is five.")*
- **$300/day target → done for the day.** *(apr-10: "If you've got one big, that's $320. Just like that. You're done for the day.")*
- Zero-trade days happen: *(apr-10: "Absolutely. It just doesn't come.")*
- **No averaging down when losing.** *(apr-9: "the general desk says you cannot double down when your position is negative.")*

**[PIPELINE GAP]** Indicator has MaxSignalsPerDay but no 5-trade-cap default, no $300-daily-target exit, no MOC-driven size reduction.

---

## 6. ENTRY LEVELS — HIERARCHY AND PRIORITY

### Structural levels she uses (per transcripts)
- Prior day H/L/close
- Globex H/L
- Midnight midpoint
- Europe 4 AM H/L
- Opening range 9:30–10 H/L
- Prior 30-min H/L
- Woody's pivots (PP, R1/R2/R3, S1/S2/S3, +S4/R4 when extended)
- Institutional candle (3:30–4 PM) H/L — dominant
- VWAP *(permission/target only)*

### Prioritization when multiple levels cluster

**1. Watering hole / congestion concept.** *(apr-10: "I'm here at the watering hole… I'm going to the bottom of the watering hole because that's where the girl is.")* → pick the DEEP edge of a multi-level cluster, not the nearest.

**2. Second-prettiest girl (prospect theory).** *(apr-10: "You don't actually go after the prettiest girl. You go after the second prettiest girl.")* → don't chase the obvious level; take the one below/behind it.

**3. Containment hierarchy.** The "in-charge" candle (per §2) defines which level wins. When its H/L is the relevant retrace level, take that.

**4. Never chase.** Always limit orders, pre-placed. Limits at multiple levels simultaneously; first fill wins.

### Instrument-specific
- Camarilla pivots: work on **NQ**, not on **ES**. *(apr-16)*
- Midnight candle matters more on NQ due to algos.
- Prior 30-min high/low: for AM, specifically the prior DAY's 30-min high/low is a "flag-plant" level. *(apr-9)*

### Measured-move targets
*(mar-6: "The 4 a.m. candlestick, if I duplicate it, it gives me a measured move event. And that measured move tells me my next target. Almost every day…")*

---

## 7. ENTRY TIMING

### 1-minute opening candle (9:30–9:31)
- Let it complete. *(mar-6: "We go to the one minute opening candle. We let that candle complete.")*
- Measure its range. If > 10 ES pts → 1 MEES only.
- **Wait for a failed bounce**, then enter on retest into the opening range. *(mar-6)*

### 2nd-minute rule
If first-minute volume < ES 12K / NQ 6K → the traders are tentative. Wait for the 2nd minute bar. If it's inside the 1st minute, range is confirmed. *(apr-9)*

### Pre-market limits
AM places limits before RTH open (apr-10: limits at 62 and 64 before 9:30). She does NOT take signals pre-RTH, but the limits sit there.

### Specific algo windows
*(apr-10: "9:04 9:02 and then 9:14 to 9:18 and then 9:24 to 9:27")* — algos tend to push at these minute-marks.

### Never market orders
*(apr-9: "I never use market orders. Always limit orders. Always limit.")*

**[PIPELINE GAP]** Indicator's `V2_3` has a pre-10:00 gate removal that aligns with AM ("10:00 is soft, not hard"). Good. But the summary doc's "limits after 10:00 ET bar closes" rule conflicts with the transcript evidence that AM places limits pre-RTH.

---

## 8. RETRACE-SIDE FILTER (MEAN-REVERSION ONLY)

- Longs only on pullback to support from above. Shorts only on pullback to resistance from below.
- *(apr-10: "I don't chase anything and I simply wait for it.")*
- *(apr-10: "I'm not trading counter trend. I have both upward formations on my moving averages.")*
- *(apr-9: "whether it's trending or sideways, we're going to pick the support and buy it into resistance or we're going to pick the resistance and buy it into support.")*

**Breakout trades are the "wrong plan"** *(apr-10)*. EXCEPTIONS:
- Sideways-day break of 3:30 H/L as directional trigger.
- 9:30–10 high breach on sideways days.
- In both cases, entry is on a **pullback** after the break, not the break itself.

**[PIPELINE OK]** Retrace-side filter is correctly implemented (`CheckEntry` + Pre-Place).

---

## 9. VWAP USAGE (regular session VWAP)

**Role:** slope gauge + side-permission filter + first-target magnet + convergence-breakout trigger. **NEVER an entry.**

- **Slope reads regime.** Flat VWAP = sideways / no trend. Sloped VWAP = directional.
- **Side = permission.** Above-VWAP → only longs. Below → only shorts.
- **First target on trend trades.** *(mar-6: "your target is going to be the VWAP is the first target.")*
- **Convergence with 50 + 200 = breakout sweet spot.** *(apr-10)*
- **Platform warning.** Different platforms compute VWAP differently across timeframes.
- **No bands.** *(apr-8: "I do not have the bands of the VWAP. I find them useless.")*

Explicit denial: *(apr-10: "You can't just go, 'Hey, I'm buying the VWAP.'")*

**[PIPELINE GAP → FIXED IN V2_4 CHANGE #1]** V2_3 was placing entries on VWAP. V2_4 removed VWAP/AnchVWAP from the entry-candidate list.

---

## 10. ANCHORED VWAP — NOT IN TRANSCRIPTS

**[NOT IN TRANSCRIPTS]** AM never says "AVWAP" or "anchored VWAP" in any of the 5 transcripts. The concept of "anchored VWAP from prior institutional candle" exists only in `AM_strategy_summary.md` and the pipeline code. It is a plausible extension (anchor where she says flow concentrates) but is not an AM-taught rule.

The V2_3 indicator was a midpoint proxy until 2026-04-19 when it was updated to a real running AVWAP to match the ML pipeline. Both sides are pipeline inventions; AM does not use this level.

---

## 11. STOPS

### Initial stop — width source
**CRITICAL DIVERGENCE:** AM verbally says stops are **width of the 3:30 institutional candle** (H–L), *(apr-16: "the size of the stop is always going to be the width of that um 330 candle.")*

**[PIPELINE GAP]** `AM_strategy_summary.md` and the indicator use "Europe 4AM candle width" clipped to 0.30–0.80 × ADR20. AM says 3:30 in apr-16. The Europe-4AM-as-stop rule appears in the summary doc only, not in transcripts verbatim. This is a reconcilable discrepancy but worth noting.

### Stop placement
- **Short:** just over the 1-minute high (or top of entry candle).
- **Long:** just under the wick of the entry candle. Halfway-up variant for 30-pt reward trades.
- **Reduced-risk:** per AM's half-or-third sizing rule when MOC unvalidated, stop stays anchored to the institutional candle width — widened trade stops are implied but NOT the "half-width of 4 AM candle" the user understood.

The explicit "half size + half 4AM-candle-width stop when 200 in-trend and 50 against" is **NOT verbatim** in any transcript. Closest matches:
- mar-6: cross-current → same-direction trade, small size.
- apr-16: MOC unvalidated → half-or-third size with expanded stops.

If Anne-Marie's yesterday's clarification was "half Europe-width stop when 50 flips against 200", that refinement is NEW (not in these 5 transcripts) and needs a fresh transcript or direct confirmation from her.

### No trailing stops
*(apr-9: "I don't trail any stops. I go level A to level B and I'm done.")*
*(apr-8: "trailing stops are terrible.")*

**[PIPELINE GAP]** V2_3 uses 30-min SMA20 trail. The summary doc acknowledges this is a backtestable proxy that compresses the left tail of the R-distribution. Live trading under AM's rules should use fixed level-to-level exits, not an SMA trail.

### Manual ratcheting when sideways
When a trade goes mid-range (e.g., stuck between 200 and 50 SMA), she moves stop up to a specific structural level (midnight high, pivot) to lock in small profit. *(apr-8)*

### Break-even concession
*(apr-8: "If you're thinking to yourself, 'Oh my gosh, I don't want to lose anything.' Then get up and leave your stop at break even and go leave the room.")* Framed as emotional concession, not optimal process.

---

## 12. EXITS

- **Level-to-level, fixed.** *(apr-9: "I go level A to level B and I'm done.")*
- **First target = VWAP** on trend-retracement trades.
- **Alternative first targets:** 4 AM candle edge, flat 50 SMA, 1-min opening range edge.
- **Scratch when thesis invalidated** (opposing large prints, pattern break) — size of loss doesn't matter.
- **Time-based flat** *(summary)*:
  - CL: flat by 14:30 ET, cancel limits 14:00 ET.
  - ES/NQ/GC: flat by 15:00 ET, cancel limits 14:30 ET.
  - **[NOT IN TRANSCRIPTS]** verbatim in the summary doc; AM does not quote these times in these 5 videos.
- **Second-prettiest girl exit** — take positions off when "sound enough" even before the best exit.

---

## 13. HIKEN ASHI & MOMENTUM

- Hiken ashi sign (above/below zero line) provides confirmation of permission. *(apr-9)*
- Above zero + price above SMAs → pullbacks are buy zones.
- Below zero + price below SMAs → bounces are sell zones.
- Flat momentum → ignore.

---

## 14. VOLUME CONFIRMATION

- **ES 1-min open benchmark:** ~15,000 contracts (range 12K–15K).
- **NQ 1-min open benchmark:** ~6,000 contracts.
- Below benchmark → "tentative traders" → wait for 2nd minute bar.
- **MOC validation (20% rule):** 3:30 candle volume ≥ 20% above 3:00 candle, 60-day lookback.
- **News-candle volume:** thin = fade candidate.
- **Big-trade threshold:** 250+ contracts at a time on ES triggers attention.

---

## 15. PIVOTS

- **Woody's pivots are always loaded.** PP, R1/R2/R3, S1/S2/S3.
- **S4/R4** are added when extended beyond R3 or below S3.
- **R3 banner**: price above R2/R3 = extended, watch for exhaustion.
- **Camarilla**: works on NQ, not on ES.
- **Pivots are targets, not stop locations** in strong trend. In sideways, pivots are entry anchors when they align with Globex boxes.

---

## 16. OPEN QUESTIONS / UNRESOLVED DETAILS

1. **Stop width: Europe 4AM vs 3:30 candle** — apr-16 transcript says 3:30; summary says Europe 4AM. Reconcile.
2. **Half-width stop on weak-trend** — not in any transcript verbatim. Needs confirmation from AM directly.
3. **Slope threshold definition** — no numerical rule stated; "eyeballed" only. Any auto-detection needs a pick threshold (e.g., "higher/lower than N bars ago" over a specific lookback).
4. **MOC validation implementation** — the 20%-volume rule is clear, but the FULL/REDUCED/NO-TRADE state gate is not in our codebase.
5. **5-trade daily cap + $300/day target** — AM enforces these; pipeline does not.
6. **Level-to-level exit vs SMA20 trail** — pipeline uses trail as a backtesting proxy. Live implementation should switch to level-to-level.
7. **Anchored VWAP** — AM does not teach this. Pipeline uses it. Revisit whether to keep the feature in the ML model training set.

---

## 17. CROSS-REFERENCE: PIPELINE GAPS SUMMARY

Gaps that affect V2_4 rule-change sequencing:

| Gap | Severity | In scope for V2_4? |
|-----|----------|--------------------|
| VWAP/AVWAP as entries | FIXED in V2_4 change #1 | ✓ done |
| Slope-based trend gate | HIGH | change #2/#3 (planned) |
| Sideways regime detection | HIGH | change #4 (planned) |
| MOC validation (20% rule) | HIGH | NEW — add as change #5 |
| Cross-current / reduced-size path | MEDIUM | part of change #3 |
| Stop width: 3:30 vs Europe 4 AM | MEDIUM | needs AM clarification first |
| Level-to-level exits (no trail) | MEDIUM | separate — affects labeling pipeline, not just indicator |
| Max 5 trades/day / $300 target | LOW | indicator-config knob |
| Camarilla pivots NQ-only | LOW | cosmetic |
| Anchored VWAP provenance | LOW | keep or drop after evidence review |

---

## SOURCE FILES
- `C:\seasonals\baiynd_autotrader\video transcripts\AM_transcript_mar-6.txt`
- `C:\seasonals\baiynd_autotrader\video transcripts\AM_transcript_apr-8.txt`
- `C:\seasonals\baiynd_autotrader\video transcripts\AM_transcript_apr-9.txt`
- `C:\seasonals\baiynd_autotrader\video transcripts\AM_transcript_apr-10.txt`
- `C:\seasonals\baiynd_autotrader\video transcripts\AM_transcript_apr_16.txt`
- `C:\seasonals\baiynd_autotrader\video transcripts\AM_strategy_summary.md`
