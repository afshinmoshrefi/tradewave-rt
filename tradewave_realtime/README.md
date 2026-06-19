# TradeWave Realtime - V1

The real-time / intraday arm of the **TradeWave** umbrella, built with **Anne-Marie Baiynd**.
V1 is a working product (no payments yet) to demo to Anne-Marie. See [`SPEC.md`](SPEC.md).

## What's in V1
- Public **landing** ("TradeWave Realtime, with Anne-Marie Baiynd") + free signup.
- The **"Anne-Marie" coach** - an AI coach (Claude + RAG) trained on her method + trading
  psychology. Evergreen (V1); educational only, never gives trade calls. Persistent AI
  disclosure + one-time acknowledgment + disclaimers.
- **Strategy library** - the curated method/psychology the coach is built on.
- **Member feed** - posts Anne-Marie publishes.
- **Admin tool** (for Anne-Marie) - curate the coach's knowledge + publish to the feed.

## Run it
```bash
cd /home/flask/tradewave_realtime
# secrets live at /etc/tradewave_realtime/secrets.env (root:root, 0600):
sudo install -m 0600 .env.example /etc/tradewave_realtime/secrets.env  # then edit it
./run.sh                      # seeds + starts on http://0.0.0.0:5001
```
Or manually:
```bash
source .venv/bin/activate
export FLASK_APP=run.py
flask seed                    # creates admins + seeds knowledge (idempotent)
python run.py                 # http://localhost:5001
```

## The coach: Claude vs demo mode
- **With `ANTHROPIC_TOKEN` set** (in `/etc/tradewave_realtime/secrets.env`): the coach uses
  Claude (`CLAUDE_MODEL`, default `claude-haiku-4-5`) grounded in the knowledge base.
- **Without a token**: the coach runs in **retrieval-only demo mode** - it still answers in
  Anne-Marie's voice from the curated knowledge, so the whole app is demoable today. Drop in
  a token and `systemctl restart tradewave-rt` to get the full conversational coach. No code change.

## Admin / demo accounts
`flask seed` creates two admins (password printed on seed, default `tradewave2026`):
- `anne-marie@thetradingbook.com` - Anne-Marie's admin login
- `afshin@tradewave.ai` - your admin login

Sign up with any other email to experience it as a member. Admins (emails in `ADMIN_EMAILS`)
get the **Admin** tab.

## Tech
Flask + SQLAlchemy (SQLite at `data/tradewave_rt.db`), session auth (WorkOS-swappable),
pure-Python TF-IDF retriever (vector-DB-swappable), Anthropic Claude for the coach. Templates
in `app/templates`, styles in `app/static`. Production: `gunicorn wsgi:app` behind nginx.

## Roadmap (post-V1)
V2 = today-aware coach (daily-briefing ingestion). Then Stripe tiers, the signal-only
NinjaTrader indicator, ML scoring, Discord. WorkOS + Postgres + nginx/gunicorn are the
production swaps.
