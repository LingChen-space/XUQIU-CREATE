# -*- coding: utf-8 -*-
"""监控采集代理路由 —— 主后端通过该路由调用本机监控微服务。"""

import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import httpx

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitor", tags=["monitor"])


class CrawlAllRequest(BaseModel):
    keyword: str = "工具"
    count: int = 50


@router.get("/health")
async def monitor_health():
    """查询监控微服务健康状态。"""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.monitor_api_base}/health")
            return resp.json()
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}


@router.post("/crawl-all")
async def trigger_crawl_all(req: CrawlAllRequest):
    """触发全平台采集（调用监控微服务）。"""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{settings.monitor_api_base}/crawl-all",
                params={"keyword": req.keyword, "count": req.count},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"监控服务不可用: {e}")


@router.post("/heybox")
async def trigger_heybox(keyword: str = Query(default="工具"), count: int = Query(default=50)):
    """触发小黑盒采集。"""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.monitor_api_base}/heybox",
                json={"keyword": keyword, "count": count, "time_range": "30d", "sort": "default"},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"监控服务不可用: {e}")


@router.post("/taptap")
async def trigger_taptap(keyword: str = Query(default="工具"), count: int = Query(default=50)):
    """触发 TapTap 采集。"""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.monitor_api_base}/taptap",
                json={"keyword": keyword, "count": count, "sort": "default", "proxy_url": None},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"监控服务不可用: {e}")


@router.post("/douyin")
async def trigger_douyin(keyword: str = Query(default="工具"), count: int = Query(default=50)):
    """触发抖音采集。"""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.monitor_api_base}/douyin",
                json={"keyword": keyword, "count": count, "sort": "default", "headless": False},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"监控服务不可用: {e}")
