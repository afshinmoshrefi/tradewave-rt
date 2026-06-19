# AMTradeCockpit V3 — Architecture Specification

**Date:** 2026-05-01
**Status:** Phase 1A draft — for Afshin's review before code is written
**Replaces (L1 only):** `AMTradeCockpitV2_5.cs`
**Preserves:** `AMTradeStrategyV1.cs` (L2 scorer + L3 safety, minor candidate-schema updates)
**Lineage:** v1 → V2 → V2_3 → V2_4 → V2_5 → **V3**
**Companion docs:** `AM_rules_v2_spec.md`, `architecture_spec_v25.md`, `am_open_questions.md`

---

## 1. Why V3 (and not V2_6)

V2_5 was the right architectural fix for V2_4's 0.27% conversion rate (2 trades / 741 touches). Going fail-open at L1 with explicit `abstain` logging at L2/L3 eliminated silent drops — that contract stays.

But V2_5 left L1's emit gate too wide: L1 emits a candidate for **every level interaction** inside each bar's [low, high]. The candidate set is the wrong unit. AM does not trade every level interaction; she trades level interactions that occur **inside congestion + with regime alignment**. V2_5 leaned on L2 to do too much filtering with too little data.

V3 keeps V2_5's L1/L2/L3 separation and the fail-open prime directive. It tightens L1's emit gate to fire only on **trader-grade triggers**, defined by three new mechanical features that compose AM's actual decision process:

1. **Dynamic level set** — today's 4 master candles plus prior 1–2 days only when current-day levels are exhausted (apr-29 framing)
2. **Body-overlap congestion** — 5-bar window common-stripe test (the mechanical version of AM's visual congestion read)
3. **5-level regime classifier** — Bullish+ / Bullish / Sideways / Bearish / Bearish+ composed from body-stack + 200 SMA slope

L1 emits a candidate **only when** price approaches a level **AND** congestion is active **AND** regime allows the direction. Each rejection at any of those gates is an explicit `abstain` event — fail-open within the narrower trigger set.

Because V2_5's overall layer contract is preserved, V3 is a focused L1 refactor, not a rebuild. L2 and L3 take a slightly richer candidate schema and otherwise continue to operate as designed.

## 2. Edge thesis (operating hypothesis)

V3 is built around three composable sub-claims, locked with Afshin on 2026-05-01:

| # | Claim | Mechanical realization |
|---|---|---|
| 1 | **Travel.** Price moves predictably between master-candle levels | §5 dynamic level set |
| 2 | **Verification.** Body-overlap congestion before approach signals "live" reversal | §6 congestion detector |
| 3 | **Regime.** 5-level regime sets direction, size, target distance | §7 regime classifier |

Every L1 gate, L2 score input, and stop/target rule maps to one of these three. Features outside these three are noise and are removed from the candidate schema unless they earn their place by a separate sub-claim.

DOM spoofing reads (apr-29 7153-long pattern) are a known 4th edge component. **Tier 1 plan:** V3 ships without DOM detection; AM's DOM-driven trades are an acknowledged gap. **Tier 2 plan (Step 1.5):** bar-based DOM proxies. **Tier 3 (deferred):** DOM sidecar AddOn.

The thesis is empirically untested. Step 2 (backtest, post-V3-build) validates each sub-claim independently. If a component fails its backtest, drop it before adding ML in Step 3.

## 3. Architecture

```
┌───────────────────────────────────────────────────────────────┐
│  L1: AMTradeCockpitV3.cs   (THIS spec — refactor of V2_5)     │
│  - Master-candle capture                                      │
│  - Dynamic level set                                          │
│  - Congestion detector                                        │
│  - Regime classifier                                          │
│  - L1 emit gate (level + congestion + regime → candidate)     │
│  - Pattern A / B / B′ sub-classification                      │
│  - Visual rendering                                           │
│  - JSONL event log + (optional) HTTP candidate emit           │
└───────────────────────────────────────────────────────────────┘
                          ↓ Candidate event
┌───────────────────────────────────────────────────────────────┐
│  L2: AMTradeStrategyV1.cs (existing scorer region)            │
│  - Heuristic scorer (rule-based V1; ML in Step 3)             │
│  - Stop / target finalization                                 │
│  - Size decision                                              │
│  - emits Signal or Abstain{layer:"L2"}                        │
└───────────────────────────────────────────────────────────────┘
                          ↓ Signal
┌───────────────────────────────────────────────────────────────┐
│  L3: AMTradeStrategyV1.cs (existing safety region)            │
│  - 12 toggleable gates (RTH window, daily loss kill,          │
│    cooldown, max signals, kill-switch, recon, etc.)           │
│  - emits Order or Abstain{layer:"L3"}                         │
└───────────────────────────────────────────────────────────────┘
                          ↓ Order
                          NT8 OrderEngine
```

**Fail-open prime directive (preserved verbatim from V2_5):** every L1 path ends in either a `candidate` event, an `abstain` event, or an `error`. There is no fourth option of silently returning. Any gate that blocks must log layer, gate name, reason, and recovery condition.

## 4. Master-candle capture

Logic is unchanged from V2_5. The 4 boundary candles (ET):

| ID | Candle | Time | Notes |
|---|---|---|---|
| A | Prior 3:30 PM (institutional) | 15:30–16:00 yesterday | Master "in charge" candidate |
| B | GlobEx | 18:00–18:30 yesterday | |
| C | Europe 4 AM | 04:00–04:30 today | |
| D | RTH 9:30 | 09:30–10:00 today | (10:00–10:30 for CL — interim) |

For each candle, V3 captures and exposes:

```csharp
struct MasterCandle {
    double Open, High, Low, Close;
    long Volume;
    double BodyTop;       // = Math.Max(Open, Close)
    double BodyBottom;    // = Math.Min(Open, Close)
    double BodyMid;       // = (Open + Close) / 2
    double BodyHeight;    // = BodyTop - BodyBottom
    double FullRange;     // = High - Low
    bool   LargeWickFlag; // = (FullRange - BodyHeight) > BodyHeight  (tail bigger than body)
}
```

Storage: 12 `MasterCandle` slots — today's A/B/C/D plus prior-day (A_y1..D_y1) plus day-2-prior (A_y2..D_y2). Loaded on session boundary, not per-bar.

Engulfment detection (apr-29 §1 update) computed per session: scan A→D in time order; mark each candle's `EngulfsAllPrior` boolean. The most-recent `true` is `engulfingMasterCandle` — used in §10.4.

## 5. Dynamic level set

### 5.1 Default level set (today only)

```
default_levels = {
    A.High, A.Low, A.BodyMid,
    B.High, B.Low, B.BodyMid,
    C.High, C.Low, C.BodyMid,
    D.High, D.Low, D.BodyMid
}
```

12 entries: 8 H/L points + 4 box midpoints (apr-29 spec update §9). Each carries metadata: origin candle ID, level kind (`master_high`, `master_low`, `box_midpoint`), origin volume.

### 5.2 Proximity threshold

```
K_ticks = LevelProximityATRMult × ATR(15)   // computed on 1-min bars, recomputed every bar
```

`LevelProximityATRMult` defaults to 1.0; tunable property. For ES at typical ATR(15) ≈ 8 points, K_ticks ≈ 8 points — a level interaction is "in proximity" if price is within ~8 points.

### 5.3 Extension trigger

```
nearest_above = min{ L ∈ active_levels : L >= price }
nearest_below = max{ L ∈ active_levels : L <= price }

extend_needed =
    (price > max(active_levels))                          // broken above the whole set
 OR (price < min(active_levels))                          // broken below the whole set
 OR (nearest_above - price > K_ticks)                     // no level above within reach
 OR (price - nearest_below > K_ticks)                     // no level below within reach
```

If `extend_needed` and `MaxPriorDaysBack >= 1`: append yesterday's master-candle levels (A_y1..D_y1, 12 more entries). Re-evaluate; if still `extend_needed` and `MaxPriorDaysBack >= 2`: append day-2-prior (A_y2..D_y2). Hard cap at 36 levels (today + 2 days).

Levels older than `MaxPriorDaysBack` days drop automatically at session boundary.

### 5.4 Active set semantics

`active_levels` is recomputed each bar — it's the set L1 considers for candidate emission. It can grow within a session (extension trigger fires) but does not shrink mid-session.

## 6. Body-overlap congestion detection

### 6.1 Mechanical formula

Window N = `CongestionWindowN` (default 5, range 3–10).

For the N bars *immediately preceding the current bar* (i.e., bars at indices 1..N, not the in-progress bar at index 0):

```csharp
double bodyTop_i    = Math.Max(Open[i], Close[i]);
double bodyBottom_i = Math.Min(Open[i], Close[i]);

double body_high_min = Min over i in [1..N] of bodyTop_i;
double body_low_max  = Max over i in [1..N] of bodyBottom_i;

bool congestion_active = body_low_max <= body_high_min;
```

**Interpretation:** all N body ranges share at least one common price (a "common stripe"). The stripe is `[body_low_max, body_high_min]`. If empty (max floor > min ceiling), no congestion.

### 6.2 Tightness (feature for L2)

```csharp
double atr15 = ATR(15);
double stripe_height = body_high_min - body_low_max;   // ≤ 0 when congested
double congestion_tightness = stripe_height / atr15;   // tighter (more negative) = stronger
```

Emitted as a feature on the candidate event. L2 scorer can prefer tighter congestion.

### 6.3 Pre-approach window semantics

Congestion is checked on the N bars **before** the level approach, not including the current bar. Rationale: the approach bar itself is the breach attempt; we want the bars leading up to it to show traders bunched at a similar price (indecision → trapped → reverse on level rejection). If the prior N bars were trending steadily into the level, that's a continuation impulse, not a reversal setup, and L1 emits Abstain rather than Candidate.

### 6.4 Boundary cases

- **Cold start (< N bars in session).** Cannot compute. L1 emits `Abstain{gate: "warmup", reason: "insufficient bars for congestion"}` for any level approach during warmup window.
- **Gap bar.** If a bar's range is more than 3 × ATR(15), exclude it from the window but DO NOT abstain — the prior N − 1 bars still vote. (Prevents news gaps from disqualifying an otherwise-congested setup.)
- **Inside-the-stripe approach.** If price is currently *inside* the congestion stripe (i.e., the stripe is wider than typical and price hasn't approached a level yet), no candidate — there's no level to approach. Wait for stripe-edge break.

## 7. Regime classifier (5-level)

### 7.1 Inputs

- **`overlap_count`** — pairwise body-overlaps among today's 4 master candles. Range 0–3.
  - Pair AB overlaps when `Math.Max(A.BodyBottom, B.BodyBottom) <= Math.Min(A.BodyTop, B.BodyTop)`. Same logic for BC and CD. Sum the trues.
- **`slope_200_pts`** — `SMA200(today @ 09:30 close)` − `SMA200(yesterday @ 09:30 close)`, in points. Computed once at 09:30 and locked.
- **`slope_threshold_pts`** — NinjaScriptProperty, default 0.5 ES points. Below this magnitude, slope is "flat."

### 7.2 Classification table

```
slope_up   = slope_200_pts >  slope_threshold_pts
slope_down = slope_200_pts < -slope_threshold_pts

if overlap_count == 0 AND slope_up:        regime = "Bullish+"
elif overlap_count <= 1 AND slope_up:      regime = "Bullish"
elif overlap_count == 0 AND slope_down:    regime = "Bearish+"
elif overlap_count <= 1 AND slope_down:    regime = "Bearish"
else:                                       regime = "Sideways"
```

`Sideways` catches: (a) ≥ 2 overlaps regardless of slope, (b) any overlap_count with slope flat, (c) overlap_count = 0 with slope flat (rare — clean structure but no directional flow).

### 7.3 Regime → trade direction / size / target distance

| Regime | Direction(s) allowed | Size (contracts, MEES baseline) | First target | Runner |
|---|---|---|---|---|
| **Bullish+** | Long only | Full (4×) | 100% Fib | 200% Fib (250% stretch) |
| **Bullish** | Long bias (full size); short OK only at clear upper levels (half size) | Normal (2×) for long; half (1×) for short | 100% | 150% (selective) |
| **Sideways** | Both | Half (1×) | Level-to-level (next master-candle edge) | None (no runner; full exit at first target) |
| **Bearish** | Short bias (full); long OK at clear lower levels (half) | Normal (2×) for short; half (1×) for long | 100% | 150% (selective) |
| **Bearish+** | Short only | Full (4×) | 100% Fib | 200% Fib (250% stretch) |

Sizing is in MEES units. ES baseline = MEES / 10 rounded down (e.g., Bullish+ Full = 4 MEES = 0 ES; the trader uses MEES at this size). The strategy's `ContractSizeMode` property selects the contract.

`ContractsBaseLine` (NinjaScriptProperty, default 2) is the "Normal" cell. Full = 2×ContractsBaseLine, Half = 0.5×ContractsBaseLine (rounded down, min 1).

### 7.4 Locking

Regime is computed **once at 09:30 RTH open** (after candle D's first bar prints) and **locked for the rest of the day**. No mid-session reclassification — avoids whipsaw.

Exception: if extreme price action (>2× ATR15 single-bar move) flips body-stack mid-day, log a `regime_revision_event` with both the locked and current values. Active regime stays locked. The event is a feature for ML in Step 3.

### 7.5 Boundary cases

- **Pre-09:30 trades.** L1 may detect setups in pre-RTH (Pattern B at GlobEx or Europe levels). Without a locked regime, pre-RTH candidates carry `regime: "PreOpen"` and L2 applies the most conservative size (half) until 09:30 locks it.
- **Insufficient SMA history.** If SMA200 has < 200 bars of data on the daily frame, regime defaults to `Sideways` and a `regime_default_warning` event is logged.
- **No prior 09:30 close** (first day after data load). Regime defaults to `Sideways`.

## 8. L1 emit gate (the core change)

For each 1-min bar `OnBarClose`:

```pseudocode
For each level L in active_levels:
    distance = abs(close - L)
    if distance > K_ticks:
        continue                                    // not yet in proximity

    direction = inferDirection(close, prevClose, L)  // see §8.1

    if !congestion_active(window=N, ending=bar-1):
        emit Abstain{
            layer: "L1", gate: "no_congestion",
            reason: "congestion_active = false in last N bars",
            recovery: "wait for congestion stripe to form"
        }
        continue

    if !regimeAllows(regime, direction):
        emit Abstain{
            layer: "L1", gate: "regime_block",
            reason: f"regime={regime} blocks {direction}",
            recovery: "wait for opposite-side approach or regime re-eval next session"
        }
        continue

    pattern_type = classifyPattern(L, regime, currentBar)   // see §9

    emit Candidate{
        ... all features per §12 ...
    }
```

**No silent paths.** Every level-proximity interaction produces one of: Candidate, Abstain (no_congestion), Abstain (regime_block), Abstain (warmup), Abstain (degenerate_geometry).

### 8.1 inferDirection

```
if close < prev_close:        approaching_from_above_meaning_descending
    if L < close:             # price still above level, descending toward it
        direction = "long"    # buying the dip into level
    else:                     # price at or below level
        direction = "long"    # confirmed touch
elif close > prev_close:      # ascending
    if L > close:             direction = "short"
    else:                     direction = "short"
else:
    direction = None          # flat bar near level — ambiguous; abstain
```

Simplified: descending into level → long; ascending into level → short. Flat-bar approach abstains with `gate: "ambiguous_direction"`.

### 8.2 regimeAllows

```
allow_long  = regime in {"Bullish+", "Bullish", "Sideways", "Bearish"}    # bearish allows long at lower levels
allow_short = regime in {"Bearish+", "Bearish", "Sideways", "Bullish"}    # bullish allows short at upper levels
```

Counter-bias trades (long in Bearish, short in Bullish) carry a `counter_bias_flag = true` feature. L2 scorer downweights or sizes-down these.

### 8.3 Multi-candidate per bar

If a bar's close is within K_ticks of two or more levels (e.g., GlobEx high and Europe high cluster), L1 emits one Candidate per level. L2 ranks. L1 does not dedupe — that's L2's job.

## 9. Pattern A / B / B′ sub-classification

Each Candidate carries `pattern_type ∈ {"A", "B", "B_prime"}`.

### 9.1 Pattern A — full-trend break (regime-gated)

Fires only in `Bullish+` or `Bearish+`. Trigger: 1-min bar that breaks the 9:30 candle's body-high (long, Bullish+) or body-low (short, Bearish+), occurring at or after 10:00 ET.

```
Pattern A long fires when:
    regime == "Bullish+"
    AND now >= 10:00 ET
    AND high > D.BodyTop
    AND L (the active level) == D.BodyTop OR D.High
```

Stop = `D.BodyBottom − 5 ticks`. Entry = `D.BodyTop + 1 tick`.

### 9.2 Pattern B — breach-and-fail (default for all other regimes)

Single 1-min bar with:

```
Pattern B long fires when:
    bar.low < L
    AND bar.close >= L
    AND prior 5 bars congested (§6)
    AND regime allows long
```

Entry trigger = `bar.high + 1 tick` (buy-stop placed at breach bar's high). Stop = `bar.low`.

apr-29 "through the V" refinement: penetration depth `bar.low - L` is recorded as a feature; L2 scorer can require minimum penetration (e.g., > 2 ticks) for high-confidence Pattern B.

apr-29 invalidator: if subsequent bars trade through `D.Open` (long setup) before entry triggers, the candidate is dead — L1 emits `Abstain{gate: "invalidator_9_30_open"}`.

### 9.3 Pattern B′ — failed-trigger recycle (apr-29)

When a Pattern B long fired, price triggered entry, then rolled back through the trigger price within M minutes (default M=15), the trigger price becomes the next short setup's stop:

```
On Pattern B trigger at price T_long, direction long:
    Mark T_long as `recent_failed_long_trigger` until either:
        - Price moves > 1× entry-bar-width above T_long (signal succeeded; clear)
        - M minutes elapse (timeout; clear)
        - Price rolls back through T_long − 1 tick (failure; mark as B′ stop reference)

When B′ stop reference is active and Pattern B short fires near T_long:
    pattern_type = "B_prime"
    stop = T_long + 1 tick
    feature: failed_trigger_level_pts = entry_price - T_long
```

Mirror logic for failed shorts becoming long stops.

### 9.4 Pattern selection precedence

Per bar, per level, only one pattern fires:

1. If Pattern A conditions met → emit as Pattern A.
2. Else if B′ stop reference exists for this level → emit as Pattern B′.
3. Else if Pattern B conditions met → emit as Pattern B.
4. Else no candidate.

## 10. Stop / target rules

### 10.1 Stop (set at L1, refinable by L2)

Per pattern:

| Pattern | Stop (long) | Stop (short) |
|---|---|---|
| A | `D.BodyBottom − 5 ticks` | `D.BodyTop + 5 ticks` |
| B | `breachBar.low` | `breachBar.high` |
| B′ | `failedTrigger + 1 tick` | `failedTrigger − 1 tick` |

L2 may apply ADR clip (`stop_distance ∈ [0.30, 0.80] × ADR20`) for label stability. L1 emits raw geometry; L2 decides whether to clip.

### 10.2 First target = 100% Fibonacci

Anchor: entry candle's low → entry candle's high (for long), high → low (for short).

```
first_target_long  = entryCandle.High
first_target_short = entryCandle.Low
```

Scale out 50% at first target. (L2 sizes the half; L1 emits the price.)

### 10.3 Runner target (regime-dependent)

Per the §7.3 table:

| Regime | Runner target |
|---|---|
| Bullish+ | `entry + 2.0 × entryCandle.range` (200% Fib); stretch 2.5× when L2 confirms strong slope |
| Bullish | `entry + 1.5 × entryCandle.range` |
| Sideways | None (full exit at first target) |
| Bearish | `entry − 1.5 × entryCandle.range` |
| Bearish+ | `entry − 2.0 × entryCandle.range` |

### 10.4 Engulfing-master structural target (apr-29)

If `engulfingMasterCandle` exists and the trade direction would target its opposite extreme, emit a parallel `engulfing_target_price`:

- Long: `engulfingMasterCandle.High`
- Short: `engulfingMasterCandle.Low`

Refinement: if the 9:30 candle has already pierced past the engulfing extreme (e.g., D.Low < A.BodyBottom on a short setup where A is engulfing), shift target to the 9:30 extreme: `D.Low` (short) / `D.High` (long).

L1 emits both `target_runner_price` (Fib) and `engulfing_target_price` (structural). L2 scorer picks which is closer (first scale-out) and which is farther (runner).

### 10.5 Time flat

Hard exit at 15:00 ET for ES/NQ/GC; 14:30 ET for CL. L1 emits `session_close` event 5 min before flat. L2/L3 close any open positions.

## 11. Visual rendering

For every Candidate emitted, V3 draws on chart at the trigger bar:

| Element | Style |
|---|---|
| Entry arrow | ▲ (long) / ▼ (short), 14pt, color = regime: bright green (Bullish+), green (Bullish), gray (Sideways), red (Bearish), bright red (Bearish+) |
| Stop line | dashed red, 1pt, extends 10 bars right of entry, label `STOP` |
| First target line | dashed green, 1pt, extends 10 bars, label `T1 (100%)` |
| Runner target line | dotted green, 1pt, extends 20 bars, label `T2 (xxx%)` (only if regime has runner) |
| Engulfing-target line | dotted gold, 1pt, extends 20 bars, label `T_engulf` (only if §10.4 applies) |
| Pattern type label | small text near arrow: `[A]`, `[B]`, `[B′]` |

For every Abstain (when `ShowAbstainMarkers = true`):
- Small `×` marker at the price level
- Hover/tooltip text: `<gate>: <reason>`

All toggleable via NinjaScriptProperties (see §13). Defaults aim for low chart clutter — Abstain markers off by default.

## 12. Candidate event schema

JSON shape emitted to JSONL log + (optional) HTTP endpoint. Field order is not contractual; field presence is.

```jsonc
{
  // Identity
  "event": "candidate",
  "version": "v3.0",
  "timestamp": "2026-05-01T10:32:14-04:00",
  "symbol": "ES",
  "bar_period_minutes": 1,
  "session_id": "es-20260501",

  // §5 — level
  "level_price": 7092.25,
  "level_kind": "master_high",            // master_high | master_low | box_midpoint | engulfing_master_high | ...
  "level_origin_candle": "C",             // A | B | C | D | A_y1 | B_y1 | ... | C_y2 | D_y2
  "level_origin_volume": 18432,
  "distance_to_level_ticks": 2,
  "active_set_size": 12,                  // grew to 24 if extended once, 36 if twice

  // §6 — congestion
  "congestion_active": true,
  "congestion_tightness": -0.18,          // (high_min - low_max) / ATR15
  "congestion_window_n": 5,
  "stripe_high": 7091.00,
  "stripe_low": 7090.50,

  // §7 — regime
  "regime": "Bullish",
  "overlap_count": 1,
  "slope_200_pts": 1.8,
  "regime_locked_at": "2026-05-01T09:30:00-04:00",
  "counter_bias_flag": false,             // true if direction opposes regime bias

  // §1 — day-type and engulfment (apr-29)
  "body_overlap_AB": false,
  "body_overlap_BC": true,
  "body_overlap_CD": false,
  "large_wick_flag_A": false,
  "large_wick_flag_B": false,
  "large_wick_flag_C": true,
  "large_wick_flag_D": false,
  "engulfing_master_candle": "C",         // null if none

  // §2 — MOC
  "moc_ratio": 1.34,                      // = vol(3:30) / vol(3:00)
  "moc_color": "GREEN",                   // GREEN | ORANGE | GRAY

  // §9 — pattern
  "pattern_type": "B",                    // A | B | B_prime
  "pattern_b_penetration_pts": 3.5,       // null if not Pattern B
  "failed_trigger_level_pts": null,       // populated only if pattern_type == B_prime

  // direction + proposed geometry
  "direction": "long",
  "entry_price": 7092.50,
  "stop_price": 7079.00,
  "target_100_price": 7106.00,
  "target_runner_price": 7113.50,         // null if regime has no runner
  "engulfing_target_price": 7142.25,      // null if §10.4 doesn't apply

  // sizing proposal (regime-driven; L2 may override)
  "proposed_contracts": 2,
  "size_basis": "Normal_Bullish",

  // discretionary features (apr-29)
  "is_post_1330_counter_trend": false,
  "nine30_width_pts": 8.5,
  "morning_prevailing_direction": "up"    // sign of close(13:30) - close(09:30)
}
```

`abstain` event — minimal schema:

```jsonc
{
  "event": "abstain",
  "version": "v3.0",
  "timestamp": "...",
  "layer": "L1",
  "gate": "no_congestion",                // see §8 for gate names
  "reason": "congestion_active = false in last 5 bars",
  "recovery": "wait for congestion stripe to form",
  "context": { /* candidate-shaped fields up to point of block */ }
}
```

## 13. NinjaScriptProperties (configuration knobs)

| Property | Type | Default | Range | Purpose |
|---|---|---|---|---|
| `CongestionWindowN` | int | 5 | 3–10 | Bars in body-overlap window (§6) |
| `LevelProximityATRMult` | double | 1.0 | 0.3–3.0 | K_ticks = ATR(15) × this (§5.2) |
| `SlopeThresholdPts` | double | 0.5 | 0.0–5.0 | Flat-vs-trending threshold (§7.1) |
| `MaxPriorDaysBack` | int | 2 | 0–3 | Cap on level-set extension (§5.3) |
| `ContractsBaseLine` | int | 2 | 1–10 | "Normal" cell of §7.3 size table |
| `PatternA_GraceMinutes` | int | 0 | 0–30 | Delay before Pattern A may fire after 10:00 ET |
| `PatternBPrime_TimeoutMin` | int | 15 | 5–60 | Window for failed-trigger recycle (§9.3) |
| `ADR_StopClipEnabled` | bool | true | bool | Whether L2 clips stop to [0.30, 0.80]×ADR20 (§10.1) |
| `ShowEntryMarkers` | bool | true | bool | Visual (§11) |
| `ShowAbstainMarkers` | bool | false | bool | Visual — verbose, off by default |
| `ShowTargetLines` | bool | true | bool | Visual |
| `EmitCandidatesToHttp` | bool | true | bool | Send to L2 scorer endpoint |
| `LogJsonlPath` | string | (default per V2_5 reference) | path | JSONL session log location |
| `EngulfingTargetEnabled` | bool | true | bool | §10.4 — emit engulfing-master target line |
| `RegimeRecomputeOn2xATRMove` | bool | false | bool | If true, log regime_revision_event on extreme moves; never used to override locked regime |

## 14. Failure modes and boundary cases

| Case | L1 behavior |
|---|---|
| Bar zero / cold start (< N bars) | Abstain `gate: "warmup"` for any level approach |
| SMA200 history < 200 bars | regime defaults to `Sideways`; emit `regime_default_warning` |
| Missing master candle (e.g., holiday GlobEx) | Levels excluded from active_set; emit `level_unavailable` warning. Other 3 candles still drive setups |
| No prior 09:30 close (first day) | regime defaults to `Sideways` |
| Multiple candidates same bar | Emit all. L2 ranks. No L1 dedupe |
| Stop and entry same price (zero-width entry candle) | Abstain `gate: "degenerate_geometry"` |
| Time flat window | At 14:55 ET (14:25 CL), L1 stops emitting new candidates. At 15:00 (14:30 CL), emit `session_close` |
| HTTP endpoint unreachable | Continue emitting to JSONL only; log connection error once per session |
| In-progress bar updates (BarsInProgress=0, IsFirstTickOfBar=false) | L1 evaluates `OnBarClose` only; does not fire on intra-bar ticks |

## 15. DOM gap (Tier 1 acknowledgment)

V3 does not detect DOM defended levels. AM's apr-29 7153 long (driven by 1000-lot pull-replace pattern) will not emit as a V3 candidate. **This is a documented and accepted limitation for V3.0.**

Estimated impact: 20–30% of AM's discretionary entries are DOM-driven and will not replicate in V3. The other 70–80% should be captured by §5/§6/§7 composition.

**Tier 2 (Step 1.5):** add bar-based DOM proxies — light pre-market volume + repeated rejection at single price + volume cluster. New `dom_proxy_active` boolean feature on Candidate. Out of scope for Phase 1A spec.

**Tier 3 (deferred):** DOM-aware NT8 AddOn subscribing to Level 2 events. 4–8 weeks of engineering. Revisit only if Step 2 backtest shows residual edge in DOM-driven trades that proxies can't capture.

## 16. What's deferred (V3.1+, not in Phase 1B)

- ML scorer (L2 enhancement) — Step 3
- Tier 2 DOM proxies — Step 1.5
- 9:30 width ↔ subdued runner-target gating — pending AM's Sidekick analysis (post 2026-05-01)
- News-candle outsized-volume level registration (apr-24 §9 add) — V3.1
- Afternoon (post-13:30) counter-trend size reduction — emitted as feature in V3, applied by L2 in V3.1
- 50% midpoint scale-in (apr-24 §6) — V3.1
- F12 hotkey kill-switch via NT8 AddOn — V1.1
- Holiday calendar via parquet lookup — V1.1
- CL rule revamp (pending AM delivery) — when AM delivers

## 17. File structure

```
C:\seasonals\baiynd_autotrader\v3_rebuild_2026-05-01\
├── architecture_spec_v3.md          (THIS document)
├── README.md                        (one-page status / quick reference) [TODO]
├── reference\
│   ├── am_rules_v2_spec_link.md     (pointer to AM_rules_v2_spec.md) [TODO]
│   └── v25_lessons_learned.md       (what worked / didn't in V2_5) [TODO]
└── tests\
    ├── test_congestion_detector.py  (unit tests for §6 formula)
    ├── test_regime_classifier.py    (table tests for §7.2)
    ├── test_dynamic_level_set.py    (extension trigger tests for §5.3)
    ├── test_l1_emit_gate.py         (integration tests for §8 paths)
    └── replay_calibration.md        (Phase 1C calibration runbook)

C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\
├── AMTradeCockpitV2_5.cs            (preserved as fallback — unchanged)
└── AMTradeCockpitV3.cs              (NEW — Phase 1B implementation)

C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Strategies\
└── AMTradeStrategyV1.cs             (existing; minor signature updates for V3 candidate schema)
```

V2_5 stays running on a separate chart for compare-during-development. Cutover to V3 happens after Phase 1C calibration passes (§18).

## 18. Test plan (Phase 1C — calibration)

### 18.1 Calibration days (transcribed AM trades)

| Date | AM trades | V3 expected fires |
|---|---|---|
| 2026-04-29 | 7153 long (DOM-driven), 7172 short, 7170 short add | 1–2 fires (DOM trade NOT captured — acknowledged gap) |
| 2026-04-27 | 4 AM Europe long during sideways-up day (PrInst H exit) | 1 fire (Sideways regime, slope-up FADE, level-to-level exit) |
| 2026-04-24 | 7085 → 7092 → 7079 Pattern B walkthrough | 1 fire (Pattern B at level, congested approach) |
| 2026-04-23 | sideways-day walkthrough (multiple touches) | TBD — depends on day-type classification |

### 18.2 Pass criteria

- V3 fires on **≥ 4 of 5** AM-narrated trades on calibration days, excluding DOM-only trades
- V3 false-positive rate (fires on bars AM didn't trade) < **50%** of total fires
- Stop / target geometry matches AM's stated stops within **2 ticks**
- Zero silent-drop bugs (every bar with a level approach within K_ticks produces either Candidate or Abstain — verified by event count audit)

### 18.3 Iteration plan (when criteria fail)

If a calibration trade fires false negative (AM took it, V3 missed):
1. Identify which sub-claim blocked: log shows `Abstain{gate: ...}`. Map gate to Travel / Congestion / Regime.
2. If Travel (level not in active_set): adjust §5 — usually `LevelProximityATRMult` or `MaxPriorDaysBack`.
3. If Congestion (`gate: "no_congestion"`): adjust §6 — usually `CongestionWindowN` or accept that her trade was DOM-driven.
4. If Regime (`gate: "regime_block"`): adjust §7.2 thresholds or §7.3 direction allowance.
5. **Don't change architecture without spec revision.** Tune knobs first; if knobs can't fix, log to `am_open_questions.md` and discuss before changing the spec.

If false-positive rate exceeds 50%:
1. Review fires AM didn't take: are they consistent in some feature (low congestion_tightness? counter_bias_flag? specific level_kind)?
2. Tighten the corresponding feature threshold or move filter to L2.
3. Re-run calibration.

### 18.4 Sign-off for cutover to V3 production

After calibration passes, V3 runs side-by-side with V2_5 for **5 trading sessions** in sim/replay. Compare candidate counts, abstain reasons, and (where AM trades) whether V3 caught it. If 5-session comparison shows V3 capturing AM's actual trades at meaningfully higher rate than V2_5 with acceptable noise, V3 cuts over to live.

---

## Appendix A — Mapping V2_5 → V3 changes

| V2_5 component | V3 status |
|---|---|
| Master-candle capture | **Reused** (§4 unchanged) |
| Pattern B state machine | **Reused with refinements** (§9.2 — through-the-V, §9.3 — B′) |
| Day-type classifier (body-stack) | **Replaced** by §7 5-level regime classifier |
| MOC validation (GREEN/ORANGE/GRAY) | **Reused** as feature; size mapping moves into §7.3 |
| Sideways FADE direction | **Subsumed** into §7 — Sideways regime traded both sides per §8.2 |
| L1 emit gate ("every level interaction") | **Replaced** by §8 (proximity + congestion + regime) |
| L2 scorer (heuristic + ML stub) | **Reused** with new candidate schema (§12) |
| L3 safety gates (12 toggleable) | **Unchanged** |
| Visual rendering | **Replaced** by §11 (regime-colored arrows + target lines) |
| JSONL event format | **Versioned** to v3.0 (§12); reader must dispatch on `version` field |

## Appendix B — Open items (ask Afshin before code)

1. Confirm `CongestionWindowN = 5` default, or do you prefer 3 / 7 to start?
2. Confirm `LevelProximityATRMult = 1.0` default. Apr-29 trades: 7153 entry vs nearest level — was that within 1× ATR15 or wider? Worth checking on a real bar before locking.
3. §7.3 Bullish / Bearish "short OK at upper levels" cell: is that AM's actual behavior or my interpolation? She said in apr-29 she shorts at upper edges of sideways. Less clear for trending days. May need to flip to long-only for Bullish (and short-only for Bearish) in V3.0 and reintroduce in V3.1.
4. §7.1 `slope_threshold_pts = 0.5` — totally a guess. Real value should come from looking at historical 09:30→09:30 SMA200 deltas on ES. Tunable property, will calibrate post-build.
5. §10.3 runner targets — AM's Fib stretch is 250% in Bullish+. Worth a one-shot check that 200% / 250% match the actual entry-candle-width math on the apr-24 7085→7092 trade.
6. Visual color scheme (§11) — green/red gradients work, or do you want a different palette?

---

**Next step (Phase 1B):** once you sign off on this spec (or redline), I write `AMTradeCockpitV3.cs`. Estimated 800-1200 lines C#. I'll write it as a clean refactor of V2_5, reusing what's marked "Reused" in Appendix A.
