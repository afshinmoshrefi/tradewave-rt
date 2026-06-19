# AM Intraday Rules by Codex

This document is a first-pass Codex synthesis of Anne-Marie Baiynd's intraday system from the eight transcript files in this folder. It intentionally ignores the existing Claude-generated rule files.

This is educational process documentation, not financial advice. The system is a risk-first intraday framework. A new trader should trade it in simulation or micros until the rule flow is automatic.

## Source Transcripts Used

- `AM_transcript_mar-6.txt`
- `AM_transcript_apr-8.txt`
- `AM_transcript_apr-9.txt`
- `AM_transcript_apr-10.txt`
- `AM_transcript_apr_16.txt`
- `AM_transcript_apr-23.txt`
- `AM_transcript_apr-24.txt`
- `AM_transcript_apr-29.txt`

## The System In One Paragraph

Anne-Marie is not trying to predict price from indicators. She is mapping where large groups of traders planted flags at high-volume institutional times, then trading from one known crowding level to the next. The 30-minute chart gives the battlefield. The 1-minute chart gives the execution. The important levels are built from the prior 3:30-4:00 p.m. institutional close, the 6:00-6:30 p.m. GlobeEx open, the 4:00-4:30 a.m. Europe open, the 9:30-10:00 a.m. regular-session open, and the 9:30-9:31 a.m. 1-minute opening candle. VWAP, the 50 SMA, the 200 SMA, pivots, momentum, volume, and order flow are used to confirm orientation, size, and targets.

## Minimal Rules

1. Trade the 30-minute chart, execute on the 1-minute chart.
2. Mark the major boxes every day: prior 3:30-4:00 p.m., 6:00-6:30 p.m., 4:00-4:30 a.m., 9:30-10:00 a.m., and the 9:30-9:31 a.m. 1-minute high/low. All times are Eastern.
3. Decide the day type before trading: trend up, trend down, sideways/congested, or no trade.
4. For a clean long trend, the key bodies should stair-step upward: 6 p.m. below 4 a.m. below 9:30. For a clean short trend, they should stair-step downward: 6 p.m. above 4 a.m. above 9:30.
5. If the boxes overlap or sit inside each other, it is sideways. Trade only the edges: buy old lows/support, sell old highs/resistance. Do not trade the middle.
6. If only two of three major boxes align, do not take a clean trend trade. Treat it as mixed unless price gives a very clear failed retest at an edge.
7. The moving averages confirm the box story. Above rising 50/200 and rising VWAP, pullbacks are buys. Below falling 50/200 and falling VWAP, bounces are sells. Flat/crossed averages mean range behavior.
8. Use limit orders. Do not use market orders.
9. Do not chase. If the entry leaves without you, wait for the next setup.
10. Default entry is confirmation, not guessing: let price touch or briefly break a level, recover or fail, then enter on proof.
11. Every trade must have the answer to two questions before entry: "What is my risk?" and "Where am I going?"
12. If the 9:30 1-minute opening range is wider than about 10 ES points, use 1 MES or reduce size. Wide opening ranges can expand violently.
13. Beginners should use hard protective stops even though Anne-Marie may sometimes manage without a hard stop in discretionary trading.
14. Do not trail stops as the default. Trade level A to level B, take the planned exit, and reassess.
15. One to three good trades is enough. Five trades is usually the upper limit on a very clean range day. No-trade days are valid.

## Chart Setup

Use a 30-minute chart for the framework and a 1-minute chart for execution.

Required:

- 30-minute candles.
- 1-minute candles.
- VWAP, no bands needed.
- 50-period SMA.
- 200-period SMA.
- Standard daily pivots.
- Prior day pivots if available.
- High/low/body boxes for the major time windows.
- 9:30-9:31 a.m. 1-minute high and low.
- Volume.

Useful but not required for version 1:

- Heikin Ashi momentum or MACD momentum. Use one clear momentum read, not both.
- Time and sales.
- Delta volume by price.
- Depth of market.
- Large-trade alerts.
- SPY as a confirmation read for ES.
- Dollar and CL as broad-market temperature gauges.

Do not make the chart busy. Anne-Marie repeatedly reduces the working system to boxes, the 50 SMA, the 200 SMA, VWAP, and pivots.

## Key Time Windows

All times are Eastern.

### Prior 3:30-4:00 p.m. Candle

This is the institutional close or "MOC" candle. It is often the dominant candle for the next session because it captures where institutions planted their end-of-day flag.

Use it for:

- Bias.
- Support/resistance.
- Gap context.
- Next-day buy-the-dip or sell-the-rip logic.
- Position sizing when volume confirms institutional flow.

MOC validation:

- Compare 3:30-4:00 volume to the prior 3:00-3:30 candle.
- Ratio greater than 1.2 means validated institutional flow.
- Ratio greater than 1.0 but not 1.2 means partial/reduced-size validation.
- Ratio at or below 1.0 stays gray/no strong flow. The transcript specifically says 0.8 to 1 remains gray.

If MOC is validated and the 50 SMA on the 30-minute chart is rising, dips are more likely to be bought. If validated and the 50 is falling, bounces are more likely to be sold.

### 6:00-6:30 p.m. GlobeEx Candle

This is the futures reopen. It often becomes support or resistance later in the session.

Use it to ask:

- Did overnight traders accept above the prior 3:30 candle?
- Did they fail to get above it?
- Is the 6 p.m. body above, below, or inside the prior institutional candle?

### Midnight Candle

The midnight candle matters, especially in NQ, but it is not yet a primary beginner rule. Mark its high and low as reference levels.

Use it only when it lines up with a larger box, VWAP, pivot, or visible reaction.

### 4:00-4:30 a.m. Europe Candle

This is a major institutional candle. Its high and low often become the day's meaningful support/resistance.

Rules:

- Above the 4 a.m. high, pullbacks tend to be buys.
- Below the 4 a.m. low, bounces tend to be sells.
- If the 4 a.m. candle engulfs prior boxes, it often becomes the day's working range.
- If price loses a 4 a.m. edge, expect movement toward the next box or pivot.

### 9:30-10:00 a.m. RTH Opening Candle

This is the regular-session trader-flow candle. It often continues or rejects the institutional flow from the prior day.

Use it to answer:

- Did 9:30 open inside the prior 3:30 candle? If yes, prior 3:30 is still in charge and the day is likely congested until a break.
- Did 9:30 open above the prior boxes and hold? That favors long continuation.
- Did 9:30 open below the prior boxes and fail back upward? That favors short continuation or sell-the-bounce behavior.

### 9:30-9:31 a.m. One-Minute Opening Candle

This is the execution reference for the regular session.

Rules:

- Mark its high and low.
- Let the candle complete.
- If ES volume is around 12,000-15,000 contracts or more, the first minute has real power.
- If ES volume is below that, traders are tentative. Wait for the second minute.
- For NQ, about 6,000 contracts is a rough first-minute normal level from the transcript.
- If the second minute stays inside the first minute, it confirms the first-minute range.
- If price ticks outside and comes back in, keep using the first-minute range.

When price loses the 9:30 1-minute low, sellers have planted a flag. Until that low is recovered, bounces are suspect. When price recovers and holds inside/above the 1-minute candle, buyers may be taking control again.

## Day Type Classification

Classify before entry. Do not force a trade before the day type is clear.

### Clean Trend Up

Conditions:

- 6 p.m. body below 4 a.m. body below 9:30 body.
- Candle bodies are not materially overlapping.
- Price is above the prior 3:30 institutional close or has reclaimed it.
- 50 SMA and 200 SMA support the move.
- VWAP has upward slope.
- Momentum is positive.
- MOC is validated if available.

Trade plan:

- Buy pullbacks to support.
- Valid supports: 9:30 edge, 4 a.m. edge, 3:30 edge, VWAP, 50 SMA, 200 SMA, pivot confluence.
- Avoid shorting except for advanced scalps into primary candles.
- Target next resistance, pivot, prior high, or box extension.

### Clean Trend Down

Conditions:

- 6 p.m. body above 4 a.m. body above 9:30 body.
- Candle bodies are not materially overlapping.
- Price is below the prior 3:30 institutional close or has lost it.
- 50 SMA and 200 SMA support the move.
- VWAP has downward slope.
- Momentum is negative.
- MOC validates downside flow if available.

Trade plan:

- Sell bounces to resistance.
- Valid resistances: 9:30 edge, 4 a.m. edge, 3:30 edge, VWAP, 50 SMA, 200 SMA, pivot confluence.
- Avoid longs except for advanced scalps into primary candles.
- Target next support, pivot, prior low, or box extension.

### Sideways / Congested Day

Conditions:

- 3:30, 6 p.m., 4 a.m., and 9:30 boxes overlap, nest, or sit on top of each other.
- VWAP is flat.
- 50 and 200 are flat, crossed, or close together.
- Momentum is flat.
- Price is inside prior major boxes.

Trade plan:

- Trade edges only.
- Buy at old lows/support.
- Sell at old highs/resistance.
- Do not trade the middle of the box.
- If multiple old levels cluster near the same price, the level tied to the highest volume candle wins.
- If 200 SMA slopes up, supports are more trustworthy. If 200 slopes down, resistances are more trustworthy.
- When the range finally breaks and holds outside, reclassify the day.

### Mixed / Two-of-Three Day

If only two of the three major candles align, do not call it a clean trend day.

Beginner rule:

- No breakout trade.
- Wait for a failed retest at a clear edge.
- Reduce size.
- Take quicker targets.

Anne-Marie acknowledged that there are discretionary two-of-three trades, but the simplified mechanical version should require all three major candles to align.

### Extended / Exhaustion Day

Conditions:

- Price is above R2/R3/R4 or below S2/S3/S4.
- Price is far from the 200 SMA.
- There has been a strong run followed by stall.
- Volume does not confirm the size of the move.
- The move may be short covering rather than durable buying.

Trade plan:

- Do not blindly fade trend.
- Expect possible reversion toward pivots, VWAP, 50, or 200.
- Reduce size.
- Wait for failure or confirmation.
- Add extra pivots such as Woody's only to find higher/lower extension targets.

## Entry Rules

### Universal Entry Rules

- Use limit orders.
- Know the stop before entry.
- Know the first target before entry.
- Do not enter in the middle of congestion.
- Do not enter because price is moving fast.
- Do not enter because you are afraid of missing it.
- If price leaves without filling you, let it go.

### Default Confirmation Entry

This is the base case for a new trader.

For long:

1. Price approaches a known support level.
2. Price touches or briefly breaks below it.
3. Price recovers the level.
4. Price pulls back but does not break the low of the breach candle.
5. Enter long when price breaks above the high of the recovery/breach candle or otherwise proves support is holding.
6. Stop goes below the low of the candle that made the breach.

For short:

1. Price approaches a known resistance level.
2. Price touches or briefly breaks above it.
3. Price fails back below the level.
4. Price bounces but does not break the high of the breach candle.
5. Enter short when price breaks below the low of the failure/rejection candle.
6. Stop goes above the high of the candle that made the breach.

Anne-Marie calls these "look below and fail" for longs and "look above and fail" for shorts.

### Look Below And Fail

Long setup:

- Price loses a support ledge.
- It recovers the ledge.
- It pulls back to a higher low.
- It starts to bounce again.
- Entry is the break above the high of the recovery candle.
- Stop is the low of the candle that breached support.

This is preferred because it proves sellers tried to continue lower and failed.

### Look Above And Fail

Short setup:

- Price breaks above resistance.
- It cannot hold above resistance.
- It comes back inside/below the level.
- It bounces to a lower high.
- Entry is the break below the low of the failure candle.
- Stop is the high of the candle that breached resistance.

This is preferred because it proves buyers tried to continue higher and failed.

### Trend-Day Breakout Entry

Use only when all major boxes align and bodies are not overlapping.

For long:

- 6 p.m. below 4 a.m. below 9:30.
- Price breaks above the 9:30 range.
- Confirmation version: wait for two non-overlapping 5-minute candles trending upward after the 9:30 high.
- Entry is above the range or on a pullback toward the 50% level of the 9:30 candle.
- Stop is the bottom of the 9:30 candle plus a small buffer, such as about five ticks, or below the failure candle if using the 1-minute confirmation.

For short:

- 6 p.m. above 4 a.m. above 9:30.
- Price breaks below the 9:30 range.
- Confirmation version: wait for two non-overlapping 5-minute candles trending downward after the 9:30 low.
- Entry is below the range or on a pullback toward the 50% level of the 9:30 candle.
- Stop is the top of the 9:30 candle plus a small buffer, or above the failure candle if using the 1-minute confirmation.

### Wide Candle Handling

If the entry candle is too wide, do not take full normal size at the break.

Rules:

- If the 9:30 1-minute opening range is more than about 10 ES points, use 1 MES or reduce size.
- If the 9:30 30-minute candle is very wide, consider half size at the break and add at VWAP, the midpoint, or a failed retest.
- Alternative: skip the break and place the full order at the midpoint. Risk: price may never come back.
- Wide opening candles often dampen later extension. Prefer 150% targets over 200% targets unless slope and flow are strong.

### Sideways Edge Entry

For congestion days:

- Identify the top and bottom of the active box cluster.
- Sell the upper edge only after failure or rejection.
- Buy the lower edge only after support holds or a look-below-and-fail.
- If the moving averages are flat/crossed and price is in the middle of boxes, do nothing.
- If under the moving averages, take longs smaller than shorts.
- If above the moving averages, take shorts smaller than longs.

### 9:30 One-Minute Opening Setup

Short example:

- The 9:30 1-minute candle sits below the 50 and 200.
- Price breaks below the 1-minute low.
- Wait for a failed bounce/retest into the opening range.
- Enter short on the failure.
- Stop above the 1-minute high or above the failure candle.
- First target is VWAP, the next support, or the next box edge.

Long example:

- The 9:30 1-minute candle sits above the 50 and 200.
- Price breaks above the 1-minute high or holds a pullback.
- Wait for a failed sell attempt or support confirmation.
- Enter long on the recovery.
- Stop below the 1-minute low or below the failure candle.
- First target is VWAP, the next resistance, or the next box edge.

## Stop Rules

Every trade needs an invalidation price.

Long stops:

- Below the low of the candle that breached support and failed.
- Below the support box being defended.
- Below the 9:30 candle low on a clean trend-day long.
- Below VWAP/50/200 only if that level is the actual support thesis.

Short stops:

- Above the high of the candle that breached resistance and failed.
- Above the resistance box being defended.
- Above the 9:30 candle high on a clean trend-day short.
- Above VWAP/50/200 only if that level is the actual resistance thesis.

Do not place a trade if the stop is too far away for the account.

Beginner risk rule:

- Start with MES.
- Keep the first practice stop near $50 max per MES contract.
- If the setup requires more risk than that, reduce size, wait for a better entry, or skip.

Anne-Marie may sometimes avoid placing a hard stop when she has account room and is actively managing the trade. That is not a beginner rule. A new trader should use protective stops.

## Target Rules

The system trades from one known level to the next. Do not enter unless there is enough room to target the next level.

Common targets:

- VWAP.
- 50 SMA.
- 200 SMA.
- Prior 3:30 high/low.
- 6 p.m. high/low.
- 4 a.m. high/low.
- 9:30 30-minute high/low.
- 9:30 1-minute high/low.
- Standard pivots.
- Prior day pivots.
- Prior highs/lows.
- Value area high/low if visible.
- Measured move of the active box.

Trend target guide:

- First target: opposite edge of the active candle/box or nearest pivot.
- Second target: 100% measured move.
- Strong trend target: 150% measured move.
- Very strong slope/flow target: 200% measured move.

If the 200 SMA is flat, target expectations should be dampened. Start with 100%-150%, not 200%.

If the 200 SMA has strong slope in the direction of the trade and the candle bodies do not overlap, larger extensions are more realistic.

Sideways target guide:

- Buy lower edge, target upper edge or midpoint resistance.
- Sell upper edge, target lower edge or midpoint support.
- Do not expect breakout-style extensions inside congestion.

Exit principle:

- Level A to Level B, then reassess.
- Do not trail by default.
- If price sits too long at a confluence level and cannot continue, take the money.
- If structure invalidates, exit even if the stop has not been hit.

## Position Sizing

Size is controlled by confidence, alignment, volatility, and account risk.

Fuller size only when:

- Major boxes align.
- Candle bodies do not overlap.
- MOC is validated.
- 50/200/VWAP agree.
- Momentum agrees.
- Entry is near a clear support/resistance edge.
- Stop is reasonable.

Reduced size when:

- Boxes overlap.
- Only two of three major boxes align.
- The market is sideways.
- The 9:30 range is wide.
- The trade is countertrend.
- The 50 and 200 disagree.
- VWAP is flat.
- Volume is odd or news-driven.
- The day is volatile or "bonkers."
- You are tired, unfocused, or emotionally off.

No trade when:

- Price is in the middle of the box.
- The stop is too large.
- You do not know the target.
- You are chasing.
- The day type is unclear.
- The setup requires guessing.

## How To Use Moving Averages

The boxes are primary. The moving averages tell you how the boxes are being accepted or rejected.

50 SMA:

- Main storyboard for short-term intraday pressure.
- Rising 50 means pullbacks are more likely to be bought.
- Falling 50 means bounces are more likely to be sold.

200 SMA:

- Major make-or-break line.
- Above a rising 200, buying dips has priority.
- Below a falling 200, selling bounces has priority.
- Flat 200 means mean reversion and range behavior are more likely.
- Far from the 200 means reversion risk increases.

If price is above the moving averages and momentum is positive, pullbacks are buy zones.

If price is below the moving averages and momentum is negative, bounces are sell zones.

If moving averages are sideways, ignore complex divergence and trade the edges only.

## How To Use VWAP

VWAP is important, but not a standalone entry.

Rules:

- VWAP slope matters.
- Flat VWAP means no trend. Expect price to bounce above and below it.
- Sloped VWAP helps identify next likely direction.
- VWAP is often retested multiple times, so do not buy or sell VWAP blindly.
- VWAP becomes powerful when it lines up with a box edge, pivot, 50, 200, or prior level.

If you enter at VWAP in a mixed/downward structure, the target may only be the 50 SMA, not the full 1-minute opening range.

## How To Use Pivots

Use standard pivots every day.

Rules:

- Pivots are public levels, so many traders see them.
- Use pivots as relative pit stops and targets.
- A pivot that lines up with a box edge is important.
- Above R2/R3 or below S2/S3 means extended. Watch for exhaustion.
- Prior day pivots help confirm trend pressure.
- Woody's pivots can add extra levels on very extended days.
- Camarilla pivots may work better on NQ than ES, but they are not required for version 1.

Do not make Fibonacci the primary beginner tool. Anne-Marie simplified toward pivots because more people watch them.

## Momentum Rules

Momentum confirms, but does not replace structure.

Use Heikin Ashi momentum or MACD if helpful.

Rules:

- If 30-minute framework says buy-the-dip, prefer momentum above zero.
- If price is above moving averages and momentum is positive, pullbacks are buys.
- If price is below moving averages and momentum is negative, bounces are sells.
- If momentum diverges while trend is up, it usually means price is searching for support, not automatically reversing.
- If momentum diverges while trend is down, it usually means price is searching for sellers, not automatically reversing.
- Ignore divergence when moving averages are sideways because it has less information value.

## Volume And Order Flow

Volume tells you whose level matters.

Rules:

- The 9:30 1-minute candle in ES normally carries about 12,000-15,000 contracts.
- If first-minute volume is light, wait.
- If micro contract volume is unusually large while ES volume is normal, smaller speculative traders may be active.
- Large MOC volume validates institutional flow.
- If several prior highs/lows cluster, the highest-volume candle wins.
- Time and sales / DOM can show large traders defending or gaming a level, but they are optional for beginners.

Big-trade/order-flow use:

- Large buyers at a price can create a floor.
- Large sellers at a price can create a ceiling.
- If large traders appear but the 30-minute structure still points the other way, structure wins.
- Do not exit merely because a big order appears. Exit if the structure changes.

## News Candle Rules

A news candle is identified mainly by outlier volume.

Rules:

- If a mid-session candle has volume greater than the major recent 9:30 or 3:30 candles, add it to the tradable level pool.
- Keep it active while it remains the highest-volume candle in recent days.
- If the 200 SMA slopes up, the lower wick/demand area can become support.
- If the 200 SMA slopes down, the upper wick/supply area can become resistance.
- If price re-enters the news candle after the news move, the news is being faded.
- Then look for the midpoint, a box, or a pivot inside that news candle.

Do not chase news. Let the structure tell you whether the news changed the framework.

## Correlation / Temperature Gauge

Anne-Marie sometimes watches the dollar and CL against ES as a temperature gauge.

Rules:

- Dollar down with ES up is normal inverse confirmation.
- Strong correlation can justify bigger size if the setup is already right.
- If correlation breaks, resolves, and breaks again, stop using it intraday.
- CL and dollar are confirmations, not entries.

## Beginner Daily Workflow

### Before 9:30

1. Mark prior 3:30-4:00 p.m. high/low/body.
2. Mark 6:00-6:30 p.m. high/low/body.
3. Mark midnight high/low as secondary reference.
4. Mark 4:00-4:30 a.m. high/low/body.
5. Load VWAP, 50 SMA, 200 SMA, and pivots.
6. Check whether MOC volume is validated.
7. Check where price is relative to the prior 3:30 box.
8. Check whether boxes are stair-stepping, overlapping, or mixed.
9. Decide provisional day type.
10. Write down the two best support levels and two best resistance levels.

### At 9:30

1. Let the 9:30 1-minute candle close.
2. Mark its high and low.
3. Check first-minute volume.
4. If volume is light, wait for the second minute.
5. Let the 9:30-10:00 30-minute candle form for the larger map.
6. Reclassify the day after the 9:30 behavior is clear.

### Before Entry

Ask:

- Am I on a trend day or range day?
- Am I trading from an edge?
- Is the trade with the 50/200/VWAP or against them?
- What candle/box is in charge?
- If I am wrong, what price proves it?
- Where is my first target?
- Is my risk acceptable?
- Am I using a limit order?

If any answer is unclear, do not trade.

### During Trade

- Watch whether price does what your thesis requires.
- If long, support must hold and price must move toward the next resistance.
- If short, resistance must hold and price must move toward the next support.
- Do not micromanage every tick.
- If a news shock appears, ask whether the framework changed.
- If framework did not change, continue with the plan.
- If framework changed, exit or reduce.

### After Trade

- Stop trading if the planned move is complete and there is no new setup.
- Go back to the 30-minute chart and reassess.
- Do not immediately revenge trade.
- If you missed the move, wait for the next setup.

## Trade Templates

### Template 1: Clean Long Trend Pullback

Conditions:

- 6 p.m. below 4 a.m. below 9:30.
- Bodies do not overlap.
- 50, 200, VWAP slope up.
- MOC validated.

Entry:

- Buy pullback to 9:30, 4 a.m., 3:30, VWAP, 50, 200, or pivot confluence.
- Prefer look-below-and-fail confirmation.

Stop:

- Below support/failure candle.

Targets:

- Top of active candle/box.
- Next pivot.
- 100%-150% measured move.
- 200% only if slope/flow is strong.

### Template 2: Clean Short Trend Bounce

Conditions:

- 6 p.m. above 4 a.m. above 9:30.
- Bodies do not overlap.
- 50, 200, VWAP slope down.
- MOC validates downside.

Entry:

- Sell bounce to 9:30, 4 a.m., 3:30, VWAP, 50, 200, or pivot confluence.
- Prefer look-above-and-fail confirmation.

Stop:

- Above resistance/failure candle.

Targets:

- Bottom of active candle/box.
- Next pivot.
- 100%-150% measured move.
- 200% only if slope/flow is strong.

### Template 3: Sideways Range

Conditions:

- Boxes overlap.
- VWAP flat.
- 50/200 flat or crossed.
- Momentum flat.

Entry:

- Buy lower edge after support holds.
- Sell upper edge after resistance fails.

Stop:

- Beyond the edge/failure candle.

Targets:

- Opposite edge.
- Midpoint if price hesitates.
- VWAP/50/200 if those are the next crowding levels.

### Template 4: One-Minute Opening Breakdown

Conditions:

- 9:30 1-minute candle breaks lower.
- Price is below 50/200 or loses them.
- Sellers hold the 1-minute low.

Entry:

- Short failed bounce into the 1-minute opening range.

Stop:

- Above the 1-minute high or failure candle.

Targets:

- VWAP.
- 50/200.
- 4 a.m. low.
- Prior box/pivot.

### Template 5: Look Below And Fail Reversal

Conditions:

- Known support from a box, pivot, news candle, or prior high/low.
- Price breaches support.
- Price recovers support.
- Price pulls back but makes a higher low.

Entry:

- Long above the recovery candle high.

Stop:

- Low of the breach candle.

Targets:

- Next resistance, often 4 a.m., 9:30, VWAP, 50, or prior 3:30 edge.

### Template 6: Look Above And Fail Reversal

Conditions:

- Known resistance from a box, pivot, news candle, or prior high/low.
- Price breaches resistance.
- Price fails back below resistance.
- Price bounces but makes a lower high.

Entry:

- Short below the failure candle low.

Stop:

- High of the breach candle.

Targets:

- Next support, often 4 a.m., 9:30, VWAP, 50, or prior 3:30 edge.

## What Not To Do

- Do not use market orders.
- Do not chase breakouts after missing the planned entry.
- Do not trade the middle of congestion.
- Do not size up on a wide 9:30 candle.
- Do not trail stops as the default method.
- Do not scalp constantly as the base system.
- Do not countertrend unless you are intentionally taking a small scalp into a primary candle.
- Do not assume VWAP alone is an entry.
- Do not assume a news move is tradable without structure.
- Do not trade because you need action.
- Do not trade live when tired or mentally unclear.

## Open Questions / Not Fully Settled In The Transcripts

These items appeared in the transcripts but are not clean enough to make beginner rules yet.

- Exact CL adaptation. The same 6 p.m., 4 a.m., and 9:30 structures matter, but CL also has different close behavior and a possible 10 a.m. key candle. Treat ES rules as primary until CL is separately tested.
- Exact target calibration between 150%, 161.8%, 200%, and 300%. Simple rule: use 100%-150% unless slope and flow are strong.
- Exact use of the midnight candle. It matters, especially in NQ, but should remain secondary for version 1.
- Exact use of the 1:30 candle. It can act as a pullback/expansion event, but it is not required for the beginner framework.
- Two-of-three alignment trades. Anne-Marie can trade them discretionarily, but the beginner rule should require all three major candles to align.
- Machine-learning veto layer. Future automation may score and veto lower-probability setups, but the manual beginner system should remain edge-based and simple.

## Final Beginner Version

If you are new, trade only this:

1. Mark the boxes.
2. Decide trend or sideways.
3. Trade only at box edges.
4. Use 50/200/VWAP to confirm direction and size.
5. Enter only after a failed break/retest.
6. Use MES.
7. Use limit orders.
8. Place a protective stop.
9. Target the next obvious level.
10. Stop after one or two clean trades.

The system becomes powerful because it repeats the same question all day: who planted a flag, did they hold it, and where is the next crowd going if they win or fail?
