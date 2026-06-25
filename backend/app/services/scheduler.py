# -*- coding: utf-8 -*-
"""每日调度器 - 基于 APScheduler 的定时任务管理。"""

import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.game import Game, GameStatus
from app.services.data_adapter import DataAdapter
from app.services.external_monitor_sync import TapKbForumSyncService
from app.services.signal_engine import SignalEngine
from app.services.llm_pipeline import LLMPipeline
from app.services.report_generator import ReportGenerator
from app.services.radar_runner import run_radar_scan_cycle

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_tap_kb_realtime_sync():
    """增量同步 Tap+快爆后台，并立即触发早期雷达扫描。"""
    async with async_session() as session:
        try:
            result = await TapKbForumSyncService(session).sync(days=30, force=False, reason="auto")
            inserted = result.get("contents", {}).get("inserted", 0)
            if inserted:
                logger.info(f"[TapKbRealtimeSync] 同步到 {inserted} 条新内容")
                await run_radar_scan_cycle(session)
            return result
        except Exception as exc:
            logger.exception(f"[TapKbRealtimeSync] 执行失败: {exc}")
            return {"ok": False, "status": "failed", "message": str(exc)}


async def run_radar_realtime_scan():
    async with async_session() as session:
        try:
            return await run_radar_scan_cycle(session)
        except Exception as exc:
            logger.exception(f"[RadarScan] 执行失败: {exc}")
            return {"ok": False, "message": str(exc)}


async def run_priority_game_exploration():
    async with async_session() as session:
        try:
            adapter = DataAdapter(session)
            result = await adapter.ingest_exploration("priority")
            await run_radar_scan_cycle(session)
            return result
        except Exception as exc:
            logger.exception(f"[RadarPriorityExploration] 执行失败: {exc}")
            return {"ok": False, "message": str(exc)}


async def run_regular_game_exploration():
    async with async_session() as session:
        try:
            adapter = DataAdapter(session)
            result = await adapter.ingest_exploration("regular")
            await run_radar_scan_cycle(session)
            return result
        except Exception as exc:
            logger.exception(f"[RadarRegularExploration] 执行失败: {exc}")
            return {"ok": False, "message": str(exc)}


async def run_daily_pipeline(force_recrawl: bool = False):
    """
    每日主管线：
    1. 数据接入 - 从爬虫体系拉取过去24h的各平台内容
    2. 信号计算 - 对每款活跃游戏计算需求信号
    3. LLM 分析 - 对候选游戏做痛点提炼
    4. 日报生成 - 汇总生成结构化日报
    """
    today = date.today()
    logger.info(f"[DailyPipeline] 开始执行 - {today}")

    async with async_session() as session:
        try:
            # --- Step 0: 外部监控后台同步 ---
            # 外部后台内容不依赖本地搜索词配置，同步可能自动创建新游戏。
            external_sync = await TapKbForumSyncService(session).sync(
                days=30,
                force=force_recrawl,
                reason="pipeline",
            )
            logger.info(f"[DailyPipeline] 外部同步完成 - {external_sync.get('message', '')}")

            # --- Step 1: 数据接入 ---
            adapter = DataAdapter(session)

            # 获取所有活跃游戏（非已停运）
            stmt = (
                select(Game)
                .where(Game.status != GameStatus.inactive)
                .order_by(Game.priority_weight.desc(), Game.name)
            )
            result = await session.execute(stmt)
            games = result.scalars().all()
            game_ids = [g.id for g in games]

            if not game_ids:
                logger.warning("[DailyPipeline] 无活跃游戏，跳过")
                return {
                    "ok": True,
                    "status": "skipped",
                    "message": "无活跃游戏，已跳过本次管线。",
                    "ingest": {
                        "status": "no_active_games",
                        "message": "暂无活跃游戏，本次未执行采集。",
                        "ingested_count": 0,
                        "combos_total": 0,
                        "force_recrawl": force_recrawl,
                    },
                    "external_sync": None,
                    "signals_count": 0,
                    "demands_count": 0,
                    "report_id": None,
                }

            count = await adapter.ingest_contents(game_ids, force_recrawl=force_recrawl)
            logger.info(f"[DailyPipeline] 数据接入完成 - {count} 条内容")

            # --- Step 2: 信号计算 ---
            engine = SignalEngine(session)
            signals = await engine.compute_all_signals(game_ids, today)
            logger.info(f"[DailyPipeline] 信号计算完成 - {len(signals)} 条信号")

            # --- Step 3: LLM 分析 ---
            pipeline = LLMPipeline(session)
            demands = await pipeline.run_pipeline(game_ids, today)
            logger.info(f"[DailyPipeline] LLM分析完成 - {len(demands)} 条需求")

            # --- Step 4: 日报生成 ---
            report_gen = ReportGenerator(session)
            report = await report_gen.generate_daily_report(today)
            logger.info(f"[DailyPipeline] 日报生成完成 - {report.id}")
            return {
                "ok": True,
                "status": "completed",
                "message": "管线执行完成",
                "external_sync": external_sync,
                "ingest": adapter.last_ingest_result,
                "signals_count": len(signals),
                "demands_count": len(demands),
                "report_id": report.id,
            }

        except Exception as e:
            logger.exception(f"[DailyPipeline] 执行失败: {e}")
            await session.rollback()
            return {
                "ok": False,
                "status": "failed",
                "message": str(e),
                "external_sync": None,
                "ingest": {
                    "status": "failed",
                    "message": "管线执行失败，未能确认采集状态。",
                    "ingested_count": 0,
                    "combos_total": 0,
                    "force_recrawl": force_recrawl,
                },
                "signals_count": 0,
                "demands_count": 0,
                "report_id": None,
            }


def start_scheduler():
    """启动每日定时调度。"""
    scheduler.add_job(
        run_daily_pipeline,
        trigger=CronTrigger(hour=settings.schedule_hour, minute=settings.schedule_minute),
        id="daily_demand_pipeline",
        name="每日需求挖掘管线",
        replace_existing=True,
    )
    scheduler.add_job(
        run_tap_kb_realtime_sync,
        trigger=IntervalTrigger(minutes=1),
        id="tap_kb_realtime_sync",
        name="Tap+快爆后台实时增量同步",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_radar_realtime_scan,
        trigger=IntervalTrigger(minutes=1),
        id="radar_realtime_scan",
        name="早期需求雷达实时扫描",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_priority_game_exploration,
        trigger=IntervalTrigger(minutes=5),
        id="radar_priority_exploration",
        name="重点游戏宽口径探索",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_regular_game_exploration,
        trigger=IntervalTrigger(minutes=30),
        id="radar_regular_exploration",
        name="普通游戏宽口径探索",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        f"调度器已启动 - 每日 {settings.schedule_hour:02d}:{settings.schedule_minute:02d} 完整分析，"
        "Tap+快爆及雷达每1分钟，重点游戏探索每5分钟，普通游戏探索每30分钟"
    )


def stop_scheduler():
    """停止调度器。"""
    scheduler.shutdown(wait=False)
    logger.info("调度器已停止")
