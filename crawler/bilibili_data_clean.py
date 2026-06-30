from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


INPUT_PATH = Path("docs/raw_response/bilibili_search_response.json")
OUTPUT_PATH = Path("bilibili_search_cleaned.json")


def _strip_html(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _format_timestamp(value: Any) -> str:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return ""
    if timestamp <= 0:
        return ""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _first_int(*values: Any) -> int:
    for value in values:
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            return max(0, int(value))
        if isinstance(value, str) and value.strip():
            try:
                return max(0, int(float(value.strip())))
            except ValueError:
                continue
    return 0


def extract_videos(payload: dict) -> list[dict]:
    results = payload.get("data", {}).get("result", [])
    cleaned_items: list[dict] = []
    seen: set[str] = set()

    for item in results:
        if not isinstance(item, dict):
            continue

        bvid = str(item.get("bvid") or "").strip()
        aid = str(item.get("aid") or "").strip()
        source_id = bvid or aid
        if source_id and source_id in seen:
            continue
        if source_id:
            seen.add(source_id)

        mid = str(item.get("mid") or "").strip()
        cleaned_item = {
            "source_id": source_id,
            "aid": aid,
            "bvid": bvid,
            "title": _strip_html(item.get("title")),
            "description": _strip_html(item.get("description")),
            "url": item.get("arcurl") or (f"https://www.bilibili.com/video/{bvid}" if bvid else ""),
            "member_name": item.get("author") or "",
            "member_url": f"https://space.bilibili.com/{mid}" if mid else "",
            "pubdate": _format_timestamp(item.get("pubdate")),
            "play_count": _first_int(item.get("play"), item.get("view")),
            "like_count": _first_int(item.get("like")),
            "comment_count": _first_int(item.get("review"), item.get("reply")),
            "fav_count": _first_int(item.get("favorites"), item.get("favorite")),
            "danmaku_count": _first_int(item.get("danmaku")),
        }
        if not any(value not in (None, "", 0) for value in cleaned_item.values()):
            continue

        cleaned_items.append(cleaned_item)

    return cleaned_items


def main() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    cleaned_items = extract_videos(payload)
    OUTPUT_PATH.write_text(
        json.dumps(cleaned_items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Exported {len(cleaned_items)} items to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
