# TradeWave Realtime - V1 Site, Chatbot, and Subscriber-Experience Design

> Written 2026-06-10, after Afshin corrected the levels model: **her levels are mechanical.**
> This doc supersedes the "parse her briefing video" pipeline in `V1_OFFERING_DESIGN.md` §4
> (that section now points here). Companion to `PRODUCT_BRIEF.md`.
> Base reality: the site already exists at `/home/flask/tradewave_realtime/` (landing, free
> signup, coach chat with RAG over 45+ entries, strategy library, feed, admin tool, legal).
> This doc defines what V1 adds and how it all fits together for a paying subscriber.

## 1. What the subscriber is buying (the offering, one paragraph)

**"Anne-Marie's level map for ES and NQ, computed her way every session, automatically - on
your screen, in your coach's head, and (for NinjaTrader users) drawn on your chart - plus her
method and trading psychology taught on demand by an AI trained on her."**

Three concrete things:
1. **The Daily Level Map** - the master-candle levels and direction read, computed
   server-side from market data every session. Automatic, never skips, never depends on
   anyone's morning.
2. **The coach** - already built; V1 upgrade makes it *today-aware* by injecting the same
   computed map (deterministic DB facts, so zero hallucination risk on numbers).
3. **The method** - the strategy library re-sequenced as a guided path, plus her feed.

The NinjaTrader indicator is a *delivery channel* of #1 for Ninja users (listed on the Ninja
platform once this offering is locked), not the product itself. The website is the product
surface every subscriber shares.

## 2. The levels engine (the heartbeat of the product)

**The model (Afshin 2026-06-10, VERIFIED against the strategy-session transcripts in
`/home/flask/baiynd_autotrader/video_transcripts/` - `AM_rules_comprehensive.md` carries
verbatim quotes; those transcripts are the canonical method source):**
- **4 master candles** (30-min, ET): **institutional/MOC 3:30-4:00pm** (her dominant frame),
  Globex open **6:00-6:30pm**, Europe open **4:00-4:30am**, US open **9:30-10:00am**. Each
  candle's high/low = levels. (The autotrader SPEC's "Europe 3:00-4:00am" is the outlier -
  transcripts confirm 4:00-4:30am.)
- **+1 watch candle:** **1:30-2:00pm** - her afternoon pullback/expansion (possible-reversal)
  marker.
- **Lookback:** levels from **today + the prior 2 days** stay on the map as potential
  reversal locations.
- **Direction read - three mechanical states, all computable:**
  - **Stair-step:** the 4 master candles stepping in one direction = high indication of the
    day's direction (Afshin; consistent with her containment teaching). Precise mechanic
    already pinned in `AM_questions_pending.md`: **body stacking**, strict no-overlap of
    candle bodies (`body_bottom_upper > body_top_lower`); nested bodies (4am inside Globex
    inside 3:30) = sideways. The engine implements exactly this.
  - **Containment = sideways:** overlapping boxes ("6pm candle inside the prior 3:30, 4am
    partially inside = sideways day until the break", apr-9) -> the read is "trade the
    edges," and the **in-charge candle** = the largest enclosing box (her hierarchy; box
    walkdown 3:30 -> 6pm -> 4am -> 9:30).
  - **SMA trend gate:** the **50/200 period SMA on the 30-min chart - stack AND slope**
    ("price above both and both rising" / inverse / neither = stand down, apr-8/apr-9).
    NOTE: transcripts say 30-min period SMAs; Afshin's note said 200-day/50-day - compute
    the 30-min stack as primary, confirm whether the daily MAs also belong on the card.
- **MOC validation (the 20% rule):** institutional candle is "in charge at full strength"
  only when its volume is >= 20% above the 3:00 candle (60-day lookback, apr-16); the
  0.80-1.00 volume-ratio band is her confirmed GRAY zone (reduced conviction, apr-24).
  Pure math; needs volume bars from the feed. Shown as validated / gray / unvalidated.
- Instruments: **ES and NQ** at launch; architecture keeps the instrument list configurable.
  (CL later note: its institutional candle is 10:00am ET, not 3:30 - the config must allow
  per-instrument candle times.)

**How the map builds across a session (this rhythm IS the engagement loop):**
| ET time | Event | Map state |
|---|---|---|
| ~6:35pm (prev. eve) | Globex open candle closes | tomorrow's map starts |
| ~4:35am | Europe candle closes | pre-open map complete -> **morning notification** |
| ~10:05am | US open candle closes | stair-step read firms up -> map updates |
| ~2:05pm | 1:30 watch candle closes | reversal marker posts |
| ~4:05pm | US close candle closes | day complete -> recap + tomorrow's inputs |

**Data architecture (VERIFIED + DECIDED 2026-06-10).** EODHD probe results (token on this
box): `ES.COMM`/`NQ.COMM` futures exist with volume; daily OHLCV good; intraday 30m/1m bars
have full overnight coverage BUT lag ~a session (good for backfill/recap/validation, not
the live morning map); the real-time quote endpoint is live (~15-min delayed). Index proxies
(SPY/QQQ/SPX) are NOT acceptable substitutes - her levels are futures prices.

**Decision (Afshin): live candle capture comes from the EXISTING TradeWave quote service on
the keyprovider server** (already polls ES, NQ, YM, CL, GC every 10 minutes for EOD; Afshin
upgrades it to capture granularly around the candle windows). The RT engine consumes from
it; EODHD intraday history is the nightly truth source.

**AS BUILT 2026-06-10 - the keyprovider service went live as a PULL API** (docs:
`/home/afshin/tradewave_realtime_level_quotes.md`): boundary snapshots at exact ET times
(price + session-cumulative high/low/volume from the ~15-20 min delayed EODHD quote),
served at `GET {KEYPROVIDER_LEVELS_URL}/levels_rt?symbols=ES,NQ&days=4`. The RT engine
polls every 15 minutes (`flask levels-sync`, systemd timer) and DERIVES capture candles:
open/close from the two boundary snapshots, body-only high/low (marked `~` on the Today
page), window volume = cumulative delta. EODHD history reconciles to exact values
overnight; captures never overwrite truth rows. The push endpoint below remains as an
alternative/backup path.
**Two capture-schedule asks for Afshin (flagged 2026-06-10):**
1. The eu pair is captured at 03:30/04:00 ET, but her Europe candle is **04:00-04:30**
   (transcripts + his own spec). Eu captures are SKIPPED by the adapter until the schedule
   moves; today's Europe candle currently arrives only via overnight history.
2. No **15:00 snapshot** exists, so a live MOC base for the CURRENT afternoon cannot be
   derived from captures (harmless for the morning map, which uses the prior session's MOC
   from history; matters only if we later want a live 3:35pm MOC read).

**The push ingest contract (backup path; build against this if push is ever preferred):**
- Push (preferred): `POST /api/ingest/candle` on the RT app, header
  `X-Ingest-Token: $LEVELS_INGEST_TOKEN` (in `/etc/tradewave_realtime/secrets.env`), JSON:
  `{"instrument": "ES", "window": "globex_open" | "europe_open" | "us_open" |
  "reversal_1330" | "moc_base_1500" | "institutional", "session_date": "YYYY-MM-DD",
  "open": n, "high": n, "low": n, "close": n, "volume": n | null,
  "captured_at": "ISO8601"}`
- One POST per completed window (resends upsert - idempotent on
  instrument+window+session_date). `session_date` = the RTH date the candle belongs to
  (the 6pm Globex-open candle posts with the NEXT day's session_date).
- **Windows to capture (ET):** 18:00-18:30 (prior eve), 04:00-04:30, 09:30-10:00,
  13:30-14:00, 15:00-15:30 (the MOC comparison base - volume matters), 15:30-16:00
  (institutional - volume matters). Per-window volume = cumulative-volume delta across the
  window boundaries if the quote source only gives running totals.
- **Reconciliation:** a nightly job replaces captured values with EODHD's true intraday
  bars once they land; any discrepancy beyond a tick tolerance is flagged on the admin
  Levels monitor. Captured levels are marked `source: capture` vs `source: reconciled` so
  precision is auditable - a wrong level on a member's chart is the worst failure mode.
- Until the keyprovider upgrade lands, the engine runs on EODHD history (maps build with
  yesterday-true data - fine for build/demo) and flips to live capture with zero code
  change when POSTs start arriving.

**Engine output (one row per instrument per session, in the DB):** the 4+1 candle H/L sets
for today and prior 2 days, the 30-min 50/200 SMA stack + slope state, the stair-step /
containment verdict (up / down / sideways, which candles, which box is in charge), the MOC
validation flag (when volume bars are available), and per-level touched-status (when
intraday quotes are available). All deterministic. The website, the chatbot, the indicator
feed, and notifications all read THIS one table - single source of truth.
**Later additive levels (same engine, post-V1, all in her transcripts):** Woody's pivots,
midnight candle/midpoint (matters when it pokes outside the Globex box; more on NQ),
Europe-box measured-move projections, prior-day H/L/close, opening-range H/L.

## 3. The Today page (the new center of the member area)

`/app` becomes **Today** (the current dashboard's welcome content folds into it). It must
answer, in 5 seconds: *what is the read, and where are the levels?*

```
TODAY - Wednesday, June 10            [session: pre-market | RTH | after-hours]
+--------------------------- ES ----------------------------+
| DIRECTION READ                                             |
| Stair-step: 3 of 4 candles stepping UP -> upward bias     |
| 30-min SMAs: price > 50 > 200, both rising (trend gate ok) |
| In charge: prior institutional candle  |  MOC: validated   |
+------------------------------------------------------------+
| LEVELS (today + prior 2 days)              [Copy levels]   |
|  6512.25  US-close candle high   today      o untouched    |
|  6498.50  Europe candle low      today      x touched 10:14|
|  6471.00  Globex-open candle low Mon (-2d)  o in play      |
|  ...                                                       |
+------------------------------------------------------------+
| [30-min chart with levels drawn]   (phase 1.1, see §7)     |
| [Ask the coach about today's map]                          |
+------------------------------------------------------------+
(NQ card below / tab)
```

Page elements, in priority order:
1. **Direction read card** - the stair-step verdict, the sideways/containment state with
   the in-charge candle, the 30-min SMA trend gate, and the MOC-validated badge, in plain
   language. Directly beneath it: the **"FROM ANNE-MARIE TODAY"** insight slot (§4c.1) when
   she has posted, collapsed when not. Wording comes from fixed templates filled with computed values (NOT the LLM -
   no generation risk on the page every member screenshots). Educational framing: "the
   method reads this as" (e.g., sideways state -> "her rule: trade the edges, not the
   middle"), never "buy/sell."
2. **The Level Card per instrument** - every level with price, provenance (which candle,
   which day), and touched-status. **[Copy levels]** button outputs a clean text block
   (price + label per line) because the user's next act is pasting into THEIR platform -
   this one button is the whole "works with any platform" answer in V1.
3. **"Ask the coach about today's map"** - deep-links into the coach with today-context
   (see §4). This stitches the two halves of the product together.
4. **Recap strip** (after 4pm, fast-follow): which levels traded and what the method said.
5. Standing disclaimer footer (impersonal, educational, same map for every member).

**Morning notification:** email/push at ~7:30am ET ("Today's ES read: upward stair-step.
Map is live.") linking to Today. The fixed-time ritual is the retention habit; the map is
already complete by then (Europe candle closed 4:35am) with zero human involvement.

## 3b. Member-area layout, page by page (designed 2026-06-10 after visual review of the built site)

**Current-state read (screenshots in /tmp/site_review/):** the built member area is a welcome
hub (greeting + 3 cards + feed excerpt), a full-page coach chat, a flat ~50-row library list,
and a post feed. Clean, but static - nothing on it is dated TODAY, and the surfaces don't
reference each other. The redesign principle: **the site opens on the trading day, and every
page carries one hook into the next surface** (map -> coach, lesson -> coach, recap -> path).

**Navigation (base.html):** `Today · Coach · Learn · Feed` + account menu. Library renames to
Learn. The Dashboard/welcome hub is retired; `/app` IS Today. Persistent header chip showing
session state everywhere: "Pre-open - map live 4:35am" / "RTH - map live" / "Closed - recap
posted". That chip is the product's heartbeat made visible. Mobile: bottom tab bar (Today,
Coach, Learn, More).

**TODAY (`/app`) - desktop, two-column. Left = the day; right = the retention rail:**
```
[TradeWave Realtime]   Today  Coach  Learn  Feed     [RTH - map live]  [acct]
+--------------------------------------------+  +------------------------+
| Wed June 10 - DIRECTION READ                |  | DAY RAILS              |
| "Stair-step UP (3 of 4). Prior 3:30 candle |  | Stop ref: 3:30 width   |
|  in charge, MOC validated. 30-min SMAs     |  | Size: FULL (MOC ok)    |
|  aligned up. Her read: dips are buys."     |  | Max 5 trades - 0 used  |
| [stair-step] [in-charge] [MOC] [SMA gate]  |  | Flat by 3:00 ET        |
+--------------------------------------------+  | "Zero-trade day = win" |
| [ ES ] [ NQ ]                               |  +------------------------+
| LEVELS - today + prior 2 days  [Copy]       |  | ASK THE COACH          |
|  6512.25  3:30 inst. high  today  untouched |  | > Walk me through      |
|  6498.50  Europe low       today  10:14 x   |  |   today's map          |
|  6471.00  Globex low       Mon-2d in play   |  | > Why is 6498 key?     |
|  ...                                        |  +------------------------+
+---------------------------------------------+  | YOUR PATH  - week 2    |
| [30-min chart w/ levels]      (phase 1.1)   |  | Next: Entries, lesson 3|
+---------------------------------------------+  +------------------------+
| after 4pm: RECAP strip (fast-follow)        |  | FROM ANNE-MARIE (feed) |
+---------------------------------------------+  +------------------------+
```
The right rail is deliberate: discipline (rails), help (coach), progress (path), presence
(feed) - all four retention layers visible every single morning. Mobile stacks in that
order: read -> levels+copy -> rails -> coach chips -> path -> feed.
**Rail upgrade per §4 (the mentor layer):** the ASK THE COACH box is PERSONAL, not generic -
"Your focus this week: permission filters (lesson 2 of 3)" + the daily check-in prompt
(morning: "What's your plan today?" / after close: "How did it go?") + one context chip
tied to the member's named struggle and today's day type (e.g., for an overtrader on a
sideways read: "Sideways day - want to talk about the trade cap?").

**Today page states (the page is time-aware):**
- **Pre-open (before 4:35am):** map building - which candles are in, "Europe candle closes
  4:30am" next-event line.
- **Open hours:** full map, touched-status updating (when feed allows).
- **After close:** recap strip on top; map stays for review.
- **Weekend/holiday:** week-in-review + path nudge + "Globex opens Sun 6pm" countdown.
- **Feed failure:** honesty banner ("map delayed - engine retrying"), last good map shown
  with timestamp. Never silently stale.

**COACH (`/app/coach`):** keep the full-page chat; add (a) a context strip above the input:
"Your coach knows: today's ES + NQ map (June 10) + the method library" - the today-awareness
made visible and trustworthy; (b) daily-refreshed chips (today's map walk-through, the
stair-step, what changed vs yesterday) alongside the evergreen chips; (c) a collapsible
past-conversations list (threads exist in the DB already); (d) entry points everywhere else
deep-link here with context pre-seeded. Disclosure header/footer unchanged.

**LEARN (`/app/library` -> "The Method") - redesigned 2026-06-10 after Afshin's call-out
that the flat library is "an overwhelming amount of unorganized information."** Root cause:
the entries are the coach's RAG chunks made visible - machine-shaped, not learner-shaped.
The fix is structural, not cosmetic: **her method's own process IS the curriculum**, and the
page is that process. No separate "path + library" split - one staged curriculum:

```
THE METHOD                    Your progress: 12 of ~38 lessons
+----------------------------------------------------------+
| STAGE 1 - Read the day (7 lessons)            5/7 done    |
|   1 The four master candles                   [done]      |
|   2 The body stack - her direction read       [done]      |
|   3 Which candle is in charge                 [continue]  |
|   ...                                                     |
| STAGE 2 - The levels (8)                      locked-ish* |
| STAGE 3 - Permission to enter (8)                         |
| STAGE 4 - Manage the trade (7)                            |
| STAGE 5 - The trader's mind (8)                           |
+----------------------------------------------------------+
| Reference (collapsed): Glossary - Her vocabulary -        |
| How the coach works          [Search the method...]       |
+----------------------------------------------------------+
```
*Nothing is hard-locked (adults, reference use is legit) - stages render collapsed until
the prior stage is done, so the ORDER is the default experience but everything stays
reachable via search/expand.

The 5 stages map straight onto her process (and onto the transcripts):
1. **Read the day** - master candles, body stack/stair-step, containment + in-charge, MOC
   validation, the SMA trend gate, day type (trend vs sideways).
2. **The levels** - the level types, the 2-day lookback, watering hole, second-prettiest
   girl, measured moves.
3. **Permission to enter** - VWAP slope, hiken ashi, volume benchmarks, look-below-and-fail,
   failed-retest, limits only.
4. **Manage the trade** - level-to-level exits, no trailing, stop width, sizing, the caps,
   flat by 3:00.
5. **The trader's mind** - process over P&L, chasing/FOMO/revenge, zero-trade day,
   everything-is-a-shade-of-gray.

Each lesson page: ordered prev/next nav, [Ask the coach about this] pre-seeded, [Mark done].
Each stage ends with a zero-build checkpoint: a coach chip "Quiz me on stage N" (just a
pre-seeded prompt - the coach already knows the material). Glossary/vocabulary/faq entries
leave the curriculum and become collapsed reference + inline links.

Implementation = curation, not code: `stage` + `order` (+ `kind`: lesson/reference) columns
on KnowledgeEntry, a one-pass retitling of entries into learning language ("The four master
candles", not "Session time-anchors, the structural reference frames"), some merges. The
coach's RAG keeps using ALL entries regardless - curriculum and coach KB stay the same rows,
one admin tool for her. A `user_lesson` table tracks done-state. Today's direction-read
badges deep-link into their lessons ("MOC: validated" -> the MOC lesson) - the daily map
becomes the curriculum's front door.

**FEED:** as built, plus a pinned "Start here" post and her posts surfacing on Today's rail.

**ACCOUNT:** plan/billing (when Stripe lands), notification preferences (morning map
email/push, recap email), disclaimer status, sign out.

**First login (one-time, after the existing disclaimer gate): the INTAKE CONVERSATION (§4.1)
- the member meets the coach before they meet any page.** The coach asks the mentor
questions (where are you, what do you trade, what's the goal, what trips you up), builds the
trader profile and the first assignment, then walks them onto Today ("here's today's map -
this is where you start every morning; notifications on?"). Notification opt-in and
instruments happen inside the conversation, not in a form. The aha moment to engineer: "it
asked me what SHE would ask me" inside the first five minutes.

## 4. The coach as MENTOR, not Q&A bot (redesigned 2026-06-10 - Afshin's call)

**The reframe:** "If I went to the best trader and asked her to teach me, what would she ask
FIRST? Where are you in your trading? What do you want to achieve? How have you been doing?
As a trader I want to feel like someone is paying attention to me and genuinely wants to
help." A staged curriculum alone is every other educational site. The differentiator is the
RELATIONSHIP: the coach knows you, builds your plan, assigns the lessons as homework, and
checks in on you. This pulls the CORE of the V2 per-user layer into V1 (the deep
self-improving memory machinery stays V2).

**4.1 The intake (day 1 - replaces form-based onboarding).** A new member's first experience
is not a dashboard - it is the coach opening the conversation the way she would: where are
you in your trading; what do you trade (futures/stocks, prop/personal, micros/minis); what
do you want to achieve; how has it been going; what keeps tripping you up (chasing? sizing?
overtrading? hesitation?). Warm, in her voice, 5-6 questions, one at a time. From the
transcript an extraction pass writes the **trader profile**.

**4.2 The trader profile (bounded, visible, theirs).** A `user_profile` row: experience
stage, instruments, account context (prop/personal - NEVER dollar amounts), goal, named
struggles, schedule, plus a short rolling summary that updates as they talk. Surfaced on a
"What your coach knows about you" page - viewable, editable, deletable (the trust feature,
per the architecture guardrails: bounded, siloed per user, no cross-user leakage).

**4.3 The personal plan (homework, assigned by the mentor).** The coach maps profile ->
curriculum: a chaser starts at Permission filters, not candle anatomy; a sizing-breaker
starts at Manage the trade. Mechanic: a deterministic struggle->lessons mapping table picks
the assignment (auditable, no LLM whim); the coach phrases and frames it ("this week I want
you on these two lessons - here's why, given what you told me"). The Method page shows
"Assigned by your coach" on top; the full 5-stage curriculum sits behind it for browsers.
The lessons ARE the homework; the mentor is why they get done.

**4.4 Continuity (the "someone is paying attention" moment).** Every return visit, the
coach's greeting carries context: profile + last-session summary + today's map state.
"Yesterday you said you broke the 5-trade cap. Today's read is sideways - the day type where
overtrading bites hardest. What's the plan?" Implementation: inject profile + a lazily
generated summary of the last thread into the system prompt. Cheap on Haiku.

**4.5 The daily check-in (mentor accountability, light-touch).** One card on Today, two
moments: morning optional "What's your plan today?" one-liner; after the close "How did it
go?" - one sentence back, the coach reflects it against the method and the day's actual map
("you respected the cap on a sideways day - that is the win"). Answers accumulate into the
member's discipline history - which becomes the V2 discipline score with zero migration.
This is also the retention engine in its purest form: the thing you lose by leaving is the
mentor who knows your story.

**Guardrails (unchanged in spirit, sharpened here):** personalization serves TEACHING only.
The profile never stores positions, balances, or live trades; the coach teaches her sizing
RULES but never prescribes the member's size; check-in reflections are process-based, never
"you should have bought." All individualized-advice refusals stay exactly as built. Memory
is user-visible, editable, deletable; chat treated as sensitive data with a deletion path.

**Marketing note (supersedes the "hold memory for V2" decision):** V1 can now honestly say
"a coach that starts by asking where you are, builds your plan, and checks in on you daily."
The V2 relaunch headline narrows to the DEEP version ("months of memory, a coach that grows
with you"), which stays true and stays held back.

## 4b. Chat surface (V1 shape)

What exists is the right skeleton: persona + disclosure + RAG citations + no-trade-calls
guardrail, on a Haiku-class model. V1 changes:

1. **Today-awareness via deterministic injection** (the big one - and now SAFE, which is why
   it moves from V2 into V1: the numbers come from the engine's DB row, not from parsing or
   generation). The system prompt gains a TODAY block: today's levels + stair-step + MA
   posture + touched-status, labeled "published identically to all members, educational."
   The coach can answer "walk me through today's ES map," "why does the Europe low matter?",
   "what does the method say when the US-open candle high is retested?" - method teaching
   wrapped around real numbers. It still never says "you should buy 6498." Refusal behavior
   for "should I buy" stays exactly as built.
2. **Honest boundaries:** no live-price prediction, no news, no positions. "Where is ES right
   now?" -> last stored quote with timestamp, or "I read the levels, not the tape" when no
   intraday feed.
3. **Context chips refresh daily:** today-chips when a map exists ("Walk me through today's
   map," "Explain today's stair-step," "What changed since yesterday?") alongside the
   existing evergreen chips (trend gate, failed-retest, chasing/revenge, risk).
4. **Threads:** "New conversation" + a simple past-sessions list (model supports it; UI
   currently reuses one thread). Matters because the coach is the product members touch
   most - their history is the seed of the V2 per-user-memory relaunch.
5. Unchanged: persistent AI-coach label, first-use acknowledgment, educational-only,
   Haiku-class model, persona separability for wind-down.

## 4c. Her daily layer - insights and quizzes (added 2026-06-10; contract §3.2/3.3 now covers both)

**Design rule for everything she touches: her input is ADDITIVE, never load-bearing.** The
mechanical map + the coach deliver full daily value on her silent days; what she adds makes
great days. And her tools must respect her reality: minutes, not sessions; phone, not desk;
approve, not author.

**4c.1 Daily insights (capture -> timely publish).**
- **Her capture tool:** one mobile-first composer in her admin - a single text box ("What
  are you seeing today?"), optional instrument tag, one [Publish] button. Under 2 minutes.
  (Later: voice note -> transcribed draft -> tap to publish, matching "she talks for a
  living." V2: auto-draft from her morning YouTube briefing for one-tap approve.)
- **Where it lands, instantly:** a "FROM ANNE-MARIE TODAY" slot on the Today page directly
  under the direction read (timestamped, her avatar, distinct styling - the human voice
  over the mechanical map); archived to the feed; included in the morning notification when
  posted before send, otherwise a quiet badge on Today (no extra push - protect
  notification trust).
- **When she skips:** the slot collapses entirely. No empty "she didn't show today" hole,
  ever. The map carries the day.
- **Coach integration:** the day's insight is injected into the coach's TODAY block, so
  members can ask "what did Anne-Marie mean by inventory feeling heavy?" - her words,
  amplified by the mentor.

**4c.2 Quizzes (she assigns; the coach administers; she sees what the room is missing).**
The loop that makes her presence personal at scale - she cannot talk to 500 members, but she
can quiz them and teach to the gaps:
1. **Create/approve (her admin, "AI drafts, she approves"):** she picks a topic or lesson;
   the coach drafts 3-5 questions from that KB entry; she edits/approves (or writes her own
   from scratch). Choose audience - everyone, a curriculum stage, or members working on a
   named struggle - and a window (e.g., this week).
2. **Deliver (as the mentor, not a form):** the coach administers it conversationally:
   "Anne-Marie asked me to check how you're reading day types this week - three quick
   questions." Answers graded deterministically for multiple-choice, coach-assisted for
   free text; immediate teaching on each miss, in her voice. The member's misses update
   their profile struggles - the quiz literally tunes their mentoring.
3. **Close the loop (her results view):** aggregated, anonymized only (contract §3.4):
   "Day-type quiz - 78 taken, 61% missed containment-means-sideways." That gap list IS her
   agenda - next insight, next weekly teach-the-coach session, or next quiz. This is the
   improvement loop made concrete and driven by her.
- **Member surfaces:** an "Anne-Marie assigned you a quiz" card on Today + a chip in the
  coach; results live in their profile page.
- **Compliance:** quizzes test the published method; educational only; individual results
  private to the member (and their coach); she sees aggregates only.

**4c.3 The daily briefing digest (decided 2026-06-10 - Afshin's ask). BUILT phase one
2026-06-12 (`app/briefing.py` + `pull_briefing.py`, first real run = her "Short
Covering?" video, digested + published to the feed + injected into coach today-context;
number scrub verifies every quoted price against today's map - the only allowed numbers;
digest is Sonnet, labeled an AI digest, links to her video). Run MANUALLY each trading
morning for now (`pull_briefing.py`); remaining: the Today card, the ~7am ET timer with
caption-lag retries, and session-end context expiry (today_context currently carries it
all day; acceptable while manual).** Original design: server pulls her
daily Blueprint Open video (yt-dlp pipeline proven on 100 videos), Haiku extracts a
structured digest (per-instrument bias in her words, themes, quotes, levels she called),
and it lands in two places: a "short version" card on Today that ALWAYS links to the full
video (we summarize, never re-host - traffic goes to her channel) and the coach's
today-context, so members can ask "what did she say about NQ this morning" all day.
Rules: (1) provenance is distinct - auto-digest is labeled "Auto-summary of today's
Blueprint Open," never "From Anne-Marie today" (reserved for her typed insights, which
take priority in the slot); (2) ASR number safety - extracted numbers sanity-checked
against the engine's price context, dropped/flagged when implausible; the coach treats
digest numbers as quotes-from-video and the engine's levels as the precise map;
(3) day-specific content NEVER enters the evergreen corpus - the digest expires from
context at session end (archived in the feed); only the separate weekly net-new-method
harvest (her-approved) feeds the knowledge base. Poll from ~7am ET with caption-lag
retries; ~$0.02/day. Zero new work for her.

**Build cost:** insights = trivial (a tagged post type + the Today slot + coach injection).
Quizzes = a `quiz`/`quiz_question`/`quiz_result` set + the conversational delivery prompt +
her builder/aggregate views - roughly 3-5 days; sequence after the mentor core, before or
with the recap fast-follow. Both demoable as design (and the insight composer as working
software) at the meeting.

## 5. The rest of the site (mostly built - deltas only)

- **Learn** (`/app/library`): add the **4-week path** view - the existing 45 entries
  sequenced (week 1 read the day: master candles, stair-step, MAs; week 2 levels + entries;
  week 3 exits + risk; week 4 psychology) with a per-user progress checkmark. Sequencing +
  one progress table; no new content.
- **Feed**: as built (her posts via admin). Her presence layer, zero promised cadence.
- **Account**: as built; gains plan/billing when Stripe lands.
- **Landing page**: as built (positioning already reviewed); reworked to the paid offer +
  founding price when billing lands. The Today page (blurred sample map) becomes the hero
  demo - show the actual artifact, not abstractions.
- **Admin additions:** a **Levels monitor** - engine health (last run, per-candle capture
  status, data-feed errors), today's computed values with a manual-correction override
  (wrong data on paying members' charts is the worst failure mode; the override is the
  circuit breaker), and a notification preview. Plus the existing knowledge/posts tools.
- **Discord (BUILT 2026-06-10, awaiting Afshin's server setup):** one server, two tiers.
  Free tier = the funnel (#general, #briefing-talk, #coach-preview where the bot answers
  EVERGREEN method questions only, 5/day/user cap, #link-up). Member tier = the value
  (#morning-map read-only with the daily map drop + her insights, #trading-the-method,
  #wins-and-lessons, #ask-the-coach with the TODAY-AWARE bot). The dividing line is the
  no-trial principle: the perishable daily value never crosses the paywall. The bot
  ("AM Coach [AI]", disclosure on every answer) NEVER uses member personal profiles in
  public - Discord bot = the room's teacher; site coach = the private mentor. Role-sync:
  member generates a code on the account page, types !link CODE in #link-up; hourly sync
  follows subscription status once BILLING_REQUIRED flips. Her drop-ins remain
  surprise-and-delight, never a promised cadence. Implementation: app/discord_bot.py +
  run_bot.py + tradewave-rt-bot.service (idempotent channel/role setup on boot); SQLite
  in WAL mode for the two processes. Launch WITH the founding cohort, not before.

## 6. The subscriber's day (the max-value loop, end to end)

- **7:30am** - phone: "Upward stair-step on ES. Map is live." Opens Today, reads the
  direction card, hits [Copy levels], pastes into their platform. Ninja users skip even
  that - the indicator drew the map at 4:35am.
- **10:05am** - map updates with the US-open candle; stair-step read firms up.
- **Intraday** - price approaches the Europe low; member asks the coach "method says what
  here?" and gets the failed-retest teaching in her voice, with the actual level in context.
- **2:05pm** - the 1:30 watch candle posts: reversal marker on or off.
- **4:05pm** - day completes; recap strip (fast-follow): "US-open low traded at 11:42 and
  held - textbook level-to-level rotation."
- **Evening/weekend** - path lesson, her feed post, evergreen coach questions.

Every beat is automatic. Anne-Marie's required daily input: zero. Her weekly 15 minutes
keeps making the coach more her; her promotion fills the funnel. Cancel = the map goes dark
tomorrow at 4:35am - that is the churn lever.

## 7. The dynamic chart decision (recommendation)

Users have their own platforms - the site must NOT try to be one. But a small read-only
30-min chart with the levels drawn earns its place for three reasons: a level table is
legible in numbers, a chart is legible in one glance; non-Ninja members (most of her
stock-audience) get a visual nowhere else; and "is price near a level right now" is the
reason to RE-OPEN the site intraday rather than only at 7:30am.

**Decision: Level Card + direction read are V1-core and work on bars alone. The chart is
phase 1.1, gated only on the data-feed verification (§2), using a lightweight client
renderer with delayed/15-min-refresh data. Level-proximity alerts ("ES within 5 pts of the
Europe low") are phase 1.2 - the strongest intraday re-engagement hook, same feed.**

## 8. Build deltas vs what exists (scope of the V1 build)

1. Levels engine: feed adapter (EODHD verify first) + candle capture jobs + the
   levels/direction table + touched-status updater. **The critical path.**
2. Today page per §3b (two-column, time-aware states, retention rail) replacing the
   dashboard + morning email/push + [Copy levels] + nav rename and the session-state header
   chip + first-run 3-step setup.
3. Coach-as-mentor core (§4): intake conversation + `user_profile` (+ "what your coach
   knows" page with edit/delete) + struggle->lessons assignment mapping + continuity
   injection (profile + last-session summary) + the Today check-in card.
4. Chat surface: TODAY block injection + context strip + daily chips + thread list.
5. Learn: 5-stage curation + progress (`user_lesson`) + assigned-first view + per-entry
   "ask the coach" footer.
6. Admin: Levels monitor + override + her insight composer (mobile-first) + quiz
   builder/aggregates (§4c).
7. WorkOS swap (same application/user pool as EOD - one TradeWave identity; staging keys
   in dev; merge existing accounts by email; do this BEFORE Stripe so billing keys to the
   durable identity).
8. Billing (Stripe, $99 founding / $149 / annual, `product_line=rt`) + member gating of
   /app + the EOD 3-month comp grant (manual during founding window, webhook-automated
   later; comp expires with explicit upgrade invite, never auto-converts).
9. Indicator licensing + the Ninja listing. **ARCHITECTURE FACT (corrected 2026-06-12,
   Afshin): the indicator computes the levels LOCALLY from whatever data feed the member
   runs in NinjaTrader** - no levels feed from us. Wins: no CME redistribution-licensing
   exposure (their licensed feed does the work), true real-time on broker feeds (better
   than our delayed capture), zero dependency on our infra mid-session, runs her method
   on ANY chart (YM/CL/GC too - a perk the site can't match).
   **Licensing (since a copied DLL is fully functional): membership KEY validated by the
   indicator against our server** - machine binding, offline grace of a few days, key
   dies on lapse/refund. One phone-home on load returns license status + METHOD CONFIG
   (candle windows, thresholds - server-driven so method confirmations never require a
   DLL redistribution; baked-in defaults as fallback) + current version (member-area
   download nudge; Ninja has no auto-update). NinjaScript decompiles easily - the bar is
   casual-sharing protection per the brief, not perfection. NO trial keys (a locally
   computing indicator on a trial key leaks the daily value - same logic as no free
   trial).
   **Consistency risk to manage:** members WILL diff indicator numbers vs the site map;
   feeds vary by ticks. Mirror the engine's canonical rules in the indicator (incl. the
   stair-step gap-bridging and validation fixes) and optionally pull the official map
   once per session for a "matches the official map" chip, labeling tick differences as
   feed variance - turns a support question into a trust feature.
   **Pricing (recommended 2026-06-12, pending Afshin's confirm): included with
   membership, FREE download, no one-time charge, no separate indicator subscription**
   (one-tier rule; the indicator is the retention surface). Listing = acquisition
   channel (free, her licensed name, a marketplace full of futures day traders); state
   NT8 support explicitly. A standalone indicator-only subscription is deliberately HELD
   BACK at launch (cannibalizes $99; agreement §5.2 already covers it if revisited -
   price near $99, never undercutting). TradingView cannot call external endpoints (Pine
   sandbox) - it would be a different mechanism; platforms that can do HTTP reuse the
   same license/config endpoint.
10. Phase 1.1/1.2 (post-launch, same feed): site chart, proximity alerts, recap strip.
11. **Her SESSION REVIEW slot (decided 2026-06-12):** a second daily her-content slot
    beside the insight - "how I traded today" captured through her composer (typing or
    dictation), published to Today + the feed, and injected into the coach's today-context
    so members can discuss her day with the bot. Same pipeline as the insight (new Post
    kind `session_review` + a today_context line). Educational process recap framing
    (what she saw, why she acted, what the map said) - NEVER a P&L scorecard; the format
    is on the attorney list (futures performance-presentation rules). Founding-window
    build, not launch-blocking.
12. **The TRADE DEBRIEF - COMMITTED founding-window deliverable (upgraded 2026-06-12,
    Afshin: "actually necessary not optional"; direction decided 2026-06-10):** the member
    describes a trade they took; the coach grades it against her rules DETERMINISTICALLY
    using the day's computed map (was it at a map level? day-type aligned? edge vs middle?
    size vs MOC state?) then teaches from it in her voice and remembers the pattern in the
    profile. The human-mentor service that costs thousands, nightly. Compliance posture:
    reviews PAST trades against published impersonal rules - education, never direction.
    Reuses the levels engine + profile; no new architecture. NOT launch-blocking - June 24
    ships without it; it lands during the founding window as the visible roadmap promise.
    **Phasing (the debrief does NOT wait for the indicator):** Phase A (founding window) -
    chat-described trades: Haiku parses "long 2 ES at 7341 at 9:42, out 7349" into a
    structured trade, a deterministic grader (pure function over the DayMap) scores it,
    the coach teaches the correction. Phase B - the indicator's "Ask my coach about this
    trade" right-click automates entry of a single trade. Phase C - opt-in end-of-session
    auto-sync + pattern memory. Her side: the aggregate-gap view from graded trades writes
    her weekly 15-minute teaching agenda.
    **Indicator trade-sync as the debrief's data source (direction set 2026-06-12):**
    the Ninja indicator can send the member's COMPLETED trades to the backend. BRIGHT
    LINE (compliance-critical): completed round-trips only, NEVER open/live positions -
    the coach must never know what a member is holding right now (past trades =
    education; present positions = advice territory). Consent shape: off by default,
    explicit opt-in toggle + account-page consent, member picks which Ninja account
    syncs (prop evals), every synced trade visible + deletable on the profile page,
    Anne-Marie sees aggregates only (contract §3.4). Data shape: instrument, side,
    contracts, entry/exit price, timestamps; NEVER account numbers or balances; dollar
    P&L never computed or shown - process grades + points only. (This consciously
    refines the "never store positions/dollar amounts" rule: that rule still governs
    the chat profile fully; consented fills live in a separate store under the above
    constraints.) Build order: license phone-home at launch (license + method config +
    version in ONE call, which doubles as minimal disclosed telemetry: indicator/NT
    version, error flag); "Ask my coach about this trade" right-click in the founding
    window (member-initiated single-trade send, pre-graded vs the map, opens a chat
    thread - the trust-building v1); full opt-in end-of-session auto-sync + pattern
    memory lands with the Phase 1.5 debrief. Post-launch nicety: her insight/session
    review as an optional chart-panel line (same payload as the map sync-check).
    **Competitive position (researched 2026-06-12):** generic "AI reviews your imported
    trades" is COMMODITY (TradeZella/Zella AI, TradesViz, TraderSync etc.); AI personas
    of named coaches exist (Trader Brian AI) but none see your trades. The unique
    compound = named educator's method twin + deterministic grading vs HER map for that
    day + her voice + her correction loop + relationship memory; §6 exclusivity is the
    moat for it. CLAIM GUARD for all marketing copy: never claim "first AI trade
    analysis" (false); the claim is "the only coach that grades your trades against
    Anne-Marie's actual levels for that day" - specific, true, needs no competitor
    names (house rule: none in customer-facing copy).

## 9. Open confirms (small, none blocking design)

1. ~~Europe candle time~~ **RESOLVED 2026-06-10 from the strategy transcripts:** 4:00-4:30am
   ET (`AM_rules_comprehensive.md` §2; the autotrader SPEC's 3:00-4:00am is the outlier and
   should be corrected there too). Candle windows stay config values per instrument.
2. **MA timeframe:** transcripts = 50/200 PERIOD SMAs on the 30-min chart (stack + slope);
   Afshin's note said 200-day/50-day. Engine computes the 30-min stack as primary; confirm
   with Afshin/AM whether the daily MAs also appear on the direction card.
3. **EODHD ES/NQ intraday entitlement** - the §2 verify step, including overnight Globex
   bars AND volume (volume gates the MOC-validated badge; without it the badge ships later).
4. **Her discretionary layer** (gamma walls, fibs from the briefings): explicitly NOT in V1.
   The mechanical engine is the product; her video stays her free channel that markets it.
   Revisit as an additive layer only if members ask for it.
5. **Known method tensions to settle via her weekly coach-teaching loop** (already staged
   per the transcripts doc §16, not V1 blockers): stop width 3:30-candle vs Europe-candle,
   anchored VWAP (pipeline invention, she does not teach it), slope thresholds.
