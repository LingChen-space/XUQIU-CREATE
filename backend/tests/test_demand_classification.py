"""需求类型分类测试。"""

import unittest

from app.schemas.demand import (
    build_experience_server_insight,
    classify_demand_category,
    extract_experience_focus,
)


class DemandClassificationTest(unittest.TestCase):
    def test_experience_server_demand_is_not_tool_demand(self):
        category = classify_demand_category(
            game_name="火影忍者体验服",
            title="火影忍者手游体验服资格招募开启提醒",
            tool_type="资格/福利聚合",
            description="汇总申请入口、抢码时间和报名条件",
            reasoning="体验服资格限量开放，玩家集中询问如何申请。",
        )

        self.assertEqual(category, "experience_server")

    def test_experience_focus_extracts_leaks_updates_and_recruitment(self):
        focus = extract_experience_focus(
            "体验服版本更新爆料，新忍者改动曝光，测试资格招募即将开启。"
        )

        self.assertEqual(focus, ["爆料内容", "更新内容", "资格招募"])

    def test_regular_calculator_stays_tool_demand(self):
        category = classify_demand_category(
            game_name="三角洲行动",
            title="三角洲行动战备值计算器",
            tool_type="配装/战备工具",
            description="计算武器配件战备阈值",
            reasoning="玩家反复提问配装方案。",
        )

        self.assertEqual(category, "tool")

    def test_experience_server_insight_splits_updates_leaks_and_recruitment(self):
        insight = build_experience_server_insight(
            "体验服版本更新：新增地图和武器平衡调整。",
            "爆料称新角色将在测试服登场，资格招募已开启报名。",
        )

        self.assertIn("新增地图", insight.update_content)
        self.assertIn("新角色", insight.leak_content)
        self.assertIn("资格招募已开启", insight.recruitment_status)
        self.assertTrue(insight.recruitment_open)

    def test_experience_server_insight_reports_missing_recruitment(self):
        insight = build_experience_server_insight("体验服更新内容曝光，新玩法即将测试。")

        self.assertEqual(insight.recruitment_status, "未发现资格招募开启消息")
        self.assertFalse(insight.recruitment_open)


if __name__ == "__main__":
    unittest.main()
