"""日报生成器 — 汇总当日需求和信号数据，生成结构化日报。

每日固定用 LLM 对当日需求挖掘情况做总结分析，写入 DailyReport.summary；
LLM 未配置或失败时回退到规则模板摘要。
"""

import json
import uuid
from collections import Counter
from datetime import date, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Game, GameStatus
from app.models.demand import Demand
from app.models.daily_report import DailyReport
from app.schemas.demand import compute_demand_level
from app.services.llm_client import build_async_client

# 与首页 dashboard 一致：该日临时展示全部历史需求，其余日期仅今日
HISTORY_SHOWCASE_DATE = date(2026, 6, 24)


class ReportGenerator:
    """日报生成器。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_daily_report(self, report_date: date) -> DailyReport:
        """生成指定日期的日报；同一天已存在日报时更新原记录。

        每日固定用 LLM 对当日需求挖掘情况做总结分析，写入 report.summary；
        LLM 未配置或失败时回退到规则模板摘要。
        """
        # 获取要展示/总结的需求（与首页 dashboard 口径一致：showcase 日取全部历史，其余仅今日；限活跃游戏；不去重）
        demands = await self._display_demands(report_date)

        # TOP 10 需求（按潜力分；去重避免同游戏同类重复占位）
        top_demands = self._dedupe_demands(demands)[:10]
        top_ids = [d.id for d in top_demands]

        # 批量取游戏名
        game_ids = {d.game_id for d in top_demands}
        games_map: dict[str, Game] = {}
        if game_ids:
            g_stmt = select(Game).where(Game.id.in_(game_ids))
            for g in (await self.session.execute(g_stmt)).scalars().all():
                games_map[g.id] = g

        # 规则模板摘要（回退 + LLM 输入）
        if top_demands:
            template_parts = []
            for d in top_demands[:5]:
                g = games_map.get(d.game_id)
                gname = g.name if g else "未知游戏"
                template_parts.append(f"{gname}·{d.tool_type.value}：{d.title}（潜力分{d.potential_score:.0f}）")
            template_summary = "今日热点需求：\n" + "\n".join(template_parts)
        else:
            template_summary = f"{report_date} 暂无满足阈值的新需求。"

        # 每日 LLM 总结分析（失败回退模板）
        summary = await self._llm_summary(report_date, demands, top_demands, games_map, template_summary)

        trending_game_ids = []
        seen_game_ids = set()
        for d in top_demands:
            if d.game_id in seen_game_ids:
                continue
            seen_game_ids.add(d.game_id)
            trending_game_ids.append(d.game_id)
            if len(trending_game_ids) >= 5:
                break

        report_stmt = select(DailyReport).where(DailyReport.report_date == report_date)
        report_result = await self.session.execute(report_stmt)
        report = report_result.scalar()
        if report is None:
            report = DailyReport(id=str(uuid.uuid4()), report_date=report_date)
            self.session.add(report)

        report.summary = summary
        report.top_demand_ids = json.dumps(top_ids, ensure_ascii=False)
        report.trending_game_ids = json.dumps(trending_game_ids, ensure_ascii=False)
        report.total_demands = len(demands)

        await self.session.commit()
        await self.session.refresh(report)

        return report

    async def _llm_summary(
        self,
        report_date: date,
        demands: list[Demand],
        top_demands: list[Demand],
        games_map: dict[str, Game],
        fallback: str,
    ) -> str:
        """用 LLM 生成当日需求挖掘总结分析；未配置或失败时回退到规则模板。"""
        if not demands or not top_demands:
            return fallback

        client = build_async_client()
        if client is None:
            return fallback

        # 等级分布
        level_counts = Counter(compute_demand_level(d.potential_score) for d in demands)
        # 工具类型分布
        type_counts = Counter(d.tool_type.value for d in demands)
        # 信号均值
        signal_totals: dict[str, float] = {}
        signal_n = 0
        for d in demands:
            try:
                sig = json.loads(d.signal_snapshot or "{}")
            except (json.JSONDecodeError, TypeError):
                sig = {}
            if not sig:
                continue
            signal_n += 1
            for k, v in sig.items():
                if isinstance(v, (int, float)):
                    signal_totals[k] = signal_totals.get(k, 0.0) + float(v)
        signal_avg = {k: round(v / signal_n, 1) for k, v in signal_totals.items()} if signal_n else {}

        # 构建上下文
        lines = [f"日期：{report_date}", f"需求总数：{len(demands)}"]
        level_str = "、".join(f"{lv}{level_counts[lv]}条" for lv in ["S级", "A级", "B级", "C级"] if level_counts.get(lv))
        if level_str:
            lines.append(f"等级分布：{level_str}")
        avg_score = sum(d.potential_score for d in demands) / len(demands)
        lines.append(f"平均潜力分：{avg_score:.0f}")
        if type_counts:
            lines.append("工具类型分布：" + "、".join(f"{t}({c}条)" for t, c in type_counts.most_common()))
        if signal_avg:
            top_sigs = sorted(signal_avg.items(), key=lambda x: x[1], reverse=True)[:4]
            lines.append("信号分(均值)：" + "、".join(f"{k}{v}" for k, v in top_sigs))
        lines.append("TOP需求：")
        for i, d in enumerate(top_demands[:8], 1):
            g = games_map.get(d.game_id)
            gname = g.name if g else "未知游戏"
            lines.append(
                f"{i}. [{compute_demand_level(d.potential_score)}] {gname}·{d.tool_type.value}："
                f"{d.title}（潜力分{d.potential_score:.0f}，可行度{d.tool_feasibility}/5）"
            )
        context = "\n".join(lines)

        prompt = (
            "你是好游快爆需求分析助手。请根据今日需求挖掘数据，写一段 150-250 字的总结分析，"
            "用于首页「每日需求洞察总结」展示。要求：突出今日最重要的需求发现与趋势；"
            "点出热门工具方向和值得跟进的游戏；语气专业简洁，可适当用 **加粗** 强调；"
            "只输出总结正文，不要标题、不要重复罗列全部数据。\n\n"
            f"今日数据：\n{context}"
        )

        try:
            resp = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "你是游戏工具需求分析师，用中文输出简洁专业的需求总结。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=500,
            )
            text = (resp.choices[0].message.content or "").strip()
            return text or fallback
        except Exception as e:  # noqa: BLE001 - 回退模板，不阻断管线
            print(f"[Report] LLM 总结生成失败，回退规则模板：{e}")
            return fallback

    async def _display_demands(self, report_date: date) -> list[Demand]:
        """与首页 dashboard 一致的需求口径，保证总结与展示一致。

        showcase 日（HISTORY_SHOWCASE_DATE）展示全部历史需求，其余日期仅当日；
        限定活跃游戏（status != inactive）；不去重（与 dashboard 的 total 口径一致）。
        """
        is_showcase = report_date == HISTORY_SHOWCASE_DATE
        active_ids = [
            row[0]
            for row in (
                await self.session.execute(
                    select(Game.id).where(Game.status != GameStatus.inactive)
                )
            ).all()
        ]
        stmt = select(Demand)
        if active_ids:
            stmt = stmt.where(Demand.game_id.in_(active_ids))
        if not is_showcase:
            stmt = stmt.where(Demand.demand_date == report_date)
        stmt = stmt.order_by(Demand.potential_score.desc())
        return (await self.session.execute(stmt)).scalars().all()

    def _dedupe_demands(self, demands: list[Demand]) -> list[Demand]:
        """按游戏、工具类型、标题去重，保留潜力分最高的一条。"""
        unique: dict[tuple[str, str, str], Demand] = {}
        for demand in demands:
            key = (
                demand.game_id,
                demand.tool_type.value,
                demand.title.strip(),
            )
            existing = unique.get(key)
            if existing is None or demand.potential_score > existing.potential_score:
                unique[key] = demand
        return sorted(
            unique.values(),
            key=lambda d: d.potential_score,
            reverse=True,
        )

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

