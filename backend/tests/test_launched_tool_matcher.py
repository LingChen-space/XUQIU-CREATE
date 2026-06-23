"""快爆已上线工具匹配测试。"""

import unittest

from app.services.launched_tool_matcher import find_launched_tool_matches


class LaunchedToolMatcherTest(unittest.TestCase):
    def test_matches_existing_kuaibao_tool_by_game_and_need_terms(self):
        matches = find_launched_tool_matches(
            game_name="洛克王国世界",
            tool_type="机制计算器",
            title="洛克王国世界孵蛋配方计算器",
            description="聚合孵蛋配方、蛋组和进化信息",
            launched_tools=[
                {"id": "1", "name": "洛克王国：世界孵蛋模拟器"},
                {"id": "2", "name": "阴阳师悬赏封印妖怪查询器"},
            ],
        )

        self.assertEqual(matches, ["洛克王国：世界孵蛋模拟器"])

    def test_does_not_match_other_game_tool_with_same_generic_type(self):
        matches = find_launched_tool_matches(
            game_name="三角洲行动",
            tool_type="交互地图",
            title="三角洲行动核电站地图/点位工具",
            description="聚合核电站资源点和撤离路线",
            launched_tools=[
                {"id": "1", "name": "原神地图资源查询器"},
                {"id": "2", "name": "阴阳师悬赏封印妖怪查询器"},
            ],
        )

        self.assertEqual(matches, [])

    def test_exact_game_tool_name_can_match_experience_server_need(self):
        matches = find_launched_tool_matches(
            game_name="王者荣耀体验服",
            tool_type="资格/福利聚合",
            title="王者荣耀体验服资格/福利聚合",
            description="体验服资格、招募和开放时间",
            launched_tools=[
                {"id": "43", "name": "王者荣耀体验服"},
            ],
        )

        self.assertEqual(matches, ["王者荣耀体验服"])

    def test_game_name_overlap_alone_does_not_match_different_tool_need(self):
        matches = find_launched_tool_matches(
            game_name="失控进化",
            tool_type="攻略辅助",
            title="失控进化攻略辅助工具",
            description="整理生存建造攻略",
            launched_tools=[
                {"id": "1", "name": "失控进化计算器合辑工具"},
                {"id": "2", "name": "失控进化组队交友大厅"},
            ],
        )

        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
