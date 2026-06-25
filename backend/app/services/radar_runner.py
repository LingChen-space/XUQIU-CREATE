"""早期需求雷达回填、扫描与调度入口。"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_content import PlatformContent
from app.models.radar import (
    ContentConcept,
    ContentMetricSnapshot,
    ContentScanState,
)
from app.services.engagement_surge import EngagementSurgeDetector
from app.services.radar import RadarService, normalize_concept
from app.services.radar_model import RadarModelReviewer


def exploration_interval_minutes(priority_weight: int) -> int:
    return 5 if int(priority_weight or 1) >= 3 else 30


async def backfill_radar_history(session: AsyncSession) -> int:
    """为历史内容建立基线，不生成提醒。"""
    contents = (
        await session.execute(
            select(PlatformContent)
            .outerjoin(ContentScanState, ContentScanState.content_id == PlatformContent.id)
            .where(ContentScanState.content_id.is_(None))
        )
    ).scalars().all()
    radar = RadarService(session)
    for content in contents:
        session.add(ContentScanState(
            content_id=content.id,
            rule_status="completed",
            model_status="completed",
            rule_scanned_at=datetime.now(),
            model_scanned_at=datetime.now(),
        ))
        session.add(ContentMetricSnapshot(
            content_id=content.id,
            platform=content.platform,
            view_count=content.view_count,
            like_count=content.like_count,
            comment_count=content.comment_count,
            share_count=content.share_count,
        ))
        for concept in radar._extract_concepts(content):
            normalized = normalize_concept(concept)
            existing = (
                await session.execute(
                    select(ContentConcept).where(
                        ContentConcept.game_id == content.game_id,
                        ContentConcept.concept_type == "new_term",
                        ContentConcept.normalized_value == normalized,
                    )
                )
            ).scalar()
            if existing is None:
                session.add(ContentConcept(
                    game_id=content.game_id,
                    content_id=content.id,
                    concept_type="new_term",
                    value=concept,
                    normalized_value=normalized,
                    occurrence_count=1,
                ))
            else:
                existing.occurrence_count += 1
                existing.last_seen_at = datetime.now()
    await session.commit()
    return len(contents)


async def run_radar_scan_cycle(session: AsyncSession) -> dict:
    """规则优先扫描全部新内容，再做模型批量审阅和增速检测。"""
    missing_contents = (
        await session.execute(
            select(PlatformContent)
            .outerjoin(ContentScanState, ContentScanState.content_id == PlatformContent.id)
            .where(ContentScanState.content_id.is_(None))
            .limit(500)
        )
    ).scalars().all()
    for content in missing_contents:
        session.add(ContentScanState(content_id=content.id))
        session.add(ContentMetricSnapshot(
            content_id=content.id,
            platform=content.platform,
            view_count=content.view_count,
            like_count=content.like_count,
            comment_count=content.comment_count,
            share_count=content.share_count,
        ))
    if missing_contents:
        await session.commit()

    radar = RadarService(session)
    rule_content_ids = (
        await session.execute(
            select(ContentScanState.content_id)
            .where(ContentScanState.rule_status == "pending")
            .limit(500)
        )
    ).scalars().all()
    for content_id in rule_content_ids:
        await radar.scan_content_rules(content_id)

    due_game_ids = (
        await session.execute(
            select(PlatformContent.game_id)
            .join(ContentScanState, ContentScanState.content_id == PlatformContent.id)
            .where(
                ContentScanState.model_status.in_(["pending", "retry_wait"]),
                (
                    ContentScanState.next_retry_at.is_(None)
                    | (ContentScanState.next_retry_at <= datetime.now())
                ),
            )
            .distinct()
        )
    ).scalars().all()
    reviewed = 0
    reviewer = RadarModelReviewer(session)
    for game_id in due_game_ids:
        reviewed += await reviewer.review_game(game_id)

    recent_snapshot_ids = (
        await session.execute(
            select(ContentMetricSnapshot.content_id)
            .where(ContentMetricSnapshot.captured_at >= datetime.now() - timedelta(minutes=10))
            .distinct()
        )
    ).scalars().all()
    surge_count = 0
    detector = EngagementSurgeDetector(session)
    for content_id in recent_snapshot_ids:
        if await detector.evaluate_content(content_id):
            surge_count += 1

    return {
        "states_created": len(missing_contents),
        "rule_scanned": len(rule_content_ids),
        "model_reviewed": reviewed,
        "surges": surge_count,
    }
