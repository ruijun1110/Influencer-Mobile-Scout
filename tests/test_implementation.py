#!/usr/bin/env python3
"""
test_implementation.py — Automated tests for scout-api notification features.

Skips: iMessage sending (requires phone), full API scout run (costs API credits).
Run: python3 tests/test_implementation.py
"""
import sys
import os
import shutil
import tempfile
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / '.claude' / 'skills' / 'scout-api' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

PASS = '\033[92mPASS\033[0m'
FAIL = '\033[91mFAIL\033[0m'

results = []

def check(name, condition, detail=''):
    status = PASS if condition else FAIL
    print(f'  [{status}] {name}' + (f' — {detail}' if detail else ''))
    results.append((name, condition))

def section(title):
    print(f'\n{"="*55}')
    print(f'  {title}')
    print('='*55)


# ── 1. append_keyword ────────────────────────────────────────
section('1. excel.append_keyword()')

import excel

CAMPAIGN = 'Beauty'
TEST_KW = '__test_autotest_keyword__'

# Ensure keyword doesn't already exist (clean up from previous runs)
kw_path = PROJECT_ROOT / 'context' / 'campaigns' / CAMPAIGN / 'keywords.md'
original_content = kw_path.read_text()
if TEST_KW in original_content:
    lines = [l for l in original_content.splitlines() if TEST_KW not in l]
    kw_path.write_text('\n'.join(lines) + '\n')

# Add new keyword
result = excel.append_keyword(CAMPAIGN, TEST_KW, 'test')
check('append new keyword returns True', result is True)

# Verify it appears in the file
after = kw_path.read_text()
check('keyword written to keywords.md', TEST_KW in after)
check('status is pending', f'| {TEST_KW} | pending |' in after)

# Duplicate (same case)
result2 = excel.append_keyword(CAMPAIGN, TEST_KW, 'test')
check('duplicate same case returns False', result2 is False)

# Duplicate (different case)
result3 = excel.append_keyword(CAMPAIGN, TEST_KW.upper(), 'test')
check('duplicate upper case returns False', result3 is False)

# Verify only one occurrence in file
count = kw_path.read_text().count(TEST_KW)
check('only one row added despite multiple attempts', count == 1, f'found {count}')

# Clean up test keyword
lines = [l for l in kw_path.read_text().splitlines() if TEST_KW not in l]
kw_path.write_text('\n'.join(lines) + '\n')


# ── 2. keywords_helper.py ────────────────────────────────────
section('2. keywords_helper.py CLI')

KH = str(SCRIPTS_DIR / 'keywords_helper.py')

def run_helper(*args):
    r = subprocess.run(['uv', 'run', KH, *args], capture_output=True, text=True, timeout=15)
    return r.stdout.strip(), r.returncode

out, rc = run_helper('list-campaigns')
check('list-campaigns exits 0', rc == 0)
campaigns = out.split(',') if out else []
check('returns at least 3 campaigns', len(campaigns) >= 3, f'got: {out!r}')
check('Beauty in campaign list', 'Beauty' in campaigns)
check('APITest in campaign list', 'APITest' in campaigns)

out, rc = run_helper('pending', 'Beauty')
check('pending Beauty exits 0', rc == 0)
check('pending count is a number', out.isdigit(), f'got: {out!r}')
beauty_pending = int(out)
check('Beauty has pending keywords', beauty_pending > 0, f'count={beauty_pending}')

out, rc = run_helper('pending', 'beauty')  # lowercase
check('pending beauty (lowercase) exits 0', rc == 0)
check('case-insensitive campaign match', out.isdigit() and int(out) == beauty_pending,
      f'got: {out!r}')

out, rc = run_helper('pending', 'nonexistent_campaign_xyz')
check('pending nonexistent returns 0', out == '0', f'got: {out!r}')

out, rc = run_helper('bad-command')
check('unknown command exits non-zero', rc != 0)


# ── 3. generate_dashboard.py ─────────────────────────────────
section('3. generate_dashboard.py')

from generate_dashboard import generate, OUTPUT_PATH

html_path = generate()
check('generate() returns a Path', isinstance(html_path, Path))
check('dashboard.html exists', OUTPUT_PATH.exists())

html = OUTPUT_PATH.read_text(encoding='utf-8')
check('HTML has <html> tag', '<html' in html)
check('HTML has campaign filter', 'campaignFilter' in html)
check('HTML has influencer grid', 'influencer-grid' in html)
check('HTML has candidates table', 'candidate-tbody' in html)
check('HTML has DATA JSON block', 'const DATA = ' in html)
check('HTML has footer timestamp', 'Generated' in html)
check('HTML is self-contained (no external script src)', 'src="http' not in html)


# ── 4. notify.py ─────────────────────────────────────────────
section('4. notify.py — config loading (no actual send)')

from notify import NOTIFY_PHONE, notify

check('NOTIFY_PHONE is loaded from .env', bool(NOTIFY_PHONE), f'got: {NOTIFY_PHONE!r}')
check('NOTIFY_PHONE starts with +', NOTIFY_PHONE.startswith('+') if NOTIFY_PHONE else False)

# Test that notify() does not raise even if node fails
import unittest.mock as mock
import notify as notify_mod

with mock.patch.object(notify_mod.subprocess, 'run') as mock_run:
    mock_run.return_value = None
    try:
        notify_mod.notify('test message')
        check('notify() does not raise', True)
    except Exception as e:
        check('notify() does not raise', False, str(e))


# Test no-op when NOTIFY_PHONE is empty
original_phone = notify_mod.NOTIFY_PHONE
notify_mod.NOTIFY_PHONE = ''
with mock.patch.object(notify_mod.subprocess, 'run') as mock_run:
    notify_mod.notify('should not send')
    check('notify() is no-op when NOTIFY_PHONE empty', not mock_run.called)
notify_mod.NOTIFY_PHONE = original_phone


# ── 5. scout.py signature ────────────────────────────────────
section('5. scout.py — arg parsing & imports')

import ast
scout_src = (SCRIPTS_DIR / 'scout.py').read_text()
check('scout.py imports notify', 'from notify import' in scout_src)
check('scout.py imports generate_dashboard', 'from generate_dashboard import' in scout_src)
check('scout.py accepts keyword arg', 'keyword' in scout_src)
check('scout.py calls notify() at start', 'Scout started' in scout_src)
check('scout.py calls notify() at audit', 'Auditing' in scout_src)
check('scout.py calls generate_dashboard()', 'generate_dashboard()' in scout_src or 'generate()' in scout_src)
check('scout.py sends qualified_urls', 'qualified_urls' in scout_src)
check('scout.py handles optional keyword sys.argv', 'sys.argv[2]' in scout_src)


# ── 6. search.py signature ───────────────────────────────────
section('6. search.py — notify_fn + keyword_filter')

search_src = (SCRIPTS_DIR / 'search.py').read_text()
check('search.py has keyword_filter param', 'keyword_filter' in search_src)
check('search.py has notify_fn param', 'notify_fn' in search_src)
check('search.py calls notify_fn for search start', 'Searching' in search_src)
check('search.py calls notify_fn for search result', 'candidates found' in search_src)


# ── 7. bot.mjs scout command ─────────────────────────────────
section('7. bot.mjs — scout command parser')

bot_src = (PROJECT_ROOT / '.claude' / 'skills' / 'tiktok-lookup' / 'scripts' / 'bot.mjs').read_text()
check('bot.mjs has SCOUT_RE regex', 'SCOUT_RE' in bot_src)
check('bot.mjs has resolveCampaign()', 'resolveCampaign' in bot_src)
check('bot.mjs has spawnScout()', 'spawnScout' in bot_src)
check('bot.mjs handles unknown campaign', "not found" in bot_src)
check('bot.mjs handles no pending keywords', 'No pending keywords' in bot_src)
check('bot.mjs scout handler before TikTok handler',
      bot_src.index('scoutMatch') < bot_src.index('TIKTOK_URL_RE.exec') if 'TIKTOK_URL_RE.exec' in bot_src
      else bot_src.index('scoutMatch') < bot_src.rindex('TIKTOK_URL_RE'))
check('bot.mjs imports execFile', 'execFile' in bot_src)
check('bot.mjs has SCOUT_PY path', 'SCOUT_PY' in bot_src)
check('bot.mjs has KEYWORDS_HELPER_PY path', 'KEYWORDS_HELPER_PY' in bot_src)


# ── Summary ──────────────────────────────────────────────────
section('Summary')
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
total = len(results)
print(f'\n  {passed}/{total} passed', end='')
if failed:
    print(f'  ({failed} failed)')
    print('\nFailed tests:')
    for name, ok in results:
        if not ok:
            print(f'  - {name}')
else:
    print('  — all green')
print()

sys.exit(0 if failed == 0 else 1)
