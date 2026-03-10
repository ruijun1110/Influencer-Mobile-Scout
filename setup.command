#!/bin/bash
cd "$(dirname "$0")"
bash setup.sh

# Colors
BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RESET='\033[0m'

divider() { echo -e "${DIM}──────────────────────────────────────────${RESET}"; }

# Start the bot
PLIST="$HOME/Library/LaunchAgents/com.tiktok-lookup.plist"
PLIST_SRC="$(dirname "$0")/.claude/skills/tiktok-lookup/launchd/com.tiktok-lookup.plist"

cp "$PLIST_SRC" "$PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo ""
divider
echo ""
echo -e "  ${GREEN}${BOLD}iMessage bot is running.${RESET}"
echo ""
echo -e "  Send a TikTok URL to your Mac via iMessage to get started."
echo -e "  ${DIM}Example: https://www.tiktok.com/@someuser${RESET}"
echo ""
divider
echo ""
echo -e "  ${DIM}Press any key to close...${RESET}"
read -n 1
