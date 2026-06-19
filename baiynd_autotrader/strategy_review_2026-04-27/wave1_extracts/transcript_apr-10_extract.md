# AM Transcript Extract — apr-10 (Live MES Combine Session)

**Source:** `C:\seasonals\baiynd_autotrader\video transcripts\AM_transcript_apr-10.txt`
**Session type:** Live TopStep $50K combine, MES (Micro E-mini S&P), screen-share with at least one observer ("two note takers today"), session window starts pre-RTH and ends ~9:50 ET when she leaves for "next meeting." Up "$95" pre-trade, account "up about $900" overall, max-loss-limit floor $48,895.
**Underlying chart:** 30-minute MES as the *trade chart*, 1-min for *rotation timing*, 15-min "for my eyeballs," ToS as a parallel scanner with price alerts (TopStep platform has no alerts).

---

## TL;DR

AM ran a textbook **buy-the-dip into a bullish 30-min** trade on MES. She placed **two staged limit buys** *before* the RTH open: first at **62** with **8-pt risk**, second more aggressive at **64** (midnight low / "coming into the VWAP") with **4-pt risk**. She refused to chase, refused to short counter-trend, and refused to take the buy-stop breakout — explicitly invoking **prospect theory** ("don't go after the prettiest girl, go after the second prettiest girl") to justify staging at a price *behind* the obvious break. Key new/unwritten rules versus V2_4: (a) **5 trades/day stated max** ("usually my max max is five") versus V2_4's `MaxSignalsPerDay = 3`; (b) **VWAP-200-50 convergence** as a *permission/trigger* for adding to a winner ("if the 50 converges with the VWAP and the 200 and the 200 is pointing up, it's going to rocket back to the top — that's going to be my sweet spot, place where I potentially add"); (c) **target depends on which entry filled** — bottom-of-1min if filled at 62, but flat-50 if filled at the VWAP entry — V2_4 has no profit target at all; (d) **soft-stop / mental stop with NO hard stop in market** — "I'm not going to have a hard stop in there because I have a lot of room"; (e) **buy-stop above 1-min high** is acknowledged as a valid setup but rejected today on poor R:R — V2_4 has no breakout-buy-stop concept; (f) **"don't trade counter-trend"** is verbatim and absolute. The risk numbers (8/4) are MES-specific dollar-equivalents, not universal.

---

## Live trades narrated (chronological)

This was a *single position-trade thesis* with two limit-buy legs staged before 9:30 RTH. AM stayed in the trade as the meeting ended; we do not see the exit.

### Pre-open setup (≈ 9:00–9:30 ET narration)

- 0:18 — She announces she's trading **MES**, not ES, because "it's [MES] sitting on the 30 minute over here." Her chart-of-record is the 30-min MES; the prior 3:30–4 PM close is her anchor candle ("here's my 3:30 to 4 p.m. close").
- 0:53 — **Bullish bias declared** verbatim: *"We know it's bullish: 50 up, VWAP up, momentum up, all the eyeball things that I use. So I know it's a buy-the-dip — but where the dip is a buy is what we have to decide. And that really is only because of risk."* (V2_4 already enforces a 30-min trend gate `close > SMA50 > SMA200` for longs — this matches.)
- 1:14 — Second-best trade rationale: *"We could just buy it here and wait. But we don't want to do that. We always want to manage risk first and manage reward later. And so we wait."*
- 1:27–1:44 — **Time-of-day algo windows** (institutional positioning windows, pre-open): *"9:14 interestingly is usually a place we will get price action moving. So 9:04, 9:02, and then 9:14 to 9:18, and then 9:24 to 9:27. For some reason the algos pick those places up."* Then 9:30–9:31 = *"the one minute open … is where you see the majority of price action planning the flag."* These are timing windows V2_4 does not encode.
- 2:18 — **Multi-feed confirmation**: dollar tracking down → bullish equities likely. ToS open in parallel "to make sure I'm not getting tunnel vision."
- 4:30 — **Entry alert plan**: places ToS price alert at **62** (below current price, intended buy-zone trigger).
  - 4:43 — *"Come along, Sally. Below 62. And I'll make sure that that's my alert. And then I want the 4 a.m. low."*
  - 4:57 — Reason: *"those are the ones that are going to manage the floor of support."*
- 5:26 — **JP Morgan call-wall context**: *"JP Morgan puts on a color spread that goes every quarter … the top of that call wall is 6865. … this number is going to be a little bit of a magnet until we clearly escape the range."* External level — not on V2_4's reference list of 15.
- 6:21 — **Second, more aggressive entry**: *"If perhaps stance you wanted to be extra aggressive, you could easily choose the midnight low since it's coming into the VWAP. And that's 64. So I'll put another one right there at 64."*
  - This is the **VWAP+midnight-low coincidence** — a *level-cluster permission* she explicitly used to add risk.
- 6:47 — **Reading inventory build**: *"I could see them building inventory right here on the one minute. … if it breaks up over the 76 line and goes to 80 if they're long, or … down to 66 all the way to 61."* Note 76 is her shorthand for the prior-bar 76-handle; she frames in the last two digits all session.
- 7:16 — **Refuses the obvious breakout play**: *"I'm unwilling to position here simply because that's not what my system tells me to do. It tells me to go where the crowding is. So I don't chase anything and I simply wait for it."*
- 7:33–8:01 — Asked about a buy-stop on the sideways break: *"You can do that. The question is at what risk? It's probably right but it could have a 15-point drawdown and the question is mentally is that the right thing to do."* (Buy-stop breakout entry → rejected on R-budget grounds, not on validity.)

### Risk + sizing structure on the two staged orders (≈ 9:43)

- 9:43–10:09 — *"My limit order here, my risk is going to be at 57. So I have about eight points of seven [sic] eight points of this one and then four points on the second one."*
  - **Leg 1**: limit buy 62, stop ~57 → ~**8-pt risk**.
  - **Leg 2**: limit buy 64, stop ~ same area 57–60 → ~**4-pt risk**.
- 10:15 — **No hard stop in market**: *"I'm not going to have a hard stop in there because I have a lot of room. … positionally I'm okay being long these two contracts and having it draw down on me if the market happens to gap down."* This is a **mental stop**, executed only if structure invalidates. V2_4 fires hard stops; this is a divergence.
- 11:19 — Confluence read: VWAP near 200 SMA, momentum flat at the would-be-breakout high but lower than the *prior* equivalent zone — *"momentum has stalled out. And so now what I will look for is a pullback."*

### Counter-thesis: optional small short

- 12:07 — *"I can tell that I have sellers up here. There's all kinds of supply up here. If this rockets to the north, I can sell a couple of those. Give myself about a five-point risk. If it works, great. If it doesn't, I'm out of the trade."*
- 12:31 — *"It's come up in two separate candles right there. There's nothing but sellers there, nothing but supply."*
- This is a **rotation-fade short** — a counter-rotation ping at supply with **5-pt risk**. AM frames it as available but says *she* won't take it because she's not trading counter-trend (17:30). **The setup exists in her toolkit but is NOT in V2_4** (V2_4 has a hard 30-min trend gate that would block the counter-trend short).

### After the open: limit-fill watch

- 14:44 — Patience drilled in: *"Sometimes you wait for the trade. Your job is not to be anxious."*
- 15:00 — Re-warns against the buy-stop above the 1-min high: *"This region up here, there's nobody but sellers there. So if I have a buy stop here, how far to the north does it exhaust before it turns around and comes right back down? Because past is prologue."*
- 15:32 — If you *did* take the buy-stop, *"you would have to put your sell order here, or the trade could potentially rotate to the south on you."* Implicit stop = **back inside the 1-min opening candle**.
- 16:33 — **Bigs vs micros budget rule**: *"You can't trade bigs with a 50K combine. You just can't. The risk will eat you alive."* Combine size dictates instrument — explicit account-aware sizing rule.
- 17:23 — Counter-trend explicitly forbidden: *"You don't want to go short. … the trend is upward and I'm not going to trade counter trend. I'm not trading counter trend. I have both upward formations on my moving averages."*
- 17:50 — Wick-out aversion: *"I don't want to get wicked out of a trade."* Aligns with V2_4's `HasLargeWick` risk-reduction concept but applied to entry timing here, not stop sizing.
- 18:16 — **Anti-scalp rationale (fees + mental)**: *"It's very expensive to trade ME contracts like that, in out in out … especially if you start sizing up. Second thing is I don't want to use up all my mental capital."* Trade frequency tradeoff.

### The fill (≈ 36:07)

- 36:07 — *"There we go. Here we go. Here we go. First one. Order filled."* — The **62 limit fills** as the chart sells off into her zone. (No mention of the 64 leg filling — it appears the more-aggressive level was *not* hit, the price stayed below it; the 62 is the only one filled in our visible window.)
- Wait — re-read 38:05 confirms only one is filled: *"my first target is going to be that 50."* If both legs had filled she'd be talking about averaging.

### In-trade management

- 37:34 — She names the outcome in real-time: *"Do you see how we just waited and it came in? Now the question is, is that the only shot I get at the 64?"*
- 37:54 — *"If you are carrying one big ES contract, you can see I almost have no draw down risk here, right?"* — relative-risk acknowledgment that on a fill at extreme low, risk becomes minimal.
- 38:05 — **Targets**: *"My first target is going to be that 50. If it can't hit through the 50, it's going to come to the bottom of the box."* (Box = 30-min reference candle.)
- 38:24 — Asked if she'll exit at first target: *"You're not going to get out, or I'm not getting out. I want to see how well it goes to the 50."*
- 38:34 — **Outcome-vs-process framing**: *"My goal is not to simply end positive. My goal is to watch a structure play out and have it be validated versus invalidated."*
- 39:30 — **Convergence as add-trigger** (verbatim): *"Ideally on the one minute, if the 50 converges with the VWAP and the 200 and the 200 is pointing up, it's going to rocket back to the top. That's going to be my sweet spot. It'll be a place where I potentially add to this position to the north."*
- 40:00 — Confirmed: *"I will add if it breaks above the top here."*
- 40:23 — Choice point: scratch at 50 or hold for the deep fade. *"My play is the deep fade taking us back to the top of the range. I don't I don't care."*
- 41:24 — She does describe the *correct mechanical exit* even though she's holding: *"This is an ideal place to take that position off. Why? Because it's made lower lows and lower highs and it can't get through the 50. … If you've got one big, that's $320. Just like that. You're done for the day."* — For a 1-contract big-ES trader, $320 is the day's goal; she calls it a "done for the day" exit. Her *daily-profit target* implication: $300/day → $1,500/wk → $12,000/mo (42:02). She does not state this as a hard rule, but it's an explicit *target rhythm*.
- 45:34 — **News shock**: a headline drops the market hard ("Detained Americans … US-Iran talks"). Her instruction is to *check the news feed* on shocks rather than react to price.
- 47:54 — Algorithmic-fade explanation: *"They just used that as liquidity. See how fast it moved into the VWAP."*
- 48:23 — *"They retraced the entire mount. So this is all algorithmic play everybody inside of that 30 minute candlestick."* The 30-min candle is the algorithmic playground; that's why she trades on 30-min and reads on 1-min.

### Exit framework (left undone — meeting ends)

- 49:17 — She tells the observer she's *staying in the trade* and will pay them back if she does anything different. So we never see the actual close.
- 49:35 — **Plan invalidation rule**: *"If I cannot get inside of this one minute opening candlestick and I cannot stay in there, I'm going to shift my temperament. I'm going to start thinking about rotation to the downside."*
- 50:08 — **Confirmation breakout level**: *"If it breaks past this 50, it must breach 74 or the buyers just do not have it in them to make anything out of the day."* 74 = the 1-min low (50:32). So her structural test is: break 50 → must take out 74 (the 1-min open low) → otherwise sideways chop.

---

## Setups inferred from the session

### Setup A — *Buy-the-Dip into Bullish 30-min* (LIVE, taken)

| field | value |
|---|---|
| **Trend gate** | bullish 30-min: 50 up, VWAP up, momentum up |
| **Entry trigger** | limit buy at *prior-day-defined floor* (here: 62, "below the 64 midnight low") |
| **Aggressive add** | second limit at the **VWAP/midnight-low confluence** (here: 64) |
| **Stop** | mental, ~5 pts below the entry zone (here at 57); NO hard stop in book |
| **Risk** | leg-1 = 8 pts MES, leg-2 = 4 pts MES (smaller risk because closer to invalidation) |
| **Target 1** | 30-min close-of-3:30 candle ("the box") low/midpoint when filled at the deep dip → flat 50 SMA when filled at the VWAP |
| **Target 2 / runner** | top of the 30-min range (deep fade) |
| **Add trigger** | VWAP+50+200 converge on the 1-min, with 200 pointing up |
| **Invalidation** | breach of "the box" downside, OR cannot recapture 1-min opening candle |

This is essentially V2_4's level-touch logic *with two divergences*:
1. AM's "stop" is a soft mental stop (V2_4 fires hard).
2. AM has *targets* (50 SMA flat, top of range); V2_4 has *no profit target, only SMA20 trail*.

### Setup B — *Rotation-Fade Short at Two-Bar Supply* (NOT taken, mentioned)

| field | value |
|---|---|
| **Context** | bullish 30-min (counter-trend!) but rotation room exists |
| **Entry** | sell into "two separate candles" of supply on a quick rocket north |
| **Stop** | 5-pt risk |
| **Target** | back into 1-min low / VWAP |
| **AM's stance** | available but NOT taken — counter-trend rule overrides |

**FLAGGED — V2_4 has no counter-trend setup at all.** She is consistent with V2_4 by *not* taking it, but acknowledges it exists as a valid scalper play. If we ever soften the trend gate, this is the canonical small-risk fade.

### Setup C — *Buy-Stop Break of 1-Min Opening Range* (NOT taken, mentioned)

| field | value |
|---|---|
| **Entry** | buy stop above the 1-min opening candle high |
| **Stop** | back inside the 1-min opening candle |
| **Target** | runup to overhead supply / next level |
| **AM's stance** | rejected today — *"15-point drawdown"* possible, R-budget bad. Valid setup, wrong moment. |

**FLAGGED — V2_4 has no break-of-opening-range setup.** Worth a slot in the indicator as an *aggressive* mode toggle.

### Setup D — *Convergence Add* (planned but not triggered before meeting ended)

| field | value |
|---|---|
| **Entry** | add to existing winning long when 50, VWAP, 200 converge on 1-min with 200 pointing up |
| **Stop** | parent-trade stop |
| **Target** | top of range / deep fade target |
| **Status** | this is an ADD signal, not a fresh entry |

**FLAGGED — V2_4 has no add-to-winner / scaling concept.** This is a critical missing capability: AM size-builds *into* convergence, V2_4 fires once and trails.

---

## Permissions (what allows a trade)

1. **30-min trend agreement** — bullish: close above 50 above VWAP, all three pointing same direction. *"50 up, VWAP up, momentum up."* (matches V2_4 hard gate)
2. **Level cluster** at the entry zone — at least *two* of {prior-30-min low, midnight low, VWAP, 4 AM low} stacking. Her two-leg structure was 62 (alert price + structural floor) + 64 (midnight + VWAP cluster).
3. **Time-of-day window** — 9:02–9:18 and 9:24–9:30 are pre-positioning; 9:30–9:31 is "planting the flag." Trades are *staged before 9:30*, not fired into noise.
4. **Inventory tell on 1-min** — sideways accumulation visible on 1-min = institutional inventory build → reads as *coiling*, not chop.
5. **Macro confirmer** — DXY direction agrees with the equity bias. Implicit but present (2:18).
6. **Convergence permission** — for the *add*, three-MA pinch on 1-min with the slowest MA (200) holding direction.
7. **News-checked** — on shocks, *check headlines first* (45:34) before re-evaluating thesis.

---

## Risk rules

- **Soft stop / mental stop**: she does NOT place hard stops in the book on these limit-staged entries. Stops are mental, executed on structure violation. Caveat: she had room and was sized small (single MES contracts). On a tighter/larger setup she may use hard stops — *she does not say*.
- **Risk-per-trade in this session**: 8 pts on leg-1, 4 pts on leg-2 (MES, $5/pt → $40 and $20 risk respectively for the $50K combine). For ES bigs ($50/pt) it would be $400 and $200 — she explicitly forbids ES bigs on a $50K combine: *"You can't trade bigs with a 50K combine. You just can't. The risk will eat you alive."*
- **Risk numbers are MES-specific dollar-equivalents**, NOT universal — they map to combine drawdown limits, not pure technical structure. The transcript does not give a generic formula. V2_4's `clip(europe_H − europe_L, 0.3*ADR_20, 0.8*ADR_20)` is an entirely different stop philosophy. **Flag this.**
- **No counter-trend trades** — *"I'm not going to trade counter trend."* (17:30, verbatim, twice for emphasis)
- **No chasing** — *"My bus pass says I'm not paying more than X to get on the train. I'm not."* (17:01) She would rather miss a trade than pay a worse fill.
- **Bigs vs micros gated by account size** — $50K combine → MES only.
- **Combine trailing-drawdown awareness** — she walks through TopStep's $48,895 floor explicitly (8:24). Trade sizing must respect the *trailing* drawdown, not just the absolute one.
- **News on shock** — when price violently moves, check news *first*, re-evaluate after. If thesis intact, hold.
- **Daily target as soft cap** — for one big ES contract, $320 = "done for the day." Implicit P&L stop at first target if it's already a winning day. Phrased as *can*, not *must*.

---

## Trade-cap rule — verbatim

**(20:00 timestamp, verbatim Q&A — V2_4 default `MaxSignalsPerDay = 3` is BELOW her stated personal max.)**

> **Q: "What is your typical number of trades per day?"**
> **AM: "That depends on what the market's giving me. Sometimes, if it's sideways, let's say I get a pocket that's very well defined and it's clear that they're moving top to bottom and bottom to top. Let's say that's what I'm seeing. I may trade it every time it comes to the bottom. And if it's a series of 30 minute candlesticks, it could be, you know, it could be five, six times. So I will go in and out and in and out maybe five trades."**
> **Q: "So that's your That's usually my max max is five."**
> **AM: "See, do you go through days that you don't trade at all? Absolutely. It just doesn't come."**

**Reading**: AM's stated *upper bound* is **5 trades per day** in defined-range chop, AND she has **zero-trade days** when nothing sets up. V2_4's default of 3 is conservative but inside her envelope; the V2_4 `Range(1, 5)` *parameter range* matches AM's max. **Recommendation for cross-reference**: V2_4 default could be argued up to 4 or 5 to match AM's actual behavior in chop — but the constraint is range-condition-aware (only 5 in defined chop, fewer when one-directional).

---

## Convergence concept (VWAP + 50 + 200)

**Verbatim, 39:30:**
> *"Ideally on the one minute, if the 50 converges with the VWAP and the 200 and the 200 is pointing up, it's going to rocket back to the top. That's going to be my sweet spot. It'll be a place where I potentially add to this position to the north."*

**Reinforced 43:17:**
> *"What I'm waiting for is the sweet spot, which I hope converges, where my 200, my VWAP, and my 50 all come in and compress at one point. And then the levy will break. When the levy breaks, it's very likely to break to the north because all of our patterns are telling us that."*

**Mechanic**:
1. **Three lines** — 1-min 50 SMA, 1-min VWAP, 1-min 200 SMA.
2. **Compression** — they pinch to a single price zone.
3. **Direction permission** — 200 must point in the trade direction (up for longs).
4. **Trigger** — break of the pinch in the trend direction = "the levy breaks."
5. **Use** — primarily an *add* trigger, but conceptually also a fresh-entry trigger. The pinch resolves with momentum because all three reference levels become *trapped* at the same price; whoever loses the pinch surrenders all their reference data at once.
6. **Why "second prettiest girl" applies**: the pinch is *not* the obvious breakout level. The obvious breakout is the 1-min opening high. The convergence is *behind* the breakout — buying it is paying less for the same outcome (this is where prospect theory and convergence link).

**FLAG — V2_4 does NOT detect 3-line convergence.** This is a major missing primitive. Even as a *visual indicator overlay* it would help the manual trader spot the sweet spot. As an autonomous rule, it would gate add-events.

---

## Prospect theory ("second prettiest girl")

**Verbatim, 36:41:**
> *"What this actually says is you don't actually go after the prettiest girl. You go after the second prettiest girl. And she gives you all the benefits of having the prettiest girl, plus a one-up against your competition."*

**AM's source citation:** Tversky & Kahneman, *Prospect theory: An analysis of decision under risk*, Econometrica 1979 (35:00–36:41). She Googles for the paper live; she's not citing this casually, she's citing it as her decision-theoretic foundation.

**What she means in trading terms:**
- The "prettiest girl" = the obvious *favorite* trade — the breakout above the 1-min opening high, the chase above resistance, the "everyone's thinking it's long" entry (23:21).
- The "second prettiest girl" = the *non-obvious* level *behind* the favorite — the dip back to VWAP/midnight-low/box-bottom *before* the breakout. Same direction, same payoff, **less competition for fills, smaller risk distance, better R:R**.
- Why it works: prospect theory says decision-makers overweight certain outcomes and underweight uncertain ones; the herd piles into the certain breakout. The trader who positions for the *retest* gets:
  1. Price improvement (entered lower / higher).
  2. A natural stop (the level that would invalidate the thesis is right next to the entry).
  3. The *same* upside if the move plays out.
- Operationally she repeats this idea as **"the watering hole"** and **"where the girl is."** The girl = the price magnet (VWAP / box / cluster) that algos return to. *"They're going to the bottom of the water cooler. They're going to the water coolers that everybody's been hanging around overnight."* (30:43)

**How it informs setup selection:**
- **Stage limits at the cluster, not the breakout.** AM's 62 and 64 limits are the second-prettiest-girl plays. The "prettiest girl" was a buy-stop above the opening range high — explicitly rejected.
- **Wait. Don't chase.** The market re-tests its decision zones; a missed first move is not a missed trade.
- **Choose the level that's also a stop**: her 64 entry is at the midnight low + VWAP because the same reference IS the invalidation marker. If price loses 64 cleanly, the thesis is wrong and she's out for ~4 pts; if it holds, she has the trade.
- **Two-leg sizing**: leg-1 deep-dip (less likely to fill, biggest R:R), leg-2 cluster (more likely to fill, smaller R). This is a literal *prospect-theory diversification* across fill probabilities.

**FLAG — V2_4 already does level-touch limits, which is structurally a "second prettiest girl" approach.** What's missing: the *staging* concept (multiple limits at progressively-more-aggressive levels with progressively-smaller risk). V2_4 fires once.

---

## Notable quotes (verbatim, with timestamps)

- 0:53 — *"We know it's bullish: 50 up, VWAP up, momentum up, all the eyeball things that I use."*
- 1:14 — *"We always want to manage risk first and manage reward later."*
- 7:25 — *"It tells me to go where the crowding is. So I don't chase anything and I simply wait for it."*
- 8:57 — *"It's not whether you have direction right because you probably will. It's whether you position with the adequate risk event in play."*
- 16:42 — *"Your system absolutely correct tells us it's bullish. See, we are choosing where we are going to engage in the market."*
- 17:01 — *"My bus pass says I'm not paying more than X to get on the train."*
- 17:30 — *"The trend is upward and I'm not going to trade counter trend."*
- 19:17 — *"I have to have clean, solid flow that tells me what's going on. And so I'm going to wait for the watering hole where all the guys and gals have moved to."*
- 20:35 — *"That's usually my max max is five."*
- 26:24 — *"When you take a trade, two things have to be in your head. What's my risk and where am I going?"*
- 27:17 — *"My exits are always thought through. I never take a trade without an exit plan."*
- 28:23 — *"Everything is about orientation, not just observation. Observation is there's the VWAP bounce. Orientation is hang on, we're headed to where the girl is at the water cooler."*
- 32:39 — *"The most statistically valid spot for the bounce off of a VWAP with a flat 50 is going to be that flat 50."*
- 38:34 — *"My goal is not to simply end positive. My goal is to watch a structure play out and have it be validated versus invalidated."*
- 39:30 — *"If the 50 converges with the VWAP and the 200 and the 200 is pointing up, it's going to rocket back to the top."*
- 42:02 — *"$300 a day, $1,500 a week, $12,000 bucks a month."*
- 43:38 — *"When the levy breaks, it's very likely to break to the north because all of our patterns are telling us that."*
- 44:32 — *"You have to be looking with purpose, not just looking. That's the difference between observation and orientation."*

---

## Setups potentially MISSING from V2_4

| # | AM concept | V2_4 status | Severity | Note |
|---|---|---|---|---|
| 1 | **5 trades/day max in chop** | Default = 3, range 1–5 | LOW | Inside V2_4's range; default could be argued up if chop is detected |
| 2 | **VWAP + 50 + 200 1-min convergence** | Not detected | **HIGH** | Critical add-trigger; not even a visual primitive in V2_4 |
| 3 | **Add-to-winner on convergence** | No add/scaling logic | **HIGH** | V2_4 is one-and-done; no pyramid |
| 4 | **Two-leg staged limits at progressive levels** | Single fire only | MED | Could be modeled as deep-leg (low fill prob, big R) + cluster-leg (high fill prob, small R) |
| 5 | **Mental/soft stop, no hard stop in book** | Hard stop fired | LOW | Probably *better* for the autonomous stack to keep hard stops; flag for manual mode |
| 6 | **Profit target = flat 50 SMA / box-bottom / range-top** | No profit target, SMA20 trail only | **HIGH** | Manual trader needs targets; current trail-only is too patient and not how AM operates |
| 7 | **Pre-9:30 algo-window timing (9:14, 9:24, etc.)** | Trades on session boundary | LOW-MED | Marginal alpha but cited explicitly |
| 8 | **Counter-trend rotation-fade short** | Hard trend-gate blocks | DEFER | AM didn't take it; OK for now |
| 9 | **Buy-stop break of 1-min OR** | Not present | MED | Aggressive-mode toggle candidate |
| 10 | **External level: JP Morgan call wall (6865 quarterly)** | Not on the 15-level list | LOW | Quarterly anchor; one extra reference |
| 11 | **DXY/macro confluence check** | Not in the gate | LOW | Soft confirmer, not a hard gate |
| 12 | **News-shock handling** | Not handled | MED | Indicator is silent on news |
| 13 | **"$300/day done" daily-profit cap** | No P&L lockout on green day | LOW-MED | Risk guardrail counterpart to MaxDailyLossDollars |
| 14 | **Bigs-vs-micros instrument gate by account size** | Not enforced | LOW | Nice-to-have; outside core indicator scope |
| 15 | **HasLargeWick → enter-timing aversion** | Stop sizing only | LOW | Already captured for stops; could extend to entry timing |

---

## Cross-reference notes for Wave 3

- **Versus V2_4 source** (`AMTradeCockpitV2_4.cs`):
  - Trend gate (close > SMA50 > SMA200) ✓ matches AM here.
  - Stop sizing via Europe range and ADR ✗ does NOT match AM's MES-specific 4/8 pt structural stops.
  - SMA20 trail ✗ does NOT match AM's flat-50 / box / range-top targets.
  - `MaxSignalsPerDay = 3` ✓ inside her range, ✗ below her stated max.
  - `MaxDailyLossDollars = 150`, `MaxDailyLosingTrades = 2` — no equivalent in transcript; transcript only discusses *upside* daily target ($300/contract).
  - 15-level reference list — VWAP, midnight, prior-30-min, opening-range all present and used in this session ✓. JP Morgan call wall (6865) is *external* and missing.

- **Versus Afshin's pain point ("missing valid setups")**: the most likely culprits, ranked:
  1. **No add-to-winner on convergence** — every "I'm in a winner that converges" moment in AM's tape becomes an unmissed pyramid; V2_4 silent.
  2. **No profit target, only SMA20 trail** — V2_4 will exit early on noise where AM holds for the deep fade, AND will hold past natural targets where AM scratches.
  3. **No staged-limit (two-leg) entry** — V2_4 likely fires once at the first level touch and ignores deeper dips that AM would have a separate, smaller-risk leg on.
  4. **Hard stop versus AM's mental-stop tolerance** — V2_4 can stop out on noise where AM tolerates drawdown to her structural invalidation. (CAVEAT: for autonomous stack, hard stops are preferable; this divergence is a *manual-mode* gap, not autonomous.)

- **Wave 3 priority**: convergence detector + add-event are highest-leverage. Profit-target system second. Two-leg staged-limit third. Counter-trend short fourth (defer; she didn't take it).

- **Open AM-escalation candidates** (low priority — none in this transcript rise to "high impact ambiguity"):
  - Whether her 4/8 pt risk numbers are *MES-specific dollar-mapped* (most likely) or *technical-structure scalars*. Transcript implies dollar-mapped via the combine-floor talk but doesn't say so explicitly. Defer; will be answered by other transcripts.
  - Whether the convergence add is a *fresh entry* trigger or *only* an add. Transcript phrasing suggests both, but she only used it as add here.

---

**End of extract.**
