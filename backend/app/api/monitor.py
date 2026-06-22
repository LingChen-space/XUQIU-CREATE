# -*- coding: utf-8 -*-
"""监控采集代理路由 —— 主后端通过该路由调用本机监控微服务。"""

import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import httpx

from app.config import settings
from app.database import async_session
from app.services.data_adapter import DataAdapter

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


class RetryRequest(BaseModel):
    platform: str
    keyword: str
    crawl_count: int = 50
    proxy_mode: str = "auto"
    douyin_browser_method: str = "method1"


@router.get("/crawl/progress")
async def get_crawl_progress():
    """获取采集进度：所有 (平台, 关键词) 组合的状态。"""
    async with async_session() as session:
        try:
            adapter = DataAdapter(session)
            records = await adapter.get_progress()
            total = len(records)
            completed = sum(1 for r in records if r["status"] == "completed")
            failed = sum(1 for r in records if r["status"] == "failed")
            running = sum(1 for r in records if r["status"] == "running")
            pending = sum(1 for r in records if r["status"] == "pending")
            return {
                "total": total,
                "completed": completed,
                "failed": failed,
                "running": running,
                "pending": pending,
                "records": records,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"查询进度失败: {e}")


@router.post("/crawl/retry")
async def retry_crawl(req: RetryRequest):
    """手动重试某个 (平台, 关键词) 组合的采集。"""
    from sqlalchemy import select
    from app.models.game import Game, GameStatus
    async with async_session() as session:
        adapter = DataAdapter(session)
        if adapter.use_mock:
            raise HTTPException(status_code=400, detail="Mock 模式下不支持重试")

        # 获取活跃游戏
        stmt = select(Game.id).where(Game.status != GameStatus.inactive)
        result = await session.execute(stmt)
        game_ids = [row[0] for row in result.all()]

        if not game_ids:
            raise HTTPException(status_code=400, detail="无活跃游戏")

        if req.proxy_mode not in {"auto", "none", "proxy"}:
            raise HTTPException(status_code=400, detail="proxy_mode 仅支持 auto/none/proxy")
        if req.douyin_browser_method not in {"method1", "method2"}:
            raise HTTPException(status_code=400, detail="douyin_browser_method 仅支持 method1/method2")

        try:
            r = await adapter.ingest_single(
                req.platform,
                req.keyword,
                game_ids,
                req.crawl_count,
                proxy_mode=req.proxy_mode,
                douyin_browser_method=req.douyin_browser_method,
            )
            return r
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"重试失败: {e}")


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


@router.get("/douyin/login")
async def douyin_login_status():
    """查询抖音登录窗口状态。"""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.monitor_api_base}/douyin/login")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"监控服务不可用: {e}")


@router.post("/douyin/login")
async def start_douyin_login(timeout_seconds: int = Query(default=300)):
    """触发本机抖音登录窗口。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.monitor_api_base}/douyin/login",
                params={"timeout_seconds": timeout_seconds},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"监控服务不可用: {e}")
