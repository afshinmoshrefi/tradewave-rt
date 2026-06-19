"""Seed admin accounts + starter knowledge for the coach.

Knowledge is loaded from versioned markdown files in `knowledge_seed/` (each with a
small front-matter header). These were distilled from Anne-Marie's method docs and her
documented trading-psychology themes - the starting point she then enriches via the
admin tool. Idempotent: safe to re-run.
"""
import os
import re
import secrets as pysecrets
from datetime import datetime
from pathlib import Path

from .extensions import db
from .models import KnowledgeEntry, Post, User
from .rag import rebuild_index

SEED_DIR = Path(__file__).resolve().parent.parent / "knowledge_seed"

# Friendly display names for the known operator/partner; everyone else derives one.
SEED_NAMES = {
    "afshin@tradewave.ai": "Afshin Moshrefi",
    "anne-marie@thetradingbook.com": "Anne-Marie Baiynd",
}

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def seed_role_for(email, config):
    """Role for a seeded account, from config (the single source of truth for who is
    operator vs partner). ADMIN_EMAILS -> admin, PARTNER_EMAILS -> partner, else member.
    Anne-Marie is in PARTNER_EMAILS, so she seeds as 'partner' - her workspace, NOT
    the Operations room with member PII and the role tool."""
    email = (email or "").lower()
    if email in config.get("ADMIN_EMAILS", set()):
        return "admin"
    if email in config.get("PARTNER_EMAILS", set()):
        return "partner"
    return "member"


def _parse_seed_file(path):
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    meta, body = {}, text
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        body = m.group(2).strip()
    return meta, body


def _ensure_user(email, name, role, password):
    """Idempotently create a privileged account. Returns (user, created, note).
    No shared static password is ever baked in: an explicit SEED_PASSWORD (env) is
    used if set, otherwise a unique random password is generated per account and
    surfaced once at the end of the seed for the operator to capture and rotate.
    For an already-existing account whose role differs from config, returns a note
    rather than silently flipping a deliberate ops_set_role change."""
    email = email.lower()
    user = User.query.filter_by(email=email).first()
    if user:
        note = (None if user.role == role else
                f"exists with role='{user.role}' (config says '{role}') - fix via ops_set_role")
        return user, False, note
    user = User(email=email, display_name=name, role=role,
                accepted_ai_disclaimer=True, accepted_at=datetime.utcnow())
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user, True, None


def run_seed(app):
    created_users = []   # (email, role, password-or-None-when-from-env)
    role_notes = []      # (email, drift note)
    seed_pw_env = os.environ.get("SEED_PASSWORD", "").strip()

    # Who to seed AND their role come straight from config (ADMIN_EMAILS /
    # PARTNER_EMAILS), the single source of truth. Anne-Marie is in PARTNER_EMAILS,
    # so she is seeded 'partner', never site operator.
    targets, seen = [], set()
    for email in sorted(app.config.get("ADMIN_EMAILS", set())):
        targets.append((email, SEED_NAMES.get(email, email.split("@")[0].title()), "admin"))
        seen.add(email)
    for email in sorted(app.config.get("PARTNER_EMAILS", set())):
        if email in seen:
            continue
        targets.append((email, SEED_NAMES.get(email, email.split("@")[0].title()), "partner"))
        seen.add(email)

    am_user = None
    for email, name, role in targets:
        pw = seed_pw_env or pysecrets.token_urlsafe(12)
        user, created, note = _ensure_user(email, name, role, pw)
        if role == "partner":
            am_user = user
        if created:
            created_users.append((email, role, None if seed_pw_env else pw))
        if note:
            role_notes.append((email, note))

    # Knowledge from seed files (idempotent by title).
    added = 0
    for path in sorted(SEED_DIR.glob("*.md")):
        meta, body = _parse_seed_file(path)
        title = meta.get("title") or path.stem.replace("_", " ").title()
        if KnowledgeEntry.query.filter_by(title=title).first():
            continue
        def _int(v, d=0):
            try:
                return int(v)
            except (TypeError, ValueError):
                return d
        # The optional beginner "in plain English" layer is stored after a delimiter
        # in the file body so the canonical seed reproduces it on a fresh box.
        content, _, plain = body.partition("\n<!--PLAIN-->\n")
        db.session.add(KnowledgeEntry(
            title=title,
            category=(meta.get("category") or "method"),
            source=meta.get("source") or path.name,
            content=content.strip(),
            plain=plain.strip(),
            stage=_int(meta.get("stage"), 0),
            stage_order=_int(meta.get("stage_order"), 0),
            kind=(meta.get("kind") or "lesson"),
            published=True,
        ))
        added += 1
    db.session.commit()

    # A welcome post on the member feed.
    if not Post.query.filter_by(title="Welcome to TradeWave Realtime").first():
        db.session.add(Post(
            title="Welcome to TradeWave Realtime",
            body=(
                "I'm glad you're here. This is where we slow the game down and trade with "
                "structure and a clear head.\n\n"
                "Start with your **coach** - ask it about the 30-minute trend gate, the "
                "failed-retest entry, or what to do when you feel yourself wanting to chase. "
                "Then browse the **Strategy Library** for the method in writing.\n\n"
                "Remember the first rule: *a zero-trade day is a win.* Trade small, trade "
                "with the trend, and let the level come to you. - Anne-Marie"
            ),
            published=True,
            author_id=am_user.id if am_user else None,
        ))
        db.session.commit()

    n = rebuild_index(app)

    print("=" * 60)
    print("TradeWave Realtime - seed complete")
    print(f"  Knowledge entries added : {added}")
    print(f"  Retrieval chunks indexed: {n}")
    if created_users:
        print("  Accounts created (capture passwords now - shown once):")
        for email, role, pw in created_users:
            shown = pw if pw else "(set via SEED_PASSWORD env)"
            print(f"    - {email}  [{role}]  password: {shown}")
        print("  Rotate these after first login.")
    else:
        print("  Privileged accounts     : already existed (unchanged)")
    for email, note in role_notes:
        print(f"  WARNING - role drift    : {email} {note}")
    print("=" * 60)
