"""LLM 痛点提炼管线。

每日对候选游戏调用 LLM，输出结构化需求卡片。
"""

import json
import re
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from app.config import settings
from app.models.game import Game
from app.models.platform_content import PlatformContent
from app.models.demand_signal import DemandSignal
from app.models.demand import Demand, DemandStatus, ToolType
from app.services.signal_engine import SignalEngine


DEMAND_ANALYSIS_PROMPT = """你是好游快爆的游戏工具需求分析师。你的任务是分析某款热门手游的用户讨论，从中挖掘出具有爆款潜力的**游戏工具需求**。

## 背景
好游快爆是一个游戏工具和福利平台，服务数千万手游玩家。我们为玩家提供各类实用游戏工具，如：
- 配装/战备计算器（帮玩家计算最佳装备搭配）
- 交互地图（标记游戏资源点、收集物位置）
- 抽卡分析工具（分析玩家的抽卡概率和记录）
- 资格/福利聚合（帮助玩家获取测试资格、福利码）
- 机制计算器（如孵蛋配方、伤害模拟、材料计算）
- 排行榜/对战数据分析
- 攻略辅助系统

## 你要分析的游戏
**游戏名称**：{game_name}

## 过去24小时跨平台内容

{contents_text}

## 该游戏的六维需求信号分（0-100）
{signals_text}

## 分析任务

请严格按以下 JSON 格式输出你的分析结果（只输出 JSON，不要其他内容）：

```json
{{
  "high_freq_questions": ["问题1", "问题2", "问题3"],
  "info_gap": "当前内容供给是否存在缺口？描述信息碎片化程度和缺位情况",
  "tool_feasibility": 4,
  "tool_type_suggestion": "配装/战备工具",
  "tool_title": "工具名称建议",
  "tool_description": "工具功能描述，50字以内",
  "reasoning": "你的判断理由，为什么这个需求有爆款潜力？",
  "potential_score": 85
}}
```

要求：
- high_freq_questions：提炼3-5个玩家反复在问的具体问题
- info_gap：判断现有攻略/内容是否能解决这些问题，信息缺口在哪
- tool_feasibility：1-5分，1=不适合做工具, 5=非常适合做工具（参数明确、有确定性逻辑）
- tool_type_suggestion：从以下列表选一个最匹配的：配装/战备工具、交互地图、抽卡/概率分析、资格/福利聚合、机制计算器、排行榜/对战数据、剧情/收集进度、攻略辅助、模拟器、数据库、其他
- potential_score：综合爆款潜力分 0-100，参考信号评分并加入你的专业判断
"""


class LLMPipeline:
    """LLM 分析管线。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.client: AsyncOpenAI | None = None
        if settings.llm_api_key:
            # 清理 base_url：确保不以 /chat/completions 结尾（SDK 会自动追加）
            clean_url = settings.llm_api_base.rstrip('/')
            if clean_url.endswith('/chat/completions'):
                clean_url = clean_url[:-len('/chat/completions')]
            self.client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=clean_url,
            )
        self.engine = SignalEngine(session)

    async def analyze_game(self, game: Game, window_date: date) -> dict | None:
        """对一款游戏执行 LLM 分析，返回需求卡片字典或 None。"""
        # 获取该游戏过去24h的内容
        cutoff = datetime.combine(window_date, datetime.min.time()) - timedelta(hours=24)
        end = datetime.combine(window_date, datetime.min.time()) + timedelta(hours=24)

        stmt = select(PlatformContent).where(
            and_(
                PlatformContent.game_id == game.id,
                PlatformContent.published_at >= cutoff,
                PlatformContent.published_at < end,
            )
        ).order_by(PlatformContent.hot_score.desc()).limit(20)

        result = await self.session.execute(stmt)
        contents = result.scalars().all()

        if len(contents) < 2:
            return None

        # 构建内容文本
        content_parts = []
        for i, c in enumerate(contents):
            part = f"[{i+1}] 平台: {c.platform.value} | 类型: {c.content_type.value} | 标题: {c.title}\n"
            part += f"    互动: 浏览{c.view_count} 赞{c.like_count} 评{c.comment_count}\n"
            if c.body:
                part += f"    摘要: {c.body[:200]}\n"
            content_parts.append(part)
        contents_text = "\n".join(content_parts)

        # 获取信号分
        signals = await self.engine.get_signals_for_game(game.id, window_date)
        signals_lines = []
        for name, score in signals.items():
            bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
            signals_lines.append(f"  {name}: [{bar}] {score:.0f}/100")
        signals_text = "\n".join(signals_lines) if signals_lines else "暂无信号数据"

        # 调用 LLM 或 Fallback
        if self.client:
            analysis = await self._call_llm(game.name, contents_text, signals_text)
        else:
            analysis = self._fallback_analysis(game, signals)

        return analysis

    async def _call_llm(self, game_name: str, contents_text: str, signals_text: str) -> dict:
        """调用 LLM API 进行分析。"""
        prompt = DEMAND_ANALYSIS_PROMPT.format(
            game_name=game_name,
            contents_text=contents_text[:6000],  # 控制 token 数
            signals_text=signals_text,
        )

        try:
            response = await self.client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "你是游戏工具需求分析师。只输出 JSON，不要其他内容。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=1024,
            )
            raw = response.choices[0].message.content
            print(f"[LLM] Raw response length for {game_name}: {len(raw) if raw else 0} chars")
            print(f"[LLM] Raw response first 300 chars: {raw[:300] if raw else 'EMPTY'}")
            return self._parse_llm_response(raw)
        except Exception as e:
            import traceback
            print(f"[LLM] Call failed for {game_name}: {e}")
            traceback.print_exc()
            return None

    def _parse_llm_response(self, raw: str) -> dict | None:
        """解析 LLM 返回的 JSON。"""
        if not raw:
            return None
        # 尝试提取 JSON 块
        # 先尝试提取 ```json ... ``` 代码块
        json_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
        if json_block:
            raw = json_block.group(1).strip()
        # 尝试匹配最外层 JSON 对象
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None

    def _fallback_analysis(self, game: Game, signals: dict) -> dict:
        """
        无 LLM API 时的规则 Fallback 分析。
        基于信号分最高的维度推断需求类型和潜力分。
        """
        scores = {k: v for k, v in signals.items() if v > 0}
        if not scores:
            return None

        top_signal = max(scores, key=scores.get)

        # 根据信号类型映射工具类型
        signal_to_tool = {
            "重复提问密度": ("机制计算器", "玩家反复提问的问题可以通过工具一站式解决"),
            "信息分散度": ("交互地图", "碎片化的攻略信息需要结构化工具整合"),
            "民间工具萌芽": ("抽卡/概率分析", "已有用户自发制作工具，说明强需求存在"),
            "资格稀缺信号": ("资格/福利聚合", "限量资源争夺是天然的聚合工具场景"),
            "机制复杂度": ("配装/战备工具", "复杂系统带来的决策成本可以用计算器降低"),
            "内容热度": ("攻略辅助", "高热度的游戏内容消费说明用户对辅助工具有需求"),
        }

        tool_type, reasoning = signal_to_tool.get(top_signal, ("其他", "综合信号表明存在用户需求"))

        # 综合潜力分：加权平均
        weights = {
            "重复提问密度": 0.25,
            "信息分散度": 0.15,
            "民间工具萌芽": 0.25,
            "资格稀缺信号": 0.15,
            "机制复杂度": 0.15,
            "内容热度": 0.05,
        }
        weighted = sum(scores.get(k, 0) * weights.get(k, 0) for k in weights)
        potential = min(100.0, weighted * 1.2)

        return {
            "high_freq_questions": [f"{game.name}相关需求待 LLM 分析"],
            "info_gap": "需要 LLM 深度分析确认信息缺口",
            "tool_feasibility": 3,
            "tool_type_suggestion": tool_type,
            "tool_title": f"{game.name}{tool_type}（待确认）",
            "tool_description": f"基于六维信号分析，{game.name}在{tool_type}方向有潜力",
            "reasoning": reasoning,
            "potential_score": round(potential, 0),
        }

    async def run_pipeline(self, game_ids: list[str], window_date: date) -> list[Demand]:
        """
        运行完整分析管线：对每款游戏执行 LLM 分析，生成需求卡片写入数据库。
        返回生成的需求列表。
        """
        # 获取游戏
        stmt = select(Game).where(Game.id.in_(game_ids))
        result = await self.session.execute(stmt)
        games = result.scalars().all()

        demands = []
        for game in games:
            analysis = await self.analyze_game(game, window_date)
            if not analysis:
                continue

            # 获取信号快照
            signal_engine = SignalEngine(self.session)
            signals = await signal_engine.get_signals_for_game(game.id, window_date)

            # 获取证据帖
            cutoff = datetime.combine(window_date, datetime.min.time()) - timedelta(hours=24)
            end = datetime.combine(window_date, datetime.min.time()) + timedelta(hours=24)
            evidence_stmt = (
                select(PlatformContent)
                .where(
                    and_(
                        PlatformContent.game_id == game.id,
                        PlatformContent.published_at >= cutoff,
                        PlatformContent.published_at < end,
                    )
                )
                .order_by(PlatformContent.hot_score.desc())
                .limit(5)
            )
            ev_result = await self.session.execute(evidence_stmt)
            evidence_posts = ev_result.scalars().all()

            # 解析 tool_type
            tool_type_str = analysis.get("tool_type_suggestion", "其他")
            try:
                tool_type = ToolType._value2member_map_.get(tool_type_str, ToolType.other)
            except Exception:
                tool_type = ToolType.other

            demand = Demand(
                id=str(uuid.uuid4()),
                game_id=game.id,
                tool_type=tool_type,
                title=analysis.get("tool_title", f"{game.name}工具需求"),
                description=analysis.get("tool_description", ""),
                potential_score=float(analysis.get("potential_score", 0)),
                tool_feasibility=int(analysis.get("tool_feasibility", 0)),
                status=DemandStatus.new,
                signal_snapshot=json.dumps(signals, ensure_ascii=False),
                llm_analysis=json.dumps(analysis, ensure_ascii=False),
                evidence_post_ids=json.dumps([p.id for p in evidence_posts], ensure_ascii=False),
                demand_date=window_date,
            )
            self.session.add(demand)
            demands.append(demand)

        await self.session.commit()
        return demands
