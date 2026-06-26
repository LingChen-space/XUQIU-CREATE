"""体验服版本/爆料需求词的 LLM 提取。

体验服类游戏不走标准工具词库，而是由 LLM 从内容标题中提取
「日期 + 新内容」型的版本/爆料需求词，例如：
  标题「三角洲行动体验服6月25日爆料，新地图A23核电站上线」
    -> term「6月25日新地图A23核心站」
  标题「和平精英体验服7月10日开服，地铁逃生上线」
    -> term「7月10日开服地铁逃生」
"""

import json
import re

from app.config import settings
from app.services.llm_client import build_async_client


EXTRACTION_PROMPT = """你是好游快爆体验服需求雷达助手。
从体验服内容标题中提取「版本/爆料」型需求词：把日期(如有)和具体新内容压缩成一个紧凑短语，
覆盖新地图/新模式/新玩法/开服/上线/新角色/新武器/新系统等版本更新信息。

规则：
- term 形如「日期+新内容」，不含标点和空格，日期用原文(如6月25日、7月10日)，后接具体新内容名称。
- 只提取确实属于版本更新/爆料/上线的信息；如果标题只是攻略、求助、资格招募等非版本内容，该条不要输出。
- 一条内容最多输出一个 term。

只输出 JSON：
{{"findings":[{{"content_id":"...","term":"日期+新内容短语","summary":"一句话说明这次更新内容"}}]}}

示例：
标题：三角洲行动体验服6月25日爆料，新地图A23核电站上线
输出：{{"content_id":"示例","term":"6月25日新地图A23核心站","summary":"6月25日上线新地图A23核电站"}}

标题：和平精英体验服7月10日开服，地铁逃生上线
输出：{{"content_id":"示例","term":"7月10日开服地铁逃生","summary":"7月10日开服并上线地铁逃生"}}

内容：
{contents}
"""


class ExperienceServerExtractor:
    """批量提取体验服版本/爆料需求词。"""

    def __init__(self, client=None):
        self.client = client if client is not None else build_async_client()

    async def extract_batch(self, contents) -> dict[str, list[dict]]:
        """contents: list[PlatformContent] -> {content_id: [{"term","summary"}]}。

        LLM 调用或解析失败时抛出，由调用方决定重试。
        """
        if self.client is None or not contents:
            return {}

        prompt_contents = "\n\n".join(
            f"内容ID：{content.id}\n标题：{content.title}\n正文：{(content.body or '')[:600]}"
            for content in contents
        )
        response = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "只输出合法JSON，不要解释。"},
                {"role": "user", "content": EXTRACTION_PROMPT.format(contents=prompt_contents)},
            ],
            temperature=0.2,
            max_tokens=2500,
        )
        raw = response.choices[0].message.content or ""
        findings = self._parse_findings(raw)

        by_content: dict[str, list[dict]] = {}
        for finding in findings:
            content_id = str(finding.get("content_id") or "").strip()
            term = str(finding.get("term") or "").strip()
            if not content_id or not term:
                continue
            by_content.setdefault(content_id, []).append({
                "term": term[:256],
                "summary": str(finding.get("summary") or "").strip()[:1000],
            })
        return by_content

    @staticmethod
    def _parse_findings(raw: str) -> list[dict]:
        block = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        if block:
            raw = block.group(1)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("模型未返回JSON对象")
        data = json.loads(match.group())
        findings = data.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError("findings必须为数组")
        return [item for item in findings if isinstance(item, dict)]
