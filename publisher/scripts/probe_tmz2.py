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
    print("ld+json type", data.get("@type") if isinstance(data, dict) else type(data))

m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
if m:
    data = json.loads(m.group(1))
    print("next keys", list(data.keys())[:5])
else:
    print("no next data")

# find first h1 vicinity
h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
if h1:
    start = h1.start()
    chunk = html[start : start + 25000]
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', chunk)
    print("imgs after h1", len(imgs))
    for u in imgs[:8]:
        print(" ", u)

paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", chunk if h1 else html[:30000], re.S | re.I)
print("paragraphs", len(paragraphs))
for p in paragraphs[:5]:
    text = re.sub(r"<[^>]+>", "", p).strip()
    if text:
        print(" P:", text[:100])