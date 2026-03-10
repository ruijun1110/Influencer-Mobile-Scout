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
| **Full Disk Access** | Terminal needs Full Disk Access to read iMessages (see below) |

No Node.js, no npm, no Python install required.

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/ruijun1110/Influencer-Mobile-Scout.git
cd Influencer-Mobile-Scout
```

### 2. Grant Full Disk Access to Terminal

The bot reads your iMessage database, which requires Full Disk Access.

1. Open **System Settings > Privacy & Security > Full Disk Access**
2. Enable **Terminal** (or iTerm / your terminal app)
3. **Quit and reopen Terminal** for the change to take effect

### 3. Run setup

Double-click **`setup.command`** in Finder (or run `bash setup.sh` from Terminal).

This will:
- Install `uv` if not already present
- Create `.claude/.env` from the template and open it for editing
- Verify Full Disk Access is working
- Register the bot as a Login Item so it starts automatically on every login
- Start the bot immediately

### 4. Fill in your API key

When `.claude/.env` opens, add your TikHub API key:

```
TIKHUB_API_KEY=your_key_here
NOTIFY_PHONE=+1XXXXXXXXXX   # optional — iMessage progress notifications
```

Save and close. That's it.

---

## iMessage Bot

**First time:** the bot starts automatically at the end of `setup.command`.

**After a reboot:** starts automatically via Login Item — nothing to do.

**If the bot stops unexpectedly:** double-click **`start.command`** in Finder to restart it.

**Check status:** double-click **`status.command`** — shows running state, uptime, last message, errors, and recent logs.

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

---

## Campaign Setup

Campaigns define the target audience, search thresholds, and keyword queue. Each campaign lives in its own folder under `context/campaigns/<CampaignName>/` and requires two files.

Copy the example template to get started:

```bash
cp -r context/campaigns/_example context/campaigns/MyCampaign
```

Then edit the two files:

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
│   └── campaigns/
│       └── _example/          ← copy this to create a new campaign
├── data/                      ← xlsx output + dashboard (gitignored)
├── setup.command              ← double-click to install
├── start.command              ← double-click to start the bot
├── status.command             ← double-click to check bot status
├── reset.command              ← double-click to uninstall everything
└── .claude/
    ├── .env                   ← API keys (gitignored)
    ├── .env.example           ← template
    └── skills/
        ├── scout-api/         ← scouting scripts
        └── tiktok-lookup/     ← iMessage bot (bot.py)
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot not responding to messages | Double-click `status.command` to diagnose; try `start.command` to restart |
| `TIKHUB_API_KEY not set` | Check `.claude/.env` |
| `Cannot read Messages database` | Grant Full Disk Access to Terminal, then quit and reopen Terminal |
| `uv: command not found` | Run `setup.command` again |
| Bot doesn't start on login | Run `setup.command` again to re-register the Login Item |
| Messages.app not signed in | Sign into iMessage in Messages.app settings |
| Want a clean re-install | Double-click `reset.command`, then `setup.command` |
