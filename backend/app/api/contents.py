# -*- coding: utf-8 -*-
"""Monitor data query API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import json

from app.database import get_db
from app.models.platform_content import PlatformContent, ContentPlatform

router = APIRouter(prefix="/api/contents", tags=["contents"])

PLATFORM_KEYS = [e.value for e in ContentPlatform]


def _content_source_key(extra_data: str) -> str:
    try:
        data = json.loads(extra_data or "{}")
    except (TypeError, ValueError):
        return "local"
    if isinstance(data, dict):
        return str(data.get("source_key") or "local")
    return "local"


@router.get("")
async def list_contents(
    game_id: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    search: str | None = Query(default=None),
    min_hot_score: float = Query(default=0),
    source_key: str | None = Query(default=None),
    days: int = Query(default=7),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now() - timedelta(days=days)
    stmt = select(PlatformContent).where(PlatformContent.collected_at >= since)

    if game_id:
        stmt = stmt.where(PlatformContent.game_id == game_id)
    if platform and platform in PLATFORM_KEYS:
        stmt = stmt.where(PlatformContent.platform == platform)
    if search:
        stmt = stmt.where(PlatformContent.title.contains(search))
    if min_hot_score > 0:
        stmt = stmt.where(PlatformContent.hot_score >= min_hot_score)
    if source_key:
        if source_key == "local":
            stmt = stmt.where(~PlatformContent.extra_data.contains('"source_key"'))
        else:
            stmt = stmt.where(PlatformContent.extra_data.contains(f'"source_key": "{source_key}"'))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total_count = count_result.scalar() or 0

    stmt = stmt.order_by(desc(PlatformContent.collected_at)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    contents = result.scalars().all()

    items = []
    for c in contents:
        items.append({
            "id": c.id,
            "game_id": c.game_id,
            "platform": c.platform.value,
            "content_type": c.content_type.value,
            "source_id": c.source_id,
            "url": c.url,
            "title": c.title,
            "body": c.body[:200] if c.body else "",
            "author": c.author,
            "view_count": c.view_count,
            "like_count": c.like_count,
            "comment_count": c.comment_count,
            "share_count": c.share_count,
            "hot_score": c.hot_score,
            "published_at": c.published_at.isoformat() if c.published_at else "",
            "collected_at": c.collected_at.isoformat() if c.collected_at else "",
            "source_key": _content_source_key(c.extra_data),
        })

    return {"total": total_count, "offset": offset, "limit": limit, "items": items}


@router.get("/stats")
async def get_content_stats(
    days: int = Query(default=7),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now() - timedelta(days=days)
    stmt = select(PlatformContent).where(PlatformContent.collected_at >= since)
    result = await db.execute(stmt)
    all_contents = result.scalars().all()

    total = len(all_contents)
    by_platform = {}
    by_source = {}
    by_date_map = {}

    for c in all_contents:
        pkey = c.platform.value if hasattr(c.platform, "value") else str(c.platform)
        source_key = _content_source_key(c.extra_data)
        by_platform[pkey] = by_platform.get(pkey, 0) + 1
        by_source[source_key] = by_source.get(source_key, 0) + 1
        dt_key = c.collected_at.strftime("%Y-%m-%d") if c.collected_at else "unknown"
        by_date_map[dt_key] = by_date_map.get(dt_key, 0) + 1

    by_date = [{"date": k, "count": v} for k, v in sorted(by_date_map.items())]

    return {"total": total, "days": days, "by_platform": by_platform, "by_source": by_source, "by_date": by_date}
