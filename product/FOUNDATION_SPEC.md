# TradeWave Realtime - Foundation Spec (the north star)

> **Canonical. Written 2026-06-16.** This is the foundation of all effort on TradeWave Realtime.
> It corrects and replaces the earlier "retention through the feeling of attention" framing of the
> goal. The coach, the curriculum, the site, the support agents, the Discord, the launch - all of it
> serves THIS. When any decision is ambiguous, settle it against §13 (the decision rule). Keep this
> file current: any decision that changes the goal, the mechanism, or the success model updates it in
> the same session. Business context, pricing, the deal, and the offering specifics live in
> `PRODUCT_BRIEF.md`; the build design lives in `V1_SITE_DESIGN.md`. This document is the WHY and the
> WHAT-FOR that both of those serve.

---

## 1. The goal, in one sentence

**Be the single most valuable resource in the world for learning and executing Anne-Marie Baiynd's
intraday strategy - better at teaching it than she is herself - so that any trader, from absolute
beginner to advanced, becomes a fluent, disciplined, and profitable executor of a rules-based
intraday strategy of their own, built from hers.**

## 2. The goal, in full

Anne-Marie Baiynd has traded successfully for nearly two decades and has developed a proven intraday
strategy (mostly ES and NQ, the micros MES and MNQ, occasionally GC and CL). Her method is proven but
complex - and when she teaches it, her own depth of mastery sometimes makes it sound harder than it
needs to be. Traders who learn it find that it eventually feels simple, "like driving a car," but many
never get there because the on-ramp is steep and intraday trading is unforgiving.

TradeWave Realtime exists to fix exactly that. It is a **digital AI Anne-Marie working alongside the
real one**: an always-on coach, plus supporting agents and features, that gives every subscriber
interactive hand-holding 24 hours a day - the next best thing to having Anne-Marie herself beside them
at every step, short of ever telling them which trade to take. It takes a trader at any level and
moves them toward fluent, profitable execution of their own rules-based intraday strategy, built from
hers. It captures each subscriber's history so it can help them **implement and rectify** their
execution over time. And when it cannot clearly answer something, the real Anne-Marie is notified to
make the coach smarter for everyone. She monitors, occasionally joins a Discord group where members can
reach her directly, and her ongoing teaching keeps the coach's knowledge authoritative and growing.

Success is measured by the subscriber's mastery and execution - not by the platform's feature list.

## 3. Why "better than Anne-Marie at teaching" is the bar (and why that is not arrogance)

She will always be the **source of truth** - the proven method is hers, and nobody understands it more
deeply. The product is not trying to out-trade her or replace her. It is trying to be a **better
teacher of her method than she is**, which a tool can genuinely be, for reasons that have nothing to do
with talent:

- **Mastery hides the ladder.** An expert who has internalized a skill forgets which rungs the beginner
  is missing, and answers at her own altitude. The product never forgets the ladder.
- **Simplification on demand.** The product can present the same idea five different ways, define every
  term, and shrink the complex to its simplest true form for the trader in front of it - "like driving
  a car."
- **Infinite patience and availability.** It is there at 2:47 in the afternoon, on the 40th repetition
  of the same question, without fatigue or judgment.
- **It remembers the individual.** It knows what this trader already learned, what they keep getting
  wrong, and what they did yesterday - so it teaches the next thing, not the same thing.

That combination - her proven method, made simple, taught patiently, 24/7, with perfect memory of you -
is a better teacher of her strategy than any human could be, including her. That is the bar.

## 4. What this product is NOT

- **Not a signal service.** It never tells anyone what to trade, when, or how much. It teaches them to
  decide.
- **Not a get-rich product.** It promises mastery of a process, never profit.
- **Not a generic chatbot or a content library.** Access to her videos is not the product; *learning to
  trade her way* is.
- **Not a clone that competes with or replaces her.** It works alongside her and routes the hard
  questions back to her.
- **Not an advice or advisory service.** It is education, bounded by the guardrails in §12.

## 5. What "success" means for the subscriber

Success is **mastery of the process**, which in her own philosophy precedes and produces profit
("process over P&L, make money without losing money"). Concretely, a successful subscriber can, on their
own and with discipline:

1. **Read the day** - grade the trend, map the levels, know whether today is even a day to trade.
2. **Wait for permission** - let price come to a level, take her kind of entry, never chase.
3. **Manage the trade** - exit level to level, size small, respect the rules and the cutoffs.
4. **Manage themselves** - handle fear, FOMO, and the red day without breaking their rules.
5. **Execute their own rule set** - a personal, written, repeatable strategy built from hers, and
   **correct it over time** from their own results.

Profit is the byproduct of that mastery. We pursue and measure the mastery; we never promise the profit.
The destination for every subscriber is **their own executable playbook, provably derived from her
method** - not a dependence on the coach forever, but a trader who has internalized the strategy.

## 6. The teaching spine - master hers, then adapt (tier-aware)

Everyone ends at the same destination (their own executable strategy); the **on-ramp differs by where
they start**, which the coach detects (beginner / developing / experienced):

- **Beginner / intermediate - "master hers, then adapt."** They have no coherent system, or a broken
  patchwork. Fidelity first: learn her exact method to fluency (the standard car), then, once fluent,
  the coach scaffolds them into adapting it to their instrument, schedule, risk, and temperament. A
  true beginner starts below even that, on the Foundations floor (what a candle, a contract, a session
  is) so they never hit a cliff.
- **Advanced - "augment what you already do."** They already have a working method. The product does
  NOT tell them to start over. Their method is the base; Anne-Marie's is the source of upgrades. The
  conversation is "you already trade - here is what she does at the open, with the institutional candle,
  with her risk discipline, that could sharpen *your* read." Their edge is respected; hers is grafted
  in.

Same mentor, different conversation by level. This is how a real master teaches: a beginner gets the
whole system; a veteran gets the one sharpening insight. The "successful **or more successful**"
language in the goal is exactly this - we serve both the trader building their first system and the
trader improving an existing one.

## 7. The mechanism - how the product actually creates mastery (the teaching engine)

This is the core of the product, the thing every feature serves. Mastery is produced by a repeating
loop the coach drives the subscriber through, at rising fidelity over time:

> **Learn -> Apply -> Do -> Reflect & Rectify -> Remember -> (repeat, harder)**

1. **Learn** - her method, simplified and scaffolded to the trader's level, on demand and in sequence.
2. **Apply** - practice in a safe setting (sim, and scenario drills: "here is today's map, where would
   you enter and why?") before real money.
3. **Do** - take real (or sim) trades and bring them back.
4. **Reflect & Rectify** - the coach debriefs each trade deterministically against that day's map (at a
   level? with the gate? sized right? exited level to level?) and teaches the correction in her voice.
   This is where leaks get found and fixed.
5. **Remember** - the coach holds the history, so it can say "this is the third time you forced a bored
   entry," connect patterns across days, and stop re-teaching what is already mastered.
6. **Repeat** at higher fidelity, advancing the curriculum and tightening the execution.

The coach is the always-on tutor through every turn of this loop. **The loop is the product.** Features
exist to power it: the curriculum powers Learn; quizzes and drills power Apply; the trade debrief powers
Do and Rectify; the memory powers Remember; the daily map is the shared ground truth the whole loop runs
against.

## 8. The AI coach - the digital Anne-Marie

The coach is an AI trained on her method and trading psychology, speaking in her voice, available every
hour, infinitely patient, that **knows the individual subscriber**. Its mandate is **simplification**:
make her complex-but-proven method feel simple and learnable for the trader in front of it, without
ever distorting it. It teaches *how she thinks* and helps the trader build *their own* process; it never
makes the decision for them. The supporting agents and features (curriculum, quizzes, debrief, daily
map, Discord bot) are extensions of this one coaching relationship, not separate products. Its hard
limits are in §12.

## 9. History and memory - the "implement and rectify" engine

You cannot rectify what you do not remember. A chatbot answers a question and forgets you; a **coach**
remembers your last trade, your recurring mistake, the lesson you struggled with, and where your head
was last week - and uses all of it to move you forward. Memory is therefore not a retention nicety; it
is the mechanism that makes "implement and rectify their strategy" possible. The coach must capture and
compound each subscriber's history - what they have learned, what they keep getting wrong, their trades
and their grades, their psychology - so its coaching gets more specific and more useful the longer they
stay, and so it can show them, with receipts, that they are getting better. This is the single biggest
thing separating this product from a generic trading chatbot.

## 10. The Anne-Marie loop - human in the loop

The real Anne-Marie keeps the digital one authoritative and improving:

- She **monitors** and occasionally **joins the Discord**, where members can reach her directly (her
  drop-ins are surprise-and-delight, never a promised schedule).
- When the coach **cannot clearly answer** a question, she is **notified**, answers it once, and her
  answer becomes part of the knowledge base - so the coach gets smarter for every member, and the one
  trader who asked gets told when she has answered.
- Her **best-efforts daily insights, session reviews, and weekly teaching** feed fresh ground truth in.

Over time the coach converges toward - and, per §3, in *teaching* exceeds - her ability to bring a
trader up the ladder, because it accumulates her answers and never loses the beginner's-eye view.

## 11. How we measure success (the model)

Mastery is measured across the natural ladder of learning a skill - understand it, apply it, do it,
feel it - plus a synthesizing layer that rolls it up. Every signal stays **money-blind** (process, never
dollars), so measurement never crosses the guardrails or risks her name.

| Level | Signal | What it tells us | Status |
|---|---|---|---|
| **Comprehension** | Quizzes (hers) + the coach's in-chat micro-checks | Did they actually *learn* it. Also reaches the light engagers who never log a trade. | Core - elevate |
| **Application** | Scenario drills ("where would you enter on today's map and why?") | Can they apply the read in a safe setting, before real money. | Future add |
| **Performance** | Real/sim trades, graded against that day's map | What they actually *did* - the behavioral ground truth of execution. **The spine.** | Built (manual); completed by the indicator auto-feed |
| **Sentiment** | Passive read of the conversation | How they feel - confidence vs spiral. The continuous early-warning + psychology layer (leading indicator, not the metric itself). | Continuous |
| **Self-report** | Periodic light survey | Perceived progress, what is still confusing, would-recommend. Calibration + curriculum feedback. | Periodic |
| **Synthesis** | The coach's holistic per-trader assessment ("the gradebook") | Where are they on the mastery curve, what is their persistent leak, what is next. **This is what success rolls up to.** | Core - build toward |

Two principles tie the model together: (1) **the trades are the primary, objective signal of mastery**;
sentiment and survey measure feelings *about* progress, the trades measure the progress - and the
indicator auto-feed is what eventually makes the trade signal complete rather than a self-selected
sample. (2) **The gradebook's power is reconciliation** - surfacing where a trader's *feeling* and their
*behavior* diverge (feels great but chasing entries; feels discouraged but actually improving), which is
exactly the highest-value move a great human mentor makes.

## 12. Hard guardrails (unchanged, non-negotiable - they bound everything above)

- **Educational only.** Never an individualized buy/sell call; never a live entry/stop/target for a
  trade they should take; never a position size, contract count, or income/return number for a member;
  never a prediction stated as the market's certain move.
- **Always disclosed as AI.** The coach is always presented as an AI trained on Anne-Marie, never as
  her, and never messages anyone pretending to be her.
- **Her words are the ground truth, and protected.** Her recorded teaching is pre-approved; AI or team
  drafts wait for approval; nothing ships in her name without her tap.
- **Members are anonymous to her**, and the system stores no positions, balances, or dollar amounts
  about any member. All measurement is money-blind.
- **Her clean reputation outranks growth.** In any conflict between a growth lever and her name, her
  name wins. The restraint is the brand.

These are why §11 measures process not profit, and why the coach teaches decisions instead of making
them. A futures attorney blesses the structure before launch.

## 13. The decision rule

For any proposed work, ask: **does it make a subscriber more masterful at executing Anne-Marie's
strategy - measured by the model in §11 - without crossing a guardrail in §12, in service of the
~2026-06-24 launch?** If yes, it is the project. If it only adds features, polish, or engagement that
does not move a subscriber up the mastery ladder, it waits. Build order favors the teaching engine
(§7): the things that help a trader Learn -> Do -> Rectify -> Remember, and the things that make the
coach a better teacher (simplification, memory) and a truer one (the Anne-Marie loop).

## 14. What this sharpening changes (vs the earlier framing)

The center of gravity moves from *"make the member feel attended to, so they stay"* to *"make the member
master her strategy, taught better than she teaches it - retention is the byproduct of delivered
mastery."* Concretely:

- The **trade debrief + the history/rectify loop + quizzes + the coach's gradebook + curriculum
  simplification** move from "retention features / fast-follows" to **the core mechanism** (§7).
- The **bar on the curriculum and the coach rises** from "do not leave them lost" to "make her hard
  thing feel easy" (§3) - simplification becomes a first-class design mandate, not a tone.
- **Measurement becomes a built system** (§11), not an afterthought - quizzes and the gradebook are
  promoted because they measure mastery and reach the people the trades signal misses.
- The **indicator auto-feed** rises in strategic importance, because it is what makes the primary
  success signal (trades) complete and objective.
- **Retention, churn, and "feeling attended to"** remain real and valuable, but as *consequences* of
  delivering mastery, not as the goal itself.

## 15. How the work to date maps to this (status 2026-06-16)

Two build rounds plus two 12-persona adversarial simulations have happened. The catastrophic pre-fix
failure (the holiday "airplane") is closed and verified against live code; a second simulation then
found that several round-1 fixes were partly illusory and the regression tests had masked the gaps -
those were fixed in round 2 and the guard was extended so the blind spots cannot recur.

- **Built and verified (regression-guarded):** the holiday/early-close/Friday session clock as one
  source of truth (§ guardrails / never-lost), the Foundations floor + tier-aware path incl. the
  bare-years tier fix and the round-robin assignment that never drops the account-critical lesson (§6),
  engagement-proof seeded memory + session-day lapse greeting (§9), the chat-first trade debrief with a
  calibrated grader (tight at-level tolerance, gate-authoritative direction, MES/MNQ alias) (§7 step 4),
  the deferral close-the-loop without the masking bug (§10), the daily never-blank next-step, and
  "your month" progress that counts study days so a learner never reads zero (toward §11). Suites green:
  34/34 UX guard, 35/35 coach evals, 49/49 admin e2e.
- **Launch-readiness:** the deterministic safety floor clears the bar - no persona churns to a clock
  bug, a cold greeting, or a dangerous answer. Ship on that floor; the items below are the gap between
  "no one is lost to a bug" and "the paying core gets the mastery they pay for".
- **Built and verified 2026-06-16 (the simplification pass, §3):** every Stage 1-5 lesson now has an
  "in plain English" beginner layer (AI-authored, each adversarially verified against her original for
  faithfulness/simplicity/voice/compliance; 33 of 40 first drafts were caught drifting and corrected
  before load). Beginners/developing readers see it first with her full version one click away;
  everyone else gets an "explain like I'm brand new" toggle. Her content is untouched (source of truth);
  the layer is reproduced in the canonical seed. NOTE: it is AI-authored and should get a review pass
  from Anne-Marie (low risk - clearly labeled, never shown as her words, her original always one click
  away), and an admin review surface for it is a small follow-on.
- **Founding-window remainder (each traceable to a section; these are the real next efforts, ordered):**
  (1) **quizzes** as the comprehension +
  measurement instrument that also reaches non-loggers (§11); (3) the coach's holistic
  **gradebook/assessment** layer (§11 synthesis); (4) a **skill test-out** + posture promotion on
  demonstrated progress so a fast learner / mis-tiered expert self-corrects (§6); (5) **sim/paper trade
  grading** so a beginner practicing safely still gets a graded debrief (§7 step 2-3); (6) the
  **indicator auto-feed** to make the trade signal complete (§11); (7) reconcile **verdict vs gate** in
  the levels engine so they never contradict at the source; (8) the missing proactive senders
  (milestone/renewal, morning brief) and re-engagement personalization + closed-day timing (§10); (9)
  an in-app **"your questions to Anne-Marie"** panel + open-question awareness in the coach (§10);
  (10) scenario **drills** for the Apply rung (§7 step 2).

Each is justified by, and traceable to, a section above - which is the point of having the foundation.
