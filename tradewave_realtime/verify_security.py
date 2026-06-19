"""Regression guard for the launch security/infra fixes. Run:
    .venv/bin/python verify_security.py

Covers: open-redirect hardening, signup never self-grants a privileged role, the
WorkOS email_verified gate, seed role derivation (Anne-Marie = partner), session
cookie + URL-scheme hardening, the SQLite durability pragmas, and the 500 handler.
"""
import sys

from app import create_app, auth
from app.extensions import db
from app.models import User
from app.seed import seed_role_for

P, F = [], []
def ck(n, c):
    (P if c else F).append(n)
    print(("  ok  " if c else "  FAIL") + " " + n)

app = create_app()


def _purge_user(email):
    """Delete a test user and every row that references it (FK is now enforced,
    so children must go first)."""
    from sqlalchemy import inspect, text
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        if not u:
            return
        uid = u.id
        insp = inspect(db.engine)
        for t in insp.get_table_names():
            if t == "users":
                continue
            cols = {c["name"] for c in insp.get_columns(t)}
            if "user_id" in cols:
                db.session.execute(
                    text(f"DELETE FROM {t} WHERE user_id = :uid"), {"uid": uid})
        db.session.delete(u)
        db.session.commit()


# ---------- open redirect (_safe_next) ----------
with app.test_request_context("/?next=/app/coach"):
    ck("safe_next keeps a same-site path", auth._safe_next() == "/app/coach")
with app.test_request_context("/?next=//evil.com/x"):
    ck("safe_next rejects protocol-relative //", auth._safe_next() != "//evil.com/x")
with app.test_request_context("/?next=/\\evil.com"):
    ck("safe_next rejects backslash /\\", "evil.com" not in auth._safe_next())
with app.test_request_context("/?next=https://evil.com"):
    ck("safe_next rejects absolute URL", "evil.com" not in auth._safe_next())

# ---------- seed role derivation ----------
with app.app_context():
    ck("seed: Anne-Marie -> partner",
       seed_role_for("anne-marie@thetradingbook.com", app.config) == "partner")
    ck("seed: Afshin -> admin",
       seed_role_for("afshin@tradewave.ai", app.config) == "admin")
    ck("seed: stranger -> member",
       seed_role_for("someone@nowhere.com", app.config) == "member")
    # no shared static password constant lingers in the module
    import app.seed as seedmod
    ck("seed: no hardcoded shared password constant",
       not hasattr(seedmod, "DEFAULT_ADMIN_PW"))

# ---------- cookie + scheme hardening ----------
ck("cookie HTTPONLY on", app.config.get("SESSION_COOKIE_HTTPONLY") is True)
ck("cookie SAMESITE Lax", app.config.get("SESSION_COOKIE_SAMESITE") == "Lax")
ck("cookie SECURE on by default", app.config.get("SESSION_COOKIE_SECURE") is True)
ck("URL scheme https", app.config.get("PREFERRED_URL_SCHEME") == "https")

# ---------- SQLite durability pragmas (set on every connection) ----------
with app.app_context():
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        with db.engine.connect() as c:
            jm = c.exec_driver_sql("PRAGMA journal_mode").scalar()
            fk = c.exec_driver_sql("PRAGMA foreign_keys").scalar()
            bt = c.exec_driver_sql("PRAGMA busy_timeout").scalar()
        ck("sqlite journal_mode=WAL", str(jm).lower() == "wal")
        ck("sqlite foreign_keys ON", int(fk) == 1)
        ck("sqlite busy_timeout>=5000", int(bt) >= 5000)
    else:
        ck("sqlite pragmas (skipped: non-sqlite URI)", True)

# ---------- 500 handler registered ----------
ck("500 error handler registered",
   bool(app.error_handler_spec.get(None, {}).get(500)))
ck("404 error handler still registered",
   bool(app.error_handler_spec.get(None, {}).get(404)))

# ---------- signup never self-grants a privileged role ----------
# Even when the typed email is in ADMIN_EMAILS, self-service signup -> member.
test_email = "verify_sec_signup@example.com"
_purge_user(test_email)
orig_admins = set(app.config["ADMIN_EMAILS"])
app.config["ADMIN_EMAILS"] = orig_admins | {test_email}
try:
    client = app.test_client()
    client.post("/signup", data={"email": test_email, "display_name": "Sec Test",
                                 "password": "password123"})
    with app.app_context():
        u = User.query.filter_by(email=test_email).first()
        ck("signup with an admin-listed email STILL creates a member",
           u is not None and u.role == "member")
finally:
    app.config["ADMIN_EMAILS"] = orig_admins
    _purge_user(test_email)

# ---------- WorkOS callback requires a verified email ----------
app.config["WORKOS_CLIENT_ID"] = "test_client"
app.config["WORKOS_API_KEY"] = "test_key"
unverified_email = "verify_sec_workos@example.com"

def _fake_authenticate(verified):
    def _inner(_code):
        return {"id": "wo_verify_test", "email": unverified_email,
                "first_name": "Sec", "last_name": "Test", "email_verified": verified}
    return _inner

_purge_user(unverified_email)

# unverified -> rejected, no account created
auth._workos_authenticate = _fake_authenticate(False)
client = app.test_client()
with client.session_transaction() as s:
    s["workos_state"] = "st1"
client.get("/auth/callback?code=c1&state=st1")
with app.app_context():
    u = User.query.filter_by(email=unverified_email).first()
    ck("WorkOS unverified email -> no account minted", u is None)

# verified -> account created, as a plain member (email not in any privileged set)
auth._workos_authenticate = _fake_authenticate(True)
client = app.test_client()
with client.session_transaction() as s:
    s["workos_state"] = "st2"
client.get("/auth/callback?code=c2&state=st2")
with app.app_context():
    u = User.query.filter_by(email=unverified_email).first()
    ck("WorkOS verified email -> account created as member",
       u is not None and u.role == "member")
_purge_user(unverified_email)

# ---------- foreign_keys=ON: knowledge_delete detaches child rows (no FK 500) ----------
from flask import render_template, url_for
from app.models import KnowledgeEntry, UserLesson, DeferredQuestion

with app.app_context():
    admin = User.query.filter_by(role="admin").first()
    admin_id = admin.id
    old = KnowledgeEntry.query.filter_by(title="__sec_fk_test__").first()
    if old:
        DeferredQuestion.query.filter_by(answered_entry_id=old.id).update(
            {"answered_entry_id": None}, synchronize_session=False)
        UserLesson.query.filter_by(entry_id=old.id).delete(synchronize_session=False)
        db.session.delete(old)
        db.session.commit()
    e = KnowledgeEntry(title="__sec_fk_test__", category="method",
                       content="x", source="test", published=True)
    db.session.add(e)
    db.session.commit()
    eid = e.id
    db.session.add(UserLesson(user_id=admin_id, entry_id=eid))
    dq = DeferredQuestion(user_id=admin_id, question="q?", answered=True,
                          answered_entry_id=eid)
    db.session.add(dq)
    db.session.commit()
    dq_id = dq.id
    with app.test_request_context():
        del_path = url_for("admin.knowledge_delete", entry_id=eid)

client = app.test_client()
with client.session_transaction() as s:
    s["user_id"] = admin_id
resp = client.post(del_path)
with app.app_context():
    gone = KnowledgeEntry.query.get(eid) is None
    lessons_gone = UserLesson.query.filter_by(entry_id=eid).count() == 0
    dq2 = DeferredQuestion.query.get(dq_id)
    ck("knowledge_delete with child rows does not 500 (FK-safe)",
       resp.status_code in (301, 302, 303) and gone)
    ck("knowledge_delete drops orphan lesson-progress rows", lessons_gone)
    ck("knowledge_delete keeps the member question, unlinked",
       dq2 is not None and dq2.answered_entry_id is None)
    if dq2:
        db.session.delete(dq2)
        db.session.commit()

# ---------- 500 page is double-fault safe even when the DB (current_user) is down ----------
import app.security as security_mod
_orig_cu = security_mod.current_user
def _boom(*a, **k):
    raise RuntimeError("simulated DB failure")
security_mod.current_user = _boom
try:
    with app.test_request_context("/"):
        html = render_template("errors/500.html")
    ck("500 page renders even when current_user() raises (no double-fault)",
       "500" in html)
finally:
    security_mod.current_user = _orig_cu

print(f"\n{len(P)} passed, {len(F)} failed")
if F:
    print("FAILED:", ", ".join(F))
sys.exit(1 if F else 0)
