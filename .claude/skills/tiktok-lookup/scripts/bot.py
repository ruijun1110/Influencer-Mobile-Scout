# /// script
# dependencies = ["httpx", "python-dotenv"]
# ///
"""
bot.py — TikTok Similar Creator iMessage Bot (osascript edition)

Polls ~/Library/Messages/chat.db for new incoming messages.
Handles TikTok URL lookups and scout commands.
Sends replies via osascript — no Node.js required.

Run: uv run bot.py
"""

import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

# --- Path setup ---
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ENV_PATH = SKILL_DIR.parents[1] / '.env'
DATA_DIR = SKILL_DIR.parents[2] / 'data'
LOOKUP_PY = SCRIPT_DIR / 'lookup.py'
SCOUT_PY = SKILL_DIR.parent / 'scout-api' / 'scripts' / 'scout.py'
KEYWORDS_HELPER_PY = SKILL_DIR.parent / 'scout-api' / 'scripts' / 'keywords_helper.py'
CAMPAIGNS_DIR = SKILL_DIR.parents[2] / 'context' / 'campaigns'
CHAT_DB = Path.home() / 'Library' / 'Messages' / 'chat.db'

# --- Load .env ---
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

# --- Patterns ---
TIKTOK_URL_RE = re.compile(r'tiktok\.com/(?:@([\w.]+)|t/([\w]+))', re.IGNORECASE)
SCOUT_RE = re.compile(r'^scout\s+#(\w+)(?:\s+(.+))?$', re.IGNORECASE)

POLL_INTERVAL = 3  # seconds


# --- iMessage send via osascript ---
def send_imessage(recipient: str, text: str):
    # Escape backslashes and double quotes for AppleScript string
    safe = text.replace('\\', '\\\\').replace('"', '\\"')
    script = f'''tell application "Messages"
  set s to 1st service whose service type = iMessage
  send "{safe}" to buddy "{recipient}" of s
end tell'''
    try:
        subprocess.run(['osascript', '-e', script], timeout=15, capture_output=True)
    except Exception as e:
        print(f'[bot] send error to {recipient}: {e}', flush=True)


# --- Campaign helpers ---
def resolve_campaign(raw: str) -> str | None:
    try:
        dirs = [d for d in CAMPAIGNS_DIR.iterdir() if d.is_dir()]
        match = next((d.name for d in dirs if d.name.lower() == raw.lower()), None)
        return match
    except Exception:
        return None


def list_campaigns() -> list[str]:
    try:
        return [d.name for d in CAMPAIGNS_DIR.iterdir() if d.is_dir()]
    except Exception:
        return []


def get_pending_count(campaign: str) -> int:
    try:
        result = subprocess.run(
            ['uv', 'run', str(KEYWORDS_HELPER_PY), 'pending', campaign],
            capture_output=True, text=True, timeout=10,
        )
        return int(result.stdout.strip()) if result.returncode == 0 else 0
    except Exception:
        return 0


# --- Scout spawn ---
def spawn_scout(campaign: str, keyword: str | None, sender: str):
    args = ['uv', 'run', str(SCOUT_PY), campaign]
    if keyword:
        args.append(keyword)
    try:
        proc = subprocess.Popen(args, env=os.environ.copy(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f'[bot] spawned scout PID {proc.pid} campaign={campaign}' +
              (f' keyword="{keyword}"' if keyword else ''), flush=True)
    except Exception as e:
        print(f'[bot] scout spawn error: {e}', flush=True)
        send_imessage(sender, f'Failed to start scout for #{campaign}: {e}')


# --- Short URL resolution ---
def resolve_short_url(short_id: str) -> str | None:
    """Resolve tiktok.com/t/<id> to a handle via redirect + TikHub API if needed."""
    try:
        import httpx
        resp = httpx.head(f'https://www.tiktok.com/t/{short_id}',
                          follow_redirects=True, timeout=10)
        url = str(resp.url)
        # Direct handle in redirect URL
        m = re.search(r'tiktok\.com/@([\w.]+)/video', url, re.IGNORECASE)
        if m:
            return m.group(1)
        # No handle — resolve via TikHub post detail
        vid_m = re.search(r'/video/(\d+)', url)
        if not vid_m:
            return None
        video_id = vid_m.group(1)
        api_key = os.environ.get('TIKHUB_API_KEY')
        detail = httpx.get(
            f'https://api.tikhub.io/api/v1/tiktok/web/fetch_post_detail',
            params={'itemId': video_id},
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=15,
        ).json()
        return detail.get('data', {}).get('itemInfo', {}).get('itemStruct', {}).get('author', {}).get('uniqueId')
    except Exception as e:
        print(f'[bot] short URL resolve error: {e}', flush=True)
        return None


# --- Message handler ---
def handle_message(sender: str, text: str):
    # Scout command
    scout_m = SCOUT_RE.match(text.strip())
    if scout_m:
        raw_campaign = scout_m.group(1)
        keyword = scout_m.group(2).strip() if scout_m.group(2) else None
        campaign = resolve_campaign(raw_campaign)
        if not campaign:
            available = ', '.join(list_campaigns()) or 'none'
            send_imessage(sender, f"Campaign '#{raw_campaign}' not found.\nAvailable: {available}")
            return
        if keyword:
            send_imessage(sender, f'Starting scout: #{campaign} "{keyword}"...')
            spawn_scout(campaign, keyword, sender)
        else:
            pending = get_pending_count(campaign)
            if pending == 0:
                send_imessage(sender, f'No pending keywords for #{campaign}.')
            else:
                send_imessage(sender, f'Starting scout: #{campaign} ({pending} pending keyword{"s" if pending != 1 else ""})...')
                spawn_scout(campaign, None, sender)
        return

    # TikTok URL
    url_m = TIKTOK_URL_RE.search(text)
    if not url_m:
        return

    handle = url_m.group(1)
    short_id = url_m.group(2)

    if not handle and short_id:
        handle = resolve_short_url(short_id)
        if not handle:
            print(f'[bot] could not resolve short URL t/{short_id}', flush=True)
            return

    print(f'[bot] TikTok URL from {sender}: @{handle}', flush=True)
    send_imessage(sender, f'Looking up similar creators for @{handle}...')

    try:
        result = subprocess.run(
            ['uv', 'run', str(LOOKUP_PY), handle, sender, str(DATA_DIR)],
            capture_output=True, text=True, timeout=30,
            env=os.environ.copy(),
        )
        output = result.stdout.strip()
        # Parse structured output: __HEADER__<text>\n__URLS__\n<urls>
        m = re.match(r'^__HEADER__(.*?)(?:\n__URLS__\n([\s\S]*))?$', output)
        if m:
            header = m.group(1).strip()
            urls = ('\n' + m.group(2).strip()) if m.group(2) else ''
            send_imessage(sender, header + urls)
        else:
            send_imessage(sender, output or 'No results.')
        print(f'[bot] replied to {sender} for @{handle}', flush=True)
    except Exception as e:
        print(f'[bot] lookup error for @{handle}: {e}', flush=True)
        send_imessage(sender, f"Sorry, couldn't find similar creators for @{handle}. Try again later.")


# --- DB polling ---
def poll(last_rowid: int) -> int:
    try:
        con = sqlite3.connect(f'file:{CHAT_DB}?mode=ro', uri=True,
                              check_same_thread=False, timeout=5)
        cur = con.execute('''
            SELECT m.rowid, m.text, h.id
            FROM message m
            JOIN handle h ON m.handle_id = h.rowid
            WHERE m.rowid > ?
              AND m.is_from_me = 0
              AND m.text IS NOT NULL
            ORDER BY m.rowid ASC
        ''', (last_rowid,))
        rows = cur.fetchall()
        con.close()
        for rowid, text, sender in rows:
            last_rowid = max(last_rowid, rowid)
            handle_message(sender, text)
    except Exception as e:
        print(f'[bot] db error: {e}', flush=True)
    return last_rowid


def get_latest_rowid() -> int:
    try:
        con = sqlite3.connect(f'file:{CHAT_DB}?mode=ro', uri=True, timeout=5)
        row = con.execute('SELECT MAX(rowid) FROM message').fetchone()
        con.close()
        return row[0] or 0
    except Exception:
        return 0


# --- Main ---
def main():
    print('[bot] Starting iMessage watcher (osascript edition)...', flush=True)
    last_rowid = get_latest_rowid()
    print(f'[bot] Watching from rowid {last_rowid}', flush=True)

    while True:
        last_rowid = poll(last_rowid)
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('[bot] Stopped.', flush=True)
        sys.exit(0)
