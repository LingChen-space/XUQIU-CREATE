from __future__ import annotations

import json
from pathlib import Path


INPUT_PATH = Path("docs/raw_response/heybox_search_response.json")
OUTPUT_PATH = Path("heybox_search_cleaned.json")


def extract_items(payload: dict) -> list[dict]:
    items = payload.get("result", {}).get("items", [])
    cleaned_items = []

    for item in items:
        info = item.get("info")
        if not isinstance(info, dict):
            continue

        linkid = info.get("linkid")
        cleaned_item = {
            "source_id": str(linkid) if linkid is not None else None,
            "linkid": info.get("linkid"),
            "title": info.get("title"),
            "description": info.get("description"),
            "thumbs": info.get("thumbs"),
            "share_url": info.get("share_url"),
            "create_at": info.get("create_at"),
        }
        if not any(value is not None for value in cleaned_item.values()):
            continue

        cleaned_items.append(cleaned_item)

    return cleaned_items


def main() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    cleaned_items = extract_items(payload)
    OUTPUT_PATH.write_text(
        json.dumps(cleaned_items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Exported {len(cleaned_items)} items to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
