"""游戏信息表。"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.sqlite import TEXT
import enum

from app.database import Base


class GameStatus(str, enum.Enum):
    """游戏状态（中文枚举）。"""
    active = "\u70ed\u95e8"           # 热门
    operating = "\u5728\u8fd0\u8425"  # 在运营
    testing = "\u6d4b\u8bd5\u4e2d"    # 测试中
    inactive = "\u5df2\u505c\u8fd0"   # 已停运

class GameGenre(str, enum.Enum):
    """游戏品类（中文枚举）。"""
    rpg = "RPG"
    fps = "FPS"
    moba = "MOBA"
    strategy = "\u7b56\u7565"
    casual = "\u4f11\u95f2"
    card = "\u5361\u724c"
    simulation = "\u6a21\u62df\u7ecf\u8425"
    battle_royale = "\u5403\u9e21"
    open_world = "\u5f00\u653e\u4e16\u754c"
    mmorpg = "MMORPG"
    other = "\u5176\u4ed6"


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="\u6e38\u620f\u540d\u79f0")
    genre: Mapped[GameGenre] = mapped_column(SAEnum(GameGenre), nullable=False, default=GameGenre.other, comment="\u54c1\u7c7b")
    publisher: Mapped[str] = mapped_column(String(128), default="", comment="\u5382\u5546")
    status: Mapped[GameStatus] = mapped_column(SAEnum(GameStatus), nullable=False, default=GameStatus.operating, comment="\u4e0a\u7ebf\u72b6\u6001")
    haoyou_id: Mapped[str] = mapped_column(String(64), default="", comment="\u597d\u6e38\u5feb\u7206\u5185\u90e8ID")
    cover_url: Mapped[str] = mapped_column(String(512), default="", comment="\u5c01\u9762\u56feURL")
    description: Mapped[str] = mapped_column(TEXT, default="", comment="\u6e38\u620f\u7b80\u4ecb")
    notes: Mapped[str] = mapped_column(TEXT, default="", comment="\u7f16\u8f91\u5907\u6ce8")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Game {self.name}>"
