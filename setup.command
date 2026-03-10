#!/bin/bash
cd "$(dirname "$0")"
bash setup.sh

# Start the bot after setup
PLIST="$HOME/Library/LaunchAgents/com.tiktok-lookup.plist"
if [ -f "$PLIST" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo ""
  echo "=== Bot started ==="
  echo "Fill in your API key in .claude/.env, then send a TikTok URL to your Mac via iMessage to test."
fi

echo ""
echo "Press any key to close..."
read -n 1
