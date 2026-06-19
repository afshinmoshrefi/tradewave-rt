# Anne-Marie Baiynd — Level-Touch Intraday Method

Synthesized from 5 recorded sessions. Written so a future reader (human or AI) can pick up AM's method without re-reading ~2,900 lines of transcript.

## Source manifest

| File | Date | Lines | Focus |
|---|---|---|---|
| `AM_transcript_mar-6.txt` | 2026-03-06 | 1039 | Genesis; first intraday demo ~1:02:00. Candle hierarchy, measured moves, "look below and go", 30-min SMA trend, size 2-3 ES, algo rhythm. |
| `AM_transcript_apr-8.txt` | 2026-04-08 | 406 | Chart setup. Woody's pivots w/ custom banner, 50/200 **period** SMAs (not day), VWAP no bands, shaded candle boxes, 200 SMA = "most statistically significant indicator", fractals, R3/R4 exhaustion. |
| `AM_transcript_apr-9.txt` | 2026-04-09 | 580 | Mechanics Q&A. Limits only, 15k ES / 6k NQ 1-min benchmark, level-to-level exits (NOT trailing), hiken ashi momentum sign, box walkdown order, congested-day edges, Globex = 6pm–6:30pm ET. |
| `AM_transcript_apr-10.txt` | 2026-04-10 | 406 | Live TopStep combine (MEES). Limits 62/64, 8-pt / 4-pt risk, VWAP/50 convergence, prospect theory "second-prettiest girl", 5 trades/day cap. |
| `AM_transcript_apr_16.txt` | 2026-04-16 | 487 | Sidekick app validates heuristics. Renames "king candle" → **institutional candle** (3:30 ET close). MOC rule: 3:30 vol ≥ 20% above 3:00. 60-day lookback. Oil institutional = 10:00 ET. Camarillas on NQ not ES. Day-of-week gates. |

## 1. Strategy thesis

Trend-filtered mean-reversion to a structural price level, with multi-factor permission gating.

- **Macro frame**: 30-min chart decides direction (stacked SMAs: price > SMA50 > SMA200 = long-only; inverse = short-only; neither = stand down).
- **Micro entry**: on the 1-min chart, wait for price to retrace to one of the 15 structural levels and take the counter-move from there. So: bullish day, pullback to the first bullish level, buy the bounce.
- **Level ≠ signal**. Level is the **location filter** (candidate only). Confirmation is the **permission filter**: SMA stack, VWAP slope, volume vs benchmark, hiken ashi sign, institutional-candle MOC validation, pivot context. A touch without permission is skipped.
- Entries are **always limit orders**, pre-placed. Never market. Thin books (micro gold) will chew market orders.

## 2. Chart / indicator stack

On AM's setup (apr-8):

- **VWAP** — no bands. Slope and distance-from matter more than the line itself.
- **SMA 50 and SMA 200**, both **period** (bar count), not day. Drawn on 30-min *and* 1-min.
- **Woody's pivots** with a custom banner she calls "claude" — labels R1–R4 / S1–S4 on the chart.
- **Camarilla pivots** work on **NQ** but not ES (apr-16). Use selectively.
- **Shaded candle boxes** (colored overlays) for the four structural candles: 3:30 ET, 6:00 PM ET (Globex open), 4:00–4:30 AM ET (europe), 9:30 AM ET (RTH open).
- **Hiken ashi** as momentum indicator. Sign relative to zero matters (above = bull momentum, below = bear).
- **MACD** for confirmation.
- **1:30 ET candle** marked with a pink line — pullback/expansion marker.
- **Fractals** used on 1-min for micro pivots.
- **Time & sales for delta volume** — she uses MotiveWave (apr-9); volume profile varies across platforms and she treats it as unreliable.

"The 200 SMA is the most statistically significant indicator on the chart." (apr-8)

## 3. Candle hierarchy

Order matters. When boxes overlap, the *larger* box dominates — the smaller candle only matters when its range pokes outside the parent.

| Candle | Time (ET) | Role |
|---|---|---|
| **Institutional** (f.k.a. "king") | 3:30 close (MOC) | Smart-money placement for overnight. **Validated** when 3:30 volume ≥ 20% above 3:00 volume (apr-16). Oil's institutional = **10:00 ET**, not 3:30. 60-day lookback for the volume comparison. |
| Globex open | 6:00–6:30 PM | Overnight session open. |
| Midnight | 00:00 | Matters only when it pokes outside the Globex box. |
| Europe | 4:00–4:30 AM | Sets the stop-distance reference (H–L = europe width). Duplicate the box up/down for **measured-move targets**. |
| RTH open | 9:30 AM | Day's opening range. |
| 1:30 PM | 1:30 PM | Afternoon pullback/expansion candle. |

Box walkdown order for the morning plan: **3:30 → 6PM → 4AM → 9:30** (apr-9).

## 4. The 15 reference levels

Prior-day H/L/close · globex H/L · midnight midpoint · europe 4AM H/L · opening range H/L · prior 30-min H/L · VWAP · anchored VWAP (from prior institutional candle) · Woody's pivots · institutional-candle H/L.

In the V2 pipeline the trend gate and VWAP/AVWAP are treated as permissions, not limit-order destinations.

## 5. Execution rules

- **Limits only**, pre-placed at every trend-aligned, untouched, in-ADR-range level (excluding VWAP/AVWAP) after the 10:00 ET bar closes.
- **On first fill**, cancel all other resting limits.
- **Cancel remaining limits 14:30 ET** (14:00 ET for CL).
- **Flat by 15:00 ET** (14:30 ET for CL).
- **Size**: 2–3 ES contracts (mar-6). TopStep-combine demo used 1–2 MEES (apr-10).
- **Max 5 trades/day.** Some days = zero trades; that is the correct outcome (apr-10).

## 6. Exits — NOT a trailing stop

This is a frequent misread. In V2's implementation the scorer uses a 30-min SMA20 trail, but AM's taught discipline is:

- **Fixed level-to-level exits**. Entry at level A, target at level B (next structural level in the direction of the trade).
- Example (apr-10, MEES): long limit 62, target = prior candle low, stop = 8 points away.
- "Scalpers revert to zero" (apr-9) — scalping trades expect the move to fade back to origin; taking them requires tighter exits.

The 30-min SMA20 trail is a backtestable proxy for AM's discretion-based "let the winner run to the next level then reassess." It compresses the left tail of the R-distribution (all losers ≈ -1R), which inflates Sharpe — a caveat AM was given in the empirical report.

## 7. Entry patterns

- **Look above and go / look below and go** (mar-6). Fake-out reversal: price pokes just past a level to stop-run the obvious crowd, then reverses. Entry is on the reversal back through the level.
- **VWAP / 50-SMA convergence then breakout** (apr-10). When VWAP and 50-period SMA coil together, the next directional push carries.
- **Measured move via 4AM box duplication**: copy the europe-candle box up (for longs) or down (for shorts) — the projected edge is the target.
- **Post-news Fibonacci retrace** on sharp news candles.
- Avoid buying VWAP blindly — "VWAP gets retested all day; you can't just buy it" (apr-10).

## 8. Confirmation / permission filters

A level-touch is taken only when *multiple* of these agree:

- 30-min SMA stack aligned with trade direction.
- VWAP on the correct side and sloping in-direction.
- Hiken ashi sign agrees (above zero for longs, below for shorts).
- 1-min open volume in range: **~15,000 contracts ES**, **~6,000 NQ** (apr-9). Low volume = skip.
- Institutional-candle MOC validation (20% rule, apr-16).
- Pivot context — R3/R4 = exhaustion zone, fade rather than chase.

## 9. Instrument-specific notes

- **ES / NQ / CL / GC / RTY** are AM's universe. V2 runs ES, NQ, CL, GC. **Not YM.**
- **CL**: institutional candle = **10:00 ET**; flat by **14:30 ET**; cancel limits **14:00 ET**.
- **NQ**: Camarilla pivots work. ES: they don't.
- **Micro gold**: book too thin for market orders — strictly limits.
- **Dollar / CL correlation break** is a setup trigger (apr-8).

## 10. Regime diagnostics

- **Short-covering rally** detected by the *speed* of the turn — sharper, faster than a genuine trend change.
- **Congested day**: trade only the **edges** of the range (apr-9).
- **Algo rhythm**: AM reads the 1-min bars for rhythmic patterns. A rhythm break signals regime change.
- **Fallback**: when the open is unreadable, use the **9:30–10:30 ET range** as the day's reference rectangle.
- **Day-of-week probability gates** (apr-16, via Sidekick) — some setups are only edged on specific weekdays.

## 11. Risk management

- **Stop distance** = width of the 04:00 ET europe candle (H–L). V2 clips this to [0.30 × ADR20, 0.80 × ADR20]; the clip is our addition, not AM's.
- **No averaging down.** A broken level means the thesis is wrong.
- **Prospect theory framing** (Tversky & Kahneman 1979): "Go to the second-prettiest girl." Meaning — don't demand the perfect setup; take the statistically sound one that's available (apr-10).
- **Combine discipline**: walk away at daily target or after 5 trades, whichever first.

## 12. Vocabulary to preserve

| Term | Meaning |
|---|---|
| **Institutional candle** | 3:30 ET close (10:00 ET for CL). Previously "king candle." |
| **MOC-validated** | Institutional candle with 3:30 volume ≥ 20% above 3:00 volume, 60-day lookback. |
| **Mark validated** | A level confirmed by permission filters — cleared to trade. |
| **Look above/below and go** | Fake-out reversal pattern. |
| **Watering hole** | A level where price repeatedly returns — high-probability reaction zone. |
| **Pretty girl / second-prettiest girl** | Prospect-theory entry metaphor: take the good-enough setup, not the perfect one. |
| **Claude banner** | AM's custom Woody's-pivot label overlay. |
| **Sidekick** | Pattern-identification app she uses to validate heuristics empirically. |

## 13. Quotes worth preserving verbatim

- "The 200 SMA is the most statistically significant indicator on the chart." (apr-8)
- "Scalpers revert to zero." (apr-9)
- "You can't just buy VWAP — it gets retested all day." (apr-10)
- "Go to the second-prettiest girl." (apr-10, on prospect theory)
- "Some days you take zero trades. That's a win." (apr-10)

## 14. What this means for the ML pipeline (pattern_scorer_rt2)

- **Labels are baked under the europe-width [0.30, 0.80] ADR clip.** Changing the clip forces event-regeneration + relabel + retrain + holdout eval.
- **The model adds selectivity, not direction.** Direction comes from AM's trend gate, which is deterministic and upstream of M2.
- **Permission filters map to features.** Hiken ashi sign, VWAP distance/slope, SMA stack state, 1-min volume vs benchmark, pivot proximity, institutional-candle MOC flag — these are exactly the kinds of signals M2's 60-feature matrix should encode, and are the *why* behind its edge over unconditional level-touch.
- **The level-to-level exit discipline is not what M2 is trained on.** M2 scores under the SMA20 trail. Any future variant that trains on level-to-level exits is a separate model, not a parameter tweak.

---

## V2_5 implementation note

As of 2026-04-27, **AMTradeCockpitV2_5.cs** is the current production indicator for level-touch detection. **AMTradeStrategyV1.cs** is the hosting strategy implementing scoring (L2) and safety gates (L3).

The V2_5 architecture separates detection (L1), scoring (L2), and safety (L3) into distinct layers with explicit contracts. V2_4 is retained as legacy/fallback, untouched. The key design change: V2_5 emits a `candidate` event for every level interaction; decisions to take or skip are made explicitly at L2/L3 with logged `abstain` events. Nothing is dropped silently.

For the full architectural rationale, layer contracts, event schemas, and test strategy, see:
- Architect spec: `C:\seasonals\baiynd_autotrader\v25_rebuild_2026-04-27\architecture_spec_v25.md`
- AM rules with V2_5 status: `C:\seasonals\baiynd_autotrader\video transcripts\AM_rules_v2_spec.md` (§11)
- Memory files: `project_v25_architecture.md`, `feedback_fail_open_principle.md` in the project memory directory
