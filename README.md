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
| **[TikHub API key](https://tikhub.io)** | Get one at tikhub.io |
| **Messages.app** | Must be signed into iMessage on the Mac |

No Node.js, no npm, no Python install required.

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/ruijun1110/Influencer-Mobile-Scout.git
cd Influencer-Mobile-Scout
```

### 2. Run setup

Double-click **`setup.command`** in Finder.

This will:
- Install `uv` if not already present
- Generate the launchd plist with your local paths
- Create `.claude/.env` from the template and open it for editing
- Start the iMessage bot automatically

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

**First time:** the bot starts automatically at the end of `setup.command`.

**After a manual stop or reinstall:** double-click **`start.command`** in Finder.

The bot restarts automatically on every login — you normally won't need to do anything after setup.

Once running, send messages from any phone that can iMessage your Mac:

| Message | What happens |
|---|---|
| A TikTok profile or video URL | Replies with up to 10 similar creators |
| `scout #<Campaign>` | Runs all pending keywords for that campaign |
| `scout #<Campaign> <keyword>` | Triggers a scout for a specific keyword |
| `scout #<unknown>` | Replies with a list of available campaigns |

For example, if you have a campaign named `Beauty`:
- `scout #Beauty` — runs all pending keywords
- `scout #Beauty glass skin` — searches "glass skin" specifically

Campaign names are case-insensitive. The bot restarts automatically on login.

Check logs: `tail -f /tmp/tiktok-lookup.log`

---

## Campaign Setup

Campaigns define the target audience, search thresholds, and keyword queue. Each campaign lives in its own folder under `context/campaigns/<CampaignName>/` and requires two files.

### `campaign.md`

```yaml
---
persona: |
  Describe the target audience, content type, and what makes a creator a good fit.
  Be as specific as needed — this is used by AI to generate relevant keywords.
view_threshold: 10000        # minimum play count to consider a video in search results
min_video_views: 50000       # minimum views required across recent videos to qualify
recent_video_count: 10       # how many recent videos to sample when auditing a creator
max_candidates_per_keyword: 5  # max creators to audit per keyword search
---
```

### `keywords.md`

A markdown table tracking which keywords have been searched:

```markdown
| keyword | status | source | date |
|---|---|---|---|
| your keyword here | pending | manual | 2026-03-10 |
```

- **status**: `pending` (not yet searched) or `searched` (done)
- **source**: `manual` (you added it) or `ai` (auto-generated)
- **date**: when the keyword was added

Add keywords manually, or let the AI generate them based on your campaign persona. Status updates to `searched` automatically after each run.

---

## Output

All results write to `data/influencers.xlsx`:

- **Influencers** sheet — qualified creators with view stats
- **Candidates** sheet — all audited profiles and their status
- **Search Log** sheet — keyword search history per campaign

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
