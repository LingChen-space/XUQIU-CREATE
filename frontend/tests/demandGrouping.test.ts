import {
  getDemandBranchTitle,
  getDemandDisplayTitle,
  groupDemandsByGame,
} from "../src/utils/demandGrouping"
import type { DemandCard } from "../src/types"

const baseDemand: DemandCard = {
  id: "demand-1",
  game_id: "delta-force",
  game_name: "三角洲行动",
  game_genre: "射击",
  tool_type: "攻略辅助",
  title: "三角洲行动 · 卡战备怎么搞",
  description: "",
  potential_score: 76,
  tool_feasibility: 4,
  status: "待评估",
  signals: {
    repeat_question: 0,
    info_scatter: 0,
    grassroots_tool: 0,
    scarcity: 0,
    mechanism_complexity: 0,
    content_heat: 0,
    external_platform_tool: 0,
  },
  llm_reasoning: "",
  demand_category: "tool",
  experience_focus: [],
  experience_insight: null,
  demand_date: "2026-06-19",
  demand_level: "A级",
  created_at: "2026-06-19T00:00:00",
}

function demand(overrides: Partial<DemandCard>): DemandCard {
  return { ...baseDemand, ...overrides }
}

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message)
}

const groups = groupDemandsByGame([
  demand({ id: "demand-1", title: "三角洲行动 · 卡战备怎么搞", potential_score: 76 }),
  demand({ id: "demand-2", title: "三角洲行动 地图资源点查询", tool_type: "交互地图", potential_score: 91 }),
  demand({
    id: "demand-3",
    game_id: "cfm",
    game_name: "CF手游",
    game_genre: "射击",
    title: "CF手游 · 体验服资格",
    demand_category: "experience_server",
    experience_focus: ["资格招募"],
    potential_score: 64,
  }),
])

assert(groups.length === 2, "同一游戏的多个需求应该聚合到一个游戏组")
assert(groups[0].gameName === "三角洲行动", "最高分游戏组应该排在前面")
assert(groups[0].count === 2, "游戏组应该统计该游戏下的需求分支数")
assert(groups[0].topScore === 91, "游戏组最高分应该来自组内最高分需求")
assert(groups[0].demands[0].id === "demand-2", "组内需求分支应该按潜力分降序")
assert(getDemandBranchTitle(groups[0].demands[0]) === "地图资源点查询", "分支标题应该去掉重复游戏名前缀")
assert(getDemandBranchTitle(groups[0].demands[1]) === "卡战备怎么搞", "分支标题应该去掉游戏名分隔符")
assert(getDemandDisplayTitle(groups[1].demands[0]) === "CF手游 · 资格招募", "体验服需求标题应该突出体验服焦点")

console.log("demandGrouping tests passed")
