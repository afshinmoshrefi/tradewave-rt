# Manual Playbook V2 — Use Wave 3 Version As-Is

**Author:** Final Synthesis Writer (Agent 22 of 22)
**Date:** 2026-04-27

---

## Use this file: `wave3_synthesis/manual_playbook.md`

The Wave 3 Manual Playbook is comprehensive, beginner-readable, and aligned with the strategy synthesis and improvement roadmap. **Use it as-is.** Do not rewrite.

It covers, in 487 lines:
- Section 1 — Morning One-Pager (the print-and-tape-to-monitor checklist): body stack, MOC, 200-SMA slope, verdict line, today's mode, manual levels (1:30 PM candle, Woody's pivots), the 5-question Go/No-Go decision.
- Section 2 — RTH Open observation window (9:30-10:00 ET): volume check, OR range note, the "do not enter on the open break" rule.
- Section 3 — 10:00 ET start of trading: pre-placing limits, the lobster buffet rule (no chasing), one-position-at-a-time discipline.
- Section 4 — Trade management: level-to-level exit doctrine (overriding V2_4's incorrect SMA20 trail), stop placement at entry candle width, the 50% midpoint add-rule, cancel-others on first fill.
- Section 5 — Cancel/exit cutoffs: 14:30 cancel all unfilled, 15:00 hard close.
- Section 6 — Daily discipline: 5-trade cap, kill-switch, two-loser walk-away, zero-trade-days are wins.
- Section 7 — Conflict-resolution protocol when indicator says X but chart says Y.
- Section 8 — The anti-doubt rubric: 30-second 5-question checklist before placing any limit.
- Section 9 — Deeper context (read weekly, not daily): why each rule exists.
- Section 10 — Quick-reference cheat sheet.
- Appendix — what V2_4 shows vs what Afshin must supply manually.

It correctly captures AM's verbatim rules where they matter:
- "I don't trail any stops. I go level A to level B and I'm done." (apr-9)
- "trailing stops are terrible." (apr-9)
- "I never use market orders. Always limit orders." (apr-9)
- "the buffet is open tomorrow." (apr-9)
- "every day, by a couple of minutes." (mar-6, on the 1:30 PM candle)
- "usually my max max is five." (apr-10)
- "Some days you take zero trades. That's a win." (paraphrased from the discipline rules)

It correctly flags the gaps Afshin must compensate for manually:
- Pattern B (look-below-and-fail) not wired in V2_4 — the playbook tells him how to identify it visually.
- Fibonacci extension levels (100/150/200%) not drawn — the playbook tells him to use NT8's Fibonacci tool anchored on the entry candle.
- 1:30 PM candle and Woody's pivots not displayed — the playbook tells him to mark them manually.
- TREND mode SMA20 trail in V2_4 contradicts AM's level-to-level exit — the playbook explicitly tells him to override the indicator and exit at the next structural level.
- STAGE button does not submit orders — the playbook walks through the manual ChartTrader submission step.

The playbook is consistent with everything in `strategy_synthesis.md` and `improvement_roadmap.md`. There are no inconsistencies that require a rewrite. The Wave 3 author did the work correctly.

---

## Single Note for Updates

When V2_4 ships the P0 indicator fixes (Pattern B wiring, two-sided FADE, level-to-level exit doctrine, day-type vocabulary fix), the playbook will need a small revision to:

1. Update Section 4.1 to remove the "the indicator currently uses SMA20 trail; you override it manually" workaround once the indicator's level-to-level exit is wired (per roadmap C-13).

2. Update the Appendix table to mark Pattern B as "wired" once C-10 is complete.

3. Update Section 7.2 (FADE direction) to describe the two-sided behavior once C-12 is wired.

These are minor edits, on the order of 30 minutes of work. Schedule for the end of the 30-day sprint when the P0 fixes have been verified in the running system.

---

*End of manual_playbook_v2.md.*
