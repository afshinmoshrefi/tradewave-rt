"""Data models for TradeWave Realtime V1."""
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.utcnow()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False, default="")
    # The shared TradeWave identity (WorkOS AuthKit). Existing local accounts
    # merge by email on their first WorkOS login.
    workos_user_id = db.Column(db.String(64), nullable=True, unique=True)
    stripe_customer_id = db.Column(db.String(64), nullable=True, unique=True)
    # Discord membership link (role-sync): set when the member links accounts.
    discord_user_id = db.Column(db.String(32), nullable=True, unique=True)
    discord_link_code = db.Column(db.String(12), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="member")  # member | partner | admin
    accepted_ai_disclaimer = db.Column(db.Boolean, nullable=False, default=False)
    accepted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    # Last time the member loaded the app/coach. The signal the re-engagement
    # lifecycle fires on - without it the product cannot even detect a lapse.
    last_active_at = db.Column(db.DateTime, nullable=True)

    threads = db.relationship("ChatThread", backref="user", lazy=True,
                              cascade="all, delete-orphan")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self):
        """The site operator (full access incl. operations)."""
        return self.role == "admin"

    @property
    def is_staff(self):
        """Anyone with workspace access: the operator or Anne-Marie (partner)."""
        return self.role in ("admin", "partner")

    @property
    def name_or_email(self):
        return self.display_name or self.email.split("@")[0]


class KnowledgeEntry(db.Model):
    """A unit of the coach's evergreen knowledge. Curated/approved by the admin.
    The same rows serve two surfaces: the coach's RAG corpus (all of them) and
    the Method curriculum (kind=lesson, organized by stage/stage_order)."""
    __tablename__ = "knowledge_entries"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    # method | psychology | rules | faq | glossary
    category = db.Column(db.String(40), nullable=False, default="method")
    content = db.Column(db.Text, nullable=False, default="")
    source = db.Column(db.String(255), nullable=False, default="")
    published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    # Curriculum placement: stage 1-5 for lessons, 0 for reference material.
    stage = db.Column(db.Integer, nullable=False, default=0)
    stage_order = db.Column(db.Integer, nullable=False, default=0)
    kind = db.Column(db.String(12), nullable=False, default="lesson")  # lesson | reference
    # Whose words + release state. Afshin's rule (2026-06-10): content sourced
    # from her recordings is PRE-APPROVED (it is already her); only AI-drafted /
    # team-written content waits as a draft. Only approved entries reach the
    # coach's corpus or members.
    provenance = db.Column(db.String(16), nullable=False, default="team_inference")
    status = db.Column(db.String(12), nullable=False, default="approved")  # draft | approved | retired
    source_quote = db.Column(db.Text, nullable=False, default="")
    # The beginner-tier "in plain English" teaching layer (AI-authored, reviewable):
    # an added simplification surfaced to beginner/developing readers and via an
    # "explain like I'm brand new" toggle. NEVER replaces her content (`content`
    # stays the source of truth); empty = no plain layer authored yet.
    plain = db.Column(db.Text, nullable=False, default="")

    PROVENANCES = ["her_words", "her_approved", "team_inference"]
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    CATEGORIES = ["method", "psychology", "rules", "faq", "glossary", "foundation"]

    STAGES = {
        1: ("Read the day", "Before any trade: the master candles, the stair-step, "
                            "and the trend gate"),
        2: ("The levels", "Where price reacts: the map and every layer on it"),
        3: ("Permission to enter", "A level is a location, not a signal: confirmation "
                                   "and her two entries"),
        4: ("Manage the trade", "Exits, risk, sizing, and the day types"),
        5: ("The trader's mind", "Her signature: psychology, patience, and process"),
    }


class UserLesson(db.Model):
    """A member's progress on a curriculum lesson. viewed_at = opened it (counts
    as progress, dismisses the on-ramp, lets chat-learning be visible);
    done_at = explicitly mastered. A row may be viewed-but-not-done."""
    __tablename__ = "user_lessons"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    entry_id = db.Column(db.Integer, db.ForeignKey("knowledge_entries.id"),
                         nullable=False)
    done_at = db.Column(db.DateTime, nullable=True)
    viewed_at = db.Column(db.DateTime, nullable=True, default=utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "entry_id", name="uq_user_lesson"),)


class Post(db.Model):
    """A lesson/update Anne-Marie publishes to the member feed.
    kind=insight posts also surface in the Today page's FROM ANNE-MARIE slot."""
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    kind = db.Column(db.String(12), nullable=False, default="post")  # post | insight
    body = db.Column(db.Text, nullable=False, default="")
    published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    author = db.relationship("User")


class UserProfile(db.Model):
    """The trader profile - what the coach knows about a member. Built by the
    intake conversation, refined over time. Bounded, user-visible, editable,
    deletable. NEVER stores positions, balances, or dollar amounts."""
    __tablename__ = "user_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True,
                        nullable=False)
    user = db.relationship("User", backref=db.backref("profile", uselist=False))
    intake_step = db.Column(db.Integer, nullable=False, default=0)
    intake_done = db.Column(db.Boolean, nullable=False, default=False)
    experience = db.Column(db.String(300), nullable=False, default="")
    instruments = db.Column(db.String(300), nullable=False, default="")
    account_type = db.Column(db.String(60), nullable=False, default="")
    goal = db.Column(db.Text, nullable=False, default="")
    recent = db.Column(db.Text, nullable=False, default="")  # how it's been going
    struggles_keys = db.Column(db.String(200), nullable=False, default="")
    struggles_raw = db.Column(db.Text, nullable=False, default="")
    schedule = db.Column(db.String(300), nullable=False, default="")
    summary = db.Column(db.Text, nullable=False, default="")
    # Rolling cross-session coaching summary (the seed of V2 deep memory):
    # regenerated by Haiku as conversations accumulate, bounded, member-visible.
    coaching_summary = db.Column(db.Text, nullable=False, default="")
    summarized_upto = db.Column(db.Integer, nullable=False, default=0)
    # When the rolling summary was last regenerated - lets it refresh on a TIME
    # cadence (not only after 8 messages) so light engagers still compound.
    summary_updated_at = db.Column(db.DateTime, nullable=True)
    assigned_json = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    @property
    def assigned(self):
        import json
        try:
            return json.loads(self.assigned_json or "[]")
        except ValueError:
            return []

    @assigned.setter
    def assigned(self, value):
        import json
        self.assigned_json = json.dumps(value)


class Subscription(db.Model):
    """A member's RT subscription, mirrored from Stripe via webhook."""
    __tablename__ = "subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", backref="subscriptions")
    stripe_subscription_id = db.Column(db.String(64), unique=True, nullable=False)
    price_id = db.Column(db.String(64), nullable=False, default="")
    plan = db.Column(db.String(20), nullable=False, default="monthly")  # monthly | annual
    status = db.Column(db.String(24), nullable=False, default="incomplete")
    founding = db.Column(db.Boolean, nullable=False, default=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    # Stamped when a renewal first fails (status -> past_due); cleared on recovery.
    # Drives the fixed grace window below so a failed card does not keep the
    # perishable daily product for Stripe's whole ~2-3 week dunning cycle.
    past_due_since = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    # Statuses recognized as a live subscription. past_due is recognized but only
    # ENTITLES for PAST_DUE_GRACE_DAYS after past_due_since (see is_active), so a
    # cheap SQL prefilter on this set must always be confirmed by is_active.
    ACTIVE_STATUSES = {"active", "trialing", "past_due"}
    PAST_DUE_GRACE_DAYS = 7

    @property
    def is_active(self):
        """Entitlement truth. active/trialing are in. past_due keeps access for a
        fixed grace window after the renewal first failed (past_due_since), then
        drops. A past_due row with no stamp yet (legacy / not-yet-synced) is treated
        as in-grace so we never wrongly lock out a member we lack timing data on."""
        if self.status in ("active", "trialing"):
            return True
        if self.status == "past_due":
            if self.past_due_since is None:
                return True
            return utcnow() - self.past_due_since < timedelta(days=self.PAST_DUE_GRACE_DAYS)
        return False


class CheckIn(db.Model):
    """The daily mentor check-in: a morning plan and an after-close review,
    one line each, with the coach's short reflection."""
    __tablename__ = "check_ins"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User")
    session_date = db.Column(db.Date, nullable=False)
    kind = db.Column(db.String(10), nullable=False)  # plan | review
    text = db.Column(db.Text, nullable=False)
    reply = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "session_date", "kind",
                                          name="uq_checkin"),)


class Appearance(db.Model):
    """A scheduled Anne-Marie appearance (Discord drop-in, webinar, AMA).
    Members see upcoming ones on Today; the coach may mention them factually -
    this is the ONLY way the coach ever cites her schedule."""
    __tablename__ = "appearances"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    where = db.Column(db.String(120), nullable=False, default="Discord")
    starts_at = db.Column(db.DateTime, nullable=False)  # stored UTC
    note = db.Column(db.String(400), nullable=False, default="")
    published = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    @property
    def starts_at_et(self):
        from datetime import timezone
        from .marketdata import ET
        return (self.starts_at.replace(tzinfo=timezone.utc).astimezone(ET)
                .strftime("%A %b %-d, %-I:%M %p ET"))


class NotificationLog(db.Model):
    """The proactivity ledger: every coach-initiated send, with its reason.
    Powers the caps (max one coach email/day per member) and the member-facing
    'why did I get this' accountability."""
    __tablename__ = "notification_log"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    kind = db.Column(db.String(24), nullable=False)  # welcome | morning_brief | ...
    channel = db.Column(db.String(12), nullable=False, default="email")
    subject = db.Column(db.String(255), nullable=False, default="")
    sent_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class IntradayBar(db.Model):
    """Raw 30-minute bar (UTC timestamp) from EODHD history or live capture.
    The engine derives candles, SMAs, and touched-status from this table."""
    __tablename__ = "intraday_bars"
    id = db.Column(db.Integer, primary_key=True)
    instrument = db.Column(db.String(8), nullable=False)
    ts = db.Column(db.Integer, nullable=False)  # unix UTC, bar open
    open = db.Column(db.Float, nullable=False)
    high = db.Column(db.Float, nullable=False)
    low = db.Column(db.Float, nullable=False)
    close = db.Column(db.Float, nullable=False)
    volume = db.Column(db.Integer, nullable=True)
    __table_args__ = (db.UniqueConstraint("instrument", "ts", name="uq_bar"),
                      db.Index("ix_bar_instrument_ts", "instrument", "ts"))


class MarketCandle(db.Model):
    """One of Anne-Marie's structural candles, extracted per session.
    source: eodhd (history-derived) | capture (keyprovider push) | reconciled."""
    __tablename__ = "market_candles"
    id = db.Column(db.Integer, primary_key=True)
    instrument = db.Column(db.String(8), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    window = db.Column(db.String(24), nullable=False)
    open = db.Column(db.Float, nullable=False)
    high = db.Column(db.Float, nullable=False)
    low = db.Column(db.Float, nullable=False)
    close = db.Column(db.Float, nullable=False)
    volume = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String(12), nullable=False, default="eodhd")
    captured_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    # Audit trail: the original capture values survive reconciliation so a bad
    # capture can be diagnosed after its row is overwritten with truth.
    capture_open = db.Column(db.Float, nullable=True)
    capture_close = db.Column(db.Float, nullable=True)
    recon_drift = db.Column(db.Float, nullable=True)
    __table_args__ = (db.UniqueConstraint("instrument", "session_date", "window",
                                          name="uq_candle"),)

    @property
    def body_low(self):
        return min(self.open, self.close)

    @property
    def body_high(self):
        return max(self.open, self.close)


class DayMap(db.Model):
    """The computed Daily Level Map for one instrument and session - the single
    source of truth the Today page, the coach, and the indicator feed all read."""
    __tablename__ = "day_maps"
    id = db.Column(db.Integer, primary_key=True)
    instrument = db.Column(db.String(8), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    payload_json = db.Column(db.Text, nullable=False, default="{}")
    status = db.Column(db.String(12), nullable=False, default="pending")  # ok | partial | pending
    built_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (db.UniqueConstraint("instrument", "session_date", name="uq_daymap"),)

    @property
    def payload(self):
        import json
        try:
            return json.loads(self.payload_json or "{}")
        except ValueError:
            return {}

    @payload.setter
    def payload(self, value):
        import json
        self.payload_json = json.dumps(value, default=str)


class MarketClosure(db.Model):
    """Admin-added full-close date (add-only override on top of the hardcoded
    holiday calendar in marketdata.py). Can only ADD a closure, never remove a
    real holiday, so a data slip can never re-open the market in the UI."""
    __tablename__ = "market_closures"
    id = db.Column(db.Integer, primary_key=True)
    closed_on = db.Column(db.Date, unique=True, nullable=False)
    reason = db.Column(db.String(120), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Trade(db.Model):
    """A member's COMPLETED trade, for the educational debrief. Money-blind by
    design: stores price LEVELS (market data, like the map) and a size BUCKET -
    NEVER dollar P&L, account balance, or position dollar value. Completed
    round-trips only; the coach never sees an open position (compliance line)."""
    __tablename__ = "trades"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User")
    session_date = db.Column(db.Date, nullable=False)
    instrument = db.Column(db.String(8), nullable=False, default="")
    side = db.Column(db.String(8), nullable=False, default="")  # long | short
    entry_price = db.Column(db.Float, nullable=True)
    exit_price = db.Column(db.Float, nullable=True)
    size_bucket = db.Column(db.String(12), nullable=False, default="unknown")  # smallest|small|normal|large|unknown
    note = db.Column(db.Text, nullable=False, default="")  # member's words, money-scrubbed
    grade_json = db.Column(db.Text, nullable=False, default="{}")  # deterministic grade vs the day's map
    reviewed = db.Column(db.Boolean, nullable=False, default=False)  # coach debriefed it
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    SIZE_BUCKETS = ["smallest", "small", "normal", "large", "unknown"]

    @property
    def grade(self):
        import json
        try:
            return json.loads(self.grade_json or "{}")
        except ValueError:
            return {}

    @grade.setter
    def grade(self, value):
        import json
        self.grade_json = json.dumps(value, default=str)


class DeferredQuestion(db.Model):
    """A question the coach could not answer and flagged for Anne-Marie. Links
    the ASKER so the loop can close: when she answers (teach publishes), the
    member gets 'Anne-Marie answered your question' - the deferral promise kept."""
    __tablename__ = "deferred_questions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User")
    message_id = db.Column(db.Integer, db.ForeignKey("chat_messages.id"), nullable=True)
    question = db.Column(db.Text, nullable=False, default="")  # the asker's own words
    answered = db.Column(db.Boolean, nullable=False, default=False)
    answered_entry_id = db.Column(db.Integer,
                                  db.ForeignKey("knowledge_entries.id"), nullable=True)
    notified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    answered_at = db.Column(db.DateTime, nullable=True)


class ChatThread(db.Model):
    __tablename__ = "chat_threads"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False, default="New conversation")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    messages = db.relationship("ChatMessage", backref="thread", lazy=True,
                               cascade="all, delete-orphan",
                               order_by="ChatMessage.created_at")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("chat_threads.id"), nullable=False)
    role = db.Column(db.String(12), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    used_llm = db.Column(db.Boolean, nullable=False, default=False)
    # Member feedback: 1 thumbs-up, -1 thumbs-down (lands in the admin review
    # queue), 0 unrated. reviewed = Anne-Marie/admin handled it.
    rating = db.Column(db.Integer, nullable=False, default=0)
    reviewed = db.Column(db.Boolean, nullable=False, default=False)
    # Anonymized version of the content for admin/Anne-Marie surfaces (lazy).
    sanitized = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
