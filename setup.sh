#!/bin/bash
# setup.sh — One-time setup for Influencer Search Agent
# Run from project root: bash setup.sh

set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$PROJECT_DIR/.claude/.env"
ENV_EXAMPLE="$PROJECT_DIR/.claude/.env.example"
PLIST_TEMPLATE="$PROJECT_DIR/.claude/skills/tiktok-lookup/launchd/com.tiktok-lookup-py.plist.template"
PLIST_OUT="$PROJECT_DIR/.claude/skills/tiktok-lookup/launchd/com.tiktok-lookup.plist"
BOT_PY="$PROJECT_DIR/.claude/skills/tiktok-lookup/scripts/bot.py"

echo "=== Influencer Search Agent Setup ==="
echo ""

# --- 1. Check uv ---
if command -v uv &>/dev/null; then
  echo "[1/4] uv found: $(uv --version)"
else
  echo "[1/4] Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$PATH"
  if ! command -v uv &>/dev/null; then
    echo "ERROR: uv install failed. Install manually: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
  echo "      uv installed: $(uv --version)"
fi

UV_PATH="$(command -v uv)"

# --- 2. Generate plist from template ---
echo "[2/4] Generating launchd plist..."
sed \
  -e "s|{{UV_PATH}}|$UV_PATH|g" \
  -e "s|{{BOT_PY}}|$BOT_PY|g" \
  -e "s|{{PROJECT_DIR}}|$PROJECT_DIR|g" \
  "$PLIST_TEMPLATE" > "$PLIST_OUT"
echo "      Written: $PLIST_OUT"

# --- 3. Create .env from example if missing ---
echo "[3/4] Checking .env..."
if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "      Created .claude/.env from template."
  echo ""
  echo ">>> Opening .env for editing — fill in your API keys, then save and close."
  open -W "$ENV_FILE"
  echo ""
else
  echo "      .claude/.env already exists — skipping."
fi

# --- 4. Full Disk Access reminder ---
echo "[4/4] Manual step required:"
echo "      Grant Full Disk Access to Terminal (or your terminal app):"
echo "      System Settings → Privacy & Security → Full Disk Access → enable Terminal"
echo ""
echo "=== Setup complete ==="
echo ""
echo "Next: open Claude Code and run /tiktok-lookup start"
