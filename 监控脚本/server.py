# -*- coding: utf-8 -*-
"""监控采集微服务 —— 对外暴露 REST API，供主后端数据适配器调用。
启动方式:
  cd 监控脚本
  python server.py --port 8001

依赖:
  pip install fastapi uvicorn httpx
"""

from __future__ import annotations

import os
# 绕过系统代理，直连 API。本机代理 127.0.0.1:7897 会导致 requests/httpx 请求超时
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.heybox.api import api_search
from app.taptap.api import api_agg_search, TapTapRiskControlError
from heybox_data_clean import extract_items
from taptap_data_clean import extract_moments
from douyin_data_clean import extract_videos

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("monitor-server")

HEYBOX_RANGE_VALUES = ("7d", "30d", "180d", "360d")
HEYBOX_SORT_VALUES = ("default", "create_date", "award_num", "comment_num")
TAPTAP_SORT_VALUES = ("default", "update_time,desc", "commented_time,desc")
DOUYIN_SORT_VALUES = ("default", "latest", "most_like")

DOUYIN_COOKIE_PATH = SCRIPT_DIR / ".cloakbrowser" / "douyin-cookies.json"

app = FastAPI(title="监控采集服务", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _deduplicate(items: list[dict], key_fields: list[str]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        key = "|".join(str(item.get(f, "")) for f in key_fields)
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_douyin_cookies() -> list[dict] | None:
    if not DOUYIN_COOKIE_PATH.exists():
        return None
    cookies = _read_json(DOUYIN_COOKIE_PATH)
    if not isinstance(cookies, list):
        raise RuntimeError(f"Douyin session file is invalid: {DOUYIN_COOKIE_PATH}")
    return cookies


def _save_douyin_cookies(cookies: list[dict]) -> None:
    _write_json(DOUYIN_COOKIE_PATH, cookies)
    logger.info("[Douyin] Saved session cookies")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CrawlRequest(BaseModel):
    keyword: str = "工具"
    count: int = 100

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("count must be a positive integer")
        return v


class HeyboxCrawlRequest(CrawlRequest):
    time_range: str = "30d"
    sort: str = "default"

    @field_validator("time_range")
    @classmethod
    def validate_range(cls, v: str) -> str:
        if v not in HEYBOX_RANGE_VALUES:
            raise ValueError(f"time_range must be one of: {HEYBOX_RANGE_VALUES}")
        return v

    @field_validator("sort")
    @classmethod
    def validate_sort(cls, v: str) -> str:
        if v not in HEYBOX_SORT_VALUES:
            raise ValueError(f"sort must be one of: {HEYBOX_SORT_VALUES}")
        return v


class TapTapCrawlRequest(CrawlRequest):
    sort: str = "default"
    proxy_url: str | None = None


class DouyinCrawlRequest(CrawlRequest):
    sort: str = "default"
    headless: bool = True

    @field_validator("sort")
    @classmethod
    def validate_sort(cls, v: str) -> str:
        if v not in DOUYIN_SORT_VALUES:
            raise ValueError(f"sort must be one of: {DOUYIN_SORT_VALUES}")
        return v


class CrawlResponse(BaseModel):
    ok: bool
    platform: str
    keyword: str
    count: int
    items: list[dict]
    message: str = ""


# ---------------------------------------------------------------------------
# 小黑盒采集
# ---------------------------------------------------------------------------

def _fetch_heybox(keyword: str, count: int, time_range: str, sort: str) -> list[dict]:
    page_size = min(30, count)
    offset = 0
    merged: list[dict] = []

    while len(merged) < count:
        logger.info(f"[Heybox] keyword={keyword!r} limit={page_size} offset={offset} range={time_range!r} sort={sort!r}")
        resp = api_search(keyword=keyword, limit=page_size, offset=offset, time_range=time_range, sort_filter=sort)
        if not resp:
            break
        page_items = resp.get("result", {}).get("items", [])
        if not page_items:
            break
        merged.extend(page_items)
        offset += len(page_items)
        if len(page_items) < page_size:
            break

    cleaned = extract_items({"result": {"items": merged}})[:count]
    return cleaned


# ---------------------------------------------------------------------------
# TapTap 采集
# ---------------------------------------------------------------------------

def _get_taptap_next_page(page_list: list[dict]) -> str:
    for item in page_list:
        if isinstance(item, dict):
            np = item.get("next_page")
            if isinstance(np, str):
                return np
    return ""


def _get_taptap_session_id(page_list: list[dict]) -> str | None:
    for item in page_list:
        if isinstance(item, dict):
            sid = item.get("session_id")
            if isinstance(sid, str) and sid:
                return sid
    return None


def _get_taptap_from_value(next_page: str) -> int | None:
    from urllib.parse import parse_qs, urlparse
    if not next_page:
        return None
    query = parse_qs(urlparse(next_page).query)
    vals = query.get("from")
    if not vals:
        return None
    try:
        return int(vals[0])
    except (TypeError, ValueError):
        return None


def _fetch_taptap(keyword: str, count: int, sort: str | None, proxy_url: str | None) -> list[dict]:
    page_size = min(20, count)
    from_ = 0
    session_id: str | None = None

    while True:
        logger.info(f"[TapTap] keyword={keyword!r} limit={page_size} from_={from_} session_id={session_id} sort={sort} proxy={proxy_url}")
        resp = api_agg_search(keyword=keyword, sort=sort, limit=page_size, from_=from_, session_id=session_id, proxy_url=proxy_url)
        if not resp:
            break
        page_list = resp.get("data", {}).get("list", [])
        if not page_list:
            break
        if session_id is None:
            session_id = _get_taptap_session_id(page_list)

        cleaned = extract_moments(resp)
        if len(cleaned) >= count:
            return cleaned[:count]

        next_page = _get_taptap_next_page(page_list)
        if not next_page:
            break
        next_from = _get_taptap_from_value(next_page)
        from_ = next_from if next_from is not None else from_ + page_size

    return []


# ---------------------------------------------------------------------------
# 抖音采集
# ---------------------------------------------------------------------------

def _fetch_douyin(keyword: str, count: int, sort: str, headless: bool) -> list[dict]:
    from app.douyin.fetcher import (
        DouyinAntiSpamException,
        get_filter_sort_type,
        get_douyin_video_search_response,
    )

    try:
        response_items, refreshed_cookies = asyncio.run(
            get_douyin_video_search_response(
                search_word=keyword,
                cookie_data=_load_douyin_cookies(),
                sort_type=get_filter_sort_type(sort),
                limit=count,
                headless=headless,
            )
        )
    except DouyinAntiSpamException as exc:
        raise RuntimeError(f"抖音风控/验证: {exc} 请先在 CLI 执行 python main.py douyin --douyin-login")
    except Exception as exc:
        msg = str(exc)
        if "验证码" in msg or "验证" in msg or "风控" in msg:
            raise RuntimeError(f"抖音验证: {msg} 请先在 CLI 执行 python main.py douyin --douyin-login")
        raise

    if refreshed_cookies:
        _save_douyin_cookies(refreshed_cookies)

    raw_payload = {"data": response_items[:count]}
    cleaned = extract_videos(raw_payload)[:count]
    return cleaned


# ---------------------------------------------------------------------------
# API 端点 - 单次采集
# ---------------------------------------------------------------------------

@app.get("/api/monitor/health")
async def health():
    douyin_ready = DOUYIN_COOKIE_PATH.exists()
    return {
        "status": "ok",
        "platforms": {
            "heybox": True,
            "taptap": True,
            "douyin": douyin_ready,
        },
    }


@app.post("/api/monitor/heybox", response_model=CrawlResponse)
async def crawl_heybox(req: HeyboxCrawlRequest):
    try:
        items = _fetch_heybox(req.keyword, req.count, req.time_range, req.sort)
        return CrawlResponse(ok=True, platform="heybox", keyword=req.keyword, count=len(items), items=items)
    except Exception as e:
        logger.exception("[Heybox] Crawl failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitor/taptap", response_model=CrawlResponse)
async def crawl_taptap(req: TapTapCrawlRequest):
    sort = None if req.sort == "default" else req.sort
    try:
        items = _fetch_taptap(req.keyword, req.count, sort, req.proxy_url)
        return CrawlResponse(ok=True, platform="taptap", keyword=req.keyword, count=len(items), items=items)
    except TapTapRiskControlError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("[TapTap] Crawl failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitor/douyin", response_model=CrawlResponse)
async def crawl_douyin(req: DouyinCrawlRequest):
    douyin_ready = DOUYIN_COOKIE_PATH.exists()
    if not douyin_ready:
        raise HTTPException(status_code=400, detail="抖音未登录，请先在 CLI 执行 python main.py douyin --douyin-login")
    try:
        items = _fetch_douyin(req.keyword, req.count, req.sort, req.headless)
        return CrawlResponse(ok=True, platform="douyin", keyword=req.keyword, count=len(items), items=items)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("[Douyin] Crawl failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# API 端点 - 多排序序列全平台采集
# ---------------------------------------------------------------------------

@app.post("/api/monitor/crawl-all")
async def crawl_all_platforms(keyword: str = Query(default="工具"), count: int = Query(default=200)):
    """一键全平台多排序序列采集。

    序列规则:
      Heybox: 最多点赞(award_num) 200条 + 本月(default,30d) 200条
      TapTap: 默认列表 200条 + 最新(update_time,desc) 200条
      Douyin: 默认 200条 + 最新 200条 + 最多点赞 200条
    """
    results: list[dict] = []

    # === Heybox: 最多点赞(award_num) + 本月默认(default,30d) ===
    try:
        items_award = _fetch_heybox(keyword, count, "30d", "award_num")
        items_default = _fetch_heybox(keyword, count, "30d", "default")
        combined = _deduplicate(items_award + items_default, ["title", "share_url"])
        results.append({"platform": "heybox", "ok": True, "count": len(combined), "items": combined, "sorts": ["award_num", "default"]})
    except Exception as e:
        results.append({"platform": "heybox", "ok": False, "error": str(e)})

    # === TapTap: 默认列表 + 最新(update_time,desc) ===
    try:
        items_default = _fetch_taptap(keyword, count, None, None)
        items_latest = _fetch_taptap(keyword, count, "update_time,desc", None)
        combined = _deduplicate(items_default + items_latest, ["title", "id_str"])
        results.append({"platform": "taptap", "ok": True, "count": len(combined), "items": combined, "sorts": ["default", "update_time,desc"]})
    except TapTapRiskControlError as e:
        results.append({"platform": "taptap", "ok": False, "error": str(e)})
    except Exception as e:
        results.append({"platform": "taptap", "ok": False, "error": str(e)})

    # === Douyin: 默认 + 最新 + 最多点赞 ===
    if DOUYIN_COOKIE_PATH.exists():
        try:
            items_default = _fetch_douyin(keyword, count, "default", headless=True)
            items_latest = _fetch_douyin(keyword, count, "latest", headless=True)
            items_mostlike = _fetch_douyin(keyword, count, "most_like", headless=True)
            combined = _deduplicate(items_default + items_latest + items_mostlike, ["video_url", "video_desc"])
            results.append({"platform": "douyin", "ok": True, "count": len(combined), "items": combined, "sorts": ["default", "latest", "most_like"]})
        except Exception as e:
            results.append({"platform": "douyin", "ok": False, "error": str(e)})
    else:
        results.append({"platform": "douyin", "ok": False, "error": "未登录"})

    total = sum(r.get("count", 0) for r in results if r.get("ok"))
    return {"ok": True, "keyword": keyword, "total_items": total, "results": results}


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="监控采集服务")
    parser.add_argument("--port", type=int, default=8001, help="服务端口 (default: 8001)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="绑定地址 (default: 127.0.0.1)")
    args = parser.parse_args()

    logger.info(f"启动监控采集服务 -> http://{args.host}:{args.port}")
    uvicorn.run("server:app", host=args.host, port=args.port, reload=False, log_level="info")
