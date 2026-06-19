---
title: Micro contracts vs full contracts (MES and MNQ vs ES and NQ)
category: glossary
stage: 0
stage_order: 0
kind: reference
source: CME contract specifications; her micros-before-minis rule from the transcripts
---
The micro contracts are the same markets at one tenth the size. Same chart, same candles, same levels, same method - only the dollars per point change. The day's map applies identically to both.

The numbers that matter:
- ES (E-mini S&P 500): one point = $50; one tick (0.25) = $12.50.
- MES (Micro E-mini S&P 500): one point = $5; one tick (0.25) = $1.25. Exactly one tenth of ES.
- NQ (E-mini Nasdaq-100): one point = $20; one tick (0.25) = $5.
- MNQ (Micro E-mini Nasdaq-100): one point = $2; one tick (0.25) = $0.50. Exactly one tenth of NQ.

What that means in practice: a 10 point stop-out costs $100 on one MES versus $1,000 on one ES. Margin requirements scale down roughly the same way, about one tenth.

Two honest trade-offs of micros:
- Commissions and fees are proportionally heavier relative to the dollars at stake, so a micro trader pays a higher percentage cost per trade. That is the tuition for learning on real money at survivable size, and it is worth paying.
- Liquidity in MES and MNQ is deep enough for learning-size orders at the levels; full contracts have the deepest book.

How this fits her teaching: trade micros before minis, and one mini before three. Start on MES (or MNQ) until the process is consistent and calm - wait for the level, enter with a limit, honor the stop, exit level to level - over many trades, not a lucky week. Evaluation and prop accounts, and any day with an unclear bias, are micro territory regardless of experience. Stepping up size is the last step, never the first.
