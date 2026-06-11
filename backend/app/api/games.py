"""游戏相关 API。"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.game import Game, GameGenre, GameStatus
from app.schemas.game import GameCreate, GameUpdate, GameOut

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
    stmt = stmt.order_by(Game.name)

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
