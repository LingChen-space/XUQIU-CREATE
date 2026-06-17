import { useEffect, useState, useMemo } from "react"
import { Search, Loader2, SlidersHorizontal, ArrowUpDown } from "lucide-react"
import { api } from "../api/client"
import type { DemandCard } from "../types"

const TOOL_TYPES = ["全部", "配装/战备工具", "交互地图", "抽卡/概率分析", "资格/福利聚合", "机制计算器", "排行榜/对战数据", "剧情/收集进度", "攻略辅助", "模拟器", "数据库", "其他"]
const STATUSES = ["全部", "待评估", "已采纳", "开发中", "已上线", "已驳回"]
const CATEGORIES = [
  { value: "全部", label: "全部" },
  { value: "tool", label: "工具需求" },
  { value: "experience_server", label: "体验服需求" },
]

const getDemandDisplayTitle = (d: DemandCard) => {
  if (d.demand_category === "experience_server" && d.experience_focus?.length > 0) {
    return `${d.game_name} · ${d.experience_focus.join(" / ")}`
  }
  return d.title
}

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

        <span style={{ fontSize: 12, color: "var(--text-muted)", marginLeft: "auto" }}>
          共 {filtered.length} 条需求
        </span>
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
          <Loader2 className="spinner" size={24} color="var(--primary)" />
        </div>
      ) : filtered.length > 0 ? (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "30%" }}>需求</th>
                <th>游戏</th>
                <th>分类</th>
                <th>类型</th>
                <th style={{ textAlign: "center", cursor: "pointer" }} onClick={() => toggleSort("potential_score")}>
                  <div style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    潜力分
                    <ArrowUpDown size={12} />
                  </div>
                </th>
                <th style={{ textAlign: "center" }}>可行度</th>
                <th style={{ textAlign: "center" }}>状态</th>
                <th style={{ textAlign: "center", cursor: "pointer" }} onClick={() => toggleSort("demand_date")}>
                  <div style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    日期
                    <ArrowUpDown size={12} />
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((d) => (
                <tr key={d.id} style={{ cursor: "pointer" }} onClick={() => onSelect(d)}>
                  <td style={{ maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 500 }}>
                    {getDemandDisplayTitle(d)}
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <span className="chip game" style={{ fontSize: 11 }}>{d.game_name}</span>
                  </td>
                  <td>
                    <span className="chip" style={{
                      fontSize: 11,
                      background: d.demand_category === "experience_server" ? "#ecfdf5" : "var(--primary-light)",
                      color: d.demand_category === "experience_server" ? "#047857" : "var(--primary)",
                    }}>
                      {d.demand_category === "experience_server" ? "体验服需求" : "工具需求"}
                    </span>
                    {d.demand_category === "experience_server" && d.experience_focus?.length > 0 && (
                      <div style={{ display: "flex", gap: 4, marginTop: 4, flexWrap: "wrap" }}>
                        {d.experience_focus.map((label) => (
                          <span key={label} style={{ fontSize: 10, color: "#047857" }}>{label}</span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>
                    {d.demand_category === "experience_server" ? (
                      <span className="chip" style={{ background: "#f0fdf4", color: "#047857" }}>
                        {d.experience_focus?.join(" / ") || "体验服内容"}
                      </span>
                    ) : (
                      <span className="chip">{d.tool_type}</span>
                    )}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <span style={{
                      fontWeight: 700, fontSize: 15,
                      color: d.potential_score >= 80 ? "var(--red)" : d.potential_score >= 60 ? "var(--amber)" : "var(--text)"
                    }}>
                      {Math.round(d.potential_score)}
                    </span>
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <span style={{ fontWeight: 500 }}>{d.tool_feasibility}</span>
                    <span style={{ color: "var(--text-muted)", fontSize: 11 }}>/5</span>
                  </td>
                  <td style={{ textAlign: "center" }} onClick={(e) => e.stopPropagation()}>
                    <select
                      value={d.status}
                      onChange={(e) => updateStatus(d.id, e.target.value)}
                      className="form-input"
                      style={{
                        fontSize: 11, padding: "3px 24px 3px 8px", width: "auto",
                        background: statusColor(d.status).bg, color: statusColor(d.status).color,
                        border: "none", fontWeight: 500
                      }}
                    >
                      {STATUSES.filter((s) => s !== "全部").map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td style={{ fontSize: 12, color: "var(--text-muted)", whiteSpace: "nowrap", textAlign: "center" }}>
                    {String(d.demand_date).slice(0, 10)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
