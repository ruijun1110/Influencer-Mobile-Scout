#!/usr/bin/env python3
"""
audit.py — Phase 2: profile audit via TikHub API.

Uses TikTokWeb endpoints:
  fetch_user_post(secUid, cursor, count, coverFormat=2) → recent videos

Response shapes:
  posts: data['itemList'] or data['item_list'] → list of {stats: {playCount}, ...}
"""
import asyncio
import logging
import statistics
from datetime import date

import excel

log = logging.getLogger('scout-api.audit')


async def run_audit(candidates: list[dict], campaign_name: str, client, config: dict) -> dict:
    """Audit all candidates. Returns summary dict."""
    min_video_views = config.get('min_video_views', config.get('view_threshold', 10000))
    recent_video_count = config.get('recent_video_count', 10)

    sem = asyncio.Semaphore(4)
    qualified = 0
    errors = 0
    qualified_urls = []

    all_pending = excel.get_pending_candidates(campaign_name)
    sec_uid_map = {c['handle']: c.get('_sec_uid', '') for c in candidates}
    for c in all_pending:
        if not c.get('sec_uid'):
            c['sec_uid'] = sec_uid_map.get(c['handle'], '')

    async def audit_one(candidate):
        nonlocal qualified, errors
        handle = candidate.get('handle', '')
        sec_uid = candidate.get('sec_uid', '')

        async with sem:
            try:
                result = await _audit_creator(
                    handle, sec_uid, candidate, client,
                    min_video_views, recent_video_count, campaign_name
                )
                if result.get('qualified'):
                    qualified += 1
                    excel.append_influencer(result['influencer_row'])
                    qualified_urls.append(f"https://www.tiktok.com/@{handle}")
                status = 'qualified' if result.get('qualified') else 'not_qualified'
                excel.update_candidate_status(handle, campaign_name, status)
                print(f"  [{handle}] → {status}")
            except Exception as e:
                errors += 1
                excel.update_candidate_status(handle, campaign_name, 'error', notes=str(e))
                print(f"  [{handle}] → error: {e}")

    await asyncio.gather(*[audit_one(c) for c in all_pending])

    return {
        'total': len(all_pending),
        'qualified': qualified,
        'errors': errors,
        'not_qualified': len(all_pending) - qualified - errors,
        'qualified_urls': qualified_urls,
    }


async def _audit_creator(handle, sec_uid, candidate, client,
                          min_video_views, recent_video_count, campaign):
    """Fetch recent videos, compute stats, return result dict."""
    posts_resp = await client.TikTokWeb.fetch_user_post(
        secUid=sec_uid,
        cursor=0,
        count=recent_video_count,
        coverFormat=2,
    )
    log.debug('[%s] posts_resp keys: %s', handle, list((posts_resp or {}).get('data', {}).keys()))
    items = (_safe_get(posts_resp, 'data', 'itemList')
             or _safe_get(posts_resp, 'data', 'item_list')
             or [])

    play_counts = []
    for item in items:
        s = item.get('stats') or {}
        pc = s.get('playCount') or s.get('play_count') or 0
        play_counts.append(pc)

    if not play_counts:
        return {'qualified': False}

    max_views = max(play_counts)
    min_views = min(play_counts)
    median_views = statistics.median(play_counts)
    qualified = all(p >= min_video_views for p in play_counts)

    notes = f'sampled {len(play_counts)}/{recent_video_count} videos' if len(play_counts) < recent_video_count else ''

    return {
        'qualified': qualified,
        'influencer_row': {
            'handle': handle,
            'profile_url': f'https://www.tiktok.com/@{handle}',
            'max_views': max_views,
            'min_views': min_views,
            'median_views': median_views,
            'triggering_video_url': candidate.get('triggering_video_url', ''),
            'triggering_play_count': candidate.get('triggering_play_count', ''),
            'keyword': candidate.get('keyword', ''),
            'campaign': campaign,
            'scouted_date': str(date.today()),
            'notes': notes,
        }
    }


def _safe_get(obj, *keys):
    for key in keys:
        if obj is None:
            return None
        if isinstance(key, int):
            obj = obj[key] if isinstance(obj, list) and len(obj) > key else None
        else:
            obj = obj.get(key) if isinstance(obj, dict) else None
    return obj
