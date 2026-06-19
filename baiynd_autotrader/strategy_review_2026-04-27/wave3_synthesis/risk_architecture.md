# Risk Architecture — AMTradeCockpit V2_4
## Afshin's Path: Sim → Live Micros → Scale

**Author:** Risk Architecture Designer (Wave 3, Agent 7 of 22)
**Date:** 2026-04-27
**Status:** Draft for team review

---

## Executive Summary

This document designs the complete risk envelope for Afshin's trading system, layered from the tightest ring (per-trade) outward to the system-level circuit breakers, and ending with the concrete numerical gates required to unlock each promotion step. Every number is grounded in the source audits; divergences between V2_4 defaults and AM's stated rules are called out explicitly and resolved in favor of AM.

Three overriding realities shaped every decision here:

1. Afshin is a beginner. Capital preservation is the primary objective. Profitability is the secondary objective. "Don't blow up" outranks "maximize return" at every decision point.
2. The only audit-verified indicator performance over the 6-week Mar-Apr 2026 window is 41.7% win rate and profit factor 0.94 on MES — a small net loss, without the ML tier-filter applied. Until ML filtering is validated live, all risk parameters must be sized for this baseline, not for the Python backtest's theoretical Sharpe 10.
3. The sim-to-live transition is a one-way ratchet. Each promotion step requires passing concrete numerical gates. There is no shortcut through the checklist.

---

## Layer 1 — Per-Trade Risk

### 1.1 Stop Sizing Rule

**AM's stated rule (AM_rules_v2_spec.md §5, apr-16, apr-24):** stop distance equals the width of the entry-trigger candle's body+wick range. If the entry candle is contained within the prior 3:30 institutional candle or the prior 9:30 candle, use the bigger enclosing candle's width. On sideways days, allow 2× candle width.

**V2_4 current behavior:** the indicator always uses `europe_4AM.High - europe_4AM.Low` clipped to `[0.30, 0.80] × ADR20`. This produces a single fixed stop distance that applies to every signal on a given day regardless of which candle triggered the entry. The anchor argument in `V2ComputeStopDistance()` exists in the function signature but is never passed by any of the three call sites (lines 1954, 2113, 3330 of the indicator file). The per-trigger stop rule is entirely unimplemented; the bigger-candle exception is dead code.

**Cost of the divergence (quantified):**
- The 6-week backtest showed avg loss of 14.58 MES points. At $5/point for MES, that is $72.90 per losing trade.
- ADR20 over the Mar-Apr period was approximately 100-110 ES points. The ADR clip produces stops in the range 30 to 88 MES points (0.30×100 to 0.80×110).
- AM's per-candle rule on a typical 9:30 bar of 15-25 MES points would produce stops of 15-25 MES points — roughly half the current ADR-clipped value on wide-ADR days and broadly comparable on tight days.
- On days where the 4AM Europe candle is unusually narrow (say 8-10 points), the ADR-clip floor at 30 points forces a stop wider than AM's rule; on days where the Europe candle is wide (say 50 points), the ADR-cap at 88 points is approximately right.
- The primary distortion is the single-per-day fixed stop rather than per-trigger sizing. On trend days where three signals fire, all three get the same stop even if the triggering candles are very different sizes.

**Recommendation:** Implement the per-trigger stop rule as designed in the `V2ComputeStopDistance()` signature. Until the code is patched, document that the current stop is systematically wider than AM's rule on tight-candle days (over-risking) and tighter than AM's rule on wide-candle days (under-protecting). For the sim phase, accept the current behavior and track it; do not trade live until the stop rule matches AM.

**Practical formula for Afshin's manual use in sim:**
- Measure the entry bar's high-to-low range in MES points.
- If that bar is contained by the prior 3:30 candle, use the prior 3:30 candle's range instead.
- On sideways days (FADE mode), double the above.
- This is your stop distance. Compare it to what the indicator shows; if they differ by more than 20%, journal it.

### 1.2 Position Sizing Decision Tree

The sizing decision is driven by three inputs: (a) the day-type / candle stack classification, (b) the MOC validation state, and (c) the per-trade dollar risk relative to the account-size-specific cap.

The tree, for Afshin's specific stages:

**Stage A — Sim (no real money, no constraints except habit-forming):**
Follow the indicator's cardSizeBucket output exactly. Do not override it. The goal is to build the habit of reading the traffic-light and sizing to it.

**Stage B — Live micros, $10,000 account (or $50K combine):**

| Day-type | MOC State | Sizing | Instrument | Max contracts |
|---|---|---|---|---|
| LONG_TREND or SHORT_TREND (4-body clean stack) | GREEN (ratio > 1.20) | Full | 2 MES | 2 |
| LONG_TREND or SHORT_TREND | ORANGE (1.00-1.20) | Reduced | 1 MES | 1 |
| LONG_TREND or SHORT_TREND | GRAY (< 1.00) | Reduced | 1 MES | 1 |
| SIDEWAYS (any overlap) | GREEN | Reduced | 1 MES | 1 |
| SIDEWAYS | ORANGE or GRAY | No trade | — | 0 |
| Large wick on any candle | Any | Reduce one step | — | — |

For the indicator's current `MaxOpeningRange` gate: if the opening range exceeds 10 ES points AND you are in full-size territory, the indicator forces "1 MES ONLY." Accept this. A wide opening range means higher intraday volatility; 1 contract is correct.

**Stage C — Live micros, scaling to 2 MES or 1 MNQ:**
Same decision tree, but 2 MES becomes the full-size default once the promotion checklist in Section 5 is passed.

**Stage D — Mini contracts (1 ES or 1 NQ):**
Only after Stage C gates are passed. Do not attempt mini contracts until at minimum 100 live-micro trades are logged with acceptable performance metrics.

**Per-trade dollar risk cap (the Gray-bucket rule, validated):**
The indicator currently blocks staging when `cardDollarsRisk > $100` regardless of day-type (lines 2118-2134 of the indicator). This is the correct rule for a beginner on MES. At MES $5/point: a $100 cap allows up to 20-point stops at 1 contract. AM's typical stops on a 9:30 candle are 15-25 points MES. The $100 cap fits AM's rule at 1 MES. Validated.

For 2 MES: the effective per-trade risk cap is $200. For the sim and early live phases, $200 is the hard per-trade limit. Once the account reaches $20,000+, revisit.

### 1.3 Add-to-Winner Rules (AM apr-24: 50% midpoint stop-tighten)

AM's rule verbatim (apr-24): "any bounces up we can add to that position and we could make our stop the 50% line to tighten up on the risk."

**V2_4 status:** Not implemented. V2_4 is single-entry, single-trail, no pyramid.

**For the sim phase, Afshin should practice this manually:**
1. When a TREND trade is running and pulls back to the 50% midpoint of the entry candle, that is the add trigger.
2. Add the same quantity as the original entry.
3. Move the hard stop for the combined position to the 50% line (the midpoint of the entry candle).
4. Net effect: total position risk is now approximately the same dollar amount as the original single-contract risk because the stop is tighter.

Until V2_4 implements this, it cannot be tracked via the indicator. Journal it manually. This is a Tier 3 feature for V2_4 — defer automation.

### 1.4 Cancel-Others on First Fill — Robustness Check

V2_4 fires a single signal at the best retrace-side level per bar. When a fill occurs, `firewallActive` is set and the staging card transitions. This is a logging-only indicator; actual order placement is manual via ChartTrader. The "cancel others" alert (A5 in the code) fires to prompt the trader to cancel any other pending limits.

**Edge case — multiple working orders from prior chart loads:**
If the chart is reloaded mid-session and the indicator is reset, previously placed limit orders in the broker's book are NOT cancelled by the indicator (it has no broker connectivity). The trader must manually verify there are no orphaned limit orders in the NT8 order book before each session start. This is a manual pre-session checklist item until live order submission is implemented.

**Robustness assessment:** in the current manual-execution architecture, this is acceptable. When `AllowLiveOrderSubmit=true` is eventually wired, the Order Manager component must include a session-start reconciliation step that cancels all open limit orders from prior sessions.

---

## Layer 2 — Daily Risk

### 2.1 Max Daily Loss — Dollar and Percent of Account

**V2_4 default:** $150.
**Backtest evidence:** the Mar-Apr capture showed a lockout at $1,813 against a $150 limit on Mar 25, meaning the $150 limit is absurdly tight — the lockout fired after the first losing trade on a bad day.

**The $150 default is wrong for any practical use.** At MES $5/point with a 14.58-point average loss (per the backtest), a single losing trade on 2 MES costs $145.80. The $150 limit locks out after exactly one standard loss.

**Recommended settings by account size:**

| Account / Stage | MaxDailyLossDollars | Approx % of Account | Rationale |
|---|---|---|---|
| Sim (any size) | $500 | N/A | Habit formation; matches a 3-loss day at 2 MES avg loss |
| Live $5,000 account | $100 | 2.0% | Conservative; protects small account |
| Live $10,000 account | $200 | 2.0% | 2 standard losses at 1 MES |
| Live $25,000 account | $400 | 1.6% | 2 standard losses at 2 MES |
| $50K TopStep combine | $500 | 1.0% | Well inside TopStep's daily loss limit; leaves buffer |
| Live $50,000 account | $750 | 1.5% | 3 standard losses at 2 MES |

The percent-of-account rule: cap daily loss at 1.5-2.0% of account equity. This scales mechanically as the account grows without requiring a parameter update, but V2_4 only supports a dollar-amount parameter today. When account growth warrants it, manually recalculate and update `MaxDailyLossDollars`.

AM's implicit daily profit soft-cap of "$300/day, done" (apr-10 verbatim: "$300 a day, $1,500 a week, $12,000 bucks a month") should be noted as a mirror rule. V2_4 has no profit-lockout, but Afshin should implement it as a manual discipline rule in sim: when up $300 net on the day, do not take further trades unless the setup is exceptional. This is the "done for the day" criteria, positive-side.

**"Done for the day" criteria — explicit:**
1. MaxDailyLossDollars hit (hard, enforced by indicator lockout).
2. MaxDailyLosingTrades hit (hard, enforced by indicator lockout).
3. Net daily profit exceeds $300 at MES scale (soft, self-enforced discipline — not in code).
4. Two consecutive stops in a row (see 2.3 below) — pause even if lockout hasn't triggered.
5. Mentally compromised (distracted, anxious, news-shocked) — flat and done.

### 2.2 Max Daily Losing Trades Count

**V2_4 default:** 2 losing trades.
**AM's stated rule (AM_rules_v2_spec §8):** "Everything is process based. I trade if the setup is there." No explicit cap stated — but AM consistently describes a self-imposed 2-3 loss ceiling as a practical discipline limit.

**Recommended setting:** 2 for sim and early live. This is appropriate. After 2 losses, the market is not cooperating with your thesis. Stopping at 2 prevents the revenge-trade spiral that destroys beginner accounts.

If 2 feels too tight on days with clean setups after the losses, consider: were the 2 losses legitimate stop-outs on valid setups, or were they execution errors / questionable setups? If legitimate, the market is not in your favor today — stop. If execution errors, fix the error but don't raise the cap as a workaround.

### 2.3 Max Consecutive Stops Before Pause

V2_4 does not have an explicit consecutive-stops counter. The `MaxDailyLosingTrades` counter covers total losing trades but not the consecutive dimension.

**Recommended rule (not currently in code):** after 2 consecutive stops, apply a mandatory 60-minute pause regardless of whether the daily lockout has triggered. If you are at 1 loss and 1 win and 1 loss, that is not 2 consecutive losses — the count resets on a win. Two consecutive stops means the market is actively rejecting your setups at these levels; re-evaluate the day-type and level context before re-engaging.

This rule should be manually enforced in sim until it can be added to the indicator.

### 2.4 Cooldown After Stop

**V2_4 default:** 30 minutes (CooldownMinutes).
**AM's behavior (apr-10 "second prettiest girl" session):** AM describes getting back in "fast on convergence" — when the VWAP, 50, and 200 SMA converge on the 1-min chart after a stop, that convergence is itself the entry trigger. There is no explicit wait time in AM's method; re-entry is permitted as soon as the next valid setup appears. The 30-minute default in V2_4 appears to be a V2_4 engineering guardrail, not an AM rule.

**Assessment:** The 30-minute cooldown is over-conservative relative to AM's practice. However, it is appropriate for Afshin as a beginner for the following reasons:
- After a stop, the trader's emotional state is often degraded. A mandatory pause prevents revenge trading.
- The 30-minute window also corresponds to one full 30-minute bar, which is the indicator's decision cycle. Waiting one bar cycle before re-entry is structurally sound.

**Recommended setting for Afshin's phases:**

| Phase | CooldownMinutes | Rationale |
|---|---|---|
| Sim (first 50 trades) | 30 | Learning discipline; prevent revenge trades |
| Sim (50+ trades, proven) | 15 | Tighten as discipline improves |
| Live micros, first 30 sessions | 30 | Maintain conservative guardrail |
| Live micros, established | 15 | Loosen once emotional control is demonstrated |

Do not set to 0. Even AM's fast re-entries involve reading the convergence signal, which takes time. A zero cooldown removes the structural pause that prevents the single most common beginner failure mode (revenge trading after a stop).

### 2.5 Trade Count Cap

**V2_4 default:** 3 (MaxSignalsPerDay).
**AM's stated rule (apr-10 verbatim, 20:00 timestamp):** "usually my max max is five" — specifically in range-bound chop. AM also has zero-trade days.

**Reconciliation:** 3 is inside AM's range. For a beginner in sim, 3 is the correct default because:
- It forces selectivity. With only 3 slots, each setup must be evaluated carefully.
- In FADE/sideways mode, V2_4 caps at `min(2, MaxSignalsPerDay)` = 2. This is correct — sideways days are noisier.
- AM's 5-trade maximum applies in well-defined range conditions where she is actively managing level-to-level rotations. V2_4 doesn't have the structural context to know when the 5-trade case applies.

**Recommended defaults:**
- TREND mode: MaxSignalsPerDay = 3 (keep default).
- FADE mode: effectively 2 (already enforced by code).
- Do NOT raise to 5 until Afshin has demonstrated profitable sim performance at 3. The higher cap is AM's ceiling for experienced discretionary trading; it is not a beginner setting.

**The cancelled-pending counting issue:** V2_4 explicitly counts cancelled pending signals against the daily budget. A pending that fires, then is cancelled at the 14:30 cutoff, consumes one slot. This is documented as intentional ("a decision-budget guardrail against over-engagement"). For Afshin, this behavior is correct: a cancelled pending represents a decision made, even if unfilled. It counts.

However, there is a subtle case: if a pending is cancelled because the indicator replaces it with a newer signal on the same bar (the "best level wins" logic), that replacement should NOT consume two slots. Review the code carefully — if a same-bar replacement is double-counting, that is a bug worth fixing.

---

## Layer 3 — Multi-Day / Weekly / Account-Level

### 3.1 Max Consecutive Losing Days Before System Pause

**Recommended:** 3 consecutive losing days → mandatory system review before resuming.

"Losing day" is defined as: net realized PnL for the session is negative, OR the daily loss limit was hit, OR a lockout was triggered.

Three consecutive losing days is a signal that either (a) market conditions have shifted out of the system's optimal regime, (b) there is a parameter or implementation bug, or (c) execution quality has degraded. In all three cases, trading more is not the solution.

During a system pause: review the JSONL logs, identify which setups fired and why they lost, check if the day-type classification was correct, compare to AM's stated rules. Only resume after identifying the root cause or confirming it was randomness.

### 3.2 Weekly Drawdown Limit

**Recommended:** maximum weekly drawdown of 5% of account equity.

If the account starts the week at $10,000 and hits $9,500 at any point during the week, stop trading for the remainder of that week. Review. Resume Monday.

For the $50K TopStep combine: TopStep's own trailing drawdown rules already enforce a hard floor. Afshin's soft weekly-DD rule should be tighter than TopStep's hard floor to ensure the combine is never in danger.

### 3.3 Account-Level Drawdown Circuit Breaker

**Recommended:** if account equity drops 5% from its most recent peak at any time, pause all trading and require a manual review before resuming.

Example: account peaks at $11,500. If it drops to $10,925 (5% from peak), trading stops until the review is completed. This is not the same as the daily loss limit; it is a cumulative drawdown gate that prevents a slow bleed-out over multiple mediocre days.

This should be tracked manually until an automated account monitor is built.

### 3.4 Performance Review Cadence

**Weekly:** review the prior week's trades. For each trade, answer: (a) was the day-type classification correct? (b) was the entry level valid per AM's rules? (c) did the stop sizing match AM's rule (vs. what the indicator used)? (d) was the exit taken correctly?

**Monthly (after 20+ trades):** run the numbers. Win rate, profit factor, average win, average loss, max drawdown. Compare against the sim-to-live gates in Section 5. Are the metrics trending toward the promotion thresholds or away from them?

**When to re-tune:**
- After 30+ trades where win rate is below 40% consistently: something is wrong. Re-examine day-type classification and entry discipline.
- After 30+ trades where profit factor is below 1.0: the exits are wrong. AM's stop or target rule is being violated. Review each trade.
- After 3+ consecutive losing weeks: pause for a full system audit, not just a quick review.

**When to consider pulling the plug on the current version:**
- 100+ sim trades with profit factor consistently below 1.2 after disciplined execution: the strategy as implemented has a negative expectancy at Afshin's execution quality. This would be the signal to escalate to AM for a fundamental rules review rather than continuing to iterate on parameters.

---

## Position-Sizing Scaling Plan: Micros to Larger

### Sim Phase (no real money)

**Duration:** minimum 30 trading sessions OR 50 completed trades, whichever comes later.

**Target metrics before graduating to live micros:**
- Win rate >= 45% (below AM's long-run but realistic for a beginner learning execution)
- Profit factor >= 1.5 (meaningfully positive expectancy)
- Average loss <= 1.3× the indicator's average stop (confirms stop discipline)
- No single losing day exceeding 2× the MaxDailyLossDollars setting (confirms day-level discipline)
- JSONL logging active and consistent (confirms infrastructure is working)

### Live Micros Phase — 1 MES, Full Sizing Permission Pending

Start here when sim gates are passed. Use `MaxDailyLossDollars = $200` for a $10K account (2%).

**Duration before scaling to 2 MES:** minimum 30 live sessions or 50 live trades, whichever comes later.

**Promotion gates to 2 MES:**
- Live win rate >= 45%
- Live profit factor >= 1.5
- Max single-session drawdown does not exceed 1.5× the configured MaxDailyLossDollars in any session
- 95th-percentile single-trade loss does not exceed MaxDailyLossDollars (i.e., no one trade is wiping out the day budget)
- Trailing account drawdown from peak < 5%

### Live Micros Phase — 2 MES

Use `MaxDailyLossDollars = $400` (2% of $20K or 1.6% of $25K).

**Same risk-percent-of-account rule applies.** The dollar number scales mechanically when the account grows.

**Duration before scaling to 1 MNQ or ES mini:** minimum 50 live sessions at 2 MES with:
- Win rate >= 48%
- Profit factor >= 1.8
- Minimum dollar profit on the period: the account has grown by at least $2,000 net since the phase started (demonstrating real edge, not just luck)
- Corrected Sharpe (zero-fill daily) >= 1.0 (approximation is acceptable manually)
- ML tier filter has been tested and validated as helping (compare tier-A-filtered trades vs. all trades)

### Mini Contracts (1 MNQ or 1 ES)

1 MNQ = $2/point (NQ) vs. 2 MES = $10/point (at $5/MES). Wait: the risk comparison depends on the stop size. For a 15-point NQ stop at 1 MNQ: $30. For a 15-point ES stop at 1 MES: $75. Mini NQ is actually LOWER risk per trade than 2 MES. 1 ES at $50/point with a 15-point stop = $750 per trade — that is significantly higher risk than 2 MES.

**Gate to 1 MNQ:** same as 2 MES graduation gates above. MNQ provides comparable but slightly lower risk than 2 MES on NQ setups.

**Gate to 1 ES:** requires a $50,000+ account and net profitable history of at least 6 months at micro/MNQ level. 1 ES with a 15-point stop is $750 at risk — 15× the MES equivalent. Do not rush this step.

**The universal sizing rule across all phases:** the dollar risk per trade (entry price minus stop price, times point value, times contracts) should never exceed 2% of account equity. This rule scales mechanically. If you are on MES and 2% of your account exceeds $200, you can size up. If you are scaling up and 2% of your account is only $150, stay at 1 MES.

---

## Enforcement Architecture — Where Each Rule Lives

### In V2_4 Indicator (in-code gating — keep here)

- `MaxDailyLossDollars` lockout (Realtime only — confirmed correct)
- `MaxDailyLosingTrades` lockout (Realtime only — confirmed correct)
- `CooldownMinutes` after stop (Realtime only — confirmed correct)
- `MaxSignalsPerDay` budget (both Historical for touch recall, Realtime for gating)
- `MaxOpeningRange` forcing 1 MES (current default 10 ES pts — keep)
- `cardSizeBucket` traffic-light Green/Orange/Gray (keep, but note: Gray = no trade in the indicator UI even though AM's rule says Gray = reduced size, not zero; this is a V2_4 stricter interpretation that is appropriate for a beginner)
- Signal cancellation at 14:30 cutoff (keep)
- Hard time-close at 15:00 ET / 14:30 CL (keep)
- RTH window gate (keep)
- Retrace-side filter (keep)
- Session-latch per level (keep)

### NT8 Strategy Host (when built — moves here eventually)

- Order state reconciliation at session start (cancel orphaned limits)
- ATM template selection driven by cardSizeBucket output
- Position size selection (1 vs. 2 MES contracts) driven by cardSizeBucket
- Cancel-others-on-fill enforcement at the order level

### NT8 Broker-Level Account Settings (enforced at broker)

- TopStep combine: daily drawdown limit enforced by TopStep's platform — this is the hard floor. Afshin's `MaxDailyLossDollars` must be set BELOW TopStep's limit, not equal to it.
- Max position size (can be set in broker account): recommend setting to 2 MES maximum until mini contract phase.
- No short-selling restriction: not applicable for futures.

### Python Pipeline / Decision Engine (enforced upstream — when wired)

- ML tier filter: only tier-A signals from `pattern_scorer_rt2_1` are eligible for execution. This is a future gate; it requires the live feature engine to be built first (currently marked KNOWN LIMITATION in DEPLOY.txt).
- Daily bias confirmation from M1 scorer: the decision_engine's `/decide` endpoint (when deployed) provides M1+M2 agreement = 2 as the highest-conviction gate.
- News blackout filter: CL EIA Wednesday 10:25-10:45 is already coded in `config.py`; FOMC/NFP/CPI are placeholders. These should be active before live trading.

---

## Edge Cases

### Lockout-Without-Signal (the 2026-04-23 Anomaly)

On 2026-04-23, the JSONL lockout event reports a $2,315 daily loss against the $150 limit, but no signal event exists for that day. The backtest infra audit confirms this anomaly and offers three explanations: manual trade entry, logging gap, or pre-loaded state.

**What the right behavior should be:**

The lockout mechanism currently gates on `realizedPnlDollarsToday`, which accumulates inside the indicator only for Realtime-mode fills. If a trade was placed manually via ChartTrader (without the indicator's staging flow), the indicator has no visibility into that trade's P&L, and `realizedPnlDollarsToday` never accumulates the loss. The lockout can only trigger from a loss it witnessed.

The $2,315 loss with no signal suggests one of: (a) a manual trade that the indicator did not log — the lockout text may be from a prior state being loaded into a new session, or (b) the signal fired but the JSONL write failed (file-lock contention is documented as a real failure mode in 6+ instances in the backtest output).

**Recommended behavior:** the indicator should NOT be the primary risk enforcement mechanism for losses it didn't generate. The broker-level daily loss limit (NT8 account settings or TopStep's enforcer) is the true backstop for manually placed trades. The indicator's `MaxDailyLossDollars` is a guardrail for trades the indicator generates. Do not assume the indicator will catch a loss from a manually placed order.

**Action items:**
- Add a JSONL event when `ResetForNewDay()` is called so the prior state is visible.
- Track any date with a lockout event but no signal event as a data quality flag in the JSONL pipeline.
- Until broker-level risk enforcement is wired, Afshin must never place a manual trade on a day where the indicator is loaded; this creates the reconciliation gap.

### Signal-Then-Cancel-Then-Retry: Slot Consumption

V2_4 explicitly documents this as intentional (line 588-590 of the indicator): "A cancelled pending still counts. Intentional: this is a decision-budget guardrail against over-engagement."

**Assessment for Afshin's specific situation:** the current behavior is correct for a beginner. Each pending signal represents a commitment of attention and decision bandwidth. Cancelling a pending because the setup didn't fill cleanly is still a use of the daily decision budget. The counter-argument is that a pending cancelled at the 14:30 cutoff (because the session is ending, not because the setup failed) should not count — but this is an edge case that affects at most 1 trade per day and the conservative counting is appropriate.

**Exception to flag:** if the same signal fires, is replaced by a better level in the same bar, and the replacement consumes two budget slots rather than one — that is a bug, not a feature. The code path needs review for within-bar level replacement to confirm only one slot is consumed.

### Sizing Bucket Gray (risk > $100) — Validation

The current code blocks staging when `cardDollarsRisk > $100`. At 1 MES ($5/pt), a stop wider than 20 points triggers Gray. At 2 MES, a stop wider than 10 points triggers Gray.

This is the right gate. AM's per-candle stop rule typically produces 12-25 point stops for ES setups. On a wide-stop day (e.g., Europe candle of 40+ points, which would produce a 40-point ADR-clipped stop at 0.40×ADR), the $100 cap correctly forces no-trade rather than risking $200+ on a single MES signal.

The Gray bucket should NOT be re-interpreted as "reduced size, take the trade anyway." AM's spec (AM_rules_v2_spec §2) says Gray = reduced size, not zero. But AM is an experienced trader with defined risk management. For Afshin in the sim and early live phases, Gray = no trade is the correct interpretation because he does not yet have the experience to judge when reduced-size Gray trades are worth taking.

Graduate to "Gray = 1 MES with tighter risk" only after demonstrating consistent profitability at Green and Orange signals over 50+ trades.

### What if NT8 Crashes Mid-Trade?

This is deferred to the NT8 Safety Reviewer (separate agent) but the risk architecture must flag it:

- If NT8 crashes while a position is open, the position remains open at the broker. It will not be flat automatically.
- The broker's own risk controls (position size limits, margin enforcement) are the only backstop.
- Afshin needs a manual emergency procedure: know how to access the broker account directly (not through NT8) to flatten any open position.
- Before any live trading, confirm the broker account has a maximum position size set and a daily loss limit set independently of NT8.
- Consider a keep-alive watchdog that sends an alert if NT8's JSONL heartbeat stops during RTH. This is a Wave 3 infrastructure item.

### Data Feed Drop Mid-Bar

If the data feed drops mid-bar, NT8 may re-process the partial bar when the feed reconnects, potentially creating a duplicate touch event. The JSONL audit confirmed a 35.6% duplicate-event rate in older sessions, partly attributable to chart reloads causing bar re-walks.

**Risk implication:** a duplicate touch can fire a second pending signal. The session-latch on first-touch-per-level prevents firing twice on the same level, but if the indicator was restarted (which clears the latch), a level previously signaled could signal again.

**Mitigation in place:** `v2TouchedThisSession` is a per-session HashSet. The per-Pr30-bar `@HHmm` stamp means a new 30-min bar produces a fresh candidate key. So static levels (PrInstH, EuropeH, etc.) are protected by the latch; dynamic Pr30 levels could theoretically re-fire after a chart reload if the new 30-min bar happens to have the same timestamp.

**Mitigation recommendation:** add a session-start indicator reload detection (check if `tradeHistory` already has trades for today when the indicator initializes) and do not reset lockout state on reload if lockout was already triggered.

### Daylight Saving Time Transitions

V2_4 relies entirely on NT8's bar timestamps, which are already DST-adjusted. The indicator performs all time comparisons against hour/minute values of those timestamps. There is no explicit DST handling in the code, and none is needed — NT8 handles it.

**Remaining gap:** the `closeHour=15, closeMinute=0` constants are set at startup and held for the session. On the day of a DST transition (second Sunday in March, first Sunday in November), the first session after the clock change may have a brief window where the close cutoff is one hour off. This affects the pending cancel cutoff (14:30) and the hard close (15:00) for the transition day only.

**Recommendation:** on DST transition dates, manually verify the indicator's displayed session close time in the "Coming Up" panel before trading. This is a once-per-year issue and a manual check is sufficient.

---

## Sim-to-Live Promotion Checklist

This is the single most important section for Afshin's near-term execution. The following gates must ALL be passed before flipping `AllowLiveOrderSubmit=true` (and even then, live order submission is not wired yet — this checklist governs when to start manually entering live orders based on indicator signals).

### Gate Set 1: Minimum Sample Size

- [ ] At least 50 completed sim trades logged in NT8 (entry + exit, not just signals)
- [ ] At least 30 distinct trading sessions covered (not 50 trades in 5 sessions)
- [ ] At least 3 sessions per day-type category (TREND, FADE/SIDEWAYS) to validate performance across regimes
- [ ] JSONL logging active and consistent for all 50+ trades (no days with missing JSONL files)

### Gate Set 2: Performance Metrics (calculated over the 50+ sim trades)

- [ ] Win rate >= 50% (conservative for a beginner — AM's long-run is higher, but sim performance may lag live due to less selectivity)
- [ ] Profit factor >= 2.0 (average win is at least 2× average loss; this is achievable if exits are disciplined)
- [ ] Maximum single-session drawdown < 1.5× configured MaxDailyLossDollars in any session
- [ ] 95th-percentile single-trade loss < MaxDailyLossDollars (the worst 5% of trades individually do not blow the day limit)
- [ ] Average trade win > average trade loss (in absolute dollar terms, not just points)
- [ ] Profit factor on FADE/SIDEWAYS trades alone >= 1.5 (FADE is harder; validate it separately)

### Gate Set 3: Discipline Metrics

- [ ] Zero instances of overriding the Gray bucket to take a trade
- [ ] Zero instances of adding position size beyond what the indicator's cardSizeBucket specified
- [ ] Zero instances of holding through the 15:00 ET hard close
- [ ] Zero instances of trading after the daily lockout triggered (no manual orders to "make it back")
- [ ] Cooldown respected: no entries within the configured CooldownMinutes after a stop
- [ ] Daily loss limit respected: on any day the lockout triggered, no further sim trades were taken

### Gate Set 4: Infrastructure Readiness

- [ ] JSONL log is complete and readable for all sessions (validate by opening at least 10 session files manually)
- [ ] The indicator's signal-to-outcome pipeline is understood: can you look at a JSONL touch event and trace why it did or did not become a signal?
- [ ] The lockout anomaly behavior is understood: you know what to do if a lockout fires but no signal is logged
- [ ] NT8 broker account settings are configured: position size max = 2 MES, daily loss limit set in the broker separately from the indicator
- [ ] Emergency flatten procedure is documented and tested: know how to close positions without NT8 if necessary

### Gate Set 5: Session-Start Checklist (must be habitual before live)

Before each session, verify:
- [ ] No orphaned limit orders in the broker book from prior sessions
- [ ] `MaxDailyLossDollars` is set correctly for current account balance (recalculate monthly)
- [ ] Indicator lockout is not carrying over from a prior session (fresh session state)
- [ ] Day-type context is read: check the candle stack, MOC state, and 200-SMA slope before RTH opens
- [ ] News calendar checked: is today an FOMC, NFP, CPI, or EIA day? If so, reduce position size or sit out

---

## Recommended Risk-Knob Defaults for V2_4

These are the concrete parameter recommendations based on the full analysis above. These replace current defaults where different.

| Parameter | Current Default | Recommended (Sim) | Recommended (Live $10K) | Recommended (Live $25K) | AM Source |
|---|---|---|---|---|---|
| MaxDailyLossDollars | $150 | $500 | $200 | $400 | Engineering; keep at 2% of account |
| MaxDailyLosingTrades | 2 | 2 | 2 | 2 | Consistent with AM's practice |
| CooldownMinutes | 30 | 30 | 30 | 15 | Conservative for beginners; V2_4 default is fine |
| MaxSignalsPerDay | 3 | 3 | 3 | 3 | AM max is 5 in chop; 3 is appropriate for beginner |
| MaxOpeningRange (force 1 MES) | 10 pts | 10 pts | 10 pts | 10 pts | Validated; appropriate |
| FADE signal cap | min(2, MaxSignalsPerDay) | 2 | 2 | 2 | Correct per V2_4 FADE mode cap |
| Gray bucket behavior | Block staging | No trade | No trade | No trade | Appropriate for beginner; stricter than AM |
| AllowLiveOrderSubmit | false | false | false (until checklist done) | true (after checklist) | Infrastructure — start false |

**Parameters that V2_4 should add but does not currently have:**

| Missing Parameter | Recommended Value | Where to enforce |
|---|---|---|
| MaxConsecutiveStops | 2 → mandatory pause | V2_4 (new) or manual |
| DailyProfitLockout | $300 (soft, manual discipline) | Manual / V2_4 future |
| WeeklyDrawdownLimit | 5% of account | Manual / Python monitor |
| AccountDrawdownFromPeak | 5% → pause | Manual / Python monitor |
| ConsecutiveLosingDays | 3 → system review | Manual |

---

## Summary

The risk architecture is designed around a single governing principle: Afshin's biggest edge right now is not losing too much. A system that avoids catastrophic losses while producing modestly positive expectancy will compound. A system that takes big swings in search of AM's theoretical win rate will blow up before the edge is proven.

The three-layer structure (per-trade, daily, multi-day) provides defense in depth. Each layer is independently sufficient to stop a bad day from becoming a bad week, and a bad week from becoming a bad account. The enforcement architecture distributes responsibility across the indicator, the broker, and the trader's own manual discipline — with redundancy, so that no single point of failure is fatal.

The most critical near-term actions, in order of priority:

1. Fix `MaxDailyLossDollars` from $150 to $500 in sim immediately. The $150 setting is locking out after one standard loss and preventing useful data collection.
2. Validate the cancelled-pending slot consumption rule is not double-counting within-bar replacements.
3. Understand and document the lockout-without-signal anomaly before any live trading.
4. Implement the per-trigger stop rule in `V2ComputeStopDistance()` — passing the anchor candle at every call site — before graduating to live trading. The current europe-4AM-fixed stop is the most significant open divergence from AM's rules.
5. Pass all five gate sets in the Sim-to-Live checklist before the first live MES trade.
