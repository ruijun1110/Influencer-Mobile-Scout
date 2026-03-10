#!/bin/bash
# setup.sh — One-time setup for Influencer Search Agent

set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$PROJECT_DIR/.claude/.env"
ENV_EXAMPLE="$PROJECT_DIR/.claude/.env.example"
PLIST_TEMPLATE="$PROJECT_DIR/.claude/skills/tiktok-lookup/launchd/com.tiktok-lookup-py.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/com.tiktok-scout.plist"
BOT_PY="$PROJECT_DIR/.claude/skills/tiktok-lookup/scripts/bot.py"
SERVICE_LABEL="com.tiktok-scout"

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

# Resolve to absolute path for plist
UV_BIN="$(cd "$(dirname "$UV_BIN")" && pwd)/$(basename "$UV_BIN")"

# Symlink to ~/.local/bin/uv so scripts always find it
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
  echo -e "  ${DIM}Opening System Settings — enable Full Disk Access for your terminal app.${RESET}"
  echo ""
  open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
  echo -e "  ${DIM}After enabling, restart your terminal and run setup again.${RESET}"
  echo -e "  ${DIM}Press any key to continue anyway...${RESET}"
  read -n 1 -s
fi

# ── 4. Install launchd service ──
step "④" "Installing background service"

# Stop existing service
launchctl bootout "gui/$(id -u)/$SERVICE_LABEL" 2>/dev/null || true
# Also clean up legacy Login Item and processes
osascript -e 'tell application "System Events" to delete every login item whose name is "TikTok Scout Bot"' 2>/dev/null || true
pkill -f "start.command.*bot" 2>/dev/null || true
rm -f /tmp/tiktok-scout-bot.lock

# Generate plist with resolved paths
mkdir -p "$HOME/Library/LaunchAgents"
sed \
  -e "s|{{UV_PATH}}|$UV_BIN|g" \
  -e "s|{{BOT_PY}}|$BOT_PY|g" \
  -e "s|{{PROJECT_DIR}}|$PROJECT_DIR|g" \
  "$PLIST_TEMPLATE" > "$PLIST_DEST"
ok "Installed $PLIST_DEST"

# ── 5. Start service ──
step "⑤" "Starting bot"
launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"
sleep 3

# Check if running
if launchctl print "gui/$(id -u)/$SERVICE_LABEL" 2>/dev/null | grep -q "state = running"; then
  ok "Bot is running"
elif [ -f "/tmp/tiktok-lookup.log" ] && tail -3 /tmp/tiktok-lookup.log | grep -q "Watching from rowid"; then
  ok "Bot is running"
else
  echo -e "  ${YELLOW}!${RESET}  Bot may not have started. Check status:"
  echo -e "  ${DIM}    ./status.command${RESET}"
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
