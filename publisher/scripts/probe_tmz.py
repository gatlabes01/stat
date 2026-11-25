import httpx
import re

url = "https://www.tmz.com/2026/11/24/thomas-markle-indicted-on-child-porn-charges/"
r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True, timeout=30)
html = r.text
for pat in [r'<article[^>]*>(.*?)</article>', r'class="[^"]*article[^"]*"', r'<img[^>]+src="([^"]+)"']:
    print(pat[:40], len(re.findall(pat, html, re.I | re.S)))
imgs = re.findall(r'src="(https://[^"]+)"', html)
tmz = [u for u in imgs if "tmz.com" in u and ("image" in u or "/web/" in u)]
print("tmz imgs", len(tmz))
for u in tmz[:20]:
    print(u[:140])