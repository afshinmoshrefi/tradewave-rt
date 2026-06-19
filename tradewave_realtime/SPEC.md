# TradeWave Realtime - V1 Product Spec

*Owner: Afshin Moshrefi (Tara Data Research LLC). Partner: Anne-Marie Baiynd. Status: V1 build. Date: 2026-06-03.*

TradeWave Realtime ("TradeWave RT") is the real-time / intraday arm of the **TradeWave** umbrella, built around trader-educator **Anne-Marie Baiynd**'s intraday futures method and trading psychology. V1 is a **working product with no payments yet** - a real, clickable site Afshin can show Anne-Marie to win her fully in; billing is added later for launch.

---

## 1. Locked decisions (D1–D7)

| # | Decision | Choice |
|---|----------|--------|
| **D1** | Chatbot identity | Named **"Anne-Marie"**, speaks in her first-person coaching voice/method, but carries a **persistent label that it's an AI coach trained on Anne-Marie's strategy** (not the real person) + first-use acknowledgment + educational/not-advice disclaimers. AM has approved use of her name. |
| **D2** | V1 scope | **Real, functional product, NO payments.** Demo the full experience to win her in; add Stripe later. |
| **D3** | Chatbot staging | **V1 = evergreen coach** (method + psychology, timeless). **V2 = today-aware** (ingests her daily briefing). **Future** = indicator, ML scoring, Discord, payments. |
| **D4** | Her helper/admin tool (in V1) | (a) **Knowledge curation** - review/correct/approve the coach's knowledge; (b) **Publish-to-subscribers** - post written lessons/updates to a member feed. |
| **D5** | Access model | **Public "TradeWave Realtime" landing + free signup** unlocks chat + feed. Unlistable until she's on board, then doubles as the free funnel. |
| **D6** | Knowledge source | **Seed from existing method docs now**, enrich her **psychology** (her signature) via her admin tool + her book *The Trading Book* + approved coaching Q&As. |
| **D7** | Tech foundation | **Reuse the TradeWave stack** - Flask + nginx on the `tradewave-rt` box, WorkOS-compatible auth (local email/password in V1, swappable), a DB, and the coach on **Claude + RAG** over the curated knowledge base with guardrails. |

---

## 2. What V1 contains

**Public (no login):**
- **Landing page** - "TradeWave Realtime, with Anne-Marie Baiynd." The hook, what you get, who she is, clear *AI-coach* disclosure, free-signup CTA, disclaimers.
- **Legal** - disclaimer, terms, privacy (educational / not advice / risk-of-loss).

**Member area (free account):**
- **Anne-Marie coach** - chat with the AI coach. Persistent "AI trained on Anne-Marie's strategy" label, one-time acknowledgment before first use, disclaimers in footer. Answers are grounded (RAG) in the curated knowledge base and **never give individualized buy/sell calls**.
- **Feed** - Anne-Marie's published posts/lessons (newest first).
- **Strategy library** - the readable, evergreen method + psychology entries the coach is built on (the published knowledge).
- **Account** - profile, disclaimer status, sign out.

**Admin (Anne-Marie / Afshin):**
- **Knowledge manager** - create/edit/publish knowledge entries (category: method / psychology / rules / faq). Editing rebuilds the coach's retrieval index. This is how she makes the coach sound like *her*.
- **Post composer** - write/publish posts to the member feed.
- **Dashboard** - counts + quick links.

**Not in V1 (deferred):** payments/tiers, the daily-briefing→knowledge pipeline (V2, today-aware), the live indicator, ML scoring, Discord.

---

## 3. The coach - behavior & guardrails

- **Persona:** warm, direct, process-over-profit; uses her signature ideas ("go level to level," "the buffet is open tomorrow," "a zero-trade day is a win," "second-prettiest girl," limits-only, no trailing stops, trade with the 30-min 200/50 SMA, the institutional candle).
- **Hard rules (system prompt + UI):**
  1. Educational coach, **not** a financial adviser or signal service. **Never** tells the user to buy/sell a specific instrument now, never gives a live entry/stop/target, never predicts prices. Redirects "should I buy X now?" into teaching the method + the trader's own process.
  2. **Grounded** in retrieved knowledge; avoids inventing specific rules/numbers it isn't given (anti-hallucination - bounded to the knowledge base).
  3. Keeps psychology + risk discipline central; reminds of risk.
  4. Always an AI ("I'm the AI coach trained on Anne-Marie's method, not Anne-Marie herself"); discloses on request.
- **Model:** Claude (default `claude-haiku-4-5` - cheap/fast, matches the EOD chatbot; configurable via `CLAUDE_MODEL`). **Fallback:** with no API token, the coach replies in a retrieval-only "demo mode" (returns the most relevant knowledge in her voice + a demo note) so the app is always demoable.

---

## 4. Architecture

- **Flask app factory** (`app/`), Blueprints: `auth`, `main`, `chat`, `admin`.
- **DB:** SQLAlchemy + SQLite for V1 (`data/tradewave_rt.db`); models map cleanly to Postgres later.
- **Auth:** session-based email/password (werkzeug hashing), `role ∈ {member, admin}`, admin emails via config. **Swap point:** WorkOS/AuthKit for production (one TradeWave identity across EOD + RT).
- **RAG:** pure-Python TF-IDF retriever over chunked published knowledge (no external embedding service needed in V1); rebuilt on knowledge change. Swap point: vector DB + embeddings later.
- **LLM:** `app/llm.py` - Anthropic client when `ANTHROPIC_API_KEY` is set, else deterministic retrieval fallback.
- **Models:** `User`, `KnowledgeEntry`, `Post`, `ChatThread`, `ChatMessage`.

## 5. Run / config

- Dev: `./run.sh` (venv + `flask run` on `:5001`).
- Env (`.env`): `SECRET_KEY`, `ANTHROPIC_API_KEY` (optional), `CLAUDE_MODEL`, `ADMIN_EMAILS`.
- Seed: `flask seed` creates admin accounts (Anne-Marie + Afshin) and ingests starter knowledge (method from `baiynd_autotrader` docs + a curated psychology seed).

## 6. Path to V2+

Today-aware coach (briefing ingestion), Stripe tiers (Apprentice/Trader/Inner Circle), the signal-only NinjaTrader indicator, ML scoring of her setups, Discord with the 24/7 bot - all build on this foundation. WorkOS + Postgres + nginx/gunicorn are the production swaps.
