#!/bin/bash
# Runs the iMessage bot. Added as a Login Item by setup.sh — starts automatically on login.
cd "$(dirname "$0")"

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# Restart loop — if bot crashes, restart after 5 seconds
while true; do
  uv run .claude/skills/tiktok-lookup/scripts/bot.py
  sleep 5
done
