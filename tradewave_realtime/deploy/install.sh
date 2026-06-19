#!/usr/bin/env bash
# TradeWave Realtime - install/refresh the systemd units on this box.
# Idempotent: safe to re-run after any unit change or on a fresh production box.
#
# What this does NOT cover (do these once per box, by hand):
#   - /etc/tradewave_realtime/secrets.env  (copy from the old box, never in git)
#   - the .venv                            (python3 -m venv .venv && .venv/bin/pip install -r requirements.txt)
#   - the Cloudflare tunnel                (cloudflared-rt.service is included as a
#                                           TEMPLATE; the tunnel UUID + hostname are
#                                           per box - set up the tunnel first)
#   - the database                         (instance/ comes from backup restore on a
#                                           new box, or starts fresh)
set -euo pipefail
cd "$(dirname "$0")"

UNITS_ALWAYS_ON=(
  tradewave-rt.service          # the web app (gunicorn :5001)
  tradewave-rt-levels.timer     # candle captures + map rebuild, every 15 min
  tradewave-rt-backup.timer     # nightly DB backup, 14-day retention
  tradewave-rt-briefing.timer   # her morning video -> feed + coach, weekday mornings
  tradewave-rt-lifecycle.timer  # daily re-engagement + Sunday weekend touch
)
# tradewave-rt-bot.service: installed but NOT enabled - needs DISCORD_BOT_TOKEN
# and DISCORD_GUILD_ID in secrets.env first, then: systemctl enable --now tradewave-rt-bot
# cloudflared-rt.service: installed but NOT enabled here - per-box tunnel config first.

echo "==> copying unit files to /etc/systemd/system"
cp units/*.service units/*.timer /etc/systemd/system/

echo "==> daemon-reload"
systemctl daemon-reload

for u in "${UNITS_ALWAYS_ON[@]}"; do
  echo "==> enable --now $u"
  systemctl enable --now "$u"
done

echo "==> status"
systemctl is-active tradewave-rt.service
systemctl list-timers 'tradewave-rt-*' --no-pager
echo "OK - app + timers installed. Bot and cloudflared left for per-box setup (see header)."
