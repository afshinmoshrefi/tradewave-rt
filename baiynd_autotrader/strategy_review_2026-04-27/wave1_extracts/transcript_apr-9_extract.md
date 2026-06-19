# AM_transcript_apr-9 Extract — Mechanics Q&A

**Source:** `C:\seasonals\baiynd_autotrader\video transcripts\AM_transcript_apr-9.txt` (1:11:22 total, 581 lines).
**Session character:** Q&A walking through mechanical mechanics of AM's intraday method, opened by an AI-pick demo and closed with a setup for a live walk-through "tomorrow." The trader (Afshin) reads pre-prepared questions (his + Claude's); AM answers each. This is the most explicit MECHANICS-only session of the corpus.

---

## TL;DR

This transcript is the canonical source for FIVE doctrines that V2_4 currently violates or misses:

1. **NO TRAILING STOPS — level-to-level only.** *"I don't trail any stops. I go level A to level B and I'm done."* (line 149). This directly contradicts V2_4's SMA20 trail.
2. **LIMITS ONLY — no market orders, ever.** *"I never use market orders. Always limit orders."* (line 94).
3. **First-minute volume benchmark: 15k ES, ~6k NQ.** Not a gate; an institutional-presence read. Reduces aggression on low-volume opens (line 102-124).
4. **Box walkdown order is FIXED:** 3:30 → 6:00 PM → 4:00 AM → 9:30. Each new box is read RELATIVE to the prior one (line 320-346).
5. **30-minute is the trading timeframe; 1-minute is execution.** *"I am actually trading a 30-min chart. I'm just using the one-minute to execute it."* (line 257).

Plus: Heikin Ashi is the **30-minute momentum sign filter** (positive = pullback-buy zone; negative = bounce-sell zone), explicitly to be ignored on sideways/flat regimes. MACD = redundant; pick one. VWAP slope and side both matter; flat VWAP = chop. Pivots (Woody's "Cloud" + standard) are always loaded; converging pivots above resistance act as relative pit-stops; in a strong trend, AM does NOT stop at the first pivot.

Plus a key concept absent from the existing spec: **"How to decide which box is the most important box of the day"** (line 84). AM was about to teach this on chart but pivoted to questions; this is a TODO for live walk-through.

---

## SETUPS

### Setup 1 — Buy-the-dip, structural (the day's actual play)

**Trigger condition:** SPY 30-min carries the directional cue; spy starts printing bigger candles around 4 AM (line 350) and signals a buy zone. AM's frame: "everything told me 'buy the dip'."

**Entry level:** prior day's closing 30-min low (i.e. the 3:30 PM 30-min candle's low). Verbatim:
> *"if I can get to the low of yesterday's 30 minute low, the closing 30 minute candle, I'm buying it… cuz that's the one that told me, 'Hey, I'm in charge.' Cuz everybody else is sitting inside of me essentially."* (line 144-147)

**Mechanics:** the 3:30 candle BODY engulfs the GlobEx 6 PM body (and partially the 4 AM body) → the 3:30 is "in charge." Buy with a limit at the 3:30 low. *Not chasing,* per the lobster-buffet rule (Setup 5).

**Permission stack used:**
- 30-min closing candle (3:30) range encloses subsequent overnight candles → sideways-but-bracketed.
- 4 AM candle low = overnight low and is **inside** the 3:30 range → 3:30 still in charge.
- SPY has a "buy zone" forming pre-RTH.
- Context: SPX in a "two-week bull" (line 249).

**Risk hand-off:** *"as long as that low holds. If that low breaks, I'm headed off to the pivot, which is sitting below me."* (line 354) — i.e., a stop and an alternate target are both pre-defined.

### Setup 2 — Trade the EDGES on congestion days

> *"on the congested days how do I trade? I trade the edges. I establish what the edges are and when it comes into an edge I buy it and when it goes into the next edge I sell it and that's all I do."* (line 412-414)

**Trigger:** sideways/congested classification (any body-overlap among the 4 boxes).
**Entries:** at the established edges (prior 30-min H, 30-min L, 3:30 H/L, 9:30 H/L).
**No chasing:** if the edge breaks while you're not watching, **wait for it to come back.**
> *"I am not going to chase it. I'm gonna put a limit order out and I'll see if it comes back to get me. If it comes back to get me, great. If it doesn't, I don't care. The buffet is open tomorrow."* (line 417-420)

This is implemented in V2_4's sideways-FADE mode (per spec §7), but only one direction (slope-gated). AM's wording here suggests **both** edges are tradeable on a true sideways day, not just slope-direction. POTENTIAL GAP — see Contradictions §C2.

### Setup 3 — The "extended R3" expectation (mean-revert intraday on extended pivots)

> *"yesterday we were above R3 yesterday. So, we were very extended… So, from the moment the day began, my thought was, well, I'm way above R3. I probably need to come in and test R3 because I know that we're extended."* (line 262-265)

**Trigger:** today's open is materially above prior R3 (or below S3) on a continuation-formation day (rising daily pivots).
**Direction:** revert TO R3 (not against trend) — i.e., expect a pullback to that level.
**Caveat:** this is conditional on no pre-market volume confirming the breakout: *"when we moved up on big volume in the pre-market in the GlobEx, it wasn't on a lot of volume."* (line 266) — i.e., extension on thin volume is suspect.

This is an **intraday mean-reversion** to a pivot level, NOT a setup V2_4 currently implements. Likely missing.

### Setup 4 — News-candle fade

> *"I will say, 'Wait a second. I see this news candle. How much volume went on that news candle? Am I above the news candle or am I inside the news candle?' If the news candle came and now I'm inside of the news candle, it tells me they're fading that news. Then I'll draw a Fibonacci and look at maybe where's the halfway point. Sometimes it's sitting right with a box, one of our boxes. So that will hold."* (line 372-377)

**Trigger:** price has re-entered the body of a prior news candle.
**Read:** the news is being faded.
**Action:** draw Fibonacci on the news candle; look for the 50% / midpoint, especially when it coincides with a known box level.
**Volume note:** AM specifically cited *"a really thin volume pocket because they were covering their shorts in that short squeeze"* (line 379-380) as the news-candle character that gets faded.

This adds a NEWS-CANDLE FADE to the spec — V2_4 has the "outsized news candle level" registration (spec §2/§9) but not the **"price now back inside news candle = fade signal"** mechanism.

### Setup 5 — Limit-only re-entry ("Lobster buffet")

> *"I'm gonna put a limit order out and I'll see if it comes back to get me. If it comes back to get me, great. If it doesn't, I don't care. The buffet is open tomorrow. I'll go get another lobster sandwich if I'm feeling it right. I I don't I don't want a peanut butter and jelly at the very expensive buffet. I'm going to wait for the lobster."* (line 417-420)

**Doctrine:** if you miss the level, do not chase. Place a limit and wait. If unfilled, the trade is a no-trade. **Discipline > completion.**

### Setup 6 — The "size-up after the predicted return" idea (NOT AM's, Afshin's)

Lines 33-43 are Afshin proposing that the AI auto-pick system reduce position size when price exceeds the predicted return. AM says *"Oh, absolutely. This is this is not trading. This is just picking."* This is about the swing-stock AI pick system, NOT about ES intraday. **Excluded from the rule extract.** Mentioning here only so it's not mistaken for a trading rule.

---

## PERMISSIONS

### P1 — Limit-orders only (HARD RULE)

> *"I never use market orders. Always limit orders. Always limit. Only because when you're in live markets, if you use market orders and the order book has thinned out, you can get absolutely smashed… I mean, absolutely destroyed."* (line 94-99)

**Implementation:** every entry is a limit. V2_4 should NEVER place a market order on entry.

### P2 — Prior 3:30 candle is the master

The closing 30-min candle from the prior day, when its body encloses subsequent boxes (6 PM, 4 AM), is **"in charge."** Direction is established only when a subsequent candle BREAKS the 3:30 H or 3:30 L.

> *"What makes the break is the break of the high of that 3:30 candlestick from the prior day or the low of that 3:30 candlestick from the prior day. And that gives us directional flow."* (line 132-134)

**Alert set:** AM keeps four alerts: prior-day 3:30 H, 3:30 L, 9:30 H, 9:30 L (line 135-137).

### P3 — SPY confirms direction pre-RTH

SPY 30-min carries more volume than ES futures (especially with 0DTE flow); SPY printing "bigger candles" at ~4 AM signaled the buy-zone today. AM checks SPY ahead of ES to position.

> *"I always look at the spy because the spy carries more volume than the ES futures. And so they're going to position a little bit differently, especially since they run so many zero DTE."* (line 140-141)

POTENTIAL GAP: V2_4 has no SPY cross-confirm.

### P4 — VWAP: slope + side

Both matter. Flat VWAP = chop, just bounces above/below.
> *"if the VWAP is flat, you don't have trend and they're going to bounce above it and below it… So, all you do is you look to the left and you go, 'Okay, where's it look like they're selling? It's got to match something.' Sometimes it's the midnight candle… And so once that resolves and the VWAP takes slope, it tells you what's likely next on the horizon."* (line 191-195)

### P5 — Pivots: Woody's "Cloud" pivots + standard pivots are ALWAYS LOADED

> *"the pivots are always loaded… I'm just looking for pivots that converge with higher price and I'm going to use them as relative pit stops."* (line 197-201)

**Trend exception:** in a strong trend, AM does NOT stop at the first pivot —
> *"if there's a pivot sitting above it and all of my moving averages are pointing up, I'm not going to stop at that pivot because trend is like a freight train. It doesn't stop on a dime."* (line 202-204)

Prior-day pivots are also referenced — AM wants Ninja to draw prior days' pivots, currently it only draws today's (line 270-273).

### P6 — Heikin Ashi (30-min momentum sign)

**Timeframe:** 30-min chart only. AM does not use HA on 1-min for entry.
**Long permission:** price ABOVE moving averages AND HA positive → pullbacks are buy zones.
**Short permission:** price BELOW moving averages AND HA negative → bounces are sell zones.
> *"if I'm on my 30 minute chart and my mental framework says, hey, listen, this is going to be a buy the dip. I want to see the hyenashi positive. If it's positive and price action are above the moving averages… pullbacks are buy zones."* (line 170-173)
> *"If I'm under my moving averages, then my bounces are sell zones."* (line 175)

**Sideways case — IGNORE:**
> *"divergence is very hard, especially if you've got sideways moving averages. You want to ignore divergence if you've got sideways moving averages because they don't give you enough oomph to tell you what's going on."* (line 176-178)

**Divergence read (when applicable):** trending MA + opposing momentum = "they're searching for support [or sellers]" (line 180-182).

### P7 — MACD is REDUNDANT with HA

> *"the MACD is easier to read than the hyenashi. I put them both on there because I'm like, well, why not see if they both agree with each other?... at the end of the day, yeah, use one or the other."* (line 184-186)

POTENTIAL GAP: V2_4 should not double-count MACD if HA is present, and vice versa. Pick one in the codified decision tree.

### P8 — Time & sales ONLY for delta-volume reads

T&S is used to confirm that big traders are "feeling the heat" (negative delta near a key level) and may need to cover. AM admits she could read this off Motive Wave's net-delta-volume-per-price (line 156). **NinjaTrader currently has no analogue;** this is information-only.

### P9 — Big-trade detection (Motive Wave only feature)

A heatmap firing on >250-contract single trades, used to identify floor-builders and forced buyers. NinjaTrader analogue not present.

> *"I have it set to tell me anytime somebody sells more than 250 contracts at a time… it lets me know where a big trader has either covered or is increasing their position."* (line 215-216)

---

## EXITS DOCTRINE

### **THE DOCTRINE (load-bearing for V2_4 surgery):**

> *"I don't trail any stops. I go level A to level B and I'm done."* (line 149)

> *"That's all. I do not let price action expand and go, 'Oh, I'll leave this on for a runner.' You put a stop order. I put an exit order. Yes. A a stop order. Yes."* (line 150-151)

This is unambiguous: AM uses **structural level-to-level exits**, not trailing stops. Once the next level is hit, she's flat. No SMA20 trail. No runner. No "let it ride."

### Why-it-matters confirmation (earlier in conversation, on the swing-stock AI system but generalized):

> *"trailing stops are terrible. You have one less trade, new trade to get into… intraday traders. You don't trail your stops because you're just you just find the next [trade]."* (line 55-62)

AM says *"trailing stops are terrible"* TWICE in this conversation (line 55, line 58). She also says she had Codex independently verify the simulation result before believing it.

### Outlier exception — extend to next resistance (rare)

> *"that might make me go, okay, instead of going to just level one, let me see if I can get to resistance level two. But that's an outlier and I like to see my moving averages going straight up or straight down for me to do something like that. Otherwise, it's going to move back and forth. And we're going to go up to the 50, down to the 200, up to the 50, down to the 200."* (line 161-164)

**Condition for extension:** 50 SMA AND 200 SMA both pointing strongly the trade direction (clean trend, not chop). Otherwise, take the first level and exit.

This is a softer "TP2" mechanic that V2_4 could implement: if both moving averages slope strongly, target the second resistance/support pivot rather than the first.

### Process > P&L

> *"I don't care what the dollar amount is that I'm making. What I care about is that I'm executing according to process. If I execute according to process, the money will follow."* (line 234-236)

Confirms exit is rule-driven, not P&L-driven.

### Hold time observation

AM states she held a trade today **"for 2 hours and 40 minutes"** (line 521) because price was doing exactly what she expected. Hold times are LEVEL-DRIVEN, not time-driven. (V2_4's time-flat at 15:00 ET still applies as a backstop.)

---

## VOLUME RULES

### V1 — First 1-min RTH volume benchmarks (READ, not gate)

| Instrument | "Normal" 1-min volume |
|---|---|
| ES | **15,000 contracts** (range 12k-15k) |
| NQ | **~6,000 contracts** (sometimes ~8k) |

AM verbatim:
> *"the average is 15,000 anywhere between 12 and 15,000 in one minute. 15,000 contracts in the first minute."* (line 104-105)
> *"6,000 is round and about the average there. Today it looks like it was five, but it's normally around 6,000."* (line 120-121)

### V2 — Below-benchmark = traders tentative

> *"If it's less than that, it tells you that the traders are tentative. So, you're going to need another minute until that 15,000 has come through."* (line 105-106)

**Action:** wait. Watch the second minute candle:
- Inside the first → confirms range (still using first 1-min as the reference).
- Briefly above the first then back inside → still using first 1-min.
- Cleanly outside → now you have a directional cue.

> *"by and large, you're looking at the one minute, but the power that one minute has is going to change depending on how many contracts play in at the first."* (line 109-110)

### V3 — Outsized 1-min volume = retail/speculative, not institutional

> *"In the MES it was very outsized. So that usually means that smaller, more speculative traders are at work rather than the big boys."* (line 116-117)
> *"the big boys today, they weren't putting a hard line in the sand. They were just saying, 'All right, let's just see what happens.'"* (line 122-123)

### V4 — How to USE the first-minute volume (it's a context filter, NOT a binary gate)

> *"It's just something to stick in our head. It's not a decisioning factor other than don't jump on in if it breaks out or breaks down. Let the traders allow themselves to wick it out."* (line 124-125)

**Implementation:** if first-1-min volume is below 12k ES (or ~5k NQ), **do not chase the open's break/down move.** Wait for a wick-out. Combined with limit-only doctrine = place limits at the relevant level, don't market into momentum.

### V5 — Volume confirms moving averages

> *"the moving averages are also going to confirm that. and the they're going to confirm that based on their location."* (line 126)

When 1-min vol is light AND MAs are unaligned → no-trade default.

### V6 — Big-trade prints (>=250 contracts) signal floor/cap building

(See P9.) AM saw 956 + 824 contract buys six minutes apart at 6855 ES → read this as floor-building → got out of her short. (line 219-230)

### V7 — Pre-market volume validates breakout

When yesterday extended above R3 on **THIN GlobEx volume**, AM expects the move to be retraced (line 266-268).

---

## LEVELS

### L1 — The four "boxes" (master 30-min candles)

Order from most-recent-decisive backward:

1. **Prior day 3:30 PM closing 30-min candle** — the "institutional candle." When its body brackets subsequent boxes, the day is in 3:30's hands.
2. **6 PM ET GlobEx open candle** — read RELATIVE to 3:30.
3. **4 AM ET Europe candle** — read RELATIVE to 6 PM and 3:30.
4. **9:30 AM RTH open candle** — read RELATIVE to all three above.

**GlobEx clarification (CONFIRMED):**
> *"6 p.m. to 6:30 p.m. Eastern time."* (line 438)

This nails GlobEx box = 18:00-18:30 ET, NOT a wider GlobEx session window. (V2_4 uses this; spec is consistent.)

### L2 — Box walkdown order — the comparison cascade (CRUCIAL, line 320-346)

When asked *"the box walkdown sequence 3:30, 6, 4, 9:30 — is this always in that specific order?"* AM says **"Yes."** Then explains the comparison:

> *"with every box is we say how does that box compare to the box before it?"* (line 322)

**Step-by-step:**
1. **3:30 box closes** (yesterday). Look at 9:30 of the same day before it. Did 9:30 close in the same range as 3:30 opened? If yes → indecision/coil.
2. **6 PM box opens.** Compare to yesterday's 3:30 box, 9:30 box, 4 AM box. Is it inside? → indecision.
3. **4 AM box.** Compare to 6 PM. If close puts you back inside 3:30 → 3:30 still in charge.
4. **9:30 box.** If it sits inside prior-day 3:30 → 3:30 still in charge → wait for break.

> *"Either it breaks above or breaks below. How do you decide if you want to position into the break? You look at your moving averages. You look at your momentum."* (line 346-347)

**Key insight:** the FIRST box that breaks the 3:30 range is the one that establishes direction. *"that's the place where you say, 'Okay, let's see how 9:30 does.'"* (line 343).

### L3 — "Inventory accumulating" recognition

> *"For days, we sat sideways in these boxes. This tells us we have inventory accumulating… overlapping boxes."* (line 290-294)

Multi-day overlapping 30-min boxes = inventory build → high-probability move pending. (Spec §1's body-stacking gate captures this; this transcript adds the multi-day persistence reading.)

### L4 — Prior-day pivots add confirmation

AM wants prior days' pivots drawn (Ninja currently doesn't out of the box). Rising pivots day-over-day = continuation regime (line 269-272).

### L5 — Daily 200 SMA = "make-or-break line for shorts" (short-cover dynamic)

> *"this 200 line that you see right here is their make or break line. And as long as the 200 stays underneath them, they are going to sell every bounce being underneath there. When it starts rising, they are compelled to buy."* (line 309-311)

This is the **daily-chart 200 SMA**, not the intraday 200. Used to identify:
- Persistent short positioning (price below daily 200 → shorts adding on bounces).
- Forced unwind / short-cover rally (price breaks daily 200 → shorts must cover).

**Speed-of-turn diagnostic:**
> *"The speed of the turn tells you whether it's trending or short covering. The faster the speed, you know that they are buying first and asking questions later. The only people that buy first and ask questions later are sellers who have to leave their position. And that's how you know it's a short covering rally."* (line 315-318)

This is a **classification feature** for the ML layer. Likely missing from V2_4.

### L6 — News-candle Fibonacci 50%

When price is back inside a prior news candle, the Fib 50% (especially when coinciding with a known box level) is a reaction zone. (See Setup 4.)

### L7 — Midnight candle

> *"the midnight candle, you don't see the actual pattern, but you know there is something there."* (line 430-431, paraphrased back to AM)

AM's response: matters MORE during congestion; matters LESS when inside other master candles. Yesterday's midnight candle marked the day's high. Today's didn't matter (was inside 3:30 + 9:30).

> *"whenever I have an answer that goes 'it depends,' I will put it in the trash."* (line 428-429)

For V1, **deprioritize**, but flag for ML classifier discovery (line 433-434: *"we can find it using classifiers when we have historical data"*).

---

## HEURISTICS

### H1 — "Most important box of the day" is determinable

> *"there's a way to say which box is the most important [box]. So, let's use your chart."* (line 87)

AM was about to teach this on the chart but pivoted to questions. **TODO for next session walk-through.** As of this transcript, the rule is not given; only the examples:
- Oct → early March: 4 AM box was most important.
- Recent: 3:30 PM box; sometimes 9:30 box.

### H2 — Indecision pattern recognition

> *"when they end up in these candles like this. No big wicks, just that sort of space."* (line 330-332)
> *"this kind of motion always says, 'Oh, we're fighting. Everybody's fighting, but they're fighting nice… having a discourse.'"* (line 328-330)

Coiling characteristic: small bodies, small wicks, overlapping ranges → break direction unknown until trigger.

### H3 — Order book / market-order risk

> *"if you use market orders and the order book has thinned out, you can get absolutely smashed… in micro gold and you put it in at market and it'll shred you. You'll be down 150 bucks in an instant."* (line 95-99)

Reinforces P1.

### H4 — "Three boxes and two moving averages — that's plenty"

> *"That's why I only have three boxes and two moving averages. Essentially, for me, that's plenty. And all I do is go one, two, three."* (line 243-245)

This is a SIMPLICITY heuristic. Three boxes (3:30, 6 PM, 4 AM) plus 9:30 forming = 4 candles in spec terms; but conversationally AM thinks of "three boxes" as the overnight stack, with 9:30 being where she takes action.

### H5 — 30-min trading, 1-min execution

> *"Essentially, I am actually trading a 30-min chart. I'm just using the one minute to do it to execute it."* (line 257)

**Implementation implication:** V2_4 should compute most signals on 30-min and only USE 1-min for the actual entry trigger placement. Many components (HA, MACD, MA slope, divergence) are 30-min ONLY.

### H6 — OODA loop framing

> *"it truly is the udal [OODA] loop observation… The orientation says which way is the current moving and who has the power."* (line 354-356)

AM frames her process as Observe → Orient → Decide → Act. Decisions update on each new 30-min print.

### H7 — "If I'm wrong, what will price do?"

> *"your only question you ask yourself is if I'm wrong, what will price do? That's all. As long as price doesn't do that, you're going to stay right."* (line 533-534)

Pre-trade question: define the invalidation level FIRST. This is a stop-placement heuristic that aligns with §5 of the spec (entry-candle width stop = "if breached, I'm wrong").

### H8 — "Easy breezy" / process flow

> *"first event, next thing. second event, next thing… It's a space where… easy breezy."* (line 535-537)

Trade flow is meant to feel mechanical; emotional load is the warning sign of a poorly-understood setup.

### H9 — Risk sizing for beginner

For Afshin specifically:
> *"I'm going to trade the MES and I'm going to take a $50 stop-loss max. So, wherever your trade is setting up, your stop better not be more than $50 below for each contract."* (line 552-554)

**Implementation for the SIM/beginner mode:** MES, max $50/contract loss. Several small wins/day → $200-ish/day → ~$4-5k/month at the cited cadence. **THIS IS A BEGINNER GUARDRAIL, not a universal rule.**

### H10 — No scalping (philosophical)

> *"I do not like scalping… the statistics on scalpers are very bad. They either will run the gambit to the top or they're at the park feeding the pigeons. There's literally no in between. And the longer a scalper goes, the more likely it is that he reverts to zero."* (line 392-405)

AM's setups are NOT scalps. Hold times are 15-180+ minutes.

### H11 — Big-trader floor-builds — let trend decide

When 824 + 956 contracts came in at 6855, AM closed her short for $50 loss because *"all of my indicators still say, hey, they're going to buy a bounce."* (line 247-248). The trade-management decision is made on indicator alignment, not on the size of the print itself.

---

## NOTABLE QUOTES

(In addition to those embedded above; verbatim, with line refs.)

**On trailing stops (the load-bearing one):**
> *"I don't trail any stops. I go level A to level B and I'm done."* (line 149)

> *"trailing stops are terrible."* (line 55)

**On limits:**
> *"I never use market orders. Always limit orders."* (line 94)

**On the 3:30 candle being "in charge":**
> *"the 3:30 candle says, 'Hey, I'm in charge.' It's the 3:30 candle of the close continually said, 'I'm in charge.'"* (line 342)

**On overnight comparison:**
> *"Cuz everybody else is sitting inside of me essentially."* (line 147 — AM personifying the 3:30 candle)

**On not chasing:**
> *"I am not going to chase it. The buffet is open tomorrow."* (line 417-418)

**On process:**
> *"If I execute according to process, the money will follow."* (line 236)

**On simplicity:**
> *"the more complex we make or design a system that we have to execute as analog creatures in a digital world, the more difficult it becomes."* (line 241-242)

**On 30-min-as-truth:**
> *"I am actually trading a 30 minute chart. I'm just using the one minute to do it to execute it."* (line 257)

**On the daily 200 line for shorts:**
> *"this 200 line… is their make or break line."* (line 309)

**On short-cover rally diagnosis:**
> *"The speed of the turn tells you whether it's trending or short covering. The faster the speed, you know that they are buying first and asking questions later."* (line 315-316)

**On loss management mindset:**
> *"I lose money every day. I just don't lose a lot of money every day."* (line 232)

**On ignoring divergence in chop:**
> *"You want to ignore divergence if you've got sideways moving averages."* (line 177)

**On the pivot freight train:**
> *"trend is like a freight train. It doesn't stop on a dime."* (line 204)

**On GlobEx timing:**
> *"6 p.m. to 6:30 p.m. Eastern time."* (line 438)

---

## SETUPS POTENTIALLY MISSING FROM V2_4

**M1 — Extended-pivot intraday mean reversion (Setup 3).**
When today opens above R3 (or below S3) of a continuation regime AND pre-market volume on the extension was thin → expect reversion to R3. Not in spec §9 levels nor in spec §4 entry rules.

**M2 — News-candle fade with Fib 50% (Setup 4).**
Spec §2 has "outsized news-candle level" registration as a level, but no entry trigger for "price now back inside news candle." This is a directional fade play that V2_4 doesn't currently fire.

**M3 — Daily 200 SMA short-cover detection (L5).**
The "daily 200 = make-or-break for shorts" is a regime classifier. Not in spec.

**M4 — "Speed of turn" short-cover diagnostic (L5).**
A quantitative feature — measure rate of price change after a level break, classify trending vs short-cover. Pure ML feature; not in spec §13's feature list.

**M5 — SPY pre-RTH cross-confirmation (P3).**
SPY 30-min direction at 4 AM-9 AM ET as a confirmer for ES direction. Not in V2_4.

**M6 — Big-trade detection >=250 contracts (P9).**
NinjaTrader analogue of MotiveWave's heatmap. Order-flow feature; not in V2_4.

**M7 — Time & sales delta read (P8).**
Net delta at a level. Not in V2_4 (and likely Tier 3 / ML-only given NT's data).

**M8 — Prior-day pivots (L4).**
Ninja currently draws today's pivots only. Drawing yesterday's (and prior-prior) pivots, AM uses them as confirmers of continuation regime. Spec mentions but V2_4 may not implement.

**M9 — "Most important box of the day" classifier (H1).**
AM said there is a determinable rule; she didn't teach it in this transcript. **Open item for live walk-through.**

**M10 — Outlier "TP2" extension when both MAs trend strongly (Exits-Doctrine outlier).**
AM allows extending exit to the SECOND level when 50 + 200 SMAs are both pointing the trade direction. V2_4 currently has only the candle-walk + first level (per spec §6); the explicit "if double-trend, target level 2" tier exists but is currently Tier-3-deferred.

**M11 — First-minute volume context filter (V1, V4).**
ES <12k, NQ <5k → "don't chase the open break, wait for wick-out." V2_4 has volume tracking but doesn't use it as a "don't chase open" filter.

---

## CONTRADICTIONS WITH V2_4

**C1 — V2_4 uses SMA20 trailing stop on the runner. THIS IS WRONG per AM doctrine.**

AM verbatim: *"I don't trail any stops. I go level A to level B and I'm done."* (line 149)
V2_4 currently: SMA20-based trailing stop on the runner half.
**Required change:** Replace SMA20 trail with **structural-level walk** (per spec §6), or simpler: exit-at-first-level-no-runner. Spec §11 priority #10 already lists this; this transcript REINFORCES the requirement with the most direct verbatim of any session.

**C2 — Sideways FADE is currently slope-direction-only; transcript suggests both edges.**

V2_4 spec §7: on sideways days, FADE only in the direction of 200 SMA slope (single side).
This transcript line 412-414: *"I trade the edges. I establish what the edges are and when it comes into an edge I buy it and when it goes into the next edge I sell it."* — sounds bidirectional.
**Resolution path:** spec §7 "wired 2026-04-27" notes dual-direction was deferred. This transcript predates that but reads as bidirectional. ASK AM in next session: in a true sideways with flat 200 SMA, do you trade both edges? If yes, V2_4 needs a flat-slope dual-side branch.

**C3 — V2_4 uses MACD AND HA simultaneously; AM says pick one.**

V2_4: both indicators present, both factor into permission logic (depending on the build).
AM line 184-186: *"yeah, use one or the other."*
**Required change:** make one canonical and demote the other to a supplementary visual (or remove). HA is the more commonly cited momentum sign in this corpus; recommend keeping HA, removing MACD from the decision tree.

**C4 — V2_4 may treat midnight candle as a tier-2 level; AM ranks it as conditional.**

AM: midnight candle matters more in congestion, less when contained in other master candles. If V2_4 tracks it equally always, that's overfit.

**C5 — V2_4's SMA50 may be used as bias; AM uses it only as risk/chop estimator.**

Spec §3 already states this correctly. Confirm V2_4 implementation matches spec §3 (slope-direction is 200-only; 50 is risk).

**C6 — Pivot stop logic may be too rigid.**

If V2_4 always exits at the first pivot, that violates AM's outlier rule (line 202-204): in strong-trend regimes (50 + 200 both pointing trade direction), skip the first pivot and target the second. Validate V2_4's behavior here.

**C7 — V2_4's "don't chase" enforcement on missed levels.**

If V2_4 currently re-evaluates and emits a new signal at a worse fill when a level is missed, that violates Setup 5 (the lobster rule). Limits should sit and either fill or expire — no chase, no re-fire at worse price.

---

## CROSS-REFERENCE NOTES (vs AM_rules_v2_spec.md)

**Already in spec, transcript CONFIRMS:**
- Spec §1 four-candle gate, body-not-wick: this transcript's box walkdown (line 320-346) is the same idea verbalized.
- Spec §3 200 SMA slope as sticky bias: consistent with this transcript's MA usage (line 162-164, 191-195).
- Spec §6 candle-walk runner over SMA20 trail: this transcript provides the most direct verbatim quote (line 149) supporting that change.
- Spec §7 sideways edges = prior 30-min H/L, prior 3:30 H/L, prior 9:30 H/L: consistent with line 25-32 (P2 alerts) and line 412-414 (Setup 2).
- Spec §9 outsized news-candle level: consistent with this transcript's news-candle fade (Setup 4) and volume reads (line 372-381).
- Spec §10 GlobEx timing 18:00-18:30: explicitly confirmed line 438.
- Spec on "trade is process-based, no daily cap": confirmed line 234-236.

**New / refined by this transcript:**
- **Volume benchmarks (15k ES, 6k NQ).** Spec §2 has MOC volume ratio but NOT first-minute volume benchmark. Add to spec as a context filter.
- **SPY cross-confirm at 4 AM.** Not in spec. New permission.
- **Prior-day pivots and "rising pivots = continuation."** Line 269-272. Spec §9 mentions today's pivots but not prior-day.
- **Daily 200 SMA short-cover dynamic.** Line 307-318. New regime-classifier feature.
- **"Speed of turn" short-cover diagnostic.** Line 315. New ML feature candidate.
- **"Most important box of the day" determinable rule.** Line 87. **Open item.**
- **News-candle fade entry mechanic (Fib 50% inside news candle).** Line 372-377. Refines spec §9's news-candle level into an actual entry trigger.
- **30-min-trade, 1-min-execute clarification.** Line 257. Explicit confirmation that all of HA/MACD/MA-slope are 30-min reads.
- **No-chase / lobster rule.** Line 417-420. Limit-only enforcement on missed entries.
- **Beginner sizing: MES, $50 max stop/contract.** Line 552-554. Specific to Afshin's path — useful for the sim/beginner-mode UI gating.

**Tabled / open after this transcript:**
- "How to decide which box is the most important box of the day" — AM didn't teach this in apr-9; pulled out the chart, then redirected to questions. **Highest-priority open item.**
- Bidirectional vs single-direction sideways fade on flat 200. AM's wording here suggests bidirectional; spec defaults to single-direction. Verify in next walk-through.
- Daily-200 short-cover detection — not yet a coded classifier.

**Apparent contradictions (none material):**
- AM mentions 4 alerts (line 135-137): prior-day 30-min H, 30-min L, 9:30 H, 9:30 L. The spec's level set §9 is broader; the alert subset is just AM's *attention* subset, not the full level cardinality. Not contradictory, but worth noting that AM PRACTICALLY watches only those four; everything else she "stares down" (line 137) — visual, not alerted.

---

## FINAL NOTE ON RESOLUTION OF V2_4 PAIN POINT

Afshin's stated pain: "valid trade setups were being missed."

This transcript suggests two of the most common reasons:
1. **V2_4 chases.** If a level is touched but not filled-with-permissions, V2_4 may re-emit at a worse price. AM doesn't. Limits should be placed and left; no re-fire. **Implement P1 + Setup 5 strictly.**
2. **V2_4 ignores 30-min context** by computing too much on 1-min. AM trades the 30-min and only executes on 1-min. If V2_4 disqualifies setups because 1-min HA flips, that's a false reject. **HA should be 30-min sign only (per H5).**

Likely also:
3. **V2_4's exit (SMA20 trail) liquidates winners early in chop**, which may cosmetically present as "missed" because the trade got stopped before reaching the structural level. Replace with level-to-level (per C1) and the missed-setup feeling may actually be a mis-exit feeling.

Three setups currently NOT in V2_4 (M1, M2, M5) would also visually present as "AM took a trade and I didn't get a signal" — these are real gaps, not perception.
