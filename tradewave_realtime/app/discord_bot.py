"""The Anne-Marie coach in Discord - the room's always-on teacher.

Design (see product/V1_SITE_DESIGN.md, Discord section): one server, two tiers.
- Member channels: the morning map drop, her insights, and #ask-the-coach with
  the TODAY-AWARE coach. PUBLIC answers never use any member's private profile.
- Free channels: #coach-preview answers EVERGREEN method questions only -
  today's map is the paid product and never crosses the paywall.
The bot is always clearly the AI ("AM Coach [AI]"), never Anne-Marie herself.

Run: `python run_bot.py` (systemd: tradewave-rt-bot.service). Needs
DISCORD_BOT_TOKEN + DISCORD_GUILD_ID in /etc/tradewave_realtime/secrets.env.
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path

import discord
from discord.ext import tasks

log = logging.getLogger("am-bot")

ROLE_MEMBER = "Member"
ROLE_FREE = "Free"

FREE_CHANNELS = {
    "general": "Say hi. Traders talking trading.",
    "briefing-talk": "Anne-Marie's free morning briefings - watch and discuss.",
    "coach-preview": "Ask the AM Coach [AI] about her METHOD. Members get the "
                     "daily map and today-aware coaching inside.",
    "link-up": "Type !link YOURCODE (from your account page) to unlock member channels.",
}
MEMBER_CHANNELS = {
    "morning-map": "The Daily Level Map drops here every session. Members only.",
    "trading-the-method": "Trading her method together. No trade calls - ever.",
    "wins-and-lessons": "Green days, red days, what the method taught you.",
    "ask-the-coach": "The AM Coach [AI], today-aware. Educational only.",
}

DISCLOSURE = ("-# AI coach trained on Anne-Marie's method - educational only, "
              "never trade advice.")

COOLDOWN_SECONDS = 45
FREE_DAILY_CAP = 5

STATE_FILE = Path(__file__).resolve().parent.parent / "instance" / "discord_state.json"


def _load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def _save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


class AMBot(discord.Client):
    def __init__(self, flask_app):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.app = flask_app
        self.state = _load_state()
        self._cooldowns = {}   # discord_user_id -> last ts
        self._free_counts = {} # (date, discord_user_id) -> n

    # ------------------------------------------------------------- lifecycle
    async def on_ready(self):
        log.info("logged in as %s", self.user)
        guild = self.get_guild(self.app.config["DISCORD_GUILD_ID"])
        if guild is None:
            log.error("guild %s not found - is the bot invited?",
                      self.app.config["DISCORD_GUILD_ID"])
            return
        await self.ensure_structure(guild)
        if not self.heartbeat.is_running():
            self.heartbeat.start()

    async def ensure_structure(self, guild):
        """Idempotently create roles, channels, and permissions."""
        roles = {r.name: r for r in guild.roles}
        member_role = roles.get(ROLE_MEMBER) or await guild.create_role(
            name=ROLE_MEMBER, colour=discord.Colour.purple(), hoist=True)
        free_role = roles.get(ROLE_FREE) or await guild.create_role(name=ROLE_FREE)

        cats = {c.name: c for c in guild.categories}
        cat = cats.get("TradeWave Realtime") or await guild.create_category(
            "TradeWave Realtime")

        chans = {c.name: c for c in guild.text_channels}
        for name, topic in FREE_CHANNELS.items():
            if name not in chans:
                await guild.create_text_channel(name, category=cat, topic=topic)
        member_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member_role: discord.PermissionOverwrite(view_channel=True),
            guild.me: discord.PermissionOverwrite(view_channel=True),
        }
        for name, topic in MEMBER_CHANNELS.items():
            ch = chans.get(name)
            if ch is None:
                await guild.create_text_channel(name, category=cat, topic=topic,
                                                overwrites=member_overwrites)
        # the map channel is read-only for humans
        chans = {c.name: c for c in guild.text_channels}
        mm = chans.get("morning-map")
        if mm:
            await mm.set_permissions(member_role, view_channel=True,
                                     send_messages=False)
        log.info("structure ensured")

    # ------------------------------------------------------------- messages
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return
        name = message.channel.name

        if name == "link-up" and message.content.lower().startswith("!link"):
            await self.handle_link(message)
            return
        if name == "ask-the-coach":
            await self.answer(message, include_today=True)
        elif name == "coach-preview":
            today_key = (datetime.utcnow().date().isoformat(), message.author.id)
            n = self._free_counts.get(today_key, 0)
            if n >= FREE_DAILY_CAP:
                await message.reply(
                    "That's my limit out here for today. Members get unlimited "
                    "coaching plus the daily level map inside - "
                    "https://rt-dev.trxstat.com", mention_author=False)
                return
            self._free_counts[today_key] = n + 1
            await self.answer(message, include_today=False)

    async def answer(self, message, include_today):
        now = time.time()
        last = self._cooldowns.get(message.author.id, 0)
        if now - last < COOLDOWN_SECONDS:
            await message.add_reaction("\N{HOURGLASS}")
            return
        self._cooldowns[message.author.id] = now

        text = message.clean_content.strip()[:2000]
        if not text:
            return
        async with message.channel.typing():
            def _call():
                with self.app.app_context():
                    from .llm import (generate_reply, _build_chat_request, _no_emdash,
                                      correct_level_typos, enforce_compliance)
                    import anthropic
                    api_key = self.app.config.get("ANTHROPIC_TOKEN")
                    if not api_key:
                        reply, _, _ = generate_reply(text)
                    else:
                        from .mentor import free_tier_stub
                        # Public channel: NEVER a member's private profile (it would leak
                        # to the room). A generic stub gives continuity + a gentle nudge.
                        req = _build_chat_request(
                            text, [], member_context=free_tier_stub(None),
                            include_today=include_today, max_tokens=550,
                            extra_instruction=(
                                "This is a PUBLIC Discord channel with many readers. "
                                "Keep it tight (a short paragraph or two), never "
                                "reference any individual's situation or history, and "
                                "teach to the room."))
                        client = anthropic.Anthropic(api_key=api_key)
                        resp = client.messages.create(**req)
                        reply = _no_emdash("".join(
                            b.text for b in resp.content
                            if getattr(b, "type", "") == "text").strip())
                    # Public room: route through the SAME safety net as the web coach
                    # (this path previously skipped both): level-typo repair, then the
                    # runtime compliance screen. A public buy/sell call here is the
                    # worst-case for Anne-Marie's reputation.
                    reply, _ = correct_level_typos(reply, text)
                    reply, _, _ = enforce_compliance(reply)
                    return reply
            try:
                reply = await asyncio.to_thread(_call)
            except Exception:
                log.exception("coach reply failed")
                await message.reply("Something hiccuped on my end - try that again.",
                                    mention_author=False)
                return
        for chunk in _split(reply + "\n" + DISCLOSURE):
            await message.reply(chunk, mention_author=False)

    async def handle_link(self, message):
        code = message.content.split(maxsplit=1)[1].strip().upper() if \
            len(message.content.split(maxsplit=1)) > 1 else ""
        def _link():
            with self.app.app_context():
                from .extensions import db
                from .models import User
                u = User.query.filter_by(discord_link_code=code).first() if code else None
                if u is None:
                    return None
                u.discord_user_id = str(message.author.id)
                u.discord_link_code = None
                db.session.commit()
                return self._is_member(u)
        is_member = await asyncio.to_thread(_link)
        try:
            await message.delete()  # the code shouldn't linger in public
        except discord.Forbidden:
            pass
        if is_member is None:
            await message.channel.send(
                f"{message.author.mention} that code didn't match - grab yours "
                "from your account page.", delete_after=20)
            return
        guild = message.guild
        role = discord.utils.get(guild.roles, name=ROLE_MEMBER if is_member else ROLE_FREE)
        if role:
            await message.author.add_roles(role)
        await message.channel.send(
            f"{message.author.mention} you're in. Welcome to the room.",
            delete_after=20)

    def _is_member(self, user):
        """Active subscription, or everyone during the free-access era."""
        if not self.app.config.get("BILLING_REQUIRED"):
            return True
        from .billing import active_subscription
        return active_subscription(user) is not None

    # ------------------------------------------------------------- heartbeat
    @tasks.loop(minutes=1)
    async def heartbeat(self):
        try:
            await self.maybe_post_map()
            await self.maybe_post_insight()
            if datetime.utcnow().minute == 7:   # hourly-ish role sync
                await self.sync_roles()
        except Exception:
            log.exception("heartbeat tick failed")

    async def maybe_post_map(self):
        def _get():
            with self.app.app_context():
                from .marketdata import ET, latest_session
                from .levels import latest_maps, direction_sentences
                now = datetime.now(ET)
                session = str(latest_session())
                if now.strftime("%H:%M") < "07:30" or session == self.state.get("map_posted"):
                    return None
                maps = latest_maps()
                if not maps or all(m.status == "pending" for m in maps):
                    return None
                lines = [f"**The Daily Level Map - {session}**"]
                for m in maps:
                    p = m.payload
                    lines.append(f"\n**{m.instrument}**")
                    for s in direction_sentences(p)[:3]:
                        lines.append(f"- {s}")
                    lvl = "\n".join(f"{lv['price']:>10.2f}  {lv['label']} ({lv['age']})"
                                    for lv in p.get("levels", [])[:8])
                    lines.append(f"```{lvl}```")
                lines.append("Full map + your coach: https://rt-dev.trxstat.com/app")
                lines.append(DISCLOSURE)
                return session, "\n".join(lines)
        result = await asyncio.to_thread(_get)
        if not result:
            return
        session, content = result
        ch = self._channel("morning-map")
        if ch:
            for chunk in _split(content):
                await ch.send(chunk)
            self.state["map_posted"] = session
            _save_state(self.state)

    async def maybe_post_insight(self):
        def _get():
            with self.app.app_context():
                from .models import Post
                row = (Post.query.filter_by(published=True, kind="insight")
                       .order_by(Post.id.desc()).first())
                if row and row.id != self.state.get("insight_posted"):
                    return row.id, row.body
                return None
        result = await asyncio.to_thread(_get)
        if not result:
            return
        pid, body = result
        ch = self._channel("morning-map")
        if ch:
            await ch.send(f"**From Anne-Marie today**\n{body[:1800]}")
            self.state["insight_posted"] = pid
            _save_state(self.state)

    async def sync_roles(self):
        """Membership role follows the subscription once billing is required."""
        guild = self.get_guild(self.app.config["DISCORD_GUILD_ID"])
        if guild is None:
            return
        def _linked():
            with self.app.app_context():
                from .models import User
                return [(u.discord_user_id, self._is_member(u))
                        for u in User.query.filter(User.discord_user_id.isnot(None))]
        pairs = await asyncio.to_thread(_linked)
        member_role = discord.utils.get(guild.roles, name=ROLE_MEMBER)
        free_role = discord.utils.get(guild.roles, name=ROLE_FREE)
        for discord_id, is_member in pairs:
            m = guild.get_member(int(discord_id))
            if m is None:
                continue
            want, drop = (member_role, free_role) if is_member else (free_role, member_role)
            if want and want not in m.roles:
                await m.add_roles(want)
            if drop and drop in m.roles:
                await m.remove_roles(drop)

    def _channel(self, name):
        guild = self.get_guild(self.app.config["DISCORD_GUILD_ID"])
        if guild is None:
            return None
        return discord.utils.get(guild.text_channels, name=name)


def _split(text, limit=1900):
    out = []
    while text:
        out.append(text[:limit])
        text = text[limit:]
    return out


def run():
    logging.basicConfig(level=logging.INFO)
    from app import create_app
    flask_app = create_app()
    token = flask_app.config.get("DISCORD_BOT_TOKEN")
    if not token:
        log.error("DISCORD_BOT_TOKEN not set - add it to "
                  "/etc/tradewave_realtime/secrets.env and restart. Exiting.")
        return
    AMBot(flask_app).run(token, log_handler=None)
