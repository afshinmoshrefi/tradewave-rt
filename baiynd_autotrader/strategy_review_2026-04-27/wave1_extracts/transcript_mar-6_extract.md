# AM Transcript Extract — mar-6 (Genesis Session)

**Source:** `C:\seasonals\baiynd_autotrader\video transcripts\AM_transcript_mar-6.txt`
**Wave:** 1, Wave1 Extracts
**Compiled:** 2026-04-27
**Method:** Ground-truth read of full transcript; no synthesis from the AM_*.md files in the same folder.

---

## TL;DR

This is the GENESIS recording — AM walking Afshin through her live methodology for the first time. The transcript is a two-act demonstration: (1) ~43:00–1:02:00, post-earnings-drift / earnings-candle method for equities; (2) ~1:02:00–1:42:00, the intraday futures method that pays her bills. The intraday system is built around four "special-time" candles — the 30-minute RTH open (9:30), the 4 a.m. Europe candle, the prior 1:30 PM candle, and the prior 3:30 PM candle — plus a consistent "look above/below and fail" reversal pattern, "measured-move" box duplication for targets, and pivot points as the day's anchor for direction (above pivot = long bias, below = short bias). She trades ES, NQ, CL, RTY (no YM), 2–3 contracts max. AM acknowledges the system runs primarily off candle TIME, not volume; she explicitly downplays moving-average and momentum complexity. Several specific elements are under-represented or absent in the v2 spec — notably the **1:30 PM prior-day candle as a primary level**, the **measured-move box duplication for targets** (not just Fib extensions), the **t-minus-3-day inventory framing**, the **"shake the trees" pre-entry interpretation**, the **bigger-time-frame substitution rule when 4 AM wicks are too wide**, and the **5-minute-fallback scalp** for late entries. The earnings/post-earnings-drift framework is also wholly outside V2_4's scope and may explain a class of "missed trades" if Afshin is conflating the two modes.

---

## 1. SETUPS (Entries) — explicit list

AM describes several distinct setups across two domains. I'll number them in the order she presents.

### 1.1 SETUP — Sideways Earnings Box, fall-out short (equities, daily)
**Where:** ~46:01–46:39 (start of earnings discussion)
**Pattern:** Chart sits sideways for two-three quarters. Earnings comes; within day three the price breaks out of the prior earnings candle range.
**Trigger:** Falls out below the bottom of the box.
**Entry:** Two options — (a) take it on the break, (b) wait for a retest of the broken level then enter on rejection.
**Stop:** Top of the earnings candle (always — for a short).
**Target:** Bottom of the prior support / next prior earnings candle.
**Verbatim:** *"When a chart is sideways like this and it falls out of its earnings candle within the third day, the trade is short into support if it falls down below."* (~46:08–46:24)
**Verbatim sizing implication:** *"If it's sideways, it's going to move sideways. Meaning, if it falls out from one earnings event, it's going to collapse into a prior earnings event. Or if it's sideways and it pops out, it's going to move to a prior earnings event and then come back in."* (~46:49–47:12)

### 1.2 SETUP — Earnings Box, breakout long with measured move (equities, daily)
**Where:** ~47:18–48:42
**Pattern:** Earnings candle opens up OUTSIDE the prior box.
**Wait:** Two days. On day 3, if price has stayed outside, take long.
**Targeting via measured move:** Use a Fibonacci or measured move of the prior congestion range. *"It's going to go the range of congestion. So I'm going to go from 100 to 200."* (~48:13)
**Drift duration:** 5–7 days. *"because the drift is usually five to seven days before it begins to fade."*
**Note (refinement at ~49:33–50:34):** A simpler/preferred entry skips the wait — enter on day 1 outside the box. *"Why not jump in the day after earnings when it's already outside of the box? And they have a point. So as long as it's outside of the box, the stop is the bottom of the candlestick."*
**Verbatim trade-management:** *"I will stay in the trade or add to the trade or whatever it is after that post earning script. And that's what I'll do into every single one of them. And I will go until I break trend. And so the way that I break trend is I don't break the prior weekly lows."* (~51:09–51:44)

### 1.3 SETUP — Intraday: 30-min open break + higher-low long (futures, intraday)
**Where:** ~1:07:01–1:07:43 (after introducing the special-time candles)
**Trigger:** Price breaks above the first 30-minute (9:30 ET) candle's high AND has been making higher lows.
**Entry direction:** Long, into the pivot.
**Exit:** Cut off ~34 ticks below the pivot (~13 points / $40 in NQ context — she said "13 points" but used "ticks" loosely; the exact mapping is fuzzy).
**Verbatim:** *"if it breaks out above the first 30 minute open and I've made higher lows, I will take the long up into the pivot and I will get out. So I will take the long from 34 68 34 2. I'll normally cut it off 34 ticks below."* (~1:07:01–1:07:30)
**Re-entry rule:** If price comes back to the pivot and the pivot holds the 30-min high, buy again — wash, rinse, repeat.
**Don't-chase rule:** *"if you miss it, don't chase it. Just wait for the next setup."* (~1:09:21)

### 1.4 SETUP — Midnight-candle failure → look-below-and-fail short
**Where:** ~1:09:29–1:10:37
**Pattern:** The MIDNIGHT candle does NOT break the prior pre-market highs.
**Trigger:** Price fails the LOW of the midnight candle.
**Direction:** Short.
**Target:** Back to the opening 30-min candle.
**Reflexive recovery:** If you get stopped out (price breaks up first then collapses), re-enter on the second look-below.
**Verbatim:** *"if the midnight candle does not break the prior um pre-market highs, then the first thing I have to look for is the failure of the low of the midnight candle and then I can take the short where back to the opening candlestick formation."* (~1:09:29–1:09:52)
**This is one of two named patterns AM coins:** "look below and go" — see §1.5.

### 1.5 SETUP — "Look below / look above and go" (the named pattern)
**Where:** ~1:10:12–1:10:30 (named); recurs throughout
**Mechanical definition (verbatim):** *"I go in again. I go here's my look below and go. That's what I call it where it looks below. If it looks below and it bounces but does not clear the candlestick of measure, it is a short as soon as it loses the low of the candle."*
**Translated:** Price wicks below a key candle's low (the "candle of measure"), then bounces but cannot reclaim the body — once price loses the low again, that's the short.
**The mirror "look above and go":** ~1:18:46–1:19:00 — *"if it breaks out and it pulls back and cannot get inside of the candlesticks, it is going to head in the direction of the break."* This is the long version.
**Pre-place implication:** *"if you see the pattern forming, you can have your order waiting out there in that space."* (~1:10:37)
**This is the canonical "Pattern B" in the v2 spec; the spec's 1-bar definition is a tighter mechanical reading than AM's verbal version, which spans multiple bars.**

### 1.6 SETUP — 4 AM into 3:30 prior-day = bounce zone (long)
**Where:** ~1:11:18–1:14:25
**Pattern:** When the 4 a.m. candle's low equals the prior day's 3:30 PM candle's bottom, THAT region is where institutional buyers have telegraphed support — and "they shake the trees" first.
**The shake:** The market gaps down through it to flush longs, then reverses up to a *specific* candle: the **1:30 PM (1:30) candle** — by **only a few minutes**, "every day."
**Verbatim:** *"Look at where they choose to turn around and go long. It's the 130 candle. Every day, Asheen. Every day. By a couple of minutes. Doesn't even matter what's going on."* (~1:12:09–1:12:35)
**Trade arithmetic example:** Entry off 1:30 candle bounce, *"my stop is halfway up that candlestick. So you've got six points of risk for 30 points of reward."* (~1:13:38–1:13:56) — i.e., 5:1 R/R when the setup forms.
**If price loses the 1:30 candle's low afterward:** target becomes the BOTTOM of the 1:30 candle — that level is "the next stop" to the prior 9:30 candle. (~1:14:03–1:14:48)

### 1.7 SETUP — Sideways-pattern revisitation: 10:00 candle low echo
**Where:** ~1:16:34–1:17:05
**Pattern:** When the chart is in a sideways pattern, the 10:00 (10:00–10:30) candle's low/high gets revisited later in the day. AM points at how today's low matched the 10:30 low EXACTLY.
**Verbatim:** *"Take a look at this 10:30 low. This is the 10:00 candle. 10 to 10:30. Look at the low and our low today."*
**Implication:** On sideways days, the 10:00 candle is a level. NOT explicitly listed in V2_4's level set as a primary tracker.

### 1.8 SETUP — Trend-break confirmation breakout (sideways → uptrend)
**Where:** ~1:17:30–1:19:40
**Pattern:** Day starts sideways; 4 AM candle is initially resistance, then breaks through it.
**Trigger options:** (a) Buy-stop above the 9:30–10:00 high (stop wide, exit if price falls back inside). (b) Wait for "look above and go" — break, pullback, fail to re-enter the candle, then long.
**Targeting:** Measure the box of the 9:30+10:00 candles, then *"walk it up by the 50s and the 200s."* — meaning use the 50% and 200% Fibonacci extensions as ladders.
**Verbatim:** *"I am going to walk it up by the 50s and the 200s. Look at how look at where resistance hits right at the 300. Look at where it retests right at the 250. It is just a clockwork event."* (~1:19:20–1:19:38)

### 1.9 SETUP — 4 AM box duplication for measured-move targets (the headline pattern)
**Where:** ~1:22:52–1:25:20 (most explicit demonstration of the day)
**Pattern:** Take the 4 AM candle as a "box" (height = high–low). Duplicate it stacked above (for longs) or below (for shorts) — each copy gives the next target zone.
**Verbatim:** *"The 4 a.m. candlestick, if I duplicate it, it gives me a measured move event. And that measured move tells me my next target. Almost every day, almost every single day, that measured move will give me my target."* (~1:22:36–1:22:52)
**Floor/ceiling logic:** Each duplicate is held as floor/ceiling by price action — "Holds it as a floor. I'm going to replicate again." (~1:23:48–1:24:06)
**Why it works (her interpretation):** *"how rhythmic the price pattern is. And it is absolutely because of algorithmic trading over and over and over again."* (~1:24:29–1:24:50)
**This is a target-defining technique that goes beyond V2_4's "100% then candle-walk" — AM treats the 4 AM box as a unit-of-measure for ladders.** The v2 spec's Fib extensions are conceptually similar but anchored to the entry candle, not the 4 AM candle.

### 1.10 SETUP — 5-minute scalp fallback for late entries
**Where:** ~1:31:40–1:32:12
**Pattern:** When AM has had meetings all day and price is far from her preferred entry on the 30-min, she drops to the 5-min and works the last 30 minutes.
**Verbatim:** *"Some days I come in and I will be very far from where I want to buy. Like maybe I want to buy here, but I've had meetings all day and price action is now here. I'll go to that 5 minute and I'll say, 'All right, can I trade the last 30 minutes for, you know, 20 points or whatever in order to get it?'"*
**Note:** This is presented as a normal (not exceptional) part of her day — V2_4 should consider whether it gates trades only on 1-min, since AM uses the 30-min as primary and 5-min as fallback.

---

## 2. PERMISSIONS / FILTERS — what she requires before taking a trade

### 2.1 Pivot-point above/below regime filter
*"if I'm above my anchored pivot, the pivot that comes in from the measurement that they calculate for the day. … If I'm above it, then I know that I'm okay. … If I'm below it, I'm going to have to think about short or short into support if I'm moving sideways."* (~1:41:00–1:41:49)
**Interpretation:** Daily pivot above = long bias permitted; below = short bias / sideways-short permitted. NOT in V2_4 spec as a gate — V2 spec uses 200 SMA slope; AM here uses the *floor pivot point*.

### 2.2 Trend bias from prior 3-day inventory
*"every day you have to reorient yourself in terms of saying, okay, what is the pattern of the last three days done? I'm always looking at t minus 3. So I'm going to look at all right, let's see what the last three days have been. If they're sitting in a box, I know they're building inventory. And if they're going to build inventory, then they're either going to distribute at a discount or distribute at a premium."* (~1:41:58–1:42:25)
**Interpretation:** A 3-day box = inventory accumulation; expect distribution either upside or downside, with measured-move ladders as the path. V2_4's lookback is "up to 3 days" for sideways edges — but AM's framing here is broader (inventory cycle, not just edges).

### 2.3 Strength-of-motion check before entry
*"as if it's holding that 1/3 candle and I've got all of these candle prints inside of it, what I'm going to look for is the strength of motion that puts me outside of that candle formation."* (~1:20:14)
**Interpretation:** Before pulling the trigger she watches for momentum out of the consolidation candle. Ambiguous mechanically — likely she means a clean body close beyond the candle's range.

### 2.4 Time-and-sales tape confirmation
*"First thing I'll do is I will look for I'll have time and sales sitting on one of my other machines on another platform. I look for time and sales and I watch to see what happens at this price point. If this price point holds, I'm going to take the long here."* (~1:21:48–1:22:11)
**Interpretation:** AM uses tape (T&S) as a final confirmation at her entry level. **This is NOT in V2_4 spec at all.** It would manifest as "did volume/aggression appear at level X?" — possibly a volume-spike check or imbalance check.

### 2.5 Trend bias from candle-formation higher-lows / lower-highs
*"You want to make sure that your candlesticks of note are always creating either higher lows further up [for long]"* (~1:30:34–1:30:43) and the inverse for shorts.
**Interpretation:** Multi-bar confirmation that trend is intact before adding/holding.

### 2.6 Don't-buy filter — chart that fails to clear an early candle
*"This formation right here where it does nothing for 1 2 3 4 5 hours until that 130 candlestick and then it immediately loses it. The fact that it can't get up above this 10 a.m. candle, it says don't buy this chart unless you're scalping it on a five minute."* (~1:31:00–1:31:23)
**Interpretation:** If price chops below the 10 AM candle's high all morning and then breaks down at 1:30, do not trade long; reduce to scalping mode if anything.

### 2.7 Algorithm-shift check (volatility regime)
*"the rhythm had shifted just slightly. And so instead of um instead of the 4hour candlestick today, what I drew was the range of the 9:30 to 10:30 candlestick formation."* (~1:27:51–1:28:18)
**Interpretation:** When 4 AM wicks are too wide to use as the framing box, SUBSTITUTE in the 9:30–10:30 range as the measured-move box. **This regime substitution is not codified in V2_4.**
*"the wicks would have thrown us out of this trade. We would not have been able to hang on with 70 points of risk. That's just absurd."* (~1:29:06–1:29:21)

---

## 3. EXIT RULES

### 3.1 Take-profit at the pivot (intraday)
Long entries off the 30-min open break → exit at the daily pivot. Then re-enter on retests.

### 3.2 Walk targets via measured-move box duplication
Discussed in 1.9. Each duplicate of the 4 AM box (or substitute box) above/below is the next target. AM uses these as the literal price levels.

### 3.3 Trail to previous swing
*"how do you stay in that trend? You want to make sure that your candlesticks of note are always creating either higher lows further up or see like this one right here. As soon as it starts breaking in this space, it's it tells you get out of the trade."* (~1:30:30–1:31:00)
**Interpretation:** Candle-formation trailing exit — get out when higher-lows fail.

### 3.4 Earnings exit (daily)
*"I will go until I break trend. And so the way that I break trend is I don't break the prior weekly lows. As long as the prior weekly lows hold, I'm going to stay in trend."* (~51:30–51:44)

### 3.5 Stop placement — entry-trigger-candle range
*"my stop would be 19. My entry point would be 24. So I got five points of risk, but my goal is to get to the top of the 4hour candlestick, which gives me almost 40 points of upside."* (~1:22:11–1:22:33) — 5pts risk for 40pts reward (8:1 R).

### 3.6 Stop placement — half-candle when adding
Implicit but not explicit on mar-6; clearer in apr-24.

### 3.7 Stop on the EARNINGS candle
*"the the stop is always at the top of the candle if you're going short."* (~46:32) — unambiguous rule for the earnings setups.

---

## 4. LEVEL DEFINITIONS & PRIORITIES (mar-6 reading)

In order of importance as AM presents them:

| # | Level | Source/time |
|---|---|---|
| 1 | **Daily floor pivot point** | Anchor for direction (above pivot = long; below = short). |
| 2 | **30-min RTH open** (9:30–10:00 candle H/L) | First level she draws every day. |
| 3 | **4 AM Europe candle** (4:00–4:30 H/L) | "Super important." |
| 4 | **Prior 3:30 PM candle** | "Last 30 minutes of the day. Huge influx of momentum and trend." |
| 5 | **Prior 1:30 PM candle** | "Every day, Asheen. Every day. By a couple of minutes." Distinct from 3:30. |
| 6 | **10:00 (10:00–10:30) candle** | Outside-engulf check at 10:00; revisited as level on sideways days. |
| 7 | **Midnight candle** | For the look-below-and-go failure pattern. |
| 8 | **Prior-day pre-market highs** | Reference for whether midnight broke them. |
| 9 | **Prior-day 4 AM** | Sometimes acts as the day's high or low — *"the 4 a.m. low from yesterday was the high"* today. (~1:08:33) |
| 10 | **Prior-2-day or prior-3-day 4 AM** | *"4 a.m. candlestick from what? One, two, 3 days ago. It's bananas."* (~1:29:41) |
| 11 | **Pivot points (S1, R1, etc.)** | "Holding the pivot point." (~56:06) — used as scaling targets. |

**The 1:30 PM candle is striking.** It is mentioned multiple times as the key turn-around level, distinct from the 3:30 PM institutional candle. V2_4's spec includes the 3:30 candle as the "institutional candle" but does NOT call out 1:30 separately — this may be a missing level.

**Multi-day 4 AM candles (1, 2, 3 days back).** AM tracks these visually and they trap support/resistance. V2_4 should consider tracking these as a recent-history set.

---

## 5. SIZING NOTES

### 5.1 Always small
*"I do not my days of swinging big are well past me… I always trade small. I don't ever have more than two or three ES on at a time."* (~1:33:51–1:33:57)
**Implication:** Position cap = 2–3 ES contracts. Same for similar scale on NQ/CL/RTY.

### 5.2 Trend-vs-counter-trend size discrimination
*"The size that you take of the trade depends on whether your trend or counter trend. So because I have a 30inut chart that is going straight up like this, I can only take small size on the short until it breaks pattern."* (~1:10:50–1:11:12)
**Implication:** Counter-trend trades = reduced size, even if the look-above/below setup fires cleanly.

### 5.3 Liquidity / DOM / bid-ask check
*"if you've got 30 ticks between your bid and your ask … you want to make sure it's liquid enough. You don't want your candlesticks to be gappy."* (~1:35:02–1:35:32)
**Implication:** Skip thin/illiquid contracts (her example: silver). **Not in V2_4 spec.**

---

## 6. TIMING CONSTRAINTS

### 6.1 Special candles (in chronological order)
- 4 a.m. ET (Europe open).
- 9:30 ET (RTH open) — first 30-min candle.
- 10:00 ET — 10:00–10:30 candle, watched for outside-engulfing of the 9:30.
- 1:30 PM ET — institutional turn-around candle.
- 3:30 PM ET — closing institutional candle.
- Midnight ET — globex midnight candle.

### 6.2 Outside-engulfing rule at 10:00
*"The 9:30 to 10:00 low and high. I'm going to look at that. The 10:00 candlestick. If it's an outside candlestick, meaning it completely engulfs the 9:30, I'm going to draw a line at the bottom of it."* (~1:06:16–1:06:32)
**Interpretation:** When the 10:00 candle engulfs the 9:30, the 10:00 candle's bottom (or top) becomes the level, not the 9:30's. **Not explicit in V2_4 spec.**

### 6.3 Crude-oil close-time difference
*"oil is already closed. Oil closes on this candle, that 2:30, right?"* (~1:35:48–1:36:00)
**Implication:** For CL the equivalent of the 3:30 institutional candle is the 2:00–2:30 PM candle (because CL closes at 2:30 ET). V2_4 has TABLED CL — this confirms the right anchor for when AM finishes the CL revamp.

### 6.4 Don't execute mid-candle
*"It's got to be the beginning of the next day. You always you always execute after the candle close. … Because you have no idea whether it's going to hold the level or not."* (~56:31–56:48)
**Context:** Said about earnings setups but the principle is general: confirm with a candle close, not intrabar.

---

## 7. MISCELLANEOUS HEURISTICS

### 7.1 "Shake the trees" pre-entry interpretation
*"what they do is they shake the trees to shake out all the people who want to go long and then they turn around and go long."* (~1:12:00)
**Mechanical implication:** Expect a stop-run BELOW the level before the real reversal. The first wick down is bait; wait for the second probe to confirm.
**Important for V2_4:** This explains why a strict "first wick = entry" rule misses many setups — AM is waiting for the second touch / the failed-second-probe.

### 7.2 Backwardation as bias signal (CL)
~1:38:52–1:39:21: AM notes the active CL contract is $90 vs the forward at $75 — total backwardation, suggesting heavy short pressure that's about to be squeezed. Used as a multi-day bias filter for CL. **Not in V2_4.**

### 7.3 "Call wall" reference (CL)
~1:37:25: *"the call wall for oil is down at $80."* — gamma/options reference. AM checks options call walls to confirm levels of oversold sentiment. **Not in V2_4.**

### 7.4 Avoid options/spy (current capacity issue)
*"What I want to do is try to do this with options in the same sort of space. So, I'm working on looking at the spy and seeing what the chains are doing. But right now, because this is the way I pay my bills, I can't really divide my time properly."* (~1:12:40–1:13:01)
**Implication:** The intraday futures system is the production system. Options are a future build-out.

### 7.5 Volume doesn't matter on intraday levels
*"the volume does not matter because we're looking at time."* (~1:33:30)
**Important contradiction:** v2 spec heavily uses volume (MOC ratio, news-candle volume tagging). On mar-6, AM is explicit that for intraday level mapping, **TIME** (which candle) trumps **VOLUME**. This is a tension between mar-6 and the apr-24 Q&A rules — the latter introduces volume priority. The mar-6 statement was about which candles to track, not how to weight conflicting same-price levels. The two are reconcilable but worth flagging.

---

## 8. NOTABLE VERBATIM QUOTES

- *"This is how I make my money to eat in general."* (1:02:09) — confirming the intraday futures method is the production strategy.
- *"4 a.m. candlestick Europe has been very influential in terms of motion. So I've always got my eye on that."* (1:08:11)
- *"Every day, Asheen. Every day. By a couple of minutes. Doesn't even matter what's going on."* (1:12:21) — about the 1:30 PM candle.
- *"Almost every day, almost every single day, that measured move will give me my target."* (1:22:46) — about 4 AM box duplication.
- *"It is just a clockwork event."* (1:19:33) — about the 50/200 Fib walk.
- *"how rhythmic the price pattern is. And it is absolutely because of algorithmic trading over and over and over again."* (1:24:29)
- *"if you miss it, don't chase it. Just wait for the next setup."* (1:09:21)
- *"They are not they're looking at price time and they're just writing out the upper edges of prices or the lower edges of prices. They're not doing anything more complex than that."* (1:43:48–1:44:00) — her thesis about institutional algos.
- *"So as simple as it seems for you. Yeah. The number. I know I know it's not simple and I know it's got the sub routine sitting inside of there because I've tried to explain it so many times. It's not easy for most people to understand this."* (~1:45:46) — her acknowledgment that there are multiple sub-routines layered on top.

---

## 9. SETUPS POTENTIALLY MISSING FROM V2_4

These are items present on mar-6 but **not (or weakly) represented** in `AM_rules_v2_spec.md`. Each is a candidate "missed setup."

### 9.1 Prior 1:30 PM candle as a primary level
**Strongest case for missing.** AM emphasizes this candle multiple times — a turn-around level that hits "by a couple of minutes" daily. V2_4 has the 3:30 candle as the institutional candle but does not separately track 1:30. The spec should add a Pr1:30 H/L level alongside Pr3:30 H/L.

### 9.2 Measured-move box duplication for targets (4 AM box ladder)
The v2 spec uses Fibonacci extensions anchored on the entry candle (100/150/200/250%). AM on mar-6 uses 4 AM box DUPLICATION — stacking copies of the 4 AM range above/below as targets. These two methods overlap but are not identical. The duplication method is more robust to entry-candle noise. **Missing as a distinct target tool.**

### 9.3 Outside-engulfing 10:00 candle replaces 9:30
When the 10:00 candle outside-engulfs the 9:30, AM uses the 10:00 candle's bottom (or top) as the level. V2_4 always uses the 9:30. **Missing as a level-substitution rule.**

### 9.4 Regime substitution: 9:30–10:30 range when 4 AM wicks are too wide
On choppy days, AM substitutes the 9:30–10:30 range as the measured-move box instead of the 4 AM. V2_4 has no such substitution — uses the 4 AM as fixed framing. **Missing as a regime selector.**

### 9.5 Multi-day 4 AM candles as levels (t-1, t-2, t-3)
AM scrolls back to call out 4 AM candles from 1, 2, 3 days ago that are still acting as levels today. V2_4 spec mentions "up to 3 days back" for prior-day highs/lows but does not explicitly track multi-day 4 AM levels. **Missing as a level type.**

### 9.6 Time-and-sales (tape) confirmation at entry
AM keeps a separate machine for T&S and uses it to confirm price action at the level. V2_4 doesn't use T&S. **Missing as a confirmation gate** — could be approximated with a volume spike/imbalance check.

### 9.7 5-minute scalp fallback for late entries
For days when AM has been busy and the 30-min entry is gone, she drops to 5-min for the last 30 minutes of RTH. V2_4 fires on 1-min only. **Missing as a fallback timeframe.**

### 9.8 "Shake the trees" two-touch logic
AM expects a first wick down (stop-run) before the real reversal — the real entry is on the SECOND probe / failed second probe. V2_4's Pattern B is a 1-bar mechanical breach-and-recover; this is OK as a tight version but may miss the multi-touch fades AM actually trades. **Possibly missing as a multi-touch pattern.**

### 9.9 Daily floor pivot as the trend-bias gate
V2_4 uses the 200 SMA slope. AM on mar-6 uses the daily PIVOT POINT. These are different signals; both are sticky-for-the-day. **Missing as a primary or supplementary gate.**

### 9.10 Inventory-cycle framing (3-day box → distribution premium/discount)
AM frames her bias setup around 3-day boxes building inventory and predicting distribution direction. V2_4 has sideways-edge tracking but not inventory-cycle interpretation. **Missing as a contextual filter.**

### 9.11 Liquidity / bid-ask spread filter
AM excludes thin contracts (silver) by spread. V2_4 ES-only mostly avoids this, but if Afshin expands to RTY/silver/etc., **missing as a tradability gate.**

### 9.12 Earnings post-earnings-drift framework (whole module)
The 43:00–1:02:00 segment on earnings is an entirely separate trading method (equity options + post-earnings drift). It is not in V2_4 at all. If Afshin expects the indicator to fire on those setups, that explains a class of "missed trades." **Either tell Afshin this is out of scope for V2_4, or build a sister indicator for it.**

### 9.13 Don't-buy "all-day chop" filter
AM's rule "don't buy this chart unless scalping on 5-min" when price can't clear the 10 AM high all morning is a distinct *negative* permission. **Missing as a do-not-trade override.**

### 9.14 Pre-place limit orders at the level
AM repeatedly puts orders out at the level ahead of time. V2_4's V2_3 had a "Pre-Place Panel" that was DEPRECATED in V2_4 in favor of breach-confirmation. This was an explicit retreat from AM's stated workflow. Worth re-examining whether the deprecation cost the trader some setups.

### 9.15 R/R skew (5:1 and 8:1 stated targets)
AM's verbatim trade arithmetic: 6 points risk for 30 points reward (5:1); 5 points risk for 40 points reward (8:1). V2_4's MVP uses 1× candle-width as first target, which is closer to 1:1. V2_4 may be exiting WAY earlier than AM. **First-target sizing may be too conservative.**

---

## 10. CROSS-REFERENCE NOTES FOR WAVE 3

Items Wave 3 specialists should pay attention to:

1. **(High priority) The 1:30 PM candle.** If V2_4's level set doesn't include Pr1:30 H/L, this is likely a primary cause of missed setups for the trader. Wave 3 should verify whether V2_4 tracks this candle and add it if not. Cross-check apr-23 and apr-24 transcripts to see if AM repeats the 1:30 emphasis or whether mar-6 was a peculiarity.

2. **(High priority) 4 AM box duplication target ladder.** This is structurally different from the entry-candle-anchored Fib ladder in V2_4. Wave 3 should evaluate whether to ADD the 4 AM box ladder as a parallel target system or REPLACE the entry-candle Fib. Also worth checking which is performing in the pipeline backtest.

3. **(High priority) First-target R/R may be too tight.** AM's 5:1 and 8:1 examples suggest first target should be FARTHER than 100% of entry-candle range. Backtest the 100%-first-target rule's hit-rate vs holding for 200% / 4-AM-box-ladder targets.

4. **(High priority) "Shake the trees" two-touch logic.** Wave 3 should examine whether the 1-bar Pattern B breach-confirm is missing trades that fire on the SECOND probe of a level. Run replay on recent days and count: how often does the FIRST breach fail and the second succeed?

5. **(Medium priority) Regime substitution: 4 AM → 9:30+10:30 box on wide-wick days.** Wave 3 should design a wide-wick detector (e.g., 4 AM range > X% of ADR or prior-N-day average 4 AM range) and add a substitution branch.

6. **(Medium priority) Multi-day 4 AM levels (t-1, t-2, t-3).** Add as a tracker. Cheap to compute, easy to display.

7. **(Medium priority) Daily pivot point as bias gate.** AM's mar-6 bias gate is the daily pivot, not the 200 SMA. The apr-24 spec uses 200 SMA. Wave 3 should ask AM directly whether she's switched, or whether they're complementary (pivot for short-term direction, SMA for regime).

8. **(Medium priority) T&S / tape confirmation.** Approximate with volume-imbalance / NBBO-aggression detection. V2_4 has no proxy. Wave 3 could add a simple "1-min volume > 1.5× recent average AT the level" gate.

9. **(Medium priority) Outside-engulfing 10:00 substitution rule.** Trivial to add; should be in V2_4's level update logic.

10. **(Medium priority) 5-minute fallback for late-entry scalps.** Wave 3 should consider whether to expose a 5-min trigger when 1-min is past prime entry zone.

11. **(Low/Medium priority) Earnings/post-earnings module.** Decision question: is V2_4 supposed to support equity-earnings setups? If yes, this is a major gap. If no, document that explicitly so the trader knows what V2_4 is and isn't covering. Mar-6 makes clear this is a real, separate AM trading method.

12. **(Low priority) Don't-buy chop filter.** Specific negative permission (price can't clear 10 AM high all morning). Easy to implement as a long-block.

13. **(Low priority) Liquidity/spread filter.** Only relevant if extending beyond ES.

14. **(Confidence note) V2_4's MOC volume gate vs mar-6's "volume doesn't matter."** These statements are about different things (mar-6: which candles to track; apr-24: how to validate trend) but Wave 3 should be alert to other tensions between the early (mar-6) and the apr-24 Q&A formulations. Mar-6 is a more raw, intuition-driven version of the system; the apr-24 spec is a more structured/codified version. Some intuition may have been sanded off.

15. **(Confidence note on transcript itself)** The transcript has ASR artifacts ("Asheen" → "Afshin", "thinker swim" → "Thinkorswim", "GlobeEx" → "Globex", "outbox/sent" digression in opening). Time stamps are accurate. The intraday demo is genuinely the genesis recording — AM is teaching this end-to-end for the first time, so it has the highest fidelity to her actual mental model before the system was filtered through written documentation. **Wave 3 should weight mar-6 high when the apr-24 spec disagrees with mar-6 on intuitions, especially around level ordering and target-laddering technique.**

---

## END OF EXTRACT
