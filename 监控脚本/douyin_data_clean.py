from __future__ import annotations

import json
from pathlib import Path


INPUT_PATH = Path("docs/douyin_search_response.json")
OUTPUT_PATH = Path("douyin_search_cleaned.json")


def extract_videos(payload: dict | list) -> list[dict]:
    if isinstance(payload, dict):
        items = payload.get("data", [])
    else:
        items = payload

    cleaned_items = []
    for item in items:
        if not isinstance(item, dict):
            continue

        cleaned_item = {
            "video_url": item.get("video_url"),
            "video_desc": item.get("video_desc"),
            "create_time": item.get("create_time"),
        }
        if not any(value is not None for value in cleaned_item.values()):
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
