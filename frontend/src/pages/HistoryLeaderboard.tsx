import { useEffect, useState, useMemo } from "react"
import { Loader2, Trophy, TrendingUp, Flame, Clock, ChevronDown, SlidersHorizontal, Zap } from "lucide-react"
import { api } from "../api/client"
import type { DemandHistoryCard, HistoryLeaderboardOut } from "../types"

const LEVEL_CONFIG: Record<string, { bg: string; color: string; label: string }> = {
  "S级": { bg: "var(--red-light)", color: "#b91c1c", label: "S" },
  "A级": { bg: "var(--amber-light)", color: "#92400e", label: "A" },
  "B级": { bg: "var(--primary-light)", color: "var(--primary)", label: "B" },
  "C级": { bg: "#f3f4f6", color: "var(--text-muted)", label: "C" },
}

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  "待评估": { bg: "#f3f4f6", color: "var(--text-secondary)" },
  "已采纳": { bg: "var(--green-light)", color: "var(--green)" },
  "开发中": { bg: "var(--primary-light)", color: "var(--primary)" },
  "已上线": { bg: "var(--purple-light)", color: "var(--purple)" },
  "已驳回": { bg: "var(--red-light)", color: "var(--red)" },
}

const STATUS_LABELS = ["全部", "待评估", "已采纳", "开发中", "已上线", "已驳回"]

interface Props {
  onSelect: (d: any) => void
  onCountChange?: (n: number) => void
}

export default function HistoryLeaderboard({ onSelect, onCountChange }: Props) {
  const [data, setData] = useState<HistoryLeaderboardOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState("全部")
  const [levelFilter, setLevelFilter] = useState("全部")
  const [minScore, setMinScore] = useState(70)
  const [maxDays, setMaxDays] = useState(90)

  useEffect(() => {
    setLoading(true)
    api.getHistoryLeaderboard(0, maxDays, 200)
      .then((d) => {
        setData(d)
        onCountChange?.(d.total_ranked)
      })
      .finally(() => setLoading(false))
  }, [maxDays])

  const leaderboard = useMemo(() => {
    if (!data?.leaderboard) return []
    let result = [...data.leaderboard]
    if (minScore > 0) {
      result = result.filter((d) => d.potential_score >= minScore)
    }
    if (statusFilter !== "全部") {
      result = result.filter((d) => d.status === statusFilter)
    }
    if (levelFilter !== "全部") {
      result = result.filter((d) => d.demand_level === levelFilter)
    }
    result.sort((a, b) => b.potential_score - a.potential_score)
    return result
  }, [data, minScore, statusFilter, levelFilter])

  const sCount = leaderboard.filter((d) => d.demand_level === "S级").length
  const aCount = leaderboard.filter((d) => d.demand_level === "A级").length
  const avgScore = leaderboard.length > 0
    ? Math.round(leaderboard.reduce((s, d) => s + d.potential_score, 0) / leaderboard.length)
    : 0

  const getRankIcon = (index: number) => {
    if (index === 0) return <Trophy size={16} color="#f59e0b" />
    if (index === 1) return <Trophy size={16} color="#94a3b8" />
    if (index === 2) return <Trophy size={16} color="#b45309" />
    if (index < 10) return <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", width: 16, textAlign: "center" }}>{index + 1}</span>
    return null
  }

  return (
    <div>
      {/* Metric row */}
      <div className="metric-row">
        <div className="metric-card">
          <div className="metric-icon purple"><Trophy size={18} /></div>
          <div className="metric-label">历史需求总量</div>
          <div className="metric-value">{data?.total_ranked ?? 0}</div>
          <div className="metric-sub">近{maxDays}天累计</div>
        </div>
        <div className="metric-card">
          <div className="metric-icon red"><Flame size={18} /></div>
          <div className="metric-label">S级/A级需求</div>
          <div className="metric-value">
            <span style={{ color: "var(--red)" }}>{sCount}</span>
            <span style={{ fontSize: 20, color: "var(--text-muted)" }}> / </span>
            <span style={{ color: "var(--amber)" }}>{aCount}</span>
          </div>
          <div className="metric-sub">高价值需求沉淀</div>
        </div>
        <div className="metric-card">
          <div className="metric-icon green"><TrendingUp size={18} /></div>
          <div className="metric-label">平均潜力分</div>
          <div className="metric-value">{avgScore}</div>
          <div className="metric-sub">
            {data ? `${data.date_range_start?.slice(0, 10)} ~ ${data.date_range_end?.slice(0, 10)}` : ""}
          </div>
        </div>
        <div className="metric-card">
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <Zap size={16} color="var(--text-muted)" />
            <select
              value={maxDays}
              onChange={(e) => setMaxDays(Number(e.target.value))}
              className="form-input" style={{ fontSize: 12, padding: "5px 28px 5px 10px", width: "auto" }}
            >
              <option value={7}>最近7天</option>
              <option value={30}>最近30天</option>
              <option value={60}>最近60天</option>
              <option value={90}>最近90天</option>
              <option value={180}>最近半年</option>
              <option value={365}>最近一年</option>
            </select>
          </div>
          <div className="metric-sub" style={{ marginTop: 4 }}>时间范围可切换</div>
        </div>
      </div>

      {/* Toolbar */}
      <div style={{
        display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12,
        marginBottom: 20, padding: "14px 20px", background: "var(--surface)",
        border: "1px solid var(--border)", borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <SlidersHorizontal size={14} color="var(--text-muted)" />
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>最低分数</span>
          <input
            type="number" min={0} max={100} value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="form-input" style={{ width: 72, padding: "6px 8px", fontSize: 12 }}
          />
        </div>
        <div style={{ width: 1, height: 24, background: "var(--border)" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>需求等级</span>
          <select value={levelFilter} onChange={(e) => setLevelFilter(e.target.value)} className="form-input" style={{ fontSize: 12, padding: "6px 28px 6px 10px" }}>
            <option value="全部">全部</option>
            <option value="S级">S级 (≥85)</option>
            <option value="A级">A级 (70-84)</option>
            <option value="B级">B级 (50-69)</option>
            <option value="C级">C级 (&lt;50)</option>
          </select>
        </div>
        <div style={{ width: 1, height: 24, background: "var(--border)" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>进度</span>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="form-input" style={{ fontSize: 12, padding: "6px 28px 6px 10px" }}>
            {STATUS_LABELS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <span style={{ fontSize: 12, color: "var(--text-muted)", marginLeft: "auto" }}>
          共 {leaderboard.length} 条
        </span>
      </div>

      {/* Leaderboard table */}
      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
          <Loader2 className="spinner" size={24} color="var(--primary)" />
        </div>
      ) : leaderboard.length > 0 ? (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 48, textAlign: "center" }}>#</th>
                <th style={{ width: "28%" }}>需求</th>
                <th>游戏</th>
                <th style={{ textAlign: "center" }}>等级</th>
                <th style={{ textAlign: "center" }}>潜力分</th>
                <th style={{ textAlign: "center" }}>可行度</th>
                <th style={{ textAlign: "center" }}>进度</th>
                <th style={{ textAlign: "center" }}>挖掘时间</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.map((d, i) => {
                const lvl = LEVEL_CONFIG[d.demand_level] || LEVEL_CONFIG["C级"]
                const sts = STATUS_STYLE[d.status] || STATUS_STYLE["待评估"]
                return (
                  <tr key={d.id} style={{ cursor: "pointer" }} onClick={() => onSelect({ ...d, signals: d.signal_scores })}>
                    <td style={{ textAlign: "center", fontSize: 13, fontWeight: 600 }}>
                      {getRankIcon(i)}
                    </td>
                    <td style={{ maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{d.title}</span>
                      {d.llm_reasoning && (
                        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {d.llm_reasoning}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className="chip game" style={{ fontSize: 11 }}>{d.game_name}</span>
                      <span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 6 }}>{d.tool_type}</span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span style={{
                        display: "inline-block",
                        padding: "3px 10px",
                        borderRadius: 5,
                        fontSize: 11,
                        fontWeight: 700,
                        background: lvl.bg,
                        color: lvl.color,
                        letterSpacing: "0.03em",
                      }}>
                        {lvl.label}
                      </span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span style={{
                        fontWeight: 700, fontSize: 16,
                        color: d.potential_score >= 80 ? "var(--red)" : d.potential_score >= 60 ? "var(--amber)" : "var(--text)"
                      }}>
                        {Math.round(d.potential_score)}
                      </span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span style={{ fontWeight: 500, fontSize: 13 }}>{d.tool_feasibility}</span>
                      <span style={{ color: "var(--text-muted)", fontSize: 11 }}>/5</span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span style={{
                        display: "inline-block",
                        padding: "3px 10px",
                        borderRadius: 5,
                        fontSize: 11,
                        fontWeight: 500,
                        background: sts.bg,
                        color: sts.color,
                        whiteSpace: "nowrap"
                      }}>
                        {d.status}
                      </span>
                    </td>
                    <td style={{ textAlign: "center", fontSize: 12, color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4, justifyContent: "center" }}>
                        <Clock size={11} color="var(--text-muted)" />
                        {String(d.demand_date).slice(0, 10)}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-icon"><Trophy size={24} /></div>
          <p style={{ fontWeight: 500, marginBottom: 6 }}>暂无历史需求数据</p>
          <p style={{ fontSize: 13 }}>运行分析管线后，高评分需求将在此沉淀为排行榜</p>
        </div>
      )}
    </div>
  )
}
