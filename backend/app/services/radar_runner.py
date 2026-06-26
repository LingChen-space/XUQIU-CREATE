"""早期需求雷达回填、扫描与调度入口。"""

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.platform_content import PlatformContent
from app.models.radar import (
    ContentConcept,
    ContentMetricHourly,
    ContentMetricSnapshot,
    ContentScanState,
    RadarClue,
    RadarClueStatus,
    RadarClueType,
)
from app.services.engagement_surge import EngagementSurgeDetector
from app.services.demand_keyword_rules import (
    is_experience_server,
    match_demand_keywords,
    rules_for_game,
)
from app.services.radar import RadarService, normalize_concept
from app.services.radar_model import RadarModelReviewer


def exploration_interval_minutes(priority_weight: int) -> int:
    return 5 if int(priority_weight or 1) >= 3 else 30


async def archive_nonstandard_radar_clues(session: AsyncSession) -> int:
    """归档旧规则产生、无法映射到当前标准词库的待处理线索。"""
    clues = (
        await session.execute(
            select(RadarClue).where(
                RadarClue.status.in_([
                    RadarClueStatus.pending,
                    RadarClueStatus.confirmed,
                ])
            )
        )
    ).scalars().all()
    games: dict[str, Game | None] = {}
    archived = 0
    for clue in clues:
        if clue.game_id not in games:
            games[clue.game_id] = await session.get(Game, clue.game_id)
        game = games[clue.game_id]
        # 体验服走 LLM 版本/爆料提取，不套标准词库，不参与归档
        if is_experience_server(game.name if game is not None else ""):
            continue
        standard_terms = (
            {rule.canonical_term for rule in rules_for_game(game.name)}
            if game is not None
            else set()
        )
        if (
            clue.clue_type != RadarClueType.new_demand
            or clue.term not in standard_terms
        ):
            clue.status = RadarClueStatus.archived
            clue.suppressed_until = None
            archived += 1
    if archived:
        await session.commit()
    return archived


async def compact_metric_snapshots(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> tuple[int, int]:
    """将30天前的明细快照按内容和小时聚合，然后删除已归档明细。"""
    cutoff = (now or datetime.now()) - timedelta(days=30)
    snapshots = (
        await session.execute(
            select(ContentMetricSnapshot)
            .where(ContentMetricSnapshot.captured_at < cutoff)
            .order_by(ContentMetricSnapshot.captured_at)
        )
    ).scalars().all()
    if not snapshots:
        return 0, 0

    grouped: dict[tuple[str, datetime], list[ContentMetricSnapshot]] = {}
    for snapshot in snapshots:
        hour_start = snapshot.captured_at.replace(minute=0, second=0, microsecond=0)
        grouped.setdefault((snapshot.content_id, hour_start), []).append(snapshot)

    for (content_id, hour_start), samples in grouped.items():
        hourly = (
            await session.execute(
                select(ContentMetricHourly).where(
                    ContentMetricHourly.content_id == content_id,
                    ContentMetricHourly.hour_start == hour_start,
                )
            )
        ).scalar()
        latest = samples[-1]
        if hourly is None:
            hourly = ContentMetricHourly(
                content_id=content_id,
                platform=latest.platform,
                hour_start=hour_start,
            )
            session.add(hourly)
        hourly.view_count = max(hourly.view_count or 0, *(sample.view_count for sample in samples))
        hourly.like_count = max(hourly.like_count or 0, *(sample.like_count for sample in samples))
        hourly.comment_count = max(
            hourly.comment_count or 0,
            *(sample.comment_count for sample in samples),
        )
        hourly.share_count = max(hourly.share_count or 0, *(sample.share_count for sample in samples))
        hourly.sample_count = (hourly.sample_count or 0) + len(samples)

    await session.flush()
    await session.execute(
        delete(ContentMetricSnapshot).where(
            ContentMetricSnapshot.id.in_([snapshot.id for snapshot in snapshots])
        )
    )
    await session.commit()
    return len(snapshots), len(grouped)


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
    games: dict[str, Game | None] = {}
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
        if content.game_id not in games:
            games[content.game_id] = await session.get(Game, content.game_id)
        game = games[content.game_id]
        if game is None:
            continue
        matches = match_demand_keywords(
            game.name,
            radar._content_text(content),
        )
        for match in matches:
            if (
                match.priority == "level_3"
                and content.published_at >= datetime.now() - timedelta(days=7)
            ):
                await radar._apply_keyword_match(
                    content,
                    game,
                    match,
                    radar._content_text(content),
                )
                continue
            concept = match.canonical_term
            normalized = normalize_concept(concept)
            existing = (
                await session.execute(
                    select(ContentConcept).where(
                        ContentConcept.game_id == content.game_id,
                        ContentConcept.concept_type == "standard_keyword",
                        ContentConcept.normalized_value == normalized,
                    )
                )
            ).scalar()
            if existing is None:
                session.add(ContentConcept(
                    game_id=content.game_id,
                    content_id=content.id,
                    concept_type="standard_keyword",
                    value=concept,
                    normalized_value=normalized,
                    occurrence_count=1,
                ))
            else:
                existing.occurrence_count += 1
                existing.last_seen_at = datetime.now()
    await session.commit()
    # 归档无法归一到标准词库的历史待处理线索（仅工具侧/非体验服；体验服走 LLM 提取，函数内跳过）。
    await archive_nonstandard_radar_clues(session)
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
    compacted_snapshots, hourly_rows = await compact_metric_snapshots(session)

    return {
        "states_created": len(missing_contents),
        "rule_scanned": len(rule_content_ids),
        "model_reviewed": reviewed,
        "surges": surge_count,
        "compacted_snapshots": compacted_snapshots,
        "hourly_rows": hourly_rows,
    }
