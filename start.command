#!/bin/bash
# start.command — Start the bot via launchd (or directly if launchd not set up)
cd "$(dirname "$0")"

SERVICE_LABEL="com.tiktok-scout"
PLIST="$HOME/Library/LaunchAgents/com.tiktok-scout.plist"

if [ -f "$PLIST" ]; then
  # Use launchd (preferred — handles single instance, auto-restart, logging)
  launchctl bootout "gui/$(id -u)/$SERVICE_LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  echo "Bot started via launchd. Check status: ./status.command"
else
  echo "LaunchAgent not installed. Run setup.command first."
  exit 1
fi
