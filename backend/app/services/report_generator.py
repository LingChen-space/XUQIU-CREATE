"""日报生成器 — 汇总当日需求和信号数据，生成结构化日报。"""

import json
import uuid
from datetime import date, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.demand import Demand
from app.models.daily_report import DailyReport


SUMMARY_PROMPT = """以下是好游快爆需求发生工具今日挖掘到的游戏工具需求：

{demand_summaries}

请用一段话（100字以内）总结今天最重要的需求发现和趋势，语气简洁专业。"""


class ReportGenerator:
    """日报生成器。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_daily_report(self, report_date: date) -> DailyReport:
        """生成指定日期的日报。"""
        # 获取当日需求
        stmt = (
            select(Demand)
            .where(Demand.demand_date == report_date)
            .order_by(Demand.potential_score.desc())
        )
        result = await self.session.execute(stmt)
        demands = result.scalars().all()

        # TOP 10 需求
        top_demands = demands[:10]
        top_ids = [d.id for d in top_demands]

        # 构建摘要
        if len(top_demands) > 0:
            summary_parts = []
            for d in top_demands[:5]:
                # 获取游戏名
                game_stmt = select(Game).where(Game.id == d.game_id)
                game_result = await self.session.execute(game_stmt)
                game = game_result.scalar()
                game_name = game.name if game else "未知游戏"
                summary_parts.append(f"{game_name}·{d.tool_type.value}：{d.title}（潜力分{d.potential_score:.0f}）")
            summary = "今日热点需求：\n" + "\n".join(summary_parts)
        else:
            summary = f"{report_date} 暂无满足阈值的新需求。"

        # 创建日报
        report = DailyReport(
            id=str(uuid.uuid4()),
            report_date=report_date,
            summary=summary,
            top_demand_ids=json.dumps(top_ids, ensure_ascii=False),
            trending_game_ids=json.dumps([d.game_id for d in top_demands[:5]], ensure_ascii=False),
            total_demands=len(demands),
        )
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)

        return report

    async def get_report_by_date(self, report_date: date) -> DailyReport | None:
        """按日期获取日报。"""
        stmt = select(DailyReport).where(DailyReport.report_date == report_date)
        result = await self.session.execute(stmt)
        return result.scalar()

    async def get_latest_report(self) -> DailyReport | None:
        """获取最新一期日报。"""
        stmt = select(DailyReport).order_by(DailyReport.report_date.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar()

