# AM Transcript Extract — apr-8 (Chart Setup Session)

**Source:** `C:\seasonals\baiynd_autotrader\video transcripts\AM_transcript_apr-8.txt`
**Session character:** This is a screen-share where AM walks Afshin through her Think-or-Swim chart setup (ahead of porting to NinjaTrader). The session is a hybrid between (a) a chart-configuration tutorial and (b) a live walk-through of "today" (a short-covering rally, ES near 6800) and "yesterday" (a sideways mosh-pit). Two concrete trade examples are described in detail. The transcript is shorter than the apr-23/apr-24 sessions and has less rules-as-code material, but it contains the canonical statement of WHY her chart looks the way it does — and several heuristics that do not appear in `AM_rules_v2_spec.md`.

---

## TL;DR

This session is the source of AM's chart-setup philosophy. Six things matter most: (1) **VWAP without bands** (she finds bands "useless… not statistically strong enough"); (2) **50 and 200 SMA on PERIOD basis** (not day) — explicitly rebutting the common reading of "DMA"; (3) **Woody's pivots with a custom banner** ("Claude wrote it for me") that auto-flags when price is above R2/R3 = "extended, watch for exhaustion"; (4) **Shaded candle boxes** for five reference candles — Prior 3:30, GlobEx 6 PM, Midnight, Europe 4 AM, RTH 9:30 — implemented as a custom indicator AM calls the **"one minute intraday"**; (5) **The 200 SMA is "the most highly statistically significant technical indicator"** and because the market is fractal she uses it on EVERY timeframe (1m, 5m, 30m, 600s/6m); (6) Two concrete trade setups are demonstrated — an **opening-range break-down with re-test entry** (the canonical "OR retest" trade that requires opening-range > 10 points → use 1 MES not size up) and a **second-trade re-engagement** when VWAP is flat (same setup repeats). She also describes a **front-running risk on round-number pivots** (6800) where a limit order at 6811 may get stopped at 6824 because traders front-run pivots. Her self-stated rhythm: *"only one setup for me, two, three trades a day max."* Several elements of this session are NOT in the V2_4 spec: Woody's pivots themselves, R2/R3/R4/S4 + the exhaustion banner, the round-number-pivot front-run heuristic, the explicit fractal-200-SMA reasoning, and the "10-point opening-range size cap."

---

## 1. Indicators She Uses (and the rationale she gives for each)

### 1.1 VWAP — no bands

> *"I have my VWAP. Okay. I do not have the bands of the VWAP. I find them useless. Uh they're not useless. They're just crowded. and statistical uh reference is not strong enough for me to go, hey, I'm going to use the upper and lower band. It's just not part of my uh setup personally."* (07:04–07:31)

- **Rule:** Plot VWAP only; do NOT plot upper/lower standard-deviation bands.
- **Rationale:** Bands are visually crowded and not statistically strong enough to support entries.
- **What VWAP gives her instead:** *"the VWAP, remember the VWAP is volume weighted average price. It measures whether the guys above are actually making money or if somebody went long, if they're actually losing money. And so it gives you the frame of the weight of the market."* (19:54–20:13)
- **Operational use:** VWAP is a **target/magnet** in her short setup ("the magnet towards the VWAP is going to come"). Slope of VWAP is also a **regime read**: *"look at the slope of this VWAP. It's telling us that everything's flattening out… we're going to chop"* (26:05–26:22).

### 1.2 50 SMA and 200 SMA — PERIOD, not DAY

This is one of the most important configuration clarifications in the whole session.

> *"you send me 50 and 200 day moving average. That was day or period for 30 minute period. They're period averages. Yeah, it's the 50 SMA, not the DMA. It's a 50 SMA and the 200 SMA."* (06:34–06:53)

- **Rule:** Both SMAs are PERIOD-based on whatever timeframe the chart is set to. On the 30-minute chart they are the 50- and 200-period 30-min SMA. On the 1-min chart they are the 50- and 200-period 1-min SMA.
- **Implication:** AM is reading a fractal stack of SMAs across timeframes, not one canonical SMA.

### 1.3 The 200 SMA is THE most statistically significant indicator

> *"the 200 moving average is the most highly… it's the most highly significant statistically speaking technical indicator. And my thought was well since the market is fractal I bet you I can use that on any time frame."* (18:49–19:14)

- **Rule:** The 200 SMA is the bias filter on EVERY timeframe she charts.
- **Operational consequence:** *"I literally only take trades in the direction of the 200 and the 50 when they're both going down."* (29:31–29:38)
- **Flat-200 special case:** *"And I know the math of a flat moving average. It tells me I have as much behavior underneath the line as above the line."* (30:05–30:13) → Flat 200 = chop, no edge.
- **"Far extension" mean-reversion exception:** *"Or I will scalp a trade that tells me, hey, you know, you're going to revert back to the 200 because you're very far away."* (29:44–29:55) → When price is dramatically far from a flat 200, she will scalp a counter-trend reversion AGAINST direction. The 200 itself is the target.

### 1.4 Woody's pivots with R3/R4/S4 expansion + custom banner

> *"I just have the pivots. The only thing that I have changed in the regular pivots, why it says clawed is because I have a banner up at the top and it tells me, hey, if you're above R2, R3, you're extended. And so you want to watch for exhaustion patterns that might show up."* (07:39–07:58)

- **Rule:** She uses **Woody's pivots** specifically — NOT classical floor pivots. Her chart says "Claude" because Claude generated the custom pivot indicator with the banner.
- **Banner output:** Auto-flags when price > R2 or > R3 → label = "extended" → behavioural cue is "watch for exhaustion."
- **Why Woody's:** *"the Woody's pivots will um give me one more line. it'll give me an S4."* (11:42–11:51) — she wants more pivot levels than the classical 3-up/3-down to catch dramatic extensions like today's short-covering rally.
- **R4/S4 use case:** When price is *"at the fourth pivot and my 200 is all the way down here, I know I'm very extended. I know it is a short covering rally."* (12:18–12:35)

### 1.5 The "one-minute intraday" custom indicator (shaded boxes)

This is the most-confusion-causing part of her email to Afshin and she clarifies it carefully here. The shaded boxes on her chart are NOT bars or sessions — they are a **single custom Think-or-Swim study** that draws color-coded boxes around five specific 30-min reference candles each day.

The five boxes (in time order):

| Box | Time (ET) | What it represents |
|---|---|---|
| Closing | 15:30–16:00 yesterday | Prior-day institutional flag-plant ("3:30 box") |
| GlobEx | 18:00–18:30 yesterday | Overnight-session open |
| Midnight | (midnight candle, 1-min) | NQ algorithm anomaly tracker — drawn but NOT shaded |
| Europe | 04:00–04:30 today | European cash open |
| RTH | 09:30–10:00 today | Opening range / institutional open |

> *"This is the closing box. This is the opening box. This is the opening um… This is Oh, this is the open of the Europe. That's 4:00 a.m. to 4:30. And then this is the GlobeEx Xbox."* (08:51–09:09)

> *"What is that called? What that It's called the one minute intraday."* (09:18–09:34)

> *"What we do, we have everything shaded. Looks nice. We go to the one minute opening candle. We let that candle complete. The system draws lines right around it."* (18:13–18:31)

- **Implementation note:** The "one minute intraday" name is misleading — Afshin himself misread it as "just bars" (09:34–09:41). It is an actual coded indicator. AM also uses a **Heikin-Ashi momentum indicator** ("hyenashi"/"hikenashi" in transcription) as a separate study (10:40–10:53; 27:02; 32:50–32:59).

### 1.6 Heikin-Ashi momentum indicator (auxiliary)

> *"and here is where the hikenashi can help you a little bit"* (27:02)
> *"I just got a green arrow showing my hyenashi is above uh zero again."* (32:50–32:59)

- **Use:** Confirms direction of momentum / polarity flip. Green arrow = momentum above zero (bullish flip).
- **Status:** Auxiliary, not primary — she mentions it once in passing as a tie-breaker.

### 1.7 The two timeframes — 30-min frame, 1-min execution

> *"I just use the 30 minute to frame everything out and then all my execution is on the one minute. Makes sense, right? And I don't go back and forth."* (11:13–11:27)

- **Rule:** Daily framework on 30-min. ALL execution on 1-min. She does NOT toggle.
- **Heuristic the spec doesn't capture:** *"set the framework just like this morning"* — meaning the framework decision is made ONCE at the open and held all day.

---

## 2. Filter / Permission Rules Tied to Chart Setup

### 2.1 Permission to enter long vs short — 200 SMA + 50 SMA stack

> *"what we're seeing is a very bullish day where dips are buys. Why? Because I'm above the 200 and I'm above the 50. But the size of the dip could be extraordinary."* (17:34–17:54)

> *"I literally only take trades in the direction of the 200 and the 50 when they're both going down."* (29:31–29:38)

- **Permission rule:**
  - Both SMAs sloping up AND price above both → **dips are buys**.
  - Both SMAs sloping down AND price below both → **bounces are sells**.
  - Both flat → no trend trade; only counter-trend revert-to-mean scalp permitted.

### 2.2 "Extended" gate — pivot R2/R3/R4 banner

> *"if you're above R2, R3, you're extended. And so you want to watch for exhaustion patterns"* (07:47)

> *"if I'm at the fourth pivot and my 200 is all the way down here, I know I'm very extended. I know it is a short covering rally."* (12:18)

- **Permission rule:** Above R2 → "extended" warning. Above R3 → "very extended." At R4 (with 200 SMA below price) → diagnose as **short-covering rally** → expect exhaustion.
- **Action:** Don't enter LONG fresh at R3/R4 even if everything else aligns; instead watch for exhaustion patterns to short.

### 2.3 The 4 AM candle as a permission level

> *"the question is, can I stay above the 4 a.m. low or do I stay above the 4 a.m. candle high? Above the high, my pullbacks or buy zones. Below the low, my bounces or sell zones."* (16:23–16:44)

- **Permission rule (very clean):**
  - Price above 4 AM **HIGH** → today's pullbacks ARE buy zones.
  - Price below 4 AM **LOW** → today's bounces ARE sell zones.
  - Price between 4 AM L and 4 AM H → no permission stated (implied: chop).

### 2.4 Cross-asset correlation permission (CL + DXY)

> *"because we've had the geopolitical unrest and the spike in oil, I've been looking at oil. It was very connected to the um indices and then it broke"* (02:10)

> *"any disconnection means that we stop using it intraday"* (04:30–04:39)

> *"As soon as you see it break and then resolve and break again it's useless."* (04:52)

> *"I'm using it as a temperature gauge for the market to see if we've got any aggressive correlations… It gives me strength of move. If the stronger the correlation is, the bigger the size I can take, if the setup looks right."* (05:44–06:12)

- **Permission rule:** When DXY/CL correlate strongly with ES → SIZE UP eligibility. When correlation breaks AND re-resolves AND breaks again → cross-asset signal is "useless" → ignore.
- **Status in V2_4:** Not encoded. The cross-asset gate is genuinely AM-specific and would need DXY + CL feeds.

### 2.5 Volume on the opening 1-min candle

> *"that first one minute candlestick carries more than 15,000 contracts on average. Sometimes it's much lighter than that. It tells me that the traders have a lack of conviction. This morning's 1 minute carried 23,000 contracts and it was directional straight down."* (31:05–31:23)

- **Permission rule (heuristic):** ES 9:30 1-min volume:
  - > 15k = baseline conviction.
  - > 20k AND directional = strong signal — fade the move on the retest.
  - < 15k = "lack of conviction" → reduce size or skip.

### 2.6 Opening-range size > 10 points → forced single-contract sizing

> *"If it's more than 10 points, you want to use one mees. You don't want to size up because 10 points could expand very dramatically."* (20:35–20:47)

- **Permission rule:** When the 1-min opening candle's range > 10 points, MES (or single-contract) only, NOT scaled in. The 10-point cap is an explicit numeric threshold.

---

## 3. Pivot Rules (R1–R4 / S1–S4)

### 3.1 Pivot system = Woody's

> *"I put up my Woody's pivot"* (17:21)

Woody's gives R1–R4 and S1–S4 (vs. classical floor's R1–R3/S1–S3).

### 3.2 The pivot itself (P) as the dividing line

> *"First things first, we come in and we go, where's the pivot? Pivot's way below me. So, it's very bullish, but it's extremely extended."* (16:58–17:13)

- **Rule:** First chart read is "where is price relative to P?" P is the bull/bear demarcation for the day.
- **"Pivot way below" + "200 way below" + "above R2/R3/R4" = short-covering rally diagnosis.**

### 3.3 R3/R4 = exhaustion zone

> *"if you're above R2, R3, you're extended. And so you want to watch for exhaustion patterns that might show up."* (07:47–07:58)

- **Rule:** R2 = warning. R3 = extended. R4 = exhaustion candidate.

### 3.4 S4 from Woody's specifically used for extreme extensions

> *"the Woody's pivots will um give me one more line. it'll give me an S4. And so when I did that, it came out and it gave me the highs, the potential highs of the day."* (11:51–12:12)

- **Rule:** AM uses S4/R4 (the Woody's-specific 4th pivot) as a **target/likely turn level** when price is dramatically extended past R3 (or below S3).

### 3.5 Round-number pivots — front-run risk

> *"what is also very likely is the big fat round number of 6,800, which happens to be a pivot."* (31:36–31:43)

> *"let's say I had my order to fill at 6811. They're front running that right now, right? So it could be that I get stopped out up here at 6824."* (32:22–32:38)

- **Heuristic rule (NOT in V2_4):** When a pivot **coincides with a round number** (e.g. 6800, 6900), expect **front-running** by other traders. Concrete example: she places limit at 6811 (just ahead of 6800), but front-runners can drive price up to her stop at 6824 before her fill executes.
- **Implication for an automated entry:** Pivot+round-number levels need a wider stop OR the entry should be moved to the breach-and-fail level rather than a pre-placed limit.

### 3.6 Pivot serves dual role — entry AND target

> *"go put a buy order at your pivot. You put a buy order at your pivot and then you'll see it moves further down."* (22:43–22:58)

- **Rule:** When you've taken profit on the first short and want to set up the next, leave a buy limit at the pivot. The pivot is BOTH a take-profit destination AND a re-engagement entry candidate.

---

## 4. Trade Setups Demonstrated

### 4.1 Setup A — Opening-Range Break-Down with Retest Short (TODAY's example)

**Context:** Market is in a short-covering rally (above R3/R4, 200 SMA way below, "very extended"). 9:30 1-min carried 23,000 contracts, directional straight down.

**Mechanics (verbatim 19:14–22:35):**
1. *"Opening candlestick formation. There it is. The goal is if it breaks below and it's under all of the moving averages, it's going to move into the next layer of support or the next moving average."* (19:21–19:33)
2. *"this opening candlestick on the one minute does something beautiful. If it is sitting underneath the 200 and the 50. Once it fails, you wait for the failed bounce and then you measure the range of that one minute open."* (20:13–20:35)
3. *"If it's more than 10 points, you want to use one mees. You don't want to size up… But you want to take it short on the retest into the opening range."* (20:35–20:47)
4. *"If these moving averages are above you, your stop is going to be just over the top of the one minute high."* (20:54–21:02)
5. First scale-in: 1 MES.
6. *"with the second move up here, you add to the position. Now you have 2 MEES, maybe 3MEES… Your stop is the same."* (21:37–21:50)
7. Target: *"the VWAP is the first target essentially. In this case, it could also be the edge of the 4:00 a.m. candle"* (21:56–22:12)
8. Hold logic: *"if you break this area and your trend is still down and you aren't above your 50, don't leave the trade. Just stay in there. Just let it work itself out."* (22:20–22:35)

**Component rules:**
- **Trigger:** 1-min opening candle (9:30–9:31) closes UNDER both 50 SMA and 200 SMA AND fails on the bounce back.
- **Entry:** SHORT on the **retest into the opening range** (price tries to re-enter the 9:30 candle's body and fails).
- **Stop:** Just over the 1-min 9:30 candle's HIGH.
- **Sizing:** If 9:30 1-min range > 10pt → 1 MES only on the first entry.
- **Add:** Add on second move up; same stop.
- **First target:** VWAP. Alt: edge of 4 AM candle (which was at 10:00 retest).
- **Stretch target:** Pivot. *"go up above my pivot. I think I'm going to go test that VWAP again"* (26:00).

### 4.2 Setup B — Second Trade / Re-engagement on Flat VWAP

**Context:** First short worked. Now traders want to know "now what?" The 30-min framework is flat (VWAP slope flattening, no new high in opening range, sideways grind).

**Mechanics (verbatim 27:02–28:36):**
1. *"if I get up over my 50 and I recover my pivot I'm going to walk right back up this 4 a.m. candlestick."* (27:08–27:18)
2. *"My 200 gives me a down to flat formation. My 50 gives me a down and then an up formation. So I have a crossurren here."* (27:56–28:02)
3. *"the trade that I would take would be the short. The exact same trade I took at the open."* (28:02–28:10)
4. *"because I expect the market to be sideways because my VWAP is flat. And so what I want to see is I want to see it move from here through the 4:00 a.m. candle and then through the rest of the 9:30."* (28:20–28:36)

**Component rules:**
- **Trigger:** Price has bounced back to a 50-SMA-recovered, VWAP-flat state, after the first short played out.
- **Entry:** Same as Setup A — short the retest, but now anchored at the 4 AM level instead of the 9:30 high.
- **Logic:** "Cross-current" (200 down-to-flat, 50 down-then-up) means choppy range → fade the bounce.
- **First target:** Walk down through 4 AM candle, then through 9:30 candle.

### 4.3 Setup C — Limit Order at Pivot for the "Third Entry"

> *"go put a buy order at your pivot."* (22:51)

**Mechanics:**
- After exiting Setup A or B, place a buy LIMIT at the day's pivot.
- The pivot doubles as a magnetic level — price often returns to it.
- This is for re-engaging long after price has stretched into S2/S3 area.
- Caveat: the front-running heuristic (§3.5) — limits at round-number-pivots can get filled poorly.

### 4.4 Setup D — Reversion-to-Mean Scalp (Counter-Trend)

> *"Or I will scalp a trade that tells me, hey, you know, you're going to revert back to the 200 because you're very far away."* (29:44–29:55)

> *"the far extensions I'm going to go backwards in time and go, okay, what am I staring at? If I come back here, I'm going to short it. So my alert will be on this particular line. It will be tell me when I hit 6827."* (30:13–30:29)

**Mechanics:**
- When price is "very far" from a flat 200 SMA, set an alert at a historic congestion level (here 6827).
- Take a **counter-trend** scalp on the assumption that price reverts to the 200.
- Target: the 200 SMA itself.
- This is the EXCEPTION to her "trade only in direction of the 200/50" rule.

### 4.5 Setup E — Yesterday's Mosh-Pit (Sideways Range Trade)

> *"my 30 minute candlestick for the close of the day and my 30 minute candlestick for the open of the day are right on top of each other. So, what everybody has said is let's fight about it."* (35:46–36:01)

**Mechanics:**
- When prior 3:30 candle and current 9:30 candle BODIES overlap → "they're going to fight about it" → sideways day.
- Wait for the break in either direction.
- Locate the 200 and 50 (which are below price → reversion likely).
- *"dips or buys, spikes or sells. All of this congestion tells me that whenever all the candlesticks are crowded like that or the shading is crowded, it tells me dips going to be buy zones, spikes going to be sell zones."* (39:11–39:30)
- Concrete trade she took: 6591 long. She admits she SIZED UP TOO FAST and was 20 points underwater before it worked. *"In hindsight, I should have waited for the close over the area and then the walk up the shading in the candle is what I should have done."* (41:00–41:22) → Self-correction: WAIT for the breakout candle to CLOSE before entering, and use the candle-shading as a step-up confirmation.

---

## 5. Level Priorities and Interactions

### 5.1 Level priority hierarchy (implicit from her workflow)

1. **Pivot (P)** — first thing she identifies in the morning.
2. **30-min closing-flag candle (Prior 3:30) AND 30-min opening candle (today's 9:30).** When these stack, day-type is set.
3. **200 SMA (period-based on whatever timeframe).** Bias filter.
4. **50 SMA.** Secondary filter / risk gauge.
5. **VWAP.** Magnet target.
6. **4 AM candle high/low.** Permission line.
7. **GlobEx 6 PM candle.** Used as a checkpoint; she watches if price holds above/below GlobEx high.
8. **Midnight candle.** Mentioned as an algorithmic-anomaly tracker (especially NQ); not shaded but tracked.
9. **R1/R2/R3/R4/S1/S2/S3/S4** (Woody's). Extension/exhaustion markers.
10. **Round numbers (6800, 6900).** Front-run hot-spots.
11. **Heavy congestion levels from prior days (e.g., 5200 cross).** Mean-reversion targets when current structure fails. *"I look for heavy congestion to the past. I look to see where they began to build inventory to the upside and it's right here at this 5200 cross. Literally, that price point is what they bounce from."* (33:32–33:48)

### 5.2 Level interactions she calls out

- **Pivot below + 200 below + above R3/R4 → short-covering rally diagnosis** (12:18).
- **9:30 candle stops at "the same place it stopped at the open" later in the day** (27:34–27:42) → today's 9:30 high becomes the day's reference resistance, even after price retraces.
- **GlobEx high = first failure level** when the day breaks above it but can't hold (39:39 area).
- **Box cluster → permission to fade range** *"the question is which dip? Which spike? And that's what you want to see when they break up above that GlobEx high, but they can't hold it. You know, they're going to walk down the boxes."* (39:30–39:49)
- **Box-walk order on a sideways day:** First box down = 3:30 box (also bottom of GlobEx box). Next = 4 AM box. Next = 9:30 box. (39:49–40:12)

### 5.3 The fractal SMA stack

> *"This rotates all the way down in the same measure as this one minute opening. It comes all the way in. You could see them dancing around the levels. It's pretty incredible."* (23:25–23:41)

- **Rule:** Trade structure is fractal — the 1-min opening setup mirrors the 6-min opening setup. SMAs and pivots interact at every timeframe. This is her stated reason for putting the 200-SMA on the 1-min chart (it works because the math is fractal).

---

## 6. Heuristics Mentioned in Passing (Easy-to-Miss)

These are micro-rules embedded in her narration that aren't formal rules but shape her decisions:

1. **"Set the framework once, don't go back and forth."** *"I set the framework just like this morning… I don't go back and forth."* (11:27)

2. **"Only one setup, two-three trades a day max."** *"Only one setup for me, two, three trades a day max."* (32:13–32:20) — This conflicts with the V2_4 spec's "no hard cap" framing. AM's behavioural truth is a soft 2–3 daily cap.

3. **"Everything else, it's nowhere near the volume."** (15:00–15:07) — Justifies why she only watches 3:30 PM, GlobEx 6 PM, 4 AM, 9:30. Volume gates her attention.

4. **"Newer algorithms are using this midnight candle, particularly in the NQ, to do all kinds of very weird things."** (15:30–15:46) — Watch midnight candle anomalies on NQ specifically.

5. **"Europe 4 AM matters because it's the European cash open. Highs and lows mean a lot."** (15:56–16:14)

6. **"Two points out of that as opposed to zero — bring my stop in."** (29:10–29:28) — When trapped between SMAs and a key level isn't breaking, tighten the stop to lock in something rather than holding for a full target.

7. **"Get up and leave your stop at break even and go leave the room and go put a buy order at your pivot."** (22:43–22:58) — Behavioural rule: physically leave the screen to avoid over-managing the trade.

8. **"Don't bandy about in the charts and do stupid things."** (32:00–32:07) — Self-restraint discipline.

9. **"I might go back and say, you know, if the moving average is really flat in these kinds of spaces, maybe I don't expect it to come all the way and I look for heavy congestion to the past."** (33:22–33:32) — Adaptive target rule: when 200 is flat, don't expect VWAP retest; look at historic congestion instead.

10. **"News candle gives us this Fibonacci."** (24:50–25:01) — On a news event, she draws a Fibonacci off the news-candle range. Specific Fib levels are not enumerated in this transcript but the practice IS mentioned.

11. **"Width the news candle out."** (25:06) — Either widen the box around the news candle OR widen the stop when trading near it. Phrasing is unclear; safest read is "treat the news candle as an enlarged risk zone."

12. **"Cross-current."** (28:02) — Her term for a 200-down-to-flat + 50-down-then-up configuration. Diagnostic tag for rangebound chop.

13. **"Use alerts because attention span is the bottleneck."** (45:28–45:48) — Implementation guidance for the indicator: alerts > continuous staring.

---

## 7. Notable Quotes (verbatim, copy-paste-ready)

- *"I do not have the bands of the VWAP. I find them useless."* — 07:09
- *"It's a 50 SMA and the 200 SMA."* (period, not day) — 06:53
- *"if you're above R2, R3, you're extended. And so you want to watch for exhaustion patterns that might show up."* — 07:47
- *"the Woody's pivots will um give me one more line. it'll give me an S4."* — 11:51
- *"Above the high, my pullbacks or buy zones. Below the low, my bounces or sell zones."* (4 AM candle) — 16:30
- *"the 200 moving average is the most highly significant statistically speaking technical indicator… since the market is fractal I bet you I can use that on any time frame."* — 18:49–19:14
- *"If it's more than 10 points, you want to use one mees."* (opening range) — 20:35
- *"the magnet towards the VWAP is going to come"* — 21:28
- *"go put a buy order at your pivot."* — 22:51
- *"my 4 hour is here. My 4 a.m. is here. My 9:30 is here in this great big box. What am I likely to do? Retrace the 4 hour. Retrace to the midnight candle."* — 25:15–25:30
- *"I literally only take trades in the direction of the 200 and the 50 when they're both going down."* — 29:31
- *"I will scalp a trade that tells me, hey, you know, you're going to revert back to the 200 because you're very far away."* — 29:44
- *"that first one minute candlestick carries more than 15,000 contracts on average… This morning's 1 minute carried 23,000 contracts and it was directional straight down."* — 31:05
- *"the big fat round number of 6,800, which happens to be a pivot."* — 31:36
- *"They're front running that right now"* (limits at round-number pivots) — 32:28
- *"Only one setup for me, two, three trades a day max."* — 32:13
- *"Dips or buys, spikes or sells. All of this congestion tells me… dips going to be buy zones, spikes going to be sell zones."* — 39:11
- *"in hindsight, I should have waited for the close over the area and then the walk up the shading in the candle is what I should have done."* — 41:07 (her own self-critique on yesterday's 6591 trade)

---

## 8. Setups Potentially MISSING from V2_4

Cross-referenced against `AM_rules_v2_spec.md`:

| # | Item | Status in V2_4 spec | Risk |
|---|---|---|---|
| 1 | **Woody's pivots (R1–R4, S1–S4) as a level set** | Not present. Spec §9 lists master candles, prior days, news-candle wicks — no pivots. | HIGH — pivots are AM's PRIMARY level read ("First things first… where's the pivot?"). |
| 2 | **R2/R3/R4 "extended → exhaustion" banner** | Not present. | HIGH — it's an explicit no-fresh-long permission gate. |
| 3 | **Round-number-pivot front-run heuristic** | Not present. | MEDIUM — affects fill quality; explains why pre-placed limits at major levels (6800/6900) underperform. |
| 4 | **10-point opening-range size cap → 1 MES forced** | Not present. Spec §1 has large-wick risk modifier and §2 has MOC sizing, but no opening-range-WIDTH cap. | MEDIUM — concrete numeric rule that's missable in code. |
| 5 | **15k / 23k contract volume thresholds for 9:30 1-min** | Not present (spec §2 uses 3:30/3:00 ratio for MOC). | MEDIUM — this is a different volume gate at a different time. |
| 6 | **Reversion-to-mean scalp when price is far from a flat 200** | Not present. Spec §3 says "flat → no trade default." | MEDIUM — this is an explicit exception AM herself takes. |
| 7 | **Cross-asset DXY + CL "temperature gauge" for size-up** | Not present. | LOW–MEDIUM — needs new feeds; size impact rather than entry impact. |
| 8 | **Period-basis 50/200 SMA on 1-min chart (fractal stack)** | Spec §3 implies 30-min basis only. AM applies same SMAs at 1-min. | MEDIUM — execution timeframe filter is missing. |
| 9 | **The "one-minute intraday" study as a single artifact** | Spec §9 lists candles individually. AM treats them as a configured study with five named boxes. | LOW (cosmetic) — but the named-box framework helps debugging. |
| 10 | **Heikin-Ashi momentum confirmation** | Not present. | LOW — auxiliary indicator. |
| 11 | **"Cross-current" tag (200 down→flat, 50 down→up)** | Not present. | LOW — but it's her term for a regime that already maps to half-size. |
| 12 | **Box-walk order on sideways days (3:30 → GlobEx → 4 AM → 9:30)** | Spec §7 has range edges (prior 3:30, prior 9:30) but not the SEQUENTIAL walk-down order AM uses. | MEDIUM — affects target ordering on fades. |
| 13 | **Setup A — opening-range break + RETEST entry** | Spec §4 Pattern A is "break of 9:30 high/low with 5-tick buffer." AM here describes a **retest after failure** entry — a stricter, second-touch version. The two are subtly different. | MEDIUM — may explain why valid trades feel "missed" (V2_4 fires on the break; AM waits for the retest). |
| 14 | **Setup B / second-trade re-engagement at 4 AM after first short** | Spec §4.B (breach-and-fail) covers single-shot setups; the SECOND TRADE on flat VWAP at the 4 AM candle is not explicitly modeled. | MEDIUM — Afshin's "missed setups" pain point likely includes second-trades. |
| 15 | **News-candle Fibonacci anchoring** | Spec §6 has Fibonacci off the entry candle. The news-candle Fib (24:50–25:01) is a separate construct AM uses for confluence targeting. | LOW–MEDIUM. |
| 16 | **Behavioural cap — "two-three trades a day max"** | Spec §8 says "process-based, no hard cap, MaxSignalsPerDay default 5." AM's stated practice is 2–3. | LOW — guardrail, not edge. |
| 17 | **Heavy-congestion historic-price levels** ("the 5200 cross") | Spec §9 lists prior days' 30-min H/L but not multi-day congestion centroids. | MEDIUM — these are AM's adaptive-target fallback when SMAs are flat. |

### Direct read on Afshin's "missed setups" pain point

The most likely culprits, ordered by impact:

1. **(#13)** V2_4 fires on the 9:30 BREAK; AM enters on the RETEST after failure. The retest is often 2–10 minutes after the break, and the V2_4 alert may have already gone stale.
2. **(#1, #2)** Pivots are missing entirely. AM uses pivots as a level set AND a permission gate AND a target. Trades originating at R1/R2/S1/S2 levels are invisible to V2_4.
3. **(#14)** Second-entry re-engagement on flat VWAP at the 4 AM level is a daily occurrence on chop days; if V2_4 only flags the first setup, the second trade looks "missed."
4. **(#6)** Mean-reversion scalps on far-extension flat-200 days are AM-positive but V2_4-prohibited (§3 says "flat → no trade").
5. **(#4)** When the 9:30 opens > 10pt range, V2_4 may still suggest size-up; AM forces 1 MES.

---

## Cross-reference notes for Wave 3

- **Confirms / strengthens existing spec items:**
  - §3 (200 SMA primacy): apr-8 is the canonical "200 = most statistically significant" quote source.
  - §4 entry mechanics: today's setup A demonstrates "fail and retest" — supports the breach-and-fail Pattern B framing, and gives a second concrete example beyond apr-24's screenshot 4 (today's setup uses 1-min 9:30 high as the breach reference rather than a clean horizontal level).
  - §7 sideways: yesterday's mosh-pit is a clean instance of body-overlap → sideways → "dips are buys, spikes are sells" → which slope-direction selects (today the 200 was up, so dips were the trade).
  - §9 level set: 4 AM candle permission rules (16:30) are reinforced; news-candle Fib anchoring (24:50) supports §9 news-candle wick treatment.

- **Contradicts existing spec items:**
  - §8 daily count: spec says "no hard cap, default 5"; AM here says "two, three trades a day max." Recommend lowering MaxSignalsPerDay to 3 for V2_4 MVP.
  - §3 flat-200 case: spec defaults to "no trade"; AM here describes a reversion-to-mean scalp at far extensions. Add this as a Tier 3 conditional exception.
  - §4 Pattern A: spec says break of 9:30 + 5-tick buffer; apr-8 example is RETEST after failure (a stricter, later trigger). Need to reconcile — likely both fire on different days. Recommend Pattern A1 (break) and A2 (break + retest) and let ML pick.

- **New items to add to spec (HIGH priority):**
  - Woody's pivots (R1–R4, S1–S4) as a first-class level set with the R2/R3 extended banner.
  - Round-number-pivot front-run heuristic (avoid limit orders directly at round-number pivots; use market or breach-and-fail entries).
  - 10-point opening-range size cap (forced 1 MES when 9:30 1-min range > 10pt).
  - 9:30 1-min volume thresholds (15k baseline, 20k+ directional, <15k skip-or-reduce).
  - Period-basis 50/200 SMA on 1-min execution timeframe (the fractal stack — currently spec's SMA references read as 30-min only).

- **New items to add to spec (MEDIUM priority):**
  - Cross-asset DXY + CL correlation gauge for size-up eligibility.
  - Box-walk target order on sideways days (3:30 → GlobEx → 4 AM → 9:30).
  - "Cross-current" regime tag (200 down→flat + 50 down→up).
  - Second-trade re-engagement at 4 AM candle after first short on flat VWAP.

- **New items to add to spec (LOW priority):**
  - Heikin-Ashi momentum confirmation as auxiliary tie-breaker.
  - Behavioural-rule layer (leave the desk, alerts not staring, "don't bandy about").
  - Historic congestion levels (e.g., "5200 cross") as adaptive targets when 200 is flat.

- **Beginner-friendly indicator notes (Afshin end-goal A):**
  - The "extended → exhaustion" banner is a HIGH-VALUE beginner-facing element. It tells a beginner DON'T enter long here even if everything else looks good.
  - The 4 AM permission line ("above high → buys; below low → sells") is the cleanest one-line decision rule in the entire transcript and should be a top-of-screen permission badge in V2_4.
  - The "10-point cap → 1 MES" rule is a simple beginner risk-control that can be displayed as a forced-size override.

- **ML stack notes (Afshin end-goal B):**
  - Add features: distance-to-Woody's-pivots (P, R1–R4, S1–S4), round-number proximity (price modulo 100), 9:30 1-min volume, DXY-ES correlation rolling window, CL-ES correlation rolling window.
  - Add target variants: realized R for "entry on retest" vs "entry on break" — let the model learn which trigger has better R.
  - Add regime tags: short-covering rally (price > R3 + 200 below), cross-current (200 flat + 50 oscillating), mosh-pit (prior 3:30 + today 9:30 body-overlap).

- **AM-escalation candidates (high-impact ambiguities only):**
  - Q: When the 9:30 1-min opening range > 10 points, do you ALWAYS take only 1 MES, or do you also size down on the second add (which spec currently says is same-stop, multi-contract)?
  - Q: For Pattern A entry — do you enter on the BREAK of 9:30 (V2_4 current), or on the RETEST after a failed bounce (apr-8 example)? Or both, depending on volume?
  - Q: On the round-number-pivot front-run risk — do you have a numerical "stay X points away from round number" rule, or is it pure judgment?
