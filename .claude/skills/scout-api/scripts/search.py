#!/usr/bin/env python3
"""
search.py — Phase 1: search TikTok for videos by keyword.

Response shape (TikTokWeb.fetch_search_video):
  data['data']['data'] → list of video items
  item['item']['author']['uniqueId']  → handle
  item['item']['author']['secUid']    → sec_uid
  item['item']['stats']['playCount']  → play_count
  item['item']['stats']['diggCount']  → like_count
  item['item']['id']                  → video_id
  item['item']['video']['id']         → same as item id
"""
import asyncio
import json
import logging
from datetime import date

import excel

log = logging.getLogger('scout-api.search')


async def run_search(campaign_name: str, client, config: dict,
                     keyword_filter: str | None = None,
                     notify_fn=None) -> list[dict]:
    keywords = excel.read_keywords(campaign_name)

    if keyword_filter:
        # Only search the given keyword (case-insensitive match)
        pending = [k for k in keywords
                   if k.get('keyword', '').strip().lower() == keyword_filter.strip().lower()
                   and k.get('status') == 'pending']
    else:
        pending = [k for k in keywords if k.get('status') == 'pending']

    if not pending:
        print("No pending keywords.")
        return []

    # Run all keyword searches concurrently (cap at 5 parallel)
    sem = asyncio.Semaphore(5)

    async def search_one(kw_row):
        keyword = kw_row['keyword']
        if notify_fn:
            notify_fn(f'🔎 Searching: "{keyword}"...')
        async with sem:
            kw_candidates = await _search_keyword(keyword, campaign_name, client, config)
        excel.mark_keyword_searched(campaign_name, keyword)
        excel.append_search_log({
            'keyword': keyword,
            'results_checked': kw_candidates[0].get('_results_checked', 0) if kw_candidates else 0,
            'candidates_found': len(kw_candidates),
            'qualified': '',
            'duration_mins': '',
            'campaign': campaign_name,
            'run_date': str(date.today()),
        })
        if notify_fn:
            notify_fn(f'✅ "{keyword}" — {len(kw_candidates)} candidates found')
        print(f"  [{keyword}] → {len(kw_candidates)} candidates")
        return kw_candidates

    results = await asyncio.gather(*[search_one(kw) for kw in pending])
    candidates = [c for kw_list in results for c in kw_list]

    added = excel.append_candidates(candidates)
    print(f"Phase 1 complete: {len(candidates)} candidates found, {added} new written to sheet.")
    return candidates


async def _search_keyword(keyword: str, campaign: str, client, config: dict) -> list[dict]:
    view_threshold = config.get('view_threshold', 10000)
    max_candidates = config.get('max_candidates_per_keyword', 5)

    results = []
    offset = 0
    results_checked = 0
    seen_handles = set()
    search_id = None

    while len(results) < max_candidates:
        try:
            resp = await client.TikTokWeb.fetch_search_video(
                keyword=keyword,
                count=20,
                offset=offset,
                search_id=search_id or '',
                cookie='',
            )
            log.debug('search_video raw resp keys: %s', list((resp or {}).keys()))
            if resp:
                log.debug('search_video resp top-level: %s', json.dumps(resp, ensure_ascii=False)[:500])
        except Exception as e:
            print(f"  [{keyword}] search error at offset {offset}: {e}")
            log.exception('search_video exception at offset %d', offset)
            break

        items = _extract_items(resp)
        if not items:
            break

        # Extract search_id for pagination
        if not search_id:
            search_id = _safe_get(resp, 'data', 'extra', 'search_request_id') or \
                        _safe_get(resp, 'data', 'data', 0, 'search_request_id')

        results_checked += len(items)

        for item in items:
            video = _safe_get(item, 'item') or item
            author = _safe_get(video, 'author') or {}
            stats = _safe_get(video, 'stats') or {}

            handle = author.get('uniqueId') or author.get('unique_id') or ''
            sec_uid = author.get('secUid') or author.get('sec_uid') or ''
            play_count = stats.get('playCount') or stats.get('play_count') or 0
            like_count = stats.get('diggCount') or stats.get('digg_count') or 0
            video_id = video.get('id') or ''

            if not handle or handle in seen_handles:
                continue
            if play_count < view_threshold:
                continue

            seen_handles.add(handle)
            results.append({
                'handle': handle,
                '_sec_uid': sec_uid,          # internal only — not written to sheet
                'triggering_video_url': f'https://www.tiktok.com/@{handle}/video/{video_id}',
                'triggering_play_count': play_count,
                'keyword': keyword,
                'campaign': campaign,
                'audit_status': 'pending',
                '_results_checked': results_checked,
            })

            if len(results) >= max_candidates:
                break

        has_more = _safe_get(resp, 'data', 'has_more')
        if not has_more:
            break
        offset += len(items)

    # Attach results_checked to first item for logging
    if results:
        results[0]['_results_checked'] = results_checked

    return results


def _extract_items(resp) -> list:
    """Try common response shapes to extract video item list."""
    if not resp:
        return []
    data = resp.get('data') or {}
    # Shape 1: data.data → list
    items = data.get('data')
    if isinstance(items, list):
        return items
    # Shape 2: data.itemList
    items = data.get('itemList') or data.get('item_list')
    if isinstance(items, list):
        return items
    return []


def _safe_get(obj, *keys):
    for key in keys:
        if obj is None:
            return None
        if isinstance(key, int):
            obj = obj[key] if isinstance(obj, list) and len(obj) > key else None
        else:
            obj = obj.get(key) if isinstance(obj, dict) else None
    return obj
