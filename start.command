#!/bin/bash
# start.command — Runs the iMessage bot. Double-click or add as Login Item.
# Terminal must have Full Disk Access for the bot to read iMessages.
cd "$(dirname "$0")"

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

LOCK_FILE="/tmp/tiktok-scout-bot.lock"

# Validate lock file — remove if stale
if [ -f "$LOCK_FILE" ]; then
  existing_pid=$(cat "$LOCK_FILE" 2>/dev/null)
  if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "[bot] Already running (PID $existing_pid). Exiting."
    exit 0
  else
    rm -f "$LOCK_FILE"
  fi
fi

echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT INT TERM HUP

# Restart loop — if bot crashes, restart after 10 seconds
while true; do
  uv run .claude/skills/tiktok-lookup/scripts/bot.py 2>&1
  echo "[$(date +%H:%M:%S)] Bot exited, restarting in 10s..."
  sleep 10
done
