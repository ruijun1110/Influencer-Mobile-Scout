#!/bin/bash
PLIST="$HOME/Library/LaunchAgents/com.tiktok-lookup.plist"

if [ ! -f "$PLIST" ]; then
  echo "ERROR: Bot not set up yet. Double-click setup.command first."
  echo ""
  echo "Press any key to close..."
  read -n 1
  exit 1
fi

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Bot started."
echo ""
echo "Press any key to close..."
read -n 1
