"""工具君对话服务 —— 上下文构建 + 流式生成。

供 /api/chat SSE 路由使用：
- build_context(): 在请求依赖作用域内同步取完当日需求数据，组装成紧凑上下文文本。
- stream_chat(): 仅与 LLM 交互（不再碰 DB），逐字 yield 增量内容。
"""

import json
from collections import Counter
from datetime import date
from typing import AsyncGenerator

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.demand import Demand, DemandStatus
from app.models.game import Game, GameStatus
from app.models.daily_report import DailyReport
from app.services.llm_client import build_async_client


SYSTEM_PROMPT = """你是「好游快爆工具君」，好游快爆拓展组的需求分析助手。

## 你的职责
协助分析师解读每日的游戏工具需求挖掘结果。你可以回答这类问题：
- 今天有哪些高潜力（S/A 级）工具需求？首推哪个？
- 某款游戏为什么会产生需求？依据是什么？
- 某类工具（如交互地图、配装工具、资格聚合）的需求情况如何？
- 多款游戏的需求潜力对比
- 某游戏的需求信号分（重复提问密度、信息分散度、资格稀缺信号等）说明什么

## 背景
好游快爆是一个游戏工具和福利平台，服务数千万手游玩家，提供配装/战备计算器、交互地图、抽卡分析、资格/福利聚合、机制计算器、排行榜/对战数据、攻略辅助等工具。系统每日凌晨 06:00 自动跑需求挖掘管线：采集各平台近 24 小时内容 → 计算需求信号分 → LLM 产出结构化需求卡片（含工具类型、潜力分 0-100、可行度 1-5、推理依据）。

需求等级：S 级（爆款，潜力分高）、A 级（高潜）、B 级、C 级。
工具类型：配装/战备工具、交互地图、抽卡/概率分析、资格/福利聚合、机制计算器、排行榜/对战数据、剧情/收集进度、攻略辅助、模拟器、数据库、其他。

## 回答风格
- 用中文回答，专业、简洁、有条理。
- 善用分点和 **加粗** 突出关键信息；涉及数据时给出具体数字。
- **严格基于下方「当日需求数据」回答，不要编造没有的数据。** 若数据不足或当日尚未生成需求，请明确说明，并可建议用户点击「立即分析」触发管线。
- 不要编造游戏事件、兑换码、链接等未在数据中出现的信息。
"""


async def build_context(db: AsyncSession, today: date) -> str:
    """组装当日需求上下文文本（在请求依赖作用域内调用，取完即返回）。"""

    # 当日需求 TOP 15（关联游戏名）
    stmt = (
        select(Demand, Game)
        .join(Game, Demand.game_id == Game.id)
        .where(Demand.demand_date == today)
        .order_by(Demand.potential_score.desc())
        .limit(15)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # 当日需求总数与工具类型分布
    count_stmt = select(func.count(Demand.id)).where(Demand.demand_date == today)
    total_today = (await db.execute(count_stmt)).scalar() or 0

    type_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    for d, _g in rows:
        type_counter[d.tool_type.value] += 1
        status_counter[d.status.value] += 1
    # 全量类型分布需要再查一次（上面只统计了 top15）
    if total_today:
        full_type_stmt = (
            select(Demand.tool_type, func.count(Demand.id))
            .where(Demand.demand_date == today)
            .group_by(Demand.tool_type)
        )
        for tool_type, cnt in (await db.execute(full_type_stmt)).all():
            type_counter[tool_type.value] = cnt

    # 最近一条日报摘要
    report_stmt = select(DailyReport).order_by(DailyReport.report_date.desc()).limit(1)
    report = (await db.execute(report_stmt)).scalar()
    report_summary = (report.summary or "").strip() if report else ""

    # 活跃游戏数
    active_stmt = select(func.count(Game.id)).where(Game.status != GameStatus.inactive)
    active_game_count = (await db.execute(active_stmt)).scalar() or 0

    parts: list[str] = []
    parts.append(f"# 当日需求数据（{today.isoformat()}）")
    parts.append(f"- 当日需求总数：{total_today} 条")
    parts.append(f"- 活跃游戏数：{active_game_count}")
    if report_summary:
        parts.append(f"- 系统日报摘要：{report_summary}")

    if type_counter:
        dist = "、".join(f"{t}({c}条)" for t, c in type_counter.most_common())
        parts.append(f"- 工具类型分布：{dist}")

    if rows:
        parts.append("\n## 今日需求 TOP 列表（按潜力分降序，最多 15 条）")
        for i, (d, g) in enumerate(rows, 1):
            sig = _safe_json(d.signal_snapshot)
            sig_brief = ""
            if sig:
                top_sigs = sorted(
                    ((k, v) for k, v in sig.items() if isinstance(v, (int, float)) and v > 0),
                    key=lambda x: x[1],
                    reverse=True,
                )[:3]
                if top_sigs:
                    sig_brief = "；信号:" + "、".join(f"{k}{int(v)}" for k, v in top_sigs)
            parts.append(
                f"{i}. [{d.tool_type.value}] 《{g.name}》{d.title} "
                f"| 潜力分{int(d.potential_score)} 可行度{d.tool_feasibility}/5 "
                f"| 状态:{d.status.value}{sig_brief}"
            )
            if d.description:
                parts.append(f"   描述：{d.description[:80]}")
    else:
        parts.append("\n## 今日暂无需求")
        parts.append("今日尚未生成需求卡片。可能当日管线还未运行（每日 06:00 自动执行），可建议用户点击「立即分析」触发。")

    # 附带少量历史背景：最近 7 天需求量趋势
    trend_parts = await _recent_trend(db, today)
    if trend_parts:
        parts.append("\n## 近 7 天需求量趋势")
        parts.extend(trend_parts)

    return "\n".join(parts)


async def _recent_trend(db: AsyncSession, today: date) -> list[str]:
    """近 7 天每日需求条数，给 LLM 一个趋势参考。"""
    from datetime import timedelta

    start = today - timedelta(days=6)
    stmt = (
        select(Demand.demand_date, func.count(Demand.id))
        .where(Demand.demand_date >= start, Demand.demand_date <= today)
        .group_by(Demand.demand_date)
        .order_by(Demand.demand_date)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []
    counts = {d: c for d, c in rows}
    line = []
    for i in range(7):
        d = start + timedelta(days=i)
        line.append(f"{d.isoformat()}:{counts.get(d, 0)}")
    return ["、".join(line)]


def _safe_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


async def stream_chat(messages: list[dict], context: str) -> AsyncGenerator[str, None]:
    """调用 LLM 流式生成，逐字 yield 增量内容。

    messages: 前端传来的对话历史（role: user/assistant）。
    context: build_context 产出的当日需求数据文本。
    """
    client = build_async_client()
    if client is None:
        raise RuntimeError("LLM 未配置：请在 backend/.env 设置 LLM_API_KEY / LLM_API_BASE / LLM_MODEL")

    # 过滤前端消息，只保留合法 role，并裁剪历史长度
    clean_messages: list[dict] = []
    for m in messages[-20:]:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and content:
            clean_messages.append({"role": role, "content": str(content)})

    full_messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n# 当日需求数据（供你回答依据）\n" + context},
        *clean_messages,
    ]

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=full_messages,
        temperature=0.5,
        max_tokens=1500,
        stream=True,
    )

    async for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
