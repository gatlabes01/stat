from __future__ import annotations

import html
import json


def compose_tmz_html(
    paragraphs: list[str],
    images: list[dict],
    image_after_paragraph: list[tuple[int, int]],
) -> str:
    img_by_index = {i: images[i] for i in range(len(images))}
    slots: dict[int, list[int]] = {}
    for para_i, img_i in image_after_paragraph:
        slots.setdefault(para_i, []).append(img_i)

    parts: list[str] = []
    for i, para in enumerate(paragraphs):
        parts.append(f"<p>{html.escape(para)}</p>")
        for img_i in slots.get(i, []):
            img = img_by_index.get(img_i)
            if not img:
                continue
            src = img.get("local_url") or img.get("url")
            alt = html.escape(img.get("alt") or "Story photo")
            credit = img.get("credit")
            cap = f'<p class="wp-caption-text">{html.escape(credit)}</p>' if credit else ""
            parts.append(
                f'<figure class="wp-block-image size-large">'
                f'<img src="{html.escape(src, quote=True)}" alt="{alt}" loading="lazy" decoding="async">'
                f"{cap}</figure>"
            )

    used = {idx for vals in slots.values() for idx in vals}
    for img_i, img in enumerate(images):
        if img_i in used:
            continue
        src = img.get("local_url") or img.get("url")
        parts.append(
            f'<figure class="wp-block-image size-large">'
            f'<img src="{html.escape(src, quote=True)}" alt="Story photo" loading="lazy"></figure>'
        )

    return "\n".join(parts)


def parse_images_json(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []