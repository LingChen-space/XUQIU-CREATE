"""Match mined demand cards against kuaibao already-launched tools."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "kuaibao_launched_tools.json"

NEED_TERMS = (
    "孵蛋", "配方", "模拟器", "计算器", "蛋组", "进化",
    "地图", "点位", "资源", "路线", "查询", "数据库", "图鉴",
    "体验服", "资格", "招募", "抢码", "报名", "福利", "兑换码", "密令", "口令", "礼包码",
    "战备", "配装", "改枪", "装备", "灵敏度", "出装", "铭文",
    "抽卡", "概率", "记录", "保底",
    "悬赏", "封印", "妖怪", "答题", "起名",
)

QUALIFICATION_NEED_TERMS = ("资格", "福利", "招募", "抢码", "报名", "申请", "开服", "开放时间")


def _normalize(text: Any) -> str:
    value = str(text or "").lower()
    value = re.sub(r"[\s:：·,，。.!！?？/\\|、\-_\(\)（）《》【】\[\]\"'“”‘’]+", "", value)
    return value


def _terms_in_text(text: str) -> set[str]:
    return {term for term in NEED_TERMS if term.lower() in text.lower()}


@lru_cache(maxsize=1)
def load_launched_tools() -> list[dict[str, str]]:
    if not DATA_PATH.exists():
        return []
    try:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    tools: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        tools.append({"id": str(item.get("id") or ""), "name": name})
    return tools


def find_launched_tool_matches(
    *,
    game_name: str,
    tool_type: str,
    title: str,
    description: str = "",
    reasoning: str = "",
    launched_tools: list[dict[str, str]] | None = None,
    limit: int = 3,
) -> list[str]:
    """Return already-launched kuaibao tool names relevant to this demand."""
    tools = launched_tools if launched_tools is not None else load_launched_tools()
    demand_text = " ".join([game_name, tool_type, title, description, reasoning])
    demand_key = _normalize(demand_text)
    game_key = _normalize(game_name)
    demand_terms = {
        term
        for term in _terms_in_text(demand_text)
        if _normalize(term) and _normalize(term) not in game_key
    }
    is_qualification_need = "资格/福利" in tool_type or any(term in demand_text for term in QUALIFICATION_NEED_TERMS)

    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for tool in tools:
        name = str(tool.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        tool_key = _normalize(name)
        if not tool_key:
            continue

        direct_match = tool_key in demand_key or demand_key in tool_key
        game_match = bool(game_key and game_key in tool_key)
        tool_is_game_label = bool(
            game_key
            and (tool_key == game_key or tool_key in game_key or game_key in tool_key)
            and len(tool_key) - len(game_key) <= len(_normalize("体验服"))
        )
        term_hits = {term for term in demand_terms if _normalize(term) in tool_key}

        if not direct_match and not game_match:
            continue
        if tool_is_game_label and not is_qualification_need:
            continue
        if not direct_match and game_match and not term_hits:
            continue

        score = 0
        if direct_match:
            score += 100
        if game_match:
            score += 50
        score += len(term_hits) * 15
        scored.append((score, name))

    scored.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    return [name for _score, name in scored[:limit]]
