# AMTradeCockpit - status for the TradeWave Realtime offering

> **Public name DECIDED 2026-06-12: "The AM Map"** (listing: "TradeWave AM Map -
> Anne-Marie Baiynd's daily levels, live on your chart"). Her initials + the
> morning + matches the site's "the map" language; her name lives in the
> subtitle (license-clean, wind-down-safe). Afshin will rename if she objects
> (floating it at the Jun 12 meeting). AMTradeCockpit stays the internal
> class/file name until the next-week indicator project.

> 2026-06-12. `AMTradeCockpitV2_6.cs` (3,753 lines, schema v26.0) placed here by
> Afshin (his copy stays in /home/afshin). This is the shipping source for the
> indicator that is INCLUDED with RT membership (decided 2026-06-12; pricing and
> licensing model: `/home/flask/product/V1_SITE_DESIGN.md` section 8, item 9).

## What v2.6 already does (verified by source inspection)

- Computes her method LOCALLY from whatever data feed runs in NinjaTrader - no
  dependency on our servers (confirms the architecture facts of 2026-06-12: no
  CME redistribution exposure, real-time on the member's own feed).
- All master candles as boxes: Globex open, midnight, Europe 4 AM, US open,
  institutional/MOC, plus the 1:30 PM watch candle (Close130) and multi-day
  master-candle revisits (her 2-day lookback).
- MOC volume validation states: Pending / Green / Orange / Gray.
- 30-minute AND 1-minute 50/200 SMAs; day-phase awareness (PreGlobEx, GlobExOpen,
  Midnight, EuropeOpen, ...).
- Candidate/touch tracking: per-session stats, unique + high-value levels touched,
  pre-touch watch labels.
- Writes local `box_capture` JSONL events on every master-candle capture - a
  natural future hook for the trade/level sync (the events already exist; the
  phone-home can ship them).
- ZERO network code today (no HttpClient/WebClient/urls anywhere).

## What RT v1 adds to it (the build, per the decided design)

1. License phone-home on load: ONE call returning license status (membership key
   + machine binding, offline grace of a few days) + method config (candle
   windows/thresholds, server-driven so method fixes never need a DLL push) +
   current version (shows "update available in your member area").
2. Backend endpoint for (1) in the RT app (small; pairs with the key on the
   member account page).
3. Later, founding window+: "Ask my coach about this trade" right-click send;
   then opt-in end-of-session trade sync (completed trades ONLY - the bright
   line; see V1_SITE_DESIGN section 8 item 12).

Note: v3 rebuild folder exists here from May; v2.6 is the copy Afshin provided
as current. If v3 is actually the live build, swap this file and say so.
