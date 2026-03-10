---
name: scout-api
description: API-backed TikTok influencer scouting using TikHub SDK (no browser required). Searches TikTok videos by keyword, audits creator profiles, and writes qualified influencers to data/influencers.xlsx. Use when the user invokes /scout-api with a campaign name, or asks to run scouting via API instead of browser automation. Requires campaign folder at context/campaigns/CAMPAIGN_NAME/ with campaign.md and keywords.md. TIKHUB_API_KEY must be set in .claude/.env.
argument-hint: <campaign-name>
allowed-tools: Read, Edit, Bash
---

# Scout-API — TikTok Influencer Scouting via TikHub

Campaign: **$ARGUMENTS**

## Pre-flight

1. Parse `$ARGUMENTS` as `<campaign-name>`
2. Verify `context/campaigns/$ARGUMENTS/campaign.md` exists — stop and tell user if not
3. Verify `context/campaigns/$ARGUMENTS/keywords.md` exists — stop and tell user if not
4. `data/influencers.xlsx` is created automatically by `excel.py` on first run — no manual setup needed

### API Key Setup

Check if `.claude/.env` exists and contains a non-empty `TIKHUB_API_KEY`:

```bash
grep -q 'TIKHUB_API_KEY=.' .claude/.env 2>/dev/null
```

If the key is missing or the file doesn't exist:

```bash
# Create .env with placeholder if it doesn't exist
[ -f .claude/.env ] || echo 'TIKHUB_API_KEY=' > .claude/.env
# Ensure the key line exists
grep -q 'TIKHUB_API_KEY' .claude/.env || echo 'TIKHUB_API_KEY=' >> .claude/.env
# Open in default editor
open .claude/.env
```

Tell the user:
> "I've opened `.claude/.env`. Paste your TikHub API key after `TIKHUB_API_KEY=`, save the file, and reply when done. Get a key at: https://tikhub.io"

Wait for the user to confirm, then re-run the `grep` check. If still empty, stop and ask the user to check the file.

### uv Setup

Check if `uv` is available:

```bash
which uv
```

If not found, install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then verify: `uv --version`. If install fails, tell user to install manually from https://docs.astral.sh/uv/getting-started/installation/ and stop.

## Step 1 — Generate Keywords (AI step)

Read `context/campaigns/$ARGUMENTS/campaign.md` (persona, thresholds).
Read `context/campaigns/$ARGUMENTS/keywords.md` (existing keywords).

Generate 5–10 new, meaningfully distinct keywords targeting the campaign persona. Before appending, compare against ALL existing keyword rows (any status) — skip any keyword that already appears in the table (case-insensitive). Only append net-new keywords as rows with `status=pending`, `source=ai`, `date=<today>`. If all generated keywords are duplicates, skip this step entirely.

Example append (use Edit tool):
```
| ai generated keyword | pending | ai | 2026-03-06 |
```

## Step 2 — Run Scout

```bash
uv run .claude/skills/scout-api/scripts/scout.py $ARGUMENTS
```

Capture stdout. If the script exits with non-zero status, report the error and stop.

## Step 3 — Report to User

Print the full stdout summary from scout.py, then add:
- Which keywords were searched
- How many candidates were found and audited
- How many qualified influencers were added to `data/influencers.xlsx`
- Any errors encountered
- Remind user: all campaigns share one xlsx file — filter the Influencers/Candidates sheets by the `campaign` column to view results for this campaign only.

## Campaign Folder Format

```
context/campaigns/<name>/
  campaign.md     ← YAML front-matter: persona, view_threshold, avg_view_standard,
                     recent_video_count, max_candidates_per_keyword
  keywords.md     ← Markdown table: keyword | status | source | date
                     status values: pending → searched
```

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `scripts/scout.py` | CLI entry point — loads .env, inits TikHub client, orchestrates search + audit |
| `scripts/search.py` | Phase 1: keyword search via `TikTokWeb.fetch_search_video` |
| `scripts/audit.py` | Phase 2: profile + video fetch via `TikTokWeb.fetch_user_profile` / `fetch_user_post` |
| `scripts/excel.py` | xlsx helpers: read/write Candidates, Influencers, Search Log sheets |

## xlsx Sheet Schemas

**Candidates** (source of truth for audit queue):
`handle`, `triggering_video_url`, `triggering_play_count`, `keyword`, `campaign`, `audit_status`

**Influencers** (qualified creators):
`handle`, `profile_url`, `max_views`, `min_views`, `median_views`, `triggering_video_url`, `triggering_play_count`, `keyword`, `campaign`, `scouted_date`, `notes`

`excel.py` uses `_ensure_columns` — it never drops existing columns, only appends missing ones.

## Qualification Criteria

A creator qualifies when **all** sampled recent videos meet `min_video_views`. Threshold comes from campaign.md (`min_video_views`), falling back to `view_threshold`, then the Config sheet defaults.
