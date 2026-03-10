#!/bin/bash
# Runs the iMessage bot. Added as a Login Item by setup.sh — starts automatically on login.
cd "$(dirname "$0")"

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

LOCK_FILE="/tmp/tiktok-scout-bot.lock"

# Exit if another instance is already running
if [ -f "$LOCK_FILE" ]; then
  existing_pid=$(cat "$LOCK_FILE")
  if kill -0 "$existing_pid" 2>/dev/null; then
    echo "[bot] Already running (PID $existing_pid). Exiting."
    exit 0
  fi
fi

# Write our PID to the lock file
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# Restart loop — if bot crashes, restart after 5 seconds
while true; do
  uv run .claude/skills/tiktok-lookup/scripts/bot.py
  sleep 5
done
