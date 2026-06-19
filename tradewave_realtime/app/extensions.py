"""Shared extensions."""
import sqlite3

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _harden_sqlite(dbapi_connection, _record):
    """Set the durability/concurrency pragmas on every SQLite connection so they
    hold on any box (a fresh deploy or a restore), not only because WAL files
    happen to exist. No-op for non-SQLite engines (e.g. a future Postgres)."""
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()
