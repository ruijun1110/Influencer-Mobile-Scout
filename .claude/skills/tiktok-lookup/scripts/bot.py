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

import fcntl
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# --- Path setup ---
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ENV_PATH = SKILL_DIR.parents[1] / '.env'
PROJECT_DIR = SKILL_DIR.parents[2]
DATA_DIR = PROJECT_DIR / 'data'
LOOKUP_PY = SCRIPT_DIR / 'lookup.py'
SCOUT_PY = SKILL_DIR.parent / 'scout-api' / 'scripts' / 'scout.py'
KEYWORDS_HELPER_PY = SKILL_DIR.parent / 'scout-api' / 'scripts' / 'keywords_helper.py'
CAMPAIGNS_DIR = PROJECT_DIR / 'context' / 'campaigns'
CHAT_DB = Path.home() / 'Library' / 'Messages' / 'chat.db'
STATUS_FILE = DATA_DIR / '.bot-status.json'
LOG_FILE = Path('/tmp/tiktok-lookup.log')

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


# --- Logging ---
def log(msg: str):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)


# --- Status file ---
_status = {}


def status_update(**kwargs):
    _status.update(kwargs)
    _status['pid'] = os.getpid()
    _status['updated_at'] = datetime.now().isoformat()
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps(_status, indent=2))
    except Exception:
        pass


# --- Startup self-checks ---
def preflight() -> list[str]:
    """Run startup checks. Returns list of fatal errors (empty = all good)."""
    errors = []

    # 1. .env exists and has API key
    api_key = os.environ.get('TIKHUB_API_KEY', '').strip()
    if not api_key:
        errors.append(f'TIKHUB_API_KEY not set. Edit: {ENV_PATH}')
    elif len(api_key) < 10:
        errors.append(f'TIKHUB_API_KEY looks invalid (too short). Edit: {ENV_PATH}')

    # 2. Messages.db readable (Full Disk Access check)
    if not CHAT_DB.exists():
        errors.append(f'Messages database not found: {CHAT_DB}')
    else:
        try:
            con = sqlite3.connect(f'file:{CHAT_DB}?mode=ro', uri=True, timeout=5)
            con.execute('SELECT 1 FROM message LIMIT 1')
            con.close()
        except sqlite3.OperationalError as e:
            if 'unable to open' in str(e) or 'authorization denied' in str(e):
                errors.append(
                    'Cannot read Messages database — Full Disk Access required.\n'
                    '  → System Settings > Privacy & Security > Full Disk Access\n'
                    '  → Enable access for Terminal (or iTerm/your terminal app)\n'
                    '  → Then quit and reopen Terminal, and run: bash setup.command'
                )
            else:
                errors.append(f'Messages database error: {e}')

    # 3. osascript works
    try:
        r = subprocess.run(
            ['osascript', '-e', 'return "ok"'],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            errors.append(f'osascript failed: {r.stderr.strip()}')
    except FileNotFoundError:
        errors.append('osascript not found — this tool requires macOS.')

    # 4. uv available (for spawning scout/lookup)
    # uv runs us, but the venv PATH may not include uv itself.
    # Search common locations and add to PATH if found.
    import shutil
    uv_path = shutil.which('uv')
    if not uv_path:
        for candidate in [
            Path.home() / '.local' / 'bin' / 'uv',
            Path.home() / '.cargo' / 'bin' / 'uv',
            Path('/opt/homebrew/bin/uv'),
            Path('/usr/local/bin/uv'),
        ]:
            if candidate.is_file():
                uv_path = str(candidate)
                os.environ['PATH'] = str(candidate.parent) + ':' + os.environ.get('PATH', '')
                break
    if not uv_path:
        errors.append(f'uv not found on PATH. Run setup.command again.')

    return errors


# --- iMessage send via osascript ---
def send_imessage(recipient: str, text: str):
    # Escape backslashes and double quotes for AppleScript string
    safe = text.replace('\\', '\\\\').replace('"', '\\"')
    script = f'''tell application "Messages"
  set s to 1st service whose service type = iMessage
  send "{safe}" to buddy "{recipient}" of s
end tell'''
    try:
        r = subprocess.run(['osascript', '-e', script], timeout=15, capture_output=True, text=True)
        if r.returncode != 0:
            log(f'send failed to {recipient}: {r.stderr.strip()}')
    except Exception as e:
        log(f'send error to {recipient}: {e}')


# --- Campaign helpers ---
def resolve_campaign(raw: str) -> str | None:
    try:
        if not CAMPAIGNS_DIR.exists():
            return None
        dirs = [d for d in CAMPAIGNS_DIR.iterdir() if d.is_dir() and not d.name.startswith('_')]
        match = next((d.name for d in dirs if d.name.lower() == raw.lower()), None)
        return match
    except Exception:
        return None


def list_campaigns() -> list[str]:
    try:
        if not CAMPAIGNS_DIR.exists():
            return []
        return [d.name for d in CAMPAIGNS_DIR.iterdir()
                if d.is_dir() and not d.name.startswith('_')]
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
        log(f'spawned scout PID {proc.pid} campaign={campaign}' +
              (f' keyword="{keyword}"' if keyword else ''))
    except Exception as e:
        log(f'scout spawn error: {e}')
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
        log(f'short URL resolve error: {e}')
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
            log(f'could not resolve short URL t/{short_id}')
            send_imessage(sender, f"Sorry, couldn't resolve that TikTok link. Try sending the full profile URL instead.")
            return

    log(f'TikTok URL from {sender}: @{handle}')
    status_update(last_message=f'@{handle} from {sender}', last_message_at=datetime.now().isoformat())
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
        log(f'replied to {sender} for @{handle}')
    except Exception as e:
        log(f'lookup error for @{handle}: {e}')
        status_update(last_error=str(e), last_error_at=datetime.now().isoformat())
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
        if rows:
            log(f'{len(rows)} new message(s)')
        for rowid, text, sender in rows:
            last_rowid = max(last_rowid, rowid)
            handle_message(sender, text)
        status_update(last_poll=datetime.now().isoformat(), state='running')
    except sqlite3.OperationalError as e:
        if 'database is locked' in str(e):
            log('chat.db locked, will retry next cycle')
        else:
            log(f'db error: {e}')
            status_update(last_error=str(e), last_error_at=datetime.now().isoformat())
    except Exception as e:
        log(f'db error: {e}')
        status_update(last_error=str(e), last_error_at=datetime.now().isoformat())
    return last_rowid


def get_latest_rowid() -> int:
    try:
        con = sqlite3.connect(f'file:{CHAT_DB}?mode=ro', uri=True, timeout=5)
        row = con.execute('SELECT MAX(rowid) FROM message').fetchone()
        con.close()
        return row[0] or 0
    except Exception:
        return 0


LOCK_FILE = Path('/tmp/tiktok-scout-bot.lock')


def acquire_lock():
    """Acquire an exclusive file lock. Exits if another instance is running."""
    try:
        lock_fd = open(LOCK_FILE, 'w')
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Write our PID for status.command to read
        lock_fd.truncate()
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        os.fsync(lock_fd.fileno())
        # Keep fd open — lock is released when process exits (any reason)
        return lock_fd
    except OSError:
        # Another instance holds the lock
        try:
            existing_pid = LOCK_FILE.read_text().strip()
        except Exception:
            existing_pid = '?'
        log(f'Another instance is already running (PID {existing_pid}). Exiting.')
        sys.exit(0)


# --- Main ---
def main():
    lock_fd = acquire_lock()  # noqa: F841 — must keep reference alive
    log('Starting iMessage watcher...')
    status_update(state='starting', started_at=datetime.now().isoformat())

    # Preflight checks
    errors = preflight()
    if errors:
        log('PREFLIGHT FAILED:')
        for e in errors:
            for line in e.split('\n'):
                log(f'  {line}')
        status_update(state='error', errors=errors)
        sys.exit(1)

    log('Preflight OK')
    last_rowid = get_latest_rowid()
    log(f'Watching from rowid {last_rowid}')
    status_update(state='running', last_poll=datetime.now().isoformat())

    while True:
        last_rowid = poll(last_rowid)
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log('Stopped.')
        status_update(state='stopped')
        sys.exit(0)
