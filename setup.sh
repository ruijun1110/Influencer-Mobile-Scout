#!/bin/bash
# setup.sh — One-time setup for Influencer Search Agent

set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$PROJECT_DIR/.claude/.env"
ENV_EXAMPLE="$PROJECT_DIR/.claude/.env.example"
PLIST_TEMPLATE="$PROJECT_DIR/.claude/skills/tiktok-lookup/launchd/com.tiktok-lookup-py.plist.template"
PLIST_OUT="$PROJECT_DIR/.claude/skills/tiktok-lookup/launchd/com.tiktok-lookup.plist"
BOT_PY="$PROJECT_DIR/.claude/skills/tiktok-lookup/scripts/bot.py"

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
warn()    { echo -e "  ${YELLOW}!${RESET}  $1"; }
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
  export PATH="$HOME/.cargo/bin:$PATH"
  if ! command -v uv &>/dev/null; then
    err "uv install failed. Visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
  ok "uv installed"
fi

UV_PATH="$(command -v uv)"

# ── 2. Plist ──
step "②" "Configuring background service"
sed \
  -e "s|{{UV_PATH}}|$UV_PATH|g" \
  -e "s|{{BOT_PY}}|$BOT_PY|g" \
  -e "s|{{PROJECT_DIR}}|$PROJECT_DIR|g" \
  "$PLIST_TEMPLATE" > "$PLIST_OUT"
ok "Service configured for this machine"

# ── 3. .env ──
step "③" "API key setup"
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

# ── 4. Full Disk Access ──
step "④" "Manual step required"
echo ""
echo -e "  The iMessage bot needs access to your Messages database."
echo -e "  ${BOLD}Please grant Full Disk Access to Terminal:${RESET}"
echo ""
echo -e "  ${CYAN}System Settings → Privacy & Security → Full Disk Access → enable Terminal${RESET}"
echo ""
echo -e "  ${DIM}(This is a one-time macOS security step — cannot be automated)${RESET}"

echo ""
divider
echo ""
echo -e "  ${GREEN}${BOLD}Setup complete.${RESET}"
echo ""
echo -e "  Once Full Disk Access is granted, the iMessage bot will be"
echo -e "  ready to receive TikTok URLs and scout commands."
echo ""
divider
echo ""
