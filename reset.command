#!/bin/bash
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

BOLD='\033[1m'
GREEN='\033[0;32m'
DIM='\033[2m'
YELLOW='\033[0;33m'
RESET='\033[0m'

divider() { echo -e "${DIM}──────────────────────────────────────────${RESET}"; }
ok()      { echo -e "  ${GREEN}✓${RESET}  $1"; }
info()    { echo -e "  ${DIM}→  $1${RESET}"; }

clear
echo ""
echo -e "${BOLD}  TikTok Influencer Scout — Reset${RESET}"
divider
echo ""
echo -e "  This will stop the bot, remove your API key config, and"
echo -e "  clean scouting results so you can run setup fresh."
echo ""
echo -e "  ${YELLOW}Press any key to continue, or Ctrl+C to cancel.${RESET}"
read -n 1 -s
echo ""

# 1. Stop bot
info "Stopping bot..."
pkill -f "bot.py" 2>/dev/null || true
pkill -f "start.command" 2>/dev/null || true
sleep 1
ok "Bot stopped"

# 2. Remove Login Item
osascript -e 'tell application "System Events" to delete every login item whose name is "TikTok Scout Bot"' 2>/dev/null || true
ok "Login Item removed"

# 3. Remove legacy launchd service
launchctl bootout "gui/$(id -u)/com.tiktok-scout" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.tiktok-scout.plist"
ok "LaunchAgent removed (if any)"

# 4. Remove .env
if [ -f "$PROJECT_DIR/.claude/.env" ]; then
  rm "$PROJECT_DIR/.claude/.env"
  ok ".env removed"
else
  ok ".env not found (already clean)"
fi

# 5. Clear logs and status
rm -f /tmp/tiktok-lookup.log
rm -f /tmp/tiktok-lookup.err
rm -f /tmp/tiktok-scout-bot.lock
rm -f "$PROJECT_DIR/data/.bot-status.json"
ok "Logs and status cleared"

echo ""
divider
echo ""
echo -e "  ${GREEN}${BOLD}Reset complete.${RESET}"
echo ""
echo -e "  Double-click ${BOLD}setup.command${RESET} to set up again."
echo ""
divider
echo ""
echo -e "  Press any key to close..."
read -n 1 -s
