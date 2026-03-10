# Implementation Plan — Scout Notifications, iMessage Trigger & Dashboard

**Date**: 2026-03-09
**Status**: Planning

---

## Overview

Three connected features:
1. **iMessage progress notifications** during `scout-api` runs
2. **iMessage → scout trigger** via `bot.mjs` command parsing
3. **HTML dashboard** generated after each run, sent via iMessage

---

## Architecture

```
bot.mjs (always running)
  │
  ├── detects TikTok URL → existing lookup flow
  │
  └── detects "scout #Campaign keyword" →
        ├── resolve campaign (case-insensitive folder match)
        ├── call keywords_helper.py append → keywords.md
        └── spawn: uv run scout.py <Campaign>
                    │
                    ├── notify.py → iMessage progress updates
                    ├── search.py (concurrent keyword search)
                    ├── audit.py (concurrent profile audit)
                    ├── generate_dashboard.py → data/dashboard.html
                    └── notify.py → send summary + attach HTML
```

---

## New Files

| File | Purpose |
|---|---|
| `.claude/skills/scout-api/scripts/notify.py` | iMessage notification helper |
| `.claude/skills/scout-api/scripts/keywords_helper.py` | CLI wrapper: append/list keywords, resolve campaign |
| `.claude/skills/scout-api/scripts/generate_dashboard.py` | Reads xlsx → outputs `data/dashboard.html` |

---

## Changed Files

| File | Changes |
|---|---|
| `scout-api/scripts/scout.py` | Accept optional keyword arg, append+filter when given, add notify calls, call dashboard gen at end |
| `scout-api/scripts/excel.py` | Add `append_keyword(campaign, keyword)` function |
| `bot.mjs` | Add scout command parser alongside TikTok URL handler |
| `.claude/.env` | Add `NOTIFY_PHONE=+1xxxxxxxxxx` |
| `context/PROJECT.md` | Update with new features |

---

## Keyword Processing Logic

```
scout.py <campaign> [keyword]
  │
  ├── keyword given:
  │     append_keyword(campaign, keyword) → keywords.md
  │     search only that keyword (ignore other pending)
  │     mark it searched when done
  │
  └── no keyword given:
        read all pending from keywords.md
        ├── none pending → print "No pending keywords" and exit
        └── search all pending concurrently (existing behaviour)
```

bot.mjs does **not** call `keywords_helper.py append` separately —
`scout.py` owns the append when a keyword arg is given.

bot.mjs only calls `keywords_helper.py pending` to decide whether to
run or reply "No pending keywords" in the no-keyword case.

---

## Step-by-Step Implementation

---

### Step 1 — `notify.py`

Thin wrapper around the existing `send-imessage` Node script.

```python
# Usage from scout.py:
from notify import notify
notify("Scout started: Beauty (8 keywords)")
```

**Implementation:**
- Read `NOTIFY_PHONE` from env (skip silently if not set — notifications are optional)
- Call the send-imessage skill's underlying script via subprocess
- Fire-and-forget (don't block scout on notification failures)

**`.env` addition:**
```
NOTIFY_PHONE=+1xxxxxxxxxx
```

---

### Step 2 — `excel.py` — add `append_keyword()`

```python
def append_keyword(campaign_name: str, keyword: str, source: str = 'imessage') -> bool:
    """Append a new pending keyword row to keywords.md.
    Returns False if keyword already exists (any status), True if appended."""
```

- Read existing keywords via `read_keywords()`
- Case-insensitive dedupe check against all existing keywords
- Append `| {keyword} | pending | {source} | {today} |` to the table
- Return `False` if duplicate (bot.mjs can reply "already in queue")

---

### Step 3 — `keywords_helper.py`

Standalone CLI script called by `bot.mjs` via subprocess.

```bash
# List available campaigns (reads context/campaigns/ dirs)
uv run keywords_helper.py list-campaigns

# Check pending keywords for a campaign
uv run keywords_helper.py pending Beauty
```

**Outputs** (stdout, one line):
- `list-campaigns` → `Beauty,PromptKey,APITest`
- `pending` → count: `3` or `0`

No `append` command — `scout.py` owns appending when a keyword arg is given.

**Campaign resolution logic:**
```python
campaigns_dir = PROJECT_ROOT / 'context' / 'campaigns'
folders = [f.name for f in campaigns_dir.iterdir() if f.is_dir()]
match = next((f for f in folders if f.lower() == name.lower()), None)
```

Case-insensitive, auto-discovers new campaigns, no hardcoding.

---

### Step 4 — `scout.py` — add notifications

Add `notify()` calls at each stage:

```
notify("🔍 Scout started: {campaign} ({n} keywords)")

# per keyword (inside search.py callback):
notify("🔎 Searching: "{keyword}"...")
notify("✅ "{keyword}" — {n} candidates found")   # or 0

notify("👤 Auditing {n} candidates...")
notify("✅ Audit done — {qualified} qualified influencers")

# at end:
notify("🎉 Scout complete: {campaign}\n{qualified} new influencers added.")
# then attach HTML (Step 6)
```

**Approach:** pass a `notify_fn` callback into `run_search()` and `run_audit()` so they can emit per-keyword updates without importing notify directly.

---

### Step 5 — `generate_dashboard.py`

Reads `data/influencers.xlsx` → writes `data/dashboard.html`.

**Called at end of `scout.py`:**
```python
from generate_dashboard import generate
generate()  # always regenerates full dashboard from all data
```

**Dashboard structure:**

```
┌─────────────────────────────────────────┐
│  TikTok Scout          [Campaign ▼]     │
│  [Influencers ●]  [Candidates]          │
├─────────────────────────────────────────┤
│  Sort: [Max Views ▼]   12 results       │
│                                         │
│  ┌──────────┐  ┌──────────┐            │
│  │ @handle  │  │ @handle  │            │
│  │ Max  2.4M│  │ Max  890K│            │
│  │ Med  1.1M│  │ Med  450K│            │
│  │ Min  600K│  │ Min  200K│            │
│  │          │  │          │            │
│  │ #beauty  │  │ #skincare│            │
│  │ Beauty   │  │ Beauty   │            │
│  │ Mar 9    │  │ Mar 8    │            │
│  │[TikTok ↗]│  │[TikTok ↗]│           │
│  └──────────┘  └──────────┘            │
│                                         │
│  Candidates ────────────────────────── │
│  @handle  keyword  status  video  date  │
└─────────────────────────────────────────┘
```

**Technical:**
- Single self-contained HTML file (inline CSS + JS, no external deps)
- Data embedded as JSON in a `<script>` block
- Mobile responsive: 1-col on phone, 2-col on tablet, 3-col on desktop
- Campaign dropdown filters both sections simultaneously
- Influencer cards sorted by max_views desc by default
- Candidates section: compact table, `audit_status` shown as colored badge
  - `pending` → gray, `qualified` → green, `not_qualified` → red
- Sticky top bar on mobile

**Data injected from xlsx:**
- Influencers sheet: all columns
- Candidates sheet: all columns
- Generated timestamp shown in footer

---

### Step 6 — `scout.py` — send dashboard

After `generate()`:
```python
from notify import notify, send_file
send_file(html_path, caption="Dashboard updated ↑")
```

`send_file()` added to `notify.py` — calls the send-imessage script with file attachment.

---

### Step 7 — `bot.mjs` — scout command parser

**Message format:** `scout #CampaignName keyword phrase`
(hashtag marks campaign, rest is keyword)

**Parsing:**
```js
const SCOUT_RE = /^scout\s+#(\w+)(?:\s+(.+))?$/i;
```

**Flow:**
```
parse message
  │
  ├── no match → skip (existing TikTok URL flow handles separately)
  │
  ├── campaign not found →
  │     reply: "Campaign '#xyz' not found. Available: Beauty, PromptKey"
  │
  ├── keyword provided →
  │     reply: "Starting scout: #Beauty "glass skin tutorial"..."
  │     spawn: uv run scout.py Beauty "glass skin tutorial"
  │     (scout.py appends keyword, searches only that keyword)
  │
  └── no keyword provided:
        check pending count via keywords_helper.py pending
        ├── 0 pending → reply: "No pending keywords for Beauty."
        └── N pending →
              reply: "Starting scout: #Beauty (N pending keywords)..."
              spawn: uv run scout.py Beauty

scout.py sends its own iMessage notifications throughout.
Final message + HTML attachment sent by scout.py on completion.
```

**Subprocess call from bot.mjs:**
```js
const args = keyword
  ? ['run', SCOUT_PY, campaign, keyword]
  : ['run', SCOUT_PY, campaign];
execFile('uv', args, { env: process.env }, callback);
```

---

## `.env` additions

```bash
NOTIFY_PHONE=+1xxxxxxxxxx   # iMessage recipient for all notifications
```

---

## iMessage Message Templates

### Keyword provided
```
You:  scout #{Campaign} {keyword}

Bot:  Starting scout: #{Campaign} "{keyword}"...
Bot:  🔎 Searching: "{keyword}"...
Bot:  ✅ "{keyword}" — {n} candidates found
Bot:  👤 Auditing {n} candidates...
Bot:  🎉 Scout complete: {Campaign}\n{qualified} qualified influencers added.
Bot:  [dashboard.html]
```

### No keyword, pending keywords exist
```
You:  scout #{Campaign}

Bot:  Starting scout: #{Campaign} ({n} pending keywords)...
Bot:  🔎 Searching: "{keyword}"...        ← repeated per keyword
Bot:  ✅ "{keyword}" — {n} candidates found
Bot:  👤 Auditing {total} candidates...
Bot:  🎉 Scout complete: {Campaign}\n{qualified} qualified influencers added.
Bot:  [dashboard.html]
```

### No keyword, nothing pending
```
You:  scout #{Campaign}

Bot:  No pending keywords for {Campaign}.
```

### Unknown campaign
```
You:  scout #{unknown}

Bot:  Campaign '#{unknown}' not found.
      Available: {Campaign1}, {Campaign2}, ...
```

### Case-insensitive campaign — bot echoes canonical name
```
You:  scout #{any-case} {keyword}

Bot:  Starting scout: #{CanonicalName} "{keyword}"...
```

---

## Parsing Edge Cases

| Input | Behaviour |
|---|---|
| `scout #Beauty` | No keyword → check pending, run if any, else "No pending keywords" |
| `scout #beauty Glass Skin` | Case-insensitive → resolves to `Beauty` campaign |
| `scout #xyz keyword` | Unknown campaign → list available ones |
| `scout #Beauty glass skin` (duplicate) | Replies "already queued", does not re-add |
| `scout #Beauty glass skin` (scout already running) | Current: spawns second process. Future: add lock file guard |
| TikTok URL in same message as scout | TikTok URL handler fires first (separate regex check order) |

---

## Out of Scope (future)

- Lock file to prevent concurrent scout runs for same campaign
- Per-sender auth allowlist
- AI keyword auto-generation (no keyword provided, no pending)
- Avatar/thumbnail images in dashboard cards
- Dashboard hosted on local server with auto-refresh

---

## Implementation Order

1. `notify.py` + `.env` `NOTIFY_PHONE`
2. `excel.py` — `append_keyword()`
3. `keywords_helper.py`
4. `scout.py` — notify calls
5. `generate_dashboard.py`
6. `scout.py` — dashboard gen + send file
7. `bot.mjs` — scout command parser
8. `PROJECT.md` update
