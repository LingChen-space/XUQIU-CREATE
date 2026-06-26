import { useEffect, useState, useMemo } from "react"
import { Search, Loader2, SlidersHorizontal, ArrowUpDown, Megaphone } from "lucide-react"
import { api } from "../api/client"
import type { DemandCard } from "../types"
import {
  DEMAND_CATEGORY_LABELS,
  getDemandBranchTitle,
  getDemandDisplayTitle,
  groupDemandsByGame,
} from "../utils/demandGrouping"
import { getCompactExperienceInsight } from "../utils/experienceInsight"

const TOOL_TYPES = ["全部", "配装/战备工具", "交互地图", "抽卡/概率分析", "资格/福利聚合", "机制计算器", "排行榜/对战数据", "剧情/收集进度", "攻略辅助", "模拟器", "数据库", "其他"]
const STATUSES = ["全部", "待评估", "已采纳", "开发中", "已上线", "已驳回"]
const CATEGORIES = [
  { value: "全部", label: "全部" },
  { value: "tool", label: "工具需求" },
  { value: "experience_server", label: "体验服需求" },
]

interface Props { onSelect: (d: DemandCard) => void; onCountChange: (n: number) => void }

export default function DemandManagement({ onSelect, onCountChange }: Props) {
  const [demands, setDemands] = useState<DemandCard[]>([])
  const [loading, setLoading] = useState(true)
  const [toolTypeFilter, setToolTypeFilter] = useState("全部")
  const [statusFilter, setStatusFilter] = useState("全部")
  const [categoryFilter, setCategoryFilter] = useState("全部")
  const [search, setSearch] = useState("")
  const [sortField, setSortField] = useState<"potential_score" | "demand_date">("potential_score")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc")

  const fetchDemands = async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = { limit: "200" }
      if (toolTypeFilter !== "全部") params.tool_type = toolTypeFilter
      if (statusFilter !== "全部") params.status = statusFilter
      const data = await api.getDemands(params)
      setDemands(data)
      onCountChange(data.length)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchDemands() }, [toolTypeFilter, statusFilter])

  const updateStatus = async (id: string, status: string) => {
    await api.updateDemand(id, { status })
    setDemands((prev) => prev.map((d) => (d.id === id ? { ...d, status } : d)))
  }

  const toggleSort = (field: "potential_score" | "demand_date") => {
    if (sortField === field) {
      setSortDir(prev => prev === "desc" ? "asc" : "desc")
    } else {
      setSortField(field)
      setSortDir("desc")
    }
  }

  const filtered = useMemo(() => {
    let result = demands.filter((d) => {
      const title = getDemandDisplayTitle(d)
      if (search && !title.includes(search) && !d.title.includes(search) && !d.game_name.includes(search)) return false
      if (categoryFilter !== "全部" && d.demand_category !== categoryFilter) return false
      return true
    })
    result.sort((a, b) => {
      const va = sortField === "potential_score" ? a.potential_score : new Date(a.demand_date).getTime()
      const vb = sortField === "potential_score" ? b.potential_score : new Date(b.demand_date).getTime()
      return sortDir === "desc" ? vb - va : va - vb
    })
    return result
  }, [demands, search, categoryFilter, sortField, sortDir])

  const groupedDemands = useMemo(() => groupDemandsByGame(filtered), [filtered])

  const statusColor = (s: string): { bg: string; color: string } => {
    const map: Record<string, { bg: string; color: string }> = {
      "待评估": { bg: "#f3f4f6", color: "var(--text-secondary)" },
      "已采纳": { bg: "var(--green-light)", color: "var(--green)" },
      "开发中": { bg: "var(--primary-light)", color: "var(--primary)" },
      "已上线": { bg: "var(--purple-light)", color: "var(--purple)" },
      "已驳回": { bg: "var(--red-light)", color: "var(--red)" },
    }
    return map[s] || { bg: "#f3f4f6", color: "var(--text-muted)" }
  }

  return (
    <div>
      {/* Toolbar */}
      <div style={{
        display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12,
        marginBottom: 20, padding: "16px 20px", background: "var(--surface)",
        border: "1px solid var(--border)", borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)"
      }}>
        <div style={{ position: "relative", flex: "0 0 auto" }}>
          <Search size={16} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
          <input type="text" placeholder="搜索需求标题或游戏名..." value={search} onChange={(e) => setSearch(e.target.value)}
            className="form-input" style={{ paddingLeft: 36, width: 260 }} />
        </div>

        <div style={{ width: 1, height: 24, background: "var(--border)" }} />

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <SlidersHorizontal size={14} color="var(--text-muted)" />
          <span style={{ fontSize: 12, color: "var(--text-muted)", marginRight: 2 }}>类型</span>
          <select value={toolTypeFilter} onChange={(e) => setToolTypeFilter(e.target.value)} className="form-input" style={{ fontSize: 12, padding: "6px 28px 6px 10px" }}>
            {TOOL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>状态</span>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="form-input" style={{ fontSize: 12, padding: "6px 28px 6px 10px" }}>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>分类</span>
          <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="form-input" style={{ fontSize: 12, padding: "6px 28px 6px 10px" }}>
            {CATEGORIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>排序</span>
          <button
            type="button"
            className={`sort-pill ${sortField === "potential_score" ? "active" : ""}`}
            onClick={() => toggleSort("potential_score")}
          >
            潜力分 <ArrowUpDown size={12} />
          </button>
          <button
            type="button"
            className={`sort-pill ${sortField === "demand_date" ? "active" : ""}`}
            onClick={() => toggleSort("demand_date")}
          >
            日期 <ArrowUpDown size={12} />
          </button>
        </div>

        <span style={{ fontSize: 12, color: "var(--text-muted)", marginLeft: "auto" }}>
          共 {groupedDemands.length} 款游戏，{filtered.length} 条需求
        </span>
      </div>

      {/* Demand groups */}
      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
          <Loader2 className="spinner" size={24} color="var(--primary)" />
        </div>
      ) : filtered.length > 0 ? (
        <div className="demand-game-groups">
          {groupedDemands.map((group) => {
            const isExperienceGroup = group.demands.some((d) => d.demand_category === "experience_server")

            return (
              <section key={group.gameId} className="demand-game-group">
                <div className="demand-game-group-header">
                  <div className="demand-game-group-title">
                    <span>{group.gameName}</span>
                    <span className="chip game">{group.gameGenre}</span>
                  </div>
                  <div className="demand-game-group-meta">
                    {isExperienceGroup ? (
                      <span>{group.count} 条体验服更新 · 仅展示</span>
                    ) : (
                      <>
                        <span>{group.count} 个需求分支</span>
                        <strong>{group.topScore} 分</strong>
                      </>
                    )}
                  </div>
                </div>

                {isExperienceGroup ? (
                  <div className="demand-branch-list" style={{
                    borderLeft: "3px solid #10b981",
                    background: "linear-gradient(180deg, #f0fdf4 0%, transparent 65%)",
                    padding: "12px 14px", borderRadius: 8,
                  }}>
                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
                      体验服版本/爆料 · 仅合并展示，不参与评估
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                      {group.demands.map((d) => {
                        const term = (d.title.split("版本/爆料：")[1] || d.title).trim()
                        return (
                          <span key={d.id} style={{
                            display: "inline-flex", alignItems: "center", gap: 6,
                            padding: "6px 12px", borderRadius: 16,
                            background: "#ecfdf5", color: "#047857",
                            border: "1px solid #bbf7d0", fontSize: 13, fontWeight: 500,
                          }}>
                            <Megaphone size={13} />{term}
                          </span>
                        )
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="demand-branch-list">
                    {group.demands.map((d) => {
                    const score = Math.round(d.potential_score)
                    const categoryTone = d.demand_category === "experience_server"
                      ? { background: "#ecfdf5", color: "#047857" }
                      : { background: "var(--primary-light)", color: "var(--primary)" }

                    return (
                      <div
                        key={d.id}
                        className="demand-branch-row"
                        role="button"
                        tabIndex={0}
                        onClick={() => onSelect(d)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") onSelect(d)
                        }}
                      >
                        <div className="demand-branch-main">
                          <div className="demand-branch-title">{getDemandBranchTitle(d)}</div>
                          <div className="demand-branch-meta">
                            <span className="chip" style={categoryTone}>
                              {DEMAND_CATEGORY_LABELS[d.demand_category]}
                            </span>
                            <span className="chip">
                              {d.demand_category === "experience_server"
                                ? d.experience_focus?.join(" / ") || "体验服内容"
                                : d.tool_type}
                            </span>
                            {(d.launched_tool_matches?.length || 0) > 0 && (
                              <span className="chip" style={{ background: "#fff7ed", color: "#9a3412" }}>
                                快爆已上线：{d.launched_tool_matches[0]}
                              </span>
                            )}
                            {d.demand_category === "experience_server" ? (
                              <div className="experience-branch-summary">
                                {getCompactExperienceInsight(d).map((item) => (
                                  <span key={item}>{item}</span>
                                ))}
                              </div>
                            ) : (
                              d.llm_reasoning && <span className="demand-branch-reason">{d.llm_reasoning}</span>
                            )}
                          </div>
                        </div>

                        <div className="demand-branch-stats">
                          <span className={`demand-branch-score ${score >= 80 ? "hot" : score >= 60 ? "warm" : ""}`}>
                            {score}
                          </span>
                          <span>{d.tool_feasibility}/5 可行</span>
                          <span>{String(d.demand_date).slice(0, 10)}</span>
                        </div>

                        <div className="demand-branch-status" onClick={(e) => e.stopPropagation()}>
                          <select
                            value={d.status}
                            onChange={(e) => updateStatus(d.id, e.target.value)}
                            className="form-input"
                            style={{
                              fontSize: 11,
                              padding: "3px 24px 3px 8px",
                              width: "auto",
                              background: statusColor(d.status).bg,
                              color: statusColor(d.status).color,
                              border: "none",
                              fontWeight: 500,
                            }}
                          >
                            {STATUSES.filter((s) => s !== "全部").map((s) => <option key={s} value={s}>{s}</option>)}
                          </select>
                        </div>
                      </div>
                    )
                  })}
                </div>
                )}
              </section>
            )
          })}
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-icon"><Search size={24} /></div>
          <p style={{ fontWeight: 500 }}>暂无匹配的需求数据</p>
          <p style={{ fontSize: 13 }}>尝试调整筛选条件或先运行分析管线生成需求。</p>
        </div>
      )}
    </div>
  )
}
