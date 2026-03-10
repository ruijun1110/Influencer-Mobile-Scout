#!/bin/bash
# start.command — Runs the iMessage bot. Double-click or add as Login Item.
# Terminal must have Full Disk Access for the bot to read iMessages.
# Single-instance is enforced by bot.py via fcntl.flock — safe to run multiple times.
cd "$(dirname "$0")"

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Restart loop — if bot crashes, restart after 10 seconds
while true; do
  uv run .claude/skills/tiktok-lookup/scripts/bot.py 2>&1
  EXIT_CODE=$?
  if [ "$EXIT_CODE" -eq 10 ]; then
    # Exit 10 = another instance already running. Stop retrying.
    echo "[$(date +%H:%M:%S)] Another instance is running. This launcher will exit."
    exit 0
  fi
  echo "[$(date +%H:%M:%S)] Bot exited (code $EXIT_CODE), restarting in 10s..."
  sleep 10
done
