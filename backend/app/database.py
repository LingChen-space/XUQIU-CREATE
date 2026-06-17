"""数据库引擎与会话管理。"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """创建所有表。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 迁移: 为已存在的 platform_search_configs 表添加 crawl_count 列
        try:
            await conn.run_sync(lambda c: c.exec_driver_sql("ALTER TABLE platform_search_configs ADD COLUMN crawl_count INTEGER NOT NULL DEFAULT 50"))
        except Exception:
            pass  # 列已存在则忽略
        try:
            await conn.run_sync(lambda c: c.exec_driver_sql("ALTER TABLE platform_contents ADD COLUMN source_id VARCHAR(128) NOT NULL DEFAULT ''"))
        except Exception:
            pass
        try:
            await conn.run_sync(lambda c: c.exec_driver_sql("ALTER TABLE crawl_progress ADD COLUMN result_detail TEXT"))
        except Exception:
            pass
        try:
            await conn.run_sync(lambda c: c.exec_driver_sql("ALTER TABLE games ADD COLUMN priority_weight INTEGER NOT NULL DEFAULT 1"))
        except Exception:
            pass
        await conn.run_sync(lambda c: c.exec_driver_sql(
            "UPDATE games SET priority_weight = 3 "
            "WHERE priority_weight = 1 AND name IN ('三角洲行动', '洛克王国：世界', '洛克王国世界', '失控进化')"
        ))
        await conn.run_sync(lambda c: c.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_platform_contents_source_id ON platform_contents (source_id)"))
        await conn.run_sync(lambda c: c.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_platform_contents_platform_source_id ON platform_contents (platform, source_id)"))
