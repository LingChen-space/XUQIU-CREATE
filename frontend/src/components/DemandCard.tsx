import { BadgeCheck, BellRing, Clock, Gauge, Megaphone } from "lucide-react"
import type { DemandCard } from "../types"
import { getDemandDisplayTitle } from "../utils/demandGrouping"
import { getExperienceInsightRows } from "../utils/experienceInsight"

const SIGNAL_LABELS: Record<string, string> = {
  repeat_question: "重复提问",
  info_scatter: "信息分散",
  grassroots_tool: "民间工具",
  scarcity: "资格稀缺",
  mechanism_complexity: "机制复杂",
  content_heat: "内容热度",
  external_platform_tool: "外部上线",
}

const BAR_COLORS = ["c1", "c2", "c3", "c4", "c5", "c6"]

const LEVEL_CONFIG: Record<string, { bg: string; color: string; label: string }> = {
  "S级": { bg: "#fef2f2", color: "#b91c1c", label: "S" },
  "A级": { bg: "#fffbeb", color: "#92400e", label: "A" },
  "B级": { bg: "#eff6ff", color: "#2563eb", label: "B" },
  "C级": { bg: "#f3f4f6", color: "#6b7280", label: "C" },
}

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  "待评估": { bg: "#f3f4f6", color: "#4b5563" },
  "已采纳": { bg: "#ecfdf5", color: "#059669" },
  "开发中": { bg: "#eff6ff", color: "#2563eb" },
  "已上线": { bg: "#f5f3ff", color: "#7c3aed" },
  "已驳回": { bg: "#fef2f2", color: "#dc2626" },
}

const CATEGORY_STYLE: Record<string, { label: string; bg: string; color: string }> = {
  tool: { label: "工具需求", bg: "var(--primary-light)", color: "var(--primary)" },
  experience_server: { label: "体验服需求", bg: "#ecfdf5", color: "#059669" },
}

const EXPERIENCE_ROW_ICONS = {
  "更新/爆料内容": Megaphone,
  资格招募: BellRing,
  当前节点: Clock,
}

function ExperienceInsightList({ demand }: { demand: DemandCard }) {
  const rows = getExperienceInsightRows(demand)

  return (
    <div className="experience-insight-list">
      {rows.map(({ label, value, tone, bg }) => {
        const Icon = EXPERIENCE_ROW_ICONS[label]
        return (
          <div key={label} className="experience-insight-row">
            <span className="experience-insight-icon" style={{ background: bg, color: tone }}>
              <Icon size={13} />
            </span>
            <div className="experience-insight-copy">
              <span className="experience-insight-label">{label}</span>
              <span className="experience-insight-text">{value}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function DemandCardView({ demand, onClick, showFullSignals = true }: { demand: DemandCard; onClick: () => void; showFullSignals?: boolean }) {
  const score = Math.round(demand.potential_score)
  const level = demand.demand_level || (score >= 80 ? "S级" : score >= 60 ? "A级" : "B级")
  const lvlCfg = LEVEL_CONFIG[level] || LEVEL_CONFIG["C级"]
  const stsCfg = STATUS_STYLE[demand.status] || STATUS_STYLE["待评估"]
  const category = CATEGORY_STYLE[demand.demand_category || "tool"] || CATEGORY_STYLE.tool
  const displayTitle = getDemandDisplayTitle(demand)
  const isExperienceServer = demand.demand_category === "experience_server"
  const launchedTools = demand.launched_tool_matches || []

  const signalEntries = Object.entries(demand.signals).filter(
    ([k]) => k in SIGNAL_LABELS
  ) as [string, number][]

  const demandDate = String(demand.demand_date).slice(0, 10)

  return (
    <div className="demand-card" onClick={onClick}>
      <div className="card-top">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="card-meta">
            <span className="chip game">{demand.game_name}</span>
            <span className="chip tool-type" style={{ background: category.bg, color: category.color }}>{category.label}</span>
            {!isExperienceServer && <span className="chip tool-type">{demand.tool_type}</span>}
          </div>
          <div className="card-title">{displayTitle}</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, flexShrink: 0, minWidth: 60 }}>
          <div
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              width: 42, height: 42, borderRadius: 8,
              background: lvlCfg.bg, color: lvlCfg.color,
              fontSize: 22, fontWeight: 800,
              border: `2px solid ${lvlCfg.color}20`,
            }}
          >
            {lvlCfg.label}
          </div>
          <span style={{ fontSize: 10, fontWeight: 600, color: lvlCfg.color, letterSpacing: "0.03em" }}>
            {level}
          </span>
        </div>
      </div>

      {isExperienceServer && demand.experience_focus?.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {demand.experience_focus.map((label) => (
            <span key={label} className="chip" style={{ fontSize: 11, background: "#f0fdf4", color: "#047857" }}>
              {label}
            </span>
          ))}
        </div>
      )}

      {isExperienceServer && <ExperienceInsightList demand={demand} />}

      {launchedTools.length > 0 && (
        <div style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 8,
          padding: "9px 11px",
          borderRadius: 8,
          background: "#fff7ed",
          color: "#9a3412",
          border: "1px solid #fed7aa",
          fontSize: 12,
          fontWeight: 600,
          lineHeight: 1.45,
        }}>
          <BadgeCheck size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            快爆站内已上线：{launchedTools.slice(0, 2).join("、")}
            {launchedTools.length > 2 ? ` 等${launchedTools.length}个工具` : ""}，建议评估优化更新。
          </span>
        </div>
      )}

      {/* Key info row: time + progress + feasibility */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "10px 12px", background: "#f9fafb", borderRadius: 8,
        flexWrap: "wrap"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "var(--text-secondary)" }}>
          <Clock size={13} color="var(--text-muted)" />
          <span style={{ fontWeight: 500 }}>{demandDate}</span>
        </div>
        <div style={{ width: 1, height: 16, background: "#e5e7eb" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12 }}>
          <Gauge size={13} color="var(--text-muted)" />
          <span style={{ fontWeight: 700, color: score >= 80 ? "var(--red)" : score >= 60 ? "var(--amber)" : "var(--text)" }}>
            {score}分
          </span>
        </div>
        <div style={{ width: 1, height: 16, background: "#e5e7eb" }} />
        <span style={{
          display: "inline-block",
          padding: "3px 10px",
          borderRadius: 5,
          fontSize: 11,
          fontWeight: 600,
          background: stsCfg.bg,
          color: stsCfg.color,
          whiteSpace: "nowrap"
        }}>
          {demand.status}
        </span>
      </div>

      {/* Signal mini bars */}
      {showFullSignals && !isExperienceServer && (
        <div className="signal-minis">
          {signalEntries.map(([key, val], i) => (
            <div key={key} className="signal-mini">
              <span className="sm-label">{SIGNAL_LABELS[key]}</span>
              <div className="sm-bar">
                <div
                  className={`sm-bar-fill ${BAR_COLORS[i % BAR_COLORS.length]}`}
                  style={{ width: `${Math.min(val, 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {!isExperienceServer && (
        demand.llm_reasoning ? (
          <div className="card-reason">{demand.llm_reasoning}</div>
        ) : (
          <div className="card-reason" style={{ color: "var(--text-muted)", fontStyle: "italic" }}>
            等待 LLM 分析...
          </div>
        )
      )}
    </div>
  )
}
