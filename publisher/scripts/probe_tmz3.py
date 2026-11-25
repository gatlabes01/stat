import json
import re

import httpx

url = "https://www.tmz.com/2026/11/24/thomas-markle-indicted-on-child-porn-charges/"
html = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True, timeout=30).text

for match in re.finditer(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    html,
    re.S | re.I,
):
    data = json.loads(match.group(1).strip())
    if isinstance(data, dict) and data.get("@type") == "NewsArticle":
        print("headline", data.get("headline"))
        print("image", data.get("image"))
        body = data.get("articleBody") or ""
        print("body len", len(body))
        print(body[:500])

# image blocks in HTML comments / data attrs
for token in ["article_blocks", "blocks", "preloadImage", "article-content-block"]:
    print(token, html.count(token))

# try tmz preload pattern
pre = re.findall(r'preloadImage\(\s*[\'"]([^\'"]+)[\'"]', html)
print("preload", len(pre))
for u in pre[:10]:
    print(u)