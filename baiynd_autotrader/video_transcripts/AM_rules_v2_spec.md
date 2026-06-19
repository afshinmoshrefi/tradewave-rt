# Anne-Marie's Rules — Implementation Spec (post apr-29 Q&A)

**Sources updated:** apr-24 chart Q&A, apr-27 sideways-fade live confirmation, **apr-29 Fed-day chart walk-through (live trade narration)**.

---

## CURRENT IMPLEMENTATION: V2_5 architecture (2026-04-27)

**Status:** V2_5 is the current production implementation. V2_4 is retained as legacy/fallback, untouched.

**Background.** V2_4 fired 2 signals in 6 months against 741 qualifying touches — a 0.27% conversion rate. Root cause: hard-coded gates inside the indicator were compounding silently, dropping 99.73% of candidates with no log entry. The sideways-fade rule wired on 2026-04-27 (§7) exposed this: even after adding the rule, candidates disappeared before reaching it. The architectural rethink that followed produced V2_5.

**Architecture (L1 / L2 / L3).**

- **L1 — AMTradeCockpitV2_5.cs (detection only, fail-open).** Detects every level interaction inside each bar's [low, high] window. Emits a `candidate` event for every hit. Never blocks on retrace-side, latch, scoring, or safety grounds. Pattern A and Pattern B both surface candidates without rejection. This layer knows nothing about trade decisions.

- **L2 — AMTradeStrategyV1.cs, scorer region (heuristic now, ML later).** Receives candidates from L1. Runs the heuristic scorer (rule-based V1; ML endpoint in V2). If scorer rejects, emits `abstain` with `layer="L2"`, gate name, reason, and recovery condition. Never silent.

- **L3 — AMTradeStrategyV1.cs, safety region (12 toggleable gates).** Independent of L1 and L2. Gates: RTH window, daily loss kill, cooldown, max signals, kill-switch, position-reconciliation, and six additional configurable guards. Each gate is a NinjaScriptProperty. Each block emits an explicit `abstain` with `layer="L3"`. No silent drops.

**Prime directive.** Every layer's first invariant: *a bug that lets a trade through (visible, recoverable) is infinitely preferable to a bug that blocks one (silent, invisible).* Every code path that does not produce a downstream event ends in either a `signal`, an `abstain`, or an `error`. There is no fourth option of silently returning. Any gate that blocks must log layer, gate name, reason, and recovery condition.

**AM ambiguities are features, not gates.** The three unresolved AM questions (3-node vs 4-node body stack, FADE direction, slope threshold for runner choice) previously caused V2_4 to block candidates when it couldn't resolve them. V2_5 emits both interpretations as feature fields on the candidate event and lets the scorer learn which matters. The architecture is shippable without AM clarifications.

**Realistic target.** AM's 15-year edge profile: Sharpe 2–3, profit factor 2.5–4, win rate 50–60%. V2_5 is designed to capture this faithfully by emitting everything and deciding explicitly, not by pre-filtering at the detection layer.

**Full design spec:** `C:\seasonals\baiynd_autotrader\v25_rebuild_2026-04-27\architecture_spec_v25.md`

---

This is the RULES-AS-CODE view. Most answers come from Anne-Marie's direct Q&A responses on 2026-04-24 — the implementation blockers that were open in prior versions are now resolved. Remaining discussion items are flagged at the bottom.

---

## 1. THE DAY-TYPE GATE

### The four candles (in time order)

| # | Candle | ET time | Notes |
|---|---|---|---|
| A | Prior day closing | 15:30–16:00 (yesterday) | |
| B | GlobEx | 18:00–18:30 (yesterday) | |
| C | Europe 4 AM | 04:00–04:30 (today) | |
| D | RTH open | 09:30–10:00 (today; or 10:00–10:30 for CL) | |

### Comparison rule (RESOLVED)
**Bodies stack, wicks don't count.** Two candles are "in sequence" only when their bodies do NOT overlap.
- `body_top(X) = max(X.open, X.close)`
- `body_bottom(X) = min(X.open, X.close)`
- X below Y requires `body_top(X) ≤ body_bottom(Y)`.
- Any body-overlap between any two adjacent candles → **sideways/consolidation**.

### Large-wick risk modifier (RESOLVED)
If any candle's wick (tail beyond its body) is **larger than the body itself**, treat as a risk event → reduce size even on otherwise full-trend days.

### Classification
- **LONG trend:** A < B < C < D (all four body-stacked up). Full size (subject to MOC + large-wick + sideways checks).
- **SHORT trend:** A > B > C > D (all four body-stacked down). Full size (same checks).
- **Cautious trend:** first three (A, B, C) stack cleanly in one direction, D breaks against. Same direction trade, reduced size. *Discretionary — tabled per AM's note, use strict-sequence-only for code V1.*
- **SIDEWAYS:** any body-overlap among the four candles, or first-three stack broken. Range trade both sides, always reduced size.

### Engulfment hierarchy (NEW from apr-29) — which master candle is "in charge"

When master candles overlap, the candle that **engulfs** prior candles becomes the dominant frame. Its high/low define make-or-break for the trapped side.

- **Engulf test:** candle X engulfs candle Y when `body_top(X) ≥ body_top(Y)` AND `body_bottom(X) ≤ body_bottom(Y)`. Wicks may be checked separately as a wider engulf-with-wicks variant.
- **In-charge ordering:** scan A→D in time order; each candle that engulfs all earlier candles becomes the new "in-charge" frame, replacing the prior one.
- **Trapped-side rule:** if the in-charge candle is the 4 AM and it engulfed the 3:30 + GlobEx, a bounce that fails to reach top of 4 AM means buyers have "lost the plot" — short bias confirmed. Mirror for shorts trapped under a down-engulfing candle.

AM verbatim apr-29: *"the 4:00 a.m. candle engulfed the 3:30 candle and the GlobeEx candle... it covered both of those candlesticks, engulfed them completely... this bounce up here has to get to the top of that 4:00 a.m. or buyers have lost the plot."*

**Implementation note (V2_5):** L1 already emits each master candle's H/L/body. Add a derived `engulfing_master_candle` field on each candidate event = the most recent candle in {A,B,C,D} that engulfs all prior. Used by §6 target rule.

---

## 2. SIZING GATE (MOC Validation)

### Input (RESOLVED)
`ratio = volume(today 3:30 PM candle) / volume(today 3:00 PM candle)`

### States (RESOLVED — apr-24 video closes the 0.80-1.00 gap)
| Ratio | State | Size |
|---|---|---|
| `ratio > 1.20` | **GREEN** | Full |
| `1.00 < ratio ≤ 1.20` | **ORANGE** | Half |
| `0.80 ≤ ratio ≤ 1.00` | **GRAY** | Reduced (half) |
| `ratio < 0.80` | **GRAY** | Reduced (half) |

AM verbatim apr-24: *"How about 8 to 1? It'll stay gray. Stay gray. It just means there's not enough institutional flow to confirm forward motion."*

### Gray = reduced size (RESOLVED)
AM: *"less than 0.80 grey; reduced size."* Not explicitly "no trade" — reduced, similar to Orange. Gray + Orange behave the same for sizing; use Gray as a stricter warning flag.

### Orange does NOT widen the stop (RESOLVED)
AM: *"Stop does not widen, size goes smaller."* Orange → half size, same stop.

### Never-full-size combinations (RESOLVED)
- Sideways day → NEVER full.
- Orange or Gray MOC → NEVER full.
- Only **GREEN + four-candle-trend-stacked** = full size.

### Green MOC + Sideways candle-sequence (RESOLVED)
This is a specific hybrid regime AM described:
1. Use 200 SMA slope to pick direction (see §3).
2. Look for deep dips (if 200 up) or sharp spikes (if 200 down).
3. Target: back toward the prior 3:30 candle.
4. Size: reduced (sideways → never full).

### Outsized news-candle level (NEW from Q&A)
If a mid-session candle's volume exceeds BOTH the prior day's 9:30 AND 3:30 candle volumes, register its high and low as **revisit levels** in today's and future days' level set. New level type — add to the tracker.

---

## 3. SMA SLOPE (direction signal, not the primary gate)

### 200 SMA slope (RESOLVED)
- **Measurement:** `slope = SMA_200(today, 09:30 close) − SMA_200(yesterday, 09:30 close)`.
- **Binary output:**
  - `slope > 0` → UP
  - `slope < 0` → DOWN
  - `slope = 0` (rare) → treat as DOWN by default / revisit.
- **Sticky for the day.** Computed once at RTH open and held.
- Applies the same way to anyone trading overnight (it's a calendar-day comparison).

### 50 SMA role (RESOLVED)
Not a bias input. Used only as a **risk/chop estimator** (a supplementary size-down signal when it's flat or choppy near price). No slope-direction gate.

---

## 4. ENTRY RULES

### Bias → entry direction (RESOLVED)
- **Longs are taken on DIPS.** Always.
- **Shorts are taken on BOUNCES.** Always.

Entry level for a dip or bounce depends on the **structural context** — which prior-day candle is providing support (dip) or resistance (bounce), and where the fade/bounce has taken price relative to nearby master candles. This is **discretionary and context-specific** — AM wants to walk through live examples before we codify. For V1, use a simple rule: nearest retrace-side master-candle edge.

### Entry rule — TWO DISTINCT PATTERNS (REFINED 2026-04-24 transcript)

The apr-24 chart walk-through revealed AM uses **two different entry mechanisms** depending on day-type. Both use 1-minute bars as the execution timeframe.

#### Pattern A — Full-trend break entry (clean 4-body stack)

Used when the day-type classifier returns LONG_TREND or SHORT_TREND (all four bodies stair-step cleanly, no overlap).

- **Trigger:** break of the 9:30 candle's high (long) or low (short).
- **Entry price:** at the break. Not a limit-at-level — this is the breakout of the 9:30 stacked body.
- **Stop:** bottom of the 9:30 candle (long) / top of the 9:30 candle (short), **plus ~5 ticks buffer** on full-trend days.
- **Timing:** "10 minutes after the high on the 9:30 candle" — i.e., the 1-min or 5-min bar after 10:00 ET that breaks the 9:30 body-high.

AM verbatim: *"on a trending day north, two non-overlapping candles means 10 minutes after the high on the 9:30 candle, you go long with the stop at the bottom of the 9:30 candle plus maybe five ticks if it's a full trending day."*

#### Pattern B — "Look below and fail" / "Look above and fail" (all other regimes)

Used when day-type is SIDEWAYS, CAUTIOUS, or when watching a specific level within a trend (news-candle wick, multi-day level, etc.). This is the **default pattern** — most of AM's trades use this.

##### Pattern B refinement (apr-29) — "through the V and back down"

The breach must **trade through** the level, not merely tag it. AM verbatim apr-29: *"I want it to move up and then back down. So through the V and then back down. I do not want it to get through the open of the 9:30 candle."*

- **Penetration requirement:** breach bar must close on the recovery side AND the prior bar's body or wick must have *crossed* the level (not just touched).
- **Invalidator:** for a Pattern B short setup at a level, if price subsequently trades through the **9:30 candle's open**, the setup is dead — abort. Mirror invalidator for longs.
- **Why:** a clean tag-and-rejection is too easy to fake. AM wants to see the V-shape — penetration, rejection, return — to confirm trapped traders.

Mechanical definition (CONFIRMED by screenshot 4 — single-bar pattern):

1. Price approaches a candidate level (e.g. 7085).
2. **Breach candle = ONE 1-minute bar** with: `low < level` AND `close >= level` (long setup; flip for short). The breach and recovery happen within the SAME bar — wick goes below, body closes back above.
3. **Confirmation requirement**: at least one bar AFTER the breach must NOT take out the breach candle's low (i.e., the next bars must hold a higher low).
4. **Entry trigger = price crosses the breach candle's HIGH** (for long) — typically a buy-stop placed at breach_bar.high. For short, sell-stop at breach_bar.low.
5. **Stop = LOW of the breach candle** (for long) / **HIGH of the breach candle** (for short).

Today's 7085→7092 confirms: breach bar wicked to 7079 (low), body closed back above 7085, body high was 7092. AM placed buy-stop at 7092, stop-loss at 7079, risk = 13 points = breach candle's full body+wick width.

**NOT a 2-bar close-based pattern.** The Gemini ThinkScript `spring_long = close[1] < IBL and close > IBL` is a related but distinct 2-bar variant (prior bar closes below, current bar closes above). It's coarser than AM's verbal rule and triggers later. We use AM's 1-bar version per screenshot 4. The 2-bar variant could be a separate ML feature.

AM verbatim: *"This candlestick high gives us the automated version of where to enter. And the stop is the low of the candlestick that accomplished the breach."*

Why the breach candle is the reference (not the level itself): the breach candle is where the market tested and rejected the break — it becomes the new, tighter support/resistance. The breach candle's body-width IS the stop distance (replaces the generic "entry-candle body width" rule from earlier for Pattern B trades).

Today's 7085 → 7092 → 7079 trade arithmetic: breach candle was one 1-min bar, high = 7092, low = 7079. Entry 7092, stop 7079, risk 13 points.

#### Which pattern fires when

| Day-type | Entry pattern |
|---|---|
| LONG_TREND (all 4 bodies up, no overlap) | Pattern A (break of 9:30) |
| SHORT_TREND (all 4 bodies down, no overlap) | Pattern A (break of 9:30) |
| CAUTIOUS_LONG / CAUTIOUS_SHORT | Pattern B (breach-and-fail) |
| SIDEWAYS | Pattern B (breach-and-fail) at each range edge |
| News-candle wick level | Pattern B (breach-and-fail) |

#### The earlier "two 5-min non-overlapping bodies" rule

That earlier phrasing was a simpler way to detect the same breach-and-fail structure on a slower timeframe. For V2_4 use Pattern B's explicit breach-candle definition on 1-min bars — it's sharper.

#### Architectural implication

V2_3's "Pre-Place Panel" of limit-at-level orders is deprecated. V2_4 still shows candidate levels, but treats them as "levels to watch for Pattern B confirmation." The Staging Card alert fires on the breach-candle close, not on the level touch.

#### Failed-trigger recycling (NEW from apr-29) — Pattern B′

When a Pattern B trigger fires, fails, and price rolls back through the trigger price, the **failed trigger price becomes the next setup's stop**. This converts a losing signal into a structural reference for the next trade.

- **Setup:** Pattern B long fires at level L (entry at breach.high = T_L), price moves up briefly, then rolls back below T_L.
- **Recycled signal:** opposite-direction Pattern B short with stop placed just above T_L (the failed long trigger). Entry trigger remains the next breach-and-fail to the downside.

AM verbatim apr-29: *"that long becomes the stop for the short. So if what I am looking for now is to take another short at the failure of 7158 to 7160. That's what I'm looking for for this afternoon."*

Concrete from apr-29: 10:30 long triggered at 7157–7158, failed; AM is now stalking a short with stop at 7158–7160.

**Implementation note (V2_5):** L1 should emit `failed_trigger_level` events with price and direction. L2 scorer can use these as a candidate pool for the opposite-direction Pattern B in the same session.

### Bounce short when 9:30 opens below 4 AM (RESOLVED default)
Default entry level = **4 AM candle close**. Expand risk when using this default (wider stop).

---

## 5. STOP RULES

### Stop width = entry candle body-width (RESOLVED)
The stop distance is the range of whichever **master candle triggered the entry** — NOT fixed to 4 AM.

### Bigger-candle exception (RESOLVED)
If the entry-trigger candle is inside the prior 3:30 candle OR inside the prior 9:30 candle (i.e., contained by one of those two reference boxes), use the **bigger enclosing candle's** width as the stop distance.

### Sideways stop = 2 × candle width (RESOLVED)
On sideways days, allow one extra candle width of room. This is why sideways trades are always half-size — the dollar risk is the same as a full-size trade with a normal stop.

### ADR clip (OUR addition, not AM's)
Our pipeline clips stop distance to [0.30, 0.80] × ADR20. This is an engineered bound for label stability, not AM's rule. Decision: keep it for the ML pipeline; don't apply it in the live indicator if AM's rule is the source of truth.

---

## 6. EXIT RULES

### First target = top of entry candle (100%) — scale out 50% (REFINED 2026-04-24)
The first target is the TOP of the entry candle (for long) / BOTTOM (for short). In Fibonacci terms this is the 100% level measured from the entry point up to the candle's high.

Scale-out 50% of the position at this first target.

**Fibonacci anchor (CONFIRMED by screenshot 2):** The Fibonacci tool is anchored from the **entry candle's low to its high** (long), or **high to low** (short). 100% = top of the entry candle. 150% = 1.5× candle width above the high. 200% = 2× candle width above. The 50% level (entry-candle midpoint) is also marked — used for adds and stop-tightening per §6.

### Runner targets = Fibonacci extensions (NEW from apr-24)
The remaining 50% rides to a Fibonacci extension target. Which extension depends on the **200 SMA slope steepness**:

| 200 SMA state | Second target |
|---|---|
| Up-sloped (running-train regime) | 200% extension (stretch: 250%) |
| Flat | 150% (cap); optionally 161.8% |
| Down-sloped on a short | mirror of above |

AM verbatim: *"If you've got all your moving averages under you and your candle bodies are not overlapping each other, you're going to have upside pressure… 200% would be the first target. Now it goes to 250"* — and *"when the moving average of the 200 is flat, it's going to dampen… I'm going to take the 100% and go to 150."*

**Tier note:** the 150/200/250 Fib ladder is a **Tier 3 nuance** (defer). Ship MVP with just the 100% first-target + candle-walk runner. ML (Phase 3) picks the right extension later.

### Engulfing-candle structural target (NEW from apr-29)

Distinct from the entry-candle Fibonacci ladder above. When Pattern B fires at a level inside an engulfing master candle (see §1 engulfment hierarchy), the **target is the opposite extreme of that engulfing candle**, with a sequenced extension:

1. **First structural target:** bottom of the engulfing master candle (for shorts) / top of it (for longs).
2. **Extended structural target:** if the 9:30 candle has already pierced past that level, the actual target shifts to the **bottom of the 9:30 candle** (long: top of 9:30).

AM verbatim apr-29: *"when the short triggers as it does, the target is always the bottom of that 4:00 a.m. candlestick. And then if that 9:30 candlestick has engaged lower, the actual target is the bottom of the 9:30 candlestick. Why? because the buyers have lost the plot."*

This runs **in parallel** with the entry-candle Fib ladder. Use whichever target is closer to entry as the first scale-out, the further as the runner target. ML scorer can learn the regime preference.

### Fibonacci extension DOWN from the institutional candle (NEW from apr-29)

For sideways-day shorts, project a Fibonacci extension **downward from the institutional master candle** (typically the 4 AM Europe candle when it's the engulfing one, or 3:30 PM otherwise). This is a third, parallel target system.

- **Anchor:** institutional candle low → high → extend DOWN by 1× candle width = 100% extension below; 1.5× = 150%; etc.
- **Behavior:** in sideways markets, prior swing lows tend to cluster at these projected levels. AM uses them as scale-out zones for runners.
- **Concrete example (apr-29):** 4 AM candle width projected down from its low landed at ~7154, which clustered with multiple other prior-day lows.

AM verbatim apr-29: *"if you draw a Fibonacci around that 4:00 a.m. candlestick and expand it as an extension down, those sorts of things going to give you a target. Particularly in sideways markets, particularly interesting."*

**Tier note:** all three target systems (entry-Fib up, engulfing-candle structural, institutional-Fib down) are Tier 3. MVP keeps 100% entry-Fib + candle-walk runner. The institutional-Fib-down system is the natural fit for the V1.1 Fibonacci runner ladder.

### Runner stop = candle-formation walk (RESOLVED)
On the remaining 50%, walk the stop using candle-based levels (previous swing low on a long, etc.), NOT the SMA20 trail. AM explicitly prefers candle-formation stops.

### Tighten-on-add: the "50% line" rule (NEW from apr-24)
When adding to a position on a bounce/pullback during a trending move, set the stop at the **50% midpoint of the entry candle** instead of its extreme. This ties the risk to the half-candle as the position grows.

AM verbatim: *"any bounces up we can add to that position and we could make our stop the 50% line to tighten up on the risk."*

**Tier note:** scale-in is Tier 3 — defer. MVP: single-entry, single scale-out at 100%, candle-walk runner.

### Convergence exit (TABLED)
No separate convergence-exit rule. The 100% scale-out + candle-walk runner covers it.

### Time flat (unchanged)
- ES/NQ/GC: 15:00 ET
- CL: 14:30 ET
- Cancel remaining limits: 14:30 ET (14:00 ET CL)

---

## 7. SIDEWAYS EXECUTION

### Range edges (RESOLVED)
- **Lookback: up to 3 days.** *"If we are consolidating we might need three days of motion to find edges."*
- **Primary edges:** prior days' 30-min highs/lows.
- **Also valid:** the 3:30 and 9:30 candle highs/lows from prior days.
- **Not valid as standalone:** pre-market wicks alone — those are usually part of a master candle anyway.

### Direction selection in Green + Sideways (WIRED INTO V2_4 — apr-27)
200 SMA slope defines the bias:
- Slope up → fade deep dips back toward prior 3:30 (LONG).
- Slope down → fade sharp spikes back toward prior 3:30 (SHORT).
- Slope flat → no trade.

**Confirmed live by AM 2026-04-27:** *"today looks like a day of neutral direction so far... I bought the steep dip off the 4am candle because the 200sma is up but now I am flat after taking profit at the 3:30pm high"*. Day-type was Sideways with body-stack DOWN/UP/overlap; she still traded LONG at the 4 AM Europe wick because slope was UP, exited at PrInst H. This is the canonical example.

### Size (RESOLVED)
Never full. Half at best.

### Stop (RESOLVED — V2_4 MVP uses europe-width clipped to ADR; AM's 2× rule deferred)
AM's stated rule: 2 × candle-body width.
V2_4 MVP: same `V2ComputeStopDistance` as trend-mode (europe width clipped to [0.30, 0.80] × ADR20). The 2× widening is on the Tier 3 list.

### First target (V2_4 MVP)
**Prior 3:30 H** for longs / **Prior 3:30 L** for shorts. AM's rule §7 above ("back toward prior 3:30") implemented as a fixed structural target rather than 1× candle-width. Skip the trade if PrInst is on the wrong side of entry (would mean target in unprofitable direction).

### Exit (V2_4 MVP)
Hard target hit intrabar → flat. No trail (trail is TREND-mode only). Hard time-close at 15:00 ET (14:30 CL) applies as backstop.

### V2_4 candidate-pool restriction (apr-27 wiring)
On Sideways-FADE days the candidate set is **structural extremes only**, slope-direction-only:
- Slope UP → GlobExL, EuropeL, PrInstL.
- Slope DOWN → GlobExH, EuropeH, PrInstH.
ORH/ORL, Pr30 H/L, SMA50_30, SMA200_30, MidMid are intraday-trend tools — explicitly excluded so the fade play stays a clean retest, not a continuation. VWAP/AnchVWAP excluded by the same rule that already applies in trend mode.

### V2_4 daily count cap
`signalsToday < min(2, MaxSignalsPerDay)` in FADE mode. Sideways days are higher-noise; the second fade is allowed if structure presents, third+ is not.

---

## 8. TRADE COUNT / DAILY DISCIPLINE

### Process-based (RESOLVED)
AM: *"Everything is process based. I trade if the setup is there."*
- No hard cap.
- No stop-after-N-winners rule.
- Implementation: `MaxSignalsPerDay` in the indicator should be treated as a guardrail, not a tight process rule. Default 5 is fine.

### Afternoon counter-trend window (NEW from apr-29)

After ~13:30 ET, any move against the morning's developed direction is classified as a **counter-trend bounce/fade**. Sizing is reduced; conviction is lower.

AM verbatim apr-29: *"right now it's past 130, which means it's the counter trend. Yes, that's what's happening right now. They're trying to build the counter trend bounce. I just don't believe that they have what they need in terms of the volume to do that."*

- **Threshold:** ~13:30 ET. Likely tied to the post-lunch volume return when institutions reposition.
- **Effect:** afternoon trades against the morning's prevailing direction → reduced size (treat like sideways-half regardless of MOC color).
- **Effect on with-trend afternoon trades:** unchanged, full process applies.

**Implementation note (V2_5):** L1 emits a feature `is_post_1330_counter_trend` boolean (true when current bar > 13:30 ET AND signal direction opposes morning prevailing direction). Morning prevailing direction = sign of (last_pre_1330_close − 09:30 open). L2 scorer applies size reduction.

---

## 9. LEVEL SET

Updated level list, ordered by priority in AM's framework:

**Master candles (the backbone):**
- Prior day 3:30 PM candle H / L (the institutional candle)
- GlobEx 6 PM candle H / L
- Europe 4 AM candle H / L
- RTH 9:30 candle H / L (or 10 AM for CL)

**Master-candle 50% midpoints (NEW from apr-29) — generalized "50% line":**
The 9:30 IB midpoint (from the Gemini ThinkScript) was a special case. AM applies the 50% midpoint to **every master candle box**:
- `Pr30Mid` = midpoint of prior day's 3:30 PM candle
- `GlobExMid` = midpoint of GlobEx 6 PM candle
- `EuropeMid` = midpoint of Europe 4 AM candle
- `IBMid` = midpoint of 9:30 candle (already in the spec)

Behavior: a box midpoint is a natural pivot. Losing it from above = short trigger; reclaiming it from below = long trigger. AM verbatim apr-29: *"You don't even have to use the moving averages... You would just use the boxes and go, 'Hey, I'm going up 50% of the GlobeEx. I'm taking it short if it loses that 50% line.'"*

**Implementation note (V2_5):** L1 already computes box H/L; emit midpoint as `(H+L)/2` and add to the candidate-level set. Mark with `level_kind="box_midpoint"` so L2 scorer can weight separately.

**Structural references (sideways edges, multi-day):**
- Prior days' highs / lows (up to 3 days back)
- Prior days' 3:30 H/L, 9:30 H/L specifically

**Additional (new from Q&A):**
- **Outsized news-candle WICK** — any mid-session bar whose volume exceeds BOTH prior day's 9:30 and prior day's 3:30 volumes. Register ONE wick as a level, direction-gated by 200 SMA slope:
  - 200 up → register the **lower wick** as a support zone.
  - 200 down → register the **upper wick** as a resistance zone.
  - 200 flat → undefined (ask AM).
  Persistence: level stays valid as long as it's the highest-volume candle in recent sessions. Replaced when a higher-volume candle prints.

**Level volume tagging (NEW from apr-24):**
Every level carries its origin candle's volume. When multiple levels cluster at a similar price, the **highest-volume origin wins**. AM verbatim: *"the one with the most volume is going to win."* Bullish vs bearish body is irrelevant — only volume ranks them.

**Tier note:** news-candle detection + volume-priority are Tier 3 nuances. MVP treats all same-named levels equally. Volume priority becomes an ML feature (or a Tier 3 indicator enhancement).

**Permissions, NOT entries (from earlier rulings):**
- VWAP (slope + distance, not entry)
- Anchored VWAP (pipeline construct — not AM's taught level)
- 50 SMA (risk/chop estimator)
- 200 SMA (bias via slope)

**Deprioritized:**
- Pre-market H/L — usually just a wick of a master candle; don't track as standalone.

---

## 10. CONTRACT-SPECIFIC: CL (CRUDE OIL)

**Status: TABLED by AM on 2026-04-24.** She wants to revamp the CL rules and send them back. Interim guidance from the transcript: use ES-style timing for CL. *"I'm going to guess that it's not going to matter and we can still keep the same structural formation."*

**Interim rule for V2_4 MVP:**
- Use the SAME 4-candle sequence as ES: Prior 3:30 → 6 PM → 4 AM → **9:30** (NOT the earlier 10 AM rule).
- Rationale per AM: GlobEx opens at the same time for CL as ES; 4 AM captures same edge; volume concentrates at 9:30 regardless of CL's pit-bell difference.
- Flat by 14:30 ET. Cancel limits at 14:00 ET (these are unchanged).

**When AM delivers the CL revamp**, re-evaluate. This is a known deferred item, not a resolved rule.

---

## 11. WHAT V2_4 NEEDS TO CHANGE (post Q&A) — STATUS IN V2_5

**Note (2026-04-27):** V2_5 is the current production implementation. This priority list is retained for historical context and to track what is now resolved vs still deferred. Items marked IMPLEMENTED are structurally addressed by the L1/L2/L3 architecture; items marked DEFERRED V1.1 remain open for a future release; items marked OPEN require AM clarification but are no longer blocking (they are emitted as features).

| Priority | Gap | Complexity | V2_5 Status |
|---|---|---|---|
| 1 | Four-candle body-stacking day-type classifier (§1) — replaces SMA-stack gate | Medium | **IMPLEMENTED** — L1 emits `day_type_am` as a feature; L2 scorer uses it |
| 2 | MOC validation (§2) — GREEN/ORANGE/GRAY with half-size on Orange/Gray + Sideways | Medium | **IMPLEMENTED** — `moc_state` emitted as feature; L2 scorer applies sizing |
| 3 | Entry stop = entry-candle body-width (§5), with bigger-candle exception | Medium | **IMPLEMENTED** — emitted as feature; L2 scorer computes stop/target |
| 4 | First target = 1× entry-candle width, scale out 50%, candle-walk runner (§6) | Large | **IMPLEMENTED (partial)** — 100% first target + runner wired; Fibonacci runner ladder (150/200/250%) deferred to V1.1 |
| 5 | Pattern B wired end-to-end (breach-candle state machine + candidate event) | Medium | **IMPLEMENTED** — L1 LevelWatchState machine, `pattern_type="B"` candidate emission |
| 6 | Sideways FADE one-direction per 200-SMA slope | DONE (MVP in V2_4 apr-27) | **IMPLEMENTED** — FADE direction emitted as feature; L2 scorer decides; both long and short directions surfaced as candidates |
| 7 | 200 SMA slope via yesterday's 9:30 → today's 9:30 delta, sticky (§3) | Small | **IMPLEMENTED** — `sma200_slope_delta` feature, locked at 9:30 |
| 8 | Outsized news-candle level detection | Small | **IMPLEMENTED** — `news_wick_registered` event; level added to tracker |
| 9 | Large-wick risk modifier (§1) — reduce size when wick > body | Small | **IMPLEMENTED** — `large_wick_flag_{A,B,C,D}` emitted as features |
| 10 | Remove SMA20 trailing-stop in favor of candle-walk | Medium | **IMPLEMENTED** — candle-walk runner in L2; SMA20 trail removed from live path |
| 11 | CL institutional candle switch (10 AM vs 9:30) | Small | **IMPLEMENTED** — instrument-specific candle times handled in L1 |
| 12 | Fail-open contract (no silent drops, explicit abstain at every gate) | Architectural | **IMPLEMENTED** — prime directive enforced at L1/L2/L3; every block is a logged `abstain` event |
| 13 | Vocabulary fix (Pattern A / Pattern B, `candidate` vs `signal`) | Small | **IMPLEMENTED** — `candidate` is L1 output; `signal` is L2 output; pattern_type on candidate |
| — | Fibonacci runner ladder (100/150/200/250%) | Medium | **DEFERRED V1.1** |
| — | 50% midpoint adds (scale-in) | Medium | **DEFERRED V1.1** |
| — | Full HTTP feature payload to ML endpoint | Large | **DEFERRED V1.1** |
| — | F12 hotkey kill-switch via NT8 AddOn | Small | **DEFERRED V1.1** |
| — | Holiday calendar via parquet lookup | Small | **DEFERRED V1.1** |
| — | Body-stacking: 3-node vs 4-node (exact count) | OPEN | **NOT BLOCKING** — both variants emitted as features; ML/heuristic decides |
| — | FADE direction one-sided vs two-sided on flat slope | OPEN | **NOT BLOCKING** — both LONG and SHORT FADE candidates emitted; scorer decides |
| — | Slope threshold for runner target choice (steep vs flat) | OPEN | **NOT BLOCKING** — raw `sma200_slope_delta` emitted; scorer maps to runner extension |
| — | CL rule revamp (AM deferred on apr-24) | OPEN | **NOT BLOCKING** — CL uses ES-style timing for now; will update when AM delivers revamp |
| — | Engulfing master-candle target (§6 NEW apr-29) | Small | **DEFERRED V1.1** — emit `engulfing_master_candle` feature; target wiring in V1.1 |
| — | Box midpoints (Pr30Mid / GlobExMid / EuropeMid) (§9 NEW apr-29) | Small | **DEFERRED V1.1** — emit as `level_kind="box_midpoint"` candidates |
| — | Pattern B "through the V" penetration requirement (§4 NEW apr-29) | Small | **DEFERRED V1.1** — refines existing breach detector; non-breaking until wired |
| — | Failed-trigger recycling Pattern B′ (§4 NEW apr-29) | Medium | **DEFERRED V1.1** — emit `failed_trigger_level` event; new candidate source |
| — | Afternoon counter-trend window (§8 NEW apr-29) | Small | **DEFERRED V1.1** — emit `is_post_1330_counter_trend` feature; sizing in L2 scorer |
| — | Institutional-Fib-down target system (§6 NEW apr-29) | Medium | **DEFERRED V1.1** — third parallel target ladder; folds into runner ladder work |
| — | DOM spoofing detection (§11.6 NEW apr-29) | Large | **NOT IN SCOPE** — requires DOM-aware sidecar; documented as discretionary-only |
| — | 9:30 width ↔ subdued motion hypothesis (§12.5 NEW apr-29) | Research | **PENDING DATA** — AM running ChatGPT/Sidekick analysis on ES 1-min CSV |

---

## 11.5 GEMINI THINKSCRIPT — what we learned from the doc

AM's Gemini-generated ThinkScript (`screenshots/5.txt`) revealed two important things:

**(a) The 9:30 IB midpoint as a level.** Gemini plots `Midpoint = (ib_high + ib_low) / 2` as a dashed gray line after 10:00 ET. This is AM's "50% line" verbalized in apr-24 for both adds and stop-tightening. Add to V2_4's level set: a derived "9:30 mid" level that activates at 10:00 ET.

**(b) Day-of-week probability table — DO NOT IMPLEMENT VERBATIM.** The ThinkScript hardcodes Mon=52, Tue=78, Wed=61, Thu=45, Fri=71 with a 65% threshold for FULL vs REDUCED size. Two problems:
- The numbers are unsourced and likely LLM-hallucinated. AM said *"Gemini wrote that for me"* — accepted whatever the model produced. No backtest, no provenance.
- The table contradicts AM's verbal claim *"Fridays are more bullish than any other day."* Tuesday=78 is higher than Friday=71 in her own code. AM didn't notice because the script is decorative, not load-bearing.

**Recommendation:** Do not codify the day-of-week table in V2_4. Log day-of-week as a feature for the ML layer (per AM's "machine learning is the nuance" framework). If a hard rule is needed pre-ML, encode only AM's stated belief: *Friday = full-size eligible when other gates pass*. Let the ML discover any real DOW edge later.

**Open question for AM:** confirm whether Tue=78 reflects any real backtest or should be removed.

## 11.6 DOM SPOOFING DETECTION — discretionary input only (NEW from apr-29)

AM uses Depth-of-Market actively to detect **defended levels** — large limit orders that get pulled-and-replaced as price approaches. She reads this as institutional spoofing to scare opposing flow, and **fades the defenders** (i.e., trades INTO the level the spoofers are trying to protect against, on the assumption that real flow will eventually overwhelm the spoof).

AM verbatim apr-29: *"I use depth of market all the time, but it's only to tell me who's trying to game the price action. So this morning, the reason that I took the long pre-market is I noticed that about 8:30 when the volume was super light, some guy, gal, whomever had a thousand lot sitting in at 7150. And I thought they are trying to defend that area. They are trying to defend it. And when it would get super close, they would pull it and then when price action would bounce up again, they would put it back out there. So, they were just trying to scare traders into not shorting because a thousand lot coming in would push the market higher. And I saw it there and I went, you guys, you're just gaming. I'm going long."*

**Concrete pattern (apr-29 Fed-day):**
1. Pre-market light volume (~8:30 ET).
2. Repeated 1,000-lot bid at 7150, pulled when price approached, re-placed when price moved away.
3. AM read = defenders gaming shorts → went **long at 7153**, well before any Pattern A or B trigger.

**Implementation status:** NOT in V2_5 scope. NT8 indicators do not have DOM event-stream access in the same way live order entry does, and detecting spoof patterns (pull-replace cycles within seconds) requires the live order book, not bar data. This rule explains why AM has discretionary entries that don't match Pattern A or B — the DOM read is a third entry source.

**V1.1+ consideration:** if the V2_5 architecture grows to include a DOM-aware sidecar process, emit `dom_defended_level` events as a new candidate source. Until then, this is a documented discretionary input the indicator cannot replicate.

---

## 12. REMAINING DISCUSSION ITEMS (post apr-29 walk-through)

Most of the original open items were resolved in the apr-24 video. Remaining:

1. **200 SMA slope flat case.** For the news-candle wick rule, we have "200 up → lower wick support, 200 down → upper wick resistance." Flat-200 behavior not stated. Low priority — flat 200 is rare.

2. **Body-stacking: what counts as "not overlapping"?** AM confirmed body-not-wick, but the exact threshold (strictly no overlap, or tolerance in ticks?) wasn't pinned down. Implementation: use strict no-overlap (`body_bottom(higher) > body_top(lower)`) for MVP, relax if behavior looks too strict on replay.

3. **CL revamp pending.** AM will revisit CL rules. For now CL uses ES-style timing (9:30 institutional candle). See §10.

4. **Gemini-generated rules doc.** AM mentioned a document named *"probability threshold Statistical hybrid 30 minute IB and statistical dashboard visual confirmation and manual scaling"* from Gemini — contains the Friday full-size rule. If obtained, parse for any other rules we haven't captured.

5. **9:30 opening width ↔ subdued future motion (RESEARCH HYPOTHESIS — apr-29).** AM stated: *"the wider the opening candlestick is, the 9:30 opening candlestick is, the more likely it is that future motion is subdued. So that way we look at only 150% versus 200%."* She's running this analysis in ChatGPT 5.5 / Sidekick (locked out until 2026-05-01). Pending: confirm the relationship empirically against the ES 1-min CSV she requested. If confirmed, the rule becomes: **wide 9:30 → cap runner at 150% Fib instead of 200%/250%**. This maps directly into the V1.1 Fibonacci runner ladder (deferred item) as a gating input.

6. **Counter-trend afternoon threshold precision.** §8 uses ~13:30 ET as the boundary. AM did not give an exact minute — confirm whether 13:30 is sharp or whether there's a transition zone (e.g., 13:00–14:00 = ramped reduction).

7. **Engulfment with vs without wicks.** §1 engulfment hierarchy uses bodies; AM's apr-29 verbal description used "engulfed them completely" which could mean either bodies or full range. MVP uses bodies (consistent with §1 body-stacking rule); confirm in next AM session.

All other apr-24 / apr-29 questions are resolved in §1–§11.

---

## 13. ML TRAINING IMPLICATIONS

Concrete feature adds needed in `event_builder.py` / `feature_builder.py`:

- `day_type_am` categorical: `long_trend / short_trend / cautious_long / cautious_short / sideways_green / sideways_orange / sideways_gray`
- `candle_sequence_delta_A_B`, `delta_B_C`, `delta_C_D` — body-gap sign and magnitude between adjacent pairs
- `body_overlap_pair_{AB,BC,CD}` — boolean
- `large_wick_flag_{A,B,C,D}` — boolean
- `sma200_slope_open_to_open` — the new measurement per §3
- `moc_ratio_3_30_vs_3_00` (replace binary flag)
- `entry_candle_width_pts` — the stop/target unit
- `outsized_news_level_proximity` — distance to any registered outsized news-candle level

**NEW from apr-29:**
- `engulfing_master_candle_id` — which of {A,B,C,D} engulfs all earlier ones (or null)
- `engulfing_master_top_pts`, `engulfing_master_bottom_pts` — distance from entry to engulfing candle's extremes (target features)
- `nine30_width_pts` — 9:30 candle width (the subdued-motion hypothesis input)
- `is_post_1330_counter_trend` — boolean per §8
- `box_midpoint_proximity_{Pr30,GlobEx,Europe,IB}` — distance from current price to each box midpoint
- `pattern_b_penetration_pts` — how far the breach bar penetrated through the level (the "through the V" depth)
- `failed_trigger_level_pts` — distance to most recent failed Pattern B trigger in same session, signed by direction

Target changes:
- Replace `realized_R_runner` (SMA20 trail) with `realized_R_candle_walk` (candle-formation exits) to match AM's actual exit model.
- Alternatively, keep both targets — the SMA20 trail version is what the current rt2_1 model was trained on, so it remains the reference for shadow validation until a new model is trained.

---

## SOURCES

- **Anne-Marie Q&A, 2026-04-29 (Fed-day live trade narration)** — engulfment hierarchy, box midpoints, "through the V" penetration, failed-trigger recycling, engulfing-candle structural target, institutional-Fib-down, afternoon counter-trend window, DOM spoofing read, 9:30-width hypothesis
- Anne-Marie Q&A, 2026-04-24 — primary, resolved most original blockers
- `AM_transcript_apr-27.txt` (file note) — sideways-fade live confirmation (canonical example)
- `AM_transcript_apr-23.txt` — day-type gate and sideways trade walk-through
- `AM_transcript_apr_16.txt` — MOC validation framework (superseded by Q&A exact numbers)
- Earlier transcripts (mar-6, apr-8/9/10) — background on levels, exits, pivots, contract-specifics
- `AM_questions_pending.md` — the original 24-question list; this spec is the answered version
