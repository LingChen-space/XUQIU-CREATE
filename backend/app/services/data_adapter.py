# -*- coding: utf-8 -*-
"""数据接入层 —— 对接监控采集微服务 API，同时保留 Mock 回退。"""

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
    t = re.sub(r'[【】\[\]「」『』""''《》（）()、，。！？…—\\-_/|\\]', '', t)
    return t
class DataAdapter:
    """数据接入适配器：优先调用监控采集微服务，回退到 Mock。"""

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

        # 多排序序列：每个平台采集多个排序维度的数据，去重合并
        # TapTap: 默认列表 + 最新(update_time,desc)
        # 黑盒: 最多点赞(award_num) + 本月默认(default,30d)
        # 抖音: 默认 + 最新 + 最多点赞
        sort_configs: list[dict] = []
        if platform_key == "xiaoheihe":
            sort_configs = [
                {"keyword": keyword, "count": count, "time_range": "30d", "sort": "award_num"},   # 最多点赞
                {"keyword": keyword, "count": count, "time_range": "30d", "sort": "default"},     # 本月默认
            ]
        elif platform_key == "taptap":
            sort_configs = [
                {"keyword": keyword, "count": count, "sort": "default", "proxy_url": proxy_url},          # 默认列表
                {"keyword": keyword, "count": count, "sort": "update_time,desc", "proxy_url": proxy_url},  # 最新
            ]
        elif platform_key == "douyin":
            sort_configs = [
                {"keyword": keyword, "count": count, "sort": "default", "headless": True},   # 默认
                {"keyword": keyword, "count": count, "sort": "latest", "headless": True},   # 最新
                {"keyword": keyword, "count": count, "sort": "most_like", "headless": True},  # 最多点赞
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

        # 去重：按标题+链接去重
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

        # 各平台数据格式归一化
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

    async def fetch_platform_contents(
        self, game_ids: list[str], since: datetime | None = None,
    ) -> list[dict]:
        """获取指定游戏在各平台的内容（优先监控服务，回退 Mock）。"""
        # 尝试监控服务
        if not self.use_mock:
            healthy = await self._check_monitor_health()
            if healthy:
                return await self._fetch_from_monitor(game_ids, since)
            logger.info("监控服务不可达，回退到 Mock 数据")

        # Mock 回退
        return await self._fetch_mock(game_ids, since)

    async def _fetch_from_monitor(
        self, game_ids: list[str], since: datetime | None = None,
    ) -> list[dict]:
        """从监控服务采集真实数据。
        
        优化：先按 (platform, keyword, crawl_count) 去重调用监控，缓存结果；
        再将结果分发到各游戏，避免每个游戏重复调用同一搜索词。
        """
        # 获取游戏信息
        stmt = select(Game).where(Game.id.in_(game_ids))
        result = await self.session.execute(stmt)
        games = {g.id: g for g in result.scalars().all()}

        # 获取启用的全局搜索词配置
        cfg_stmt = select(PlatformSearchConfig).where(
            PlatformSearchConfig.enabled == True,
        )
        cfg_result = await self.session.execute(cfg_stmt)
        configs = list(cfg_result.scalars().all())

        if not configs:
            logger.warning("无启用的搜索词配置，回退到 Mock")
            return await self._fetch_mock(game_ids, since)

        # 第一步：按 (platform, keyword, crawl_count) 去重，先调用监控采集
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

        # 第二步：将采集结果分发到所有游戏
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

        logger.info(f"[Monitor] 总计 {len(all_contents)} 条 (来自 {len(monitor_cache)} 组平台搜索)")
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

            # 为每对 game+config 生成 mock 搜索词内容
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

    async def ingest_contents(self, game_ids: list[str], since: datetime | None = None) -> int:
        """从数据源拉取内容并写入 platform_contents 表。
        
        清洗规则：
        1. 过滤：仅保留与游戏工具/福利/攻略相关的内容
        2. 去重：URL 去重 + 标题相似去重
        """
        contents = await self.fetch_platform_contents(game_ids, since)
        logger.info(f"[Ingest] 原始采集 {len(contents)} 条")
        
        # 清洗步骤 1：关键词过滤，只保留工具相关
        filtered = [c for c in contents if _is_tool_related(
            c.get("title", ""), c.get("body", "")
        )]
        logger.info(f"[Ingest] 工具相关过滤后 {len(filtered)} 条 (过滤掉 {len(contents) - len(filtered)} 条)")
        
        if not filtered:
            return 0
        
        # 清洗步骤 2：查询数据库中已存在的 URL
        urls = set(c.get("url", "") for c in filtered if c.get("url"))
        existing_urls: set[str] = set()
        if urls:
            stmt = select(PlatformContent.url).where(PlatformContent.url.in_(urls))
            result = await self.session.execute(stmt)
            existing_urls = set(result.scalars().all())
        
        # 清洗步骤 3：去重 — URL 去重 + 标题归一化去重
        seen_urls: set[str] = set(existing_urls)
        seen_titles: set[str] = set()
        count = 0
        dup_url = 0
        dup_title = 0
        
        for c in filtered:
            url = c.get("url", "")
            title = c.get("title", "")
            
            # URL 去重
            if url and url in seen_urls:
                dup_url += 1
                continue
            
            # 标题归一化去重（跨 URL 的相同内容）
            norm_title = _normalize_title(title)
            if norm_title and norm_title in seen_titles:
                dup_title += 1
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
        logger.info(f"[Ingest] 入库 {count} 条 (URL去重 {dup_url}, 标题去重 {dup_title})")
        return count
