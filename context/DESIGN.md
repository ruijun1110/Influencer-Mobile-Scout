# TikTok Influencer Scout — System Design

## Invocation

```
/scout <campaign-name>
```

Reads `context/campaigns/<campaign-name>.md`, runs the full pipeline, writes results to `data/influencers.xlsx`.

---

## File Structure

```
Influencer Search Agent/
├── .claude/
│   ├── settings.local.json
│   ├── skills/scout/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── setup.py
│   └── agents/
│       ├── tiktok-search.md
│       └── tiktok-scout.md
├── context/
│   ├── DESIGN.md
│   └── campaigns/
├── data/
│   └── influencers.xlsx
└── logs/
```

---

## Components

### Skill — `scout`

Runs in the main Claude Code context. Owns the full workflow: reads campaign config, derives keywords, manages concurrency, writes final results to the Influencers sheet.

- No persona
- Explicitly scoped tools via `allowed-tools` frontmatter
- Invoked via `/scout <campaign-name>` using `$ARGUMENTS`

### Agent — `tiktok-search`

One instance per keyword. Handles browser navigation to TikTok search, DOM extraction, and writing candidates to the `Candidates` sheet.

- Model: `haiku`
- Tools: `mcp__claude-in-chrome__*`, `Bash`
- Opens its own dedicated tab; closes it on completion

### Agent — `tiktok-scout`

One instance per creator. Navigates the creator's profile, computes average views, returns a structured qualification result.

- Model: `haiku`
- Tools: `mcp__claude-in-chrome__*`, `Bash`
- Opens its own dedicated tab; closes it on completion

---

## Browser Standard

All browser interactions use the **Claude Chrome extension MCP** (`mcp__claude-in-chrome__*`). This operates within the user's existing Chrome session.

Every subagent calls `tabs_create_mcp` at startup to acquire a dedicated tab. The returned `tabId` is passed to every subsequent MCP tool call in that invocation. The main skill uses `tabs_context_mcp` to reuse the existing tab — it does not create a new one.

---

## TikTok Extraction Standards

### Search pages

Results are server-side rendered. Extract from DOM via JavaScript — no XHR interception. The count on each video card is **like count**, used as the filter proxy for `view_threshold`.

### Profile stats

Read from `__UNIVERSAL_DATA_FOR_REHYDRATION__` script tag. Do not read follower counts from DOM — they are async and show `0` until hydration completes.

### View counts

Read from `[data-e2e="user-post-item"] strong` elements. If the initial extraction returns zero results, follow the recovery ladder in order:

1. Scroll into viewport and retry
2. Wait 3 seconds and retry
3. Hard-reload via navigation (not browser refresh) and retry
4. Click the Popular tab and retry
5. Enter the profile via the triggering video URL and retry
6. Monitor and replay `api/post/item_list` network request via `fetch()`

Only skip after all six steps fail.

---

## Concurrency Model

### Phase 1 — Search

All keywords dispatched simultaneously as `tiktok-search` subagents. Cap: 10 concurrent.

### Phase 2 — Audit

Buffer-and-pool dispatch:

- **Pool**: 10 concurrent `tiktok-scout` subagents
- **Buffer**: 15 rows pre-loaded from `Candidates` sheet
- **On-deck**: 5 handles held in buffer, deployed immediately when any pool slot frees
- Buffer refills (next 15 rows) when it drops below 5

The moment a subagent finishes, the next buffered handle is dispatched without waiting for other in-flight agents.

---

## Queue and State

The `Candidates` sheet is the authoritative queue for Phase 2. Tasks (via `TaskCreate`/`TaskUpdate`) are created per dispatch for UI progress visibility only — the orchestrator never reads `TaskList` to decide what to dispatch next.

### `audit_status` lifecycle

```
pending → (dispatched) → qualified | not_qualified | skipped | error
```

---

## Data Model

### `data/influencers.xlsx` — Four sheets

**Candidates** — Phase 1 output and Phase 2 queue

| Column | Description |
|---|---|
| handle | TikTok username |
| triggering_video_url | Video that surfaced this creator |
| like_count | Like count of triggering video |
| keyword | Keyword that found this creator |
| campaign | Campaign name |
| audit_status | `pending` → `qualified` / `not_qualified` / `skipped` / `error` |

**Influencers** — Final qualified output

| Column | Description |
|---|---|
| handle | TikTok username |
| profile_url | `https://www.tiktok.com/@<handle>` |
| nickname | Display name |
| followers | Follower count |
| avg_views | Average views across sampled videos |
| recent_video_count | Actual number of videos sampled |
| bio | Profile bio |
| triggering_video_url | From Phase 1 |
| triggering_like_count | From Phase 1 |
| keyword | From Phase 1 |
| campaign | Campaign name |
| scouted_date | Date added |
| status | `new` on creation |
| notes | Flagged if sampled < requested |

**Search Log** — One row per keyword per run

| Column | Description |
|---|---|
| keyword | Search term |
| results_checked | Total cards found before filter |
| candidates_found | Count passing threshold |
| qualified | Count that passed audit |
| duration_mins | Time for this keyword |
| campaign | Campaign name |
| run_date | Date of run |

**Config** — Default thresholds

| Key | Default |
|---|---|
| view_threshold | 10000 |
| avg_view_standard | 50000 |
| recent_video_count | 10 |
| max_candidates_per_keyword | 5 |
| max_concurrent_audits | 10 |

---

## Campaign File Format

Location: `context/campaigns/<name>.md`

```yaml
---
keywords:
  - keyword one
  - keyword two
persona: |
  Audience description used for keyword derivation.
view_threshold: 10000
avg_view_standard: 50000
recent_video_count: 10
max_candidates_per_keyword: 5
---
```

Any unset field falls back to the `Config` sheet defaults.

---

## Permissions

`settings.local.json` sets `dangerouslyAllowAll: true`. This file is gitignored and machine-local.
