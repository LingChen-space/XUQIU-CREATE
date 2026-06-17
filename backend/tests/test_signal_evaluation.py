"""需求信号评估规则测试。"""

from types import SimpleNamespace
import unittest

from app.models.platform_content import ContentType
from app.models.game import default_priority_weight
from app.services.data_adapter import DataAdapter
from app.services.llm_pipeline import LLMPipeline
from app.services.signal_engine import SignalEngine
from app.utils.engagement import compute_content_hot_score
from app.utils.keyword_matcher import detect_external_platform_tools


class SignalEvaluationTest(unittest.TestCase):
    def test_detects_external_platform_tool_launch_signal(self):
        strength, evidence = detect_external_platform_tools(
            ["洛克王国跑图辅助工具已经上线，玩家可以直接打开在线入口使用。"],
            ["https://tool.example.com/rock-map"],
        )

        self.assertGreaterEqual(strength, 0.8)
        self.assertTrue(any("上线" in item or "入口" in item for item in evidence))

    def test_single_post_comments_and_likes_outweigh_passive_views(self):
        engaged_post = compute_content_hot_score(
            view_count=0,
            like_count=120,
            comment_count=80,
            share_count=0,
        )
        passive_views = compute_content_hot_score(
            view_count=10000,
            like_count=0,
            comment_count=0,
            share_count=0,
        )

        self.assertGreater(engaged_post, passive_views)

    def test_content_heat_includes_single_post_engagement_boost(self):
        engine = SignalEngine.__new__(SignalEngine)
        low_engagement_contents = [
            SimpleNamespace(
                content_type=ContentType.post,
                view_count=5000,
                like_count=0,
                comment_count=0,
                share_count=0,
            )
            for _ in range(2)
        ]
        boosted_contents = low_engagement_contents + [
            SimpleNamespace(
                content_type=ContentType.post,
                view_count=0,
                like_count=120,
                comment_count=80,
                share_count=0,
            )
        ]

        self.assertGreater(
            engine._compute_content_heat(boosted_contents),
            engine._compute_content_heat(low_engagement_contents),
        )

    def test_monitor_item_mapping_preserves_comment_count(self):
        adapter = DataAdapter.__new__(DataAdapter)

        mapped = adapter._map_monitor_item(
            game_id="game-1",
            game_name="洛克王国：世界",
            platform_key="taptap",
            item={
                "title": "洛克跑图工具已经上线",
                "summary": "在线入口可直接使用",
                "thumbs": [1, 2, 3],
                "comments": 85,
                "created_time": 0,
                "id_str": "123",
            },
            keyword="工具",
        )

        self.assertEqual(mapped["comment_count"], 85)
        self.assertGreater(mapped["hot_score"], 0)

    def test_repeat_question_and_content_heat_have_higher_fallback_weight(self):
        pipeline = LLMPipeline.__new__(LLMPipeline)

        repeat_analysis = pipeline._fallback_analysis(
            SimpleNamespace(name="普通游戏", priority_weight=1),
            {"重复提问密度": 90},
        )
        heat_analysis = pipeline._fallback_analysis(
            SimpleNamespace(name="普通游戏", priority_weight=1),
            {"内容热度": 90},
        )

        self.assertGreaterEqual(repeat_analysis["potential_score"], 35)
        self.assertGreaterEqual(heat_analysis["potential_score"], 30)

    def test_priority_games_get_default_weight_and_score_boost(self):
        pipeline = LLMPipeline.__new__(LLMPipeline)
        signals = {"重复提问密度": 70, "内容热度": 70}

        normal = pipeline._fallback_analysis(
            SimpleNamespace(name="普通游戏", priority_weight=1),
            signals,
        )
        priority = pipeline._fallback_analysis(
            SimpleNamespace(name="三角洲行动", priority_weight=default_priority_weight("三角洲行动")),
            signals,
        )

        self.assertEqual(default_priority_weight("三角洲行动"), 3)
        self.assertEqual(default_priority_weight("洛克王国：世界"), 3)
        self.assertEqual(default_priority_weight("失控进化"), 3)
        self.assertGreater(priority["potential_score"], normal["potential_score"])


if __name__ == "__main__":
    unittest.main()
