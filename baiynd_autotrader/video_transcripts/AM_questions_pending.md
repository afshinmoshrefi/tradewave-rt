# Questions for Anne-Marie — Round 4 (post screenshots + Gemini doc, 2026-04-24)

The apr-24 video answered Round 2 blockers. The screenshots + Gemini ThinkScript resolved Round 3 ambiguities. What's left is mostly low-priority nuance plus one new question raised by the Gemini doc itself.

---

## RESOLVED post-screenshots

- ✅ Pattern B mechanic is **single-bar** breach-and-fail (one 1-min bar with `low < level` and `close >= level`). Confirmed by screenshot 4 + AM verbatim. Entry = breach bar's high; stop = breach bar's low.
- ✅ Fibonacci anchor is **entry-candle low → high** (long; flip for short). 100% = top of entry candle. 150%/200% = runner targets per 200-SMA slope.
- ✅ MOC `0.80–1.00` band is **GRAY** (reduced size). AM verbatim: *"8 to 1, it'll stay gray. Stay gray."*
- ✅ "Two of three" sticky case = nested bodies (4 AM inside Globex inside 3:30). Treat as sideways for V2_4 MVP. Optional Pattern B at 9:30 edge.

---

## LOW-PRIORITY OPEN ITEMS

**1. 200 SMA flat case for news-candle wick.** Rule is: 200 up → lower wick = support; 200 down → upper wick = resistance. What about flat 200?

**2. Body-stacking tolerance.** Strict no-overlap (`body_bottom_upper > body_top_lower`) or tick-based tolerance? MVP uses strict.

**3. CL revamp.** You said you'd revisit. No urgency — MVP uses ES-style timing.

**4. Day-of-week stats in Gemini code (NEW question).** Your Gemini ThinkScript hardcodes:
   - Mon = 52%, Tue = **78%**, Wed = 61%, Thu = 45%, Fri = **71%**
   - At threshold 65, FULL-size triggers on **Tuesday AND Friday**.
   - But you verbally said *"Fridays are more bullish than ANY other day of the week"* and *"This is the only place that it says go full size on Fridays."*
   - **Tuesday is HIGHER than Friday in your own code.**
   - Are these stats backtested or did Gemini hallucinate them? Should V2_4 use the Gemini table at all, or just log day-of-week as an ML feature?

**5. AVWAP on the chart (NEW question).** Screenshot 2 shows what appears to be an anchored VWAP line. Earlier you said you don't really use AVWAP — is the line on your chart from a separate indicator that's just decorative, or is it part of your trade decisions on certain days?

**6. The IB midpoint (50% line) as a level.** Gemini's code plots `(ib_high + ib_low) / 2` as a dashed gray line — your "50% line" for adds and stop-tightening. Confirm we should expose this as a tradable level on the chart at 10:00 ET (after the 9:30 candle closes).

---

## SCREENSHOTS RECEIVED (2026-04-24)

Thank you — all 4 screenshots + the Gemini ThinkScript are in `C:\seasonals\baiynd_autotrader\screenshots\`. They unblocked the implementation spec significantly. No additional screenshots needed at this time.

---

## CAUTIOUS MODE + 2-OF-3 (still tabled)

- **Cautious mode exact size / stop widening** — you said table it, discretionary.
- **2-of-3 partial satisfaction** — tabled. apr-24 added "failed bounce at 9:30 in sticky cases" but flagged as discretionary. MVP treats as sideways.

These stay deferred. ML layer handles the nuance.
