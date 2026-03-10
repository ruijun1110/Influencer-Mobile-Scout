# TikTok Influencer Scout

A toolkit for discovering and auditing TikTok influencers — running entirely on your Mac, no server required.

[中文说明](README.zh.md)

---

## Features

- **API-based scouting** — Search TikTok by keyword, audit creator profiles, write qualified influencers to Excel
- **iMessage bot** — Send a TikTok URL from your phone → get similar creator recommendations back; or trigger a scout with `scout #Campaign keyword`
- **Dashboard** — Auto-generated HTML dashboard with campaign/keyword filters
- **Notifications** — Optional iMessage progress updates during scouting

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **macOS** | iMessage features require macOS |
| **[uv](https://docs.astral.sh/uv/)** | Python runner — installed automatically by `setup.sh` |
| **[TikHub API key](https://tikhub.io)** | Free tier available — get one at tikhub.io |
| **Messages.app** | Must be signed into iMessage on the Mac |

No Node.js, no npm, no Python install required.

---

## Installation

### 1. Clone the repo

```bash
git clone <repo-url>
cd influencer-search-agent
```

### 2. Run setup

```bash
bash setup.sh
```

This will:
- Install `uv` if not already present
- Generate the launchd plist with your local paths
- Create `.claude/.env` from the template and open it for editing

### 3. Fill in your API key

When `.claude/.env` opens, add your TikHub API key:

```
TIKHUB_API_KEY=your_key_here
NOTIFY_PHONE=+1XXXXXXXXXX   # optional — iMessage progress notifications
```

Save and close.

### 4. Grant Full Disk Access to Terminal

The iMessage bot reads `~/Library/Messages/chat.db`, which requires Full Disk Access.

**System Settings → Privacy & Security → Full Disk Access → enable your terminal app**

This is a one-time manual step.

---

## iMessage Bot

Start the background daemon:

```bash
launchctl load ~/Library/LaunchAgents/com.tiktok-lookup.plist
```

Or use the provided skill commands (see skill docs).

Once running, from any phone that can iMessage your Mac:

| Message | What happens |
|---|---|
| `https://www.tiktok.com/@someuser` | Replies with up to 10 similar creators |
| `scout #Beauty glass skin` | Triggers a scout for keyword "glass skin" in the Beauty campaign |
| `scout #Beauty` | Runs all pending keywords in the Beauty campaign |
| `scout #unknown` | Replies with available campaign list |

The bot restarts automatically on login.

Check logs: `tail -f /tmp/tiktok-lookup.log`

---

## Campaign Setup

Campaigns live in `context/campaigns/<name>/`. Each needs two files:

**`campaign.md`** — defines the target audience and thresholds:
```yaml
---
persona: |
  Describe the target audience and content type.
view_threshold: 10000
min_video_views: 50000
recent_video_count: 10
max_candidates_per_keyword: 5
---
```

**`keywords.md`** — keyword queue:
```markdown
| keyword | status | source | date |
|---|---|---|---|
| skincare routine | pending | manual | 2026-03-10 |
| glass skin | pending | manual | 2026-03-10 |
```

Status flow: `pending` → `searched`

---

## Output

All results write to `data/influencers.xlsx`:

- **Influencers** sheet — qualified creators with view stats
- **Candidates** sheet — all audited profiles
- **Search Log** sheet — keyword search history

Open `data/dashboard.html` in any browser for a visual view with campaign/keyword filters.

---

## Project Structure

```
├── context/
│   └── campaigns/          ← one folder per campaign
├── data/                   ← xlsx output + dashboard (gitignored)
├── setup.sh                ← one-time setup script
└── .claude/
    ├── .env                ← API keys (gitignored)
    ├── .env.example        ← template
    └── skills/
        ├── scout-api/      ← scouting scripts
        └── tiktok-lookup/  ← iMessage bot (bot.py)
```

---

## Troubleshooting

| Error | Fix |
|---|---|
| Bot not reading messages | Grant Full Disk Access to Terminal (step 4) |
| `TIKHUB_API_KEY not set` | Check `.claude/.env` |
| `uv: command not found` | Run `bash setup.sh` again |
| Bot not responding | Ensure Messages.app is signed in; check `/tmp/tiktok-lookup.err` |
| Plist not found | Run `bash setup.sh` to regenerate it |
