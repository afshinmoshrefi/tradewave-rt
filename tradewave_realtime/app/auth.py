"""Authentication & the one-time AI-disclosure acknowledgment.

When WorkOS is configured (WORKOS_CLIENT_ID set), sign-in/sign-up route through
AuthKit - the shared TradeWave identity spanning EOD + RT. Existing local accounts
merge by email on first WorkOS login. The local email/password forms remain as a
dev fallback so the seeded demo accounts keep working until launch.
"""
import json
import re
import secrets as pysecrets
import urllib.parse
import urllib.request
from datetime import datetime

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)

from .extensions import db
from .models import User
from .security import current_user, login_required, login_user, logout_user

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def workos_enabled():
    return bool(current_app.config.get("WORKOS_CLIENT_ID")
                and current_app.config.get("WORKOS_API_KEY"))


@bp.route("/auth/workos")
def workos_start():
    """Send the user to AuthKit (hosted sign-in/sign-up for the TradeWave identity)."""
    if not workos_enabled():
        flash("Single sign-on isn't configured yet - use the form below.", "warn")
        return redirect(url_for("auth.login"))
    state = pysecrets.token_urlsafe(24)
    session["workos_state"] = state
    session["workos_next"] = _safe_next()
    qs = {
        "client_id": current_app.config["WORKOS_CLIENT_ID"],
        "redirect_uri": url_for("auth.workos_callback", _external=True),
        "response_type": "code",
        "provider": "authkit",
        "state": state,
    }
    # Open AuthKit on the right screen: signup page asks for sign-up, login for sign-in.
    hint = request.args.get("screen_hint")
    if hint in ("sign-up", "sign-in"):
        qs["screen_hint"] = hint
    params = urllib.parse.urlencode(qs)
    return redirect(f"https://api.workos.com/user_management/authorize?{params}")


@bp.route("/auth/callback")
def workos_callback():
    if not workos_enabled():
        return redirect(url_for("auth.login"))
    error = request.args.get("error")
    if error:
        flash(f"Sign-in was cancelled or failed ({error}). Try again.", "warn")
        return redirect(url_for("auth.login"))
    code = request.args.get("code")
    state = request.args.get("state")
    if not code or state != session.pop("workos_state", None):
        flash("Sign-in could not be verified - please try again.", "warn")
        return redirect(url_for("auth.login"))
    try:
        wo_user = _workos_authenticate(code)
    except Exception as exc:
        current_app.logger.warning("WorkOS authenticate failed: %s", exc)
        flash("Sign-in failed - please try again.", "warn")
        return redirect(url_for("auth.login"))

    email = (wo_user.get("email") or "").strip().lower()
    if not email:
        flash("Your login did not include an email address.", "warn")
        return redirect(url_for("auth.login"))

    # A returning WorkOS identity (matched by its stable id) is already trusted.
    # Any path that creates a new account or merges by email requires the IdP to
    # have verified the email - otherwise an unverified-email IdP response could
    # take over an existing account or mint a privileged one (role is granted by
    # email match just below).
    user = User.query.filter_by(workos_user_id=wo_user["id"]).first()
    if user is None:
        if not wo_user.get("email_verified"):
            flash("Please verify your email with your identity provider, then sign "
                  "in again.", "warn")
            return redirect(url_for("auth.login"))
        user = User.query.filter_by(email=email).first()
    is_new = user is None  # a merge of an existing account is NOT a new signup
    if user is None:
        user = User(
            email=email,
            display_name=" ".join(p for p in (wo_user.get("first_name"),
                                              wo_user.get("last_name")) if p),
            role=("admin" if email in current_app.config["ADMIN_EMAILS"] else
                      "partner" if email in current_app.config["PARTNER_EMAILS"]
                      else "member"),
        )
        user.set_password(pysecrets.token_urlsafe(32))  # unusable; WorkOS owns auth
        db.session.add(user)
    user.workos_user_id = wo_user["id"]
    if not user.display_name and wo_user.get("first_name"):
        user.display_name = " ".join(p for p in (wo_user.get("first_name"),
                                                 wo_user.get("last_name")) if p)
    db.session.commit()
    if is_new:
        try:
            from .notify import send_welcome
            send_welcome(user)
        except Exception:
            current_app.logger.exception("welcome email failed")
    nxt = session.pop("workos_next", None) or url_for("main.dashboard")
    login_user(user)
    if not user.accepted_ai_disclaimer:
        return redirect(url_for("auth.welcome", next=nxt))
    return redirect(nxt)


def _workos_authenticate(code):
    """Exchange the AuthKit code for the WorkOS user (raw HTTP, no SDK needed)."""
    body = json.dumps({
        "client_id": current_app.config["WORKOS_CLIENT_ID"],
        "client_secret": current_app.config["WORKOS_API_KEY"],
        "grant_type": "authorization_code",
        "code": code,
    }).encode()
    req = urllib.request.Request(
        "https://api.workos.com/user_management/authenticate",
        data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return data["user"]


def _safe_next(default_endpoint="main.dashboard"):
    nxt = request.args.get("next") or request.form.get("next")
    # Only same-site absolute paths. Reject protocol-relative ("//evil.com") and
    # backslash ("/\evil.com") forms that many browsers treat as absolute - an
    # open-redirect / phishing primitive on a payment-handling app.
    if (nxt and nxt.startswith("/")
            and not nxt.startswith("//") and not nxt.startswith("/\\")):
        return nxt
    return url_for(default_endpoint)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user():
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        name = (request.form.get("display_name") or "").strip()
        pw = request.form.get("password") or ""
        if not EMAIL_RE.match(email):
            flash("Please enter a valid email.", "warn")
        elif len(pw) < 8:
            flash("Password must be at least 8 characters.", "warn")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered - try signing in.", "warn")
        else:
            # Self-service signup ALWAYS creates a plain member. The local form is
            # unauthenticated, so it must never grant admin/partner just because the
            # typed email matches a configured operator/partner address - that was a
            # privilege-escalation hole. Privileged roles come only from the seeded
            # operator, a WorkOS email-verified match, or ops_set_role.
            user = User(email=email, display_name=name, role="member")
            user.set_password(pw)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            try:
                from .notify import send_welcome
                send_welcome(user)
            except Exception:
                current_app.logger.exception("welcome email failed")
            return redirect(url_for("auth.welcome", next=_safe_next()))
    return render_template("auth/signup.html", next=request.args.get("next", ""))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(pw):
            login_user(user)
            if not user.accepted_ai_disclaimer:
                return redirect(url_for("auth.welcome", next=_safe_next()))
            return redirect(_safe_next())
        flash("Email or password is incorrect.", "warn")
    return render_template("auth/login.html", next=request.args.get("next", ""))


@bp.route("/welcome", methods=["GET", "POST"])
@login_required
def welcome():
    """One-time acknowledgment that the coach is an AI, not Anne-Marie herself."""
    user = current_user()
    if user.accepted_ai_disclaimer:
        return redirect(_safe_next())
    if request.method == "POST":
        if request.form.get("acknowledge"):
            user.accepted_ai_disclaimer = True
            user.accepted_at = datetime.utcnow()
            db.session.commit()
            flash("You're in. Say hi to your coach whenever you're ready.", "ok")
            return redirect(_safe_next())
        flash("Please check the box to continue.", "warn")
    return render_template("auth/welcome.html", next=request.args.get("next", ""))


@bp.route("/logout", methods=["POST", "GET"])
def logout():
    logout_user()
    flash("Signed out.", "ok")
    return redirect(url_for("main.index"))
