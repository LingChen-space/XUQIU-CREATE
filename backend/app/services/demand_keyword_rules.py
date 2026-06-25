"""统一需求词库：游戏隔离、固定别名与确定性匹配。"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "demand_keywords.json"

GAME_ALIASES: dict[str, tuple[str, ...]] = {
    "三角洲行动": ("三角洲行动", "三角洲行动体验服", "三角洲"),
    "失控进化": ("失控进化",),
    "异环": ("异环",),
    "洛克王国世界": ("洛克王国世界", "洛克王国：世界", "洛克世界"),
    "原神": ("原神",),
    "鸣潮": ("鸣潮",),
    "崩坏：星穹铁道": ("崩坏：星穹铁道", "崩坏星穹铁道", "星穹铁道", "崩铁"),
}

SPECIAL_ALIASES: dict[str, tuple[str, ...]] = {
    "3X3任务": ("3X3任务", "3X3", "3×3任务", "三乘三任务"),
    "卡战备": ("卡战备", "压战备", "战备限制"),
    "每日密码": ("每日密码", "今日密码", "密码门密码"),
    "圣遗物评分器": ("圣遗物评分器", "圣遗物评分", "圣遗物打分"),
    "声骸评分器": ("声骸评分器", "声骸评分", "声骸打分"),
    "平民配队": ("平民配队", "平民怎么配队", "零氪配队"),
}

FIXED_REPLACEMENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("查询", ("查看", "在哪看")),
    ("计算器", ("计算", "测算", "估算")),
    ("模拟器", ("模拟", "预演")),
    ("推荐", ("怎么选", "哪个好")),
    ("搭配", ("配队", "组合", "配置")),
    ("排行", ("排名", "榜单", "强度榜")),
    ("榜单", ("排行", "排名", "强度榜")),
    ("点位", ("位置", "地点", "在哪")),
    ("位置", ("点位", "地点", "在哪")),
    ("路线", ("路径", "跑图路线", "规划")),
    ("材料", ("素材", "养成资源")),
    ("攻略", ("教程", "打法", "怎么过")),
    ("评分器", ("评分", "打分")),
    ("测算", ("计算", "估算")),
)


@dataclass(frozen=True)
class DemandKeywordRule:
    game_name: str | None
    category: str
    priority: str
    canonical_term: str
    aliases: tuple[str, ...]
    suggested_tool_type: str

    @property
    def is_generic(self) -> bool:
        return self.game_name is None


@dataclass(frozen=True)
class DemandKeywordMatch:
    rule: DemandKeywordRule
    matched_alias: str

    @property
    def canonical_term(self) -> str:
        return self.rule.canonical_term

    @property
    def priority(self) -> str:
        return self.rule.priority

    @property
    def category(self) -> str:
        return self.rule.category


def normalize_keyword(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").lower().replace("×", "x")
    return re.sub(r"[\s\W_]+", "", normalized, flags=re.UNICODE)


def _tool_type_for(term: str, category: str) -> str:
    mappings = (
        (("地图", "点位", "位置", "采集点", "刷新点", "路线"), "交互地图"),
        (("抽卡", "祈愿", "跃迁", "卡池", "保底"), "抽卡/概率分析"),
        (("配队", "阵容", "搭配", "战备", "配装"), "配装/战备工具"),
        (("图鉴", "查询", "资料", "掉落"), "数据库"),
        (("进度", "任务清单", "收集"), "剧情/收集进度"),
        (("计算", "测算", "评分", "模拟", "统计", "规划"), "机制计算器"),
    )
    for keywords, tool_type in mappings:
        if any(keyword in term for keyword in keywords):
            return tool_type
    return "攻略辅助" if "攻略" in category else "其他"


def _aliases_for(term: str) -> tuple[str, ...]:
    aliases = {term, *SPECIAL_ALIASES.get(term, ())}
    for source, replacements in FIXED_REPLACEMENTS:
        if source not in term:
            continue
        for replacement in replacements:
            aliases.add(term.replace(source, replacement))
    return tuple(sorted(aliases, key=lambda item: (-len(normalize_keyword(item)), item)))


@lru_cache(maxsize=1)
def load_keyword_catalog() -> dict:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    games = {
        game_name: tuple(
            DemandKeywordRule(
                game_name=game_name,
                category=item["category"],
                priority=item["priority"],
                canonical_term=item["term"],
                aliases=_aliases_for(item["term"]),
                suggested_tool_type=_tool_type_for(item["term"], item["category"]),
            )
            for item in items
        )
        for game_name, items in payload["games"].items()
    }
    generic = tuple(
        DemandKeywordRule(
            game_name=None,
            category=item["category"],
            priority=item["priority"],
            canonical_term=item["term"],
            aliases=_aliases_for(item["term"]),
            suggested_tool_type=_tool_type_for(item["term"], item["category"]),
        )
        for item in payload["generic"]
    )
    return {
        "version": payload["version"],
        "source": payload["source"],
        "games": games,
        "generic": generic,
    }


def canonical_game_name(game_name: str) -> str | None:
    candidate = normalize_keyword(game_name)
    if not candidate:
        return None
    for canonical, aliases in GAME_ALIASES.items():
        normalized_aliases = tuple(normalize_keyword(alias) for alias in aliases)
        if candidate in normalized_aliases:
            return canonical
        if any(
            alias
            and len(alias) >= 3
            and (alias in candidate or candidate in alias)
            for alias in normalized_aliases
        ):
            return canonical
    return None


def rules_for_game(game_name: str) -> tuple[DemandKeywordRule, ...]:
    catalog = load_keyword_catalog()
    canonical = canonical_game_name(game_name)
    selected = (*catalog["games"].get(canonical, ()), *catalog["generic"])
    by_term: dict[str, DemandKeywordRule] = {}
    for rule in selected:
        by_term.setdefault(rule.canonical_term, rule)
    return tuple(by_term.values())


def match_demand_keywords(game_name: str, text: str) -> list[DemandKeywordMatch]:
    normalized_text = normalize_keyword(text)
    if not normalized_text:
        return []

    candidates: list[tuple[int, int, int, str, DemandKeywordRule]] = []
    for rule in rules_for_game(game_name):
        for alias in rule.aliases:
            normalized_alias = normalize_keyword(alias)
            if len(normalized_alias) < 2:
                continue
            start = normalized_text.find(normalized_alias)
            if start >= 0:
                candidates.append((
                    len(normalized_alias),
                    start,
                    start + len(normalized_alias),
                    alias,
                    rule,
                ))

    matches: list[DemandKeywordMatch] = []
    seen_terms: set[str] = set()
    occupied: list[tuple[int, int]] = []
    for _, start, end, alias, rule in sorted(candidates, key=lambda item: -item[0]):
        if rule.canonical_term in seen_terms:
            continue
        if any(start < used_end and end > used_start for used_start, used_end in occupied):
            continue
        seen_terms.add(rule.canonical_term)
        occupied.append((start, end))
        matches.append(DemandKeywordMatch(rule=rule, matched_alias=alias))
    return matches
