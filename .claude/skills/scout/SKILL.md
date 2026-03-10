---
name: scout
description: Orchestrates a multi-phase workflow to find, audit, and record qualified TikTok creators into data/influencers.xlsx. Use when the user invokes /scout with a campaign name, or asks to run a scouting campaign.
argument-hint: <campaign-name>
allowed-tools: Bash, Read, TaskCreate, TaskUpdate, TaskList, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__find
---

# Scout — TikTok Influencer Scouting

Campaign: **$ARGUMENTS**
Campaign folder: `context/campaigns/$ARGUMENTS/`

## Pre-flight

1. Verify `context/campaigns/$ARGUMENTS/campaign.md` exists — stop and tell user if not
2. Verify `context/campaigns/$ARGUMENTS/keywords.md` exists — stop and tell user if not
3. Read `campaign.md` — extract: `persona`, `view_threshold`, `min_video_views`, `recent_video_count`, `max_candidates_per_keyword`
4. Read Config sheet from `data/influencers.xlsx` for fallback defaults on any unset criteria; load `max_concurrent_audits` (default: 10)
5. If `data/influencers.xlsx` does not exist, run `python3 .claude/skills/scout/scripts/setup.py` first
6. Create log file: `logs/scout-$ARGUMENTS-<YYYYMMDDHHmmss>.log` (append-only JSONL)
7. **Login probe:** Use `tabs_context_mcp` to get the current Chrome tab ID. Navigate it to `https://www.tiktok.com/search/video?q=test`. Wait 2 seconds. Run this JS to detect a login wall:

```javascript
JSON.stringify({
  loginWall: !!(
    document.querySelector('[class*="LoginModal"]') ||
    document.querySelector('[data-e2e*="login"]') ||
    document.querySelector('[class*="login-modal"]') ||
    document.title.toLowerCase().includes('log in')
  )
})
```

If `loginWall: true`, tell the user:
> "TikTok is not logged in. Please log in to the Chrome tab, then reply to continue."
Wait for explicit user confirmation before proceeding.

8. Log: `{ phase: 0, event: "run_start", campaign: "$ARGUMENTS" }`

## Phase 1 — Search (one keyword per run)

Read `context/campaigns/$ARGUMENTS/keywords.md`. Find the **first** `pending` row.

**If no pending keyword exists**, generate exactly one new keyword targeting the campaign persona — it must be meaningfully distinct from all existing rows (any status, case-insensitive). Append it as a `pending` row with `source=ai`, `date=<today>`, then use it as the keyword for this run.

**Dispatch one `tiktok-search` subagent** for that single keyword:
- `keyword` — the search term
- `view_threshold` — from campaign / Config
- `max_candidates` — `max_candidates_per_keyword` from campaign / Config
- `campaign` — $ARGUMENTS
- `campaign_dir` — absolute path to `context/campaigns/$ARGUMENTS/`
- `xlsx_path` — absolute path to `data/influencers.xlsx`
- `log_file` — the run's log file path

After the subagent completes, mark its Task `completed`. If it returns `{ error: "auth_required" }`, report to user and stop.

Print a Phase 1 summary — keyword searched, candidates found.

## Phase 2 — Profile Audit (concurrent)

The `Candidates` sheet is the source of truth for the queue.

**Dispatch model:**
- At startup, read 15 `pending` rows from `Candidates` into a local buffer. Dispatch the first 10 simultaneously to fill the pool.
- The remaining 5 in the buffer are on-deck — ready to deploy the instant a slot frees.
- The moment any subagent finishes, immediately dispatch the next handle from the buffer. Do not wait for other in-flight agents.
- When the buffer runs low (fewer than 5 remaining), read the next 15 `pending` rows from the sheet to refill it.
- Continue until the buffer is empty and no `pending` rows remain in the sheet.

**On each subagent completion:**
1. Update `audit_status` in `Candidates` sheet: `qualified`, `not_qualified`, `skipped`, or `error`
2. Mark its Task `completed`
3. Immediately dispatch the next handle from the buffer

**Task creation (UI only):** Create a Task for a handle only when you are about to dispatch it — not before.

Pass to each `tiktok-scout` instance: `handle`, `triggering_video_url`, `triggering_play_count`, `min_video_views`, `recent_video_count`, `log_file`

On any instance returning `{ error: "bot_challenge" }` or `{ error: "rate_limited" }`:
- Halt all remaining dispatches immediately
- Wait for in-flight instances to finish
- Update their rows in the sheet
- Log `{ phase: 2, event: "halt", reason, completed, remaining }`
- Report to user

## Phase 3 — Write Results

For each qualified creator returned from Phase 2, append one row to the `Influencers` sheet:

| Column | Value |
|---|---|
| handle | from audit |
| profile_url | `https://www.tiktok.com/@<handle>` |
| max_views | from audit |
| min_views | from audit |
| median_views | from audit |
| triggering_video_url | from Phase 1 |
| triggering_play_count | from Phase 1 |
| keyword | from Phase 1 |
| campaign | $ARGUMENTS |
| scouted_date | today |
| notes | flag if videos sampled < requested |

Update `Search Log`: add `qualified` count and `duration_mins`.
Log: `{ phase: 3, event: "run_end", qualified_total, duration_ms }`

## Completion Report

Print:
- Keyword searched this run
- Candidates evaluated, creators added
- Skipped creators with reasons
- Any errors
- Log file path
- Remind user: filter Influencers/Candidates sheets by `campaign` column to view this campaign's results
