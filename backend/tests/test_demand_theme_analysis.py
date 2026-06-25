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
                content("三角洲体验服核电站地图太复杂了，撤离路线怎么走", "求交互地图标点", 160, 88, 11000, "b"),
                content("三角洲行动体验服核电站资源点位置汇总", "出生点和撤离点需要标记", 100, 62, 8000, "c"),
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

    def test_latest_redeem_code_mentions_create_welfare_code_demand(self):
        analyses = self.pipeline._theme_analysis_from_contents(
            SimpleNamespace(name="问剑长生", priority_weight=2),
            [
                content("问剑长生端午兑换码更新，仙长快来领密令", "最新口令码和礼包码有效期整理", 160, 82, 12000, "a"),
                content("仙长端午安康，来领密令！", "兑换码、福利码入口和领取方式汇总", 120, 64, 9000, "b"),
                content("问剑长生最新口令码合集", "今日新增礼包码，过期前记得兑换", 95, 40, 7000, "c"),
            ],
            {},
        )

        welfare = next(a for a in analyses if a["theme_key"] == "welfare_code")
        self.assertEqual(welfare["tool_type_suggestion"], "资格/福利聚合")
        self.assertTrue(any(keyword in welfare["tool_title"] for keyword in ["兑换码", "密令", "口令"]))
        self.assertGreaterEqual(welfare["potential_score"], 80)
        self.assertEqual(welfare["evidence_post_ids"], ["a", "b", "c"])

    def test_game_analysis_can_return_multiple_theme_demands(self):
        async def get_contents(game_id, window_date, limit=None):
            return [
                content("三角洲行动体验服卡战备怎么搞", "配装和战备值看不懂", 150, 80, 10000, "a"),
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
        self.assertTrue(all(a["allow_auto_promote"] is False for a in analyses))
        self.assertEqual(
            {a["standard_term"] for a in analyses},
            {"卡战备", "地图点位"},
        )

    def test_non_priority_game_analysis_only_uses_generic_terms(self):
        analyses = self.pipeline._keyword_analysis_from_contents(
            SimpleNamespace(name="测试新游戏", priority_weight=1),
            [
                content(
                    "测试新游戏战绩查询和圣遗物评分器",
                    "",
                    100,
                    50,
                    5000,
                    "a",
                ),
            ],
            {},
        )

        self.assertEqual(
            {analysis["standard_term"] for analysis in analyses},
            {"战绩查询"},
        )

    def test_locke_domain_terms_create_breeding_mechanism_demand(self):
        analyses = self.pipeline._theme_analysis_from_contents(
            SimpleNamespace(name="洛克王国世界", priority_weight=3),
            [
                content("洛克孵蛋配方合集，持续更新", "整理目前已知的孵蛋配方和蛋组", 456, 134, 15600, "a"),
                content("洛克王国世界孵蛋配方表有吗？", "不同精灵配种出来是什么，求配方表", 234, 67, 8900, "b"),
                content("求分享洛克孵蛋计算工具", "有没有孵蛋模拟器或者计算工具", 45, 12, 2100, "c"),
            ],
            {},
        )

        mechanism = next(a for a in analyses if a["tool_type_suggestion"] == "机制计算器")
        self.assertIn("孵蛋", mechanism["tool_title"])
        self.assertGreaterEqual(mechanism["potential_score"], 80)

    def test_open_world_collection_terms_create_map_demands(self):
        examples = [
            ("原神", "原神5.6全地图神瞳宝箱收集路线", "新版地图资源全收集，采集路线和点位都整理好了"),
            ("崩坏：星穹铁道", "眠鸥之星宝箱和折纸小鸟位置", "地图工具没法对应账号，只能一处一处跑图确认"),
        ]

        for game_name, title, body in examples:
            with self.subTest(game_name=game_name):
                analyses = self.pipeline._theme_analysis_from_contents(
                    SimpleNamespace(name=game_name, priority_weight=1),
                    [
                        content(title, body, 140, 55, 9000, "a"),
                        content(f"{game_name}隐藏宝箱跑图路线", "收集物位置太散，想要地图标点", 90, 36, 6000, "b"),
                    ],
                    {},
                )

                self.assertIn("交互地图", {a["tool_type_suggestion"] for a in analyses})

    def test_fps_and_moba_setup_terms_create_loadout_demands(self):
        examples = [
            ("CF手游体验服", "CF手游体验服灵敏度压枪参数", "准星、陀螺仪和枪械配置求推荐"),
            ("王者荣耀体验服", "王者荣耀体验服新英雄出装铭文", "英雄强度、装备和铭文怎么搭配"),
        ]

        for game_name, title, body in examples:
            with self.subTest(game_name=game_name):
                analyses = self.pipeline._theme_analysis_from_contents(
                    SimpleNamespace(name=game_name, priority_weight=1),
                    [
                        content(title, body, 120, 48, 8000, "a"),
                        content(f"{game_name}配置推荐工具", "想直接查一套能用的配置方案", 80, 30, 5000, "b"),
                    ],
                    {},
                )

                self.assertIn("配装/战备工具", {a["tool_type_suggestion"] for a in analyses})

    def test_survival_and_economy_terms_create_specific_demands(self):
        examples = [
            ("失控进化", "失控进化建家抄家蓝图攻略", "资源点、配方和组件怎么规划最省材料", "攻略辅助"),
            ("暗区突围体验服", "暗区突围体验服物价行情查询", "装备、子弹和钥匙价格波动太快，想看行情表", "数据库"),
        ]

        for game_name, title, body, expected_tool_type in examples:
            with self.subTest(game_name=game_name):
                analyses = self.pipeline._theme_analysis_from_contents(
                    SimpleNamespace(name=game_name, priority_weight=1),
                    [
                        content(title, body, 130, 52, 8500, "a"),
                        content(f"{game_name}资料整理", "信息分散，求一个工具集中查询", 78, 26, 4800, "b"),
                    ],
                    {},
                )

                self.assertIn(expected_tool_type, {a["tool_type_suggestion"] for a in analyses})

    def test_posts_that_only_mention_other_games_do_not_trigger_current_game_demand(self):
        analyses = self.pipeline._theme_analysis_from_contents(
            SimpleNamespace(name="鸣潮", priority_weight=1),
            [
                content("洛克王国世界跑图辅助工具", "洛克王国地图资源查询和蛋组查询器", 200, 80, 12000, "a"),
                content("三角洲行动卡战备怎么搞", "武器配件和战备阈值看不懂", 160, 70, 10000, "b"),
            ],
            {},
        )

        self.assertEqual([], analyses)

    def test_domain_specific_theme_replaces_overlapping_generic_theme(self):
        analyses = self.pipeline._theme_analysis_from_contents(
            SimpleNamespace(name="原神", priority_weight=1),
            [
                content("原神5.6全地图神瞳宝箱收集路线", "新版地图资源全收集，采集路线和点位都整理好了", 160, 80, 12000, "a"),
                content("原神隐藏宝箱跑图路线", "收集物位置太散，想要地图标点", 100, 50, 8000, "b"),
            ],
            {},
        )

        map_demands = [a for a in analyses if a["tool_type_suggestion"] == "交互地图"]
        self.assertEqual(1, len(map_demands))
        self.assertEqual("genshin_map", map_demands[0]["theme_key"])

    def test_experience_server_requires_current_game_evidence(self):
        analyses = self.pipeline._theme_analysis_from_contents(
            SimpleNamespace(name="CF手游体验服", priority_weight=1),
            [
                content("CF手游体验服灵敏度压枪参数", "准星、陀螺仪和枪械配置求推荐", 120, 48, 8000, "cf"),
                content("下载和平精英体验服", "和平精英体验服下载教程", 180, 60, 10000, "peace"),
                content("三角洲体验服免费下载安装教程", "三角洲体验服下载资格入口", 160, 55, 9000, "delta"),
                content("麻瓜图书管理员帮助工具", "书架位置和地图工具", 130, 40, 7000, "generic"),
            ],
            {},
        )

        evidence_ids = {post_id for item in analyses for post_id in item["evidence_post_ids"]}
        self.assertIn("cf", evidence_ids)
        self.assertNotIn("peace", evidence_ids)
        self.assertNotIn("delta", evidence_ids)
        self.assertNotIn("generic", evidence_ids)

    def test_experience_server_rejects_base_game_posts_without_experience_marker(self):
        analyses = self.pipeline._theme_analysis_from_contents(
            SimpleNamespace(name="三角洲行动体验服", priority_weight=3),
            [
                content("三角洲行动体验服新地图核电站点位整理", "资源点和路线都变了", 220, 130, 16000, "exp"),
                content("三角洲行动倒子弹路线攻略", "大坝跑刀摸金路线", 180, 80, 12000, "base"),
                content("洛克王国地图资源查询器", "洛克王国世界跑图工具", 150, 70, 10000, "locke"),
                content("真萌新推荐", "工具多到你无法想象", 120, 45, 7000, "generic"),
            ],
            {},
        )

        evidence_ids = {post_id for item in analyses for post_id in item["evidence_post_ids"]}
        self.assertIn("exp", evidence_ids)
        self.assertNotIn("base", evidence_ids)
        self.assertNotIn("locke", evidence_ids)
        self.assertNotIn("generic", evidence_ids)

    def test_fallback_evidence_ids_are_filtered_by_experience_server_game(self):
        from app.services.llm_pipeline import _evidence_ids_for_analysis

        evidence_ids = _evidence_ids_for_analysis(
            SimpleNamespace(name="三角洲行动体验服"),
            {"tool_title": "三角洲行动体验服交互地图（待确认）"},
            [
                content("三角洲行动体验服新地图核电站点位整理", "资源点和路线都变了", content_id="exp"),
                content("三角洲行动倒子弹路线攻略", "普通服跑刀摸金路线", content_id="base"),
                content("洛克王国地图资源查询器", "洛克王国世界跑图工具", content_id="locke"),
                content("真萌新推荐", "工具多到你无法想象", content_id="generic"),
            ],
        )

        self.assertEqual(["exp"], evidence_ids)


if __name__ == "__main__":
    unittest.main()
