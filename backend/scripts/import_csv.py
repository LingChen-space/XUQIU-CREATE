# -*- coding: utf-8 -*-
"""
CSV 数据导入脚本
将爬虫体系导出的 CSV 数据导入到需求发生工具数据库。
CSV 编码: GBK (兼容 GB2312)
列: 来源, 时间, 标题, 摘要, 文章ID, 昵称, URL
"""

import csv
import json
import sys
import uuid
import re
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from sqlalchemy import select
from app.database import async_session, init_db, Base, engine
from app.models.game import Game, GameGenre, GameStatus
from app.models.platform_content import PlatformContent, ContentPlatform, ContentType


# ============================================================
# 手游关键词库 - 用于从标题/正文中识别游戏
# ============================================================
MOBILE_GAME_KEYWORDS = {
    "三角洲行动": {"genre": GameGenre.fps, "publisher": "腾讯", "status": GameStatus.operating},
    "原神": {"genre": GameGenre.open_world, "publisher": "米哈游", "status": GameStatus.operating},
    "鸣潮": {"genre": GameGenre.open_world, "publisher": "库洛游戏", "status": GameStatus.operating},
    "火影忍者": {"genre": GameGenre.rpg, "publisher": "腾讯", "status": GameStatus.operating},
    "洛克王国：世界": {"genre": GameGenre.rpg, "publisher": "腾讯", "status": GameStatus.testing},
    "洛克王国": {"genre": GameGenre.rpg, "publisher": "腾讯", "status": GameStatus.operating},
    "崩坏：星穹铁道": {"genre": GameGenre.rpg, "publisher": "米哈游", "status": GameStatus.operating},
    "星穹铁道": {"genre": GameGenre.rpg, "publisher": "米哈游", "status": GameStatus.operating},
    "永劫无间手游": {"genre": GameGenre.battle_royale, "publisher": "网易", "status": GameStatus.operating},
    "永劫无间": {"genre": GameGenre.battle_royale, "publisher": "网易", "status": GameStatus.operating},
    "绝区零": {"genre": GameGenre.rpg, "publisher": "米哈游", "status": GameStatus.operating},
    "明日方舟：终末地": {"genre": GameGenre.rpg, "publisher": "鹰角网络", "status": GameStatus.testing},
    "明日方舟": {"genre": GameGenre.strategy, "publisher": "鹰角网络", "status": GameStatus.operating},
    "无限暖暖": {"genre": GameGenre.open_world, "publisher": "叠纸", "status": GameStatus.operating},
    "王者荣耀": {"genre": GameGenre.moba, "publisher": "腾讯", "status": GameStatus.operating},
    "和平精英": {"genre": GameGenre.fps, "publisher": "腾讯", "status": GameStatus.operating},
    "英雄联盟手游": {"genre": GameGenre.moba, "publisher": "腾讯", "status": GameStatus.operating},
    "蛋仔派对": {"genre": GameGenre.casual, "publisher": "网易", "status": GameStatus.operating},
    "以闪亮之名": {"genre": GameGenre.simulation, "publisher": "祖龙娱乐", "status": GameStatus.operating},
    "恋与深空": {"genre": GameGenre.simulation, "publisher": "叠纸", "status": GameStatus.operating},
    "光与夜之恋": {"genre": GameGenre.simulation, "publisher": "腾讯", "status": GameStatus.operating},
    "金铲铲之战": {"genre": GameGenre.strategy, "publisher": "腾讯", "status": GameStatus.operating},
    "暗区突围": {"genre": GameGenre.fps, "publisher": "腾讯", "status": GameStatus.operating},
    "第五人格": {"genre": GameGenre.rpg, "publisher": "网易", "status": GameStatus.operating},
    "逆水寒": {"genre": GameGenre.mmorpg, "publisher": "网易", "status": GameStatus.operating},
    "重返未来：1999": {"genre": GameGenre.rpg, "publisher": "深蓝互动", "status": GameStatus.operating},
    "重返未来1999": {"genre": GameGenre.rpg, "publisher": "深蓝互动", "status": GameStatus.operating},
    "白荆回廊": {"genre": GameGenre.rpg, "publisher": "上海烛龙", "status": GameStatus.operating},
    "白夜极光": {"genre": GameGenre.rpg, "publisher": "腾讯", "status": GameStatus.inactive},
    "幻塔": {"genre": GameGenre.open_world, "publisher": "完美世界", "status": GameStatus.operating},
    "创造吧！我们的星球": {"genre": GameGenre.simulation, "publisher": "腾讯", "status": GameStatus.operating},
    "卡拉彼丘": {"genre": GameGenre.fps, "publisher": "创梦天地", "status": GameStatus.operating},
    "尘白禁区": {"genre": GameGenre.fps, "publisher": "西山居", "status": GameStatus.operating},
    "蔚蓝档案": {"genre": GameGenre.rpg, "publisher": "Nexon", "status": GameStatus.operating},
    "碧蓝航线": {"genre": GameGenre.rpg, "publisher": "蛮啾网络", "status": GameStatus.operating},
    "少女前线2：追放": {"genre": GameGenre.rpg, "publisher": "散爆网络", "status": GameStatus.operating},
    "少女前线2": {"genre": GameGenre.rpg, "publisher": "散爆网络", "status": GameStatus.operating},
    "阴阳师": {"genre": GameGenre.rpg, "publisher": "网易", "status": GameStatus.operating},
    "梦幻西游": {"genre": GameGenre.rpg, "publisher": "网易", "status": GameStatus.operating},
    "三国志·战略版": {"genre": GameGenre.strategy, "publisher": "灵犀互娱", "status": GameStatus.operating},
    "三国志战略版": {"genre": GameGenre.strategy, "publisher": "灵犀互娱", "status": GameStatus.operating},
    "崩坏3": {"genre": GameGenre.rpg, "publisher": "米哈游", "status": GameStatus.operating},
    "崩坏：星穹铁道": {"genre": GameGenre.rpg, "publisher": "米哈游", "status": GameStatus.operating},
    "崩坏星穹铁道": {"genre": GameGenre.rpg, "publisher": "米哈游", "status": GameStatus.operating},
    "无期迷途": {"genre": GameGenre.rpg, "publisher": "自意网络", "status": GameStatus.operating},
    "深空之眼": {"genre": GameGenre.rpg, "publisher": "勇士网络", "status": GameStatus.operating},
    "天地劫：幽城再临": {"genre": GameGenre.rpg, "publisher": "紫龙游戏", "status": GameStatus.operating},
    "天地劫": {"genre": GameGenre.rpg, "publisher": "紫龙游戏", "status": GameStatus.operating},
    "钢岚": {"genre": GameGenre.strategy, "publisher": "紫龙游戏", "status": GameStatus.operating},
    "铃兰之剑": {"genre": GameGenre.strategy, "publisher": "心动网络", "status": GameStatus.operating},
    "出发吧麦芬": {"genre": GameGenre.rpg, "publisher": "心动网络", "status": GameStatus.operating},
    "寻道大千": {"genre": GameGenre.rpg, "publisher": "三七互娱", "status": GameStatus.operating},
    "无尽冬日": {"genre": GameGenre.strategy, "publisher": "点点互动", "status": GameStatus.operating},
    "向僵尸开炮": {"genre": GameGenre.casual, "publisher": "", "status": GameStatus.operating},
    "小妖问道": {"genre": GameGenre.rpg, "publisher": "", "status": GameStatus.operating},
    "流浪方舟": {"genre": GameGenre.rpg, "publisher": "", "status": GameStatus.operating},
    "命运-冠位指定": {"genre": GameGenre.rpg, "publisher": "Bilibili", "status": GameStatus.operating},
    "FGO": {"genre": GameGenre.rpg, "publisher": "Bilibili", "status": GameStatus.operating},
    "明日之后": {"genre": GameGenre.open_world, "publisher": "网易", "status": GameStatus.operating},
    "荒野乱斗": {"genre": GameGenre.casual, "publisher": "Supercell", "status": GameStatus.operating},
    "部落冲突": {"genre": GameGenre.strategy, "publisher": "Supercell", "status": GameStatus.operating},
    "荒野行动": {"genre": GameGenre.fps, "publisher": "网易", "status": GameStatus.operating},
    "QQ飞车手游": {"genre": GameGenre.casual, "publisher": "腾讯", "status": GameStatus.operating},
    "QQ飞车": {"genre": GameGenre.casual, "publisher": "腾讯", "status": GameStatus.operating},
    "穿越火线：枪战王者": {"genre": GameGenre.fps, "publisher": "腾讯", "status": GameStatus.operating},
    "穿越火线手游": {"genre": GameGenre.fps, "publisher": "腾讯", "status": GameStatus.operating},
    "崩坏：因缘精灵": {"genre": GameGenre.rpg, "publisher": "米哈游", "status": GameStatus.testing},
    "红色沙漠": {"genre": GameGenre.mmorpg, "publisher": "Pearl Abyss", "status": GameStatus.operating},
    "幻兽帕鲁": {"genre": GameGenre.open_world, "publisher": "Pocketpair", "status": GameStatus.operating},
    "帕鲁": {"genre": GameGenre.open_world, "publisher": "Pocketpair", "status": GameStatus.operating},
    # 妮姬/胜利女神
    "妮姬": {"genre": GameGenre.rpg, "publisher": "Shift Up", "status": GameStatus.operating},
    "NIKKE": {"genre": GameGenre.rpg, "publisher": "Shift Up", "status": GameStatus.operating},
    "胜利女神": {"genre": GameGenre.rpg, "publisher": "Shift Up", "status": GameStatus.operating},
}

# 按关键词长度降序排列，长关键词优先匹配
SORTED_KEYWORDS = sorted(MOBILE_GAME_KEYWORDS.keys(), key=len, reverse=True)


def detect_games(text: str) -> list[str]:
    """从文本中识别提及的游戏名称。返回匹配到的标准游戏名列表。"""
    found = []
    for kw in SORTED_KEYWORDS:
        if kw in text:
            found.append(kw)
    # 去重：移除被更长名称包含的短名称
    deduped = []
    for name in found:
        is_sub = False
        for other in found:
            if name != other and name in other:
                is_sub = True
                break
        if not is_sub:
            deduped.append(name)
    return deduped


def parse_platform(source: str) -> ContentPlatform:
    """将 CSV 中的来源字段映射为平台枚举。"""
    source_lower = source.strip().lower()
    mapping = {
        "抖音": ContentPlatform.douyin,
        "douyin": ContentPlatform.douyin,
        "b站": ContentPlatform.bilibili,
        "bilibili": ContentPlatform.bilibili,
        "tap": ContentPlatform.taptap,
        "taptap": ContentPlatform.taptap,
        "小黑盒": ContentPlatform.xiaoheihe,
        "xiaoheihe": ContentPlatform.xiaoheihe,
        "游戏盒": ContentPlatform.other,  # 好游快爆游戏盒
        "好游快爆": ContentPlatform.other,
    }
    for k, v in mapping.items():
        if k in source_lower:
            return v
    return ContentPlatform.other


def compute_hot_score(view_count: int = 0, like_count: int = 0, comment_count: int = 0, share_count: int = 0) -> float:
    """根据互动数据估算热度分 (0-100)。"""
    raw = (view_count * 0.001) + (like_count * 0.1) + (comment_count * 0.5) + (share_count * 1.0)
    if raw <= 0:
        return 10.0  # 基础分
    import math
    score = min(100.0, math.log10(raw + 1) * 25)
    return round(score, 1)


async def import_csv(csv_path: str, dry_run: bool = False):
    """主导入流程。"""
    print(f"[Import] 开始解析 CSV: {csv_path}")

    # 读取 CSV (GBK 编码)
    rows = []
    with open(csv_path, "r", encoding="gbk", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"[Import] 共读取 {len(rows)} 条记录")

    async with async_session() as session:
        # 获取现有游戏列表
        stmt = select(Game)
        result = await session.execute(stmt)
        existing_games = {g.name: g for g in result.scalars().all()}
        print(f"[Import] 现有 {len(existing_games)} 款游戏")

        new_games_added = {}
        content_count = 0
        matched_count = 0
        unmatched_count = 0

        for i, row in enumerate(rows):
            source = row.get("来源", "").strip()
            title = row.get("标题", "").strip()
            body = row.get("摘要", "").strip()
            author = row.get("昵称", "").strip()
            url = row.get("URL", "").strip()
            article_id = row.get("文章ID", "").strip()
            time_str = row.get("时间", "").strip()

            if not title and not body:
                continue

            # 解析时间
            published_at = datetime.now()
            if time_str:
                try:
                    # 格式: 2026-6-8 12:15
                    published_at = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    try:
                        published_at = datetime.strptime(time_str, "%Y/%m/%d %H:%M")
                    except ValueError:
                        pass

            # 识别游戏
            combined_text = title + " " + body
            detected_names = detect_games(combined_text)

            # 确定游戏 ID
            game_ids = []
            for name in detected_names:
                if name in existing_games:
                    game_ids.append(existing_games[name].id)
                elif name in new_games_added:
                    game_ids.append(new_games_added[name].id)
                else:
                    # 创建新游戏
                    info = MOBILE_GAME_KEYWORDS[name]
                    game = Game(
                        id=str(uuid.uuid4()),
                        name=name,
                        genre=info["genre"],
                        publisher=info["publisher"],
                        status=info["status"],
                        description=f"从爬虫数据自动发现 - {name}",
                    )
                    session.add(game)
                    new_games_added[name] = game
                    game_ids.append(game.id)

            if game_ids:
                matched_count += 1
            else:
                unmatched_count += 1

            # 解析平台
            platform = parse_platform(source)

            # 计算热度分
            hot_score = compute_hot_score()

            # 为每个关联的游戏创建一条内容记录
            extra_data = json.dumps({
                "article_id": article_id,
                "source_raw": source,
                "matched_games": detected_names,
            }, ensure_ascii=False)

            for gid in (game_ids if game_ids else ["__unmatched__"]):
                if gid == "__unmatched__":
                    # 未匹配到游戏的跳过创建 platform_content
                    # 但可以在后续手动关联
                    continue

                content = PlatformContent(
                    id=str(uuid.uuid4()),
                    game_id=gid,
                    platform=platform,
                    content_type=ContentType.post,
                    url=url if url else f"no_url_{article_id}",
                    title=title[:500] if title else "",
                    body=body[:2000] if body else "",
                    author=author if author else "",
                    view_count=0,
                    like_count=0,
                    comment_count=0,
                    share_count=0,
                    hot_score=hot_score,
                    published_at=published_at,
                    extra_data=extra_data,
                )
                session.add(content)
                content_count += 1

            if (i + 1) % 50 == 0:
                print(f"[Import] 进度: {i+1}/{len(rows)}, 已创建 {content_count} 条内容, "
                      f"新增 {len(new_games_added)} 款游戏")

        # 提交
        if not dry_run:
            await session.commit()
            print(f"\n[Import] === 导入完成 ===")
            print(f"  CSV 总记录: {len(rows)}")
            print(f"  匹配到游戏: {matched_count}")
            print(f"  未匹配记录: {unmatched_count}")
            print(f"  创建内容: {content_count} 条")
            print(f"  新增游戏: {len(new_games_added)} 款")
            for name in new_games_added:
                print(f"    + {name}")
        else:
            await session.rollback()
            print(f"\n[Import] === 预览模式 (dry_run) ===")
            print(f"  将创建 {content_count} 条内容")
            print(f"  将新增 {len(new_games_added)} 款游戏")
            for name in new_games_added:
                print(f"    + {name}")

    return content_count, len(new_games_added)


async def main():
    csv_path = Path("D:/Users/PC5080/Desktop/监控数据（抖音、游戏盒、tap、小黑盒）.csv")
    if not csv_path.exists():
        print(f"[Error] CSV 文件不存在: {csv_path}")
        return

    # 确保数据库表已创建
    await init_db()

    # 执行导入（可先用 dry_run=True 预览）
    await import_csv(str(csv_path), dry_run=False)


if __name__ == "__main__":
    asyncio.run(main())
