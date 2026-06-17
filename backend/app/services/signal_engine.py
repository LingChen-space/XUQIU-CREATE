"""需求信号评分引擎。

对每款游戏计算多个维度的需求信号分 (0-100)，为 LLM 分析提供数据基础。
"""

import json
from datetime import datetime, timedelta, date
from collections import defaultdict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Game
from app.models.platform_content import PlatformContent, ContentType
from app.models.demand_signal import DemandSignal, SignalType
from app.utils.text_similarity import detect_repeat_questions
from app.utils.engagement import compute_content_hot_score
from app.utils.keyword_matcher import (
    detect_external_platform_tools,
    detect_grassroots_tools,
    detect_scarcity_signal,
)


class SignalEngine:
    """需求信号计算引擎。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute_all_signals(self, game_ids: list[str], window_date: date) -> list[DemandSignal]:
        """对一批游戏计算全部信号，写入 demand_signals 表。"""
        all_signals = []

        for gid in game_ids:
            # 获取该游戏过去 24h 的内容
            cutoff = datetime.combine(window_date, datetime.min.time()) - timedelta(hours=24)
            end = datetime.combine(window_date, datetime.min.time()) + timedelta(hours=24)

            stmt = select(PlatformContent).where(
                and_(
                    PlatformContent.game_id == gid,
                    PlatformContent.published_at >= cutoff,
                    PlatformContent.published_at < end,
                )
            )
            result = await self.session.execute(stmt)
            contents = result.scalars().all()

            if not contents:
                continue

            all_texts = [c.title + " " + c.body for c in contents if c.title or c.body]
            all_urls = [c.url for c in contents]

            # 1. 重复提问密度 (0-100)
            repeat_score = await self._compute_repeat_question(contents, all_texts)
            # 2. 信息分散度 (0-100)
            scatter_score = await self._compute_info_scatter(contents)
            # 3. 民间工具萌芽 (0-100)
            grassroots_score = self._compute_grassroots(contents, all_texts, all_urls)
            # 4. 资格稀缺信号 (0-100)
            scarcity_score = self._compute_scarcity(contents, all_texts)
            # 5. 机制复杂度 (0-100) — 基于内容提及的系统参数数量估算
            complexity_score = await self._compute_complexity(contents, all_texts)
            # 6. 内容热度 (0-100)
            heat_score = self._compute_content_heat(contents)
            # 7. 外部平台工具上线 (0-100)
            external_platform_score = self._compute_external_platform_tool(contents, all_texts, all_urls)

            scores = {
                SignalType.repeat_question: repeat_score,
                SignalType.info_scatter: scatter_score,
                SignalType.grassroots_tool: grassroots_score,
                SignalType.scarcity: scarcity_score,
                SignalType.mechanism_complexity: complexity_score,
                SignalType.content_heat: heat_score,
                SignalType.external_platform_tool: external_platform_score,
            }

            for signal_type, score in scores.items():
                signal = DemandSignal(
                    game_id=gid,
                    signal_type=signal_type,
                    score=round(score, 1),
                    window_date=window_date,
                )
                self.session.add(signal)
                all_signals.append(signal)

        await self.session.commit()
        return all_signals

    # ── 各维度计算 ──────────────────────────────────────────────────────────

    async def _compute_repeat_question(self, contents: list[PlatformContent], all_texts: list[str]) -> float:
        """重复提问密度：检测相似问题的密度。"""
        if len(all_texts) < 2:
            return 0.0

        # 只检测帖子类型的文本
        post_texts = [c.title + " " + c.body for c in contents if c.content_type == ContentType.post]
        if len(post_texts) < 2:
            post_texts = all_texts

        ratio = detect_repeat_questions(post_texts, settings.signal_repeat_question_threshold)
        # 映射到 0-100: ratio=0.5 对应高分
        score = min(100.0, ratio * 200)
        return round(score, 1)

    async def _compute_info_scatter(self, contents: list[PlatformContent]) -> float:
        """
        信息分散度：攻略/信息是否碎片化分布。
        内容数越多且非集中在少数几个来源 => 分越高。
        """
        n = len(contents)
        if n == 0:
            return 0.0

        # 计算作者集中度：unique_authors / total
        authors = [c.author for c in contents if c.author]
        unique_ratio = len(set(authors)) / max(len(authors), 1)

        # 超过阈值的碎片帖数量
        if n > settings.signal_info_scatter_threshold:
            scatter = min(100.0, (n / 20) * 60 + unique_ratio * 40)
        else:
            scatter = unique_ratio * 30

        return round(scatter, 1)

    def _compute_grassroots(self, contents: list[PlatformContent], all_texts: list[str], all_urls: list[str]) -> float:
        """民间工具萌芽：检测用户自制的工具/文档。"""
        strength, evidence = detect_grassroots_tools(all_texts, all_urls)
        # 强度 0-1 映射到 0-100: 线性映射并加成
        score = min(100.0, strength * 100)
        return round(score, 1)

    def _compute_external_platform_tool(
        self,
        contents: list[PlatformContent],
        all_texts: list[str],
        all_urls: list[str],
    ) -> float:
        """外部平台工具上线：检测已有同类工具入口、链接或上线信息。"""
        strength, evidence = detect_external_platform_tools(all_texts, all_urls)
        score = min(100.0, strength * 100)
        return round(score, 1)

    def _compute_scarcity(self, contents: list[PlatformContent], all_texts: list[str]) -> float:
        """资格稀缺信号：检测限量/抢码/体验服关键词。"""
        strength, keywords = detect_scarcity_signal(all_texts)
        score = min(100.0, strength * 100)
        return round(score, 1)

    async def _compute_complexity(self, contents: list[PlatformContent], all_texts: list[str]) -> float:
        """
        机制复杂度：从内容中估算游戏系统的参数维度。
        检测内容中提及的属性/参数类词汇的密度。
        """
        complexity_keywords = [
            "属性", "参数", "数值", "伤害", "防御", "暴击", "攻击力", "血量",
            "阈值", "上限", "下限", "公式", "倍率", "系数", "概率", "保底",
            "词条", "套装", "配装", "天赋", "技能等级", "突破", "材料",
            "百分比", "加成", "减免", "触发", "战备", "配件", "武器",
        ]

        combined = " ".join(all_texts)
        hit_count = 0
        for kw in complexity_keywords:
            hit_count += combined.count(kw)

        if len(all_texts) == 0:
            return 0.0

        # 每篇内容平均命中关键词数
        avg_hits = hit_count / len(all_texts)
        # 映射：avg_hits=1 => 10分, avg_hits=10 => 100分
        score = min(100.0, avg_hits * 10)
        return round(score, 1)

    def _compute_content_heat(self, contents: list[PlatformContent]) -> float:
        """内容热度：综合总量热度，并加入单篇高互动帖子加成。"""
        if not contents:
            return 0.0

        total_views = sum(c.view_count for c in contents)
        total_likes = sum(c.like_count for c in contents)
        total_comments = sum(c.comment_count for c in contents)
        total_shares = sum(c.share_count for c in contents)

        aggregate_score = compute_content_hot_score(total_views, total_likes, total_comments, total_shares)
        single_scores = [
            compute_content_hot_score(c.view_count, c.like_count, c.comment_count, c.share_count)
            for c in contents
            if c.content_type in (ContentType.post, ContentType.video, ContentType.search_term)
        ]
        single_post_score = max(single_scores) if single_scores else 0.0
        score = min(100.0, aggregate_score * 0.75 + single_post_score * 0.35)
        return round(score, 1)

    async def get_signals_for_game(self, game_id: str, window_date: date) -> dict:
        """获取某游戏在指定日期的需求信号。"""
        stmt = select(DemandSignal).where(
            and_(DemandSignal.game_id == game_id, DemandSignal.window_date == window_date)
        )
        result = await self.session.execute(stmt)
        signals = result.scalars().all()

        return {s.signal_type.value: s.score for s in signals}
