"""搜索词配置 API — 每款游戏多平台搜索关键词管理。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.game import Game
from app.models.platform_search_config import PlatformSearchConfig
from app.schemas.search_config import SearchConfigCreate, SearchConfigUpdate, SearchConfigOut

router = APIRouter(prefix="/api/search-configs", tags=["search-configs"])

PLATFORM_LABELS: dict[str, str] = {
    "douyin": "抖音",
    "taptap": "TapTap",
    "xiaoheihe": "小黑盒",
    "bilibili": "B站",
    "nga": "NGA",
    "weibo": "微博",
    "tieba": "贴吧",
}


def _to_out(cfg: PlatformSearchConfig) -> SearchConfigOut:
    return SearchConfigOut(
        id=cfg.id,
        game_id=cfg.game_id,
        platform=cfg.platform,
        keywords=cfg.keywords,
        enabled=cfg.enabled,
        crawl_count=cfg.crawl_count,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )


@router.get("/platforms")
async def list_platforms():
    """列出支持的平台列表。"""
    return [{"key": k, "label": v} for k, v in PLATFORM_LABELS.items()]


@router.get("", response_model=list[SearchConfigOut])
async def list_configs(
    db: AsyncSession = Depends(get_db),
):
    """获取搜索词配置列表，可按游戏筛选。"""
    stmt = select(PlatformSearchConfig).order_by(PlatformSearchConfig.platform)
    result = await db.execute(stmt)
    configs = result.scalars().all()
    return [_to_out(c) for c in configs]


@router.post("", response_model=SearchConfigOut, status_code=201)
async def create_config(
    payload: SearchConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    """为指定游戏新增一个平台的搜索词配置。"""

    # 检查是否已有同平台配置
    existing = await db.execute(
        select(PlatformSearchConfig).where(
            PlatformSearchConfig.platform == payload.platform,
        )
    )
    if existing.scalar():
        raise HTTPException(status_code=409, detail=f"该游戏已存在 {PLATFORM_LABELS.get(payload.platform, payload.platform)} 平台的搜索词配置")

    cfg = PlatformSearchConfig(
        platform=payload.platform,
        keywords=payload.keywords,
        enabled=payload.enabled,
        crawl_count=payload.crawl_count,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return _to_out(cfg)


@router.put("/{config_id}", response_model=SearchConfigOut)
async def update_config(
    config_id: str,
    payload: SearchConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新搜索词配置。"""
    stmt = select(PlatformSearchConfig).where(PlatformSearchConfig.id == config_id)
    result = await db.execute(stmt)
    cfg = result.scalar()
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")

    if payload.keywords is not None:
        cleaned = ",".join(kw.strip() for kw in payload.keywords.split(",") if kw.strip())
        if not cleaned:
            raise HTTPException(status_code=400, detail="至少需要一个搜索关键词")
        cfg.keywords = cleaned
    if payload.enabled is not None:
        cfg.enabled = payload.enabled
    if payload.crawl_count is not None:
        if payload.crawl_count < 10:
            raise HTTPException(status_code=400, detail="抓取条数不能少于10条")
        if payload.crawl_count > 1000:
            raise HTTPException(status_code=400, detail="抓取条数不能超过1000条")
        cfg.crawl_count = payload.crawl_count

    await db.commit()
    await db.refresh(cfg)
    return _to_out(cfg)


@router.delete("/{config_id}")
async def delete_config(config_id: str, db: AsyncSession = Depends(get_db)):
    """删除搜索词配置。"""
    stmt = select(PlatformSearchConfig).where(PlatformSearchConfig.id == config_id)
    result = await db.execute(stmt)
    cfg = result.scalar()
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")

    await db.delete(cfg)
    await db.commit()
    return {"ok": True}
