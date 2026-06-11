# -*- coding: utf-8 -*-
"""数据接入层 - 对接现有爬虫体系 API，同时提供 Mock 数据用于开发验证。"""

import json
import uuid
from datetime import datetime, timedelta, date
from typing import AsyncIterator

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Game, GameStatus, GameGenre
from app.models.platform_content import PlatformContent, ContentPlatform, ContentType
from app.models.platform_search_config import PlatformSearchConfig


# --- Mock 数据：开发阶段演示用 ---
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
    """根据游戏名生成合理的模拟内容数据。"""
    templates = {
        "三角洲行动": [
            ("B站", ContentType.post, "三角洲M4A1配件怎么搭配？求大佬推荐战备方案", 12500, 342, 89,
             "玩了半个月了，M4还是配不好，握把到底选垂直还是三角？战备值卡在多少合适？求一套完整配装方案"),
            ("B站", ContentType.video, "【三角洲行动】全武器战备值推荐表！这期视频整理了所有武器的最佳战备值上限", 89200, 3200, 456,
             "整理了全武器战备值表，记得三连"),
            ("TapTap", ContentType.post, "求问三角洲战备怎么算？", 5600, 89, 34,
             "新人刚入坑，战备值系统看得一头雾水，有没有大佬做个计算器"),
            ("小黑盒", ContentType.post, "分享一个自制的三角洲配装Excel表", 3200, 156, 67,
             "花了三天整理了目前所有配件的战备值和属性，需要的自取 https://docs.qq.com/sheet/xxx"),
            ("抖音", ContentType.video, "三角洲最强配装推荐，这套战备性价比最高", 156000, 8900, 1200,
             "三角洲行动热门配装方案，记得收藏"),
        ],
        "火影忍者": [
            ("TapTap", ContentType.post, "火影忍者手游体验服资格怎么获取？", 34000, 567, 234,
             "听说体验服要开放申请了，有没有抢码攻略"),
            ("B站", ContentType.post, "火影体验服资格申请攻略！先到先得", 25000, 890, 340,
             "体验服资格限量发放，分享抢码技巧"),
        ],
        "洛克王国：世界": [
            ("B站", ContentType.post, "洛克王国世界孵蛋配方表有吗？", 8900, 234, 67,
             "孵蛋机制搞不懂，不同精灵配种出来是什么？求配方表"),
            ("TapTap", ContentType.post, "洛克孵蛋配方合集，持续更新", 15600, 456, 134,
             "整理了目前已知的孵蛋配方"),
            ("小黑盒", ContentType.post, "求分享洛克孵蛋计算工具", 2100, 45, 12,
             "有没有孵蛋模拟器或者计算工具？"),
        ],
        "原神": [
            ("B站", ContentType.video, "原神5.6全地图神瞳/宝箱收集路线", 230000, 12000, 2300,
             "新版地图资源全收集，跟跑视频"),
            ("TapTap", ContentType.post, "有没有好用的原神抽卡记录分析工具？", 12000, 234, 89,
             "想看看自己真实保底概率，官方的只能看半年"),
            ("小黑盒", ContentType.post, "我做了个抽卡统计网页，欢迎大家使用", 2100, 56, 23,
             "自己做了一个抽卡记录分析H5 https://github.com/xxx"),
        ],
    }

    defaults = [
        ("TapTap", ContentType.post, f"{game_name}攻略求推荐", 2000, 30, 10, "新手求攻略"),
    ]

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


# --- 数据适配器 ---

def _generate_search_term_contents(game_name: str, platform_key: str, keywords: list[str]) -> list[dict]:
    """根据搜索词配置生成搜索词类型的模拟内容。"""
    platform_label_map = {
        "douyin": "抖音", "taptap": "TapTap", "xiaoheihe": "小黑盒",
        "bilibili": "B站", "nga": "NGA", "weibo": "微博", "tieba": "贴吧",
    }
    platform_label = platform_label_map.get(platform_key, platform_key)

    results = []
    now = datetime.now()
    for i, kw in enumerate(keywords):
        jitter = timedelta(hours=(hash(kw + game_name) % 24))
        # 生成搜索词类型的帖子/视频
        search_titles = [
            f"{game_name} {kw} 攻略分享",
            f"关于{game_name}的{kw}，有人研究过吗",
            f"{game_name}{kw}最新整理，建议收藏",
            f"求{game_name} {kw}，大佬们帮帮忙",
        ]
        title = search_titles[i % len(search_titles)]
        views = 3000 + (hash(kw) % 50000)
        likes = 50 + (hash(kw) % 500)
        comments = 15 + (hash(kw) % 100)

        results.append({
            "platform": platform_label,
            "content_type": ContentType.search_term,
            "title": title,
            "body": f"在{platform_label}搜索「{game_name} {kw}」发现的热门内容，玩家讨论集中在{kw}相关话题",
            "view_count": views,
            "like_count": likes,
            "comment_count": comments,
            "share_count": max(1, int(likes * 0.15)),
            "hot_score": min(100.0, (views / 2000) + (likes * 0.01)),
            "published_at": now - jitter,
            "url": f"https://{platform_label.lower()}.example.com/search?q={kw}",
            "extra_data": json.dumps({"search_keyword": kw, "platform": platform_key}, ensure_ascii=False),
        })
    return results

class DataAdapter:
    """
    数据接入适配器。
    生产环境：通过 HTTP 调用现有爬虫体系 API 获取数据。
    开发环境：使用 Mock 数据。
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.use_mock = not settings.crawler_api_key

    async def seed_games(self) -> list[Game]:
        """初始化种子游戏数据（仅开发 Mock 模式）。"""
        existing = await self.session.execute(select(Game))
        if existing.scalars().first():
            return []

        games = []
        for g in MOCK_GAMES:
            game = Game(
                id=str(uuid.uuid4()),
                name=g["name"],
                genre=g["genre"],
                publisher=g["publisher"],
                status=g["status"],
                description=g["description"],
            )
            self.session.add(game)
            games.append(game)

        await self.session.commit()
        return games

    async def fetch_platform_contents(
        self, game_ids: list[str], since: datetime | None = None
    ) -> list[dict]:
        """从爬虫 API 获取指定游戏的平台内容。"""
        if self.use_mock:
            return await self._fetch_mock(game_ids, since)

        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {"game_ids": ",".join(game_ids)}
            if since:
                params["since"] = since.isoformat()
            resp = await client.get(
                f"{settings.crawler_api_base}/contents",
                params=params,
                headers={"Authorization": f"Bearer {settings.crawler_api_key}"},
            )
            resp.raise_for_status()
            return resp.json()["data"]

    async def _fetch_mock(self, game_ids: list[str], since: datetime | None = None) -> list[dict]:
        """生成 Mock 数据。"""
        stmt = select(Game).where(Game.id.in_(game_ids))
        result = await self.session.execute(stmt)
        games = {g.id: g.name for g in result.scalars().all()}

        # 读取搜索词配置，为每个游戏/平台/关键词生成搜索词内容
        cfg_stmt = select(PlatformSearchConfig).where(
            PlatformSearchConfig.game_id.in_(game_ids),
            PlatformSearchConfig.enabled == True,
        )
        cfg_result = await self.session.execute(cfg_stmt)
        configs = list(cfg_result.scalars().all())

        all_contents = []
        for gid in game_ids:
            name = games.get(gid, "")
            contents = _generate_mock_contents(name)
            for c in contents:
                c["game_id"] = gid
            all_contents.extend(contents)

            # 为每个搜索词配置生成搜索词内容
            game_configs = [cfg for cfg in configs if cfg.game_id == gid]
            for cfg in game_configs:
                keywords_list = [kw.strip() for kw in cfg.keywords.split(",") if kw.strip()]
                if keywords_list:
                    search_contents = _generate_search_term_contents(name, cfg.platform, keywords_list)
                    for sc in search_contents:
                        sc["game_id"] = gid
                    all_contents.extend(search_contents)

        if since:
            since_dt = since if isinstance(since, datetime) else datetime.fromisoformat(str(since))
            all_contents = [c for c in all_contents if c["published_at"] >= since_dt]

        return all_contents

    async def ingest_contents(self, game_ids: list[str], since: datetime | None = None) -> int:
        """
        从数据源拉取内容并写入 platform_contents 表。
        返回写入的记录数。
        """
        contents = await self.fetch_platform_contents(game_ids, since)
        count = 0
        for c in contents:
            platform_key = c.get("platform", "other").lower()
            platform_map = {e.value.lower(): e for e in ContentPlatform}
            platform_enum = next((e for k, e in platform_map.items() if k in platform_key), ContentPlatform.other)

            content = PlatformContent(
                id=str(uuid.uuid4()),
                game_id=c["game_id"],
                platform=platform_enum,
                content_type=ContentType.post,
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
