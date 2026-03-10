#!/usr/bin/env python3
# /// script
# dependencies = ["openpyxl"]
# ///
"""
keywords_helper.py — CLI for bot.mjs to query campaign/keyword state.

Usage:
    uv run keywords_helper.py list-campaigns
    uv run keywords_helper.py pending <CampaignName>

Output (stdout, single line):
    list-campaigns → comma-separated canonical names, e.g. "Beauty,PromptKey,APITest"
    pending        → integer count, e.g. "3"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import excel

CAMPAIGNS_DIR = excel.PROJECT_ROOT / 'context' / 'campaigns'


def list_campaigns() -> list[str]:
    if not CAMPAIGNS_DIR.exists():
        return []
    return [f.name for f in sorted(CAMPAIGNS_DIR.iterdir()) if f.is_dir()]


def resolve_campaign(name: str) -> str | None:
    """Case-insensitive campaign resolution. Returns canonical folder name or None."""
    folders = list_campaigns()
    return next((f for f in folders if f.lower() == name.lower()), None)


def pending_count(campaign_name: str) -> int:
    keywords = excel.read_keywords(campaign_name)
    return sum(1 for k in keywords if k.get('status') == 'pending')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} list-campaigns | pending <Campaign>", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == 'list-campaigns':
        print(','.join(list_campaigns()))

    elif cmd == 'pending':
        if len(sys.argv) < 3:
            print("Usage: keywords_helper.py pending <Campaign>", file=sys.stderr)
            sys.exit(1)
        campaign = resolve_campaign(sys.argv[2])
        if not campaign:
            print("0")
        else:
            print(pending_count(campaign))

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
