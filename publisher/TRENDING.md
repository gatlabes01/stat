# Trending searches automation

## Live URLs
- Hub: `https://detailz.xyz/trending/`
- Topics: `https://detailz.xyz/trending/{keyword-slug}/`
- Date archive (redirects to canonical): `trending/archive/YYYY/MM/DD/{slug}/`
- Sitemap: `https://detailz.xyz/trending/sitemap.xml`

## GitHub Action
- Workflow: `.github/workflows/publish-trending.yml`
- Schedule: **every 5 minutes** (`0,5,10…55` UTC) + `workflow_dispatch` + `repository_dispatch` (`publish-trending`)
- For **~1 minute** pulls (trending + news): see [TRIGGER_EVERY_MINUTE.md](TRIGGER_EVERY_MINUTE.md)
- GitHub may skip some scheduled ticks under load; green runs mean sync worked when fired.
- Requires secret: `OPENAI_API_KEY` (optional; without it, template copy is used)

## Env (Actions or local)
```
TRENDING_MAX_PER_RUN=15
TRENDING_MIN_TRAFFIC_SCORE=0
One URL per keyword. All Trends RSS headlines for each keyword are kept (no relevance filter). When headlines change, the same page updates in place. Up to MAX_PER_RUN new keywords per cycle.
TRENDING_MIN_TRAFFIC_SCORE=200
TRENDING_GEO=US
```

## Local run
```
cd publisher
set REPO_ROOT=.. 
set EXPORT_DIR=..
python tools/trending_publisher.py --deploy none
```

## Indexing (built-in)
- `robots`: index, follow, large previews, unlimited snippets
- JSON-LD: Article, FAQPage, BreadcrumbList, Speakable; hub uses ItemList + WebSite
- hreflang `en-us` + canonical on every URL
- After push: Google/Bing **sitemap ping** + optional **IndexNow** for new URLs
- Set repo secret `INDEXNOW_KEY` (random GUID); file `{key}.txt` is published at site root

Submit `https://detailz.xyz/trending/sitemap.xml` once in Google Search Console.