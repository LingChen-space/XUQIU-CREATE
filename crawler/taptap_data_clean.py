from __future__ import annotations

import json
from pathlib import Path


INPUT_PATH = Path("docs/raw_response/taptap_search_response.json")
OUTPUT_PATH = Path("taptap_search_cleaned.json")


def iter_moment_items(node):
    if isinstance(node, dict):
        if node.get("type") == "moment" and isinstance(node.get("moment"), dict):
            yield node["moment"]

        for value in node.values():
            yield from iter_moment_items(value)

    elif isinstance(node, list):
        for item in node:
            yield from iter_moment_items(item)


def extract_moments(payload: dict) -> list[dict]:
    root_list = payload.get("data", {}).get("list", [])
    cleaned_items = []
    seen_ids = set()

    for moment in iter_moment_items(root_list):
        moment_id = moment.get("id_str")
        if moment_id in seen_ids:
            continue
        if moment_id is not None:
            seen_ids.add(moment_id)

        footer_images = moment.get("topic", {}).get("footer_images") or []
        cleaned_items.append(
            {
                "source_id": moment.get("id_str"),
                "title": moment.get("title"),
                "summary": moment.get("summary"),
                "thumbs": [
                    image.get("url")
                    for image in footer_images
                    if isinstance(image, dict) and image.get("url")
                ],
                "created_time": moment.get("created_time"),
                "id_str": moment.get("id_str"),
            }
        )

    return cleaned_items


def main() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    cleaned_items = extract_moments(payload)
    OUTPUT_PATH.write_text(
        json.dumps(cleaned_items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Exported {len(cleaned_items)} items to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
