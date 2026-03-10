# scout-api — Implementation PRD

## Goal

Replace the browser-automation-based influencer scouting system with a Python script stack backed by the TikHub API SDK. The new system runs as a second skill (`/scout-api`) alongside the existing `/scout` skill. Both write to the same `data/influencers.xlsx`.

---

## Repository for SDK

`https://github.com/TikHub/TikHub-API-Python-SDK-V2`

Install: `pip install tikhub-sdk-v2`
Auth: `TIKHUB_API_KEY` in `.env` at repo root.

### TikTok API classes used

| Class | Import |
|---|---|
| `TikTokWebAPIApi` | `tikhub_sdk_v2.api.TikTokWebAPIApi` |
| `TikTokAppV2APIApi` | `tikhub_sdk_v2.api.TikTokAppV2APIApi` |

### Key methods

**Phase 1 — Search**
- `TikTokWebAPIApi.fetch_search_video_api_v1_tiktok_web_fetch_search_video_get(keyword, cursor, count)`
  - Returns paginated video results. Each video has `author.unique_id`, `stats.play_count`, `stats.digg_count`, `share_url`.
  - Use `play_count` directly — no proxy needed (unlike DOM-based system which used like count).
  - Paginate via `cursor` / `has_more` until `max_candidates_per_keyword` is reached.

**Phase 2 — Audit**
- `TikTokAppV2APIApi.handler_user_profile_api_v1_tiktok_app_v2_handler_user_profile_get(unique_id)`
  - Returns `data.stats.follower_count`, `data.user.nickname`, `data.user.signature` (bio).
- `TikTokAppV2APIApi.fetch_user_post_videos_api_v1_tiktok_app_v2_fetch_user_post_videos_get(unique_id, count)`
  - Returns `data.videos[]` each with `stats.play_count`.
  - Request exactly `recent_video_count` videos. If fewer returned, use what's available and note in `notes`.

---

## File Structure

```
Influencer Search Agent/
├── .claude/
│   └── skills/
│       ├── scout/                      ← existing, untouched
│       └── scout-api/
│           ├── SKILL.md
│           └── scripts/
│               ├── requirements.txt
│               ├── scout.py            ← CLI orchestrator
│               ├── search.py           ← Phase 1
│               ├── audit.py            ← Phase 2
│               └── excel.py            ← xlsx read/write
├── context/
│   ├── DESIGN.md                       ← existing
│   ├── DESIGN_API.md                   ← this file
│   └── campaigns/
│       └── <name>/
│           ├── campaign.md             ← thresholds + persona
│           └── keywords.md            ← keyword pool with status
├── data/
│   └── influencers.xlsx
└── .env
```

---

## Skill — `scout-api`

### `.claude/skills/scout-api/SKILL.md`

Frontmatter:
```
allowed-tools: Read, Edit, Bash
```

Steps the skill executes (in order):

1. Parse `$ARGUMENTS` as `<campaign-name>`.
2. Read `context/campaigns/<campaign-name>/campaign.md` — load persona, thresholds.
3. Read `context/campaigns/<campaign-name>/keywords.md` — load existing keyword list.
4. **Generate new keywords**: Using the persona and existing keywords as context, generate 5–10 new keywords that:
   - Are not duplicates or near-duplicates of anything already in the list.
   - Match the campaign persona and audience.
   - Can be a single word, phrase, or full sentence.
   - Append each to `keywords.md` with `status=pending`, `added_by=ai`, `added_date=today`.
5. Run `pip install -r .claude/skills/scout-api/scripts/requirements.txt -q`.
6. Run `python .claude/skills/scout-api/scripts/scout.py <campaign-name>`.
7. Report the keyword that was searched and summary counts from stdout.

The skill's only LLM work is step 4. All data operations are delegated to Python scripts.

---

## Campaign File Format

### `context/campaigns/<name>/campaign.md`

```yaml
---
persona: |
  Describe the target audience. Used by AI to generate relevant keywords.
  Example: "Women 18-35 interested in affordable K-beauty skincare routines,
  following dermatologist creators and before/after transformation content."
view_threshold: 50000
min_video_views: 30000
recent_video_count: 10
max_candidates_per_keyword: 5
---
```

All fields optional — missing fields fall back to Config sheet defaults in xlsx.

### `context/campaigns/<name>/keywords.md`

```markdown
| keyword | status | added_by | added_date |
|---|---|---|---|
| skincare routine for oily skin | searched | user | 2026-03-06 |
| glass skin tutorial | pending | ai | 2026-03-06 |
| dermatologist recommended moisturizer | pending | user | 2026-03-06 |
```

- `status`: `pending` | `searched`
- `added_by`: `user` | `ai`
- Script picks the **first `pending` row** (top to bottom), executes search, then marks it `searched`.
- If no `pending` rows remain, script exits with message: `"No pending keywords. Add more or run /scout-api to generate."`.

---

## Phase 1 — `search.py`

**Input**: campaign name, config (thresholds loaded from campaign.md + xlsx Config sheet fallback)

**Logic**:
1. Load config.
2. Read keywords.md, find first row where `status == pending`. If none, exit.
3. Call `fetch_search_video` with the keyword. Paginate until `max_candidates_per_keyword` candidates collected or `has_more == false`.
4. For each video in results: if `play_count >= view_threshold`, add to candidates.
5. Write candidates to Candidates sheet (append-only, skip if handle+keyword combo already exists).
6. Mark keyword row as `searched` in keywords.md.
7. Write one row to Search Log sheet.

**Candidate dedup rule**: Skip a candidate if the same `handle` already exists in the Candidates sheet for this campaign (regardless of keyword). One creator should not be audited twice.

**Output**: list of candidate dicts passed to `audit.py`.

---

## Phase 2 — `audit.py`

**Input**: list of candidates from Phase 1 (or all `pending` rows from Candidates sheet if run standalone)

**Logic per candidate**:
1. Call `handler_user_profile_get(unique_id=handle)`.
   - Extract: `bio` (signature field) for link extraction only.
2. Call `fetch_user_post_videos_get(unique_id=handle, count=recent_video_count)`.
   - Extract: list of `play_count` per video.
3. Compute stats:
   - `max_views = max(play_counts)`
   - `min_views = min(play_counts)`
   - `median_views = statistics.median(play_counts)`
4. Qualification check: `all(v >= min_video_views for v in play_counts)`.
   - If fewer videos returned than `recent_video_count`, still qualify on what's available; set `notes = f"sampled {len(play_counts)}/{recent_video_count} videos"`.
5. Extract links from bio:
   - Regex for `https?://(www\.)?instagram\.com/\S+`
   - Regex for `https?://(www\.)?linktr\.ee/\S+`
   - Also capture bare `@handle` mentions followed by "instagram" or "IG" in bio.
   - Join found URLs/mentions as comma-separated string.
6. Update Candidates sheet: set `audit_status` to `qualified` | `not_qualified` | `error`.
7. If qualified: append row to Influencers sheet.

**Error handling**: On API error for a candidate, set `audit_status = error`, write error message to `notes`, continue to next candidate. Do not crash the run.

**Concurrency**: `asyncio` with `asyncio.Semaphore(10)` — run up to 10 audits concurrently.

---

## Phase 3 — `scout.py` (orchestrator)

```
usage: scout.py <campaign-name>
```

1. Load `.env` — set `TIKHUB_API_KEY`.
2. Initialize `tikhub_sdk_v2.Configuration` with API key.
3. Create `ApiClient`.
4. Call `search.py` logic → get candidates list.
5. Call `audit.py` logic with candidates → get results.
6. Print summary to stdout:
   ```
   Keyword searched : glass skin tutorial
   Candidates found : 5
   Audited          : 5
   Qualified        : 3
   Written to       : data/influencers.xlsx
   ```

The skill reads this stdout and surfaces it to the user.

---

## `excel.py` — Sheet Operations

Uses `openpyxl`. All operations are append-safe (never truncate existing data).

### Sheet: Candidates

Columns: `handle`, `triggering_video_url`, `triggering_play_count`, `keyword`, `campaign`, `audit_status`

- `audit_status` initial value: `pending`
- Written by `search.py`
- Updated in-place by `audit.py` (find row by handle+campaign, update status)

### Sheet: Influencers

Columns: `handle`, `profile_url`, `max_views`, `min_views`, `median_views`, `links`, `triggering_video_url`, `triggering_play_count`, `keyword`, `campaign`, `scouted_date`, `notes`

- Written by `audit.py` for qualified creators only
- `profile_url` = `https://www.tiktok.com/@{handle}`

### Sheet: Search Log

Columns: `keyword`, `results_checked`, `candidates_found`, `qualified`, `campaign`, `run_date`

- One row appended per `search.py` run

### Sheet: Config

Key-value pairs. Read by scripts as fallback when campaign.md doesn't specify a threshold.

| key | default_value |
|---|---|
| view_threshold | 50000 |
| min_video_views | 30000 |
| recent_video_count | 10 |
| max_candidates_per_keyword | 5 |

`excel.py` exposes:
- `load_config(campaign_name) -> dict` — merges Config sheet defaults with campaign.md overrides
- `append_candidates(rows)`
- `update_candidate_status(handle, campaign, status, notes)`
- `candidate_exists(handle, campaign) -> bool`
- `append_influencer(row)`
- `append_search_log(row)`
- `get_pending_candidates(campaign) -> list`

---

## `requirements.txt`

```
tikhub-sdk-v2
openpyxl
python-dotenv
```

---

## Data Flow Diagram

```
/scout-api <campaign>
       │
       ▼
[SKILL: generate keywords]
  reads campaign.md + keywords.md
  appends N new pending keywords to keywords.md
       │
       ▼
[scout.py] ──────────────────────────────────────────┐
       │                                             │
       ▼                                             │
[search.py]                                          │
  pick first pending keyword from keywords.md        │
  call TikHub fetch_search_video (paginate)          │
  filter: play_count >= view_threshold               │
  dedup: skip handle if already in Candidates        │
  write to Candidates sheet                          │
  mark keyword searched in keywords.md              │
  write to Search Log                               │
       │                                             │
       ▼                                             │
[audit.py] ← candidates list                        │
  asyncio semaphore(10)                              │
  per creator:                                       │
    fetch profile → bio (for link extraction)         │
    fetch recent videos → play_counts                │
    compute max/min/median                           │
    qualify: all play_counts >= min_video_views      │
    extract links from bio                           │
    update Candidates audit_status                   │
    if qualified → append to Influencers             │
       │                                             │
       ▼                                             │
[stdout summary] ────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1 — Foundation

- Create `.claude/skills/scout-api/` directory structure
- Write `requirements.txt`
- Write `excel.py` with all sheet operations and `load_config`
- Write campaign.md template and keywords.md template
- Verify xlsx opens/writes correctly with a smoke test

### Phase 2 — Search

- Write `search.py`
- Integrate TikHub `TikTokWebAPIApi`
- Implement keyword picker, pagination, candidate filter, dedup
- Write to Candidates sheet and Search Log
- Mark keyword as searched in keywords.md
- Test with one real keyword against a real campaign

### Phase 3 — Audit

- Write `audit.py`
- Integrate `TikTokAppV2APIApi`
- Implement profile fetch, video fetch, stats computation
- Implement qualification logic
- Implement link extraction regex
- Implement async concurrency with semaphore
- Write to Influencers sheet

### Phase 4 — Orchestrator + Skill

- Write `scout.py` to wire Phase 1 + 2 + print summary
- Write `SKILL.md` with keyword generation prompt and Bash invocation
- End-to-end test: run `/scout-api` on a real campaign, verify xlsx output

### Phase 5 — Hardening

- Error handling: API failures per candidate → `error` status, continue
- Handle empty video list from API
- Handle creators with < `recent_video_count` videos
- Handle no pending keywords gracefully
- Validate `.env` / API key present before running; fail fast with clear message

---

## Constraints and Notes

- Never truncate or rewrite existing xlsx rows — only append or update in-place by row lookup.
- The existing `/scout` skill must remain completely untouched.
- `scout-api` writes `triggering_play_count` (not `triggering_like_count`) — this is a schema addition to the Influencers sheet, not a rename that breaks old rows.
- Old rows written by `/scout` will simply have empty cells for the new columns — this is acceptable.
- All async API calls use the same `ApiClient` instance (not one per coroutine).
- `keywords.md` is the single source of truth for which keywords have been searched. The Search Log in xlsx is a historical record, not a queue.
