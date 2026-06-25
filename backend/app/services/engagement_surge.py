"""内容互动增速与动态基线检测。"""

import math
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_content import PlatformContent
from app.models.radar import ContentMetricSnapshot, RadarClue, RadarClueLevel
from app.services.radar import RadarService


MINIMUM_5M = {"views": 200, "likes": 10, "comments": 5, "shares": 3}


def weighted_velocity(delta_5m: dict[str, float]) -> float:
    return round(
        delta_5m["views"] * 0.001
        + delta_5m["likes"] * 0.4
        + delta_5m["comments"] * 1.2
        + delta_5m["shares"] * 1.5,
        3,
    )


def classify_surge(
    delta: dict[str, int],
    elapsed_minutes: float,
    baseline_scores: list[float],
    weighted_velocity: float | None = None,
    previous_velocity: float | None = None,
) -> dict | None:
    if elapsed_minutes <= 0:
        return None
    scale = 5.0 / elapsed_minutes
    delta_5m = {key: max(0.0, float(delta.get(key, 0))) * scale for key in MINIMUM_5M}
    if not any(delta_5m[key] >= threshold for key, threshold in MINIMUM_5M.items()):
        return None

    score = weighted_velocity if weighted_velocity is not None else globals()["weighted_velocity"](delta_5m)
    baseline = sorted(float(item) for item in baseline_scores)
    if len(baseline) >= 20:
        percentile = round(sum(1 for item in baseline if item <= score) / len(baseline) * 100, 1)
        if percentile >= 99:
            level = RadarClueLevel.urgent
        elif percentile >= 95:
            level = RadarClueLevel.important
        else:
            return None
        return {
            "level": level,
            "percentile": percentile,
            "velocity": score,
            "delta_5m": delta_5m,
        }

    if previous_velocity and previous_velocity > 0:
        ratio = score / previous_velocity
        if ratio >= 6:
            level = RadarClueLevel.urgent
        elif ratio >= 3:
            level = RadarClueLevel.important
        else:
            return None
        return {
            "level": level,
            "percentile": None,
            "velocity": score,
            "velocity_ratio": round(ratio, 2),
            "delta_5m": delta_5m,
        }
    return None


class EngagementSurgeDetector:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.radar = RadarService(session)

    async def evaluate_content(self, content_id: str) -> RadarClue | None:
        content = await self.session.get(PlatformContent, content_id)
        if content is None:
            return None
        snapshots = (
            await self.session.execute(
                select(ContentMetricSnapshot)
                .where(ContentMetricSnapshot.content_id == content_id)
                .order_by(ContentMetricSnapshot.captured_at.desc())
                .limit(3)
            )
        ).scalars().all()
        if len(snapshots) < 2:
            if content.hot_score < 70:
                return None
            clues = await self.radar.apply_system_findings(content.id, [{
                "type": "engagement_surge",
                "concept": content.source_id or content.title,
                "summary": "当前绝对热度较高，等待下一次快照确认增速。",
                "novelty": 30,
                "demand_intent": 20,
                "timeliness": 50,
                "engagement_velocity": 40,
                "external_validation": 0,
            }])
            return clues[0] if clues else None

        latest, previous = snapshots[0], snapshots[1]
        elapsed = max(
            (latest.captured_at - previous.captured_at).total_seconds() / 60,
            0.01,
        )
        delta = self._snapshot_delta(previous, latest)
        delta_5m = {key: value * 5 / elapsed for key, value in delta.items()}
        velocity = weighted_velocity(delta_5m)
        previous_velocity = None
        if len(snapshots) >= 3:
            older = snapshots[2]
            old_elapsed = max(
                (previous.captured_at - older.captured_at).total_seconds() / 60,
                0.01,
            )
            old_delta = self._snapshot_delta(older, previous)
            previous_velocity = weighted_velocity({
                key: value * 5 / old_elapsed for key, value in old_delta.items()
            })
        baseline = await self._baseline_scores(content, latest.captured_at)
        result = classify_surge(
            delta=delta,
            elapsed_minutes=elapsed,
            baseline_scores=baseline,
            weighted_velocity=velocity,
            previous_velocity=previous_velocity,
        )
        if result is None:
            return None

        delta_label = (
            f"{elapsed:.0f}分钟新增浏览{delta['views']}、点赞{delta['likes']}、"
            f"评论{delta['comments']}、分享{delta['shares']}"
        )
        rank_label = (
            f"，位于同平台同龄内容前{max(1, 100 - math.floor(result['percentile']))}%"
            if result.get("percentile") is not None
            else f"，较上一周期增速{result.get('velocity_ratio', 0)}倍"
        )
        clues = await self.radar.apply_system_findings(content.id, [{
            "type": "engagement_surge",
            "concept": content.source_id or content.title,
            "summary": f"{delta_label}{rank_label}",
            "trigger_reason": f"互动突增：{delta_label}{rank_label}",
            "novelty": 30,
            "demand_intent": 30,
            "timeliness": 100,
            "engagement_velocity": 100 if result["level"] == RadarClueLevel.urgent else 80,
            "external_validation": 0,
            "force_level": result["level"].value,
            "engagement_detail": result,
        }])
        return clues[0] if clues else None

    async def _baseline_scores(self, content: PlatformContent, captured_at: datetime) -> list[float]:
        since = captured_at - timedelta(days=7)
        rows = (
            await self.session.execute(
                select(ContentMetricSnapshot, PlatformContent)
                .join(PlatformContent, PlatformContent.id == ContentMetricSnapshot.content_id)
                .where(
                    ContentMetricSnapshot.platform == content.platform,
                    ContentMetricSnapshot.captured_at >= since,
                )
                .order_by(ContentMetricSnapshot.content_id, ContentMetricSnapshot.captured_at)
            )
        ).all()
        grouped: dict[str, list[tuple[ContentMetricSnapshot, PlatformContent]]] = defaultdict(list)
        for snapshot, item in rows:
            grouped[snapshot.content_id].append((snapshot, item))

        target_bucket = self._age_bucket(captured_at - content.published_at)
        scores: list[float] = []
        for pairs in grouped.values():
            for index in range(1, len(pairs)):
                previous, item = pairs[index - 1]
                latest, _ = pairs[index]
                if self._age_bucket(latest.captured_at - item.published_at) != target_bucket:
                    continue
                elapsed = (latest.captured_at - previous.captured_at).total_seconds() / 60
                if elapsed <= 0:
                    continue
                delta = self._snapshot_delta(previous, latest)
                scores.append(weighted_velocity({
                    key: value * 5 / elapsed for key, value in delta.items()
                }))
        return scores

    @staticmethod
    def _snapshot_delta(
        previous: ContentMetricSnapshot,
        latest: ContentMetricSnapshot,
    ) -> dict[str, int]:
        return {
            "views": max(0, latest.view_count - previous.view_count),
            "likes": max(0, latest.like_count - previous.like_count),
            "comments": max(0, latest.comment_count - previous.comment_count),
            "shares": max(0, latest.share_count - previous.share_count),
        }

    @staticmethod
    def _age_bucket(age: timedelta) -> str:
        hours = max(0, age.total_seconds() / 3600)
        if hours <= 1:
            return "0-1h"
        if hours <= 6:
            return "1-6h"
        if hours <= 24:
            return "6-24h"
        return "24h+"
