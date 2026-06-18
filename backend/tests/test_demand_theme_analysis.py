"""需求主题分析规则测试。"""

from datetime import datetime
from types import SimpleNamespace
import asyncio
import unittest

from app.models.platform_content import ContentType
from app.services.llm_pipeline import LLMPipeline


def content(
    title: str,
    body: str = "",
    likes: int = 0,
    comments: int = 0,
    views: int = 0,
    content_id: str = "content-1",
):
    return SimpleNamespace(
        id=content_id,
        title=title,
        body=body,
        content_type=ContentType.post,
        view_count=views,
        like_count=likes,
        comment_count=comments,
        share_count=0,
        hot_score=0,
        published_at=datetime.now(),
    )


class DemandThemeAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.pipeline = LLMPipeline.__new__(LLMPipeline)

    def test_repeated_hot_loadout_keywords_create_delta_force_loadout_demand(self):
        analyses = self.pipeline._theme_analysis_from_contents(
            SimpleNamespace(name="三角洲行动", priority_weight=3),
            [
                content("三角洲行动卡战备怎么搞，战备值一直不够", "求一套配装和配件方案", 180, 96, 12000, "a"),
                content("卡战备到底怎么搞？新手配装求推荐", "武器配件和战备阈值看不懂", 120, 75, 9000, "b"),
                content("三角洲行动战备值配装表有人做了吗", "想要可以直接算的工具", 95, 64, 7000, "c"),
            ],
            {},
        )

        loadout = next(a for a in analyses if a["tool_type_suggestion"] == "配装/战备工具")
        self.assertIn("卡战备", loadout["tool_title"])
        self.assertGreaterEqual(loadout["potential_score"], 80)
        self.assertEqual(loadout["evidence_post_ids"], ["a", "b", "c"])

    def test_hot_nuclear_power_plant_mentions_create_map_demand(self):
        analyses = self.pipeline._theme_analysis_from_contents(
            SimpleNamespace(name="三角洲行动体验服", priority_weight=3),
            [
                content("三角洲行动体验服新地图核电站点位整理", "资源点和路线都变了", 220, 130, 16000, "a"),
                content("核电站地图太复杂了，撤离路线怎么走", "求交互地图标点", 160, 88, 11000, "b"),
                content("体验服核电站资源点位置汇总", "出生点和撤离点需要标记", 100, 62, 8000, "c"),
            ],
            {},
        )

        map_demand = next(a for a in analyses if a["tool_type_suggestion"] == "交互地图")
        self.assertIn("核电站", map_demand["tool_title"])
        self.assertGreaterEqual(map_demand["potential_score"], 80)

    def test_experience_server_recruitment_mentions_create_qualification_demand(self):
        analyses = self.pipeline._theme_analysis_from_contents(
            SimpleNamespace(name="三角洲行动体验服", priority_weight=3),
            [
                content("三角洲行动体验服资格怎么申请", "抢码入口和开放时间在哪看", 130, 90, 9000, "a"),
                content("体验服测试资格招募开启，报名条件汇总", "资格有限先到先得", 110, 70, 8500, "b"),
            ],
            {},
        )

        qualification = next(a for a in analyses if a["tool_type_suggestion"] == "资格/福利聚合")
        self.assertIn("体验服资格", qualification["tool_title"])
        self.assertGreaterEqual(qualification["potential_score"], 70)

    def test_game_analysis_can_return_multiple_theme_demands(self):
        async def get_contents(game_id, window_date, limit=None):
            return [
                content("三角洲行动卡战备怎么搞", "配装和战备值看不懂", 150, 80, 10000, "a"),
                content("三角洲行动体验服核电站地图点位", "资源点和撤离路线汇总", 170, 95, 12000, "b"),
            ]

        async def get_signals_for_game(game_id, window_date):
            return {"内容热度": 80}

        self.pipeline.client = None
        self.pipeline._get_recent_contents = get_contents
        self.pipeline.engine = SimpleNamespace(get_signals_for_game=get_signals_for_game)

        analyses = asyncio.run(self.pipeline._analyze_game_demands(
            SimpleNamespace(id="game-1", name="三角洲行动体验服", priority_weight=3),
            datetime.now().date(),
        ))

        tool_types = {a["tool_type_suggestion"] for a in analyses}
        self.assertIn("配装/战备工具", tool_types)
        self.assertIn("交互地图", tool_types)


if __name__ == "__main__":
    unittest.main()
