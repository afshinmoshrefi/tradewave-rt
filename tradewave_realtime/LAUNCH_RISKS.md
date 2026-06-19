# TradeWave Realtime - Launch Readiness Punch-List

> Generated 2026-06-15 by the codebase deep-read risk critic. Worked down before the ~June 24 launch. Severity is the critic's; verify each against current code before acting (a few may already be partially addressed).

**5 high · 7 medium · 0 low · 12 drift · 12 gaps**

---
## STATUS UPDATE 2026-06-18 (HIGH-1 residual closed - trade-debrief freemium gate)

Decided with Afshin: the debrief stays a funnel (a free prospect must see it run) but on a leash.
Locked behind `verify_debrief.py` (6 checks):
- **Free tier: one debrief per rolling 7 days.** `trades.log_trade` calls `next_free_debrief()`
  (keys off `is_paid`, so dormant pre-launch); over the cap it flashes an upsell and skips the
  grade/coach hand-off instead of grading. `app/trades.py`.
- **Exact map levels are paid-only.** The deterministic grade notes (which print level prices,
  e.g. "~5120.00") now render on the trades card for paid/staff only; free users keep the
  structural summary, which carries no numbers - so the debrief can no longer leak the paid
  levels to a free account. `app/templates/app/trades.html`.
- The coach debrief path was already number-safe for free users (today_context is paid-gated;
  recent_trades_context passes only boolean tags), so no change was needed there.

Net: HIGH-1 (the freemium model) is now coherent end to end - free gets a weekly, number-scrubbed
debrief plus the day-one full map; paid gets the level numbers, unlimited debriefs, the indicator.
The scrub IS the model (no hard subscription decorator by design).
---
## STATUS UPDATE 2026-06-18 (MEDIUM-7 CLOSED - Stripe webhook hardening + past_due grace)

Fixed and locked behind `verify_billing.py` (16 checks; runs on a throwaway temp DB, fully
mocked Stripe, no network):
- **`int(rt_user_id)` guarded:** a non-numeric metadata value no longer raises -> 500 -> Stripe
  infinite-retry loop; resolution falls back to `stripe_customer_id`. `billing.py`.
- **Unresolved-but-RT subscription now screams:** an RT (paying) sub with no resolvable local
  account logs at ERROR ("MANUAL REVIEW REQUIRED", `journalctl -p err`) instead of a buried
  warning.
- **Stripe API version pinned:** `config.STRIPE_API_VERSION` defaults to `2026-05-27.dahlia`
  (matches the installed lib 15.2.0); `_stripe()` applies it so `retrieve()`/webhook payload
  shapes stay stable. `current_period_end` is read from both the item and subscription shapes.
- **`past_due` 7-day grace (decided with Afshin):** a failed renewal keeps access for a FIXED
  7-day window, not Stripe's whole ~2-3 week dunning cycle. New `Subscription.past_due_since`
  (stamped on entry to past_due, cleared on recovery) + `PAST_DUE_GRACE_DAYS=7`; `is_active`
  encodes the window and `active_subscription()` confirms it (SQL prefilter on `ACTIVE_STATUSES`
  is no longer sufficient on its own). Micro-migration adds the column on upgraded DBs (verified
  live). `models.py`, `billing.py`, `app/__init__.py`.

Residual follow-up (nice-to-have, not a blocker): a real operator email/ops-channel alert for
the unresolved-sub case (`notify.py` currently has only member-facing senders); and `admin.py`
KPI count still counts past-grace `past_due` rows as active (cosmetic dashboard stat, not a gate).
---
## STATUS UPDATE 2026-06-17 (verified against current code + adversarially checked)

Fixed and locked behind `verify_security.py` (24 checks):
- **HIGH-2 (signup self-grant role): FIXED.** Local `/signup` always creates `member`; WorkOS callback now
  requires `email_verified` before lazy-create/merge (field name confirmed against WorkOS docs). `auth.py`.
- **HIGH-3 (seed over-privilege + shared password): FIXED.** Seed roles derive from config (AM -> partner);
  the hardcoded `tradewave2026` is gone (per-account random or `SEED_PASSWORD`, shown once). Root cause also
  fixed: `secrets.env` had AM in `ADMIN_EMAILS` - corrected (backed up). `seed.py`, `secrets.env`.
- **HIGH-4 (SQLite hardening): FIXED.** WAL/busy_timeout/synchronous/foreign_keys per-connection in
  `extensions.py`; boot DDL serialized across workers with a file lock in `__init__.py`.
- **MEDIUM-4 (open redirect): FIXED.** `_safe_next` rejects `//` and `/\`. `auth.py`.
- **MEDIUM-5 (cookie/scheme hardening): FIXED.** SECURE/HTTPONLY/SAMESITE + PREFERRED_URL_SCHEME in `config.py`.
- **Gap-5 (no 500 handler): FIXED, double-fault-safe.** 500 handler rolls back + static fallback;
  `inject_globals` no longer throws if the DB is the failure. `__init__.py`, `errors/500.html`.
- **Derived from foreign_keys=ON (two pre-existing latent bugs it exposed): FIXED.** `knowledge_delete`
  now detaches `UserLesson` + `DeferredQuestion` before delete (`admin.py`); 500 page survives a DB-down.
- **HIGH-5 (no runtime compliance backstop on the live coach reply): FIXED.** Deterministic `screen_reply`/
  `enforce_compliance` in `llm.py` catches live directional calls, income projections, and specific position
  sizes and replaces them with a safe redirect (flags the message for review). Wired into the web coach
  (stream + message), Discord `answer()` (which also now gets level-typo repair it previously skipped), the
  daily check-in, and `intake_wrapup`; `maybe_update_summary` keeps the prior note rather than persist a
  tripping one. `generate_reply` stays unscreened so the eval battery still measures raw model behavior.
  Adversarially hardened (trader synonyms/slang/softeners, income recall, sizing, markdown) and locked by
  `verify_compliance.py` (71 checks). Residual: exotic output-byte evasion (unicode homoglyphs) is out of
  scope for a deterministic screen; an LLM-based screen is the future path to that.

STILL OPEN: HIGH-1 reframed (the freemium levels SCRUB matches the decided model, but the trade debrief is
not gated); the MEDIUM/drift/gap items not listed above. All five HIGH blockers + the highest-priority items
are now closed.
---

## HIGH - launch blockers

### HIGH-1. The paywall does not exist on the website. BILLING_REQUIRED is honored in exactly one place (Discord role-sync, discord_bot.py:221). Every member web route - /app (Today + the daily levels), /app/feed, /app/library (the whole Method curriculum), /app/account, and the coach (chat.py is @disclaimer_required only) - is gated by @login_required with NO subscription check. active_subscription() is referenced only for the account-page display (main.py:180), a KPI count (admin.py:113), and Discord. So flipping BILLING_REQUIRED=1 at launch will NOT require payment to consume the full product: anyone who creates a free account (and /signup is open and self-service) keeps the perishable daily-levels map, the coach, and all lessons for free. With 'no free trial' as a core pricing decision and real money flowing to Anne-Marie's 35% statement, this is the headline launch blocker - the thing being sold is not behind the gate.
- **Where:** app/main.py:24-203 (dashboard/feed/library/account, all @login_required only); app/chat.py:48,66,86,159,177 (@disclaimer_required only); BILLING_REQUIRED used only at app/discord_bot.py:221; contrast config.py:64 and billing.py:167 which both assert a web paywall that is not implemented
- **Fix:** Add a subscription gate decorator (active_subscription(user) is not None OR BILLING_REQUIRED off) and apply it to dashboard, library, library_entry, feed, and all chat coach routes. Decide the free-vs-paid surface explicitly (landing + account reachable; Today/coach/library paid). Test the BILLING_REQUIRED=1 path end to end before launch - today no automated check exercises it for the web tier.

### HIGH-2. Self-service signup is wide open and can self-grant privileged roles. POST /signup creates a full member account with no billing and no WorkOS, and role is assigned purely by whether the typed email is in ADMIN_EMAILS/PARTNER_EMAILS (auth.py:148-153). Anyone who signs up using the configured operator or partner email string (both knowable) is auto-granted admin or partner with NO verification, gaining the Operations room or Anne-Marie's workspace. The same string-membership escalation exists on the WorkOS callback (auth.py:83-85) with no email_verified check, so an unverified-email IdP response could mint a partner/operator. Live privilege-escalation / account-takeover path at launch.
- **Where:** app/auth.py:130-162 (open signup + role self-assignment), app/auth.py:70-89 (WorkOS lazy-create, no email_verified gate)
- **Fix:** Before launch: (1) disable or invite-gate the local /signup+/login forms in production and make WorkOS the only live path, OR remove ADMIN/PARTNER auto-assignment from self-service signup so privileged roles can only be granted via ops_set_role. (2) On the WorkOS callback require wo_user['email_verified'] before lazy-create and before merging an existing account by email.

### HIGH-3. Seeding over-privileges Anne-Marie to site operator. seed.py:_ensure_admin hardcodes role='admin' and run_seed seeds anne-marie@thetradingbook.com as an admin (seed.py:40,51-53), contradicting config.py (she is PARTNER, 'her workspace but not operations') and auth.py's own logic that would assign her 'partner'. If the prod DB is seeded, AM gets is_admin=True -> the Operations room: the full member directory with real emails/names, the role-assignment tool, market ops, and KPIs. That breaks the operator-vs-partner boundary, exposes member PII to the partner, and lets her change roles. Default password for both seeded accounts is the hardcoded 'tradewave2026' (seed.py:17) with accepted_ai_disclaimer pre-set - two guessable full-privilege logins if seed runs on prod and the password isn't rotated.
- **Where:** app/seed.py:17,40,51-53; contrast config.py:36-49, app/auth.py:83-85, app/security.py:58-69
- **Fix:** Make the partner seed role='partner' (only the operator is admin). Do not seed a shared static password into prod - force a reset, or create the operator out-of-band and grant AM partner via ops_set_role. Verify on the live prod DB that anne-marie@thetradingbook.com is role='partner' and no account still has the default password before launch.

### HIGH-4. SQLite has zero hardening under concurrent load. extensions.py creates db with no engine options: no busy_timeout, no journal_mode pragma, no pool config. The app runs gunicorn -w 2 --threads 8 (up to 16 concurrent writers) against one SQLite file. WAL is on only because the runtime files happen to exist (data/*.db-wal is 4MB now = real write pressure), NOT because the code sets it - not guaranteed on a fresh box or restore. With no busy_timeout, concurrent writes (chat inserts, ratings, check-ins, the levels-sync DayMap rebuild while members read, webhook upserts) will throw 'database is locked' under launch-day concurrency, and there is no 500 handler so members get a raw error page. Both gunicorn workers also run create_all()+ALTER micro-migrations concurrently at boot, which can collide on first deploy.
- **Where:** app/extensions.py:1-5 (no engine_options); deploy/units/tradewave-rt.service:11 (-w 2 --threads 8); app/__init__.py:45-90 (boot create_all+ALTER per worker)
- **Fix:** Set engine options in code so they hold on any box: journal_mode=WAL, busy_timeout ~5000ms, synchronous=NORMAL, foreign_keys=ON via SQLALCHEMY_ENGINE_OPTIONS or a connect event. Run create_all/micro-migrations once (release step or --preload) not per worker. Add a 500 handler. Load-test ~20 concurrent chat sessions before launch.

### HIGH-5. Educational-only / no-individualized-advice / no-sizing / no-income guardrails are prompt-only on the live path. The only deterministic backstops on a real reply are em-dash stripping and digit-flip level repair. There is NO runtime post-filter for buy/sell calls, position sizing, or income projections - looks_like_advice_seeking() only influences the demo/no-key fallback, never the Sonnet output. The eval battery gates this at build time but nothing blocks a non-compliant answer at request time. A prompt regression, jailbreak, or out-of-distribution question that elicits 'buy NQ here, 2 micros, stop at X' or 'you can make $5k/mo' ships straight to a paying member in Anne-Marie's coach voice - the exact CTA/NFA compliance line and reputational risk the partnership exists to avoid. Worse in Discord #ask-the-coach, where answer() bypasses even correct_level_typos and the reply is public to the whole room.
- **Where:** app/persona.py:77-105 (rules) vs no runtime enforcement in app/chat.py / app/llm.py generate_reply/stream_reply; app/discord_bot.py answer() bypasses correct_level_typos
- **Fix:** Add a deterministic post-generation screen on the live reply (and the Discord reply) for the highest-risk patterns: imperative buy/sell of a named instrument, an explicit contract/lot count tied to the member, and dollar/percent income figures presented as expectations; on a hit replace with the safe redirect. Route the Discord direct-client path through the same scrub/level-repair the web coach uses. Treat the eval battery as necessary-but-not-sufficient.

## MEDIUM

### MEDIUM-1. The morning briefing publishes an AI digest under Anne-Marie's name with no AI badge on the feed. publish_briefing sets author_id to the partner user (briefing.py:164-169) and feed.html:11 renders 'date - {author.display_name}' (Anne-Marie Baiynd) with no AI label for kind='briefing'. The only disclosure is one sentence inside the body. A member skimming the feed sees a post authored by Anne-Marie that is actually a Sonnet summary of her video. This contradicts the always-AI-never-her invariant and can embarrass her if the digest mis-summarizes or attaches a wrong number to her name.
- **Where:** app/briefing.py:164-169 (author_id=her.id); app/templates/app/feed.html:11 (byline, no AI badge for kind='briefing')
- **Fix:** Do not attribute the briefing to her as author. Set author_id=None and render a clear 'AI digest of Anne-Marie's video' byline/badge for kind='briefing' on the feed (and Today if surfaced), or add an explicit AI tag next to the author name. Keep her name only on the linked video.

### MEDIUM-2. now_context() tells the coach (and a paying member) a flatly false thing on Friday afternoon. The phase ladder marks weekend-closed when wd==4 and hm>='17:00', so Friday 16:00-17:00 falls through to the final else, which says 'Globex reopens 6:00 PM ET and starts tomorrow's map' - but tomorrow is Saturday; Globex does not reopen until Sunday. The coach repeats this verbatim. The same pattern is mirrored on the Today time_note (main.py:65-78), and is_session_day ignores market holidays entirely (marketdata.py:45), so on a weekday holiday the coach treats it as a normal session and Today shows a stale map with no 'markets closed' note. Summer 2026 is holiday-heavy right at launch.
- **Where:** app/levels.py:322,341 (Friday 16:00-17:00 -> wrong else branch); app/main.py:64-78 (mirror); app/marketdata.py:45 (no holiday calendar)
- **Fix:** Fix the Friday boundary so 16:00-17:00 and the 17:00-18:00 break produce correct copy, and make the weekend message cover Friday-after-close through Sunday 18:00. Add a market-holiday list to is_session_day (even a hardcoded 2026 set) so the coach, the briefing 'today's video' guard, the email session-day cap, and the Today note all treat holidays as closed.

### MEDIUM-3. Reconciliation drift is detected but never alerted, so a bad capture can teach a wrong level to every member all day. A capture that prints far from EODHD truth only produces logger.warning at the overnight reconcile; no admin alert, no DayMap flag, no review-queue entry. By then the wrong level has already driven the published map, the Discord morning-map post, the briefing allowed-numbers, and the coach today_context for the whole session. The ops drift table shows recon_drift>0.5 only after reconciliation and only if an operator opens the page. The pull path (fetch_keyprovider_levels) also lacks the NaN/Infinity/OHLC/session-date guards the push endpoint enforces, so the weaker write path can land a malformed-but-positive capture. A wrong daily level in front of paying traders (and posted publicly in Discord) is a direct credibility and Anne-Marie-embarrassment risk.
- **Where:** app/marketdata.py:155-161 (warning-only drift); app/marketdata.py:240-268 (pull path missing ingest.py:44-54 guards)
- **Fix:** On a capture-vs-truth drift over tolerance, raise something an operator sees (flag the DayMap, add an ops alert/notification, or block the Discord map post on suspect data). Apply the same isfinite/positive/OHLC/session-date plausibility guards from ingest.py to fetch_keyprovider_levels so both write paths are symmetric.

### MEDIUM-4. Open redirect after login via protocol-relative / backslash next. _safe_next only checks startswith('/'), and the WorkOS flow stores the same value (auth.py:123-127, used at 39/100). '//evil.com/path' and '/\evil.com' both pass and many browsers treat them as absolute, so a crafted login link bounces a just-authenticated member to an attacker site - a clean phishing primitive against a payment-handling app at launch. Verified: both variants return startswith('/')==True.
- **Where:** app/auth.py:123-127 (_safe_next), used at auth.py:39,100,151,156,185,193
- **Fix:** Reject next values starting with '//' or '/\' (ideally allow only known internal endpoints). One-line fix: require nxt.startswith('/') and not nxt.startswith('//') and not nxt.startswith('/\').

### MEDIUM-5. Session cookie is not actually marked secure/httponly/samesite, despite the code comment claiming ProxyFix makes it 'treated as secure'. No SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE is set anywhere (grep-confirmed), so Flask defaults apply (Secure=False, SameSite=None). For an authenticated, payment-handling app the session cookie lacks standard hardening; the ProxyFix comment overstates the protection. Also no SERVER_NAME/PREFERRED_URL_SCHEME is set, so the Stripe success/cancel/portal _external URLs and the WorkOS redirect_uri can be built with the wrong scheme/host behind the tunnel, sending members to a broken post-checkout page at the conversion moment.
- **Where:** app/__init__.py:14-17 (ProxyFix comment) and config.py (no cookie flags, no SERVER_NAME/PREFERRED_URL_SCHEME)
- **Fix:** Set SESSION_COOKIE_SECURE/HTTPONLY=True and SESSION_COOKIE_SAMESITE='Lax'. Set PREFERRED_URL_SCHEME='https' and pin the external host (SERVER_NAME) so url_for(_external=True) for Stripe and WorkOS always yields correct https URLs; verify the real post-checkout redirect on the deployed tunnel.

### MEDIUM-6. With ANTHROPIC_TOKEN unset, member text reaches Anne-Marie's review screen protected only by a narrow regex. sanitize_for_admin falls back to scrub_sensitive when the LLM is off, masking only $-prefixed amounts, the words dollars/bucks/grand, and 'N k' immediately before account/drawdown/profit/loss/funded, plus a short size vocabulary. Common phrasing a struggling trader types - 'blew up my 50k', 'down 4200 today', 'lost two hundred', 'my 50000 account', '3 ES', a real name, a prop-firm name - passes through to her review queue. The /welcome consent copy tells the member 'she does not read your conversations' (welcome.html:12), stronger than what the code does: thumbs-down and couldn't-answer questions ARE surfaced to her. Mismatch between the promise and the behavior, plus a real PII-leak path when the key is absent.
- **Where:** app/privacy.py:19-25,38-42 (narrow fallback regex); app/admin.py reviews/teach surfaces; app/templates/auth/welcome.html:12 (over-strong consent claim)
- **Fix:** Treat the deterministic fallback as insufficient for display: if the LLM is unavailable, redact more aggressively (mask standalone 3-6 digit numbers in money-ish contexts, or do not show the question text at all). Reconcile the welcome copy to the real flow ('we anonymize flagged messages before she reviews them').

### MEDIUM-7. Webhook user-resolution can silently drop a real paying member, and a non-numeric rt_user_id 500s the handler into a Stripe retry loop. _sync_subscription resolves by metadata.rt_user_id then stripe_customer_id; a subscription created outside the app's own checkout (Stripe dashboard, invoice, EOD->RT migration) can carry an RT price but no rt_user_id and a customer not in User.stripe_customer_id - it logs 'no local user' and drops, so a paying member gets no entitlement with only a log line. int(rt_user_id) is unguarded (billing.py:190-192): a non-numeric value raises ValueError, returns 500, and Stripe retries forever. Also past_due is in ACTIVE_STATUSES so a failed card keeps full access (levels + Discord) for the entire dunning window on a perishable daily product, and current_period_end is read via bracket-only access that may be null on newer Stripe API versions (no API version pinned), leaving the account page with no renewal date.
- **Where:** app/billing.py:189-197 (resolution + unguarded int), app/models.py:179 (past_due active), app/billing.py:212 (period_end); no Stripe API version pinned
- **Fix:** Wrap int(rt_user_id) in try/except and on any unresolved-but-RT subscription log loudly AND alert (real revenue). Pin the Stripe API version for the launch account and verify both current_period_end shapes and the _is_rt filter against a live test sub. Make the past_due grace a conscious decision (drop it or time-cap it) given the value is consumed every morning.

## Drift (code vs documented design)

1. Approval/holdback gate is unimplemented: the design rule is 'her-words pre-approved, AI/team-drafted content held as draft', but BOTH write paths force status='approved' - teach_publish hardcodes provenance='her_words'/status='approved' (admin.py:199-200) and _save_knowledge hardcodes entry.status='approved' for every entry regardless of provenance, including team_inference (admin.py:363). The model default is also status='approved'. Code comments admit the draft path is only hypothetical. Net: any team_inference content authored in the admin tool publishes live to the coach immediately; the draft-hold the brief calls for does not exist.
2. RAG index and the coach corpus disagree on the gate: rag.rebuild_index filters published=True ONLY (rag.py:113) while method_corpus filters published=True AND status='approved' (llm.py:96). A published-but-not-approved entry is kept OUT of the answer body but is STILL retrievable as a member-facing citation chip and, in demo/no-key mode, quoted verbatim in _fallback_reply. The two filters are designed inconsistently against 'only approved reaches members'. Latent today only because no draft can currently be created.
3. Briefing feed byline attributes an AI digest to Anne-Marie as author with no AI badge (briefing.py:164-169 author_id=her.id; feed.html:11 renders author.display_name), contradicting the always-AI-never-her invariant. Body text discloses it; the byline does not.
4. now_context()/Today time_note state a false 'Globex reopens tonight, tomorrow's map starts building' on Friday 16:00-17:00 because the weekend-closed condition is wd==4 and hm>='17:00', leaving the 16:00-17:00 window in the wrong else branch (levels.py:322,341; main.py:65-78). The engine elsewhere treats the session as running to 16:00, so this is internally inconsistent.
5. Seed grants Anne-Marie role='admin' (site operator), contradicting config.py's PARTNER design and auth.py's role logic. A seeded prod DB over-privileges the partner into the Operations room, the member PII directory, and role management (seed.py:40,51-53 vs config.py:36-49, security.py:58-69).
6. Deferral routing is a brittle prose substring match: rating=-2 is set iff the literal 'flagged this for Anne-Marie' appears in the reply (chat.py:132,202), keyed to the exact persona sentence. Any paraphrase, a missing hyphen ('Anne Marie'), or a reworded apology silently fails to route a genuinely-unanswerable question into her review queue, breaking the correction loop; a reply that merely quotes the phrase is mis-tagged. The signal should be structured, not prose.
7. Member thumbs-up can silently de-queue a genuinely-unanswerable question: deferral sets rating=-2 (review queue is rating<=-1, admin.py), but rate_message accepts rating in (-1,0,1) and overwrites the -2 (chat.py:159-174). A member rating that answer up removes it from her correction queue. Two distinct signals (auto -2 loop vs member -1/0/1 feedback) share one column with no separation.
8. BILLING_REQUIRED is documented as the launch flip that 'requires an active subscription on member pages' (config.py:64, billing.py:167), but it gates only Discord role-sync; the member website is not paywalled (main.py @login_required only). Code-vs-design mismatch.
9. The non-streaming /message coach endpoint never calls maybe_update_summary - only the SSE /stream path does (chat.py:150), and mentor.maybe_update_summary's docstring still claims it 'Runs on coach-page load' which is no longer true. Any client using /message leaves the rolling coaching_summary stale.
10. Stale model docstring: Post.kind is documented as 'post | insight' (models.py:113) but briefing writes kind='briefing' (briefing.py:167) and main.py only special-cases insight/post; a reader trusting the comment misses briefing posts. Column is free-text so it works, but the contract is stale.
11. The seed welcome Post is signed '- Anne-Marie' and authored as her (seed.py author_id=am_user) but is team/seed copy, not her words - the same author-attribution tension the provenance discipline is meant to prevent, applied to member-facing copy.
12. The daily insight composer (admin.py:377) and member-feed posts (_save_post) take raw free-text, store it unescaped, and render via the `md` filter (extensions registered with markdown 'extra', which passes raw HTML through) with no scrub and no review. A stray dollar amount, position, or individualized call typed by the partner goes live to every member's Today page and into the coach today_context unfiltered, unlike the briefing path which scrubs numbers; stray HTML/script in an insight would also render on every member's page.

## Open gaps (designed-but-not-built / unfinished)

1. No website subscription enforcement exists at all - the subscription gate that BILLING_REQUIRED implies for the web tier was never built (only Discord consumes it). Designed-but-not-built and the gating launch item.
2. No coach-voice email is wired. notify defines COACH_KINDS and the full session-day/quiet-hours/once-per-24h cap policy, but only send_welcome (transactional) is actually called. The morning-brief / check-in-nudge / re-engagement sends the brief describes are unimplemented, so the entire proactive-email cap logic is unexercised and unverified in production.
3. No runtime compliance backstop for individualized-advice/sizing/income on the live coach path; enforcement is the system prompt plus a build-time eval battery only. The advice-seeking detector is wired only into the demo fallback.
4. The NinjaTrader AM Map indicator integration is out-of-band: DayMap is documented as feeding 'the indicator feed' but no Flask route serves DayMap/levels to the indicator. The landing page sells the indicator + 'hands your completed trades to your coach for a debrief', but there is no trade-ingest or debrief surface in these routes - the completed-trades debrief is unbuilt. If the indicator/debrief ship slips, the landing copy is false at launch.
5. No 500 error handler (only a 404 handler is registered, __init__.py). Combined with un-hardened SQLite, a 'database is locked' or any unhandled exception renders a raw Werkzeug page to members.
6. Market-holiday handling is unbuilt: is_session_day checks Mon-Fri only with a 'holidays handled by admin override later' comment and no override mechanism exists. Affects the coach session-phase, the Today note, the briefing 'today's video' guard, and the email session-day cap.
7. Schema constraints are not guaranteed on an upgraded prod DB: no Alembic, only a hand-maintained ADD COLUMN micro-migration loop that cannot create the model's UniqueConstraints/Indexes (uq_checkin, uq_candle, uq_daymap, uq_user_lesson). On an already-seeded DB those duplicate-prevention invariants may silently not exist; any new model column added without a matching micro-migration entry exists on fresh boxes but is missing on upgraded ones.
8. No startup configuration assertion: if a box is restored from backup or install.sh runs without /etc/.../secrets.env, config silently falls back - SECRET_KEY auto-generates (invalidating all sessions), BILLING/LLM/WORKOS flip off - and the app boots in a half-configured state with no loud failure. secrets.env is an out-of-band manual prerequisite per the brief.
9. Backup safety net is thin: nightly SQLite .backup() lands on the SAME host (/home/flask/backups), with no integrity check, no off-box copy, and no OnFailure alert on the systemd unit. A silently failing backup (disk full, missing SRC) goes unnoticed - the only DB recovery path ~9 days from a paid launch.
10. Free-tier abuse controls in Discord are in-memory only: FREE_DAILY_CAP and the per-user cooldown live in process dicts that reset on every bot restart/crash, and guild-join (not the account link) is the de-facto free-access boundary since coach-preview channels are everyone-visible. A restart loop lets free users exceed the cap and burn Sonnet tokens.
11. run.py uses debug=True (Werkzeug interactive debugger = RCE if exposed). The intended prod path is gunicorn/wsgi.py, but both entrypoints build the same app and nothing prevents launching the wrong one.
12. The static ingest token has no rate limiting, nonce, or replay protection; anyone holding LEVELS_INGEST_TOKEN can overwrite any not-yet-reconciled capture for any in-range session and trigger an immediate map rebuild that propagates to Today + Discord + coach within seconds (plausibility guards bound it to plausible-but-wrong values).
