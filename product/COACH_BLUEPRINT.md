# The Coach Blueprint - the state-of-the-art AI mentor, in this context

> Written 2026-06-10 from a 6-lens research + design workflow (3 web researchers: AI
> companions/coaches, expert-in-the-loop systems, learning loops; 3 product designers:
> member arc, proactive surface, Anne-Marie's input system; ~90 graded findings).
> This is the big picture of the chatbot: history, memory, proactivity, her input loop,
> and quizzes - what to build, in what order, and what to refuse. Companion to
> `PRODUCT_BRIEF.md` and `V1_SITE_DESIGN.md`. Raw findings: the coach-blueprint workflow
> output (session artifacts).

## 0. The thesis

The coach is not a Q&A feature; it is a RELATIONSHIP with five systems around it:
memory (it knows you), proactivity (it reaches out with real value), her loop (it keeps
becoming more her), assessment (it measures and tunes the teaching), and a lifecycle
(it coaches a veteran differently than a beginner). The research consensus: products
win on ORGANIC RECALL ("last week you said...") and honest, utility-anchored outreach;
they die on creepy profiling, needy notifications, and gamification guilt. Every system
below is deterministic at its core (triggers, templates, schedulers) with the LLM doing
phrasing, never origination - that is both the compliance posture and the cost posture.

## 1. Memory and history (the "mentor who knows you" engine)

- **One continuous stream, not chat threads.** Threads signal "tool"; a single stream
  with date anchors signals relationship (the Pi lesson). Each trading day auto-rolls a
  ChatThread (`session_date`, `kind`: chat|intake|quiz|debrief, auto `title`/`summary`),
  rendered as one stream with day dividers that include the day's map verdict ("Tue Jun 9 -
  sideways day"). Check-ins write into the same stream. No "new chat" as primary affordance.
- **Structured memory notes replace the single summary blob.** `member_note` table:
  kind (pattern|commitment|progress|milestone|preference), text <=200 chars, source +
  date, status (active|resolved|archived), confirmed flag. Cap ~25 active; weekly Haiku
  consolidation merges and RESOLVES (progress arcs: "couldn't stop revenge trading" ->
  resolved, with the resolution being a coaching moment). Struggle tags decay after ~60
  days unless reconfirmed, and the reconfirmation is itself a mentor question.
- **Recall moments, rationed.** Exactly ONE recall per greeting, chosen by deterministic
  priority (open commitment due > milestone > struggle-x-today's-map match > recent
  progress), woven conversationally. At most one unprompted recall per conversation.
  Recall is always about what they SAID, never inferred P&L. This is the single
  highest-leverage retention mechanic in the research.
- **Transparency as the trust feature.** "Memory updated - tap to review" moments;
  the profile page shows facts-you-told-it separately from coaching observations, each
  with provenance and per-item delete; a "don't save this" ephemeral toggle for sensitive
  talk. Bounded memory beats total recall (the inverted-U: past a threshold, support
  flips to surveillance).
- **In-chat recall tool.** FTS index over the member's own history; a `search_our_history`
  tool the coach can call (max 2/reply), quoting with dates. Member-facing history search.
- **Lifecycle stage flips the coaching posture.** Deterministic student -> practitioner ->
  veteran thresholds (tenure + lessons + check-ins) select one of three fixed posture
  paragraphs: instruct -> Socratic debrief -> teach-back + advanced nuance. The mentoring
  itself matures; day 300 must not sound like day 1.
- **Pre-launch scale fixes (blockers):** paginate the chat render (last ~30 + lazy load),
  move summarization off the page-load path, session-aware context injection (summary +
  last 8 raw), a real chat-deletion path, and a write-time scrub masking dollar amounts
  and contract counts in check-ins/notes.

## 2. The proactive surface (it reaches out, honestly)

- **One anchor outbound: the 7:30am personal brief.** Map verdict + your focus lesson +
  your yesterday (one recall line), template-rendered from DayMap/CheckIn rows - ZERO LLM
  in the send path. This is the retention ritual.
- **One coach card slot on Today,** deterministically ranked (commitment due > quiz open >
  debrief offer > lesson nudge > milestone). Never stacked cards.
- **Honest re-engagement, the differentiated move:** after 5-7 quiet trading days, ONE
  message in her teaching voice tied to the member's recorded goal - and the red-day
  pattern named out loud ("you went quiet after a hard day; that is exactly when we
  should talk") - then an explicit "I'll stop checking in unless you want me to," honored.
  The willingness to stop is the credibility mechanic (the Duolingo self-aware stop).
- **Governance is a product feature:** a ProactivityLedger (every send: trigger, channel,
  timestamp) powering hard caps (max one coach-initiated push/day), quiet hours
  (no outbound 20:00-06:30 ET, none weekends/holidays), a real preference center with
  per-kind toggles, and a "Why did I get this?" explainer. THE WALL: the coach voice
  never sells - dunning, win-backs, upsells, cross-sells always come from the TradeWave
  sender, never the mentor persona or her name.
- **Proactive copy is linted by the eval battery:** every template rendered across the
  full matrix of map states, regex-asserted against banned constructions (imperative
  trade verbs, urgency vocabulary, em dashes) with the required impersonal-provenance
  line. Proactive messages bypass the chat guardrails, so they must be safe by
  construction.
- **Level-proximity alerts (later, opt-in):** bare data, frozen template, no verb of
  action ("ES 6502.75 - within 5 points of the Europe low, untouched"). The teaching
  happens only after the member taps in. Trade-debrief prompts fire after-close only.

## 3. Anne-Marie's input system (the loop that keeps it her)

- **FOUNDATION, pre-launch (half a day):** `status` (draft|approved|retired) and
  `provenance` (her_words|her_approved|team_inference) + `source_quote` columns on
  KnowledgeEntry, with `method_corpus()` filtering to approved only. NOTHING AI-drafted
  ever speaks in her name without her tap; provenance is also what makes the contractual
  wind-down auditable and powers member-facing trust ("Reviewed by Anne-Marie - May 2026").
- **The gap agenda (the connective tissue):** a weekly Haiku job mines thumbs-downs,
  hedged/weak coach answers, quiz aggregate misses, and staged method tensions into a
  ranked list of AT MOST 5 topics with sanitized evidence ("3 members asked..."). Items
  she skips for 4 weeks expire silently - the queue never guilt-piles. This list IS her
  weekly ritual, her SMS nudge body, and the quiz-topic proposer.
- **The 15-minute voice-first Coach Trainer:** Saturday SMS with a magic link (no login),
  mobile single-column, the trainer asks one gap at a time with the member evidence, she
  TALKS (browser speech-to-text v1, pluggable transcriber later), one follow-up question
  max per item, Haiku drafts lessons preserving her verbatim phrasing, batched one-tap
  approval (Approve / Tweak / Skip) with her quote shown above each draft. Approval flips
  the linked gap to answered and goes live to every member within the minute - and the
  flash says so ("Live. Every member's coach knows this now.").
- **Escalate-to-expert with member follow-up (the loop made visible):** when asked beyond
  the corpus, the coach defers honestly ("I've flagged that for Anne-Marie"), files the
  gap, and after she answers, MESSAGES THE ASKING MEMBER with her answer. Members see
  their questions literally reach her.
- **Zero-effort harvest in parallel:** weekly yt-dlp pull of her new briefings, Haiku
  diffs against the corpus, only net-new candidates enter her digest (most weeks zero);
  quarterly 30-40 video voice refresh per the saturation finding.
- **One-tap corrections from the review queue:** on any flagged answer she records a
  20-second voice note; it becomes a high-priority override entry, provenance her_words.
- **Impact, never chores:** her dashboard reframed as reach and legacy - members coached,
  questions answered in her voice, gaps closed ("since you taught the overlap read, 41
  members asked; none flagged it"), quiz heatmap. No revenue on this screen (the monthly
  statement is its own surface). Every nudge opens with the impact recap - the research
  says visible impact is THE thing that keeps experts in these loops.
- **Sanitization layer (must):** Haiku scrub of names, dollar amounts, account/prop
  details from ANY member text she sees (agenda evidence AND the existing review queue).
- **Sequencing (the prior architecture's hard rule, kept):** run the first month
  MANUALLY - ship provenance + agenda + approvals first; Afshin pulls the agenda, she
  answers however she likes, he drafts, she one-tap approves. Ask her modality preference
  at the meeting. Productize the voice trainer only after the manual month proves the
  channel.

## 4. Quizzes and mastery (the measurement spine)

- **Retrieval practice, not gatekeeping:** 3-5 questions, 2 minutes, conversational
  (one question per turn), no pass/fail stakes; each miss gets ONE Socratic walk-back
  question, then her approved rationale verbatim - the rationale she writes/approves IS
  the canonical miss-teaching.
- **Two lanes:** (A) HER assigned pulse quizzes ("Anne-Marie asked me to check how you're
  reading day types") to all/stage/struggle cohorts with a window; (B) the coach's quiet
  spaced resurfacing of each member's shaky concepts - only inside conversations the
  member already started, max one per session, backs off on decline.
- **The unfair advantage: scenario questions from the REAL resolved map.** "Yesterday's
  ES master candles stacked like this - stair-step, containment, or mixed?" auto-graded
  against the engine's own stored read. And the **Morning Read drill**: the member
  commits their day-type read before the badge unblurs, graded against the deterministic
  answer. Predicting the ENGINE's read of completed candles, never the market - compliance
  clean, and no competitor can replicate it without the levels engine.
- **Concept mastery, not XP:** a fixed concept taxonomy mirroring the 5 stages; per-member
  per-concept new/shaky/solid (simple spaced scheduler); a "Method fluency" panel on the
  profile the coach also speaks to ("day types are solid now; sizing is still shaky").
  Optional one-tap confidence capture - confident-AND-wrong is the highest-value signal
  for both the member's coaching and her heatmap.
- **Results tune the mentoring through existing rails:** misses map to struggle keys ->
  resolve_assignment re-assigns lessons with a stated why; misses write member_notes;
  her aggregate heatmap (takers, miss %, most-chosen wrong answer, confident-wrong %)
  has one-tap "draft a follow-up quiz" and "add to my teaching agenda."
- **Honesty rules:** "method fluency," never "trading skill"; no leagues, leaderboards,
  XP, badges-as-competence, quiz-gated content, or assignment push-pressure.

## 5. The lifecycle arc (day 1 to month 12)

Week 1 is a designed sequence (intake -> guided first map walk -> first lesson -> day-7
baseline quiz), one clear next action per day through the greeting + one rail card.
Month 2+ centers on generation-then-correction: the trade DEBRIEF as a first-class
session kind, graded deterministically against that day's map (at a level? day-type
aligned? edge vs middle? flat by 3?). Month 6+ is teach-back ("explain the in-charge
candle like I'm new" - graded against the lesson), advanced nuance, and VISIBLE coach
growth ("what Anne-Marie taught me this week" - the approved-entries diff, which is also
public proof the subscription buys a coach becoming more her). Quarterly: a "your
trading review" assembled only from real longitudinal data, written as a letter from
the coach in her voice. Day-30: a reflected-back month in the member's own words
(the Wrapped pattern - honest by construction). No daily streaks anywhere; the only
counted thing is process discipline, in her language ("a disciplined zero-trade day
counts").

## 5b. Trader levels - the "belts" decision (Afshin's idea, refined 2026-06-10)

Afshin's instinct: ~5 trader levels like karate belts - assess on entry, interact by
level, advance by test, remind of prior levels. DECISION: the need is right and the
system already exists - **the 5 Method stages ARE the belts**; do NOT build a separate
global "trader level." Specifics:
- **Placement** = intake + the day-7 baseline quiz (starting stage + shaky concepts),
  never a public rank.
- **The belt test** = the stage checkpoint quiz, conversational, graded against her
  approved answers. Passing is a named moment in the coach's voice ("Stage 2 is yours -
  you read the map like she does now") and a milestone memory note.
- **Two axes, not one number:** Method STAGE controls WHAT is taught (content,
  vocabulary assumed); lifecycle POSTURE (student/practitioner/veteran) controls HOW it
  talks. A 20-year trader new to her method = Stage 1 content, peer tone. A true
  beginner = Stage 1 content, hand-holding. One global level gets one of these wrong
  for half the members.
- **Prior-level reminders** = the spaced resurfacing lane (re-check a shaky Stage 1
  concept inside a Stage 3 member's conversation).
- **HARD RULE:** stages certify fluency in HER METHOD, never trading skill or
  profitability. Copy never says "professional," "certified," or implies competence at
  trading. A single global "trader level" rank is a standing refusal (see §6) - it
  reads as a skill certification, insults experienced members placed low, and shames
  stuck members into churn.

## 6. Standing refusals (decisions, not preferences)

No login/loss-aversion streaks, XP, leaderboards, badges, confetti. No LLM-generated
outbound email bodies. No coach-initiated intraday teaching pushes (RTH outbound is
bare proximity data at most). No "we miss you" neediness or escalating re-engagement
(the response to silence is one honest touch, then quiet). No auto-publishing AI drafts
into the corpus (her tap is the only path to approved). No persona sliders as her
control surface (her controls are corrections, approvals, the interviewer). No revenue
on her weekly dashboard. No quiz framing as trading-skill certification. The coach
voice never sells.

## 7. Build sequence

| When | What |
|---|---|
| **Pre-launch (blockers)** | KnowledgeEntry status/provenance + corpus filter; chat pagination + async summary; chat deletion path + dollar-scrub at write time; review-queue sanitization. |
| **Launch +1-2 weeks** | Gap agenda job + /admin/agenda + her one-tap approvals (the MANUAL ritual); quiz builder + Lane A + her heatmap (contractual); notification prefs + ProactivityLedger + the 7:30am personal brief. |
| **Founding window** | member_note structured memory + recall selector + transparency moments; date-anchored sessions + pagination UX; voice-first Coach Trainer + SMS nudge (after the manual month); Morning Read drill; honest re-engagement playbook; escalate-to-expert follow-ups. |
| **V2 (the relaunch)** | Trade debrief (the flagship); lifecycle postures + teach-back; concept mastery panel + spaced Lane B; FTS recall tool; quarterly reviews; harvest automation; proximity alerts. |

The V2 relaunch headline stays: "months of memory, a coach that grows with you" - and by
then it is literally true, on these rails.
