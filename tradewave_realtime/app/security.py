"""Auth helpers: session login + access decorators.

V1 uses simple session-based email/password auth. Swap point: WorkOS/AuthKit for
production so one TradeWave identity spans EOD + RT.
"""
from functools import wraps

from flask import flash, g, redirect, request, session, url_for

from .models import User


def login_user(user):
    session.clear()
    session["user_id"] = user.id


def logout_user():
    session.clear()


def current_user():
    if "user_id" not in session:
        return None
    if getattr(g, "_cached_user", None) is None:
        g._cached_user = db_get_user(session["user_id"])
    return g._cached_user


def db_get_user(uid):
    return User.query.get(uid)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Please sign in to continue.", "info")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """Workspace access: the operator OR Anne-Marie (partner role)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        u = current_user()
        if u is None:
            return redirect(url_for("auth.login", next=request.path))
        if not u.is_staff:
            flash("That area is for Anne-Marie & the TradeWave team.", "warn")
            return redirect(url_for("main.dashboard"))
        return view(*args, **kwargs)
    return wrapped


def operator_required(view):
    """Operations access: the site operator only."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        u = current_user()
        if u is None:
            return redirect(url_for("auth.login", next=request.path))
        if not u.is_admin:
            flash("That area is for the site operator.", "warn")
            return redirect(url_for("admin.dashboard" if u.is_staff else "main.dashboard"))
        return view(*args, **kwargs)
    return wrapped


def disclaimer_required(view):
    """Gate the coach behind the one-time AI-disclosure acknowledgment."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        u = current_user()
        if u is None:
            return redirect(url_for("auth.login", next=request.path))
        if not u.accepted_ai_disclaimer:
            return redirect(url_for("auth.welcome", next=request.path))
        return view(*args, **kwargs)
    return wrapped
