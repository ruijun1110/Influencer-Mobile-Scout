#!/usr/bin/env python3
# /// script
# dependencies = ["tikhub", "openpyxl", "python-dotenv"]
# ///
"""
scout.py — CLI orchestrator for API-based TikTok influencer scouting.

Usage:
    uv run scout.py <campaign-name> [keyword]

Reads .env from .claude/.env (four parents up from this script).
If [keyword] is given, appends it to keywords.md and searches only that keyword.
"""
import asyncio
import sys
from pathlib import Path

# Load .env from .claude/.env at project root
dotenv_path = Path(__file__).resolve().parents[4] / '.claude' / '.env'
if dotenv_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path)
    except ImportError:
        # manual parse
        import os
        for line in dotenv_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())

import os
import sys
import logging
import traceback

# Structured logging to stderr (captured by tee)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stderr,
)
log = logging.getLogger('scout-api')

# Add scripts dir to path so sibling imports work
sys.path.insert(0, str(Path(__file__).parent))
import excel
import search as search_mod
import audit as audit_mod
from notify import notify
from generate_dashboard import generate as generate_dashboard


async def main(campaign_name: str, keyword: str | None = None):
    api_key = os.environ.get('TIKHUB_API_KEY')
    if not api_key:
        print(
            f"ERROR: TIKHUB_API_KEY is not set.\n"
            f"  Add your key to: {dotenv_path}\n"
            f"  Example:  TIKHUB_API_KEY=your_key_here\n"
            f"  Get a key at: https://tikhub.io",
            file=sys.stderr,
        )
        sys.exit(1)

    # Verify campaign files exist
    campaign_dir = excel.PROJECT_ROOT / 'context' / 'campaigns' / campaign_name
    if not (campaign_dir / 'campaign.md').exists():
        print(f"ERROR: campaign file not found: {campaign_dir / 'campaign.md'}", file=sys.stderr)
        sys.exit(1)

    # If keyword given, append to keywords.md (deduped)
    if keyword:
        added = excel.append_keyword(campaign_name, keyword, source='imessage')
        if not added:
            notify(f'"{keyword}" is already queued for #{campaign_name}.')
            print(f'Keyword already exists: {keyword}')
            return

    print(f"Scout-API: campaign={campaign_name}" + (f", keyword={keyword}" if keyword else ""))

    # Load config
    config = excel.load_config(campaign_name)
    print(f"Config: view_threshold={config['view_threshold']}, "
          f"avg_view_standard={config['avg_view_standard']}, "
          f"recent_video_count={config['recent_video_count']}, "
          f"max_candidates_per_keyword={config['max_candidates_per_keyword']}")

    # Count pending keywords for notification
    all_keywords = excel.read_keywords(campaign_name)
    if keyword:
        pending_keywords = [k for k in all_keywords if k.get('keyword', '').strip().lower() == keyword.strip().lower()]
        n_keywords = 1
    else:
        pending_keywords = [k for k in all_keywords if k.get('status') == 'pending']
        n_keywords = len(pending_keywords)

    if n_keywords == 0:
        notify(f'No pending keywords for #{campaign_name}.')
        print("No pending keywords.")
        return

    notify(f'🔍 Scout started: #{campaign_name} ({n_keywords} keyword{"s" if n_keywords != 1 else ""})')

    # Init TikHub client
    from tikhub import Client
    async with Client(api_key=api_key) as client:
        # Phase 1 — Search
        print("\n--- Phase 1: Search ---")

        def search_notify(msg: str):
            notify(msg)

        candidates = await search_mod.run_search(
            campaign_name, client, config,
            keyword_filter=keyword,
            notify_fn=search_notify,
        )

        # Phase 2 — Audit
        print("\n--- Phase 2: Audit ---")
        notify(f'👤 Auditing {len(candidates)} candidates...')
        summary = await audit_mod.run_audit(candidates, campaign_name, client, config)

    # Report
    print(f"\n=== Scout-API Summary: {campaign_name} ===")
    print(f"  Candidates found:   {len(candidates)}")
    print(f"  Audited:            {summary['total']}")
    print(f"  Qualified:          {summary['qualified']}")
    print(f"  Not qualified:      {summary['not_qualified']}")
    print(f"  Errors:             {summary['errors']}")
    print(f"  Results written to: {excel.XLSX_PATH}")

    n_qualified = summary['qualified']
    qualified_urls = summary.get('qualified_urls', [])

    notify(f'🎉 Scout complete: #{campaign_name}\n{n_qualified} new influencer{"s" if n_qualified != 1 else ""} added.')

    # Send qualified profile links (blank line between each suppresses rich preview)
    if qualified_urls:
        links = '\n\n'.join(qualified_urls)
        notify(f'New influencers:\n\n{links}')

    # Generate dashboard locally (desktop only)
    try:
        generate_dashboard()
    except Exception as e:
        print(f"[dashboard] warning: {e}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <campaign-name> [keyword]", file=sys.stderr)
        sys.exit(1)
    campaign = sys.argv[1]
    kw = sys.argv[2] if len(sys.argv) >= 3 else None
    asyncio.run(main(campaign, kw))
