import re

import httpx

url = "https://www.tmz.com/2026/11/24/thomas-markle-indicted-on-child-porn-charges/"
html = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True, timeout=30).text
h1 = re.search(r"<h1[^>]*>", html, re.I)
start = h1.start() if h1 else 0
chunk = html[start : start + 50000]

# find positions of images and text paragraphs
events = []
for m in re.finditer(r'https://imagez\.tmz\.com/image/[^"\s<>]+', chunk):
    url = m.group(0).split("?")[0]
    if "_xl." in url or "_lg." in url or "_md." in url:
        events.append((m.start(), "img", url))
for m in re.finditer(r"<p[^>]*>(.*?)</p>", chunk, re.S | re.I):
    text = re.sub(r"<[^>]+>", " ", m.group(1))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 40 and "wbq.push" not in text and "preloadImage" not in text:
        events.append((m.start(), "p", text))

events.sort(key=lambda x: x[0])
seen_img = set()
for _, kind, val in events:
    if kind == "img":
        base = re.sub(r"_(xs|sm|md|lg|xl|1by1|4by3|16by9)\.", "_", val)
        if val in seen_img:
            continue
        seen_img.add(val)
        print("IMG", val)
    else:
        print("P", val[:100])