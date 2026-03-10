# Influencer Search Agent — Project Documentation

## Overview

A Claude Code–powered toolkit for discovering and auditing TikTok influencers. Supports two scouting modes (browser and API), plus an iMessage bot for ad-hoc similar creator lookup.

---

## Project Structure

```
Influencer Search Agent/
├── context/
│   ├── PROJECT.md              ← this file
│   ├── DESIGN.md               ← browser-based scout design notes
│   ├── DESIGN_API.md           ← API-based scout design notes
│   └── campaigns/
│       ├── <name>/
│       │   ├── campaign.md     ← YAML: persona, thresholds, config
│       │   └── keywords.md     ← keyword table (pending → searched)
│       ├── Beauty/
│       ├── PromptKey/
│       └── APITest/
├── data/
│   ├── influencers.xlsx        ← shared output for all scouting campaigns
│   └── similar_users.xlsx      ← output for tiktok-lookup iMessage bot
├── logs/
│   └── scout-<campaign>-<ts>.log
└── .claude/
    ├── .env                    ← TIKHUB_API_KEY, NOTIFY_PHONE (never commit)
    ├── agents/
    │   ├── tiktok-search.md    ← subagent: searches one keyword via browser
    │   └── tiktok-scout.md     ← subagent: audits one creator profile via browser
    └── skills/
        ├── scout/              ← /scout <campaign> — browser-based scouting
        │   ├── SKILL.md
        │   └── scripts/setup.py
        ├── scout-api/          ← /scout-api <campaign> — API-based scouting
        │   ├── SKILL.md
        │   └── scripts/
        │       ├── scout.py              ← CLI entry point: uv run scout.py <campaign> [keyword]
        │       ├── search.py             ← keyword search via TikHub SDK
        │       ├── audit.py              ← profile audit via TikHub SDK
        │       ├── excel.py              ← xlsx read/write helpers
        │       ├── notify.py             ← iMessage notifications via IMessageSDK
        │       ├── keywords_helper.py    ← CLI: list-campaigns, pending <campaign>
        │       └── generate_dashboard.py ← reads xlsx → writes data/dashboard.html
        └── tiktok-lookup/      ← /tiktok-lookup start|stop|status
            ├── SKILL.md
            ├── launchd/
            │   └── com.tiktok-lookup.plist
            └── scripts/
                ├── bot.mjs     ← iMessage daemon: TikTok URL lookup + scout command parser
                └── lookup.py   ← TikHub API + xlsx write (uv run)
```

---

## Skills

### `/scout <campaign>` — Browser-based scouting
- Uses Chrome via Photon MCP browser tools
- Dispatches `tiktok-search` subagent per keyword (sequential, one at a time)
- Dispatches `tiktok-scout` subagents for profile auditing (concurrent pool)
- If no pending keywords, generates one new AI keyword per run
- Writes to `data/influencers.xlsx`

### `/scout-api <campaign>` — API-based scouting
- No browser required — uses TikHub SDK via Python
- Parallel keyword search (`asyncio`, semaphore 5)
- Concurrent profile audit (`asyncio`, semaphore 4)
- Run via `uv run scout.py <campaign> [keyword]` — no venv setup needed
- Optional `[keyword]` arg: appends keyword to `keywords.md` and searches only that keyword
- Sends iMessage progress notifications via `notify.py` (requires `NOTIFY_PHONE` in `.env`)
- On completion: sends qualified influencer TikTok profile URLs via iMessage
- Generates `data/dashboard.html` — self-contained responsive HTML dashboard (desktop only)
- Writes to `data/influencers.xlsx`

### `/tiktok-lookup start|stop|status` — iMessage bot (TikTok lookup + scout trigger)
- Persistent background daemon managed via macOS `launchd`
- **TikTok URL lookup**: watches for TikTok URLs → resolves handle → fetches similar creators → replies with profile links; writes to `data/similar_users.xlsx`
- **Scout command**: `scout #<Campaign> [keyword]` — case-insensitive; resolves campaign, appends keyword, spawns `scout.py` in background
  - `scout #Beauty glass skin` → appends keyword, runs scout for that keyword only
  - `scout #Beauty` → runs scout on all pending keywords (or replies "No pending keywords")
  - `scout #unknown` → replies with available campaign list

---

## xlsx Schemas

### `data/influencers.xlsx`

**Candidates** sheet:
| handle | triggering_video_url | triggering_play_count | keyword | campaign | audit_status |

**Influencers** sheet:
| handle | profile_url | max_views | min_views | median_views | triggering_video_url | triggering_play_count | keyword | campaign | scouted_date | notes |

**Search Log** sheet:
| keyword | results_checked | candidates_found | qualified | duration_mins | campaign | run_date |

**Config** sheet:
| key | value |
Defaults: `view_threshold=10000`, `min_video_views=10000`, `recent_video_count=10`, `max_candidates_per_keyword=5`

### `data/similar_users.xlsx`

**Lookups** sheet:
| queried_handle | similar_handle | profile_url | lookup_date | requested_by |

---

## Campaign Folder Format

```yaml
# campaign.md — YAML front-matter
persona: "..."
view_threshold: 10000
min_video_views: 50000
recent_video_count: 10
max_candidates_per_keyword: 5
```

```markdown
# keywords.md — markdown table
| keyword | status | source | date |
|---|---|---|---|
| beauty tips | searched | ai | 2026-03-01 |
| skincare routine | pending | ai | 2026-03-09 |
```

Status flow: `pending` → `searched`

---

## TikHub API Endpoints Used

| Purpose | Endpoint |
|---|---|
| Keyword search | `GET /api/v1/tiktok/web/fetch_search_video` |
| User profile (handle → sec_uid) | `GET /api/v1/tiktok/web/fetch_user_profile?uniqueId=` |
| User posts (view counts) | `GET /api/v1/tiktok/app/v3/fetch_user_post` |
| Similar users | `GET /api/v1/tiktok/app/v3/fetch_similar_user_recommendations?sec_uid=` |

**Response notes:**
- Profile endpoint: `data.statusCode == 0` = success; `data.userInfo.user.secUid` = sec_uid
- Similar users: `data.users[]` (flat objects), handle field = `unique_id` (snake_case)
- Very large accounts (charlidamelio, gordonramsay) may return empty similar user lists — TikTok API limitation

---

## Known Issues

*(none active — see Resolved below)*

---

## Resolved Issues

### tiktok-lookup: iMessage watcher not triggering

**Status**: Fixed (2026-03-09)

**Root cause 1 — Wrong callback name**: `@photon-ai/imessage-kit` v2.1.2 `WatcherEvents` interface does **not** have `onNewMessage`. The actual callbacks are `onMessage` (all), `onDirectMessage`, `onGroupMessage`. Passing `onNewMessage` was silently ignored.
- **Fix**: Changed `startWatching({ onNewMessage })` → `startWatching({ onMessage })` in `bot.mjs`.

**Root cause 2 — Short URL resolution failure**: TikTok short URLs (`tiktok.com/t/xxx`) redirect to `/@/video/<id>` with no username in the path. The old regex required a non-empty handle after `@` and always failed.
- **Fix**: Extract video ID from redirect, call `GET /api/v1/tiktok/web/fetch_post_detail?itemId=<id>` → `data.itemInfo.itemStruct.author.uniqueId`.

**Root cause 3 — Mail app opening instead of TikTok**: `profile_url` was stored/sent as `tiktok.com/@handle` (no scheme) — iOS treated it as an email-like address.
- **Fix**: All URLs now use `https://www.tiktok.com/@handle`.

---

## Environment

- macOS, Apple Silicon (`/opt/homebrew/bin/node`)
- Node.js via Homebrew
- Python via system + `uv` for isolated script environments
- `.claude/.env` holds `TIKHUB_API_KEY` and `NOTIFY_PHONE`
- System sleep disabled on AC power (System Settings → Battery)
