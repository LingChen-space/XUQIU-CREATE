"""统一需求词库与固定近义词匹配测试。"""

import unittest

from app.services.demand_keyword_rules import (
    canonical_game_name,
    load_keyword_catalog,
    match_demand_keywords,
    rules_for_game,
)


class DemandKeywordRulesTest(unittest.TestCase):
    def test_catalog_contains_excel_standard_counts(self):
        catalog = load_keyword_catalog()
        game_term_count = sum(len(items) for items in catalog["games"].values())

        self.assertEqual(len(catalog["games"]), 7)
        self.assertEqual(game_term_count, 240)
        self.assertEqual(len(catalog["generic"]), 39)

    def test_priority_counts_match_excel(self):
        catalog = load_keyword_catalog()
        self.assertEqual(
            {
                game: {
                    level: sum(rule.priority == level for rule in rules)
                    for level in ("level_1", "level_2")
                }
                for game, rules in catalog["games"].items()
            },
            {
                "三角洲行动": {"level_1": 34, "level_2": 14},
                "失控进化": {"level_1": 16, "level_2": 12},
                "异环": {"level_1": 21, "level_2": 14},
                "洛克王国世界": {"level_1": 29, "level_2": 12},
                "原神": {"level_1": 19, "level_2": 13},
                "鸣潮": {"level_1": 16, "level_2": 10},
                "崩坏：星穹铁道": {"level_1": 19, "level_2": 11},
            },
        )

    def test_priority_game_only_uses_own_and_generic_rules(self):
        terms = {rule.canonical_term for rule in rules_for_game("原神")}

        self.assertIn("圣遗物评分器", terms)
        self.assertIn("战绩查询", terms)
        self.assertNotIn("声骸评分器", terms)
        self.assertNotIn("卡战备", terms)

    def test_regular_game_only_uses_generic_rules(self):
        terms = {rule.canonical_term for rule in rules_for_game("测试新游戏")}

        self.assertEqual(len(terms), 39)
        self.assertIn("战绩查询", terms)
        self.assertNotIn("圣遗物评分器", terms)

    def test_fixed_aliases_normalize_to_canonical_terms(self):
        delta_matches = match_demand_keywords(
            "三角洲行动",
            "今天3×3怎么做？密码门今日密码也更新了",
        )
        genshin_matches = match_demand_keywords(
            "原神",
            "这个圣遗物打分到底多少，四星平民怎么配队",
        )

        self.assertEqual(
            {item.canonical_term for item in delta_matches},
            {"3X3任务", "每日密码"},
        )
        self.assertIn(
            "圣遗物评分器",
            {item.canonical_term for item in genshin_matches},
        )
        self.assertIn(
            "平民配队",
            {item.canonical_term for item in genshin_matches},
        )

    def test_game_alias_resolves_to_standard_name(self):
        self.assertEqual(canonical_game_name("星穹铁道"), "崩坏：星穹铁道")
        self.assertEqual(canonical_game_name("三角洲行动体验服"), "三角洲行动")
        self.assertIsNone(canonical_game_name("不存在的游戏"))

    def test_longer_overlapping_standard_term_wins(self):
        matches = match_demand_keywords("三角洲行动", "卡战备技巧讨论")

        self.assertEqual(
            [item.canonical_term for item in matches],
            ["卡战备技巧"],
        )


if __name__ == "__main__":
    unittest.main()
