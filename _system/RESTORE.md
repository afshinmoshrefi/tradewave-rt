# TradeWave Realtime - Deploy / Rebuild Runbook

Stand up the tradewave-rt box (LAN `192.168.1.177`, public `https://rt-dev.trxstat.com`)
from this repo. Everything runs as **root**. The app tree lives at **`/home/flask`**.

> This is a PRIVATE repo, but SECRETS ARE NOT IN IT. The repo holds all code, config,
> systemd units, the DB snapshot, and this runbook. The secrets (`secrets.env`), the
> Cloudflare tunnel credential, and `cert.pem` live ONLY in the off-box backup tarball
> `tradewave-rt-FULL-backup-*.tar.gz`. You need BOTH the repo and that tarball to restore.

## What you need before you start
- This repo (`git clone`).
- The off-box backup tarball `tradewave-rt-FULL-backup-*.tar.gz` (holds the secrets + tunnel cred).
- Cloudflare dashboard access (for DNS, if the tunnel UUID ever changes).
- WorkOS + Stripe dashboard access (redirect URI / webhook live there, not on the box).

> The repo is plain git (no LFS; largest file ~1.6 MB). A normal clone needs no extra tooling.

---

## 1. Base packages
```bash
apt-get update && apt-get install -y \
  git python3.13 python3.13-venv python3.13-dev build-essential \
  sqlite3 pandoc tzdata
# yt-dlp (briefing timer) may also need ffmpeg; install if the briefing pull fails:
#   apt-get install -y ffmpeg
python3.13 --version   # expect 3.13.7 (the interpreter the venv was built against)
```

## 2. cloudflared (apt package, not in git)
```bash
# add Cloudflare's apt repo + key, then:
apt-get install -y cloudflared
/usr/bin/cloudflared --version    # live box ran 2026.5.2; newer is fine
```

## 3. Clone the repo to the exact path
```bash
git clone git@github.com:<owner>/<repo>.git /home/flask
# if /home/flask exists, clone elsewhere and move contents so the tree root is /home/flask
```

## 4. Restore application secrets -> /etc (from the off-box tarball, NOT git)
```bash
# the tarball stores them under etc/tradewave_realtime/ - extract just that subtree:
tar -xzf tradewave-rt-FULL-backup-*.tar.gz -C / etc/tradewave_realtime
chmod 0600 /etc/tradewave_realtime/secrets.env*
chown root:root /etc/tradewave_realtime/secrets.env*
```
Contains the live keys: `SECRET_KEY, ANTHROPIC_TOKEN, CLAUDE_MODEL, ADMIN_EMAILS, PORT,
EOD_TOKEN, LEVELS_INGEST_TOKEN, WORKOS_*, STRIPE_*, RESEND_API_KEY`.
(Discord bot creds are intentionally absent - see step 9.)

## 5. Restore Cloudflare tunnel creds -> /root/.cloudflared (cred + cert from the tarball)
```bash
# tunnel credential + origin cert + config come from the tarball (not in git):
tar -xzf tradewave-rt-FULL-backup-*.tar.gz -C / root/.cloudflared
# (config.yml is ALSO in git at _system/cloudflared/config.yml if you need it standalone)
chmod 0700 /root/.cloudflared
chmod 0400 /root/.cloudflared/*.json
chmod 0600 /root/.cloudflared/cert.pem
chmod 0644 /root/.cloudflared/config.yml
chown -R root:root /root/.cloudflared
```

## 6. Database
The DB is NOT in git (runtime data + PII). The schema auto-creates on first app boot
(`db.create_all()`); you then populate it one of two ways:

- **Fresh install / dev** - rebuild content from versioned source:
  ```bash
  cd /home/flask/tradewave_realtime
  .venv/bin/flask seed
  ```
  Loads the 54 `knowledge_entries` from `knowledge_seed/*.md` (verified byte-identical to
  the production knowledge), plus the admin/partner accounts and the welcome post. Idempotent.

- **Recover real production data** (live users, subscriptions, posts, day_maps) - restore the
  most recent off-box snapshot instead of seeding:
  ```bash
  cp <snapshot>.db /home/flask/tradewave_realtime/data/tradewave_rt.db
  ```
  Snapshots live in the nightly `backups/` dir on the box and in the
  `tradewave-rt-FULL-backup-*.tar.gz` tarball. Verify: `sqlite3 ... 'PRAGMA integrity_check;'` -> ok.

## 7. Rebuild the Python virtualenv (the 317M .venv is git-ignored)
```bash
python3.13 -m venv /home/flask/tradewave_realtime/.venv
VPIP=/home/flask/tradewave_realtime/.venv/bin/pip
$VPIP install --upgrade pip
# MANDATORY: exact versions. Do NOT fall back to requirements.txt (it is loosely pinned
# and would drop/upgrade ~50 packages).
$VPIP install -r /home/flask/_system/requirements.lock
# Playwright browser binaries are NOT in pip - install them (screenshots break otherwise):
/home/flask/tradewave_realtime/.venv/bin/playwright install --with-deps chromium
```

## 8. Install systemd units
```bash
cp /home/flask/_system/systemd/*.service /home/flask/_system/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
```
(The 11 units in `_system/systemd/` are byte-identical to the live `/etc` copies and to
`tradewave_realtime/deploy/units/`. If they ever drift, re-diff and re-capture so the
repo stays authoritative. The in-tree `deploy/install.sh` works but its DB comments are
stale - follow THIS file for the DB, and note it does not enable cloudflared-rt.)

## 9. Enable + start to match live state EXACTLY
```bash
systemctl enable --now \
  tradewave-rt.service cloudflared-rt.service \
  tradewave-rt-backup.timer tradewave-rt-briefing.timer \
  tradewave-rt-levels.timer tradewave-rt-lifecycle.timer
```
Do **NOT** enable `tradewave-rt-bot.service` - it is intentionally disabled (Discord creds
not in secrets.env). Leaving it disabled matches current state.

## 10. Account-side items (NOT on this box - verify in dashboards)
- **DNS:** CNAME `rt-dev.trxstat.com -> abf8a47a-97a3-4b8f-af48-1b444207e125.cfargotunnel.com`.
  Reusing the same tunnel UUID (step 5) keeps the existing record. If rebuilding the tunnel:
  `cloudflared tunnel route dns rt-dev rt-dev.trxstat.com`.
- **WorkOS:** confirm `https://rt-dev.trxstat.com/...` is still a registered AuthKit redirect URI.
- **Stripe:** confirm the webhook endpoint still points at the public hostname.
- **Levels feed:** `tradewave-rt-levels` pulls from `http://104.238.214.253:7671` every 15 min
  (override via `KEYPROVIDER_LEVELS_URL` in secrets.env if that host changes).

## 11. Verify running state
```bash
systemctl is-active tradewave-rt cloudflared-rt          # active
ss -tlnp | grep -E ':5001|:20241'                        # gunicorn :5001, cloudflared metrics 127.0.0.1:20241
cloudflared tunnel list                                  # rt-dev shows active connections
systemctl list-timers | grep tradewave                   # 4 timers scheduled
dig +short rt-dev.trxstat.com                            # Cloudflare IPs
```
Then load `https://rt-dev.trxstat.com`, confirm the site renders and WorkOS login works.

## 12. Agent context (separate from this repo)
The Claude transcripts + memory (`/root/.claude`, `/home/afshin/.claude`) are git-ignored
and archived in the off-box tarball (`tradewave-rt-FULL-backup-*.tar.gz`). Unpack them to
their home paths if you want the conversation/memory history back.
