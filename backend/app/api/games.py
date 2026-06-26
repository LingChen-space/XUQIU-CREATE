"""游戏相关 API。"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.game import Game, GameGenre, GameStatus, default_priority_weight
from app.models.platform_search_config import PlatformSearchConfig
from app.schemas.game import GameCreate, GameUpdate, GameOut

TAP_PROXY_PLATFORM = "taptap"


class TapTapGroupPayload(BaseModel):
    group_id: str = ""

router = APIRouter(prefix="/api/games", tags=["games"])


def _game_to_out(game: Game) -> GameOut:
    return GameOut(
        id=game.id,
        name=game.name,
        genre=game.genre.value if game.genre else "",
        publisher=game.publisher or "",
        status=game.status.value if game.status else "",
        haoyou_id=game.haoyou_id or "",
        cover_url=game.cover_url or "",
        priority_weight=game.priority_weight or 1,
        description=game.description or "",
        notes=game.notes or "",
        created_at=game.created_at,
        updated_at=game.updated_at,
    )


@router.get("", response_model=list[GameOut])
async def list_games(
    status: str | None = None,
    genre: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """获取游戏列表，支持按状态和品类筛选。"""
    stmt = select(Game)
    if status:
        stmt = stmt.where(Game.status == status)
    if genre:
        stmt = stmt.where(Game.genre == genre)
    stmt = stmt.order_by(Game.priority_weight.desc(), Game.name)

    result = await db.execute(stmt)
    games = result.scalars().all()
    return [_game_to_out(g) for g in games]


@router.get("/{game_id}", response_model=GameOut)
async def get_game(game_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个游戏详情。"""
    stmt = select(Game).where(Game.id == game_id)
    result = await db.execute(stmt)
    game = result.scalar()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    return _game_to_out(game)


@router.post("", response_model=GameOut, status_code=201)
async def create_game(payload: GameCreate, db: AsyncSession = Depends(get_db)):
    """手动添加监控游戏。"""
    genre_map = {e.value: e for e in GameGenre}
    genre_enum = genre_map.get(payload.genre, GameGenre.other)
    status_map = {e.value: e for e in GameStatus}
    status_enum = status_map.get(payload.status, GameStatus.operating)

    game = Game(
        id=str(uuid.uuid4()),
        name=payload.name,
        genre=genre_enum,
        publisher=payload.publisher or "",
        status=status_enum,
        haoyou_id=payload.haoyou_id or "",
        cover_url=payload.cover_url or "",
        priority_weight=payload.priority_weight or default_priority_weight(payload.name),
        description=payload.description or "",
        notes=payload.notes or "",
    )
    db.add(game)
    await db.commit()
    await db.refresh(game)
    return _game_to_out(game)


@router.put("/{game_id}", response_model=GameOut)
async def update_game(game_id: str, payload: GameUpdate, db: AsyncSession = Depends(get_db)):
    """编辑游戏信息。"""
    stmt = select(Game).where(Game.id == game_id)
    result = await db.execute(stmt)
    game = result.scalar()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    if payload.name is not None:
        game.name = payload.name
    if payload.genre is not None:
        genre_map = {e.value: e for e in GameGenre}
        game.genre = genre_map.get(payload.genre, GameGenre.other)
    if payload.publisher is not None:
        game.publisher = payload.publisher
    if payload.status is not None:
        status_map = {e.value: e for e in GameStatus}
        if payload.status not in status_map:
            raise HTTPException(status_code=400, detail=f"无效状态: {payload.status}")
        game.status = status_map[payload.status]
    if payload.haoyou_id is not None:
        game.haoyou_id = payload.haoyou_id
    if payload.cover_url is not None:
        game.cover_url = payload.cover_url
    if payload.priority_weight is not None:
        if payload.priority_weight < 1 or payload.priority_weight > 5:
            raise HTTPException(status_code=400, detail="游戏权重需在 1-5 之间")
        game.priority_weight = payload.priority_weight
    if payload.description is not None:
        game.description = payload.description
    if payload.notes is not None:
        game.notes = payload.notes

    await db.commit()
    await db.refresh(game)
    return _game_to_out(game)


@router.delete("/{game_id}")
async def delete_game(game_id: str, db: AsyncSession = Depends(get_db)):
    """删除游戏。"""
    stmt = select(Game).where(Game.id == game_id)
    result = await db.execute(stmt)
    game = result.scalar()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    await db.delete(game)
    await db.commit()
    return {"ok": True, "id": game_id}


@router.get("/{game_id}/taptap-group")
async def get_game_taptap_group(game_id: str, db: AsyncSession = Depends(get_db)):
    """获取游戏绑定的 TapTap 分组 group_id（Tap接口配置，供代理同步读取）。"""
    cfg = (
        await db.execute(
            select(PlatformSearchConfig).where(
                PlatformSearchConfig.game_id == game_id,
                PlatformSearchConfig.platform == TAP_PROXY_PLATFORM,
            )
        )
    ).scalar()
    return {"group_id": (cfg.keywords or "") if cfg else ""}


@router.put("/{game_id}/taptap-group")
async def set_game_taptap_group(
    game_id: str,
    payload: TapTapGroupPayload,
    db: AsyncSession = Depends(get_db),
):
    """设置/清空游戏的 TapTap 分组 group_id（写入 platform_search_configs platform=taptap）。"""
    game = (await db.execute(select(Game).where(Game.id == game_id))).scalar()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    group_id = (payload.group_id or "").strip()
    cfg = (
        await db.execute(
            select(PlatformSearchConfig).where(
                PlatformSearchConfig.game_id == game_id,
                PlatformSearchConfig.platform == TAP_PROXY_PLATFORM,
            )
        )
    ).scalar()

    if not group_id:
        if cfg is not None:
            await db.delete(cfg)
    elif cfg is None:
        db.add(PlatformSearchConfig(
            id=str(uuid.uuid4()),
            game_id=game_id,
            platform=TAP_PROXY_PLATFORM,
            keywords=group_id,
            enabled=True,
            crawl_count=10,
            source_key="tap_proxy",
        ))
    else:
        cfg.keywords = group_id
        cfg.enabled = True
        cfg.source_key = "tap_proxy"

    await db.commit()
    return {"ok": True, "game_id": game_id, "group_id": group_id}
