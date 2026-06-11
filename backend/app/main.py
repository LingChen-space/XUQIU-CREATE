"""需求发生工具 — FastAPI 主入口。

启动方式: uvicorn app.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.services.scheduler import start_scheduler, stop_scheduler

# 注册路由
from app.api.games import router as games_router
from app.api.demands import router as demands_router
from app.api.reports import router as reports_router
from app.api.dashboard import router as dashboard_router

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def seed_initial_data():
    """首次启动时初始化种子数据。"""
    from app.database import async_session
    from app.services.data_adapter import DataAdapter

    # 确保 data 目录存在
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    async with async_session() as session:
        adapter = DataAdapter(session)
        games = await adapter.seed_games()
        if games:
            logger.info(f"初始化种子游戏数据: {len(games)} 款游戏")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # 启动：初始化数据库
    logger.info("初始化数据库...")
    await init_db()
    await seed_initial_data()

    # 启动每日调度器
    start_scheduler()
    logger.info(f"{settings.app_name} 启动完成")

    yield

    # 关闭
    stop_scheduler()
    logger.info(f"{settings.app_name} 已关闭")


app = FastAPI(
    title=settings.app_name,
    description="好游快爆 · 游戏工具需求智能挖掘系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(games_router)
app.include_router(demands_router)
app.include_router(reports_router)
app.include_router(dashboard_router)


@app.get("/api/health")
async def health_check():
    """健康检查。"""
    return {"status": "ok", "app": settings.app_name}


@app.post("/api/pipeline/run")
async def trigger_pipeline():
    """手动触发一次完整分析管线（用于测试和演示）。"""
    from app.services.scheduler import run_daily_pipeline
    await run_daily_pipeline()
    return {"ok": True, "message": "管线执行完成"}
