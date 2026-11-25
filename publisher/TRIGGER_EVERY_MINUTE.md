# Trigger /trending and /news every ~1 minute

GitHub Actions **cannot** schedule faster than **5 minutes**. For ~**1 minute** TMZ + Google Trends publishes, ping `repository_dispatch` on the `stat` repo.

| Event type | Workflow | Site path |
|------------|----------|-----------|
| `publish-trending` | `publish-trending.yml` | `/trending/` |
| `publish-news` | `publish-news.yml` | `/news/` |

## Option A — Cloudflare Worker (recommended)

1. GitHub **PAT** with **Contents** + **Actions** on `gatlabes01/stat`.
2. ```powershell
   cd workers\publish-trigger
   npx wrangler login
   npx wrangler secret put GITHUB_PAT
   npx wrangler deploy
   ```
3. Every minute UTC the worker sends **both** dispatches (`publish-trending`, then `publish-news`).

Optional: `wrangler secret put GITHUB_REPO` (default `gatlabes01/stat`).

If you deployed the old `workers/trending-trigger` worker, delete it in the Cloudflare dashboard and use `publish-trigger` instead.

## Option B — cron-job.org (free account)

Create **two** jobs (each every 1 minute), or one job that your plan allows with two chained requests:

**Trending job**

- URL: `https://api.github.com/repos/gatlabes01/stat/dispatches`
- Method: POST
- Headers: `Authorization: Bearer PAT`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`, `Content-Type: application/json`
- Body: `{"event_type":"publish-trending"}`

**News job**

- Same URL and headers
- Body: `{"event_type":"publish-news"}`

## GitHub cron backup

- Trending: `0,5,10…55` UTC
- News: `2,7,12…57` UTC (offset +2 min)

## Overlap

Each workflow has its own concurrency group; a new dispatch cancels an in-progress run for that workflow only. Trending and news can run in parallel (different folders).

## Limits

- Trends RSS: ~10 keywords/run; `TRENDING_MAX_PER_RUN=15`.
- News: `ENRICH_BATCH_SIZE=12` per run in Actions.
- Actions minutes and git push rate still apply.