# AM Method — Manual Trading Playbook
### For Afshin | ES Futures (MES/SIM) | V2_4 Panel | 2026-04-27

> **How to use this document:** Read Section 1 (the Morning One-Pager) before 9:00 ET every day — it is designed to be printed and taped to your monitor. Read Sections 2–8 once per week until they are second nature. When you feel doubt mid-session, go directly to Section 8.

---

## SECTION 1 — MORNING ONE-PAGER (Print This Page)

*Complete this checklist top-to-bottom. Every checkbox must be answered before you place a single order.*

---

### STEP 1 — Read the Body Stack (the four boxes, in order)

The **body stack** is AM's core day-type diagnostic. Four 30-minute reference candles — called "boxes" — tell you what the institutional participants decided to do with price. You read them like stairs. If they stair-step in one direction, you have a trend. If any two boxes overlap each other (bodies, not wicks), you have a sideways day.

The four boxes in order:

| Label | What it is | Where on V2_4 |
|-------|-----------|---------------|
| **A** | Prior-day Institutional Candle (3:30–4:00 PM ET yesterday) | Displayed as "INSTITUTIONAL" box — the boldest shaded box |
| **B** | GlobEx Candle (6:00–6:30 PM ET yesterday) | "GLOBEX 6PM" box |
| **C** | Europe Candle (4:00–4:30 AM ET today) | "EUROPE 4AM" box |
| **D** | RTH Open Candle (9:30–10:00 AM ET today) — not final until 10:00 | "RTH 9:30" box |

**The body-stack rule:** Compare bodies (open-to-close range), NOT wicks.
- `[ ] A body entirely below B body, B below C, C below D` → **LONG TREND day**
- `[ ] A body entirely above B body, B above C, C above D` → **SHORT TREND day**
- `[ ] B below C and C below D (three-link chain, A is context only)` → also usable as **LONG TREND**
- `[ ] Any two adjacent boxes overlap (bodies touch or cross)` → **SIDEWAYS day**

**The body-stack mental model — "A to D, do they stair-step?"**
Imagine you're looking at a staircase from left to right. A is the bottom step, D is the top. Each step must be clearly higher (or lower) than the one before — no two steps can sit at the same height. If any two steps overlap, the staircase is broken. A broken staircase = sideways. You can still trade sideways; you just trade it differently (see Step 5).

---

### STEP 2 — Read the MOC Signal (Institutional Flow Validation)

**MOC** (Market-On-Close) is the comparison between the volume of yesterday's 3:30 PM candle vs the volume of yesterday's 3:00 PM candle. A big institutional close-out (3:30 volume at least 20% higher than 3:00) validates that smart money established a directional position overnight. Your V2_4 panel shows this as a colored state.

| Panel Color | What It Means | Your Action |
|-------------|---------------|-------------|
| **GREEN** | Vol(3:30) > 1.20 × Vol(3:00) — institutional flow confirmed | Full-size eligible (subject to other gates) |
| **ORANGE** | Vol(3:30) between 1.00 and 1.20 × Vol(3:00) — weak flow | Half-size only |
| **GRAY** | Vol(3:30) ≤ 1.00 × Vol(3:00) — no institutional conviction | Half-size, no aggressive entries |

`[ ] Note today's MOC state: ______`

**Key rule:** MOC GREEN + TREND day = full-size eligible. MOC GRAY + SIDEWAYS = minimum size, maximum patience.

---

### STEP 3 — Read the 200-SMA Slope

The 200 SMA slope (shown on your V2_4 info card) tells you which direction institutional money is biased for *this session*. It is computed as the difference between today's 9:30 SMA200 value and yesterday's 9:30 SMA200 value on the 30-minute chart.

| Slope Reading | What It Means |
|---------------|---------------|
| **UP** (positive delta) | Trend is up. On TREND days: buy dips. On SIDEWAYS days: fade the deep dips long. |
| **DOWN** (negative delta) | Trend is down. On TREND days: sell bounces. On SIDEWAYS days: fade the sharp spikes short. |
| **FLAT** (near zero) | No directional edge. On SIDEWAYS days with flat slope: **DO NOT TRADE** (the indicator will show null verdict). |

`[ ] Note today's 200 SMA slope: ______`

**The slope is sticky.** It is read once at the RTH open and does not change during the session.

---

### STEP 4 — Read the Verdict Line

Your V2_4 info card panel shows a **Verdict** line that synthesizes the body stack, MOC, and slope into a single recommendation. Read it, but also verify it against your own read from Steps 1–3.

- `TREND LONG` → dips are buy entries
- `TREND SHORT` → bounces are sell entries
- `FADE LONG` → sideways day, buy the deep dips
- `FADE SHORT` → sideways day, sell the sharp spikes
- `NO FIRE` or blank → do not trade today

`[ ] Verdict line reads: ______`

`[ ] My own read (Steps 1–3) agrees: YES / NO`

If they disagree, see Section 7 for the conflict-resolution protocol.

---

### STEP 5 — Determine Today's Mode and the Two Levels You Will Trade

**For TREND LONG:** Write down (a) the Europe 4 AM candle LOW and (b) the GlobEx 6 PM candle LOW. These are your pre-place limit candidates. On a clean stair-step day the prior Institutional candle (A) HIGH may also serve as a breakout target — but your **entry** is at a dip back to one of these box lows, not at the breakout.

**For TREND SHORT:** Write down (a) the Europe 4 AM candle HIGH and (b) the GlobEx 6 PM candle HIGH.

**For SIDEWAYS (FADE LONG):** Your entry zone is the Europe LOW or Institutional LOW — wherever the deep dip lands. Your target is the Institutional candle HIGH (the prior 3:30 PM candle's top edge).

**For SIDEWAYS (FADE SHORT):** Entry zone is Europe HIGH or Institutional HIGH. Target is Institutional LOW.

**For NO FIRE:** Close the chart and do something productive. This is a correct outcome.

`[ ] Today's primary entry level: ______`
`[ ] Today's secondary entry level: ______`
`[ ] Today's first profit target: ______`

---

### STEP 6 — Mark Two Levels the Panel Does NOT Show (Do This Manually)

Your V2_4 panel does not display these. Mark them on the chart by hand before 9:30.

**1. Yesterday's 1:30 PM ET candle** — this candle is AM's "daily turn-around level." She has called it out explicitly in session recordings: "every day, by a couple of minutes." On days where a retracement is developing in the afternoon, price consistently reacts at this level. Draw a horizontal line at its HIGH and LOW.
`[ ] 1:30 PM candle H: ______ L: ______`

**2. Daily Pivot Levels (Woody's Pivots)** — AM uses Woody's pivots as her primary level set for the day. They are NOT shown on the V2_4 panel. You have two options: (a) install a free Woody's Pivot indicator in NT8 and display it as a separate study, or (b) calculate or look up the Pivot Point (PP), R1, R2, R3, S1, S2, S3 each morning and write them on a sticky note. The Pivot Point (PP) is the most important — above it means the day leans bullish; below it means the day leans bearish.
`[ ] PP (Pivot Point): ______`
`[ ] R1/S1: ______ / ______`
`[ ] R2/S2: ______ / ______`

**Extension alert:** If price is already above R2 when you sit down, the day may be in an "extended" condition. AM's rule: above R2 = watch for exhaustion, do NOT enter fresh longs. Above R3 = short-covering-rally territory, extreme caution.

---

### STEP 7 — The Go / No-Go Decision (30 Seconds)

Answer all five questions. All five must be YES for a GO day.

```
[ ] 1. Does the body stack give me a clear direction? (A/B/C stair-step, or clean B/C/D)
[ ] 2. Is the 200 SMA slope aligned with the body-stack direction?
[ ] 3. Is MOC GREEN or ORANGE? (GRAY alone = no aggressive trade)
[ ] 4. Are we NOT extended above R2/R3 or below S2/S3 in the wrong direction?
[ ] 5. Do I have at least one clear level to pre-place a limit at?
```

**If 4 or 5 are YES → GO (with appropriate size per MOC state)**
**If 3 or fewer are YES → WAIT or NO-TRADE**

Today's mode: `[ ] TREND LONG  [ ] TREND SHORT  [ ] FADE LONG  [ ] FADE SHORT  [ ] NO-TRADE`

---

## SECTION 2 — RTH OPEN: 9:30–10:00 ET

*This window is FOR OBSERVATION ONLY. Do not enter during this window.*

### 2.1 Watch the 9:30 One-Minute Volume

The very first 1-minute candle after 9:30 ET tells you how much institutional conviction is behind the open. Your V2_4 panel captures this.

| Volume Level | What It Means | What You Do |
|---|---|---|
| ES > 15,000 contracts | Normal institutional presence | Proceed with the plan |
| ES > 20,000 contracts + directional | Strong institutional conviction | High-confidence setup likely forming |
| ES < 12,000 contracts | Traders are tentative, retail-heavy | Wait for the second candle before reading direction |

**NQ benchmarks:** Normal ≈ 6,000 contracts. Below 5,000 = wait.

`[ ] 9:30 1-min volume: ______ (HIGH / NORMAL / LOW)`

### 2.2 Note the Opening Range

During 9:30–10:00 ET, the Opening Range (OR) is forming. Do not trade into it — just watch.

- If the OR range is **more than 10 ES points wide:** note that AM's rule is "1 MES only" on this day. You do not size up. The wide range means the market is fighting about direction and the wick risk is extreme.
- If the OR range is **under 10 points:** normal sizing rules apply.

`[ ] OR High: ______  OR Low: ______  Width: ______ points`
`[ ] If > 10 pts: SIZE CAP IS 1 MES TODAY`

### 2.3 The Rule You Must Not Break

> **Do NOT enter on the open break. Wait for the retest.**

AM's standard method is the "failed bounce / look-below-and-fail" or "look-above-and-fail" pattern. This means: price breaks one way, makes its statement, then comes back to retest the level it broke from. That retest is your entry — not the initial break. If you chase the initial break, you are paying the worst price in the move.

**Important note:** V2_4's current signal system uses a pre-placed limit approach that is close to this — but the OR itself does not become a candidate level until 10:00 ET when the indicator locks the range. This is by design. Your job is to wait.

---

## SECTION 3 — 10:00 ET: START OF TRADING WINDOW

At 10:00 the Opening Range is locked, the RTH 9:30 candle is finalized, and V2_4's full candidate pool is active. This is when trading begins.

### 3.1 Re-Verify the Verdict

Re-read the V2_4 verdict line at 10:00 with the now-completed RTH930 box visible. The day-type classification may shift slightly as the 9:30 box completes. If the verdict changed direction from your pre-market read, treat the 10:00 read as final.

`[ ] 10:00 Verdict confirmation: ______`

### 3.2 Pre-Place at the Trend-Side Level

On a TREND LONG day:
- Place a buy limit at the Europe 4 AM LOW, the GlobEx LOW, or the Institutional candle LOW — whichever is closest to current price and has not yet been touched today.
- The limit must be placed **at the level**, not chasing price. If price is already past the level, do not enter.

On a TREND SHORT day: mirror logic at the respective HIGHS.

On a FADE day: pre-place at the structural extreme (see Section 1, Step 5 targets).

**The limit-only doctrine:** AM's rule is unambiguous — **always limit orders, never market orders.** A market order in a thin ES book can get you filled 3–5 points away from intent. Limits or nothing.

### 3.3 The Lobster Buffet Rule

> "I'm gonna put a limit order out and I'll see if it comes back to get me. If it comes back to get me, great. If it doesn't, I don't care. The buffet is open tomorrow."
> — Anne-Marie Baiynd (apr-9 session)

**Definition:** If you miss a level — if price ran to your target without filling your limit — you do NOT chase it by moving your order to a worse price. You cancel the order and wait for the next setup. Missing a trade is not a loss. Chasing a missed trade IS a loss.

**If the level was touched but your limit wasn't filled:** Place a new limit at the next available structural level in the same direction. Do not use a market order to get in.

### 3.4 One Position at a Time

V2_4 enforces this in code, but it bears stating: you hold at most one ES/MES position at any moment. You do not add a second position while the first is open, unless you are performing the approved "add at 50% midpoint" mechanics (see Section 4.3). A new limit can sit pending while you are in a trade — but it is automatically cancelled when the first fill happens.

---

## SECTION 4 — TRADE MANAGEMENT

### 4.1 The Level-to-Level Exit Doctrine

> "I don't trail any stops. I go level A to level B and I'm done."
> — Anne-Marie Baiynd (apr-9 session)

**This is AM's most important rule and V2_4 currently implements it incorrectly in TREND mode (the indicator uses an SMA20 ratchet trail instead).** As a manual trader, you override this. Here is the correct exit plan:

**For FADE (sideways) trades:** V2_4 sets a fixed target at the Institutional candle H/L. That target is your exit. When price reaches it, you are done. No debate.

**For TREND trades:** The indicator will trail with SMA20, but AM's intended behavior is:
1. When price reaches the HIGH of your entry candle (= 100% Fibonacci extension, measured from entry candle LOW to HIGH), take at least half the position off.
2. Let the other half run to the next structural level — the next box high/low, the next pivot, or the 200% Fibonacci extension if the 200 SMA slope is steep.
3. When the second target hits, you are completely flat. Done.

**What the 200 SMA slope tells you about targets:**
- Slope steep (clear upward or downward angle): runner can go to 200% extension, possibly 250%.
- Slope flat (nearly horizontal): cap your runner at the 150% extension. Do not hold for more.

### 4.2 Stop Placement

**Default stop:** The width of the entry trigger candle — that is, from the candle's HIGH to LOW. Place your hard stop at the far edge of that candle.

**Bigger-candle exception:** If your entry trigger candle is contained INSIDE the prior 3:30 Institutional candle OR inside the RTH 9:30 candle, use the larger candle's width as your stop distance. This gives you more room when entering at a zone that is still "inside" the major structural candle.

**Wide-candle sizing rule:** When the 9:30 candle opens with a range wider than 10 points, your stop is also wider than normal. Use 1 MES only on that day (see Section 2.2). The dollar risk stays manageable because size is capped.

**Practical check before placing the limit:**
- Calculate: `(Entry Level) - (Stop Level) = stop distance in points`
- Calculate: `stop distance × $5/point (MES) = dollar risk`
- If dollar risk exceeds your personal daily loss cap divided by 5 (one-fifth of your max daily loss), reduce size or skip the trade.

### 4.3 Adding to a Winner (Optional, Advanced)

When price moves in your favor and then pulls back to the 50% midpoint of the entry candle:
- You may add to the position at that 50% level.
- When you add, **move your hard stop to the 50% line** (the same level you added at). This tightens the stop and locks in part of the gain.
- Cancel all other pending limits at that moment.

This mechanic is not required for every trade. Use it when you are very confident in the trend continuation and the 200 SMA and 50 SMA are both aligned and pointing in your direction.

### 4.4 The Cancel-Others Rule

The moment your first limit fills: cancel all other pending limit orders. Do not let a second order fill while you are already positioned. V2_4 fires an alert for this ("CANCEL OTHERS"), but you must execute the cancellation manually in ChartTrader.

---

## SECTION 5 — CANCEL AND EXIT CUTOFFS

These are hard rules. No discretion.

| Time | Rule |
|------|------|
| **14:30 ET** | Cancel ALL unfilled limit orders. No new orders may be placed after this time. |
| **15:00 ET** | Be completely flat. Hard close on all positions — no exceptions. |

**The T-minus-60-second alert:** V2_4 fires an audio alert approximately 60 seconds before the 15:00 hard close. When you hear it, if you are still in a trade, place a market order (yes, this is the one time a market order is appropriate) or accept whatever fills the hard close gives you. Holding past 15:00 in ES carries overnight gap risk.

---

## SECTION 6 — DAILY DISCIPLINE

### 6.1 Trade Count Cap

**Maximum 5 trades per day.** This is AM's stated personal cap (confirmed in the apr-10 session: "that's usually my max max is five"). On most days you will take 1–3. On well-defined sideways days in a tight range, up to 5 is acceptable. More than 5 means you are overtrading.

**V2_4 default cap is 3 for TREND mode and 2 for FADE mode.** The indicator enforces these limits automatically. If you want to take more, change the MaxSignalsPerDay parameter — but do not exceed 5 total.

**Important:** V2_4 counts a pending limit that was later cancelled against your trade budget. A limit placed and cancelled still used up one "slot." This is by design.

### 6.2 The Hard Daily Loss Kill-Switch

Before each session, write down a dollar amount: "If I lose more than $______ today, I stop trading immediately." Fill in an amount you can afford to lose without emotional damage — for most beginners on MES sim, $100–$200 is reasonable. V2_4 has a `MaxDailyLossDollars` parameter for this.

When the kill-switch triggers:
1. Close all open positions.
2. Cancel all pending limits.
3. Close the trading application.
4. Do not re-open it until tomorrow.

### 6.3 The Two-Loser Walk-Away Rule

After 2 consecutive losing trades in the same session, stop trading for the rest of that day. This is not a recommendation — it is a rule. Two consecutive losses means either (a) the day is not behaving as the indicators predicted, or (b) you are making execution errors. Both situations require a mental reset that cannot happen while you are still watching the chart.

### 6.4 Zero-Trade Days Are Wins

Some days, when you finish the morning checklist, you will find that none of the five go/no-go questions produce a YES. On those days, the correct answer is to take zero trades. AM: *"Some days you take zero trades. That's a win."* Do not force a trade to feel productive.

---

## SECTION 7 — WHEN THE INDICATOR SAYS X BUT THE CHART SAYS Y

### 7.1 Verdict Says NO FIRE but a Clean Structure Forms

**What it usually means:** The body-stack test failed (boxes overlapped), but the chart shows a beautiful level approaching with confluence (VWAP near 200 SMA near a box low). 

**What to do:**
1. Check the 200 SMA slope. If it is truly flat, there is no directional edge — the indicator is correct to say no-fire. Do not override.
2. If the slope is NOT flat, the issue may be that the V2_4 body-stack required all four boxes to stack cleanly and they did not quite clear. Use judgment: if B, C, and D are stacked in one direction (even if A is in the middle), you may treat it as a cautious trade at half-size.
3. Never override NO FIRE with a full-size entry.

### 7.2 Verdict Says FADE LONG but the Slope Feels Weak

**Situation:** The indicator says fade-long (sideways day, slope up), but price has been grinding down all morning and the bounce keeps failing.

**What to do:**
1. Go back to the 200 SMA itself on the 30-minute chart. Is it actually sloping up, or is it flat / barely positive?
2. If the slope is near zero (a small positive number), that is a borderline "flat" case. Reduce size to the minimum (1 MES) or skip.
3. If price cannot hold above the Europe LOW after two attempts, the level has lost its significance. Cancel the limit and wait. Do not keep moving your limit down to chase the dip.

### 7.3 "Approaching Entry" Alert — Verify the Limit Is Live

When V2_4 fires its "Approaching Entry" alert (price is within about 25% of the stop distance from your limit level), this is your cue to **physically confirm in ChartTrader or the Order Ticket that the limit order is sitting in the broker queue.** The indicator shows the limit on-screen, but until you manually stage and submit the ATM order, it is not in the market. 

**The workflow:**
1. Indicator fires "Approaching Entry."
2. You look at the Staging Card — verify direction, entry price, stop price, size.
3. You click CONFIRM on the Staging Card (this logs the ticket).
4. You open ChartTrader and submit the ATM strategy.

Step 4 is manual. The indicator does NOT submit orders automatically. If you hear the alert and do nothing, no order goes to the broker.

### 7.4 The Body-Stack Shows LONG but Price Is Above R2/R3

**Situation:** The four boxes stair-step up cleanly (LONG TREND day), but price is already well above R2 or R3 on Woody's Pivots (which you've written down in your pre-market checklist).

**What to do:** Do NOT enter fresh longs. AM's rule is explicit: above R2 = watch for exhaustion. Above R3 = "very extended." The trend-long verdict from the body-stack tells you direction was established overnight. But if you are chasing a move that is already at R3, you are buying near the top of the day's range. Wait for a pullback to the dip buy zone that makes sense, or skip the day if the first target would already be above R3.

---

## SECTION 8 — THE ANTI-DOUBT RUBRIC

### The "Should I Take This Trade?" Checklist (30 Seconds, 5 Questions)

When you feel uncertain — when you want to take a trade but you're not sure if it's right — go through this checklist. All five should be YES before you place the order.

**Print this block and keep it next to your keyboard.**

```
BEFORE I PLACE THIS LIMIT:

[ ] 1. Is this level a master-candle extreme?
        (It must be a HIGH or LOW of one of the four boxes, OR the ORH/ORL,
        OR the prior 30-min H/L — NOT a random mid-candle price.)

[ ] 2. Am I entering INTO the level from the trend side?
        Long day: price must be FALLING DOWN to support — not breaking out above.
        Short day: price must be BOUNCING UP to resistance — not breaking down below.
        (AM's rule: "longs are taken on dips, shorts are taken on bounces — always.")

[ ] 3. Is the 200 SMA slope still aligned with my trade direction?
        (If the slope has changed since the morning read, verify again now.)

[ ] 4. Am I within my trade count for today?
        (Current signals today: ______ / Max allowed: ______)

[ ] 5. Is there at least a 1:1 reward-to-risk on this setup?
        (Target distance ÷ Stop distance. If less than 1, skip the trade.)
```

If any answer is NO, do not take the trade. Write down why the trade did not qualify. This log will become your most valuable learning tool.

---

### The Doubt Decoder

| What You're Thinking | What It Actually Means |
|---|---|
| "This looks so good, I should size up" | Reduce size by half. Confidence bias inflates risk. |
| "I missed the entry, I'll get the next one at a worse level" | Cancel. The lobster buffet is open tomorrow. |
| "The verdict says no-fire but I just KNOW this will work" | Walk away. Overriding the gate is how accounts die. |
| "I've taken 2 losers, maybe the third will recover them" | Stop for the day. This is the most dangerous thought in trading. |
| "I need to be in a trade — I've been watching for two hours" | The market does not owe you a setup. Waiting IS trading. |
| "The indicator didn't fire but AM would have taken this" | Review Section 7. If unclear, pass and note it for review. |

---

## SECTION 9 — DEEPER CONTEXT: THE WHY BEHIND THE RULES

*(Read this section weekly, not daily. It explains the reasoning behind the rules so they feel less arbitrary.)*

### Why the Body Stack Works

AM's insight, confirmed by her "Sidekick" data tool against 60 days of 30-minute candles: when institutional participants establish positions at the 3:30 PM close (the MOC), those positions express themselves through the overnight session in a directional sequence. Each subsequent session candle (GlobEx, Europe, RTH open) either confirms or contradicts the prior. When they all confirm (stair-step), the institutional flow is clean and the bias is reliable. When any box contradicts (overlaps), multiple parties are fighting for control, and the day will be messy. The body (open-to-close) reflects where *settled* price action ended up; the wick reflects noise and stop-running. That is why bodies matter and wicks do not.

### Why Level-to-Level Exits (Not Trailing Stops)

Trailing stops (like the SMA20 trail in TREND mode) were designed for swing traders who hold positions for days. On an intraday timeframe, a trailing stop means you are giving back 50–80% of your profit before it triggers. AM trades 15 to 180-minute holds. Her "level B" is always a structural price — a box edge, a pivot, a Fibonacci extension — not a moving average that follows price with a lag. Level-to-level exits make the trade feel mechanical because you define the exit BEFORE the entry. The decision is made in advance; during the trade, you have nothing to do.

### Why Limits Only (Never Market Orders)

AM used this exact reasoning in the apr-9 session: "If you use market orders and the order book has thinned out, you can get absolutely smashed." ES liquidity is deep on most days, but the first-minute book can thin dramatically after a news event or at the open. A market order at 9:32 ET on a volatile day can fill 3–5 points away from the last traded price. A limit order at your structural level fills where you intend or not at all — both outcomes are controlled. The uncontrolled outcome (a poor fill on a market order) destroys the R/R calculation you did before the trade.

### Why the 1:30 PM Candle Matters

AM described this in the mar-6 genesis session with unusual emphasis: "every day, Asheen, every day, by a couple of minutes." The 1:30 PM ET 30-minute candle represents the first major afternoon liquidity window — pension funds and institutional rebalancers begin positioning for the afternoon before the 3:30 PM MOC. When a retracement is in progress, this level acts as the turn-around point for the next leg. Mark it on the chart every morning because V2_4 does not display it.

### Why Pivots Are Not in V2_4

The V2_4 indicator does not plot Woody's Pivots (R1–R4, S1–S4). AM uses them as her primary daily level set — "first things first, where's the pivot?" — but they require an external data calculation. You need to set up a pivot indicator separately in NT8, or calculate the levels manually. They serve two purposes: (1) as targets for exits (the first pivot above is often the first target on a TREND day), and (2) as "extension gates" (above R2 = extended, above R3 = exhausted — do not initiate new longs). These are rules your V2_4 panel cannot tell you, so you must supply them manually.

### Why the 200 SMA Is THE Indicator

AM's reasoning: *"the 200 moving average is the most statistically significant indicator. Since the market is fractal, I bet I can use it on any timeframe."* She uses it on 1-min, 30-min, and daily charts simultaneously. On the daily: it separates long-side from short-side. On the 30-min: its slope direction gates intraday entries. On the 1-min: it shows where convergence is forming (when the 50 SMA and VWAP all compress to the same level, a breakout is imminent). The V2_4 panel shows you the 30-min 200 SMA slope. The 1-min 200 SMA is drawn on your chart for visual reference.

---

## SECTION 10 — QUICK-REFERENCE CHEAT SHEET

```
DAILY FLOW                          RULES THAT NEVER CHANGE
─────────────────────────────────   ────────────────────────────────────────
Pre-9:30:  Read boxes A→D           Limits only. No market orders.
           MOC state                One position at a time.
           200 SMA slope            No chasing missed levels.
           Pivots (manual)          Cancel others on first fill.
           1:30 candle (manual)     Cancel limits at 14:30 ET.
           Go/No-Go decision        Flat by 15:00 ET.
                                    Max 5 trades per day.
9:30-10:00: Observe only            Stop after 2 consecutive losses.
            Volume check
            OR range note
                                    SIZING RULES
10:00+:    Verify verdict           ────────────────────────────────────────
           Pre-place limits         GREEN MOC + TREND = full size
           Wait for level touch     ORANGE or GRAY MOC = half size
           No chasing               SIDEWAYS day = always half size
                                    OR > 10 pts = 1 MES only
14:30:     Cancel all limits        Extended (above R2) = no fresh longs
15:00:     FLAT — no exceptions

EXIT TARGETS (manual, V2_4 TREND mode)
────────────────────────────────────────────────────────────────────
First target:   100% of entry candle (top of candle for longs)  → scale off 50%
Runner target:  150% if 200 SMA is flat
                200–250% if 200 SMA is steeply sloped
Stop:           Far edge of entry trigger candle
                (or far edge of containing box if entry candle is inside 3:30/9:30)
```

---

## APPENDIX — WHAT V2_4 SHOWS vs WHAT YOU SUPPLY MANUALLY

| Information | V2_4 Shows It? | How to Get It If Not |
|---|---|---|
| Institutional candle (3:30 PM) box H/L | YES | — |
| GlobEx 6 PM candle box H/L | YES | — |
| Europe 4 AM candle box H/L | YES | — |
| RTH 9:30 candle box H/L | YES | — |
| VWAP (session) | YES | — |
| Anchored VWAP (from institutional candle) | YES | — |
| 30-min SMA50 and SMA200 | YES | — |
| 1-min SMA50 and SMA200 | YES | — |
| MOC state (GREEN/ORANGE/GRAY) | YES | — |
| 200 SMA slope verdict | YES | — |
| Body-stack day-type | YES | — |
| Verdict line | YES | — |
| Pre-place panel (candidate levels + stop estimate) | YES | — |
| Staging card (entry/stop/size) | YES on signal | — |
| Woody's Pivots (PP, R1–R4, S1–S4) | **NO** | Install pivot indicator in NT8 separately, or calculate manually |
| 1:30 PM ET candle H/L | **NO** | Draw horizontal line at prior day's 1:30 candle H/L each morning |
| Yesterday's 1:30 PM ET candle H/L | **NO** | Same as above |
| First-minute volume (9:30 1-min contracts) | YES (panel shows it) | — |
| Fibonacci extension levels (100/150/200%) | **NO** | Draw manually using NT8 Fibonacci Extension tool anchored on the entry candle at signal time |
| Pattern B (look-below-and-fail) entry signal | **NO** (scaffolded, not wired) | Watch for it visually: price wicks below level, closes back above → next bar holds higher low → enter on touch of breach-bar high |
| Runner ladder / next structural level | **NO** | Use your manually drawn pivots and the box H/L levels to identify the next target |

---

*Document version: 2026-04-27. Written for Afshin's manual sim trading on V2_4. To be updated when V2_4 adds Pattern B firing, Fibonacci overlays, or pivot integration.*
