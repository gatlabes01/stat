import re

import httpx

url = "https://www.tmz.com/2026/11/24/thomas-markle-indicted-on-child-porn-charges/"
html = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True, timeout=30).text

h1 = re.search(r"<h1[^>]*>", html, re.I)
start = h1.start() if h1 else 0
end_match = re.search(r'<div[^>]+class="[^"]*related[^"]*"', html[start:], re.I)
end = start + end_match.start() if end_match else start + 40000
chunk = html[start:end]

# ordered blocks: images and paragraphs in appearance order
tokens = re.findall(
    r'(<img[^>]+src="([^"]+)"[^>]*>)|(<p[^>]*>.*?</p>)',
    chunk,
    re.S | re.I,
)
for i, t in enumerate(tokens[:20]):
    img_tag, img_src, para = t
    if para:
        text = re.sub(r"<[^>]+>", " ", para)
        text = re.sub(r"\s+", " ", text).strip()
        print(i, "P", text[:90])
    elif img_src:
        if "imagez.tmz.com" in img_src:
            print(i, "IMG", img_src)