"""Configuration for TradeWave Realtime (V1)."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Secrets live outside the app directory, in /etc. systemd injects them via
# EnvironmentFile; this dotenv load covers manual runs (flask seed / python run.py).
# A local .env is honored only as a dev fallback when the /etc file is absent.
SECRETS_FILE = Path("/etc/tradewave_realtime/secrets.env")
load_dotenv(SECRETS_FILE if SECRETS_FILE.exists() else BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    # Session-cookie hardening for an authenticated, payment-handling app. Secure is
    # on by default (the app is served over the https tunnel); set SESSION_COOKIE_SECURE=0
    # only for local http dev. ProxyFix lets Flask see the forwarded https scheme.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "1") != "0"
    # So url_for(_external=True) builds correct https URLs for Stripe success/cancel/
    # portal and the WorkOS redirect_uri behind the tunnel. SERVER_NAME is left unset
    # unless pinned via env (setting it wrong breaks routing); PREFERRED_URL_SCHEME +
    # ProxyFix(x_host) already yield the right scheme/host.
    PREFERRED_URL_SCHEME = "https"
    SERVER_NAME = os.environ.get("SERVER_NAME", "").strip() or None

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'tradewave_rt.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite under gunicorn -w2 --threads8 (up to 16 concurrent writers): give the
    # driver a real busy-wait so concurrent writes wait instead of throwing
    # "database is locked". WAL/synchronous/foreign_keys pragmas are set per-connection
    # in extensions.py so they hold on any box. (No-op for a future Postgres URL.)
    if SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 15}}

    # LLM - canonical secret is ANTHROPIC_TOKEN (consistent with the other apps);
    # ANTHROPIC_API_KEY is still accepted as a fallback.
    ANTHROPIC_TOKEN = (os.environ.get("ANTHROPIC_TOKEN")
                       or os.environ.get("ANTHROPIC_API_KEY", "")).strip()
    # Surface-level model split (decided 2026-06-10): member-facing conversation
    # runs on Sonnet (the centerpiece deserves the better emotional register and
    # profile-aware coaching); mechanical jobs (extraction, summaries) stay on
    # Haiku. ~$1-2/member/month at typical usage with the shared cached prefix.
    CHAT_MODEL = os.environ.get("CHAT_MODEL", "claude-sonnet-4-6").strip()
    CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5").strip()

    # Role assignment on signup. ADMIN = the site operator (Afshin): everything.
    # PARTNER = Anne-Marie: her workspace (teach, answers, insights, schedule,
    # knowledge) but not operations.
    ADMIN_EMAILS = {
        e.strip().lower()
        for e in os.environ.get("ADMIN_EMAILS", "afshin@tradewave.ai").split(",")
        if e.strip()
    }
    PARTNER_EMAILS = {
        e.strip().lower()
        for e in os.environ.get(
            "PARTNER_EMAILS", "anne-marie@thetradingbook.com").split(",")
        if e.strip()
    }

    # WorkOS AuthKit - the shared TradeWave identity (same application as EOD).
    # When WORKOS_CLIENT_ID is set, login/signup route through AuthKit; the local
    # email/password forms remain as a dev fallback only.
    WORKOS_CLIENT_ID = os.environ.get("WORKOS_CLIENT_ID", "").strip()
    WORKOS_API_KEY = os.environ.get("WORKOS_API_KEY", "").strip()
    WORKOS_AUTHKIT_DOMAIN = os.environ.get("WORKOS_AUTHKIT_DOMAIN", "").strip().rstrip("/")

    # Stripe - RT keeps its own products (product_line=rt) so revenue stays cleanly
    # separable for the monthly Anne-Marie statement.
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "").strip()
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    # Pin the Stripe API version so webhook/retrieve payload shapes stay stable even
    # if the shared account's default version drifts. Default matches the installed
    # stripe lib (15.x -> "2026-05-27.dahlia", where current_period_end moved onto the
    # subscription item); billing.py reads both shapes defensively regardless.
    STRIPE_API_VERSION = os.environ.get("STRIPE_API_VERSION", "2026-05-27.dahlia").strip()
    # Flip at launch: when True, member pages require an active subscription.
    BILLING_REQUIRED = os.environ.get("BILLING_REQUIRED", "0") == "1"

    # Email (Resend): transactional + proactive coach emails. EMAIL_FROM must
    # use a domain verified in the Resend dashboard.
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
    EMAIL_FROM = os.environ.get(
        "EMAIL_FROM", "TradeWave Realtime <coach@tradewave.ai>").strip()

    # Discord: the member room. Bot token + server id arrive when Afshin
    # creates the application (see the setup checklist).
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    DISCORD_GUILD_ID = int(os.environ.get("DISCORD_GUILD_ID", "0") or 0)

    # Market data: EODHD for history/backfill, the TradeWave keyprovider quote
    # service for live candle capture (pushes to /api/ingest/candle).
    EOD_TOKEN = os.environ.get("EOD_TOKEN", "").strip()
    LEVELS_INGEST_TOKEN = os.environ.get("LEVELS_INGEST_TOKEN", "").strip()
    # The TradeWave realtime quote service on keyprovider (candle boundary snapshots).
    KEYPROVIDER_LEVELS_URL = os.environ.get(
        "KEYPROVIDER_LEVELS_URL", "http://104.238.214.253:7671").strip().rstrip("/")
    INSTRUMENTS = {
        "ES": {"eodhd": "ES.COMM", "name": "E-mini S&P 500"},
        "NQ": {"eodhd": "NQ.COMM", "name": "E-mini Nasdaq-100"},
    }

    # Branding
    BRAND = "TradeWave Realtime"
    PARTNER = "Anne-Marie Baiynd"
    COACH_NAME = "Anne-Marie"
    COACH_LABEL = "AI coach trained on Anne-Marie Baiynd's strategy"
    PORT = int(os.environ.get("PORT", "5001"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.ANTHROPIC_TOKEN)
