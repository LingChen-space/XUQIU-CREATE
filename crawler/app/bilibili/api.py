from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests

from app.bilibili.buvid import get_buvid_from_homepage, get_buvid_from_spi
from app.bilibili.wbi import get_w_rid


API_SEARCH_BY_TYPE = "https://api.bilibili.com/x/web-interface/wbi/search/type"
BILIBILI_SEARCH_RESULT_ORDER_CLICK = "click"
BILIBILI_SEARCH_RESULT_ORDER_PUBDATE = "pubdate"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)
COOKIE_STORE_PATH = Path(__file__).resolve().parents[2] / ".bilibili" / "cookie.txt"


class BilibiliAPIError(RuntimeError):
    """Raised when Bilibili returns an unusable response."""


def build_proxies(proxy_url: str | None) -> dict[str, str] | None:
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


def request_new_cookie(proxy_url: str | None = None) -> str:
    buvid3 = ""
    buvid4 = ""
    b_nut = str(int(time.time()))

    try:
        buvid3, buvid4 = get_buvid_from_spi(proxy_url=proxy_url)
    except Exception:
        pass

    if not buvid3:
        buvid3, homepage_b_nut = get_buvid_from_homepage(proxy_url=proxy_url)
        b_nut = homepage_b_nut or b_nut

    if not buvid3:
        raise BilibiliAPIError("Failed to build Bilibili cookie: buvid3 is empty.")

    cookie = f"buvid3={buvid3}; b_nut={b_nut};"
    if buvid4:
        cookie += f" buvid4={buvid4};"
    return cookie


def get_cookie(proxy_url: str | None = None) -> str:
    if COOKIE_STORE_PATH.exists():
        cookie = COOKIE_STORE_PATH.read_text(encoding="utf-8").strip()
        if cookie:
            return cookie

    cookie = request_new_cookie(proxy_url=proxy_url)
    COOKIE_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    COOKIE_STORE_PATH.write_text(cookie, encoding="utf-8")
    return cookie


def get_bilibili_web_search_result(
    keyword: str,
    search_order: str = BILIBILI_SEARCH_RESULT_ORDER_CLICK,
    cookie: str | None = None,
    *,
    page: int = 1,
    page_size: int = 42,
    proxy_url: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "category_id": "",
        "search_type": "video",
        "ad_resource": "5654",
        "__refresh__": "true",
        "_extra": "",
        "context": "",
        "page": page,
        "page_size": page_size,
        "order": search_order,
        "pubtime_begin_s": 0,
        "pubtime_end_s": 0,
        "from_source": "",
        "from_spmid": "333.337",
        "platform": "pc",
        "highlight": 1,
        "single_column": 0,
        "keyword": keyword,
        "source_tag": 3,
        "gaia_vtoken": "",
        "dynamic_offset": 0,
        "web_roll_page": page,
        "web_location": "1430654",
    }

    w_rid, wts = get_w_rid(params)
    params["w_rid"] = w_rid
    params["wts"] = wts

    try:
        response = requests.get(
            API_SEARCH_BY_TYPE,
            params=params,
            headers={"User-Agent": USER_AGENT, "Cookie": cookie or get_cookie(proxy_url=proxy_url)},
            proxies=build_proxies(proxy_url),
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise BilibiliAPIError(f"Bilibili search request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise BilibiliAPIError("Failed to parse Bilibili search response.") from exc

    if payload.get("code") != 0:
        raise BilibiliAPIError(
            f"Bilibili search failed: code={payload.get('code')} message={payload.get('message')}"
        )
    data = payload.get("data", {})
    if isinstance(data, dict) and data.get("v_voucher") and not data.get("result"):
        raise BilibiliAPIError("B站返回验证 voucher，请换更具体的关键词或刷新 Cookie 后重试。")
    return payload
