import type { DemandCard, DemandDetail, ExperienceServerInsight } from "../types"

type ExperienceDemand = DemandCard | DemandDetail

export interface ExperienceInsightRow {
  label: "更新/爆料内容" | "资格招募" | "当前节点"
  value: string
  tone: string
  bg: string
}

export function getExperienceInsight(demand: ExperienceDemand): ExperienceServerInsight {
  return demand.experience_insight || {
    update_content: "未发现更新内容",
    leak_content: "未发现爆料内容",
    recruitment_status: demand.experience_focus?.includes("资格招募") ? "发现资格招募相关消息" : "未发现资格招募开启消息",
    recruitment_time: "未发现明确时间",
    current_stage: demand.experience_focus?.includes("资格招募") ? "资格待确认" : "观察中",
    recruitment_open: demand.experience_focus?.includes("资格招募") || false,
  }
}

export function getExperienceInsightRows(demand: ExperienceDemand): ExperienceInsightRow[] {
  const insight = getExperienceInsight(demand)
  const contentParts = [insight.update_content, insight.leak_content].filter(
    (value) => value && value !== "未发现更新内容" && value !== "未发现爆料内容"
  )
  const contentValue = contentParts.length > 0 ? contentParts.join(" · ") : "未发现更新/爆料内容"
  const recruitmentParts = [insight.recruitment_status]
  if (insight.recruitment_time && insight.recruitment_time !== "未发现明确时间") {
    recruitmentParts.push(insight.recruitment_time)
  }

  return [
    { label: "更新/爆料内容", value: contentValue, tone: "#2563eb", bg: "var(--primary-light)" },
    {
      label: "资格招募",
      value: recruitmentParts.join(" · "),
      tone: insight.recruitment_open ? "#059669" : "#6b7280",
      bg: insight.recruitment_open ? "var(--green-light)" : "#f3f4f6",
    },
    { label: "当前节点", value: insight.current_stage, tone: "#0f766e", bg: "#ccfbf1" },
  ]
}

export function getCompactExperienceInsight(demand: ExperienceDemand): string[] {
  const missingPrefixes = ["未发现更新/爆料内容", "未发现资格招募"]
  return getExperienceInsightRows(demand)
    .filter((row) => !missingPrefixes.some((prefix) => row.value.startsWith(prefix)))
    .map((row) => `${row.label}：${row.value}`)
}
