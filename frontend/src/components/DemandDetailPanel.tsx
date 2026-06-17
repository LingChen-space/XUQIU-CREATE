import { useEffect, useState } from "react"
import { X, ExternalLink, Loader2, Clock, Gauge, Flag } from "lucide-react"
import { api } from "../api/client"
import type { DemandCard, DemandDetail } from "../types"
import RadarChart from "./RadarChart"

const SIGNAL_NAMES: [string, string][] = [
  ["重复提问密度", "repeat_question"],
  ["信息分散度", "info_scatter"],
  ["民间工具萌芽", "grassroots_tool"],
  ["资格稀缺信号", "scarcity"],
  ["机制复杂度", "mechanism_complexity"],
  ["内容热度", "content_heat"],
  ["外部平台工具上线", "external_platform_tool"],
]

const getDemandDisplayTitle = (demand: DemandCard | DemandDetail) => {
  if (demand.demand_category === "experience_server" && demand.experience_focus?.length > 0) {
    return `${demand.game_name} · ${demand.experience_focus.join(" / ")}`
  }
  return demand.title
}

const LEVEL_CONFIG: Record<string, { bg: string; color: string; label: string }> = {
  "S级": { bg: "#fef2f2", color: "#b91c1c", label: "S级" },
  "A级": { bg: "#fffbeb", color: "#92400e", label: "A级" },
  "B级": { bg: "#eff6ff", color: "#2563eb", label: "B级" },
  "C级": { bg: "#f3f4f6", color: "#6b7280", label: "C级" },
}

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  "待评估": { bg: "#f3f4f6", color: "#4b5563" },
  "已采纳": { bg: "#ecfdf5", color: "#059669" },
  "开发中": { bg: "#eff6ff", color: "#2563eb" },
  "已上线": { bg: "#f5f3ff", color: "#7c3aed" },
  "已驳回": { bg: "#fef2f2", color: "#dc2626" },
}

export default function DemandDetailPanel({ demand, onClose }: { demand: DemandCard; onClose: () => void }) {
  const [detail, setDetail] = useState<DemandDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getDemandDetail(demand.id).then(setDetail).finally(() => setLoading(false))
  }, [demand.id])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [onClose])

  const d = detail
  const score = Math.round(demand.potential_score)
  const level = demand.demand_level || "C级"
  const lvlCfg = LEVEL_CONFIG[level] || LEVEL_CONFIG["C级"]
  const stsCfg = STATUS_STYLE[demand.status] || STATUS_STYLE["待评估"]

  return (
    <>
      <div className="slideover-overlay" onClick={onClose} />
      <div className="slideover-panel">
        <div className="slideover-header">
          <div style={{ flex: 1, minWidth: 0, paddingRight: 16 }}>
            <h3>{getDemandDisplayTitle(d || demand)}</h3>
            <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
              <span className="chip game">{demand.game_name}</span>
              {demand.demand_category === "experience_server" ? (
                (demand.experience_focus?.length ? demand.experience_focus : ["体验服内容"]).map((label) => (
                  <span key={label} className="chip" style={{ background: "#f0fdf4", color: "#047857" }}>{label}</span>
                ))
              ) : (
                <span className="chip">{demand.tool_type}</span>
              )}
              {/* Level badge */}
              <span style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                padding: "4px 12px", borderRadius: 6,
                fontSize: 13, fontWeight: 700,
                background: lvlCfg.bg, color: lvlCfg.color,
                border: `1.5px solid ${lvlCfg.color}30`,
              }}>
                <Flag size={13} />
                {lvlCfg.label}
              </span>
              {/* Score */}
              <span style={{ fontWeight: 700, fontSize: 15, color: score >= 80 ? "var(--red)" : score >= 60 ? "var(--amber)" : "var(--text)" }}>
                <Gauge size={14} style={{ verticalAlign: "-2px", marginRight: 3 }} />
                {score}分
              </span>
              {/* Status */}
              <span style={{
                display: "inline-block",
                padding: "4px 12px", borderRadius: 5,
                fontSize: 12, fontWeight: 600,
                background: stsCfg.bg, color: stsCfg.color,
              }}>
                {demand.status}
              </span>
              {/* Date */}
              <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "var(--text-muted)" }}>
                <Clock size={13} />
                {String(demand.demand_date).slice(0, 10)}
              </span>
            </div>
          </div>
          <button className="btn btn-outline btn-sm" onClick={onClose} style={{ flexShrink: 0 }}>
            <X size={16} />
          </button>
        </div>

        <div className="slideover-body">
          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
              <Loader2 className="spinner" size={22} color="var(--primary)" />
            </div>
          ) : d ? (
            <>
              {/* Signal radar */}
              <div className="slideover-section">
                <h4>需求信号</h4>
                <div style={{ display: "flex", gap: 28, alignItems: "flex-start" }}>
                  <RadarChart signals={d.signals} />
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
                    {SIGNAL_NAMES.map(([label, key]) => {
                      const val = (d.signals as any)[key] || 0
                      return (
                        <div key={key} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <span style={{ width: 84, fontSize: 12, color: "var(--text-secondary)", flexShrink: 0 }}>{label}</span>
                          <div style={{ flex: 1, height: 7, borderRadius: 4, background: "#e5e7eb", overflow: "hidden" }}>
                            <div style={{
                              height: "100%", borderRadius: 4,
                              background: key === "content_heat" ? "var(--cyan)" : key === "external_platform_tool" ? "var(--purple)" : key === "scarcity" ? "var(--amber)"
                                : key === "grassroots_tool" ? "var(--green)" : key === "mechanism_complexity" ? "var(--red)"
                                : key === "info_scatter" ? "#8b5cf6" : "var(--primary)",
                              width: `${Math.min(val, 100)}%`,
                              transition: "width 0.5s ease"
                            }} />
                          </div>
                          <span style={{ width: 34, textAlign: "right", fontSize: 12, fontWeight: 600, flexShrink: 0 }}>
                            {Math.round(val)}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>

              {/* LLM Analysis */}
              <div className="slideover-section">
                <h4>LLM 分析</h4>
                <div style={{ background: "#f9fafb", borderRadius: 10, padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
                  {d.llm_analysis.high_freq_questions?.length > 0 && (
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>
                        玩家高频问题
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {d.llm_analysis.high_freq_questions.map((q, i) => (
                          <span key={i} className="chip" style={{ background: "var(--primary-light)", color: "var(--primary)", fontSize: 12 }}>
                            {q}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>信息缺口</div>
                    <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.6 }}>
                      {d.llm_analysis.info_gap || "暂无"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>分析推理</div>
                    <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.7 }}>
                      {d.llm_analysis.reasoning || d.llm_reasoning || "暂无"}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 24, paddingTop: 8, borderTop: "1px solid #e5e7eb" }}>
                    <div>
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>工具化可行度 </span>
                      <span style={{ fontWeight: 700, fontSize: 15 }}>
                        {d.llm_analysis.tool_feasibility || d.tool_feasibility}
                      </span>
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>/5</span>
                    </div>
                    {d.llm_analysis.tool_type_suggestion && (
                      <div>
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>建议类型 </span>
                        <span className="chip" style={{ fontSize: 12 }}>{d.llm_analysis.tool_type_suggestion}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Evidence posts */}
              {d.evidence_posts?.length > 0 && (
                <div className="slideover-section">
                  <h4>证据帖 ({d.evidence_posts.length})</h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {(function() {
                      // Deduplicate by URL, keeping first occurrence
                      const seen = new Set<string>()
                      const deduped = d.evidence_posts.filter(ep => {
                        const key = ep.url || ep.id
                        if (seen.has(key)) return false
                        seen.add(key)
                        return true
                      })
                      // Also deduplicate by title to collapse same-name posts
                      const seenTitles = new Set<string>()
                      const unique = deduped.filter(ep => {
                        const key = ep.platform + '|' + ep.title
                        if (seenTitles.has(key)) return false
                        seenTitles.add(key)
                        return true
                      })
                      return unique.map((ep) => {
                        const hasValidUrl = ep.url && !ep.url.startsWith('no_url') && !ep.url.includes('.example.com') && ep.url.startsWith('http')
                        const content = (
                          <>
                            <span className="platform-badge">{ep.platform}</span>
                            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ep.title}</span>
                            {hasValidUrl ? <ExternalLink size={14} color="var(--text-muted)" /> : <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>无链接</span>}
                          </>
                        )
                        if (hasValidUrl) {
                          return (
                            <a key={ep.id} href={ep.url} target="_blank" rel="noopener noreferrer" className="evidence-link" title={ep.url}>
                              {content}
                            </a>
                          )
                        }
                        return (
                          <div key={ep.id} className="evidence-link" style={{ cursor: 'default', opacity: 0.7 }} title="来源链接不可用">
                            {content}
                          </div>
                        )
                      })
                    })()}
                  </div>
                </div>
              )}

              {/* Similar past demands */}
              {d.similar_past_demands?.length > 0 && (
                <div className="slideover-section">
                  <h4>相似历史需求</h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    {d.similar_past_demands.map((s) => (
                      <div key={s.id} style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "8px 0", borderBottom: "1px solid #f3f4f6", fontSize: 13
                      }}>
                        <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.title}</span>
                        <span style={{ display: "flex", gap: 16, fontSize: 12, color: "var(--text-muted)", flexShrink: 0, marginLeft: 12 }}>
                          <span>{s.demand_date}</span>
                          <span style={{ fontWeight: 600 }}>{s.potential_score}分</span>
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ textAlign: "center", color: "var(--text-muted)", padding: 60 }}>加载失败，请重试</div>
          )}
        </div>
      </div>
    </>
  )
}
