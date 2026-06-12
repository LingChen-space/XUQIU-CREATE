from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.heybox.api import api_search
from app.taptap.api import api_agg_search, TapTapRiskControlError
from douyin_data_clean import (
    INPUT_PATH as DOUYIN_INPUT_PATH,
    OUTPUT_PATH as DOUYIN_OUTPUT_PATH,
    extract_videos,
)
from heybox_data_clean import (
    INPUT_PATH as HEYBOX_INPUT_PATH,
    OUTPUT_PATH as HEYBOX_OUTPUT_PATH,
    extract_items,
)
from taptap_data_clean import (
    INPUT_PATH as TAPTAP_INPUT_PATH,
    OUTPUT_PATH as TAPTAP_OUTPUT_PATH,
    extract_moments,
)


DEFAULT_KEYWORD = "\u5de5\u5177"
DEFAULT_COUNT = 100
DEFAULT_PROXY = "http://127.0.0.1:17890"
DOUYIN_COOKIE_PATH = Path(".cloakbrowser/douyin-cookies.json")

HEYBOX_RANGE_VALUES = ("7d", "30d", "180d", "360d")
HEYBOX_SORT_VALUES = ("default", "create_date", "award_num", "comment_num")
TAPTAP_SORT_VALUES = ("default", "update_time,desc", "commented_time,desc")
DOUYIN_SORT_VALUES = ("default", "latest", "most_like")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def has_heybox_items(payload: dict) -> bool:
    return bool(payload.get("result", {}).get("items", []))


def has_taptap_items(payload: dict) -> bool:
    return bool(payload.get("data", {}).get("list", []))


def has_douyin_items(payload: dict) -> bool:
    return bool(payload.get("data", []))


def get_taptap_next_page(page_list: list[dict]) -> str:
    for item in page_list:
        if isinstance(item, dict):
            next_page = item.get("next_page")
            if isinstance(next_page, str):
                return next_page
    return ""


def get_taptap_session_id(page_list: list[dict]) -> str | None:
    for item in page_list:
        if isinstance(item, dict):
            session_id = item.get("session_id")
            if isinstance(session_id, str) and session_id:
                return session_id
    return None


def get_taptap_from_value(next_page: str) -> int | None:
    if not next_page:
        return None
    query = parse_qs(urlparse(next_page).query)
    from_values = query.get("from")
    if not from_values:
        return None
    try:
        return int(from_values[0])
    except (TypeError, ValueError):
        return None


def ensure_target_count(platform: str, actual_count: int, target_count: int) -> None:
    if actual_count < target_count:
        raise RuntimeError(
            f"{platform} exported {actual_count} cleaned items, below target count {target_count}.",
        )


def fetch_heybox_payload(
    keyword: str,
    target_count: int,
    time_range: str,
    sort_filter: str,
) -> dict:
    page_size = min(30, target_count)
    offset = 0
    merged_items: list[dict] = []
    merged_payload: dict | None = None

    while len(merged_items) < target_count:
        print(
            f"[Heybox] Requesting api_search "
            f"keyword={keyword!r} limit={page_size} offset={offset} "
            f"range={time_range!r} sort={sort_filter!r}"
        )
        response = api_search(
            keyword=keyword,
            limit=page_size,
            offset=offset,
            time_range=time_range,
            sort_filter=sort_filter,
        )
        if not response:
            print("[Heybox] api_search returned no response, stopping fetch.")
            break

        page_items = response.get("result", {}).get("items", [])
        print(f"[Heybox] api_search returned {len(page_items)} items.")
        if not page_items:
            print("[Heybox] No more items returned, stopping fetch.")
            break

        if merged_payload is None:
            merged_payload = response
            merged_payload.setdefault("result", {})["items"] = merged_items

        merged_items.extend(page_items)
        offset += len(page_items)

        if len(page_items) < page_size:
            break

    if merged_payload is None:
        merged_payload = {"msg": "", "result": {"items": []}}

    merged_payload["result"]["items"] = merged_items[:target_count]
    return merged_payload


def fetch_taptap_payload(
    keyword: str,
    target_count: int,
    sort: str | None,
    proxy_url: str | None,
) -> tuple[dict, list[dict]]:
    page_size = min(20, target_count)
    from_ = 0
    session_id: str | None = None
    merged_list: list[dict] = []
    merged_payload: dict | None = None

    while True:
        print(
            f"[TapTap] Requesting api_agg_search "
            f"keyword={keyword!r} limit={page_size} from_={from_} "
            f"session_id={session_id or 'None'} sort={sort or 'default'} "
            f"proxy={proxy_url or 'direct'}"
        )
        response = api_agg_search(
            keyword=keyword,
            sort=sort,
            limit=page_size,
            from_=from_,
            session_id=session_id,
            proxy_url=proxy_url,
        )
        if not response:
            print("[TapTap] api_agg_search returned no response, stopping fetch.")
            break

        page_list = response.get("data", {}).get("list", [])
        print(f"[TapTap] api_agg_search returned {len(page_list)} top-level list items.")
        if not page_list:
            print("[TapTap] No more list items returned, stopping fetch.")
            break

        if session_id is None:
            session_id = get_taptap_session_id(page_list)
            print(f"[TapTap] Initialized session_id={session_id or 'None'}.")

        if merged_payload is None:
            merged_payload = response
            merged_payload.setdefault("data", {})["list"] = merged_list

        merged_list.extend(page_list)
        merged_payload["data"]["list"] = merged_list

        cleaned_count = len(extract_moments(merged_payload))
        print(f"[TapTap] Accumulated {cleaned_count} cleaned moments so far.")
        if cleaned_count >= target_count:
            print("[TapTap] Reached target cleaned count, stopping fetch.")
            break

        next_page = get_taptap_next_page(page_list)
        if not next_page:
            print("[TapTap] next_page is empty, stopping fetch.")
            break

        next_from = get_taptap_from_value(next_page)
        print(f"[TapTap] Parsed next_page from value: {next_from!r}.")
        if next_from is None:
            from_ += page_size
        else:
            from_ = next_from

    if merged_payload is None:
        merged_payload = {"data": {"list": []}}

    cleaned = extract_moments(merged_payload)[:target_count]
    merged_payload["data"]["list"] = merged_list
    return merged_payload, cleaned


def export_heybox(
    keyword: str,
    target_count: int,
    time_range: str,
    sort_filter: str,
) -> list[dict]:
    raw_payload = fetch_heybox_payload(keyword, target_count, time_range, sort_filter)
    cleaned_items = extract_items(raw_payload)[:target_count]

    if has_heybox_items(raw_payload):
        write_json(HEYBOX_INPUT_PATH, raw_payload)
    if cleaned_items:
        write_json(HEYBOX_OUTPUT_PATH, cleaned_items)

    ensure_target_count("Heybox", len(cleaned_items), target_count)
    print(f"Heybox exported {len(cleaned_items)} items to {HEYBOX_OUTPUT_PATH}")
    return cleaned_items


def export_taptap(
    keyword: str,
    target_count: int,
    sort: str | None,
    proxy_url: str | None,
) -> list[dict]:
    raw_payload, cleaned_items = fetch_taptap_payload(keyword, target_count, sort, proxy_url)

    if has_taptap_items(raw_payload):
        write_json(TAPTAP_INPUT_PATH, raw_payload)
    if cleaned_items:
        write_json(TAPTAP_OUTPUT_PATH, cleaned_items)

    ensure_target_count("TapTap", len(cleaned_items), target_count)
    print(f"TapTap exported {len(cleaned_items)} items to {TAPTAP_OUTPUT_PATH}")
    return cleaned_items


def load_douyin_cookies(path: Path = DOUYIN_COOKIE_PATH) -> list[dict] | None:
    if not path.exists():
        print(
            f"[Douyin] No saved session found at {path}. "
            "If verification is required, run: python main.py --douyin-login",
            file=sys.stderr,
        )
        return None

    cookies = read_json(path)
    if not isinstance(cookies, list):
        raise RuntimeError(f"Douyin session file is invalid: {path}")
    return cookies


def save_douyin_cookies(cookies: list[dict], path: Path = DOUYIN_COOKIE_PATH) -> None:
    write_json(path, cookies)
    print(f"[Douyin] Saved session cookies to {path}", file=sys.stderr)


def login_douyin() -> None:
    from app.douyin.browser_core import (
        DOUYIN_SCREEN,
        DOUYIN_WWW_URL,
        start_douyin_browser_session,
    )

    print("[Douyin] Opening douyin.com. Please log in manually in the browser.")
    print("[Douyin] Press Enter here after login is complete to save the session.")
    with start_douyin_browser_session(
        DOUYIN_WWW_URL,
        headless=False,
        context_kwargs={
            "viewport": {"width": 1440, "height": 1000},
            "screen": DOUYIN_SCREEN,
        },
    ) as session:
        input()
        save_douyin_cookies(session.get_cookies())


def export_douyin(keyword: str, target_count: int, sort: str, headless: bool) -> list[dict]:
    from app.douyin.fetcher import (
        DouyinAntiSpamException,
        get_filter_sort_type,
        get_douyin_video_search_response,
    )

    try:
        response_items, refreshed_cookies = asyncio.run(
            get_douyin_video_search_response(
                search_word=keyword,
                cookie_data=load_douyin_cookies(),
                sort_type=get_filter_sort_type(sort),
                limit=target_count,
                headless=headless,
            )
        )
    except DouyinAntiSpamException as exc:
        raise RuntimeError(
            f"{exc} Please run python main.py --douyin-login, then retry the search."
        ) from exc
    except Exception as exc:
        message = str(exc)
        if "\u9a8c\u8bc1\u7801" in message or "\u9a8c\u8bc1" in message or "\u98ce\u63a7" in message:
            raise RuntimeError(
                f"{message} Please run python main.py --douyin-login, then retry the search."
            ) from exc
        raise

    if refreshed_cookies:
        save_douyin_cookies(refreshed_cookies)

    raw_payload = {"data": response_items[:target_count]}
    cleaned_items = extract_videos(raw_payload)[:target_count]

    if has_douyin_items(raw_payload):
        write_json(DOUYIN_INPUT_PATH, raw_payload)
    if cleaned_items:
        write_json(DOUYIN_OUTPUT_PATH, cleaned_items)

    ensure_target_count("Douyin", len(cleaned_items), target_count)
    print(f"Douyin exported {len(cleaned_items)} items to {DOUYIN_OUTPUT_PATH}")
    return cleaned_items


def add_common_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--keyword",
        default=DEFAULT_KEYWORD,
        help=f"Search keyword. Defaults to {DEFAULT_KEYWORD!r}.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Target cleaned item count. Defaults to {DEFAULT_COUNT}.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch Heybox, TapTap, and Douyin search data.",
    )
    subparsers = parser.add_subparsers(dest="platform", required=True)

    heybox_parser = subparsers.add_parser("heybox", help="Fetch Heybox search data.")
    add_common_search_args(heybox_parser)
    heybox_parser.add_argument(
        "--range",
        dest="time_range",
        default="30d",
        choices=HEYBOX_RANGE_VALUES,
        help="Heybox time range. Defaults to 30d.",
    )
    heybox_parser.add_argument(
        "--sort",
        default="default",
        choices=HEYBOX_SORT_VALUES,
        help="Heybox sort filter. Defaults to default.",
    )

    taptap_parser = subparsers.add_parser("taptap", help="Fetch TapTap search data.")
    add_common_search_args(taptap_parser)
    taptap_parser.add_argument(
        "--sort",
        default="default",
        metavar="SORT",
        help=(
            "TapTap sort. Valid values: "
            f"{', '.join(TAPTAP_SORT_VALUES)}. Defaults to default."
        ),
    )
    taptap_parser.add_argument(
        "--proxy",
        default=DEFAULT_PROXY,
        help=f"HTTP/HTTPS proxy URL for TapTap requests. Defaults to {DEFAULT_PROXY}.",
    )

    douyin_parser = subparsers.add_parser("douyin", help="Fetch Douyin video search data.")
    add_common_search_args(douyin_parser)
    douyin_parser.add_argument(
        "--sort",
        default="default",
        choices=DOUYIN_SORT_VALUES,
        help="Douyin sort type. Defaults to default.",
    )
    douyin_parser.add_argument(
        "--douyin-login",
        action="store_true",
        help="Open douyin.com for manual login, then save session cookies.",
    )
    douyin_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Douyin search browser in headless mode. Not supported with --douyin-login.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.platform == "heybox":
        if args.count <= 0:
            raise ValueError("--count must be a positive integer.")
        export_heybox(args.keyword, args.count, args.time_range, args.sort)
        return

    if args.platform == "taptap":
        if args.count <= 0:
            raise ValueError("--count must be a positive integer.")
        if args.sort not in TAPTAP_SORT_VALUES:
            raise ValueError(
                f"--sort must be one of: {', '.join(TAPTAP_SORT_VALUES)}"
            )
        proxy_url = args.proxy.strip() or None
        sort = None if args.sort == "default" else args.sort
        try:
            export_taptap(args.keyword, args.count, sort, proxy_url)
        except TapTapRiskControlError as exc:
            raise RuntimeError(
                f"{exc} "
                "\u8bf7\u5207\u6362 --proxy \u540e\u91cd\u8bd5\uff0c"
                "\u4f8b\u5982\uff1apython main.py taptap --proxy http://127.0.0.1:7890"
            ) from exc
        return

    if args.platform == "douyin":
        if args.douyin_login:
            if args.headless:
                raise ValueError("--douyin-login requires a visible browser; remove --headless.")
            login_douyin()
            return

        if args.count <= 0:
            raise ValueError("--count must be a positive integer.")
        export_douyin(args.keyword, args.count, args.sort, args.headless)
        return


if __name__ == "__main__":
    main()
