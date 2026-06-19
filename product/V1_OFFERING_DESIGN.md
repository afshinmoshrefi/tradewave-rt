# TradeWave Realtime - V1 Offering Design (max value, minimum churn)

> Written 2026-06-10. Companion to `PRODUCT_BRIEF.md` (the canonical brief). This doc answers:
> what exactly is V1, why her audience will pay for it, and why they will stay. It also closes
> brief §8 Q1 (levels pipeline) and Q7 (trial policy). Evidence sources: 100 mined briefings
> (`/home/flask/am_youtube/`), the indicator spec (`/home/flask/baiynd_autotrader/SPEC.md`),
> the built coach (`/home/flask/tradewave_realtime/`), the deal draft, and trading-community
> churn benchmarks (8-15%/mo typical; #1 churn driver = the room goes quiet / questions
> unanswered; first 90 days decide retention).

## 1. The one insight everything hangs on

Anne-Marie already publishes her levels every morning, free, on YouTube (1,300+ daily
"Blueprint Open" videos). Sample from 2026-06-03: gamma flip at 7594, pivot at 7612, call wall
7650, NQ buy zone ~30,600, oil buy zone 95.70 with targets into 99, gold range 4450-4540, SPY
pullback 756.30. The content is NOT the scarce thing. What her audience does NOT have:

1. **The levels on their chart.** They watch a 15-minute video and hand-transcribe numbers
   onto NinjaTrader/TradingView/broker charts before the open. Tedious, error-prone, daily.
2. **Anything after 9:30.** The video is pre-open. Walls migrate ("they can shift within 15
   minutes"), and there is no updated map and nobody to ask.
3. **Anyone to ask, ever.** "Was that a look-below-and-fail?" "Why is the gamma flip support?"
   Free viewers get no answers. Her paid room gets her live, but it is small, expensive, and
   she is finite.
4. **The method, taught systematically.** The videos assume you already speak her language.
   The book is from 2011. There is no structured path from "follower" to "trades the method."

**So V1 sells the productization of what she already does, not new content from her:**
her morning map delivered onto your chart and phone, the method behind every level
queryable 24/7, and a room that never goes quiet. Zero new daily obligations for her.

**Positioning sentence (unchanged from the brief):** "Trade with Anne-Marie's levels on your
chart, learn her method from her own words, in her room."

## 2. The V1 value stack (what a $99/mo member gets)

### Layer 1 - The Morning Map (the daily perishable core)
Her levels for the day, structured: per instrument (ES, NQ, YM, CL, GC, BTC, SPY - the set she
covers every morning), each with labeled levels (call/put wall, gamma flip, pivot, 200-SMA,
value area, fib zone, buy/sell zone) plus her stated bias (dips-are-buys / bounces-are-sells /
range edges). Delivered simultaneously by ~9:15 ET to:
- **The NinjaTrader indicator** (futures traders - levels appear drawn on the chart),
- **The Morning Map web page** (everyone else - stock/SPY traders, TradingView users, phone),
- **Discord** (#morning-map post + @everyone-free notification),
- **Email/push** ("Today's map is live").

The web page and Discord delivery are NOT nice-to-haves: her audience includes many
stock/ETF traders who will never install NinjaTrader. The indicator is the premium delivery
mechanism, not the only one. This roughly doubles the addressable slice of her audience.

**Skip-day fallback (designed, see §4):** the indicator's 15 mechanical levels (prior-day
H/L/C, Globex H/L, Europe candle, rolling 30-min H/L, VWAP, pivots, institutional candle)
compute locally and never skip. On a day with no briefing, members get a "Framework Map"
(mechanical levels + a standing note that these are the structural levels her method starts
from). The product degrades gracefully; the chart is never blank.

### Layer 2 - The coach as MENTOR (upgraded 2026-06-10 - the differentiator)
The chat skeleton is built and live (46 curated entries, her voice, AI-disclosure +
no-trade-calls guardrails verified). V1 makes it a mentor, not a Q&A bot: it OPENS the
relationship the way she would ("where are you in your trading? what do you want to achieve?
how has it been going?"), builds a bounded user-visible trader profile, assigns lessons as
homework matched to the member's named struggles, greets every return with continuity, and
runs a light daily check-in ("what's the plan?" / "how did it go?"). Today-aware via
deterministic injection of the computed map. It kills the #1 churn driver (unanswered
questions) AND creates the feeling no other trading site has: someone is paying attention
to me. Full design: `V1_SITE_DESIGN.md` §4. Deep months-long memory + the self-improving
loop remain the V2 relaunch.

### Layer 3 - The room (presence and identity)
Discord, subscription-gated by a role-sync bot. Defined heartbeat: the Morning Map drop +
her free briefing video linked at the same moment (we link her YouTube, never paywall or
re-host her free content - her channel keeps growing, members get one habit loop).
Channels: #morning-map, #trading-the-method (member discussion), #wins-and-lessons,
#ask-the-coach (links to the site coach). **No promised live Anne-Marie cadence** - the
contract gives best-efforts promotion and a weekly coach-teaching session, nothing in-room.
Any drop-in from her is surprise-and-delight, never an SLA. The product must retain without
her showing up.

### Layer 4 - The Method curriculum (first-90-days engine)
The existing 46 knowledge entries re-organized into her 5-stage process (read the day, the
levels, permission to enter, manage the trade, the trader's mind) with ordered lessons,
progress tracking, and coach-checkpoint chips. Zero new content - curation of what is built
(design: `V1_SITE_DESIGN.md` §3b). This exists because first-90-day engagement is the single
best churn predictor, and a new member needs a told order, not a pile of entries.

## 3. Why members stay (retention architecture, mapped to churn drivers)

| Churn driver (benchmarked) | V1 countermeasure |
|---|---|
| Value feels optional / no daily habit | The Morning Map is perishable daily value at a fixed time. Cancel = blank chart at tomorrow's open. |
| Room goes quiet, questions unanswered >48h | Coach answers in seconds, 24/7. Discord heartbeat is automated (map drop), not dependent on anyone showing up. |
| No felt progress after the first month | The 4-week path, then the daily loop (map -> trade -> ask the coach why). |
| Price re-evaluation each month | Founding rate lock: $99/mo for life **while continuously subscribed**; lapse and rejoin = $149. The discount itself becomes the switching cost. Annual option (~2 months free) moves the cancel decision to once a year. |
| Key-person fatigue (she goes quiet) | Framework Map fallback + evergreen coach + community = the product still delivers on her silent days. |
| Nothing accumulates | V1: the mentor core - trader profile, assigned plan, check-in history (leaving = losing the mentor who knows your story). V2 relaunch: DEEP memory ("months of history, a coach that grows with you"). |

Churn target: **under 5%/mo for the founding cohort** (vs 8-15% benchmark). Leading
indicators to instrument from day one: map-open rate (did they view today's map), active
days/week, coach conversations/week, week-4 path completion. A member who opens the map
4+ days/week does not churn; build the dashboard around that number.

## 4. The levels pipeline - SUPERSEDED 2026-06-10 (same day, after Afshin's correction)

**Her levels are MECHANICAL, not discretionary.** They derive from the 4 master candles
(Globex open 6:00-6:30pm, Europe open 4:00-4:30am, US open 9:30-10am, US close 3:30-4pm ET,
plus the 1:30-2pm watch candle), kept on the map for today + the prior 2 days, with the
50d/200d MA posture and the master-candle stair-step as the direction read. So the pipeline
is NOT "parse her briefing video" - it is a **server-side levels engine** computing the map
from intraday market data (EODHD if its ES/NQ futures intraday coverage verifies; pluggable
feed otherwise), automatically, every session, with zero dependence on her morning and zero
parse risk. Full engine + site + chatbot design: **`V1_SITE_DESIGN.md`** (canonical for all
of this). The "skip-day fallback" concept above is obsolete - a mechanical engine has no
skip days. Her briefing video stays her free channel that markets the product; her
discretionary layer (gamma walls, fibs) is explicitly NOT in V1.

Compliance posture (unchanged): the map is impersonal, identical for every subscriber,
regularly circulated, with disclaimers everywhere; the coach never personalizes it; the
futures attorney blesses pre-launch. Wind-down posture is now even cleaner: the engine is
pure math on market data; only the persona layer carries her identity.

## 5. What V1 is NOT (scope discipline)

- **No free trial** (closes brief §8 Q7). A trial of a levels product is drive-by scraping:
  the daily map is the value, consumable in one morning. Risk reversal instead:
  **14-day money-back guarantee** - card-up-front friction deters scrapers, the guarantee
  removes the stranger's risk, and refunds net out of revenue before the 35% split so the
  economics stay aligned. Revisit only with conversion data saying otherwise.
- **No tiers.** One price, everything included ($99 founding -> $149, annual ~ $990).
- **No promised Anne-Marie live time.** See §2 Layer 3.
- **No per-user memory / proactive coaching** (V2 relaunch, decided).
- **No today-aware coach** (V2 - it is the natural upsell moment: "your coach now knows
  today's map"). V1 coach answers method questions; the map page answers "what are today's
  levels."
- **No auto-trading anything.** The quarantined strategy code stays quarantined.
- **Fast-follow (founding window, not launch-blocking): the 3:00 Recap** - an auto-drafted,
  admin-approved evening post: which map levels traded, what the method said about each
  touch. Closes the daily loop (morning map -> trade -> evening recap) and doubles
  engagement touchpoints. Build it in week 1-2 after launch.

## 5b. The three subscriber questions (added 2026-06-10 - the core dilemma, answered)

**Q1 - What does a paying member need to actually day trade?** Three moments, three needs:
1. **Before the open - the PLAN:** the Daily Level Map + direction read, PLUS the "day
   rails" card: the method's risk discipline for today, all mechanical and impersonal -
   stop-width reference (the institutional/Europe candle width), MOC-validated size state
   (full / gray / reduced), the standing rules (max 5 trades, limits only, flat by 3:00,
   "a zero-trade day is a win"). A trader with a plan and rails trades the method; one
   with only levels trades their impulses.
2. **At the screen - PERMISSION:** her core teaching is "level = location filter,
   confirmation = permission filter." Real-time permission state (SMA stack, VWAP slope,
   volume vs benchmark) belongs in the NinjaTrader indicator, which computes on the USER's
   own data feed - that sidesteps exchange real-time-display licensing entirely and is why
   the indicator exists. On the site: the permission CHECKLIST as education (library + a
   printable card) + the coach to ask in the moment. The site plans and teaches; the
   indicator executes-supports; the coach mentors.
3. **After the close - the MIRROR:** the recap (which levels traded, what the method said)
   so members learn from the day whether or not they traded it.

**Q2 - What makes them KEEP subscribing?** Reframe value from P&L to PROCESS - authentically
her ("process over profit," psychology as her signature). P&L-anchored value churns with
drawdowns; process-anchored value survives them. By lifecycle stage:
- **Days 1-14 (aha):** first morning map + first coach conversation + the 4-week path
  started. Onboarding email sequence drives exactly these three.
- **Days 15-90 (habit):** the 7:30am ritual + recap closes the loop + first "the method
  called it" moments. The habit IS the retention.
- **Month 3+ (accumulation):** things they would LOSE by leaving - chat history (seeds the
  V2 per-user-memory relaunch), discipline/process history, founding price lock, community
  identity. V2's "discipline score" (did I trade at eligible levels, respect the cap, go
  flat on time) is the long-term anti-churn engine: it gives a winning scoreboard even in
  a losing market week.
- **Mechanics:** founding rate locked while continuously subscribed; annual at 2 months
  free pushed at checkout; **pause-don't-cancel** (1-click pause up to 2 months, keeps the
  founding rate) in the cancel flow - recovers the "taking a break from trading" churn,
  which in this audience is a big share of all churn.

**Q3 - The right price to KEEP them?** **$99/mo founding (locked while subscribed), $149
standard after the window, annual $990.** Why $99 and not higher: the LTV math favors
duration over rate for this audience. At 8%/mo churn (benchmark), expected lifetime is
~12.5 months; at 5% it is ~20 months - cutting churn 8->5 adds ~60% LTV, more than a
$99->$149 price raise adds, and the raise works against the churn cut. $99 sits below the
psychological "one losing trade" threshold where the monthly is-it-worth-it audit bites,
undercuts the $197 room tier while carrying more product than $50-225 alert Discords, and
matches the audience's stated $99-149 norm. Unit check: at $99, ~$96 net after processing,
~$33.60 to AM (35%), ~$62/member/mo to the company against pennies of Haiku inference and a
fixed data-feed cost - margins work from ~50 members. Policy: never raise the price on an
existing subscriber (the lock IS the retention feature); raise the new-member price (to
$149, later maybe more) only when shipped value visibly grows (recap, alerts, V2 memory
relaunch).



8:50am, phone buzzes: "Today's map is live." NinjaTrader opens with her levels already
drawn; the gamma flip, the pivot, her bias for ES and NQ. SPY-only member checks the web
map instead. 11:40am, price does something weird at a wall - they ask the coach "was that a
look above and fail?" and get her method back in her voice, instantly. 3:15pm, the recap
posts: the NQ pivot she flagged held to the tick; the member sees the method working whether
or not they traded it. Evening, week-2 of the path: the entries lesson. In Discord, forty
people traded the same map today and are talking about it.

That loop, every market day, is the product. Nothing in it requires her time.

## 7. Launch mechanics (founding window)

- Gate order (unchanged): signed agreement -> attorney pass -> launch. Neither is moved by
  this doc.
- Founding window: announced cap by date, not member count ("founding rate ends [date]" -
  honest, no fake scarcity). Her announcement + one joint live webinar with a live demo of
  the map landing on a chart + the coach answering. The demo IS the pitch.
- Cross-sell per the brief (EOD inside RT Discord, RT to the EOD list); bundle math already
  fixed by the contract formula.

## 8. What must be true for this to work (honest risks)

1. **Her daily video keeps coming.** 1,300+ uploads says the habit is real, but it is
   contractually best-efforts. Mitigated by the Framework Map fallback; watch the actual
   skip rate during the founding window before promising "every morning" in copy
   (say "every trading morning she publishes, plus the structural map every day").
2. **Parse accuracy.** A wrong level on a paying member's chart is the worst failure mode.
   Human approval stays in the loop until the error rate proves out; numbers get a sanity
   check against the mechanical levels (a "pivot" 4% from price is a flag).
3. **Her own paid room.** RT must not be positioned as "her room, cheaper." Differentiation
   is honest and structural: her room = her, live, real-time. RT = the productized method:
   map on your chart, coach on demand, community. Never name her room pricing in our copy.
4. **The indicator licensing** (brief §8 Q2) still needs its design session - the map feed
   endpoint should authenticate with a subscription-checked token from day one even if v1
   enforcement is simple.

## 9. Brief deltas applied this session

- §8 Q1 (levels pipeline): **designed** - parse-her-briefing + approve + fan-out, 9:15 SLA,
  Framework Map fallback (this doc §4).
- §8 Q7 (trial): **decided** - no trial; 14-day money-back guarantee (this doc §5).
- §4 offering refinements: Morning Map is platform-agnostic (web + Discord + indicator, not
  indicator-only); first-90-days path added to v1 scope (sequencing only); 3:00 Recap named
  the first fast-follow.
