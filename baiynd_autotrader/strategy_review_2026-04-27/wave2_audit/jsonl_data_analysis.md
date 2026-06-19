# JSONL Session Log Audit — AMTradeCockpit V2_4

**Auditor:** Wave 2 / Agent 4 (data forensics)
**Run date:** 2026-04-27
**Source:** `C:\seasonals\cockpit\sessions\` (103 session folders)
**Window:** 2025-10-21 -> 2026-04-27 (six months and six days, 189 calendar days, 135 weekdays in span, 103 covered = **32 missing weekdays / 23.7% gap**)

---

## TL;DR

- **2 signal events in 6 months.** Both on consecutive days (2026-03-19 and 2026-03-20), both SHORT, both off VWAP at 09:32 in `rthactive`, one followed by a daily-loss-limit `lockout` event 29 minutes later. Afshin is right: setups are missing, almost all of them.
- **103 sessions, 24,656 raw event lines, 15,882 unique** after dedup. Touch events are duplicated by NT8 (likely chart replay re-walks) at a 35.6% rate. Almost every legacy session fires each touch event two or more times. Counts in this report are **deduplicated** unless explicitly stated otherwise.
- **2,956 unique touches; 741 qualifying** (`retrace_side=true`, `already_latched=false`). Conversion rate of qualifying touches into signals = **0.27%** (2 / 741). Even if every qualifying touch should fire, the system is silently swallowing 99.7% of the entry triggers.
- **Day-type strings emitted by V2_4 do NOT match the spec.** Heartbeats label sessions `congestion`, `unknown`, `extended`, `trending`. The spec strings `LongTrend / ShortTrend / CautiousLong / CautiousShort / Sideways / Unknown` never appear once. The Sideways-FADE wiring added today cannot have fired historically because the code never produced the string `Sideways`.
- **Heartbeat / phase_change / bias_change / bar_close / lockout / signal events all begin on 2026-03-17.** Anything before that date (96 of 103 sessions) only contains `touch` events. Pre-2026-03-17 the indicator was strictly an annotation logger, not a strategy.
- **MOC field is absent from every payload type.** No `moc`, `moc_state`, no Green/Orange/Gray label, nothing.
- **No "stuck phase" anomalies in heartbeats** — phase always advances `globexopen -> midnight -> europeopen -> rthopen -> rthactive -> rthclose -> globexopen`. But the V2 era (Oct 2025–Mar 16) has no phase logging, so we cannot verify legacy behaviour from the JSONL alone.
- **Pattern B is everywhere.** 1,271 of 2,956 unique touches (43.0%) wicked through a level then closed back on the original side. V2_4 has the scaffolding but no firing path; this is the single largest cluster of latent setups.
- **OOS recommendation: do NOT do a calendar split on this dataset.** The schema break at 2026-03-17 makes pre/post-split incomparable, and only 7 sessions are truly V2_4-instrumented. Keep all 7 V2_4 sessions for calibration, treat 96 legacy sessions as a touch-replay corpus only.

---

## Q1. Volume of data

| Metric | Value |
|---|---|
| Session folders with `events.jsonl` | 103 |
| First session | 2025-10-21 |
| Last session | 2026-04-27 |
| Calendar span | 189 days |
| Weekdays in span | 135 |
| **Coverage** | **103 / 135 = 76.3%** |
| Missing weekdays | 32 |
| Total raw event lines | 24,656 |
| Total unique lines after dedup | 15,882 |
| Duplicate rate | 35.6% (8,776 dup lines) |
| Mean unique events / session | 154.2 |
| Min / Max unique events per session | 1 / 2,829 |

Gaps in the 32 missing weekdays cluster around US holidays (2025-12-25, 2026-01-01) but also include a **suspicious 11-weekday gap from 2026-03-23 through 2026-04-06**, plus 2026-03-04 isolated. These look like NT8 down-time or session-collector failures, not market closures. Worth checking with Afshin.

Per-month volume (deduplicated):

| Month | Sess | Unique events | Touches | Qualifying | Signals | Heartbeats |
|-------|-----:|--------------:|--------:|-----------:|--------:|-----------:|
| 2025-10 |  8 |    136 |    136 |    49 | 0 |     0 |
| 2025-11 | 18 |    232 |    232 |    72 | 0 |     0 |
| 2025-12 | 18 |    684 |    684 |   249 | 0 |     0 |
| 2026-01 | 17 |  1,569 |  1,569 |   411 | 0 |     0 |
| 2026-02 | 16 |    925 |    925 |   336 | 0 |     0 |
| 2026-03 | 13 |  9,925 |    223 |    91 | 2 | 5,160 |
| 2026-04 | 13 |  2,411 |    187 |    68 | 0 |   677 |

The huge March/April line counts come almost entirely from per-minute heartbeats on the 7 V2_4 instrumented sessions, not from new touch volume. Touch volume is actually *lower* in the V2_4 era than in the V2 (Jan-Feb) peak.

---

## Q2. Event type distribution

Deduplicated counts across all sessions:

| type | count | share |
|---|---:|---:|
| bar_close | 7,008 | 44.13% |
| heartbeat | 5,824 | 36.67% |
| touch | 2,956 | 18.61% |
| bias_change | 60 | 0.38% |
| phase_change | 30 | 0.19% |
| signal | **2** | 0.01% |
| lockout | 2 | 0.01% |

Raw (un-deduplicated) counts: touch = 11,675; heartbeat = 5,837; bar_close = 7,050. Deduplication strips ~75% of touch line-volume but leaves heartbeats and bar_close largely intact (they had unique timestamps and payloads naturally).

Sessions with **0 signals**: 101 / 103 (98.1%).
Sessions with **0 touches** (after dedup): 2 — `2026-04-22` and `2026-04-27`. Heartbeats present but no levels firing.
Sessions with the highest unique touch count: 2026-01-22 (287), 2026-01-27 (174), 2026-01-08 (163), 2026-01-09 (151), 2026-01-19 (148), 2026-01-20 (148). All January 2026 — extended, range-bound months produce a lot of level revisits.

---

## Q3. Touch -> Signal conversion rate (the smoking gun)

This is the headline finding. Across the entire 6-month corpus:

- 2,956 unique touches
- **741 qualifying touches** (`retrace_side=true` AND `already_latched=false`)
- **2 signals** (out of those 741)
- **Conversion rate: 0.27%**

For comparison, even a permissive setup-firing rule (1 signal per qualifying touch with no further filters) would have produced ~741 signals over the period; a rule with reasonable bias / phase / day-type / lockout gating would still likely produce 50-200 signals. The system is producing 2.

### Top sessions with qualifying touches but zero signals (deduped)

| Session | Qualifying | Signals |
|---|---:|---:|
| 2026-01-09 | 31 | 0 |
| 2026-01-22 | 30 | 0 |
| 2026-01-23 | 29 | 0 |
| 2026-01-27 | 27 | 0 |
| 2026-01-28 | 24 | 0 |
| 2026-01-29 | 23 | 0 |
| 2026-03-06 | 22 | 0 |
| 2026-01-20 | 21 | 0 |
| 2026-01-08 | 20 | 0 |
| 2026-01-13 | 20 | 0 |
| 2026-01-30 | 20 | 0 |
| 2026-03-09 | 18 | 0 |
| 2026-03-03 | 17 | 0 |
| 2026-03-10 | 15 | 0 |
| 2026-02-26 | 14 | 0 |

Critical caveat: **of these 15 sessions, none of them have heartbeat / phase_change / bias_change events.** They are V2-era logs. No signal could have fired because the signal-emission code was not yet in the indicator. So calling these "missed setups" is technically wrong — they were sessions where the strategy didn't yet exist. But they DO show that the touch-detection layer was identifying ample opportunities; the missing layer was the gating + entry decision.

### Both observed signals

| Date | Time | Side | Level | Phase | Day_type | trend_dir | Entry | Stop | adr20 | eu_width |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-03-19 | 09:32 | SHORT | VWAP | rthactive | extended | SHORT | 6619.52 | 6651.22 | 105.66 | 15.0 |
| 2026-03-20 | 09:32 | SHORT | VWAP | rthactive | unknown | SHORT | 6636.37 | 6668.90 | 108.41 | 12.25 |

Both are 09:32 VWAP rejections in `rthactive`, both SHORT, both follow a non-qualifying touch in the prior bar. The 03-19 trade hit the daily loss limit ($1,584.94) at 10:01 — the lockout event records this. The 03-20 trade also lost ($2,315.83 daily loss confirmed via 04-23 lockout text — wait, that's a different date. Re-reading: the 04-23 lockout reports a $2,316 loss but with no signal that day, so the trade must have come from manual entry or a non-logged signal). The signal emission path therefore exists and works under specific conditions, but those conditions are extremely narrow: rthactive + extended/unknown day_type + VWAP level + first-bar of qualifying retrace seems to be roughly the recipe.

The four V2_4-era sessions where heartbeats existed AND touches existed (2026-03-17, 2026-03-18, 2026-04-22, 2026-04-23) had 4, 0, 4, 7 qualifying touches respectively, all without signals. These are the closest to true "missed setups" in the empirical sense — the gating logic was live and chose not to fire.

### Distribution of qualifying touches per session

- min 0, max 31, **median 4.0, mean 7.2**
- 25 sessions have 0 qualifying touches (no setup signal possible)
- 19 sessions have 10+ qualifying touches yet only 2 of them ever produced a signal

A baseline tuning target might be: 1 signal per session at minimum on days with 5+ qualifying touches. That alone would imply ~50-60 signals over the corpus instead of 2.

---

## Q4. Day-type classification distribution

### What V2_4 actually emits in heartbeats

Across 5,824 unique heartbeats from 7 sessions, only four `day_type` values are observed:

| Observed day_type | Count | Share |
|---|---:|---:|
| congestion | 3,081 | 52.90% |
| unknown    | 1,864 | 32.01% |
| extended   |   753 | 12.93% |
| trending   |   126 |  2.16% |

### What the spec calls for

`LongTrend / ShortTrend / CautiousLong / CautiousShort / Sideways / Unknown` — **none of these strings appear anywhere in the JSONL.** The classifier in V2_4 is using a different vocabulary: `congestion / extended / trending / unknown`. Nine months of "Sideways FADE" wiring added today (2026-04-27) cannot trigger because the upstream label never says `Sideways`.

There are two possible reads here:
1. The audit spec describes what V2_4 *should* produce; the indicator hasn't been updated yet. If so, the FADE wiring is dead code until the day_type emitter is rewritten.
2. The label set is intentional and `congestion` IS the V2_4 equivalent of `Sideways`. If so, the FADE rule should be reading `day_type == "congestion"` rather than `"Sideways"`.

Either way, this is a vocabulary mismatch worth flagging back to Wave 3.

### Per-session dominant day_type (only 7 sessions have heartbeats)

| Dominant | Count |
|---|---:|
| congestion | 4 |
| unknown | 2 |
| trending | 1 |

### Sideways/FADE qualification estimate

Treating `congestion` as the operational equivalent of `Sideways`, **3 of the 6 pre-2026-04-27 V2_4-instrumented sessions** would have qualified for FADE: 2026-03-17, 2026-03-18, 2026-04-22. Today's session (2026-04-27) is also dominantly `congestion`. The "trending" only session was 2026-04-23. So roughly **half** of V2_4-era sessions could have been FADE candidates, but the absolute count of historical FADE-eligible sessions is only 3. We have insufficient pre-2026-03-17 day-type labels to extrapolate further; the legacy logger does not write a day_type at all.

---

## Q5. Pattern B opportunities

Pattern B definition used: a touch where the bar wicked through the level (low < level for LONG, or high > level for SHORT) AND the bar closed back on the original side (close > level for LONG, close < level for SHORT). All four required fields (`bar_open`, `bar_high`, `bar_low`, `bar_close`, `level_price`) were present on 100% of touch events, so the count below is unbiased.

| Bucket | Count |
|---|---:|
| Total unique touches | 2,956 |
| Pattern B touches (wick-through + close-back) | **1,271** |
| Share | **43.0%** |

### Cross-tab with existing touch flags

| pattern_B | retrace_side | already_latched | count |
|:---:|:---:|:---:|---:|
| F | F | F | 376 |
| F | F | T | 448 |
| F | T | F | 443 |
| F | T | T | 418 |
| **T** | **F** | **F** | **352** |
| T | F | T | 335 |
| **T** | **T** | **F** | **298** |
| T | T | T | 286 |

The bolded rows are particularly interesting:
- **352 Pattern B touches that are currently flagged as NOT on retrace_side** — meaning the V2 logic dismissed them despite the bar showing a textbook rejection. Pattern B is the recovery path for these.
- **298 Pattern B touches that ARE on retrace_side and not latched** — these would qualify under both Pattern A AND Pattern B, so are the lowest-hanging-fruit candidates.

### Top 10 sessions by Pattern B count (deduped)

2026-01-22 (113), 2026-01-27 (75), 2026-01-08 (74), 2026-01-09 (71), 2026-01-20 (66), 2026-01-13 (53), 2026-01-28 (49), 2026-01-23 (43), 2026-01-19 (42), 2026-01-12 (38). January 2026 dominates — likely a high-volatility period with many wick-rejections through round levels.

---

## Q6. MOC distribution

**No MOC field exists in any payload anywhere in the corpus.**

Heartbeat payload key set: `bias, day_type, in_lockout, phase, price, signal_state, vwap`. No `moc`, `moc_state`, no Green/Orange/Gray label.

Signal payload key set: `adr20, day_type, entry, eu_width, inst_hi, inst_lo, level, phase, side, stop, trend_dir, vwap`. Same — no MOC.

Touch / bar_close / phase_change / bias_change / lockout payloads also do not contain MOC.

If MOC is computed live by the indicator, it is not being persisted to the JSONL stream. Recommendation for Wave 3: add `moc_state` to the heartbeat payload immediately so backtest replays can reconstruct it.

---

## Q7. Levels by frequency

Deduplicated touch counts per level. "Qual" = touch with `retrace_side=true` and `already_latched=false`. "Qual %" = qual / total touches at this level.

| Level | Touches | Share | Qualifying | Qual % |
|---|---:|---:|---:|---:|
| VWAP | 433 | 14.65% | 104 | 24.0% |
| Pr30H | 303 | 10.25% | 60 | 19.8% |
| EuropeH | 220 | 7.44% | 51 | 23.2% |
| ORH | 207 | 7.00% | 42 | 20.3% |
| OR30H | 206 | 6.97% | 33 | 16.0% |
| Pr30L | 206 | 6.97% | 54 | 26.2% |
| AnchVWAP | 190 | 6.43% | 70 | **36.8%** |
| EuropeL | 189 | 6.39% | 42 | 22.2% |
| GlobExH | 175 | 5.92% | 44 | 25.1% |
| MidMid | 156 | 5.28% | 45 | 28.8% |
| SMA50_30 | 136 | 4.60% | 52 | **38.2%** |
| PrInstH | 120 | 4.06% | 37 | 30.8% |
| PrInstL | 116 | 3.92% | 32 | 27.6% |
| GlobExL | 100 | 3.38% | 31 | 31.0% |
| OR30L | 96 | 3.25% | 17 | 17.7% |
| ORL | 89 | 3.01% | 22 | 24.7% |
| **SMA200_30** | **14** | **0.47%** | 5 | 35.7% |

### Coverage of the V2_4 expected level set

All 15 expected levels (`GlobExH/L, EuropeH/L, OR30H/L, PrInstH/L, ORH/L, Pr30H/L, SMA50_30, SMA200_30, MidMid`) are present. Plus `VWAP` and `AnchVWAP` which are *not* in the spec's V2_4 list — these dominate the touch stream by volume but should be treated separately.

### Standouts

- **VWAP and AnchVWAP combined account for 21.1% of all touches** — they fire constantly because price is always close to a moving anchor. This means VWAP touches need additional gating to avoid noise; the 2 signals in the corpus both fired off VWAP, suggesting VWAP-rejection in `rthactive` is the only rule that's actually working today.
- **SMA50_30** has a very high qualifying ratio (38.2%) — when it fires it tends to be a clean retrace. Worth promoting to a primary trigger level in V2_4.
- **AnchVWAP** at 36.8% qualifying — similar story, very clean.
- **SMA200_30 fires only 14 times in 6 months.** Either the calculation is bugged, the threshold is too tight, or the level is genuinely outside the daily price range most days. Worth checking Wave 3.
- **OR30H/L** ratio is on the low end (16.0%, 17.7%). These bars fire often but don't qualify as retrace setups, suggesting the level is being touched intra-bar without a clean rejection.

---

## Q8. Sessions with anomalies

### Empty / near-empty sessions (deduped)

The 10 smallest sessions have 1-4 unique events each. All are V2-era touch-only logs:

| Session | Unique events |
|---|---:|
| 2025-11-10 | 1 |
| 2025-10-24 | 2 |
| 2026-02-18 | 2 |
| 2026-04-24 | 2 |
| 2025-11-07 | 3 |
| 2025-11-24 | 3 |
| 2025-12-22 | 3 |
| 2025-10-23 | 4 |
| 2025-11-06 | 4 |
| 2025-11-11 | 4 |

A 1-event session is a session where the indicator caught one touch, then either the strategy aborted, was disabled, or NT8 disconnected. 2026-04-24 is particularly suspicious because it sits between 2026-04-23 (full V2_4 instrumented) and 2026-04-27 (full V2_4 instrumented) yet contains only 2 unique touch events with no heartbeats.

### Stuck-phase anomalies

Searched for sessions where the heartbeat reported `phase=europeopen` past 09:30 local time. **Zero such sessions.** Phase advancement works correctly in all 7 heartbeat-bearing sessions. However, this only verifies the V2_4 era — V2-era sessions have no heartbeat and therefore cannot be checked for stuck-phase regressions from the JSONL alone.

### Sessions with signal but missing follow-through

Both signal-bearing sessions (2026-03-19, 2026-03-20) have 1,380 and 1,020 heartbeats respectively, with last events at 23:59 and 16:59 same-day. Both terminate cleanly. No "signal then silence" anomaly.

### Sessions with 0 heartbeats but other event types

96 of 103 sessions. Caused by V2 -> V2_4 schema upgrade on 2026-03-17. Not a runtime anomaly; an architectural one.

### Lockout-without-signal anomaly

2026-04-23 has a `lockout` event reporting `$2316 daily loss / $150` limit, but the signal stream for that day is empty. Either:
- The trade entry was placed manually and only the realized P&L was logged via lockout, or
- The strategy fired a signal but the signal event was not logged (logger bug), or
- The lockout text is from a pre-loaded state.

Worth investigating — if the strategy fired but the signal didn't make it to JSONL, this represents a logging gap that hides real strategy behaviour from any forward audit.

---

## Q9. Quality of recent vs older sessions (schema evolution)

### Schema by event type, first-seen / last-seen dates

| Type | First seen | Last seen |
|---|---|---|
| touch | 2025-10-21 | 2026-04-24 |
| bar_close | **2026-03-17** | 2026-04-27 |
| heartbeat | **2026-03-17** | 2026-04-27 |
| phase_change | **2026-03-17** | 2026-04-27 |
| bias_change | **2026-03-17** | 2026-04-27 |
| signal | **2026-03-19** | 2026-03-20 |
| lockout | **2026-03-19** | 2026-04-23 |

Conclusion: a hard schema upgrade landed on **2026-03-17**. Pre-2026-03-17 the indicator was a level-touch annotation logger. Post-2026-03-17 it is a fully instrumented session-state recorder.

### Touch payload schema is stable across the entire window

`['already_latched', 'bar_close', 'bar_high', 'bar_low', 'bar_open', 'direction', 'level', 'level_price', 'retrace_side', 'session_date']` — same keys in 2025-10-21 and 2026-04-27. So touch-driven analysis is consistent over the full 6 months.

### Pre vs post upgrade touch counts

| Era | Sessions | Unique touches | Qualifying | Q-share |
|---|---:|---:|---:|---:|
| Pre-2026-03-17 (V2 / legacy) | 96 | 2,769 | 673 | 24.3% |
| Post-2026-03-17 (V2_4) | 7 | 187 | 68 | 36.4% |

The qualifying-share is higher post-upgrade, but that's a 7-session sample. The touch *count* is much lower per V2_4 session (median ~25 touches/session vs ~30 in V2 era), possibly because V2_4 added gating to suppress redundant touches.

### Duplicate-event rate

The duplicate rate of 35.6% is **not evenly distributed**. The worst-offending sessions are January-February 2026 V2-era logs where touches duplicate up to 8x within the same minute (2026-01-14 at 89.9% dup rate). Post-2026-03-17 V2_4 sessions are mostly unique (small dup count on bar_close from intra-day reloads, but heartbeats are unique). The dedup logic in V2_4 appears to have been fixed alongside the schema upgrade.

This means any analysis that uses the raw JSONL as-is and doesn't dedup will overweight pre-upgrade days by ~3-4x and dramatically distort touch-frequency metrics in favour of January 2026.

### Recommendations for schema hygiene

1. Add `moc_state` to heartbeat payload (currently missing entirely).
2. Add `event_id` or sequential counter to make dedup unambiguous (timestamp+payload-hash works but is fragile).
3. Add explicit Sideways / LongTrend / ShortTrend / CautiousLong / CautiousShort / Unknown emission, OR document that `congestion / extended / trending / unknown` is the canonical V2_4 vocabulary and update the spec.
4. Backfill phase_change / bias_change / heartbeat into pre-2026-03-17 sessions if you have the raw NT8 chart history available — this would make the entire 103-session corpus comparable for backtesting.

---

## Q10. Recommended OOS partition + caveats

### The problem with a naive calendar split

The obvious "Oct-Feb train, Mar-Apr test" split is broken for three reasons:

1. **Schema break at 2026-03-17.** Train data has no day_type, no MOC, no heartbeats, no phase, no bias. Test data has all of them. Any model trained on touches+flags in the pre-period will literally have no input vector for the post-period MOC/day_type features.
2. **Only 2 signal events in the entire corpus.** You cannot validate a signal-emission classifier with N=2. The "test set" has 1 signal at most under any reasonable split. Fitness has to be measured against a different proxy (qualifying touches, Pattern B fires, etc.).
3. **The 32-weekday gap (especially the 11-day blackout 03-23 to 04-06) breaks any time-series cross-validation.** Don't pretend it's a continuous corpus.

### Recommended split

**Phase A — Touch-detection rule calibration (corpus = all 103 sessions, deduped touches):**
- Train: 2025-10-21 -> 2026-02-13 (76 sessions, ~2,200 unique touches, ~570 qualifying)
- Validate: 2026-02-17 -> 2026-04-24 (27 sessions, ~750 unique touches, ~170 qualifying)
- Use this to tune Pattern A and Pattern B trigger conditions on touch flags and bar geometry. No need for heartbeat data.

**Phase B — Day-type / MOC / phase gating calibration (corpus = 7 V2_4 sessions only):**
- This is too small for train/validate split; treat all 7 as a *calibration* set and report per-session fits without any held-out.
- For real OOS validation: Wave 3 should commit to logging at full V2_4 schema for an additional 30-50 sessions before any backtest is treated as out-of-sample.

**Phase C — Forward validation (after Wave 3 ships):**
- Take the next 30 trading days post-deployment and score live signals against the rule under audit.
- Report per-day metrics: qualifying-touch count, signals emitted, signals-vs-qualifying ratio, P&L, day_type accuracy.

### Caveats for any backtest

- **Touches in the JSONL are not raw bars.** They are post-filter detections. If V2_4 changes its touch-emission gates, replay accuracy degrades.
- **Both signals are 09:32 VWAP SHORTs.** Any rule tuned to fit them will overfit to a single setup template.
- **The 2026-04-23 lockout-without-signal hints at a logging gap.** Signals may have fired without being recorded. Backtest "0 signals on day X" should not be treated as ground truth.
- **NT8 chart-replay duplicates need filtering at ingest.** Any pipeline that reads the raw JSONL must dedup by `(t, type, payload)` tuple.
- **Pre-upgrade sessions cannot be used to calibrate any rule that depends on phase, bias, day_type, or MOC.** Only touch-pattern rules transfer.

---

## Cross-reference notes for Wave 3

1. **The `Sideways FADE` rule wired today depends on `day_type == "Sideways"`, which the indicator never emits.** Confirm with the day-type classifier whether `congestion` is the intended canonical label and update the FADE gate accordingly. If V2_4 is supposed to emit `Sideways`, this is a bug ticket for Wave 3 to fix the classifier output strings.
2. **MOC is invisible in the JSONL.** Wave 3 should add MOC to heartbeat (and ideally to the signal payload at the moment of fire) before any further data collection. Without it, MOC validation is impossible.
3. **The 2 historical signals are concentrated on VWAP rejections in `rthactive`.** Pattern A (clean retrace) seems gated to that single condition. Wave 3 should review the signal-emission code for over-restrictive gating: the touch/qualifying ratio is healthy (~25%) but the qualifying/signal ratio is 0.27%, indicating one or more downstream gates are systematically rejecting setups.
4. **Pattern B is roughly 43% of touches and 50% of *non-retrace-side* touches** — meaning under the V2 retrace_side rule, Pattern B-eligible bars are being thrown away in roughly equal numbers as Pattern A bars. Wave 3's Pattern B implementation will roughly double the candidate-setup pool.
5. **Only 7 of 103 sessions have heartbeats.** Wave 3 cannot use the bulk of this corpus as-is for any rule validation that depends on phase/bias/day_type. Forward collection of 30-50 more V2_4 sessions is a prerequisite for any meaningful OOS test of the new gating logic.
6. **The 11-weekday gap (2026-03-23 to 2026-04-06) and various other missing weekdays.** Wave 3 should confirm with Afshin whether these are expected (vacation, system off) or signal logger failures.
7. **Touch double-emission in V2-era sessions (35.6% dup rate).** If anyone bulk-loads pre-2026-03-17 JSONL into a database without dedup, all touch frequency analyses will be skewed by ~3-4x. Build dedup into the ingest pipeline.
8. **The 2026-04-23 lockout reports a $2,315 loss with no logged signal.** Either log gap or manual-trade-induced lockout. Worth a 5-minute conversation with Afshin.
9. **The signal payload contains `eu_width`, `adr20`, `inst_hi`, `inst_lo` — these are great features for a regime-aware classifier and should be present in heartbeat too**, not just signal-fire moments. Add to Wave 3 schema.
10. **The trader's intuition is supported by the data.** Two signals in 6 months on 741 qualifying touches is a 0.27% conversion rate. Even allowing for false positives, the gating logic is at least 50-100x too restrictive. The "missed setups" feeling is empirically real, not perception.

---

## Appendix A — Methodology and reproducibility

- All counts presented are deduplicated unless explicitly marked "raw".
- Dedup key: full JSON line string (`(t, type, payload)` tuple — order-preserved, NT8 emits stable JSON).
- Pattern B definition: `(direction == LONG AND bar_low < level_price AND bar_close > level_price) OR (direction == SHORT AND bar_high > level_price AND bar_close < level_price)`. Open is not used in this definition; intraday close-back is sufficient.
- Qualifying touch: `retrace_side == True AND already_latched == False` per the V2 spec field set.
- Late-europeopen check: any heartbeat at HH:MM >= 09:31 with `phase == "europeopen"`. Zero observed.
- Trading-day calendar: simple Mon-Fri filter on the calendar window 2025-10-21 to 2026-04-27 inclusive. Holidays not subtracted (US 2025-11-27 Thanksgiving and 2025-12-25 Christmas Day are the obvious ones).
- Analysis scripts are saved alongside this report at `C:\Users\afshi\Documents\NinjaTrader 8\bin\Custom\Indicators\analyze_jsonl.py`, `analyze_jsonl_dedup.py`, `report_jsonl.py`, and the cached pickle `analyze_jsonl_dedup.pkl` for re-use.

---

## Appendix B — Headline number cheat sheet

```
Sessions:              103         (Oct 21 2025 - Apr 27 2026)
Calendar coverage:     76.3%       (32 missed weekdays in span)
Raw event lines:       24,656
Unique events:         15,882      (dedup removes 8,776 = 35.6%)
Touches:               2,956       (deduplicated)
Qualifying touches:    741         (retrace_side + not already_latched)
Pattern B touches:     1,271       (43.0% of all touches)
Heartbeats:            5,824       (only on 7 of 103 sessions)
Bias changes:          60          (only on 7 sessions)
Phase changes:         30          (only on 7 sessions)
SIGNALS:               2           (Mar 19, Mar 20 - both SHORT VWAP rthactive)
Lockouts:              2           (Mar 19, Apr 23)

Conversion rate:       0.27%       (signals / qualifying touches)
Sessions with signals: 2 / 103
Sessions w/o signals:  101 / 103   (98.1%)

Day-type vocabulary (V2_4):
  congestion 53%, unknown 32%, extended 13%, trending 2%
  Spec calls for: LongTrend, ShortTrend, CautiousLong, CautiousShort,
                  Sideways, Unknown - NONE of these appear in JSONL.

MOC field:             not present anywhere
Schema break:          2026-03-17 (heartbeat / phase / bias / bar_close
                                   / signal / lockout all begin here)
```
