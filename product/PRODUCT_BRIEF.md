# TradeWave Realtime - Product & Offering Brief (READ FIRST)

> **What this is:** the canonical product/offering brief for TradeWave Realtime, written 2026-06-10
> from the business-strategy session on the TW2 dev box (.176). Any session designing the offering,
> the site, the coach, or the launch starts HERE. The deal contract draft lives at
> `/home/flask/TradeWave_RT_AnneMarie_Agreement_DRAFT.md` - it SHAPES the product (see §3).
> Keep this file current: update it in the same session as any decision that changes it.
> **The product north star (the goal, the mechanism, and the success model) is `FOUNDATION_SPEC.md` -
> read it first; this brief carries the business context, deal, pricing, and offering specifics that sit
> under that goal.**

## 0. The Goal (north star - corrected and sharpened 2026-06-16; full text in `FOUNDATION_SPEC.md`)

**Be the single most valuable resource in the world for learning and executing Anne-Marie Baiynd's
intraday strategy - better at teaching it than she is herself - so that any trader, from absolute
beginner to advanced, becomes a fluent, disciplined, and profitable executor of a rules-based intraday
strategy of their own, built from hers.** A digital AI Anne-Marie working alongside the real one: 24/7
interactive coaching that takes a trader at any level toward mastery, short of ever telling them what to
trade; it captures each subscriber's history to help them implement and rectify their execution; and
when it cannot clearly answer, the real Anne-Marie is notified to make it smarter for everyone. Success
is the subscriber's mastery and execution, measured money-blind across comprehension (quizzes),
application (drills), performance (trades graded vs the map), sentiment, and self-report, rolled up by
the coach's per-trader assessment. Decisions are settled against the decision rule in `FOUNDATION_SPEC.md`
§13. (This corrects the earlier "retention through the feeling of attention" framing: mastery is the
center; retention is its byproduct.)

## 1. Why this product exists (business context)

- Afshin (Tara Data Research LLC, sole operator) has a hard goal: **revenue within 60 days
  (~by 2026-08-09)**. TradeWave Realtime is the #1 lever because it is the only asset with a
  built-in audience attached: **Anne-Marie Baiynd (AMB)** - well-known trader/educator
  ("The Trading Book"), large reach, and SHE requested this product, so she will promote it.
- The sister product is **TradeWave EOD** (tradewave.ai, seasonal-pattern SaaS, 22 paying /
  ~200 free, runs on the TW2 stack on the .176-lineage boxes). RT and EOD cross-sell both ways;
  a "TradeWave Complete" bundle is anticipated in the contract's bundle formula.
- Afshin is a technologist, not a marketer, with small resources. Every design choice must favor
  shipping v1 fast over completeness. **Target: v1 launchable ~2026-06-24.**

## 2. Audience

AMB's followers: retail intraday and short-swing traders (futures and stocks) who follow her
morning briefings and want to trade HER method. They buy access, levels, and learning - not
software features. They are accustomed to $99-149/mo trading-community pricing.

## 3. The deal (product-shaping facts - full text in the agreement draft)

- AMB is an **independent contractor and affiliate**, NOT an owner. The site, software, coach,
  knowledgebase, brand, and customers belong to the Company.
- Her fee: **35% of NET Real Time Revenue** (gross subscriptions minus processing fees, refunds,
  chargebacks, sales tax), paid monthly with a statement. An advertising provision may adjust
  the split slightly (pending). Build the revenue statement/report with this exact definition.
- **Bundle rule:** for an EOD+RT bundle, RT's share = RT standalone price / sum of standalone
  prices x net bundle revenue. Pricing design must keep standalone prices defined.
- **The "Anne-Marie" AI coach is the contractual centerpiece** - an AI trained on her method and
  trading psychology. HARD requirements from the contract: always clearly disclosed as an AI
  trained on her, never represented as Anne-Marie herself; educational only; **never gives
  individualized buy/sell calls**; she gets review/correction rights on how she is represented.
- Her ongoing input (contract updated 2026-06-10): ~15 min weekly coach-teaching session +
  best-efforts SHORT DAILY INSIGHTS for subscribers (no quota, no penalty; the product's
  core daily value never depends on them) + periodic SUBSCRIBER QUIZZES she creates or
  approves (she sees aggregated anonymized results only) + best-efforts promotion. Design
  for her layer: `V1_SITE_DESIGN.md` §4c.
- Exit: 75-day notice, 90-day wind-down (de-identify/rename the coach, keep the product and
  customers). Design the coach so the persona layer is SEPARABLE from the engine (a renameable
  persona on top of a generic coaching engine), so wind-down is a config change, not a rebuild.
- **Contract is a DRAFT - not signed yet. Signing precedes launch.** Lawyer review pending.

## 4. The offering (DECIDED - challenge only with evidence, not taste)

**Positioning, one sentence:** "Trade with Anne-Marie's levels on your chart, learn her method
from her own words, in her room."

Three value layers, in priority order:

1. **Her LEVELS, computed her way every session - the "Daily Level Map".** HER LEVELS ARE
   MECHANICAL (corrected 2026-06-10, VERIFIED against the strategy transcripts at
   `/home/flask/baiynd_autotrader/video_transcripts/` - the canonical method source): the
   4 master candles (institutional/MOC 3:30-4pm, Globex open 6-6:30pm, Europe open
   4-4:30am, US open 9:30-10am ET, + the 1:30-2pm watch candle), kept in play for today +
   prior 2 days, with a three-state direction read (master-candle STAIR-STEP up/down,
   containment-overlap = sideways "trade the edges" + the in-charge candle), the 30-min
   50/200 SMA stack+slope trend gate, and the MOC 20%-volume validation badge. A server-side levels engine computes the map from
   intraday futures data (EODHD if its ES/NQ intraday coverage verifies - UNCONFIRMED, check
   first; feed is pluggable) - automatic, never skips, zero daily work for her. ES + NQ at
   launch. Delivered three ways: the Today page on the site, the NinjaTrader indicator
   (built - see `/home/flask/baiynd_autotrader/`; to be listed on the Ninja platform), and
   Discord/notifications. **Decided 2026-06-12: the indicator is INCLUDED in the
   subscription** (not a separate product; its revenue is subscription revenue, inside the
   35%); indicators for additional platforms come post-launch on the same gated feed.
   Levels are perishable daily value - that is the retention engine.
   Full design: `V1_SITE_DESIGN.md`. The indicator's levels feed must be gated on an active
   subscription (licensing/auth design still needed - §8 Q2).
2. **Her METHOD, on demand.** The AI coach over a knowledgebase of 6 strategy videos Afshin made
   with her + 60 of her morning briefings (transcripts in `/home/flask/am_youtube/`; app skeleton
   + knowledge_seed in `/home/flask/tradewave_realtime/`). Position it as "her teaching
   assistant," speaking from her own words, available when she is not.
3. **Her PRESENCE.** A Discord server with a defined daily heartbeat: her morning briefing drops
   + levels push to the indicator at the same moment. Her live cadence should be stated (the
   contract says best-efforts promotion + weekly teaching; any in-room cadence promised to
   members must be agreed with her, not assumed). **Two additions decided 2026-06-12:**
   (a) her daily SESSION REVIEW - a short "how I traded today" note published to all
   subscribers and visible to the coach's today-context. Framed as an educational process
   recap (what she saw, why she acted), NEVER a P&L scorecard; the format goes on the
   futures-attorney list with the live-trading rules. Best efforts, her option, no quota.
   (b) her appearances (Discord drop-ins etc.) run on a PUBLISHED SCHEDULE she controls in
   her admin (the Appearance tool, built 2026-06-10) - members and the coach may cite only
   what she has published.

**Pricing (decided; rationale in `V1_OFFERING_DESIGN.md` §5b):** ONE tier at launch,
everything included. **$99/mo founding rate, LOCKED while continuously subscribed** (rises to
$149 for new members after the founding window; NEVER raise on an existing subscriber - the
lock is a retention feature), **annual $990** (~2 months free, pushed at checkout),
**pause-don't-cancel** (up to 2 months, keeps the founding rate) in the cancel flow. No tier
matrix in v1 - every added option costs clarity and build time. Standalone price must stay
defined for the bundle math.
Billing via the Company's Stripe. **Trial: DECIDED 2026-06-10 - NO free trial** (a levels
product's daily value is consumable in one morning; a trial is drive-by scraping). Risk
reversal instead: **14-day money-back guarantee** (card-up-front friction deters scrapers;
refunds net out of revenue before the 35% split). Revisit only with conversion data.

**v1 scope - IN:** the levels engine (feed adapter + master-candle capture + direction read,
serving the Today page / coach / indicator / notifications from one table), the Today page,
indicator + gated levels feed, Discord (role-sync gated, automated heartbeat), content library
(videos + briefings), the coach as MENTOR (decided 2026-06-10, Afshin: "I want to feel like
someone is paying attention to me" - intake conversation as onboarding, bounded trader
profile, personalized lesson assignment, continuity greetings, daily check-in; the CORE of
the per-user layer pulled into v1; design in `V1_SITE_DESIGN.md` §4), "The Method" staged
curriculum (the existing ~46 KB entries re-organized into her 5-stage process - read the day,
levels, permission, manage, mindset - curation not new content, presented assigned-first;
`V1_SITE_DESIGN.md` §3b), her daily-insight slot + composer (additive, never load-bearing)
and the quiz loop (she assigns, the coach administers, she sees aggregate gaps;
`V1_SITE_DESIGN.md` §4c - quizzes may trail launch by 1-2 weeks without member-facing harm),
signup/billing, landing page.
**v1 fast-follow (founding window, not launch-blocking):** the 3:00 ET Recap - auto-drafted,
admin-approved post on which map levels traded; closes the daily loop. **And the TRADE
DEBRIEF Phase A (upgraded to COMMITTED 2026-06-12 - "necessary not optional"):** member
describes a trade in chat, a deterministic grader scores it against that day's map, the
coach teaches the correction in her voice. No indicator dependency (chat-first); the
indicator right-click send and opt-in auto-sync follow (`V1_SITE_DESIGN.md` §8 item 12,
incl. the completed-trades-only bright line). Competitive basis researched 2026-06-12:
generic AI trade review is commodity; grading against HER method's daily map in her voice
is the unique compound, protected by the agreement's §6 exclusivity.
**v1 scope - OUT (v2):** DEEP per-user memory (months-long compounding history + the
self-improving gap/trainer loop - the V2 relaunch headline narrows to this) and PROACTIVE
unprompted coaching outreach; multi-tier; mobile apps; anything else. (The today-aware coach
moved INTO v1 2026-06-10 - deterministic level injection made it safe.)
**Retention design + churn countermeasures (churn target <5%/mo founding cohort):**
`V1_OFFERING_DESIGN.md` §3. Hard rule from it (refined 2026-06-12 now the schedule tool
exists): the ONLY live Anne-Marie time ever promised to members is what SHE has published
in her schedule tool; everything else stays surprise-and-delight, never an SLA.

**Live events (framework decided 2026-06-12, agreement §5.6):** education and
live-trading events run SEPARATE from the subscription, managed and funded by Tara Data
Research; her participation voluntary per event; split agreed in writing per event before
announcement, anchor [50%] of NET event revenue AFTER direct documented event costs
(costs recoup off the top, so the contract safely allows in-person formats too).
Near-term events planned ONLINE-ONLY for economics; do not pitch in-person.
Live-trading formats ship only after the futures attorney blesses them.

## 5. Launch plan (summary - detail lives with the marketing workstream on .176)

She announces to her audience + one joint live webinar (live demo converts trading audiences
best). Founding-member window creates urgency. Cross-sell: EOD pitched inside the RT Discord,
RT pitched to the EOD list. AMB is also an EOD affiliate - her pushes coordinate.

## 6. Hard guardrails (do not violate)

- **Educational and impersonal only. The coach NEVER gives individualized buy/sell calls or
  personalized advice** (contract §Compliance + the same publisher-exclusion rule TradeWave EOD
  follows). Disclaimers on all signal-bearing content.
- **AI disclosure:** the coach is always presented as an AI trained on her - never as her.
- No em-dashes in any content (use " - "); no competitor name-drops in customer-facing copy.
- Coach runtime model (DECIDED 2026-06-10 after live A/B + cost modeling): member-facing
  chat on Sonnet 4.6, mechanical jobs on Haiku 4.5 - NOT a frontier model. Architecture:
  the FULL method corpus (~11k tokens) is a prompt-cached system prefix shared by all
  members (replaces RAG for chat; retrieval keeps powering the related-lesson chips).
  Measured cost ~$0.015/message; typical member well under $1/mo. No per-message model
  routing (the router would fail at the highest-stakes messages; caches are model-scoped).

## 7. What exists where

On THIS box (tradewave-rt, 192.168.1.177):
- `/home/flask/tradewave_realtime/` - the site/app (Flask; has its own SPEC.md + knowledge_seed).
- `/home/flask/baiynd_autotrader/` - the NinjaTrader indicator project (AMTradeCockpit v2.6/v3,
  its own SPEC.md, reviews, video transcripts).
- `/home/flask/am_youtube/` - her video/briefing transcripts (.vtt) - the coach KB raw material.
- `/home/flask/TradeWave_RT_AnneMarie_Agreement_DRAFT.{md,docx}` - the deal.
- `/home/flask/product/` - this brief + `V1_OFFERING_DESIGN.md` (value/retention design,
  trial decision) + `V1_SITE_DESIGN.md` (the levels engine, Today page, chatbot, subscriber
  journey - canonical for the site/coach build) + `COACH_BLUEPRINT.md` (the state-of-the-art
  coach big picture: memory/history, proactivity, Anne-Marie's input loop, quizzes,
  lifecycle - canonical for all coach evolution; 6-lens research workflow, 2026-06-10).

On the TW2 EOD dev box (192.168.1.176, repo github.com/afshinmoshrefi/tradewave-tw2): the whole
EOD ecosystem map (`docs/TRADEWAVE_ECOSYSTEM.md` - READ FIRST over there), the affiliate program,
Stripe/WorkOS/MailerLite wiring knowhow, and the Tara chatbot pattern worth reusing.

## 8. Open design questions for the NEXT session (the detailed offering design)

1. **Levels pipeline: DESIGNED 2026-06-10, revised same day** (`V1_SITE_DESIGN.md` §2) - a
   mechanical server-side levels engine (master candles + 2-day lookback + MA/stair-step
   direction read) computed from intraday futures data. Pre-open map complete by ~4:35am ET
   automatically; map updates as each master candle closes. No skip days by construction.
   GATE: verify EODHD ES/NQ intraday (incl. overnight Globex bars) before building the
   adapter; feed is pluggable if not. Remaining: build it.
2. **Indicator licensing:** how the NinjaTrader indicator authenticates a subscription (key
   check against the RT backend? expiry-token?). Must survive sharing/piracy casually, not
   perfectly.
3. **Coach architecture:** KB chunking/retrieval over the transcripts, persona prompt (separable
   per §3 wind-down), disclosure line, refusal behavior for advice-seeking questions.
4. **Auth + billing wiring: DECIDED 2026-06-11** - same WorkOS application/user pool as EOD
   (one TradeWave identity; RT on staging env keys now, prod at launch; existing dev
   accounts merge by email). Sequence: WorkOS swap BEFORE Stripe. Stripe stays separate RT
   products with `product_line=rt` metadata; monthly AMB statement per the §3 net-revenue
   definition. Founding sweetener (leaning yes, Afshin to confirm): 3 months of EOD
   included as a COMP entitlement that expires with an explicit upgrade invite (never an
   auto-converting trial), granted manually during the founding window, automated later.
   Revenue rule: the EOD comp is a Company marketing cost - the FULL $99 stays in Net RT
   Revenue for AMB's 35%; no allocation to EOD.
   **Cross-movement SETTLED 2026-06-12 (shape) with one duration call pending:**
   RT→EOD: **CONFIRMED 2026-06-12 - every new RT member gets 3 months of EOD (Analyst)
   comped.** NO agreement change needed (full $99 stays in Net RT Revenue; comp =
   Company marketing cost, as decided).
   **RT member upgrades to PAID EOD (decided lane 2026-06-12):** flows through the
   SEPARATE, pre-existing EOD affiliate agreement with AMB (fact surfaced 2026-06-12 -
   such an agreement exists), NOT the RT agreement: attribution rule = an EOD sub
   opened by a current/former RT member counts as her referral at that agreement's
   rate. During the comp: $0 owed anywhere. RT agreement §5.2 now names this seam;
   open item: attorney reads BOTH agreements together + the EOD agreement may need a
   side letter if its attribution is link/code-based.
   EOD→RT: NO free RT for EOD subscribers in any tier - they get the funnel (free
   Discord tier + founding-rate invite). Preserves $99 integrity and AMB's revenue base.
   Mechanism: explicit COMP ENTITLEMENT on the EOD side keyed off the shared WorkOS
   identity (manual during founding window, automated later via the shared Stripe
   account) - NEVER via webhook mirroring of EOD Stripe subs (RT webhook filters
   product_line=rt as of 2026-06-12; paid-vs-comped must stay distinct for the AMB
   statement).
   Also confirmed 2026-06-12: RT production billing = SAME Stripe account as EOD,
   extended as a new product line (product_line=rt metadata, rt_* lookup keys).
5. **Discord gating:** subscription-linked roles (bot-managed), and what is public vs member-only.
6. **Domain/brand:** realtime.tradewave.ai vs its own domain - weigh SEO, the bundle story, and
   the wind-down clause (the brand is TradeWave Realtime, hers is licensed).
7. **Trial policy: DECIDED 2026-06-10** - no trial, 14-day money-back guarantee (see §4).

**The decision rule for everything: does it move the ~2026-06-24 v1 launch? If no, it waits.**
