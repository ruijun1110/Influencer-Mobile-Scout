/**
 * bot.mjs — TikTok Similar Creator iMessage Bot
 *
 * Listens for any iMessage containing a TikTok profile URL,
 * looks up similar creators via TikHub API, and replies with profile links.
 *
 * Run: node bot.mjs
 * Requires: @photon-ai/imessage-kit (already in send-imessage/node_modules)
 */

import { createRequire } from 'module';
import { execFileSync, execFile } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join, resolve } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = resolve(__dirname, '..');
const LOOKUP_PY = join(__dirname, 'lookup.py');
const ENV_PATH = resolve(SKILL_DIR, '..', '..', '.env');
const DATA_DIR = resolve(SKILL_DIR, '..', '..', '..', 'data');
const SCOUT_PY = resolve(SKILL_DIR, '..', 'scout-api', 'scripts', 'scout.py');
const KEYWORDS_HELPER_PY = resolve(SKILL_DIR, '..', 'scout-api', 'scripts', 'keywords_helper.py');
const CAMPAIGNS_DIR = resolve(SKILL_DIR, '..', '..', '..', 'context', 'campaigns');

// Load .env manually (no dotenv dep needed)
import { readFileSync, existsSync } from 'fs';
if (existsSync(ENV_PATH)) {
  for (const line of readFileSync(ENV_PATH, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
    const [k, ...rest] = trimmed.split('=');
    process.env[k.trim()] ??= rest.join('=').trim();
  }
}

const require = createRequire(import.meta.url);
const PHOTON_PATH = resolve(
  __dirname,
  '../../../../send-imessage/node_modules/@photon-ai/imessage-kit'
);
const { IMessageSDK } = require(PHOTON_PATH);

const TIKTOK_URL_RE = /tiktok\.com\/(?:@([\w.]+)|t\/([\w]+))/i;
const SCOUT_RE = /^scout\s+#(\w+)(?:\s+(.+))?$/i;

import { readdirSync, statSync } from 'fs';

/** Resolve campaign name (case-insensitive). Returns canonical name or null. */
function resolveCampaign(rawName) {
  try {
    const dirs = readdirSync(CAMPAIGNS_DIR).filter(d => {
      try { return statSync(`${CAMPAIGNS_DIR}/${d}`).isDirectory(); } catch { return false; }
    });
    return dirs.find(d => d.toLowerCase() === rawName.toLowerCase()) || null;
  } catch { return null; }
}

/** List all campaign folder names. */
function listCampaigns() {
  try {
    return readdirSync(CAMPAIGNS_DIR).filter(d => {
      try { return statSync(`${CAMPAIGNS_DIR}/${d}`).isDirectory(); } catch { return false; }
    });
  } catch { return []; }
}

/** Get pending keyword count for a campaign via keywords_helper.py */
function getPendingCount(campaign) {
  try {
    const out = execFileSync('uv', ['run', KEYWORDS_HELPER_PY, 'pending', campaign], {
      timeout: 10000, env: { ...process.env },
    }).toString().trim();
    return parseInt(out) || 0;
  } catch { return 0; }
}

/** Spawn scout.py detached (fire-and-forget). scout.py sends its own iMessage updates. */
function spawnScout(campaign, keyword) {
  const args = keyword
    ? ['run', SCOUT_PY, campaign, keyword]
    : ['run', SCOUT_PY, campaign];
  const child = execFile('uv', args, {
    env: { ...process.env },
    timeout: 0,  // no timeout — scout can run long
  }, (err) => {
    if (err) console.error(`[scout] exited with error for ${campaign}:`, err.message);
    else console.log(`[scout] completed for ${campaign}`);
  });
  console.log(`[scout] spawned PID ${child.pid} for campaign=${campaign}` + (keyword ? ` keyword="${keyword}"` : ''));
}

const sdk = new IMessageSDK({
  watcher: {
    pollInterval: 3000,
    excludeOwnMessages: true,
  },
});

const processed = new Set();

console.log('[tiktok-lookup] Starting iMessage watcher...');

await sdk.startWatching({
  onMessage: async (msg) => {
    if (processed.has(msg.id)) return;
    processed.add(msg.id);
    if (processed.size > 500) {
      const arr = [...processed];
      processed.clear();
      arr.slice(-250).forEach(id => processed.add(id));
    }

    // --- Scout command handler ---
    const scoutMatch = msg.text?.match(SCOUT_RE);
    if (scoutMatch) {
      const rawCampaign = scoutMatch[1];
      const keyword = scoutMatch[2]?.trim() || null;
      const sender = msg.sender;

      const campaign = resolveCampaign(rawCampaign);
      if (!campaign) {
        const available = listCampaigns().join(', ') || 'none';
        await sdk.send(sender, `Campaign '#${rawCampaign}' not found.\nAvailable: ${available}`);
        return;
      }

      if (keyword) {
        await sdk.send(sender, `Starting scout: #${campaign} "${keyword}"...`);
        spawnScout(campaign, keyword);
      } else {
        const pending = getPendingCount(campaign);
        if (pending === 0) {
          await sdk.send(sender, `No pending keywords for #${campaign}.`);
        } else {
          await sdk.send(sender, `Starting scout: #${campaign} (${pending} pending keyword${pending !== 1 ? 's' : ''})...`);
          spawnScout(campaign, null);
        }
      }
      return;
    }

    // --- TikTok URL handler ---
    const match = msg.text?.match(TIKTOK_URL_RE);
    if (!match) return;

    // Resolve short URL (tiktok.com/t/xxx) to handle via redirect + TikHub API
    let handle = match[1]; // direct @handle match
    if (!handle && match[2]) {
      try {
        const res = await fetch(`https://www.tiktok.com/t/${match[2]}`, {
          method: 'HEAD', redirect: 'follow',
        });
        // Try direct handle from redirect URL first
        const directHandle = res.url.match(/tiktok\.com\/@([\w.]+)\/video/i)?.[1];
        if (directHandle) {
          handle = directHandle;
        } else {
          // Redirect goes to /@/video/<id> without username — resolve via TikHub
          const videoId = res.url.match(/\/video\/(\d+)/i)?.[1];
          if (!videoId) { console.log(`[tiktok-lookup] Could not resolve short URL: ${match[0]}`); return; }
          const apiKey = process.env.TIKHUB_API_KEY;
          const detail = await fetch(
            `https://api.tikhub.io/api/v1/tiktok/web/fetch_post_detail?itemId=${videoId}`,
            { headers: { Authorization: `Bearer ${apiKey}` } }
          ).then(r => r.json());
          const h = detail?.data?.itemInfo?.itemStruct?.author?.uniqueId;
          if (!h) { console.log(`[tiktok-lookup] Could not resolve video author for ${videoId}`); return; }
          handle = h;
        }
      } catch (e) {
        console.error('[tiktok-lookup] Short URL resolve failed:', e.message);
        return;
      }
    }
    const sender = msg.sender;

    console.log(`[tiktok-lookup] TikTok URL detected from ${sender}: @${handle}`);

    // Acknowledge immediately
    try {
      await sdk.send(sender, `Looking up similar creators for @${handle}...`);
    } catch (e) {
      console.error('[tiktok-lookup] Failed to send ack:', e.message);
    }

    // Run lookup
    try {
      const result = execFileSync('uv', ['run', LOOKUP_PY, handle, sender, DATA_DIR], {
        timeout: 30000,
        env: { ...process.env },
      }).toString().trim();

      // Parse structured output: __HEADER__<text>\n__URLS__\n<url per line>
      const headerMatch = result.match(/^__HEADER__(.*?)(?:\n__URLS__\n([\s\S]*))?$/);
      if (headerMatch) {
        const header = headerMatch[1].trim();
        const urlBlock = headerMatch[2] ? '\n' + headerMatch[2].trim() : '';
        await sdk.send(sender, header + urlBlock);
      } else {
        await sdk.send(sender, result);
      }
      console.log(`[tiktok-lookup] Replied to ${sender} for @${handle}`);
    } catch (e) {
      const errMsg = e.stderr?.toString().trim() || e.message;
      console.error(`[tiktok-lookup] Lookup failed for @${handle}:`, errMsg);
      await sdk.send(sender, `Sorry, couldn't find similar creators for @${handle}. Try again later.`);
    }
  },

  onError: (err) => {
    console.error('[tiktok-lookup] Watcher error:', err.message);
  },
});

console.log('[tiktok-lookup] Watching for TikTok URLs in iMessages...');

process.on('SIGINT', async () => {
  sdk.stopWatching();
  await sdk.close();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  sdk.stopWatching();
  await sdk.close();
  process.exit(0);
});

// Keep alive
await new Promise(() => {});
