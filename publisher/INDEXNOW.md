# IndexNow (detailz.xyz)

## One-time: GitHub secret

1. Open [stat → Settings → Secrets → Actions](https://github.com/gatlabes01/stat/settings/secrets/actions).
2. **New repository secret**
   - Name: `INDEXNOW_KEY`
   - Value: `b4f17932-fd25-4924-88e4-c1dca75c6951` (same as repo root `b4f17932-fd25-4924-88e4-c1dca75c6951.txt`)

## Verify live

After push/deploy:

- https://detailz.xyz/b4f17932-fd25-4924-88e4-c1dca75c6951.txt → **200**, body is the key only

## What runs automatically

| Workflow | IndexNow |
|----------|----------|
| Publish trending searches | New `/trending/{slug}/` URLs |
| Publish TMZ news | New `/news/article/{slug}/` URLs |

Sitemap ping (Google/Bing) still runs on every push.

## Local

`publisher/.env`:

```env
INDEXNOW_KEY=b4f17932-fd25-4924-88e4-c1dca75c6951
```