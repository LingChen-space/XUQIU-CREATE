import { getExperienceInsight, getExperienceInsightRows } from "../src/utils/experienceInsight"
import type { DemandCard } from "../src/types"

const demand: DemandCard = {
  id: "demand-1",
  game_id: "delta-exp",
  game_name: "三角洲行动体验服",
  game_genre: "FPS",
  tool_type: "资格/福利聚合",
  title: "三角洲行动体验服 · 核电站爆料",
  description: "",
  potential_score: 90,
  tool_feasibility: 3,
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
  demand_category: "experience_server",
  experience_focus: ["爆料内容", "更新内容"],
  experience_insight: {
    update_content: "版本更新：新增核电站地图和撤离路线",
    leak_content: "爆料称核电站资源点位置曝光",
    recruitment_status: "资格招募已开启报名",
    recruitment_time: "6月20日10:00",
    current_stage: "报名中",
    recruitment_open: true,
  },
  demand_date: "2026-06-22",
  demand_level: "S级",
  created_at: "2026-06-22T00:00:00",
}

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message)
}

const insight = getExperienceInsight(demand)
assert(insight.recruitment_time === "6月20日10:00", "应该保留资格招募时间")
assert(insight.current_stage === "报名中", "应该保留当前体验服节点")

const rows = getExperienceInsightRows(demand)
assert(rows.length === 3, "体验服摘要应该展示更新/爆料、资格、当前节点三项")
assert(rows.some((row) => row.label === "更新/爆料内容" && row.value.includes("核电站") && row.value.includes("资源点")), "应该合并展示更新和爆料内容")
assert(rows.some((row) => row.label === "资格招募" && row.value.includes("6月20日10:00")), "资格招募应该带时间")
assert(rows.some((row) => row.label === "当前节点" && row.value === "报名中"), "应该展示当前节点")

console.log("experienceInsight tests passed")
