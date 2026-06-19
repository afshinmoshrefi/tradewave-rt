# AM Transcript Extract - April 16 Session ("Sidekick" Validation)

**Source file:** `C:\seasonals\baiynd_autotrader\video transcripts\AM_transcript_apr_16.txt`
**Session type:** Heuristic-validation walkthrough using AM's "Sidekick" prototype app
**Auditor:** Wave-1 transcript extraction agent
**Date of extract:** 2026-04-27

---

## TL;DR

This session is the single most important rule-articulation session in the corpus so far. AM uses her "Sidekick" tool, which she built the night before, to **quantitatively validate** what was previously a heuristic for her: that the 3:30-4:00 PM ET 30-minute candle dominates next-day flow. She formally **renames the "King Candle" to the "Institutional Candle"** and provides the long-missing volume threshold that turns the heuristic into a rule. Five concrete additions/changes for V2_4:

1. **MOC validation rule (precise):** the 3:30 30-min candle must close with **>= 20% more volume than the 3:00 30-min candle** to validate institutional flow. Below that threshold, stops widen and size is reduced (orange). No flow = no trade (gray).
2. **Lookback:** 60 days of 30-minute data for the Sidekick pattern-ID analysis.
3. **Symbol-specific institutional candle:** **Oil/CL uses the 10:00 AM ET candle, NOT 3:30 ET**, because oil's strategic flow forms after the RTH opening range, not at the equity MOC.
4. **Camarilla pivots:** active for **NQ only** ("they don't work as well in the ES"). V2_4 likely treats them uniformly.
5. **Day-of-week gating:** statistical-probability and threshold-size both **shift every day of the week**. Sidekick reads the day, then sets the threshold (her example: Thursday continuation prob = 45% per Edgeful, but if her institutional MOC is validated AND the 30m 50-SMA is up, dip-buys still work). V2_4 (per task brief) has not implemented this table.

Other extensions: a **1:30 PM ET "pink" candle** that gates pullback/expansion behavior; a tri-state size-signal (green/orange/gray); explicit stop-sizing rule (stop = width of the 3:30 institutional candle when MOC validated); first target = high of 9:30 candle (or high of 4:00 AM candle if entered overnight).

She also explicitly de-recommends **Volume Profile / Value Area** as a cross-platform input ("freaking bananas" - each platform computes it differently), so V2_4 should not lean on VA-high/VA-low for automation.

---

## 1. Institutional-Candle Definition

### 1.1 Renaming - rationale verbatim

> "And so this King candle that we're calling it. And so what we'll call that um I want us to rename the king candle. I want it I want to rename it the institutional candle. And here's why. What I noticed in the data is that that 3:30 candlestick, and I knew this because I used the prior 3:30 to map out the rest of the day, but it told me definitively 3:30 to 4 is where institutional flow is dramatically important." (lines 17-21)

> "9:30 in the morning ends up being trader flow and continuation of institutional candlesticks that come the day before." (line 22)

So she draws a distinction: **3:30 ET = institutional flow**, **9:30 ET = trader flow that continues the prior day's institutional flow**. The naming change is not cosmetic - it is meant to communicate what *kind* of participant is behind the candle.

### 1.2 Which candles she analyzed

> "look at the last 60 days and take these 30 minute candles, 3:30 in the afternoon, GlobeEx open, 4:00 a.m., 9:30 in the morning, all Eastern time" (lines 14-16)

The Sidekick "pattern identification" run was over **60 days** of data on **four 30-minute candles**: 3:30 PM ET (the institutional candle), the GlobEx open (~6:00 PM ET), 4:00 AM ET, and 9:30 AM ET (RTH open).

### 1.3 What the analysis returned

> "The first is yes that 3:30 candle is the one that's going to dominate for prior days." (lines 26-27)

> "Sidekick gave me the first thing. It gave me what the conviction candles are relative to the 30 minute uh closing candlestick. And then what tends to happen based on how much volume occurs in that 3:30 candle. It tells us how big the stop loss needs to be." (lines 40-43)

So Sidekick produces, per symbol: (a) which of the four candles is the dominant ("conviction") candle, and (b) the volume-conditional stop-loss expectation.

### 1.4 Validation against Edgeful (her benchmark)

> "this structure beats every single edge flow statistic that we have. I mapped it against opening range or regular hours, middle of the day, market lulls. I did everything and I took all the open data that Edgeful had. I plugged it into Gemini and Gemini said, 'Your statistics beat every single one of these.'" (lines 34-38)

> "it's on every single one that Edgeful put together. This system beats all of them. All of them. And by a country mile." (lines 282-284)

This is her self-reported confidence anchor for the rule set.

---

## 2. MOC Validation Rules (the key quantitative addition)

### 2.1 The 20% threshold - verbatim

> "When that candle becomes dramatically important is if the 3:30 candlestick moves with at least 20% more volume than the 3:00 candlestick and what that tells us about market on close positions for institutional flow. We have market on open that's M O and we have market on close M O C." (lines 28-31)

**Rule (formal):** `MOC_VALIDATED = (Vol_3:30 >= 1.20 * Vol_3:00)`

Where `Vol_3:30` is the volume of the 3:30-4:00 PM ET 30-minute candle and `Vol_3:00` is the volume of the 3:00-3:30 PM ET 30-minute candle on the same trading day (the prior session for next-day signal use).

### 2.2 What happens below threshold (the 0.80/1.00 gap clarification)

> "If the 30 minute candlestick is not at least 20% more of the volume, the the stops expand." (lines 43-44)

Combined with the tri-state UI signal:

> "this will flash up green or red telling us what institutional flow looks like. It'll tell me what size I want to take, whether it's reduced or full. Reduced size will be orange. No trade will be gray. It'll be nothing. And then full size will be green." (lines 140-143)

And later, on Thursday:

> "The threshold is gray at 65 because it's sitting at the minimum. That's telling us, hey, listen, based on Thursday, we still have good solid flow from our threshold event." (lines 151-152)

**Reading the 0.80 vs 1.00 vs 1.20 gap:** AM does not name the lower bound numerically in this transcript, but the *behavior* she describes implies:
- Vol_3:30 / Vol_3:00 >= 1.20 -> GREEN, full size, MOC validated, stop = width of 3:30 candle
- 1.00 <= ratio < 1.20 -> ORANGE, reduced size (half or 1/3), stops expand
- ratio < 1.00 (3:30 quieter than 3:00) -> GRAY, no trade

She does not in this session say the lower bound is exactly 0.80 or 1.00; that needs another session to confirm. **AM-escalation flag:** this transcript leaves the lower edge of the orange zone formally undefined. The task brief says it was clarified later - not in apr_16.

### 2.3 Confirmation example

> "MOC gives us what the trading structure looked like in the prior day. And notice MOC is almost twice as high as the 3:00 candle. And so it gives us the market on close validation." (lines 207-209)

Demonstrating the rule on the live NQ chart - the prior 3:30 candle was ~2x the 3:00 candle, well above 1.20x, so the structure shows up as "Mark validated" in the Sidekick header.

### 2.4 What MOC validation unlocks

> "if institutional market on close has been validated from the day before, the only short trades or scalp trades into primary candles like that 9:30 candle or the 4:00 a.m. candle or anything like that." (lines 154-156)

Translation: when MOC is validated long, intraday shorts only into reaction zones at the 9:30 or 4:00 AM candle highs - the dominant trade is dip-buying. (And mirror logic for validated-short, by symmetry.)

> "if you have institutional flow, the trade becomes the high of the 30 minute candle to go long. And notice you can do that at 4:00 a.m. because it really does hold the range. the size of the stop is always going to be the width of that um 3:30 candle." (lines 161-164)

**Stop-sizing rule:** `Stop = high_of_3:30 - low_of_3:30` (the width of the institutional candle). This is the validated-MOC stop. For non-validated MOC, "stops expand" (line 44) - magnitude not quantified.

### 2.5 Targets

> "your first target is going to be the high. If you take it in the middle of the night, the first target is going to be the high of the 4hour candlestick." (lines 168-170)

She corrects herself - she says "4 hour" but means **4 AM** candle:

> "And then height of 4 a.m. or 4 hour 4, sorry, 4 a.m. I always say 4 hour. It's the 4 a.m. candlestick." (line 170)

So: first target = high of 9:30 candle for daytime entries; first target = high of 4:00 AM candle for overnight entries.

### 2.6 Stocks transfer

> "Now it turns out that this is also incredibly important for stocks in general because they all move at that same time but some stocks have a little bit of a sticky patch." (lines 32-34)

Out of scope for ES futures trading but a flag that the same MOC framework will be ported to TradeWave's individual-stock layer.

---

## 3. CL / Oil Specifics

### 3.1 The rule - verbatim

> "And and what are your king candles of oil? The interestingly enough, it is the 10 a.m. candlestick formation. Now really, but they open at 8. I know, but the open does not matter. It's about after after the regular what is it called? After the opening range formation of the regular trading hours, oil strategizes its position. All the traders strategize from that um from that space." (lines 184-189)

**Rule:** for CL/oil, the institutional candle is **10:00 AM ET (not 3:30 PM ET)**. Rationale: oil's RTH open is 9:00 AM ET (CME pit open) so the 10:00 candle is the first candle *after* the opening range, which is when oil traders settle into a directional bias. Her phrasing - "all the traders strategize from that space" - implies the 10:00 candle is for oil what the 3:30 candle is for equity index futures: the participant-confirmation candle.

### 3.2 Inferred MOC analog for CL

She does not in this transcript say whether the **20% volume rule** transfers to CL with 10:00 vs 9:30. But the language "10 a.m. candlestick formation" parallels her equity-index framing, so the most defensible default for V2_4 would be: `Vol_10:00_CL >= 1.20 * Vol_9:30_CL` to validate. **AM-escalation candidate** - confirm in a later session.

### 3.3 Symbol coverage Sidekick analyzed

> "I built a pattern that's for the NQ for the YM for gold and for oil and all of them came back with some super interesting formations." (lines 181-183)

So far Sidekick covers: ES (presumably, though she switches off the NQ tab to look at it - line 98), NQ, YM, GC (gold), CL (oil). Each has its own Sidekick-determined institutional candle. **V2_4 should not assume 3:30 ET for CL or GC.** Gold's institutional candle is not stated in this transcript - another AM-escalation candidate.

---

## 4. Camarilla Pivots

### 4.1 Verbatim

> "wait what is this line here Yeah, usually when you see something This is a camarilla. Okay. So, the camarillas for the NQ work really well. They don't work as well in the ES." (lines 275-276)

> "the Camarillas, they do great for the NQ." (line 281)

**Rule:** Camarilla pivots are **active on NQ, suppressed on ES.** No reason given beyond empirical performance. She does not specify which Camarilla level (H3, H4, L3, L4) she uses or how she draws them.

### 4.2 What she says they do for NQ on the chart

> "And notice interestingly how it it behaves so robustly around these pivots. It literally tells you when to take profit as long as everything sits in the same direction. if MOC is validated, if um your 50 simple moving average is up and then we can use the probability of continuation." (lines 266-269)

So on NQ: Camarilla levels function as **profit-take zones** when (MOC validated) AND (30m 50-SMA up) AND (probability-of-continuation favorable). They are filtered, not standalone.

### 4.3 Implication for V2_4

V2_4 either applies Camarilla to all symbols or to none - her rule is symbol-dependent. **Flag:** add a per-symbol enable for Camarilla and switch it OFF for ES, ON for NQ. Other symbols (YM, CL, GC) - she does not say, so default OFF until confirmed.

---

## 5. Day-of-Week Gating (the source of the missing V2_4 table)

### 5.1 The big takeaway - verbatim

> "So the big takeaway is that this shifts every day of the week. The statistical probability and the threshold size, what size you want to uh position it, it's now triggered by days of the week and what the data say about the range of motion." (lines 148-150)

This is explicitly the source of the day-of-week table that the brief notes V2_4 hasn't implemented. Sidekick is doing a **two-axis lookup**: day-of-week x Edgeful-style continuation probability, then setting the size threshold.

### 5.2 Worked Thursday example

> "What happens on Thursdays in general? So the statistical probability that edgeful says about continuation on the day is only 45%." (lines 103-105)

> "Edgeville says it's only 45% probability that the price action continues to the high. For me, I have that the institutional market on close has been validated. And if the 50 simple moving average on the 30 is up, trending upward, the dips are still going to get bought. They're absolutely still going to get bought simply because the institutional flow is green and it's been validated for dip buying." (lines 107-111)

> "The threshold is gray at 65 because it's sitting at the minimum. That's telling us, hey, listen, based on Thursday, we still have good solid flow from our threshold event." (lines 151-152)

**Rule structure (Thursday example):**
- Edgeful baseline continuation probability: 45%
- AM override layer: if MOC validated AND 30m 50-SMA up, dip-buys are still good - just don't expect new HOD
- Sidekick threshold reading on Thursday: gray at 65 (described as "sitting at the minimum"), but the MOC threshold event still permits trade because flow is green

### 5.3 What this implies for the table

The full day-of-week table is not enumerated in this transcript. She gives only Thursday. The other six days of the week each have their own (a) baseline continuation probability and (b) Sidekick threshold setting. **AM-escalation candidate:** request the full table or the Sidekick screenshots she promised to send.

### 5.4 The 50-SMA filter

> "the 50 is the 50 and the 200 are absolutely my go-tos I don't I don't use anything else and people are like oh why don't you because it gives me such high reliability it truly is phenomenal" (lines 272-275)

**Confirmation rule:** **30-minute 50-SMA + 200-SMA** are her core trend filters, and she does not use other MAs. V2_4 should make these the canonical trend layer.

---

## 6. Other Setups in the Transcript

### 6.1 The 1:30 PM ET "pink" candle (pullback/expansion gate)

> "Notice it breaks the 50 simple moving average, but it does not lose the low of the uh 1:30 candle. And so this little nuance here at this 1:30 candle, notice I have it pink." (lines 124-125)

> "We haven't really talked about it, but it's for the pullback event. This 1:30 candlestick is a pullback event or it's an expansion event. It trend is going in the opposite direction." (lines 128-129)

> "this 1:30 candle that I have in pink, that is a candle that I have always had there, but it's just not uh it only comes into play if we have a retracement event that gives us the dip buying formation. Right? So, we can go if it holds the 1:30 candle and it begins to hold and we had institutional flow then it's very likely to go to the top of the 9:30 candle." (lines 132-135)

**Rule:** the 1:30 PM ET 30-min candle is a conditional support/resistance level. It only matters if (a) price has retraced into it AND (b) prior-day MOC is validated. If both, the dip is likely to hold and rotate back to the high of the 9:30 candle. V2_4 should flag the 1:30 candle and switch its display on only during retracement events with validated MOC.

### 6.2 Tri-state size signal (the Sidekick UI surfaces it)

Already quoted in 2.2:
- GREEN = full size (validated MOC, all filters aligned)
- ORANGE = reduced size, "half size or a third" (line 159), MOC marginally validated or trend marginally aligned
- GRAY = no trade

V2_4 needs an equivalent multi-level signal, not a binary go/no-go.

### 6.3 Initial Balance / IB-traders' setup

> "a lot of people right now are going to be confused because they go, 'Wait a second. I lost my entire 9:30 candle. Here's my 10:30 candle.' The guys who trade initial balance are now going to say, 'Okay, I had a look below that initial balance and now it's above the initial balance.' So, they are trying to go long. They're going to try and push it into that first pivot." (lines 171-175)

She doesn't trade IB herself but recognizes that **after a 9:30-candle-low loss followed by a 10:30 reclaim above the initial balance high, IB traders push price into the first pivot.** This is anti-confluence - she is using it as a *secondary participant flow* explanation for why dip-buys post-MOC-validation work into pivot 1. V2_4 could optionally add an "IB-reclaim" annotation but it is not load-bearing.

### 6.4 Volume profile / value area - explicitly NOT to use

> "the reason we can't use value area high is because each platform has a unique way of counting candle closes and opens. And so this number can vary... If you use Ninja, you're going to get a totally different volume profile... It's just It's freaking bananas." (lines 234-251)

> "that's why Edgeold does not use that in its statistics because it's variable across different platforms." (lines 251-252)

**Rule:** V2_4 should NOT use value-area-high or value-area-low as a quantitative input for the autonomous stack, because the values are not portable across platforms. It can be displayed as a visual aid for manual trading only. (V2_4 does compute its own VA - that is platform-internal and self-consistent, but it should not be treated as a ground-truth value AM endorses.)

### 6.5 Drawdown-aware entry gating (machine-learning side)

> "if you say hey I want my max draw down on the day to be no more than seven points your entry will be at the minimum if I can't get it down here for maximum draw down I'm not taking the trade right" (lines 76-78)

> "machine learning could tell you... this is a good trade because it has high chance of working with 7% or it says oh no this is not good because the uh this would have at least maybe 15% draw down" (lines 79-81)

This is a forward-looking ML-layer rule, not an indicator rule, but worth noting: each setup gets a **predicted-drawdown band**, and the trade is gated by user-set max DD. Out of scope for V2_4 indicator but relevant for the autonomous stack downstream.

### 6.6 Model drift / retraining cadence

> "I use the models based on last 12 years okay so what happens in the intraday because intraday moves so quickly because of zero DTE that cycle that we use is 3 to 6 weeks, but we have to check it at the end of every week to make sure that it's still tracking and if it's shifting anywhere." (lines 82-85)

End-of-day models: 12-year training window. Intraday models: **3-6 week retraining cycle, weekly drift check** because of 0-DTE-driven regime changes. Indirect note for the ML layer.

---

## 7. Notable Quotes (high signal density, condensed for Wave 3 reuse)

1. (Naming) "I want it I want to rename it the institutional candle... 3:30 to 4 is where institutional flow is dramatically important." (lines 18-21)
2. (9:30 vs 3:30) "9:30 in the morning ends up being trader flow and continuation of institutional candlesticks that come the day before." (line 22)
3. (Threshold) "if the 3:30 candlestick moves with at least 20% more volume than the 3:00 candlestick" (lines 28-29)
4. (Lookback) "look at the last 60 days and take these 30 minute candles" (line 14)
5. (Stop-sizing) "the size of the stop is always going to be the width of that um 3:30 candle" (lines 163-164)
6. (Below threshold) "If the 30 minute candlestick is not at least 20% more of the volume, the stops expand." (lines 43-44)
7. (Tri-state) "Reduced size will be orange. No trade will be gray... full size will be green." (lines 142-143)
8. (Day of week) "this shifts every day of the week. The statistical probability and the threshold size... it's now triggered by days of the week" (lines 148-150)
9. (Camarilla) "the camarillas for the NQ work really well. They don't work as well in the ES." (line 276)
10. (Oil) "for oil... it is the 10 a.m. candlestick formation... after the opening range formation of the regular trading hours, oil strategizes its position." (lines 184-188)
11. (Validation against Edgeful) "This system beats all of them. All of them. And by a country mile." (lines 282-284)
12. (50-SMA) "the 50 and the 200 are absolutely my go-tos I don't I don't use anything else" (lines 272-274)
13. (1:30 candle) "this 1:30 candlestick is a pullback event or it's an expansion event" (line 128)
14. (1:30 + MOC chain) "if it holds the 1:30 candle and it begins to hold and we had institutional flow then it's very likely to go to the top of the 9:30 candle" (lines 134-135)
15. (Targets, overnight) "If you take it in the middle of the night, the first target is going to be the high of the... 4 a.m. candlestick" (lines 168-170)
16. (Validated MOC -> trade direction) "if institutional market on close has been validated from the day before, the only short trades or scalp trades into primary candles like that 9:30 candle or the 4:00 a.m. candle" (lines 154-156)
17. (Volume profile portability) "every single one of them gives us a different value area high, value area low. It's just It's freaking bananas." (lines 249-250)

---

## 8. Setups Potentially MISSING from V2_4 (priority-ordered)

**Priority 1 - quantitative gaps (V2_4 needs the number):**

1. **MOC 20% threshold (Vol_3:30 / Vol_3:00 >= 1.20).** The brief says V2_4 has a 3:30 candle. Confirm whether V2_4 actually applies the 1.20 ratio test, and whether it uses the *prior session's* 3:30 vs 3:00 to gate *next session's* trades (not same-session, since the candle closes at 4:00 PM).
2. **60-day rolling lookback.** Sidekick uses 60 days for the pattern-ID analysis. V2_4 likely uses a different (or fixed) lookback for whatever historical comparison it does. Align.
3. **Day-of-week table.** Five rows minimum (Mon-Fri), each with a baseline continuation probability and a Sidekick threshold value. The brief explicitly flags this as not implemented.
4. **Stop = width of 3:30 candle (validated case).** Confirm V2_4 stop-sizing matches.
5. **Per-symbol institutional candle lookup table** - ES/NQ/YM = 3:30 PM ET, CL = 10:00 AM ET, GC = unknown (escalate). V2_4 likely hardcodes 3:30 for all symbols.

**Priority 2 - structural gaps (V2_4 needs the rule shape):**

6. **Tri-state size signal (green/orange/gray)** with explicit reduced-size = 1/2 or 1/3. V2_4 may have a binary signal.
7. **Camarilla NQ-only enable.** Per-symbol toggle. Default ON for NQ, OFF for ES, undefined elsewhere.
8. **1:30 PM ET conditional candle.** Display only during retracement-into-1:30-candle events with validated MOC. V2_4 may not have this conditional layer.
9. **First-target rules:** daytime entry -> high of 9:30 candle; overnight entry -> high of 4:00 AM candle. Confirm V2_4 emits the correct one based on entry time.
10. **Validated-MOC -> dip-buy-only directive.** Counter-trend (short) trades only into 9:30 or 4:00 AM candle reaction zones when MOC is long-validated (and mirror).

**Priority 3 - filtering / display:**

11. **30-minute 50-SMA and 200-SMA** as the canonical trend filters. V2_4 should use 30m timeframe specifically (not generic "current chart timeframe").
12. **Volume profile / value area** suppressed in autonomous stack (display-only for manual). V2_4 should not pass VA values to ML.
13. **9:30 vs 3:30 participant labeling** in the indicator UI: 9:30 is "trader flow continuation," 3:30 is "institutional flow."

**Priority 4 - downstream / ML stack (not V2_4 indicator scope but flagged):**

14. ML drawdown-band gating on entries.
15. Intraday model 3-6 week retraining cadence with weekly drift checks.

---

## 9. Cross-Reference Notes for Wave 3

- **MOC threshold lower bound (the "0.80 vs 1.00" question in the brief):** apr_16 leaves this UNDEFINED. AM names only the upper threshold (1.20). The orange-band lower bound is implied behaviorally but not stated. Wave 3 should pull this from a later transcript - the brief says it was "clarified later." Until then, defensible default: orange = `1.00 <= ratio < 1.20`, gray = `ratio < 1.00`.
- **Symbol institutional-candle table:** apr_16 confirms ES (3:30), NQ (3:30 implicit), YM (3:30 implicit), CL (10:00). GC explicitly mentioned as Sidekick-analyzed (line 182) but the candle time is NOT stated. Wave 3 needs to find GC's institutional time.
- **Day-of-week table:** apr_16 gives only Thursday in detail. Other days need cross-reference from later sessions or Sidekick screenshots she promised to send (lines 47-50, 230-232).
- **Camarilla level used:** apr_16 says NQ only; level (H3/H4/L3/L4) not specified. Wave 3 should look for "H3" or "H4" or "Camarilla level" in other transcripts.
- **CL volume threshold:** the 1.20x rule is stated for the 3:30/3:00 pair. apr_16 does not explicitly extend it to 10:00/9:30 for CL. Default-extend with caution and validate elsewhere.
- **"Sidekick" provenance:** AM built Sidekick the night before this session (line 203). Earlier transcripts will not reference Sidekick by name. Wave 3 should map old terminology ("king candle") to new ("institutional candle") consistently across the transcript corpus.
- **Beginner-friendly translation:** AM's intent (lines 211-217) is explicitly to "obfuscate as much as possible" so the end-user just sees "buy the dip, best dip, low of the institutional flow candle risk..." without seeing the underlying statistics. This shapes the UX target for Afshin's beginner-trading view of V2_4: surface the directive ("dip-buy permitted, full size") not the volume ratio.
- **Validation philosophy:** AM treats Edgeful as the external benchmark and Gemini as the comparison oracle. The "beats every Edgeful statistic" claim (lines 34-38, 282-284) is her self-reported confidence; OOS backtesting is the Wave-2/3 job to confirm this for Afshin's actual fills.
- **Off-topic content excluded:** ~30 minutes of the 58-minute session is unrelated to rules - discussion of Howard, Mike Sachello, Trade Wave homepage, family, NetJets, etc. (roughly lines 53-69, 295-486). All relevant rule content is captured above.

---

**End of extract.**
