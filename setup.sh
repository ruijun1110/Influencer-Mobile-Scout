#!/bin/bash
# setup.sh — One-time setup for Influencer Search Agent

set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$PROJECT_DIR/.claude/.env"
ENV_EXAMPLE="$PROJECT_DIR/.claude/.env.example"
START_CMD="$PROJECT_DIR/start.command"

# Colors
BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
RESET='\033[0m'

divider() { echo -e "${DIM}──────────────────────────────────────────${RESET}"; }
step()    { echo -e "\n${CYAN}${BOLD}$1${RESET}  ${DIM}$2${RESET}"; }
ok()      { echo -e "  ${GREEN}✓${RESET}  $1"; }
info()    { echo -e "  ${DIM}→  $1${RESET}"; }
err()     { echo -e "  ${RED}✗  $1${RESET}"; }

clear
echo ""
echo -e "${BOLD}  TikTok Influencer Scout — Setup${RESET}"
divider
echo ""

# ── 1. uv ──
step "①" "Checking dependencies"
if command -v uv &>/dev/null; then
  ok "uv $(uv --version | awk '{print $2}') already installed"
else
  info "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v uv &>/dev/null; then
    err "uv install failed. Visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
  ok "uv installed"
fi

# ── 2. .env ──
step "②" "API key setup"
if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  ok "Created .claude/.env"
  echo ""
  echo -e "  ${YELLOW}${BOLD}Opening your config file — add your TikHub API key, then save and close.${RESET}"
  echo -e "  ${DIM}Get a key at: https://tikhub.io${RESET}"
  echo ""
  open -W "$ENV_FILE"
else
  ok ".claude/.env already exists"
fi

# ── 3. Login Item ──
step "③" "Registering auto-start on login"
chmod +x "$START_CMD"
osascript << APPLESCRIPT 2>/dev/null && ok "Login Item registered — bot will start automatically on login" || true
tell application "System Events"
  set existingItems to every login item whose path is "$START_CMD"
  if (count of existingItems) is 0 then
    make new login item at end of login items with properties {path:"$START_CMD", hidden:true, name:"TikTok Scout Bot"}
  end if
end tell
APPLESCRIPT

# ── 4. Start now ──
step "④" "Starting bot"
# Stop any existing launchd instance
launchctl unload "$HOME/Library/LaunchAgents/com.tiktok-lookup.plist" 2>/dev/null || true

# Kill any existing bot processes
pkill -f "bot.py" 2>/dev/null || true
pkill -f "bot.mjs" 2>/dev/null || true
sleep 1

# Start bot in background (inherits Terminal's FDA)
nohup bash "$START_CMD" > /tmp/tiktok-lookup.log 2>&1 &
sleep 3

if tail -3 /tmp/tiktok-lookup.log | grep -q "Watching from rowid"; then
  ok "Bot is running"
else
  echo -e "  ${YELLOW}!${RESET}  Check logs: tail -f /tmp/tiktok-lookup.log"
fi

echo ""
divider
echo ""
echo -e "  ${GREEN}${BOLD}Setup complete.${RESET}"
echo ""
echo -e "  Send a TikTok URL to your Mac via iMessage to test it."
echo -e "  ${DIM}The bot starts automatically on every login.${RESET}"
echo ""
divider
echo ""
