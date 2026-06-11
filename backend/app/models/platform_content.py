"""平台内容表。"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Float, ForeignKey, Enum as SAEnum, func, Text
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.database import Base


class ContentPlatform(str, enum.Enum):
    bilibili = "B站"
    douyin = "抖音"
    taptap = "TapTap"
    xiaoheihe = "小黑盒"
    nga = "NGA"
    weibo = "微博"
    tieba = "贴吧"
    other = "其他"


class ContentType(str, enum.Enum):
    video = "视频"
    post = "帖子"
    comment = "评论"
    search_term = "搜索词"


class PlatformContent(Base):
    __tablename__ = "platform_contents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_id: Mapped[str] = mapped_column(String(36), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联游戏")
    platform: Mapped[ContentPlatform] = mapped_column(SAEnum(ContentPlatform), nullable=False, comment="来源平台")
    content_type: Mapped[ContentType] = mapped_column(SAEnum(ContentType), nullable=False, comment="内容类型")
    url: Mapped[str] = mapped_column(String(1024), default="", comment="原文URL")
    title: Mapped[str] = mapped_column(String(512), default="", comment="标题")
    body: Mapped[str] = mapped_column(Text, default="", comment="正文/简介")
    author: Mapped[str] = mapped_column(String(128), default="", comment="作者")
    view_count: Mapped[int] = mapped_column(Integer, default=0, comment="浏览/播放量")
    like_count: Mapped[int] = mapped_column(Integer, default=0, comment="点赞数")
    comment_count: Mapped[int] = mapped_column(Integer, default=0, comment="评论数")
    share_count: Mapped[int] = mapped_column(Integer, default=0, comment="转发/分享数")
    hot_score: Mapped[float] = mapped_column(Float, default=0.0, comment="平台热度分(0-100)")
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="发布时间")
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="采集时间")

    # 扩展字段，存 JSON 字符串
    extra_data: Mapped[str] = mapped_column(Text, default="{}", comment="扩展数据JSON: 高赞评论、标签等")

    def __repr__(self):
        return f"<PlatformContent {self.platform.value} {self.title[:30]}>"
