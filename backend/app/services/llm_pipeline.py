"""LLM 痛点提炼管线。

每日对候选游戏调用 LLM，输出结构化需求卡片。
"""

import json
import re
import uuid
from dataclasses import dataclass
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
from app.utils.engagement import compute_content_hot_score


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

## 该游戏的需求信号分（0-100）
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


@dataclass(frozen=True)
class DemandThemeRule:
    key: str
    tool_type: str
    title_label: str
    description_label: str
    keywords: tuple[str, ...]
    title_keywords: tuple[str, ...]
    feasibility: int


DEMAND_THEME_RULES = (
    DemandThemeRule(
        key="map",
        tool_type="交互地图",
        title_label="地图/点位工具",
        description_label="地图点位、路线和资源位置",
        keywords=("地图", "新地图", "点位", "路线", "资源点", "核电站", "出生点", "撤离点", "位置", "跑图"),
        title_keywords=("核电站", "新地图", "地图", "点位", "资源点"),
        feasibility=4,
    ),
    DemandThemeRule(
        key="loadout",
        tool_type="配装/战备工具",
        title_label="卡战备/配装工具",
        description_label="战备值、配装、配件和武器方案",
        keywords=("卡战备", "战备值", "战备", "配装", "配件", "武器", "装备", "改枪", "阈值", "怎么搞"),
        title_keywords=("卡战备", "战备值", "战备", "配装", "改枪"),
        feasibility=4,
    ),
    DemandThemeRule(
        key="qualification",
        tool_type="资格/福利聚合",
        title_label="体验服资格/福利聚合",
        description_label="体验服资格、抢码、报名入口和开放时间",
        keywords=("体验服", "资格", "抢码", "申请", "内测", "测试资格", "开放时间", "招募", "报名", "入口"),
        title_keywords=("体验服资格", "资格", "抢码", "招募", "报名"),
        feasibility=3,
    ),
    DemandThemeRule(
        key="gacha",
        tool_type="抽卡/概率分析",
        title_label="抽卡/概率分析工具",
        description_label="抽卡记录、概率、保底和出货分析",
        keywords=("抽卡", "概率", "保底", "记录", "出货", "歪了", "池子"),
        title_keywords=("抽卡", "概率", "保底"),
        feasibility=4,
    ),
    DemandThemeRule(
        key="mechanism",
        tool_type="机制计算器",
        title_label="机制计算器",
        description_label="材料、养成、公式、伤害和机制参数",
        keywords=("材料", "养成", "突破", "技能", "公式", "伤害", "倍率", "系数", "计算器", "机制"),
        title_keywords=("计算器", "公式", "伤害", "材料"),
        feasibility=4,
    ),
    DemandThemeRule(
        key="guide",
        tool_type="攻略辅助",
        title_label="攻略辅助工具",
        description_label="攻略、教程、打法、阵容和推荐方案",
        keywords=("攻略", "教程", "打法", "阵容", "推荐", "新手", "入门", "教学"),
        title_keywords=("攻略", "教程", "打法", "阵容"),
        feasibility=3,
    ),
)


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
        analyses = await self._analyze_game_demands(game, window_date)
        return analyses[0] if analyses else None

    async def _get_recent_contents(
        self,
        game_id: str,
        window_date: date,
        limit: int | None = None,
    ) -> list[PlatformContent]:
        """获取指定游戏在日期窗口内的高热内容。"""
        cutoff = datetime.combine(window_date, datetime.min.time()) - timedelta(hours=24)
        end = datetime.combine(window_date, datetime.min.time()) + timedelta(hours=24)

        stmt = select(PlatformContent).where(
            and_(
                PlatformContent.game_id == game_id,
                PlatformContent.published_at >= cutoff,
                PlatformContent.published_at < end,
            )
        ).order_by(PlatformContent.hot_score.desc())
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def _analyze_game_demands(self, game: Game, window_date: date) -> list[dict]:
        """对一款游戏产出一个或多个需求分析结果。"""
        contents = await self._get_recent_contents(game.id, window_date)
        if len(contents) < 2:
            return []

        signals = await self.engine.get_signals_for_game(game.id, window_date)

        if self.client:
            contents_text = self._format_contents_for_prompt(contents[:20])
            signals_text = self._format_signals_for_prompt(signals)
            analysis = await self._call_llm(game.name, contents_text, signals_text)
            return [analysis] if analysis else []

        analyses = self._theme_analysis_from_contents(game, contents, signals)
        if analyses:
            return analyses

        fallback = self._fallback_analysis(game, signals)
        return [fallback] if fallback else []

    def _format_contents_for_prompt(self, contents: list[PlatformContent]) -> str:
        """构建 LLM 提示词里的内容列表。"""
        content_parts = []
        for i, c in enumerate(contents):
            platform = c.platform.value if hasattr(c.platform, "value") else str(c.platform)
            content_type = c.content_type.value if hasattr(c.content_type, "value") else str(c.content_type)
            part = f"[{i+1}] 平台: {platform} | 类型: {content_type} | 标题: {c.title}\n"
            part += f"    互动: 浏览{c.view_count} 赞{c.like_count} 评{c.comment_count}\n"
            if c.body:
                part += f"    摘要: {c.body[:200]}\n"
            content_parts.append(part)
        return "\n".join(content_parts)

    def _format_signals_for_prompt(self, signals: dict) -> str:
        """构建 LLM 提示词里的信号分列表。"""
        signals_lines = []
        for name, score in signals.items():
            bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
            signals_lines.append(f"  {name}: [{bar}] {score:.0f}/100")
        return "\n".join(signals_lines) if signals_lines else "暂无信号数据"

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

    def _theme_analysis_from_contents(self, game: Game, contents: list[PlatformContent], signals: dict) -> list[dict]:
        """从具体内容关键词和热度中提取多个需求主题。"""
        theme_stats: dict[str, dict] = {}

        for content in contents:
            title = content.title or ""
            body = content.body or ""
            title_text = title.lower()
            body_text = body.lower()
            heat = max(
                float(getattr(content, "hot_score", 0) or 0),
                compute_content_hot_score(
                    getattr(content, "view_count", 0),
                    getattr(content, "like_count", 0),
                    getattr(content, "comment_count", 0),
                    getattr(content, "share_count", 0),
                ),
            )

            for rule in DEMAND_THEME_RULES:
                title_hits = [kw for kw in rule.keywords if kw.lower() in title_text]
                body_hits = [kw for kw in rule.keywords if kw.lower() in body_text]
                if not title_hits and not body_hits:
                    continue

                stat = theme_stats.setdefault(rule.key, {
                    "rule": rule,
                    "matched_contents": [],
                    "title_hits": 0,
                    "keyword_hits": 0,
                    "heat_sum": 0.0,
                    "max_heat": 0.0,
                    "focus_counts": {},
                })
                stat["matched_contents"].append(content)
                stat["title_hits"] += len(title_hits)
                stat["keyword_hits"] += len(title_hits) + len(body_hits)
                stat["heat_sum"] += heat
                stat["max_heat"] = max(stat["max_heat"], heat)

                for kw in title_hits + body_hits:
                    stat["focus_counts"][kw] = stat["focus_counts"].get(kw, 0) + (2 if kw in title_hits else 1)

        analyses: list[dict] = []
        priority_weight = max(1, min(int(getattr(game, "priority_weight", 1) or 1), 5))
        priority_multiplier = 1 + (priority_weight - 1) * 0.08

        for stat in theme_stats.values():
            rule: DemandThemeRule = stat["rule"]
            matched_contents = stat["matched_contents"]
            if not matched_contents:
                continue

            focus = self._select_theme_focus(rule, stat["focus_counts"])
            avg_heat = stat["heat_sum"] / len(matched_contents)
            potential = (
                len(matched_contents) * 12
                + stat["title_hits"] * 8
                + stat["keyword_hits"] * 3
                + avg_heat * 0.35
                + stat["max_heat"] * 0.25
            ) * priority_multiplier
            potential_score = round(min(100.0, potential), 0)
            if potential_score < 35:
                continue

            evidence_posts = sorted(
                matched_contents,
                key=lambda c: max(
                    float(getattr(c, "hot_score", 0) or 0),
                    compute_content_hot_score(
                        getattr(c, "view_count", 0),
                        getattr(c, "like_count", 0),
                        getattr(c, "comment_count", 0),
                        getattr(c, "share_count", 0),
                    ),
                ),
                reverse=True,
            )[:5]
            top_titles = [c.title for c in evidence_posts if getattr(c, "title", "")]
            focus_prefix = f"{focus}" if focus else rule.title_label
            tool_title = self._build_theme_title(game.name, rule, focus)

            analyses.append({
                "high_freq_questions": top_titles[:5],
                "info_gap": f"近24小时内容集中提到{focus_prefix}，但信息分散在多篇帖子和摘要中，需要聚合成可直接使用的{rule.description_label}。",
                "tool_feasibility": rule.feasibility,
                "tool_type_suggestion": rule.tool_type,
                "tool_title": tool_title,
                "tool_description": f"聚合{game.name}相关{rule.description_label}，按热度内容提炼可操作信息。",
                "reasoning": (
                    f"{len(matched_contents)}篇内容命中“{focus_prefix}”相关关键词，"
                    f"标题命中{stat['title_hits']}次，最高热度{stat['max_heat']:.0f}分。"
                ),
                "potential_score": potential_score,
                "evidence_post_ids": [p.id for p in evidence_posts if getattr(p, "id", None)],
                "theme_key": rule.key,
            })

        return sorted(analyses, key=lambda item: item["potential_score"], reverse=True)

    def _select_theme_focus(self, rule: DemandThemeRule, focus_counts: dict[str, int]) -> str:
        """选择最适合放进需求标题的具体主题词。"""
        for kw in rule.title_keywords:
            if kw in focus_counts:
                return kw
        if not focus_counts:
            return ""
        return max(focus_counts, key=focus_counts.get)

    def _build_theme_title(self, game_name: str, rule: DemandThemeRule, focus: str) -> str:
        """生成自然的需求标题，避免体验服等词重复。"""
        suffix = rule.title_label
        if focus and focus not in suffix:
            suffix = f"{focus}{suffix}"
        if game_name.endswith("体验服") and suffix.startswith("体验服"):
            suffix = suffix[len("体验服"):]
        return f"{game_name}{suffix}"

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
            "外部平台工具上线": ("攻略辅助", "外部平台已有工具上线，说明需求被验证且适合做更好的站内体验"),
        }

        tool_type, reasoning = signal_to_tool.get(top_signal, ("其他", "综合信号表明存在用户需求"))

        # 综合潜力分：加权平均
        weights = {
            "重复提问密度": 0.35,
            "内容热度": 0.30,
            "民间工具萌芽": 0.15,
            "信息分散度": 0.10,
            "资格稀缺信号": 0.10,
            "机制复杂度": 0.10,
            "外部平台工具上线": 0.10,
        }
        weighted = sum(scores.get(k, 0) * weights.get(k, 0) for k in weights)
        priority_weight = max(1, min(int(getattr(game, "priority_weight", 1) or 1), 5))
        priority_multiplier = 1 + (priority_weight - 1) * 0.08
        potential = min(100.0, weighted * 1.2 * priority_multiplier)

        return {
            "high_freq_questions": [f"{game.name}相关需求待 LLM 分析"],
            "info_gap": "需要 LLM 深度分析确认信息缺口",
            "tool_feasibility": 3,
            "tool_type_suggestion": tool_type,
            "tool_title": f"{game.name}{tool_type}（待确认）",
            "tool_description": f"基于需求信号分析，{game.name}在{tool_type}方向有潜力",
            "reasoning": reasoning,
            "potential_score": round(potential, 0),
        }

    async def run_pipeline(self, game_ids: list[str], window_date: date) -> list[Demand]:
        """
        运行完整分析管线：对每款游戏执行 LLM 分析，生成需求卡片写入数据库。
        返回生成的需求列表。
        """
        # 获取游戏
        stmt = select(Game).where(Game.id.in_(game_ids)).order_by(Game.priority_weight.desc(), Game.name)
        result = await self.session.execute(stmt)
        games = result.scalars().all()

        demands = []
        for game in games:
            analyses = await self._analyze_game_demands(game, window_date)
            if not analyses:
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

            for analysis in analyses:
                # 解析 tool_type
                tool_type_str = analysis.get("tool_type_suggestion", "其他")
                try:
                    tool_type = ToolType._value2member_map_.get(tool_type_str, ToolType.other)
                except Exception:
                    tool_type = ToolType.other

                title = analysis.get("tool_title", f"{game.name}工具需求")
                demand_stmt = (
                    select(Demand)
                    .where(
                        and_(
                            Demand.game_id == game.id,
                            Demand.demand_date == window_date,
                            Demand.tool_type == tool_type,
                            Demand.title == title,
                        )
                    )
                    .order_by(Demand.created_at.desc())
                )
                demand_result = await self.session.execute(demand_stmt)
                demand = demand_result.scalar()
                if demand is None:
                    demand = Demand(
                        id=str(uuid.uuid4()),
                        game_id=game.id,
                        status=DemandStatus.new,
                        demand_date=window_date,
                    )
                    self.session.add(demand)

                evidence_ids = analysis.get("evidence_post_ids") or [p.id for p in evidence_posts]
                demand.tool_type = tool_type
                demand.title = title
                demand.description = analysis.get("tool_description", "")
                demand.potential_score = float(analysis.get("potential_score", 0))
                demand.tool_feasibility = int(analysis.get("tool_feasibility", 0))
                demand.signal_snapshot = json.dumps(signals, ensure_ascii=False)
                demand.llm_analysis = json.dumps(analysis, ensure_ascii=False)
                demand.evidence_post_ids = json.dumps(evidence_ids[:5], ensure_ascii=False)
                demands.append(demand)

        await self.session.commit()
        return demands
