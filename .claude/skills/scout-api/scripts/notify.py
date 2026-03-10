#!/usr/bin/env python3
"""
notify.py — iMessage notification helper for scout-api.

Reads NOTIFY_PHONE from .env. If not set, all calls are no-ops.
Uses the IMessageSDK via a small inline Node.js script.

Usage:
    from notify import notify

    notify("Scout started")
"""
import os
import subprocess
from pathlib import Path

# Resolve paths
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[3]
_ENV_PATH = _PROJECT_ROOT / '.claude' / '.env'

# Load NOTIFY_PHONE from .env if not already in environment
if 'NOTIFY_PHONE' not in os.environ and _ENV_PATH.exists():
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            if k.strip() == 'NOTIFY_PHONE':
                os.environ['NOTIFY_PHONE'] = v.strip()
                break

NOTIFY_PHONE = os.environ.get('NOTIFY_PHONE', '').strip()


def notify(text: str):
    """Send a text iMessage via osascript. No-op if NOTIFY_PHONE is not set."""
    if not NOTIFY_PHONE:
        return
    safe = text.replace('\\', '\\\\').replace('"', '\\"')
    script = f'''tell application "Messages"
  set s to 1st service whose service type = iMessage
  send "{safe}" to buddy "{NOTIFY_PHONE}" of s
end tell'''
    try:
        subprocess.run(['osascript', '-e', script], timeout=15, capture_output=True)
    except Exception as e:
        print(f"[notify] warning: {e}")


