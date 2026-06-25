"""标准需求词驱动的探索采集关键词测试。"""

import unittest

from app.services.data_adapter import collection_keywords_for_game


class KeywordCollectionTest(unittest.TestCase):
    def test_priority_game_queries_include_game_name_and_standard_terms(self):
        queries = collection_keywords_for_game("原神", "priority", slot=0)

        self.assertEqual(queries[0], "原神")
        self.assertIn("原神 版本更新内容", queries)
        self.assertTrue(all(
            query == "原神" or query.startswith("原神 ")
            for query in queries
        ))
        self.assertFalse(any("声骸评分器" in query for query in queries))

    def test_priority_game_rotates_level_one_and_level_two_terms(self):
        first = set(collection_keywords_for_game("三角洲行动", "priority", slot=0))
        second = set(collection_keywords_for_game("三角洲行动", "priority", slot=1))

        self.assertNotEqual(first, second)
        self.assertTrue(any("卡战备" in query or "熟图工具" in query for query in first | second))
        self.assertTrue(any("攻略" in query or "技巧" in query or "打法" in query for query in first | second))

    def test_regular_game_only_uses_generic_standard_terms(self):
        queries = collection_keywords_for_game("测试新游戏", "regular", slot=0)

        self.assertEqual(queries[0], "测试新游戏")
        self.assertIn("测试新游戏 战绩查询", queries)
        self.assertIn("测试新游戏 版本更新内容", queries)
        self.assertFalse(any("圣遗物" in query for query in queries))

    def test_queries_never_use_unscoped_generic_short_terms(self):
        queries = collection_keywords_for_game("鸣潮", "priority", slot=3)

        self.assertNotIn("战绩查询", queries)
        self.assertNotIn("版本更新内容", queries)
        self.assertTrue(all("鸣潮" in query for query in queries))


if __name__ == "__main__":
    unittest.main()
