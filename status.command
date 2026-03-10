#!/bin/bash
# status.command — Show bot status and recent logs
cd "$(dirname "$0")"

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
RESET='\033[0m'

SERVICE_LABEL="com.tiktok-scout"
STATUS_FILE="data/.bot-status.json"
LOG_FILE="/tmp/tiktok-lookup.log"
ERR_FILE="/tmp/tiktok-lookup.err"

divider() { echo -e "${DIM}──────────────────────────────────────────${RESET}"; }

clear
echo ""
echo -e "${BOLD}  TikTok Influencer Scout — Status${RESET}"
divider
echo ""

# --- Service status via launchctl ---
if launchctl print "gui/$(id -u)/$SERVICE_LABEL" 2>/dev/null | grep -q "state = running"; then
  PID=$(launchctl print "gui/$(id -u)/$SERVICE_LABEL" 2>/dev/null | grep "pid =" | awk '{print $3}')
  echo -e "  Status:    ${GREEN}● Running${RESET} (PID $PID)"
else
  # Check if service is loaded but not running
  if launchctl print "gui/$(id -u)/$SERVICE_LABEL" 2>/dev/null | grep -q "state ="; then
    STATE=$(launchctl print "gui/$(id -u)/$SERVICE_LABEL" 2>/dev/null | grep "state =" | awk '{print $3}')
    echo -e "  Status:    ${RED}● Not running${RESET} (state: $STATE)"
  else
    echo -e "  Status:    ${RED}● Not installed${RESET}"
    echo -e "  ${DIM}Run setup.command to install.${RESET}"
  fi
fi

# --- Status file details ---
if [ -f "$STATUS_FILE" ]; then
  echo ""

  # Parse JSON with python (available on all Macs)
  python3 -c "
import json, sys
from datetime import datetime
try:
    s = json.load(open('$STATUS_FILE'))
    started = s.get('started_at', '')
    if started:
        t = datetime.fromisoformat(started)
        d = datetime.now() - t
        h, m = divmod(int(d.total_seconds()) // 60, 60)
        print(f'  Uptime:    {h}h {m}m' if h else f'  Uptime:    {m}m')
    last_poll = s.get('last_poll', '')
    if last_poll:
        t = datetime.fromisoformat(last_poll)
        ago = int((datetime.now() - t).total_seconds())
        print(f'  Last poll: {ago}s ago')
    last_msg = s.get('last_message', '')
    last_msg_at = s.get('last_message_at', '')
    if last_msg:
        ago = ''
        if last_msg_at:
            t = datetime.fromisoformat(last_msg_at)
            mins = int((datetime.now() - t).total_seconds()) // 60
            ago = f' ({mins}m ago)' if mins else ' (just now)'
        print(f'  Last msg:  {last_msg}{ago}')
    last_err = s.get('last_error', '')
    last_err_at = s.get('last_error_at', '')
    errors = s.get('errors', [])
    if errors:
        print(f'  Errors:    {len(errors)} preflight error(s)')
        for e in errors:
            for line in e.split(chr(10)):
                print(f'             {line}')
    elif last_err:
        ago = ''
        if last_err_at:
            t = datetime.fromisoformat(last_err_at)
            mins = int((datetime.now() - t).total_seconds()) // 60
            ago = f' ({mins}m ago)'
        print(f'  Last err:  {last_err}{ago}')
    else:
        print(f'  Errors:    none')
except Exception as e:
    print(f'  (status file parse error: {e})')
" 2>/dev/null
fi

# --- Recent logs ---
echo ""
divider
echo -e "  ${CYAN}Recent log:${RESET}"
echo ""
if [ -f "$LOG_FILE" ]; then
  tail -15 "$LOG_FILE" | while IFS= read -r line; do
    echo -e "  ${DIM}$line${RESET}"
  done
else
  echo -e "  ${DIM}(no log file yet)${RESET}"
fi

# --- Recent errors ---
if [ -f "$ERR_FILE" ] && [ -s "$ERR_FILE" ]; then
  echo ""
  divider
  echo -e "  ${RED}Recent errors:${RESET}"
  echo ""
  tail -10 "$ERR_FILE" | while IFS= read -r line; do
    echo -e "  ${RED}$line${RESET}"
  done
fi

echo ""
divider
echo ""
echo -e "  ${DIM}Commands:${RESET}"
echo -e "  ${DIM}  Restart:  launchctl kickstart -k gui/$(id -u)/$SERVICE_LABEL${RESET}"
echo -e "  ${DIM}  Stop:     launchctl bootout gui/$(id -u)/$SERVICE_LABEL${RESET}"
echo -e "  ${DIM}  Logs:     tail -f $LOG_FILE${RESET}"
echo ""
echo -e "  Press any key to close..."
read -n 1 -s
