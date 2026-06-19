"""TradeWave Realtime application factory."""
import markdown as md
from flask import Flask, g
from markupsafe import Markup

from config import Config
from .extensions import db


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object())

    # Behind the Cloudflare tunnel / a reverse proxy: trust forwarded proto + host so
    # url_for() builds https URLs and the session cookie is treated as secure.
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)

    # Blueprints
    from .auth import bp as auth_bp
    from .main import bp as main_bp
    from .chat import bp as chat_bp
    from .admin import bp as admin_bp
    from .ingest import bp as ingest_bp
    from .mentor import bp as mentor_bp
    from .billing import bp as billing_bp
    from .trades import bp as trades_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ingest_bp)
    app.register_blueprint(mentor_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(trades_bp)

    _register_template_helpers(app)
    _register_cli(app)
    _register_errors(app)

    @app.before_request
    def _reset_user_cache():
        g._cached_user = None

    with app.app_context():
        # Both gunicorn workers run this at boot; serialize the schema DDL with a
        # cross-process file lock so create_all() + the ALTER micro-migrations can't
        # collide on first deploy. Whoever loses the race finds the columns already
        # present (the migrations are idempotent) and no-ops.
        def _boot_schema():
            db.create_all()
            _run_micro_migrations(app)
        _with_boot_lock(_boot_schema)
        from .rag import rebuild_index
        try:
            rebuild_index(app)  # per-process in-memory index; no DDL, no lock needed
        except Exception as exc:  # pragma: no cover
            app.logger.warning("Index build deferred: %s", exc)

    return app


def _with_boot_lock(fn):
    """Run fn while holding an exclusive cross-process lock (Linux flock)."""
    import fcntl
    import tempfile
    from pathlib import Path
    lock_path = Path(tempfile.gettempdir()) / "tradewave_rt_boot.lock"
    with open(lock_path, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fn()
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _run_micro_migrations(app):
    """Idempotent ALTERs for columns added after a table already existed (SQLite).
    Postgres later gets real migrations; this keeps dev moving."""
    from sqlalchemy import inspect, text
    added = {
        "users": [("workos_user_id", "VARCHAR(64)"),
                  ("stripe_customer_id", "VARCHAR(64)"),
                  ("discord_user_id", "VARCHAR(32)"),
                  ("discord_link_code", "VARCHAR(12)"),
                  ("last_active_at", "DATETIME")],
        "user_lessons": [("viewed_at", "DATETIME"), ("done_at", "DATETIME")],
        "knowledge_entries": [("stage", "INTEGER NOT NULL DEFAULT 0"),
                              ("stage_order", "INTEGER NOT NULL DEFAULT 0"),
                              ("kind", "VARCHAR(12) NOT NULL DEFAULT 'lesson'"),
                              ("provenance", "VARCHAR(16) NOT NULL DEFAULT 'team_inference'"),
                              ("status", "VARCHAR(12) NOT NULL DEFAULT 'approved'"),
                              ("source_quote", "TEXT NOT NULL DEFAULT ''"),
                              ("plain", "TEXT NOT NULL DEFAULT ''")],
        "posts": [("kind", "VARCHAR(12) NOT NULL DEFAULT 'post'")],
        "subscriptions": [("past_due_since", "DATETIME")],
        "market_candles": [("capture_open", "FLOAT"), ("capture_close", "FLOAT"),
                           ("recon_drift", "FLOAT")],
        "chat_messages": [("rating", "INTEGER NOT NULL DEFAULT 0"),
                          ("reviewed", "BOOLEAN NOT NULL DEFAULT 0"),
                          ("sanitized", "TEXT")],
        "user_profiles": [("coaching_summary", "TEXT NOT NULL DEFAULT ''"),
                          ("summarized_upto", "INTEGER NOT NULL DEFAULT 0"),
                          ("summary_updated_at", "DATETIME")],
    }
    insp = inspect(db.engine)
    with db.engine.begin() as conn:
        for table, cols in added.items():
            if table not in insp.get_table_names():
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    app.logger.info("migrated: %s.%s", table, name)
    # done_at became nullable (viewed-but-not-done rows); SQLite can't ALTER a
    # column's NOT NULL, so rebuild user_lessons in place if it is still NOT NULL.
    if "user_lessons" in insp.get_table_names():
        cols = {c["name"]: c for c in insp.get_columns("user_lessons")}
        if cols.get("done_at") and not cols["done_at"]["nullable"]:
            with db.engine.begin() as conn:
                conn.execute(text(
                    "CREATE TABLE user_lessons_new (id INTEGER PRIMARY KEY, "
                    "user_id INTEGER NOT NULL, entry_id INTEGER NOT NULL, "
                    "done_at DATETIME, viewed_at DATETIME, "
                    "UNIQUE(user_id, entry_id))"))
                conn.execute(text(
                    "INSERT INTO user_lessons_new (id, user_id, entry_id, done_at, viewed_at) "
                    "SELECT id, user_id, entry_id, done_at, "
                    "COALESCE(viewed_at, done_at) FROM user_lessons"))
                conn.execute(text("DROP TABLE user_lessons"))
                conn.execute(text("ALTER TABLE user_lessons_new RENAME TO user_lessons"))
            app.logger.info("rebuilt user_lessons (done_at now nullable)")


def _register_template_helpers(app):
    @app.template_filter("md")
    def render_md(text):
        return Markup(md.markdown(text or "", extensions=["extra", "sane_lists", "nl2br"]))

    @app.context_processor
    def inject_globals():
        import os
        from .security import current_user
        from . import persona
        cfg = app.config
        _css = os.path.join(app.static_folder, "css", "styles.css")
        asset_v = int(os.path.getmtime(_css)) if os.path.exists(_css) else 0
        # current_user() hits the DB. This context processor runs for EVERY render,
        # including the error pages - so a 500 caused by a locked/broken DB must not
        # re-throw here, or the error page itself 500s (a raw traceback to a member).
        try:
            user = current_user()
        except Exception:
            user = None
        return {
            "ASSET_V": asset_v,
            "BRAND": cfg["BRAND"],
            "PARTNER": cfg["PARTNER"],
            "COACH_NAME": cfg["COACH_NAME"],
            "COACH_LABEL": cfg["COACH_LABEL"],
            "AI_DISCLOSURE": persona.AI_DISCLOSURE,
            "RISK_DISCLAIMER": persona.RISK_DISCLAIMER,
            "LLM_ENABLED": bool(cfg.get("ANTHROPIC_TOKEN")),
            "WORKOS_ENABLED": bool(cfg.get("WORKOS_CLIENT_ID") and cfg.get("WORKOS_API_KEY")),
            "BILLING_ENABLED": bool(cfg.get("STRIPE_SECRET_KEY")),
            "current_user": user,
        }


def _register_cli(app):
    @app.cli.command("seed")
    def seed_command():
        """Create admin accounts and ingest starter knowledge."""
        from .seed import run_seed
        run_seed(app)

    @app.cli.command("reindex")
    def reindex_command():
        from .rag import rebuild_index
        n = rebuild_index(app)
        print(f"Reindexed {n} knowledge chunks.")

    import click

    @app.cli.command("levels-backfill")
    @click.option("--days", default=12, show_default=True)
    def levels_backfill(days):
        """Pull 30m bar history from EODHD into the bar store."""
        from .marketdata import fetch_intraday_bars
        for instrument in app.config["INSTRUMENTS"]:
            n = fetch_intraday_bars(instrument, days=days)
            print(f"{instrument}: {n} new bars")

    @app.cli.command("billing-init")
    def billing_init():
        """Idempotently create the RT product + founding prices in Stripe."""
        from .billing import billing_enabled, ensure_products
        if not billing_enabled():
            print("STRIPE_SECRET_KEY not configured.")
            return
        for lookup, price_id in ensure_products().items():
            print(f"{lookup}: {price_id}")

    @app.cli.command("email-test")
    @click.argument("address")
    def email_test(address):
        """Send the welcome email to ADDRESS (tests the Resend wiring)."""
        from .models import User
        from .notify import email_enabled, send_welcome
        if not email_enabled():
            print("RESEND_API_KEY not set - add it to secrets.env first.")
            return
        u = User.query.filter_by(email=address).first()
        if u is None:
            u = User(email=address, role="member")
            ok = False
            try:
                from .notify import send_welcome as sw
                ok = sw(u)  # not persisted; ledger write will fail silently
            except Exception as exc:
                print("send failed:", exc)
            print("sent:", ok)
            return
        print("sent:", send_welcome(u))

    @app.cli.command("levels-build")
    @click.option("--date", "date_str", default=None,
                  help="Session date YYYY-MM-DD (default: latest session)")
    def levels_build(date_str):
        """Build the Daily Level Map for every configured instrument."""
        from datetime import date as _date
        from .levels import build_map, direction_sentences
        session = _date.fromisoformat(date_str) if date_str else None
        for instrument in app.config["INSTRUMENTS"]:
            row = build_map(instrument, session)
            print(f"\n{instrument} {row.session_date} [{row.status}]")
            for s in direction_sentences(row.payload):
                print(f"  - {s}")
            print(f"  levels: {len(row.payload.get('levels', []))}")

    @app.cli.command("levels-sync")
    @click.option("--backfill/--no-backfill", default=None,
                  help="Force or skip the EODHD history pull (default: hourly)")
    def levels_sync(backfill):
        """The 15-minute heartbeat: pull keyprovider captures, hourly EODHD
        history, rebuild the maps. Run by the systemd timer."""
        from datetime import datetime
        from .levels import build_map
        from .marketdata import fetch_intraday_bars, fetch_keyprovider_levels
        try:
            n = fetch_keyprovider_levels()
            print(f"keyprovider: {n} capture candles")
        except Exception as exc:
            print(f"keyprovider pull failed (continuing): {exc}")
        if backfill is None:
            backfill = datetime.utcnow().minute < 15
        if backfill:
            for instrument in app.config["INSTRUMENTS"]:
                try:
                    n = fetch_intraday_bars(instrument, days=3)
                    print(f"eodhd {instrument}: {n} new bars")
                except Exception as exc:
                    print(f"eodhd {instrument} failed (continuing): {exc}")
        for instrument in app.config["INSTRUMENTS"]:
            row = build_map(instrument)
            print(f"{instrument} {row.session_date} [{row.status}]")

    @app.cli.command("lifecycle-tick")
    def lifecycle_tick_cmd():
        """Daily lifecycle pass: re-engage drifting members + Sunday weekend touch.
        Run by the tradewave-rt-lifecycle systemd timer."""
        from .notify import lifecycle_tick
        result = lifecycle_tick(app)
        print(f"lifecycle: {result}")


def _register_errors(app):
    from flask import render_template

    @app.errorhandler(404)
    def not_found(_):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(exc):
        # A "database is locked" or any uncaught exception now renders a branded page
        # instead of a raw Werkzeug traceback to a paying member.
        app.logger.exception("unhandled 500: %s", exc)
        # The 500 is often the DB itself - clear the failed session so the error
        # page's own queries can run, and fall back to a static page if even
        # rendering throws (so the error handler can never itself 500).
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            return render_template("errors/500.html"), 500
        except Exception:
            app.logger.exception("500 page render failed; serving static fallback")
            return (
                "<!doctype html><meta charset=utf-8><title>Something went wrong</title>"
                "<div style='font-family:system-ui;text-align:center;padding:80px'>"
                "<h1>500</h1><p>Something hiccuped on our end. It's logged - please "
                "try again in a moment.</p></div>"
            ), 500
