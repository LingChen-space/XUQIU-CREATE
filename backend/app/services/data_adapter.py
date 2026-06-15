# -*- coding: utf-8 -*-
"""数据接入层 —— 对接监控采集微服务 API，同时保留 Mock 回退。
断点续传：每个 (平台, 关键词) 组合独立采集-清洗-入库-提交，
中断后重新执行时通过 URL/标题去重自动跳过已有数据。"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Game, GameStatus, GameGenre
from app.models.platform_content import PlatformContent, ContentPlatform, ContentType
from app.models.platform_search_config import PlatformSearchConfig
from app.models.crawl_progress import CrawlProgress

logger = logging.getLogger(__name__)

# 平台标识映射
PLATFORM_MAP: dict[str, ContentPlatform] = {
    "douyin": ContentPlatform.douyin,
    "taptap": ContentPlatform.taptap,
    "xiaoheihe": ContentPlatform.xiaoheihe,
    "bilibili": ContentPlatform.bilibili,
    "nga": ContentPlatform.nga,
    "weibo": ContentPlatform.weibo,
    "tieba": ContentPlatform.tieba,
}

MONITOR_PLATFORM_ENDPOINTS: dict[str, str] = {
    "xiaoheihe": "/heybox",
    "taptap": "/taptap",
    "douyin": "/douyin",
}


# --- Mock 数据（开发阶段无监控服务时的回退） ---

MOCK_GAMES = [
    {"name": "三角洲行动", "genre": GameGenre.fps, "publisher": "腾讯", "status": GameStatus.operating,
     "description": "腾讯天美工作室出品的战术射击手游"},
    {"name": "原神", "genre": GameGenre.open_world, "publisher": "米哈游", "status": GameStatus.operating,
     "description": "开放世界冒险RPG"},
    {"name": "鸣潮", "genre": GameGenre.open_world, "publisher": "库洛游戏", "status": GameStatus.operating,
     "description": "开放世界动作RPG"},
    {"name": "火影忍者", "genre": GameGenre.rpg, "publisher": "腾讯", "status": GameStatus.operating,
     "description": "火影忍者正版授权格斗手游"},
    {"name": "洛克王国：世界", "genre": GameGenre.rpg, "publisher": "腾讯", "status": GameStatus.testing,
     "description": "洛克王国IP开放世界新作"},
    {"name": "崩坏：星穹铁道", "genre": GameGenre.rpg, "publisher": "米哈游", "status": GameStatus.operating,
     "description": "银河冒险RPG"},
    {"name": "永劫无间手游", "genre": GameGenre.battle_royale, "publisher": "网易", "status": GameStatus.operating,
     "description": "冷兵器吃鸡手游"},
    {"name": "绝区零", "genre": GameGenre.rpg, "publisher": "米哈游", "status": GameStatus.operating,
     "description": "都市幻想动作RPG"},
]


def _generate_mock_contents(game_name: str) -> list[dict]:
    templates = {
        "三角洲行动": [
            ("B站", ContentType.post, "三角洲M4A1配件怎么搭配？求大佬推荐战备方案", 12500, 342, 89,
             "玩了半个月了，M4还是配不好，握把到底选垂直还是三角？战备值卡在多少合适？求一套完整配装方案"),
            ("B站", ContentType.video, "【三角洲行动】全武器战备值推荐表", 89200, 3200, 456,
             "整理了全武器战备值表，记得三连"),
            ("TapTap", ContentType.post, "求问三角洲战备怎么算？", 5600, 89, 34,
             "新人刚入坑，战备值系统看得一头雾水，有没有大佬做个计算器"),
            ("小黑盒", ContentType.post, "分享一个自制的三角洲配装Excel表", 3200, 156, 67,
             "花了三天整理了目前所有配件的战备值和属性"),
            ("抖音", ContentType.video, "三角洲最强配装推荐", 156000, 8900, 1200, "三角洲行动热门配装方案"),
        ],
        "火影忍者": [
            ("TapTap", ContentType.post, "火影忍者手游体验服资格怎么获取？", 34000, 567, 234,
             "听说体验服要开放申请了，有没有抢码攻略"),
            ("B站", ContentType.post, "火影体验服资格申请攻略！先到先得", 25000, 890, 340, "体验服资格限量发放"),
        ],
        "洛克王国：世界": [
            ("B站", ContentType.post, "洛克王国世界孵蛋配方表有吗？", 8900, 234, 67,
             "孵蛋机制搞不懂，不同精灵配种出来是什么？求配方表"),
            ("TapTap", ContentType.post, "洛克孵蛋配方合集，持续更新", 15600, 456, 134, "整理了目前已知的孵蛋配方"),
            ("小黑盒", ContentType.post, "求分享洛克孵蛋计算工具", 2100, 45, 12, "有没有孵蛋模拟器或者计算工具？"),
        ],
        "原神": [
            ("B站", ContentType.video, "原神5.6全地图神瞳/宝箱收集路线", 230000, 12000, 2300, "新版地图资源全收集"),
            ("TapTap", ContentType.post, "有没有好用的原神抽卡记录分析工具？", 12000, 234, 89, "想看看自己真实保底概率"),
            ("小黑盒", ContentType.post, "我做了个抽卡统计网页，欢迎大家使用", 2100, 56, 23, "抽卡记录分析H5"),
        ],
    }
    defaults = [("TapTap", ContentType.post, f"{game_name}攻略求推荐", 2000, 30, 10, "新手求攻略")]
    contents = templates.get(game_name, defaults)
    results = []
    now = datetime.now()
    for platform, ctype, title, views, likes, comments, body in contents:
        jitter = timedelta(hours=hash(title) % 24)
        results.append({
            "platform": platform,
            "content_type": ctype,
            "title": title,
            "body": body,
            "view_count": views,
            "like_count": likes,
            "comment_count": comments,
            "share_count": max(1, int(likes * 0.15)),
            "hot_score": min(100.0, (views / 2000) + (likes * 0.01)),
            "published_at": now - jitter,
            "url": f"https://{platform.lower()}.example.com/post/{uuid.uuid4().hex[:8]}",
            "extra_data": json.dumps({"top_comments": [f"我也想知道{i}" for i in range(3)]}, ensure_ascii=False),
        })
    return results


# --- 内容清洗：判断是否与游戏工具有关 ---

TOOL_RELEVANCE_KEYWORDS = [
    # 工具类
    "工具", "配装", "计算器", "模拟器", "地图", "抽卡", "战备", "攻略",
    "配方", "助手", "辅助", "查询", "一键", "生成器", "制作", "合成", "分析",
    "build", "配队", "阵容", "加点", "天赋", "装备", "武器",
    # 福利类
    "体验服", "资格", "兑换码", "激活码", "礼包", "福利", "限量", "抢码",
    "测试资格", "内测", "先到先得",
    # 数据类
    "排行榜", "排名", "数据", "图鉴", "百科", "属性", "技能", "孵蛋",
    # 攻略类
    "推荐", "教学", "教程", "新手", "入门", "毕业", "成型",
]


def _is_tool_related(title: str, body: str) -> bool:
    """判断内容是否与游戏工具/福利/攻略相关。"""
    text = (title + " " + body).lower()
    for kw in TOOL_RELEVANCE_KEYWORDS:
        if kw.lower() in text:
            return True
    return False


def _normalize_title(title: str) -> str:
    """归一化标题用于去重比较：去空格、去特殊符号、小写。"""
    import re
    t = title.strip().lower()
    t = re.sub(r'\s+', '', t)
    t = re.sub(r'[【】\[\]「」『』""''《》（）()、，。！？…—_/|\\-]', '', t)
    return t


class DataAdapter:
    """数据接入适配器：优先调用监控采集微服务，回退到 Mock。
    
    断点续传：每个 (平台, 关键词) 组合独立采集并立即提交到数据库。
    中断后重新执行时，URL/标题去重自动跳过已有数据，不重复入库。
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.use_mock = not settings.monitor_api_base

    async def seed_games(self) -> list[Game]:
        existing = await self.session.execute(select(Game))
        if existing.scalars().first():
            return []
        games = []
        for g in MOCK_GAMES:
            game = Game(
                id=str(uuid.uuid4()), name=g["name"], genre=g["genre"],
                publisher=g["publisher"], status=g["status"], description=g["description"],
            )
            self.session.add(game)
            games.append(game)
        await self.session.commit()
        return games

    async def _check_monitor_health(self) -> bool:
        """检测监控服务是否可达。"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{settings.monitor_api_base}/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def _call_monitor(
        self, platform_key: str, keyword: str, count: int = 50, proxy_url: str | None = None,
    ) -> list[dict]:
        """调用监控服务采集指定平台数据（支持多排序序列去重）。"""
        endpoint = MONITOR_PLATFORM_ENDPOINTS.get(platform_key)
        if not endpoint:
            logger.warning(f"不支持的监控平台: {platform_key}")
            return []

        sort_configs: list[dict] = []
        if platform_key == "xiaoheihe":
            sort_configs = [
                {"keyword": keyword, "count": count, "time_range": "30d", "sort": "award_num"},
                {"keyword": keyword, "count": count, "time_range": "30d", "sort": "default"},
            ]
        elif platform_key == "taptap":
            sort_configs = [
                {"keyword": keyword, "count": count, "sort": "default", "proxy_url": proxy_url},
                {"keyword": keyword, "count": count, "sort": "update_time,desc", "proxy_url": proxy_url},
            ]
        elif platform_key == "douyin":
            sort_configs = [
                {"keyword": keyword, "count": count, "sort": "default", "headless": False},
                {"keyword": keyword, "count": count, "sort": "latest", "headless": False},
                {"keyword": keyword, "count": count, "sort": "most_like", "headless": False},
            ]
        else:
            sort_configs = [{"keyword": keyword, "count": count}]

        all_items: list[dict] = []
        url = f"{settings.monitor_api_base}{endpoint}"

        for payload in sort_configs:
            sort_label = payload.get("sort", "default")
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    items = data.get("items", [])
                    logger.info(f"[Monitor] {platform_key} '{keyword}' sort={sort_label} → {len(items)}条")
                    all_items.extend(items)
            except httpx.HTTPStatusError as e:
                logger.warning(f"[Monitor] {platform_key} sort={sort_label} HTTP {e.response.status_code}: {e.response.text[:200]}")
            except Exception as e:
                logger.warning(f"[Monitor] {platform_key} sort={sort_label} 调用失败: {e}")

        seen: set[str] = set()
        deduped: list[dict] = []
        for item in all_items:
            title = item.get("title", "") or item.get("video_desc", "")
            url_key = item.get("share_url", "") or item.get("video_url", "") or item.get("id_str", "")
            key = f"{title}|{url_key}"
            if key not in seen:
                seen.add(key)
                deduped.append(item)

        logger.info(f"[Monitor] {platform_key} '{keyword}' 去重后 → {len(deduped)}条 (原始{len(all_items)}条)")
        return deduped

    def _map_monitor_item(
        self, game_id: str, game_name: str, platform_key: str, item: dict, keyword: str = "",
    ) -> dict:
        """将监控服务返回的原始 item 映射为标准 content 格式。"""
        now = datetime.now()
        platform_label_map = {
            "xiaoheihe": "小黑盒", "taptap": "TapTap", "douyin": "抖音",
            "bilibili": "B站", "nga": "NGA", "weibo": "微博", "tieba": "贴吧",
        }
        platform_label = platform_label_map.get(platform_key, platform_key)

        if platform_key == "xiaoheihe":
            title = item.get("title", "")
            body = item.get("description", "")
            url = item.get("share_url", "")
            thumbs = item.get("thumbs", 0)
            like_count = int(thumbs) if isinstance(thumbs, (int, float)) else 0
            create_at = item.get("create_at", 0)
            pub_time = datetime.fromtimestamp(create_at) if create_at else now
            view_count = 0
            comment_count = 0
        elif platform_key == "taptap":
            title = item.get("title", "")
            body = item.get("summary", "")
            like_count = len(item.get("thumbs", []))
            create_time = item.get("created_time", 0)
            pub_time = datetime.fromtimestamp(create_time) if create_time else now
            moment_id = item.get("id_str", "")
            url = f"https://www.taptap.cn/moment/{moment_id}" if moment_id else ""
            view_count = 0
            comment_count = 0
        elif platform_key == "douyin":
            title = item.get("video_desc", "")
            body = item.get("video_desc", "")
            url = item.get("video_url", "")
            like_count = item.get("like_count", 0) or 0
            create_time_str = item.get("create_time", "")
            try:
                pub_time = datetime.strptime(create_time_str, "%Y-%m-%d %H:%M:%S") if create_time_str else now
            except (ValueError, TypeError):
                pub_time = now
            view_count = 0
            comment_count = 0
        else:
            title = item.get("title", "")
            body = item.get("body", item.get("description", ""))
            url = item.get("url", item.get("share_url", item.get("video_url", "")))
            pub_time = now
            view_count = 0
            like_count = 0
            comment_count = 0

        hot_score = min(100.0, (like_count * 0.5) + (view_count / 2000))

        return {
            "platform": platform_label,
            "content_type": ContentType.search_term,
            "title": title or f"{game_name} {keyword}",
            "body": body or "",
            "view_count": max(0, view_count),
            "like_count": max(0, like_count),
            "comment_count": max(0, comment_count),
            "share_count": 0,
            "hot_score": hot_score,
            "published_at": pub_time,
            "url": url,
            "extra_data": json.dumps(
                {"search_keyword": keyword, "platform_key": platform_key, "raw": item},
                ensure_ascii=False,
            ),
        }

    # ======================== 断点续传：分批采集 + 进度追踪 ========================

    async def _ensure_progress_records(self, configs: list[PlatformSearchConfig]) -> list[tuple]:
        """确保每个 (平台, 关键词) 组合都有进度记录。返回尚未完成的组合列表。"""
        combos: list[tuple] = []
        for cfg in configs:
            platform_key = cfg.platform
            if platform_key not in MONITOR_PLATFORM_ENDPOINTS:
                continue
            keywords = [kw.strip() for kw in cfg.keywords.split(",") if kw.strip()]
            crawl_count = cfg.crawl_count or 50
            for kw in keywords:
                # 查是否已有进度记录
                stmt = select(CrawlProgress).where(
                    CrawlProgress.platform == platform_key,
                    CrawlProgress.keyword == kw,
                    CrawlProgress.crawl_count == crawl_count,
                )
                result = await self.session.execute(stmt)
                existing = result.scalar()
                # 每次执行均重置进度，重新采集（DB级去重保证不重复入库）
                if existing is not None:
                    existing.status = "pending"
                    existing.items_fetched = 0
                    existing.items_ingested = 0
                    existing.error_msg = None
                    existing.started_at = None
                    existing.completed_at = None
                else:
                    progress = CrawlProgress(
                        id=str(uuid.uuid4()),
                        platform=platform_key,
                        keyword=kw,
                        crawl_count=crawl_count,
                        status="pending",
                    )
                    self.session.add(progress)
                combos.append((platform_key, kw, crawl_count, cfg))

        if combos:
            await self.session.commit()
        return combos

    async def _update_progress(
        self, platform_key: str, keyword: str, crawl_count: int,
        status: str, items_fetched: int = 0, items_ingested: int = 0,
        error_msg: str | None = None,
    ):
        """更新采集进度。"""
        stmt = select(CrawlProgress).where(
            CrawlProgress.platform == platform_key,
            CrawlProgress.keyword == keyword,
            CrawlProgress.crawl_count == crawl_count,
        )
        result = await self.session.execute(stmt)
        progress = result.scalar()
        if progress is None:
            progress = CrawlProgress(
                id=str(uuid.uuid4()),
                platform=platform_key,
                keyword=keyword,
                crawl_count=crawl_count,
            )
            self.session.add(progress)

        progress.status = status
        progress.items_fetched = items_fetched
        progress.items_ingested = items_ingested
        progress.error_msg = error_msg
        if status == "running" and progress.started_at is None:
            progress.started_at = datetime.now()
        if status in ("completed", "failed"):
            progress.completed_at = datetime.now()

        await self.session.commit()

    async def _dedup_and_insert(self, mapped_items: list[dict]) -> int:
        """对已映射的内容进行数据库级去重并入库，返回实际入库数。"""
        if not mapped_items:
            return 0

        # 过滤工具相关
        filtered = [c for c in mapped_items if _is_tool_related(
            c.get("title", ""), c.get("body", "")
        )]
        if not filtered:
            return 0

        # 查数据库中已存在的 URL（含本次会话已入库的）
        urls = set(c.get("url", "") for c in filtered if c.get("url"))
        existing_urls: set[str] = set()
        if urls:
            stmt = select(PlatformContent.url).where(PlatformContent.url.in_(urls))
            result = await self.session.execute(stmt)
            existing_urls = set(result.scalars().all())

        seen_urls: set[str] = set(existing_urls)
        seen_titles: set[str] = set()
        count = 0

        for c in filtered:
            url = c.get("url", "")
            title = c.get("title", "")
            if url and url in seen_urls:
                continue
            norm_title = _normalize_title(title)
            if norm_title and norm_title in seen_titles:
                continue
            if url:
                seen_urls.add(url)
            if norm_title:
                seen_titles.add(norm_title)

            platform_key = c.get("platform", "other").lower()
            platform_map = {e.value.lower(): e for e in ContentPlatform}
            platform_enum = next((e for k, e in platform_map.items() if k in platform_key), ContentPlatform.other)

            content = PlatformContent(
                id=str(uuid.uuid4()),
                game_id=c["game_id"],
                platform=platform_enum,
                content_type=c.get("content_type", ContentType.post),
                url=c.get("url", ""),
                title=c.get("title", ""),
                body=c.get("body", ""),
                author=c.get("author", ""),
                view_count=c.get("view_count", 0),
                like_count=c.get("like_count", 0),
                comment_count=c.get("comment_count", 0),
                share_count=c.get("share_count", 0),
                hot_score=c.get("hot_score", 0.0),
                published_at=c.get("published_at", datetime.now()),
                extra_data=c.get("extra_data", "{}"),
            )
            self.session.add(content)
            count += 1

        await self.session.commit()
        return count

    async def _ingest_single_combo(
        self, platform_key: str, keyword: str, crawl_count: int,
        config: PlatformSearchConfig, games: dict,
    ) -> int:
        """采集单个 (平台, 关键词) 组合并入库，返回入库条数。"""
        proxy_url = getattr(config, "proxy_url", None) or None

        await self._update_progress(platform_key, keyword, crawl_count, "running")

        try:
            # 1. 调用监控采集
            items = await self._call_monitor(platform_key, keyword, crawl_count, proxy_url)
            fetched = len(items)

            if not items:
                await self._update_progress(platform_key, keyword, crawl_count,
                    "completed", items_fetched=0, items_ingested=0)
                return 0

            # 2. 映射到各游戏
            mapped: list[dict] = []
            for game_id, game in games.items():
                for item in items:
                    m = self._map_monitor_item(game_id, game.name, platform_key, item, keyword)
                    m["game_id"] = game_id
                    mapped.append(m)

            # 3. 过滤 + 去重 + 入库
            ingested = await self._dedup_and_insert(mapped)

            await self._update_progress(platform_key, keyword, crawl_count,
                "completed", items_fetched=fetched, items_ingested=ingested)

            logger.info(f"[Ingest] {platform_key} '{keyword}' 入库 {ingested} 条 (原始 {fetched} 条)")
            return ingested

        except Exception as e:
            error_msg = str(e)[:500]
            logger.error(f"[Ingest] {platform_key} '{keyword}' 失败: {error_msg}")
            await self._update_progress(platform_key, keyword, crawl_count,
                "failed", error_msg=error_msg)
            return 0

    async def ingest_contents(self, game_ids: list[str], since: datetime | None = None) -> int:
        """分批从数据源拉取内容并写入 platform_contents 表。
        
        每个 (平台, 关键词) 组合独立采集并立即提交。中断后重跑不会重复入库。
        进度记录到 crawl_progress 表，已完成组合自动跳过。
        """
        if self.use_mock:
            return await self._ingest_mock(game_ids, since)

        healthy = await self._check_monitor_health()
        if not healthy:
            logger.info("监控服务不可达，回退到 Mock 数据")
            return await self._ingest_mock(game_ids, since)

        # 获取游戏信息
        stmt = select(Game).where(Game.id.in_(game_ids))
        result = await self.session.execute(stmt)
        games = {g.id: g for g in result.scalars().all()}

        if not games:
            logger.warning("无有效游戏")
            return 0

        # 获取启用的搜索词配置
        cfg_stmt = select(PlatformSearchConfig).where(
            PlatformSearchConfig.enabled == True,
        )
        cfg_result = await self.session.execute(cfg_stmt)
        configs = list(cfg_result.scalars().all())

        if not configs:
            logger.warning("无启用的搜索词配置，回退到 Mock")
            return await self._ingest_mock(game_ids, since)

        # 确保进度记录存在，并获取未完成的组合
        combos = await self._ensure_progress_records(configs)

        if not combos:
            logger.info("[Ingest] 所有组合已完成，无需采集")
            return 0

        total = 0
        for platform_key, keyword, crawl_count, cfg in combos:
            count = await self._ingest_single_combo(
                platform_key, keyword, crawl_count, cfg, games)
            total += count

        logger.info(f"[Ingest] 本次共入库 {total} 条")
        return total

    async def ingest_single(
        self, platform_key: str, keyword: str, game_ids: list[str],
        crawl_count: int = 50,
    ) -> dict:
        """手动重试单个 (平台, 关键词) 组合的采集。"""
        if self.use_mock:
            return {"ok": False, "error": "Mock 模式下不支持重试"}

        stmt = select(Game).where(Game.id.in_(game_ids))
        result = await self.session.execute(stmt)
        games = {g.id: g for g in result.scalars().all()}

        # 构造一个临时 config
        cfg_stmt = select(PlatformSearchConfig).where(
            PlatformSearchConfig.enabled == True,
            PlatformSearchConfig.platform == platform_key,
        )
        cfg_result = await self.session.execute(cfg_stmt)
        config = cfg_result.scalar()
        if config is None:
            config = PlatformSearchConfig(
                id=str(uuid.uuid4()),
                platform=platform_key,
                keywords=keyword,
                crawl_count=crawl_count,
                enabled=True,
            )

        count = await self._ingest_single_combo(platform_key, keyword, crawl_count, config, games)
        return {"ok": True, "platform": platform_key, "keyword": keyword, "ingested": count}

    async def get_progress(self) -> list[dict]:
        """获取当前采集进度（所有组合的状态）。"""
        stmt = select(CrawlProgress).order_by(CrawlProgress.created_at.desc())
        result = await self.session.execute(stmt)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "platform": r.platform,
                "keyword": r.keyword,
                "crawl_count": r.crawl_count,
                "status": r.status,
                "items_fetched": r.items_fetched,
                "items_ingested": r.items_ingested,
                "error_msg": r.error_msg,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in records
        ]

    # ======================== 兼容旧接口 ========================

    async def fetch_platform_contents(
        self, game_ids: list[str], since: datetime | None = None,
    ) -> list[dict]:
        """兼容旧接口：获取指定游戏在各平台的内容。"""
        if not self.use_mock:
            healthy = await self._check_monitor_health()
            if healthy:
                return await self._fetch_from_monitor(game_ids, since)
            logger.info("监控服务不可达，回退到 Mock 数据")
        return await self._fetch_mock(game_ids, since)

    async def _fetch_from_monitor(
        self, game_ids: list[str], since: datetime | None = None,
    ) -> list[dict]:
        """兼容旧接口：一次性全部采集（不含断点续传）。"""
        stmt = select(Game).where(Game.id.in_(game_ids))
        result = await self.session.execute(stmt)
        games = {g.id: g for g in result.scalars().all()}

        cfg_stmt = select(PlatformSearchConfig).where(
            PlatformSearchConfig.enabled == True,
        )
        cfg_result = await self.session.execute(cfg_stmt)
        configs = list(cfg_result.scalars().all())

        if not configs:
            logger.warning("无启用的搜索词配置，回退到 Mock")
            return await self._fetch_mock(game_ids, since)

        monitor_cache: dict[tuple, list[dict]] = {}
        for cfg in configs:
            platform_key = cfg.platform
            if platform_key not in MONITOR_PLATFORM_ENDPOINTS:
                continue
            keywords = [kw.strip() for kw in cfg.keywords.split(",") if kw.strip()]
            crawl_count = cfg.crawl_count or 50
            proxy_url = getattr(cfg, "proxy_url", None) or None
            for kw in keywords:
                cache_key = (platform_key, kw, crawl_count)
                if cache_key not in monitor_cache:
                    items = await self._call_monitor(platform_key, kw, crawl_count, proxy_url)
                    monitor_cache[cache_key] = items
                    logger.info(f"[Monitor] {platform_key} '{kw}' → {len(items)}条")

        all_contents: list[dict] = []
        for game_id in game_ids:
            game = games.get(game_id)
            if not game:
                continue
            for cfg in configs:
                platform_key = cfg.platform
                if platform_key not in MONITOR_PLATFORM_ENDPOINTS:
                    continue
                keywords = [kw.strip() for kw in cfg.keywords.split(",") if kw.strip()]
                crawl_count = cfg.crawl_count or 50
                for kw in keywords:
                    cache_key = (platform_key, kw, crawl_count)
                    items = monitor_cache.get(cache_key, [])
                    for item in items:
                        mapped = self._map_monitor_item(game_id, game.name, platform_key, item, kw)
                        mapped["game_id"] = game_id
                        all_contents.append(mapped)

        if since:
            all_contents = [c for c in all_contents if c["published_at"] >= since]

        logger.info(f"[Monitor] 总计 {len(all_contents)} 条")
        if not all_contents:
            logger.warning("监控服务未返回任何数据，回退到 Mock")
            return await self._fetch_mock(game_ids, since)

        return all_contents

    async def _fetch_mock(self, game_ids: list[str], since: datetime | None = None) -> list[dict]:
        """Mock 数据回退。"""
        stmt = select(Game).where(Game.id.in_(game_ids))
        result = await self.session.execute(stmt)
        game_map = {g.id: g.name for g in result.scalars().all()}

        cfg_stmt = select(PlatformSearchConfig).where(
            PlatformSearchConfig.enabled == True,
        )
        cfg_result = await self.session.execute(cfg_stmt)
        configs = list(cfg_result.scalars().all())

        all_contents = []
        for gid in game_ids:
            name = game_map.get(gid, "")
            contents = _generate_mock_contents(name)
            for c in contents:
                c["game_id"] = gid
            all_contents.extend(contents)

            for cfg in configs:
                keywords_list = [kw.strip() for kw in cfg.keywords.split(",") if kw.strip()]
                for kw in keywords_list:
                    platform_label_map = {"douyin": "抖音", "taptap": "TapTap", "xiaoheihe": "小黑盒",
                                          "bilibili": "B站", "nga": "NGA", "weibo": "微博", "tieba": "贴吧"}
                    label = platform_label_map.get(cfg.platform, cfg.platform)
                    now = datetime.now()
                    jitter = timedelta(hours=hash(kw + name) % 24)
                    all_contents.append({
                        "game_id": gid,
                        "platform": label,
                        "content_type": ContentType.search_term,
                        "title": f"{name} {kw} 热门讨论",
                        "body": f"通过搜索词「{kw}」在{label}发现的内容",
                        "view_count": 3000 + (hash(kw) % 50000),
                        "like_count": 50 + (hash(kw) % 500),
                        "comment_count": 15 + (hash(kw) % 100),
                        "share_count": 5,
                        "hot_score": min(100.0, 10 + (hash(kw) % 90)),
                        "published_at": now - jitter,
                        "url": f"https://{label.lower()}.example.com/search?q={kw}",
                        "extra_data": json.dumps({"search_keyword": kw, "mock": True}, ensure_ascii=False),
                    })

        if since:
            all_contents = [c for c in all_contents if c["published_at"] >= since]
        return all_contents

    async def _ingest_mock(self, game_ids: list[str], since: datetime | None = None) -> int:
        """Mock 模式下的入库（保持原有逻辑）。"""
        contents = await self._fetch_mock(game_ids, since)

        # 创建进度记录（Mock 模式也需要展示进度）
        cfg_stmt = select(PlatformSearchConfig).where(PlatformSearchConfig.enabled == True)
        cfg_result = await self.session.execute(cfg_stmt)
        mock_configs = list(cfg_result.scalars().all())

        if mock_configs:
            for cfg in mock_configs:
                platform_key = cfg.platform
                if platform_key not in MONITOR_PLATFORM_ENDPOINTS:
                    continue
                keywords = [kw.strip() for kw in cfg.keywords.split(",") if kw.strip()]
                crawl_count = cfg.crawl_count or 50
                for kw in keywords:
                    stmt2 = select(CrawlProgress).where(
                        CrawlProgress.platform == platform_key,
                        CrawlProgress.keyword == kw,
                    )
                    r2 = await self.session.execute(stmt2)
                    existing_p = r2.scalar()
                    if existing_p is not None:
                        existing_p.status = "completed"
                        existing_p.items_fetched = max(existing_p.items_fetched or 0, 1)
                        existing_p.items_ingested = max(existing_p.items_ingested or 0, 1)
                        existing_p.started_at = existing_p.started_at or datetime.now()
                        existing_p.completed_at = datetime.now()
                    else:
                        progress = CrawlProgress(
                            id=str(uuid.uuid4()),
                            platform=platform_key,
                            keyword=kw,
                            crawl_count=crawl_count,
                            status="completed",
                            items_fetched=1,
                            items_ingested=1,
                            started_at=datetime.now(),
                            completed_at=datetime.now(),
                        )
                        self.session.add(progress)
            await self.session.commit()

        return await self._dedup_and_insert(contents)
