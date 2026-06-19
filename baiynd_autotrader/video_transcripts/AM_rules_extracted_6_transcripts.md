# Anne-Marie Baiynd Strategy Rules Extracted From 6 Transcripts

Source files:

- `AM_transcript_mar-6.txt` - 1039 lines
- `AM_transcript_apr-8.txt` - 407 lines
- `AM_transcript_apr-9.txt` - 581 lines
- `AM_transcript_apr-10.txt` - 407 lines
- `AM_transcript_apr_16.txt` - 488 lines
- `AM_transcript_apr-23.txt` - 155 lines

Purpose:

- Extract the complete rule inventory from the transcript set before any NinjaTrader indicator is programmed.
- Separate direct transcript facts from implementation inferences.
- Preserve ambiguities as questions instead of guessing.
- Primary scope is the intraday futures method. Earnings and stock adaptations are included separately because they were also taught in the transcripts.

Important limitation:

- This is not a final trading system. It is the extracted rule book that must be reviewed with Anne-Marie before coding.

---

## 1. Core Model

### 1.1 Big-to-small workflow

Direct rules:

- Start with the wide-angle context and collapse down to execution detail. She explicitly describes this as "big collapsed to small." Source: apr_16 L1-L6.
- The 30-minute chart frames the trade. The 1-minute chart is used for execution and rotation detail. Sources: apr-8 L93-L96, apr-9 L252-L257, apr-10 L232-L234.
- A 15-minute chart may be used visually, but it is not the core decision chart. Source: apr-10 L24-L26.
- The method is primarily about time, price, and trader behavior around specific candles, not generic indicators. Source: mar-6 L817-L825, apr-23 L12-L31.

Implementation inference:

- Ninja should run multi-timeframe logic: at least one 30-minute series for structural candles and trend context, plus a 1-minute series for entries, confirmations, alerts, and opening-minute logic.

### 1.2 Level-to-level trading

Direct rules:

- Every trade must have the exit planned before entry. Source: apr-10 L220-L223.
- The model is level A to level B, not "let's see how it goes." Sources: apr-9 L148-L151, apr-10 L220-L230.
- She does not use trailing stops as the default intraday method. Sources: apr-9 L51-L62, L148-L151.
- She does not leave runners by default. Source: apr-9 L148-L151.
- She does not chase missed trades. If the trade leaves without her, she waits for the next setup or puts a limit at a pullback level. Sources: mar-6 L568-L572, apr-9 L415-L420, apr-10 L61-L68.

Implementation inference:

- The indicator should not initially be an autotrader. It should mark levels, context, setups, invalidations, and suggested targets. Auto-execution depends on unresolved confirmation and stop questions.

### 1.3 The repeated management question

Direct rules:

- Before and during a trade, ask: if I am wrong, what will price do? Stay with the trade only while price does not do that. Source: apr-9 L534-L536.
- Trade the formation, not the P/L. Source: apr-8 L272-L275, apr-9 L232-L238, apr-10 L304-L310.
- If the market is too volatile, risk is too wide, or traders are still deciding, do not force a trade. Source: apr-9 L539-L543.

Implementation inference:

- Each signal should have an explicit invalidation condition attached. A marker without invalidation is incomplete.

---

## 2. Instruments And Time Base

### 2.1 Futures universe

Direct rules:

- She trades ES, NQ, CL, and RTY. She does not normally trade YM. Source: mar-6 L533-L536.
- CL/oil is traded often. Source: mar-6 L533-L536.
- Later pattern work also references NQ, YM, gold, and oil as instruments with separate profiles. Source: apr_16 L181-L184.
- For a 50K TopStep combine, she avoids big ES contracts and uses MES/MEES because ES risk is too large. Source: apr-10 L129-L132.

Implementation inference:

- First implementation should support ES/MES first, then NQ/MNQ, then CL, because CL has different timing rules and unresolved candle conflicts.

### 2.2 Time zone

Direct rules:

- The pattern study uses 3:30 PM, Globex open, 4:00 AM, and 9:30 AM, all Eastern time. Source: apr_16 L13-L18.
- Globex open candle is 6:00-6:30 PM Eastern. Sources: apr-8 L128-L129, apr-9 L437-L438, apr-23 L2-L4.
- The institutional closing candle for index futures is 3:30-4:00 PM Eastern. Sources: apr-8 L116-L128, apr_16 L19-L22.
- The Europe candle is 4:00-4:30 AM Eastern. Source: apr-8 L133-L135.
- The RTH 30-minute opening candle is 9:30-10:00 AM Eastern. Sources: mar-6 L545-L553, apr-8 L133-L137.
- The RTH 1-minute opening candle is 9:30-9:31 AM Eastern. Sources: apr-8 L147-L152, apr-10 L18-L19, apr-9 L441-L460.
- User clarification 2026-04-23: for ES, the 4 AM candle means the Europe open candle from 4:00-4:30 AM Eastern, and the 6 PM candle means the Globex open candle from 6:00-6:30 PM Eastern.

Implementation inference:

- Ninja must normalize all time logic to Eastern time and must not depend on the user's local computer time.

---

## 3. Required Chart Stack

### 3.1 Moving averages

Direct rules:

- Use 50 SMA and 200 SMA. They are period averages, not daily moving averages. Source: apr-8 L55-L69.
- The 50 and 200 are used on both 30-minute and 1-minute charts. Sources: apr-8 L93-L96, apr-9 L252-L257.
- The 200 SMA is treated as the most important technical reference. Sources: apr-8 L152-L157, apr-9 L300-L318.
- If price is above the 50 and 200, dips are buy zones. Source: apr-8 L145-L147.
- If price is under the moving averages and momentum is below zero, bounces are sell zones. Source: apr-9 L174-L175.
- When both 50 and 200 are going down, she takes shorts in that direction. Source: apr-8 L242-L244.
- If the 200 was upward into the day, dips into it tend to be bought even if it later flattens. Source: apr-23 L77-L81.

Ambiguity:

- She eyeballs up, down, flat, and turning. No numerical slope threshold is stated in the transcripts.

### 3.2 VWAP

Direct rules:

- Use VWAP, but do not use VWAP bands. Source: apr-8 L60-L64.
- VWAP slope matters. A flat VWAP implies no trend and oscillation above and below. Source: apr-9 L187-L195.
- Once VWAP resolves and takes slope, it points toward likely next direction. Source: apr-9 L194-L195.
- VWAP gets retested often, so buying VWAP by itself is not a rule. Source: apr-10 L204-L209.
- VWAP should be the same across timeframes; if a platform shows different VWAPs on 1-minute and 30-minute, she distrusts that platform's VWAP. Source: apr-10 L175-L178.
- VWAP can be a first target, a magnet, or part of a confluence cluster. Sources: apr-8 L173-L182, apr-10 L216-L230.

Implementation inference:

- VWAP should not be treated as a naked entry level. It can be a target, permission filter, or cluster component.

### 3.3 Pivots

Direct rules:

- Pivots are always loaded. Source: apr-9 L197-L210.
- Standard pivots are used. Source: apr-9 L198-L200.
- She also uses Woody's pivots or extended pivots when price is beyond normal levels. Source: apr-8 L97-L103.
- If price is far above pivots, e.g. near R3/R4, it is extended and exhaustion should be watched. Sources: apr-8 L97-L103, apr-9 L258-L265.
- Pivots are relative pit stops and targets. Source: apr-9 L200-L205.
- In strong trend, she does not automatically exit at a pivot because trend can carry through. Source: apr-9 L202-L205.
- In sideways trade, pivots help identify buy/sell edges when they align with shaded time boxes. Source: apr-8 L323-L326.
- Prior-day pivots help confirm the direction of trending pressure. Source: apr-9 L269-L272.
- Camarilla pivots work well on NQ but not as well on ES. Source: apr_16 L275-L282.

Ambiguity:

- The exact pivot formulas to use in Ninja need confirmation: standard, Woody, Camarilla by instrument, or all plotted with a display priority.

### 3.4 Momentum

Direct rules:

- Heikin-Ashi is used as a momentum indicator with a zero line. Source: apr-9 L166-L175.
- For buy-the-dip, she wants Heikin-Ashi positive / above zero. Source: apr-9 L170-L174.
- If price is above MAs and Heikin-Ashi is positive, pullbacks are buy zones. Source: apr-9 L170-L174.
- If price is under MAs and momentum is below zero, bounces are sell zones. Source: apr-9 L174-L175.
- Ignore divergence when moving averages are sideways. Source: apr-9 L176-L178.
- Negative divergence while the 50 is still rising means price is searching for support, not necessarily reversing. Source: apr-9 L179-L182.
- MACD is sometimes easier to read than Heikin-Ashi; she may use both for agreement, but one can be chosen. Source: apr-9 L183-L186.
- Momentum divergence can be price making higher highs while momentum fails to make higher highs; this implies momentum stalled and a pullback is likely. Source: apr-10 L94-L100.

Ambiguity:

- The exact Heikin-Ashi momentum formula and MACD settings are not in the transcripts.

### 3.5 Order flow and auxiliary gauges

Direct rules:

- Time and sales is used to infer delta volume at a price point. Sources: mar-6 L669-L674, apr-9 L152-L160.
- MotiveWave provides net delta volume per price, bid/ask dome, and big-trades heatmap. Source: apr-9 L213-L216.
- Big trades over 250 contracts at once are watched. Source: apr-9 L213-L218.
- Large buys around a price can imply an attempted floor, but trend and other indicators dominate. Source: apr-9 L220-L230, L247-L248.
- SPY 30-minute context is watched for ES because SPY has heavy volume and 0DTE positioning. Source: apr-9 L139-L145.
- Dollar and CL can be temperature gauges for ES. Stronger correlation can justify larger size if setup is right. Source: apr-8 L21-L53.
- If dollar/ES correlation breaks, resolves, then breaks again, stop using that relationship intraday. Source: apr-8 L30-L43.
- Volume profile is useful visually for extremes, but value area differs by platform. It should not be a first proof-of-concept rule. Sources: apr_16 L1-L7, L232-L263.

Implementation inference:

- The first Ninja indicator can omit true order-flow and volume-profile logic unless reliable data is available. It should leave hooks for future order-flow filters.

---

## 4. Structural Candles And Levels

### 4.1 Institutional candle

Direct rules:

- The 3:30-4:00 PM candle is the institutional or MOC candle for index futures in the later transcript discussions. Sources: apr-8 L116-L128, apr_16 L17-L22.
- It maps the rest of the next day. Sources: apr_16 L19-L22, apr-23 L16-L25.
- 9:30 is trader flow and often continuation of the prior day institutional candle. Source: apr_16 L22-L23.
- The prior 3:30 candle can be "in charge" when later candles sit inside it. Sources: apr-9 L334-L346, apr-23 L16-L25.
- If the 3:30 candle volume is at least 20% greater than the 3:00-3:30 candle volume, the MOC/institutional flow is validated. Source: apr_16 L28-L31.
- If that 20% validation fails, stops expand. Source: apr_16 L42-L45.
- UI state should show institutional flow green/red, size full/reduced/no trade as green/orange/gray. Source: apr_16 L140-L143.
- User clarification 2026-04-23: the active institutional candle is fluid. Anne-Marie said it was the 4 AM candle for months, then changed to the 3:30 PM candle. Therefore the indicator must not permanently hard-code 3:30 as the only institutional candle.
- Transcript-derived selection rule: the active/ruling candle is determined by comparing each key box to the prior/reference boxes, not by a fixed calendar date. Anne-Marie says to ask how each box compares to the box before it; if later boxes are inside or close back inside a prior box, the prior box is "in charge." Sources: apr-9 L320-L346.
- Transcript-derived current-regime rule: in the later sessions, 3:30 is dominant because it is the last major volume candle and MOC validation identifies institutional flow. Sources: apr-9 L338-L346, apr_16 L19-L31, L136-L145, apr-23 L42-L50.
- Transcript-derived former/alternate-regime rule: 4 AM can be the active box when that rhythm is holding; she says it was the important box for months, and March 6 shows 4 AM measured moves and 4 AM support/resistance as the active rhythm. Sources: apr-9 L84-L87, mar-6 L564-L588, L676-L685.

Implementation inference:

- Compute `mocVolumeRatio = Volume(15:30-16:00) / Volume(15:00-15:30)`.
- Treat `mocVolumeRatio >= 1.20` as a validation candidate.
- The direction of green/red institutional flow is not fully defined. It is likely candle direction, but this must be confirmed.
- The active institutional candle should be detected by containment/control first, with a manual override available. Candidate anchors include at least 3:30 PM, 4 AM, and sometimes 9:30.

### 4.2 Globex 6 PM candle

Direct rules:

- The 6:00-6:30 PM Eastern candle is the Globex open. Sources: apr-8 L128-L129, apr-9 L437-L438.
- It is one of the primary boxes in the sequence: 3:30, 6 PM, 4 AM, 9:30. Source: apr-9 L320-L325.
- If it opens inside the prior 3:30 candle, the prior 3:30 candle may stay in charge. Sources: apr-9 L334-L339, apr-23 L16-L19.
- If it cannot get above the 50% range of the prior closing candle, that matters. Source: apr-23 L2-L5.

Ambiguity:

- The exact 50% comparison should be specified: midpoint of high-low, body midpoint, or another range.

### 4.3 Midnight candle

Direct rules:

- Midnight high/low is plotted. Source: apr-8 L70-L76.
- Newer algorithms use the midnight candle, especially in NQ, but she did not have a hard rule initially. Source: apr-8 L129-L132.
- If the midnight candle does not break prior premarket highs, watch for failure of the midnight low and possible short back to the opening candle formation. Source: mar-6 L573-L580.
- Midnight can mark the high on some days, but if it is inside larger formations it may not matter much. Source: apr-9 L420-L435.
- It matters more in congestion when big candles matter. Source: apr-9 L420-L435.

Implementation inference:

- Plot midnight high/low as reference-only in the first version unless classifiers later prove a formal rule.

### 4.4 Europe 4 AM candle

Direct rules:

- The 4:00-4:30 AM Eastern candle is the Europe open. Source: apr-8 L133-L135.
- Its high and low matter. Source: apr-8 L133-L137.
- Above the 4 AM high, pullbacks are buy zones. Below the 4 AM low, bounces are sell zones. Source: apr-8 L135-L137.
- If 4 AM low matches prior 3:30 candle area, expect a bounce attempt, often after a shakeout. Source: mar-6 L584-L593.
- The 4 AM candle range can be duplicated up/down for measured-move targets. Source: mar-6 L676-L685.
- If the 4 AM range is not holding and wicks create excessive risk, switch to a larger structure such as the 9:30-10:30 formation. Source: mar-6 L713-L731.
- Prior 4 AM candles from 1-3 days ago may matter. Source: mar-6 L713-L731.
- The 4 AM close can be an exit target, not just high/low. Source: apr-23 L47-L50.

Ambiguity:

- Some older summaries use 4 AM candle width as stop distance. Apr_16 says 3:30 candle width. This must be resolved.

### 4.5 RTH 9:30-10:00 opening candle

Direct rules:

- The 9:30-10:00 candle is the regular-hours 30-minute opening box. Sources: mar-6 L545-L553, apr-8 L133-L137.
- Its high/low are important. Sources: mar-6 L545-L553, apr-8 L133-L137.
- If 9:30 sits inside the prior 3:30 candle, the 3:30 remains in charge and you wait for a break. Source: apr-9 L344-L346.
- If the 10:00 candle engulfs the 9:30 candle, draw a line at the bottom of it. Source: mar-6 L545-L553.
- If price loses a news candle, a likely target is the prior 9:30 candle. Source: mar-6 L610-L614.
- If price looks below initial balance and returns above it, initial-balance traders may try to go long into the first pivot. Source: apr_16 L172-L175.

### 4.6 RTH 9:30-9:31 one-minute opening candle

Direct rules:

- Let the first 1-minute RTH candle complete before using it. Source: apr-8 L147-L152.
- Draw high/low around it. Sources: apr-8 L147-L152, apr-9 L441-L460.
- The 9:30-9:31 candle plants the flag for the day. Source: apr-10 L18-L19.
- If opening range is more than 10 ES points, use only one MES/MEES and do not size up. Sources: apr-8 L167-L170, apr-9 L92-L93.
- ES normal first-minute volume is around 12,000-15,000 contracts, with 15,000 as an important benchmark. Source: apr-9 L101-L111.
- NQ normal first-minute volume is around 6,000 contracts. Source: apr-9 L119-L121.
- Low first-minute volume means tentative traders. Wait for the second minute to add information. Source: apr-9 L105-L110.
- If the second minute is inside the first minute, it confirms the first-minute range. Source: apr-9 L107-L110.
- First-minute volume is not a standalone decision factor, except it tells you not to jump into a breakout/breakdown too early. Source: apr-9 L123-L127.
- If price is below and cannot recover into the 1-minute low, sellers remain in control and breakdown can continue. Source: apr-10 L209-L213.
- If price cannot get inside the one-minute opening candle and stay there, shift temperament toward downside rotation. Source: apr-10 L393-L397.

### 4.7 10:00-10:30 candle

Direct rules:

- The 10:00-10:30 low can become repeat support/target. Source: mar-6 L629-L633.
- If price cannot regain the 10 AM candle after stalling and losing 1:30, do not buy except possibly a five-minute scalp. Source: mar-6 L741-L748.
- The 9:30 and 10:00 candles may be measured together for projections. Source: mar-6 L649-L652.

### 4.8 1:30 candle

Direct rules:

- The 1:30 candle high/low is watched. Sources: mar-6 L545-L553, apr_16 L123-L135.
- It can be a pullback event or expansion event. Source: apr_16 L126-L132.
- It matters when there is a retracement event that creates dip-buying formation. Source: apr_16 L132-L135.
- If price holds the 1:30 candle and prior institutional flow exists, it may go to the top of the 9:30 candle. Source: apr_16 L134-L146.
- If price cannot get back over the top of the 1:30 candle after losing it, target can become the bottom of the 1:30 candle. Source: mar-6 L600-L609.
- Turnarounds may occur near the 1:30 candle after a shakeout around 4 AM / 3:30 confluence. Source: mar-6 L584-L593.

Ambiguity:

- Confirm whether "1:30 candle" means the candle opening at 1:30 PM or the candle closing at 1:30 PM.

### 4.9 Pre-market high/low

Direct rules:

- Pre-market high/low are used in decisions and targets. Source: mar-6 L573-L580, apr-23 L37-L50.
- On Apr 23, she covered a short at the pre-market low and then looked for a long. Source: apr-23 L37-L50.

Implementation inference:

- Add named pre-market high and low levels using the overnight session from 6:00 PM through 9:29 AM ET, unless Anne-Marie defines a narrower range.

### 4.10 Multi-day lookback levels

Direct rules:

- She uses T-3 context: examine the last three days. Source: mar-6 L826-L834.
- If the last three days are boxed, inventory is building. Source: mar-6 L826-L834.
- Prior 4 AM candles from 1-3 days ago may matter. Source: mar-6 L713-L731.
- Apr 23 long referenced the 30-minute low from two days earlier. Source: apr-23 L88-L92.

Implementation inference:

- Track prior structural 30-minute highs/lows for at least three days, not just the immediately prior 30-minute bar.

---

## 5. Day-Type And Regime Classification

### 5.1 Three-candle sequence rule

Direct rules:

- For a long, the 6 PM candle must sit below the 4 AM candle, and the 4 AM candle must sit below the 9:30 candle. Source: apr-23 L60-L64.
- For a short, the 6 PM / Globex candle must sit above the 4 AM candle, and the 4 AM candle must sit above the 9:30 candle. Source: apr-23 L60-L64.
- Otherwise it is sideways and you trade a range. Source: apr-23 L60-L64.
- All three have to converge in the right direction. Source: apr-23 L60-L64.
- If all candles are not moving in sequence, it is choppy and becomes mean reversion. Source: apr-23 L29-L31.
- User clarification 2026-04-23: "sits below" means full-candle separation. For long sequence, the 6 PM high must be below the 4 AM low, and the 4 AM high must be below the 9:30 low. User also confirmed the short-side symmetry as the working rule: the 6 PM low must be above the 4 AM high, and the 4 AM low must be above the 9:30 high.

Implementation inference:

- This should be the primary day-type classifier. The ES long and short sequence comparisons are now clarified as full high-low candle separation.

### 5.2 Containment / in-charge rule

Direct rules:

- Compare each box to the prior/reference box. Source: apr-9 L320-L333.
- If 6 PM is inside prior 3:30, inside prior 9:30, and touching 4 AM range, do nothing; the prior 3:30 is the last major volume candle to watch. Source: apr-9 L334-L339.
- If 4 AM closes inside 3:30, 3:30 is in charge. Source: apr-9 L340-L343.
- If 9:30 sits inside prior 3:30, 3:30 remains in charge; wait for break above or below. Source: apr-9 L344-L346.
- Opening inside the prior 3:30 closing formation means same battleground and likely wash-rinse-repeat until a break. Source: apr-23 L16-L25.
- Which box is most important can change over time: 4 AM was important from about October to early March; later it was generally 3:30 PM, but it can also be 9:30. Source: apr-9 L84-L87.
- If the 4 AM rhythm/range is not holding and the wicks create excessive risk, switch to a larger structure such as the 9:30-10:30 formation. Source: mar-6 L713-L731.
- If the boxes are not running in sequence, classify the day as choppy/mean-reversion rather than forcing a trend read. Source: apr-23 L29-L31.

Implementation inference:

- The active range should default to the candle whose high-low range contains the later important candles, with institutional candle priority when validated by volume.
- Practical detection order for ES: first test the three-candle sequence for clean long/short day; if sequence fails, use containment to find the in-charge range; if 3:30 contains later boxes or has validated MOC volume, treat 3:30 as in charge; if 4 AM measured moves and support/resistance are holding better than 3:30 and risk is acceptable, treat 4 AM as active; if neither is holding cleanly, move to the larger 9:30-10:30 structure.

### 5.3 Trend context and sideways context

Direct rules:

- If prior close 30-minute candle and current opening 30-minute candle overlap/on top of each other, traders are fighting about it. Source: apr-8 L289-L294.
- Overlapping boxes imply inventory accumulation. Source: apr-9 L291-L293.
- Flat VWAP, flat moving averages, flat momentum, falling volume, and no new opening-range high suggest sideways/chop. Source: apr-8 L214-L220, L313-L319.
- In heavy congestion, dips are buys and spikes are sells. Source: apr-8 L316-L319.
- In sideways conditions, trade both directions: short old highs and long old lows. Source: apr-23 L151-L154.

Implementation inference:

- Sideways is not a no-trade state. It is a different playbook.

---

## 6. Bias And Permission Gates

### 6.1 Moving-average permission

Direct rules:

- Above 50 and 200 on a bullish day means dips are buys. Source: apr-8 L145-L147.
- Under moving averages means bounces are sell zones. Source: apr-9 L174-L175.
- If 200 and 50 disagree or one is flat, this is cross-current / weaker trend and should reduce size rather than automatically create full permission. Sources: mar-6 L581-L584, apr-8 L230-L236.
- If price is far from a flat 200, reversion toward the 200 is likely. Source: apr-8 L246-L249.

### 6.2 VWAP permission

Direct rules:

- Flat VWAP means sideways/no trend. Source: apr-9 L187-L195.
- VWAP slope resolving gives direction. Source: apr-9 L194-L195.
- If VWAP is inside the prior 3:30 candle, price is at a crowded watering-hole area. Source: apr-10 L216-L219.

### 6.3 Pivot permission

Direct rules:

- Above anchored/daily pivot means think long. Below it means think short or short into support if sideways. Source: mar-6 L817-L825.
- If primary pivot is lost, downward pressure is present. Source: mar-6 L676-L685.
- Pivots identify buy areas when they mesh with shaded events. Source: apr-8 L323-L326.

### 6.4 Momentum permission

Direct rules:

- Heikin-Ashi above zero supports buy-the-dip. Source: apr-9 L166-L175.
- Heikin-Ashi below zero with price under MAs supports sell-the-bounce. Source: apr-9 L174-L175.
- Divergence is ignored in sideways MA conditions. Source: apr-9 L176-L178.

### 6.5 External context permission

Direct rules:

- Dollar down can confirm bullish ES action. Source: apr-10 L21-L23.
- If dollar/ES inverse relationship breaks, resolves, then breaks again, stop using it intraday. Source: apr-8 L30-L43.
- SPY can inform ES direction because SPY has more volume and 0DTE positioning. Source: apr-9 L139-L145.
- Call-wall levels can act as magnets until price clearly escapes the range. Source: apr-10 L48-L53.

Implementation inference:

- External context should be advisory in the first indicator unless reliable symbols/data feeds are guaranteed.

---

## 7. Entry Rules

### 7.1 Universal entry rules

Direct rules:

- Use limit orders only, not market orders. Source: apr-9 L94-L99.
- Market orders can get destroyed in thin books. Source: apr-9 L94-L99.
- Do not chase. Sources: mar-6 L568-L572, apr-10 L61-L68, apr-9 L415-L420.
- Go where the crowding is, not where the market already ran. Source: apr-10 L61-L62.
- Entry must have risk and destination already thought through. Sources: apr-10 L220-L230, L247-L253.
- If the setup is forming, the order can wait at the level. Source: mar-6 L581-L584.
- On volatile/savage days, wait for confirmation instead of blindly pre-placing. Source: apr-23 L88-L92.

Implementation inference:

- Entries should be stateful: context detected, setup armed, level tagged, confirmation passed or failed, suggested entry, invalidation, target.

### 7.2 Long-day execution

Direct rules:

- Long day setup described on Apr 23: 3:30 formation into Globex; if Globex is a dip, 4 AM is higher than Globex, premarket gets into old 3:30, then 9:30 opens and breaks above, it is a long. Source: apr-23 L12-L15.
- In bullish context, buy the dip, but the exact dip is chosen by risk. Source: apr-10 L7-L13.
- Candidate long areas include prior 3:30/institutional low, 4 AM low, midnight low, VWAP/200 confluence, pivot, pre-market low, and multi-day prior 30-minute lows. Sources: apr-10 L41-L57, apr-23 L45-L50, apr-23 L88-L92.
- If price comes into an upward-sloping 200, dips tend to be bought. Source: apr-23 L77-L81.
- If price holds the 1:30 candle with institutional flow, it is likely to go to the top of the 9:30 candle. Source: apr_16 L134-L146.
- If price gets above the 50 and recovers pivot, it can walk back up the 4 AM candle. Source: apr-8 L221-L226.

Implementation inference:

- Long entries should occur on retracement to a structural support level, not on random bullish movement.

### 7.3 Short-day execution

Direct rules:

- Short sequence: Globex/6 PM sits above 4 AM, and 4 AM sits above 9:30. Source: apr-23 L60-L64.
- If 9:30 opened below the 4 AM candlestick, she described it as a short on the bounce. Source: apr-23 L20-L21.
- Below the 4 AM low, bounces are sell zones. Source: apr-8 L135-L137.
- If opening candle fails below and is under 50/200, wait for failed bounce and short the retest into opening range. Source: apr-8 L158-L170.
- If moving averages are above price, stop goes just over the one-minute high. Source: apr-8 L170-L173.
- If price looks above but cannot regain the 30-minute candle low, it is a short. Source: mar-6 L600-L609.

Ambiguity:

- The exact short entry level for full-sequence short needs confirmation: 9:30 low, 4 AM low, or bounce into the 4 AM candle.

### 7.4 Sideways execution

Direct rules:

- If the three key candles do not run in sequence, it is mean reversion. Source: apr-23 L29-L31.
- In sideways, trade a range. Source: apr-23 L60-L64.
- In sideways, short old highs and long old lows. Source: apr-23 L151-L154.
- Establish edges, buy one edge, sell the next edge. Source: apr-9 L407-L414.
- In heavy congestion, dips are buys and spikes are sells. Source: apr-8 L316-L319.
- If price breaks above Globex high but cannot hold it, expect it to walk down boxes. Source: apr-8 L319-L323.
- Box walkdown may be 3:30/bottom of Globex, then 4 AM, then 9:30. Source: apr-8 L319-L323.
- On Apr 23, she shorted a topping/heavy congestion formation, covered near premarket low, then looked for long. Source: apr-23 L25-L50.
- In a sideways environment, she gave the short some room because participants were gaming each other. Source: apr-23 L67-L75.

Implementation inference:

- Sideways mode needs both long and short alerts. It should not be filtered out just because trend state is neutral.

### 7.5 Opening one-minute short pattern

Direct rules:

- Let first 1-minute RTH candle complete. Source: apr-8 L147-L152.
- If it breaks below and is under all moving averages, expect move to next support layer or next moving average. Source: apr-8 L158-L161.
- If it is sitting below 200 and 50 and fails, wait for failed bounce and short the retest into the opening range. Source: apr-8 L165-L170.
- If the 1-minute opening range is more than 10 points, use one MES/MEES only. Source: apr-8 L167-L170.
- Stop for the short goes just above the top of the 1-minute high if moving averages are above price. Source: apr-8 L170-L173.
- Stay short until VWAP, a measured target, or both are tested. Source: apr-8 L173-L182.
- A second move up can be an add if risk is defined and same stop is valid. Source: apr-8 L175-L181.

### 7.6 Look-above/look-below-and-go

Direct rules:

- "Look below and go": price looks below, bounces, fails to clear the candle of measure, then becomes short when it loses the low. Source: mar-6 L573-L580.
- "Look above and go": price breaks out, pulls back, cannot get back inside the candles, then heads in the direction of the break. Source: mar-6 L638-L648.
- If price breaks back inside the candles after breakout, exit. Source: mar-6 L638-L648.

Implementation inference:

- This is a breakout-retest-continuation pattern, not a raw breakout chase.

### 7.7 Breakout rules and exceptions

Direct rules:

- Raw breakout entries are possible, but risk can be large and she often rejects them. Source: apr-10 L63-L68, L118-L125.
- In sideways, a break of prior 3:30 high/low can create directional flow. Source: apr-9 L129-L137.
- Breach of 9:30-10:00 high can be the trend-break/breakout trigger. Source: mar-6 L638-L648.
- If missed, do not chase; wait for pullback or skip. Sources: mar-6 L568-L572, apr-9 L415-L420.

### 7.8 Pre-open timing windows

Direct rules:

- Algos may position around 9:02, 9:04, 9:14-9:18, and 9:24-9:27 before the open. Source: apr-10 L13-L19.

Implementation inference:

- These should be visual awareness windows, not hard entry triggers, until validated.

---

## 8. Stop, Risk, And Size Rules

### 8.1 Universal risk rules

Direct rules:

- Manage risk first and reward later. Source: apr-10 L10-L13.
- If max drawdown target cannot be met by the entry, do not take the trade. Source: apr_16 L74-L81.
- If risk is too wide, price too volatile, or traders still deciding, stand aside. Source: apr-9 L539-L543.
- Avoid illiquid/gappy markets, wide bid/ask, and poor depth. Source: mar-6 L769-L775.
- She always trades small relative to risk; usually no more than two or three ES at a time. Source: mar-6 L757-L768.
- In TopStep 50K combine, do not use big ES; use MES/MEES. Source: apr-10 L129-L132.
- Start with MES/MEES and about $50 maximum stop-loss per contract when learning. Source: apr-9 L552-L554.
- Size up only after the mechanical flow is established. Source: apr-9 L548-L558.

### 8.2 Size reduction conditions

Direct rules:

- Countertrend trades use smaller size until the pattern breaks. Source: mar-6 L581-L584.
- If the 1-minute opening range is more than 10 ES points, use one MES/MEES and do not size up. Source: apr-8 L167-L170.
- Bonkers price action/statistical framework can reduce size; Apr 23 she traded one contract because size was reduced. Source: apr-23 L67-L75.
- Reduced size can mean half size or one-third size. Source: apr_16 L158-L160.
- Full/reduced/no-trade states are intended for UI: green/orange/gray. Source: apr_16 L140-L143.

Ambiguity:

- The exact rule for choosing half size versus one-third size is not stated.

### 8.3 Stop placement

Direct rules:

- Short stop in earnings setup is top of the earnings candle. Source: mar-6 L396-L398.
- Intraday short stop can be just above the one-minute opening high. Source: apr-8 L170-L173.
- Intraday long stop can be just under the wick/level. Source: mar-6 L669-L674.
- A short around a candle failure can use a stop halfway up that candle. Source: mar-6 L600-L609.
- In Apr 10 live setup, risk for two long limits was about 7-8 points on one and 4 points on the other, with risk around 57. Source: apr-10 L80-L89.
- She may not physically place a hard stop if account room allows, but the invalidation/risk is still thought through. Source: apr-10 L84-L89.
- Apr_16 says if market is validated, stop size is the width of the 3:30 candle. Source: apr_16 L161-L168.

Conflict:

- Older summaries and some prior implementation notes used 4 AM candle width as stop distance. Apr_16 directly says 3:30 candle width. This is a top clarification.

### 8.4 Daily trade management

Direct rules:

- Typical frequency is one setup, two to three trades per day max. Source: apr-8 L262-L264.
- On very defined sideways range, she may trade it five or six times, but max is usually five. Source: apr-10 L161-L168.
- Some days she does not trade at all. Source: apr-10 L168-L170.
- Apr 23 she was done after two trades. Source: apr-23 L50-L53.
- A $300-ish single big-contract win can be enough to be done for the day. Source: apr-10 L329-L337.
- No averaging down when losing is consistent with the professional desk rule she described. Source: apr-9 L300-L318.

Implementation inference:

- Indicator should support configurable hard cap of five trades/day, optional "done after 2 winners in sideways", and optional daily target advisory.

---

## 9. Exit Rules

### 9.1 Universal exits

Direct rules:

- Exit level-to-level. Source: apr-9 L148-L151.
- No default trailing stop. Sources: apr-9 L51-L62, L148-L151.
- Target is the next structural level in the trade direction. Sources: apr-10 L220-L230, apr-23 L47-L50.
- If worried about giving back gains, move stop to breakeven and leave the room; this is an emotional management concession, not the main edge. Source: apr-8 L186-L188.

### 9.2 Common target types

Direct rules:

- VWAP can be a first target for an opening short/trend retracement. Source: apr-8 L173-L182.
- 4 AM candle edge/low can be a target if it mattered intraday. Source: apr-8 L181-L184.
- 4 AM candle close can be a target. Source: apr-23 L47-L50.
- Pivot can be a target. Sources: mar-6 L554-L557, apr-8 L181-L188.
- Prior 9:30 candle can be a target if news candle is lost. Source: mar-6 L610-L614.
- Top/bottom of 1:30 candle can be a target after a failure. Source: mar-6 L600-L609.
- Premarket low can be a target/cover area. Source: apr-23 L37-L40.
- If entering at VWAP after one-minute low is lost, target may be the 50 because the 50 is the real boundary. Source: apr-10 L254-L266.
- If entering deep support/watering-hole area, target can be the low of the one-minute opening candle. Source: apr-10 L220-L230.

### 9.3 Confluence exit

Direct rules:

- If 30-minute opening low, VWAP, 50, and 200 are jammed inside the 4 AM candle, that is a place to get out. Source: apr-23 L82-L86.
- The longer price sits in such a cluster, the less likely the hoped-for extension becomes. Source: apr-23 L85-L86.
- When price has lower lows/lower highs and cannot get through the 50, taking the position off at the 50 is valid. Source: apr-10 L329-L335.
- If price cannot break the 50 after a lower objective, downside/back-to-box-bottom remains likely. Source: apr-10 L304-L306, L329-L333.

Implementation inference:

- Add a "confluence exit" alert when three or more major levels cluster within a configurable tick band and price stalls.

### 9.4 Thesis invalidation

Direct rules:

- If the formation has not changed, a news shock can be ignored. Source: apr-10 L357-L389.
- If price cannot get inside and stay inside the one-minute opening candle, shift toward downside rotation. Source: apr-10 L393-L397.
- If price breaks past the 50, it must breach the one-minute opening low or buyers lack strength and the day may chop sideways. Source: apr-10 L397-L401.
- If 4 AM rhythm is no longer holding and wicks create too much risk, switch to a larger range. Source: mar-6 L713-L731.
- Stay in trend while candles of note keep creating higher lows/lower highs in the trade direction; exit when that structure breaks. Source: mar-6 L733-L740.

---

## 10. Measured Moves And Range Projection

Direct rules:

- Duplicate the 4 AM candle range to generate measured-move targets. Source: mar-6 L676-L685.
- If primary pivot is lost, duplicate the range downward toward support level 1. Source: mar-6 L707-L709.
- The 9:30 and 10:00 30-minute candles can be measured and walked up/down. Source: mar-6 L649-L652.
- If the 4 AM measured rhythm is not holding, use a larger structure such as the 9:30-10:30 formation. Source: mar-6 L713-L731.
- In T-3 boxed inventory, measured move defines distribution/top/support/resistance. Source: mar-6 L826-L834.

Ambiguity:

- "Walk it up by the 50s and 200s" is unclear: it may mean Fibonacci 50%/200%, price handles, or duplicated ranges. Source: mar-6 L649-L652.

---

## 11. News Candles

Direct rules:

- News candles matter, but she generally does not trade the news headline itself. Sources: mar-6 L610-L614, apr-23 L33-L52.
- If price loses a news candle, expected target can be the prior 9:30 candle. Source: mar-6 L610-L614.
- For a news candle, check volume and whether price is above it or inside it. Source: apr-9 L372-L375.
- If price moves inside the news candle, the news is being faded. Source: apr-9 L372-L377.
- A Fibonacci midpoint of a news candle may matter if it aligns with one of the boxes. Source: apr-9 L375-L377.
- Thin volume pocket from a short squeeze means look for prior-day boxes or pivots that should hold. Source: apr-9 L378-L381.
- On Apr 10, a news shock dropped the market, but the formation did not change because price retraced and held the anticipated 30-minute area. Source: apr-10 L357-L389.

Implementation inference:

- First version should treat large news candles as visual/alert events unless a reliable news or volatility-spike detector is added.

---

## 12. Instrument-Specific Rules

### 12.1 ES / MES

Direct rules:

- ES is primary. Source: apr-8 L45-L53.
- First-minute RTH volume benchmark is 12,000-15,000, around 15,000. Source: apr-9 L101-L111.
- Opening 1-minute range over 10 ES points requires reduced size, one MES/MEES. Source: apr-8 L167-L170.
- In TopStep 50K combine, use MES/MEES rather than ES. Source: apr-10 L129-L132.

### 12.2 NQ / MNQ

Direct rules:

- NQ first-minute volume benchmark is around 6,000. Source: apr-9 L119-L121.
- Midnight candle matters especially in NQ due to newer algorithms. Source: apr-8 L129-L132.
- Camarilla pivots work well on NQ. Source: apr_16 L275-L282.

### 12.3 CL / oil

Direct rules:

- CL is traded often. Source: mar-6 L533-L536.
- Oil does not use the 3:30 candle the same way because oil closes earlier; March 6 says use the 2:00-2:30 candle/close area. Source: mar-6 L776-L785.
- If oil trend and momentum are up, take breakout above the relevant close/4 AM structure and ride it while the 4 AM low holds. Source: mar-6 L776-L785.
- Apr_16 says oil's king/institutional candle is the 10:00 AM candlestick because oil positions after the regular-hours opening range. Source: apr_16 L185-L190.

Conflict:

- CL has two different extracted references: 2:00-2:30 close logic and 10:00 AM institutional candle. This must be clarified before coding CL.

### 12.4 RTY, YM, gold

Direct rules:

- RTY is in her traded universe. Source: mar-6 L533-L536.
- YM is not normally traded by her. Source: mar-6 L533-L536.
- Apr_16 references separate patterns for NQ, YM, gold, and oil, but not full rules. Source: apr_16 L181-L184.

Implementation inference:

- Do not assume ES rules transfer unchanged to all futures. Instrument profiles are needed.

---

## 13. Stock And Earnings Rules

These are separate from the intraday futures indicator but were directly discussed.

### 13.1 Post-earnings drift

Direct rules:

- Instruments already in trend generally report in trend. Source: mar-6 L371-L377.
- Post-earnings drift becomes clear within about five days, generally 5-7 days after earnings. Source: mar-6 L371-L377.
- Use daily candles for earnings trades, especially in high volatility; weekly candles are also used. Source: mar-6 L386-L391.
- If a company reports after market close, the following day is the highlighted earnings candle with high and low. Source: mar-6 L386-L391.
- Timing often uses T+2: wait two days, and on day three act if price has moved outside the earnings candle/box. Source: mar-6 L389-L407.
- If price closes inside the earnings candle range, under high and above low, do nothing. Source: mar-6 L447-L451.
- For bullish action after earnings, she wants price to close above the prior earnings candle and close a day there; execute at beginning of next day after the candle close. Source: mar-6 L467-L475.

Ambiguity:

- There is a conflict between waiting until day three and acting day after earnings if price is already outside the box. Source: mar-6 L421-L429.

### 13.2 Earnings direction and targets

Direct rules:

- If sideways and price falls out below the earnings candle by day three, short into support. Source: mar-6 L392-L403.
- Short stop is top of the earnings candle. Source: mar-6 L396-L398.
- Short target is bottom of support or the next candlestick formation. Source: mar-6 L396-L398.
- If price pops out of a sideways earnings structure, it tends to move to a prior earnings event/candle area and then come back in. Source: mar-6 L399-L403.
- If next earnings candle opens outside a multi-quarter box and remains outside by day three, take the trade in breakout direction. Source: mar-6 L404-L414.
- Measured move can be the congestion range projected from breakout. Source: mar-6 L404-L414.
- The drift often fades after 5-7 days. Source: mar-6 L411-L414.
- Trend remains valid while prior weekly lows hold. Source: mar-6 L430-L437.

### 13.3 Earnings option structure

Direct rules:

- Use Trade Wave seasonality around the earnings window to choose structure. Source: mar-6 L415-L420.
- Flat seasonality can imply iron condor. Source: mar-6 L415-L420.
- Upward seasonality can imply bull put spread / credit spread. Source: mar-6 L415-L420.
- Downward seasonality can imply bear call spread. Source: mar-6 L415-L420.
- IV percentile determines premium choice: cheap IV means buy premium; expensive IV means sell premium. Source: mar-6 L438-L444.
- Conservative expression can be buy stock and sell covered call. Source: mar-6 L461-L466.
- Moderate risk can be call spread or short put spread. Source: mar-6 L461-L466.
- High risk can be long calls or short puts. Source: mar-6 L461-L466.

Ambiguity:

- The risk-tier explanation includes a self-correction around selling puts plus buying calls. Needs confirmation before programmatic labeling.

### 13.4 Earnings scanning

Direct rules:

- Scan top 20 or top 50 stocks. Source: mar-6 L481-L489.
- Set alert if price closes above earnings-candle high or below earnings-candle low. Source: mar-6 L481-L489.
- Use Trade Wave weeklies as a major filter. Source: mar-6 L481-L489.
- When hundreds report, focus on the five highest market-cap companies reporting that day and generate a story. Source: mar-6 L492-L500.
- Proposed metrics include average return 10 days before and 10 days after earnings; possibly test 10/20-day windows and find statistically useful windows. Source: apr_16 L360-L374.

### 13.5 Intraday stock adaptation

Direct rules:

- Same structural motion may apply to stocks because the method is based on volume for intraday motion. Source: apr-23 L138-L149.
- For stocks, she mentions three candles, primarily two candles, for regular events. Source: apr-23 L117-L118.
- Holding the high of the prior 30-minute close mattered in her stock example. Source: apr-23 L117-L119.
- In the Avis example, next day broke above 30-minute opening, lost it, fell under the 50, then lost the 30-minute low; that opened the floodgates for short. Source: apr-23 L120-L129.
- Before the break, nothing told her to go short. Source: apr-23 L126-L129.
- Possible stock target was a prior breakaway formation. Source: apr-23 L136-L137.

Implementation inference:

- Stock adaptation should be a later module, not the first Ninja futures indicator.

---

## 14. Indicator Requirements Inferred From Rules

### 14.1 Required plots

- Active institutional candle high, low, midpoint, close, and volume status, with 3:30 PM and 4 AM supported at minimum.
- 6:00-6:30 PM Globex candle high/low/body.
- Midnight candle high/low.
- 4:00-4:30 AM Europe candle high/low/close and projected measured moves.
- 9:30-10:00 RTH opening candle high/low.
- 9:30-9:31 first-minute high/low and range.
- 10:00-10:30 high/low.
- 1:30 candle high/low.
- Premarket high/low.
- Prior three days' key 30-minute highs/lows, especially prior 3:30 and 4 AM levels.
- Standard pivots, optional Woody's extended pivots, optional Camarilla for NQ.
- 50 SMA and 200 SMA on 30-minute and 1-minute views.
- VWAP without bands.
- Optional Heikin-Ashi/MACD panel or status.

### 14.2 Required status labels

- Day type: LONG, SHORT, SIDEWAYS, WAIT/UNCLASSIFIED.
- Active/in-charge candle: 3:30, 6 PM, 4 AM, 9:30, or other.
- Institutional validation: green/full, orange/reduced, gray/no trade.
- MOC volume ratio.
- Trend permission: bullish, bearish, cross-current, flat.
- VWAP regime: up, down, flat.
- Opening minute volume status: normal, light/tentative, outsized.
- Risk state: acceptable, reduced-size, too-wide/no-trade.
- Setup state: context, armed, tagged, confirmed, invalidated, target reached.

### 14.3 Required alerts

- Prior 3:30 high/low breach.
- 9:30 high/low breach.
- First-minute high/low breach/reclaim.
- Price entering active support/resistance cluster.
- Confirmation reclaim/rejection after tag.
- Confluence exit cluster.
- Formation changed / invalidation.
- Too much risk / no-trade state.

Ambiguity:

- Whether repeated alerts should fire at the same level or only one alert per setup/day is not resolved.

---

## 15. High-Priority Open Questions

These are ordered by implementation blocker priority. Ask them one at a time.

1. Resolved 2026-04-23: for ES, the long/short three-candle sequence uses full high-low candle separation.
2. Resolved 2026-04-23: the institutional candle is fluid, not always 3:30. It was the 4 AM candle for months, then changed to 3:30 PM. Need rule for detecting which candle is active.
3. What defines green/red institutional flow: close vs open, close vs prior close, delta, body direction, or another rule?
4. Is MOC validation simply `3:30 volume >= 1.20 * 3:00 volume`, or does a 60-day percentile/z-score also decide validation?
5. If MOC is not validated, should the indicator mark reduced size, no trade, wider stop, or all of those?
6. Reduced size can be half or one-third. What decides half versus one-third?
7. Stop width conflict: should futures stop distance use the 3:30 institutional candle width, the 4 AM candle width, or whichever candle is in charge?
8. What does "holds" mean mechanically: intrabar touch and bounce, one-minute close back above/below, two closes, minimum ticks, or time at level?
9. On volatile days, what confirmation did she wait for when level was 7085 and entry was 7092?
10. For a full short-sequence day, what exact level is the first short trigger: 9:30 low, 4 AM low, Globex low, or bounce into a broken level?
11. For "short on the bounce," bounce to what: 4 AM low, 4 AM close, candle midpoint, or another level?
12. What numerical slope threshold defines 50 SMA and 200 SMA as up, down, or flat?
13. Is 200 SMA slope latched near the open for the whole day, while 50 SMA updates live?
14. What exact VWAP session/anchor should Ninja use: RTH-only, ETH daily reset, or platform default?
15. What pivot formulas should be plotted by default: standard, Woody's, Camarilla, or instrument-specific?
16. What qualifies as "inside" or "partially inside" another candle: full high/low containment, body containment, close-only, or tolerance-based?
17. What is the lookback limit for old highs/lows in sideways mode: prior day, three days, five days, or more?
18. Should premarket high/low be a standalone level, and what exact time range defines premarket?
19. What is the mechanical rule for "heavy congestion" and "topping formation"?
20. What threshold defines "too volatile" or "risk too wide"?
21. How should the confluence exit be coded: how many levels, within how many ticks, and does it require price stalling for N bars?
22. What is the first target priority: next structural level, pivot, VWAP, 50 SMA, active candle edge, or closest level in trade direction?
23. Should the midnight candle be only a reference plot in version one, or does it need formal signal rules now?
24. Should time-and-sales/delta and big-trade thresholds be part of version one, or later?
25. For CL, is the special institutional candle the 2:00-2:30 close area or the 10:00 AM candle?
26. For CL, should the three-candle sequence still use 6 PM / 4 AM / 9:30, or 6 PM / 4 AM / 10 AM?
27. What exactly does "walk it up by the 50s and 200s" mean in measured moves?
28. For earnings, should entry wait until T+2/day three, or can the day-after-earnings breakout be acted on immediately if already outside the box?
29. For earnings, should alerts be close-based only, intraday breach, or both?
30. What IV percentile thresholds define cheap versus expensive premium?

---

## 16. Rules That Should Not Be Coded Yet

- Anchored VWAP from the institutional candle unless Anne-Marie confirms it; it appears in prior summaries/pipeline work, not clearly in the six transcripts.
- Automated market orders.
- Volume-profile value area logic, because platforms compute it inconsistently.
- Full CL rules until the 2:00-2:30 vs 10:00 AM conflict is resolved.
- Fully automated entries until "holds", "confirmation", "sits below", and stop width are clarified.
- Earnings option strategy automation until IV thresholds and T+2 versus day-one breakout are clarified.
