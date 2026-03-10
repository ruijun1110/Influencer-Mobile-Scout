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
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Find uv wherever it may be installed
UV_BIN="$(command -v uv 2>/dev/null || true)"
if [ -z "$UV_BIN" ]; then
  for candidate in \
    "$HOME/.local/bin/uv" \
    "$HOME/.cargo/bin/uv" \
    "/opt/homebrew/bin/uv" \
    "/usr/local/bin/uv"; do
    if [ -x "$candidate" ]; then
      UV_BIN="$candidate"
      break
    fi
  done
fi

if [ -n "$UV_BIN" ]; then
  ok "uv $("$UV_BIN" --version | awk '{print $2}') found at $UV_BIN"
else
  info "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  UV_BIN="$HOME/.local/bin/uv"
  if [ ! -x "$UV_BIN" ]; then
    err "uv install failed. Visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
  ok "uv installed"
fi

# Symlink to ~/.local/bin/uv so start.command always finds it
mkdir -p "$HOME/.local/bin"
if [ "$UV_BIN" != "$HOME/.local/bin/uv" ]; then
  ln -sf "$UV_BIN" "$HOME/.local/bin/uv"
  info "Linked uv to ~/.local/bin/uv"
fi

# ── 2. .env ──
step "②" "API key setup"
if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  ok "Created .claude/.env"
  echo ""
  echo -e "  ${YELLOW}${BOLD}Opening your config file — add your TikHub API key, then save it.${RESET}"
  echo -e "  ${DIM}Get a key at: https://tikhub.io${RESET}"
  echo ""
  open "$ENV_FILE"
  echo -e "  ${DIM}Press any key once you've saved your API key...${RESET}"
  read -n 1 -s
else
  ok ".claude/.env already exists"
fi

# ── 3. Full Disk Access check ──
step "③" "Checking permissions"
CHAT_DB="$HOME/Library/Messages/chat.db"
if [ -r "$CHAT_DB" ]; then
  ok "Messages database readable (Full Disk Access OK)"
else
  echo ""
  echo -e "  ${YELLOW}${BOLD}Full Disk Access is required to read iMessages.${RESET}"
  echo ""
  echo -e "  ${DIM}Grant Full Disk Access to your terminal app:${RESET}"
  echo -e "  ${DIM}  System Settings > Privacy & Security > Full Disk Access${RESET}"
  echo -e "  ${DIM}  Enable: Terminal (or iTerm / your terminal app)${RESET}"
  echo ""
  echo -e "  ${DIM}Opening System Settings now...${RESET}"
  open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
  echo -e "  ${DIM}After enabling, quit and reopen Terminal, then run setup again.${RESET}"
  echo ""
  echo -e "  ${DIM}Press any key to continue anyway...${RESET}"
  read -n 1 -s
fi

# ── 4. Register Login Item ──
step "④" "Registering auto-start on login"
chmod +x "$START_CMD"

# Remove legacy launchd service if present
launchctl bootout "gui/$(id -u)/com.tiktok-scout" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.tiktok-scout.plist"

osascript << APPLESCRIPT 2>/dev/null && ok "Login Item registered — bot starts automatically on login" || true
tell application "System Events"
  set existingItems to every login item whose path is "$START_CMD"
  if (count of existingItems) is 0 then
    make new login item at end of login items with properties {path:"$START_CMD", hidden:true, name:"TikTok Scout Bot"}
  end if
end tell
APPLESCRIPT

# ── 5. Start now ──
step "⑤" "Starting bot"

# Kill any existing bot processes
# Kill by lock file PID (most reliable — catches uv-spawned python)
if [ -f /tmp/tiktok-scout-bot.lock ]; then
  BOT_PID=$(cat /tmp/tiktok-scout-bot.lock 2>/dev/null)
  [ -n "$BOT_PID" ] && kill "$BOT_PID" 2>/dev/null
fi
pkill -f "tiktok-lookup/scripts/bot.py" 2>/dev/null || true
pkill -f "start.command" 2>/dev/null || true
rm -f /tmp/tiktok-scout-bot.lock
sleep 1

# Start in background — inherits Terminal's Full Disk Access
nohup bash "$START_CMD" >> /tmp/tiktok-lookup.log 2>&1 &
sleep 3

if [ -f "/tmp/tiktok-lookup.log" ] && tail -3 /tmp/tiktok-lookup.log | grep -q "Watching from rowid"; then
  ok "Bot is running"
else
  echo -e "  ${YELLOW}!${RESET}  Check status: ./status.command"
fi

echo ""
divider
echo ""
echo -e "  ${GREEN}${BOLD}Setup complete.${RESET}"
echo ""
echo -e "  Send a TikTok URL to your Mac via iMessage to test it."
echo -e "  ${DIM}The bot starts automatically on every login.${RESET}"
echo -e "  ${DIM}Check status anytime: double-click ${BOLD}status.command${RESET}"
echo ""
divider
echo ""
