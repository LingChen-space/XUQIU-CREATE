import { useEffect, useState, useRef } from "react"
import { RefreshCw, Loader2, BarChart3, Gamepad2, TrendingUp, Zap, FileText, Plus, Brain, Target, Layers, RotateCw, ChevronDown, ChevronUp, CheckCircle, XCircle, Circle } from "lucide-react"
import { api } from "../api/client"
import type { DashboardSummary, DemandCard, Game, CrawlProgress, CrawlProgressRecord } from "../types"
import DemandCardView from "../components/DemandCard"

const LEVEL_STYLE: Record<string, { bg: string; color: string }> = {
  "S级": { bg: "var(--red-light)", color: "#b91c1c" },
  "A级": { bg: "var(--amber-light)", color: "#92400e" },
  "B级": { bg: "var(--primary-light)", color: "var(--primary)" },
  "C级": { bg: "#f3f4f6", color: "var(--text-muted)" },
}

const PLATFORM_COLORS: Record<string, { label: string; color: string; bg: string }> = {
  "B站": { label: "B站", color: "#fb7299", bg: "rgba(251,114,153,0.1)" },
  "抖音": { label: "抖音", color: "#fe2c55", bg: "rgba(254,44,85,0.1)" },
  "TapTap": { label: "TapTap", color: "#15bfff", bg: "rgba(21,191,255,0.1)" },
  "小黑盒": { label: "小黑盒", color: "#00c091", bg: "rgba(0,192,145,0.1)" },
  "NGA": { label: "NGA", color: "#f4a460", bg: "rgba(244,164,96,0.1)" },
  "微博": { label: "微博", color: "#e6162d", bg: "rgba(230,22,45,0.1)" },
  "贴吧": { label: "贴吧", color: "#3385ff", bg: "rgba(51,133,255,0.1)" },
}
const DEFAULT_PLATFORM_COLOR = { label: "其他", color: "#888", bg: "rgba(136,136,136,0.1)" }

interface Props {
  onSelect: (d: DemandCard) => void
  onGameCountChange: (n: number) => void
  onDemandCountChange: (n: number) => void
}

export default function DailyOverview({ onSelect, onGameCountChange, onDemandCountChange }: Props) {
  const [data, setData] = useState<DashboardSummary | null>(null)
  const [games, setGames] = useState<Game[]>([])
  const [loading, setLoading] = useState(true)
  const [pipelineLoading, setPipelineLoading] = useState(false)
  const [progress, setProgress] = useState<CrawlProgress | null>(null)
  const [progressLoading, setProgressLoading] = useState(false)
  const [progressExpanded, setProgressExpanded] = useState(true)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchData = async (showLoader = true) => {
    if (showLoader) setLoading(true)
    try {
      const [summary, gameList] = await Promise.all([api.getDashboardSummary(), api.getGames()])
      setData(summary)
      setGames(gameList)
      const active = gameList.filter((g: Game) => g.status !== "已停运")
      onGameCountChange(active.length)
      onDemandCountChange(summary.total_demands_today)
      try {
        const p = await api.getCrawlProgress()
        setProgress(p)
        const hasRunning = p.records.some(r => r.status === 'running' || r.status === 'pending')
        if (hasRunning) startPolling()
      } catch {}
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const startPolling = () => {
    setProgressLoading(true)
    setProgressExpanded(true)
    const poll = async () => {
      try {
        const p = await api.getCrawlProgress()
        setProgress(p)
        const allDone = p.records.every(r => r.status === 'completed' || r.status === 'failed')
        if (allDone && p.records.length > 0) {
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
          setProgressLoading(false)
        }
      } catch {
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
        setProgressLoading(false)
      }
    }
    poll()
    pollRef.current = setInterval(poll, 2000)
  }

  const triggerPipeline = async () => {
    setPipelineLoading(true)
    try {
      await api.triggerPipeline()
      startPolling()
      await fetchData(false)
    } finally {
      setPipelineLoading(false)
    }
  }

  const activeGames = games.filter((g) => g.status !== "已停运")
  const activeGameNames = new Set(activeGames.map((g) => g.name))
  const hotDemands = data?.top_demands?.filter((d) => d.potential_score >= 70).length ?? 0
  const analysis = data?.daily_analysis

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "60vh" }}>
        <Loader2 className="spinner" size={28} color="var(--primary)" />
      </div>
    )
  }

  return (
    <div>
      {/* Metric cards */}
      <div className="metric-row">
        <div className="metric-card">
          <div className="metric-icon blue"><FileText size={18} /></div>
          <div className="metric-label">今日需求</div>
          <div className="metric-value">{data?.total_demands_today ?? 0}</div>
          <div className="metric-sub">{data?.today_date}</div>
        </div>
        <div className="metric-card">
          <div className="metric-icon green"><Gamepad2 size={18} /></div>
          <div className="metric-label">趋势游戏</div>
          <div className="metric-value">{data?.trending_games?.length ?? 0}</div>
          <div className="metric-sub">有需求信号活跃的游戏</div>
        </div>
        <div className="metric-card">
          <div className="metric-icon red"><Zap size={18} /></div>
          <div className="metric-label">爆款需求</div>
          <div className="metric-value" style={{ color: "var(--red)" }}>{hotDemands}</div>
          <div className="metric-sub">潜力分 ≥ 70 的高价值需求</div>
        </div>
        <div className="metric-card action-card">
          <button
            className="btn btn-primary"
            onClick={triggerPipeline}
            disabled={pipelineLoading}
            style={{ width: "100%", justifyContent: "center", padding: "12px 0", fontSize: 14 }}
          >
            {pipelineLoading ? <Loader2 className="spinner" size={16} /> : <RefreshCw size={16} />}
            {pipelineLoading ? "分析中..." : "立即分析"}
          </button>
          <div className="metric-sub" style={{ textAlign: "center" }}>每日 06:00 自动执行</div>
        </div>
      </div>

      {/* Crawl progress panel */}
      {progress && progress.records.length > 0 && (
        <div style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "16px 20px",
          marginBottom: 24,
          boxShadow: "var(--shadow-sm)",
        }}>
          <div
            onClick={() => setProgressExpanded(!progressExpanded)}
            style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", marginBottom: progressExpanded ? 12 : 0 }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {progressLoading ? <Loader2 size={14} className="spinner" color="var(--primary)" /> : <CheckCircle size={14} color={progress.completed === progress.total ? "var(--green)" : "var(--primary)"} />}
              <span style={{ fontSize: 13, fontWeight: 600 }}>采集进度</span>
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {progress.completed}/{progress.total} 完成
                {progress.failed > 0 && <span style={{ color: "var(--red)", marginLeft: 4 }}>{progress.failed} 失败</span>}
                {progress.running > 0 && <span style={{ color: "var(--primary)", marginLeft: 4 }}>{progress.running} 进行中</span>}
              </span>
            </div>
            {progressExpanded ? <ChevronUp size={16} color="var(--text-muted)" /> : <ChevronDown size={16} color="var(--text-muted)" />}
          </div>

          <div style={{
            height: 6, borderRadius: 3, background: "var(--border)",
            overflow: "hidden", marginBottom: 12,
          }}>
            <div style={{
              height: "100%", borderRadius: 3,
              background: progress.failed > 0 && progress.completed + progress.failed >= progress.total ? "var(--amber)" : "var(--primary)",
              width: `${progress.total > 0 ? Math.round((progress.completed + progress.failed) / progress.total * 100) : 0}%`,
              transition: "width 0.4s ease",
            }} />
          </div>

          {progressExpanded && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {progress.records.map((r) => {
                const pc = PLATFORM_COLORS[r.platform] || DEFAULT_PLATFORM_COLOR
                return (
                  <div key={r.id} style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "6px 10px", borderRadius: 6,
                    background: r.status === "failed" ? "rgba(239,68,68,0.05)" : "#f9fafb",
                    fontSize: 12,
                  }}>
                    {r.status === "completed" && <CheckCircle size={14} color="var(--green)" />}
                    {r.status === "failed" && <XCircle size={14} color="var(--red)" />}
                    {r.status === "running" && <Loader2 size={14} className="spinner" color="var(--primary)" />}
                    {r.status === "pending" && <Circle size={14} color="var(--text-muted)" />}

                    <span style={{
                      display: "inline-flex", alignItems: "center",
                      padding: "1px 8px", borderRadius: 4, fontSize: 11,
                      fontWeight: 600, background: pc.bg, color: pc.color,
                      minWidth: 48, justifyContent: "center",
                    }}>{pc.label}</span>

                    <span style={{ flex: 1, color: "var(--text)", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.keyword}</span>

                    <span style={{ color: "var(--text-muted)", fontSize: 11, minWidth: 70, textAlign: "right", whiteSpace: "nowrap" }}>
                      {r.items_ingested > 0 ? `${r.items_ingested} 条入库` : r.items_fetched > 0 ? `${r.items_fetched} 条抓取` : "-"}
                    </span>

                    {r.status === "failed" && (
                      <button
                        className="btn btn-xs btn-outline"
                        style={{ color: "var(--red)", borderColor: "var(--red)", fontSize: 11, whiteSpace: "nowrap" }}
                        onClick={async (e) => {
                          e.stopPropagation()
                          try {
                            await api.retryCrawl(r.platform, r.keyword)
                            const p = await api.getCrawlProgress()
                            setProgress(p)
                            if (!pollRef.current) startPolling()
                          } catch {}
                        }}
                      >
                        <RotateCw size={11} style={{ marginRight: 3 }} />
                        重试
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Daily summary analysis panel */}
      {analysis && analysis.total_demands > 0 && (
        <div style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "20px 24px",
          marginBottom: 24,
          boxShadow: "var(--shadow-sm)",
        }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <Brain size={18} color="var(--primary)" />
            <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>每日需求洞察总结</h3>
          </div>

          {/* Summary text */}
          <p style={{
            fontSize: 14, lineHeight: 1.7, color: "var(--text-secondary)",
            margin: "0 0 18px 0", padding: "12px 16px",
            background: "var(--primary-light)",
            borderRadius: 8,
            borderLeft: "3px solid var(--primary)",
          }}>
            {analysis.summary_text}
          </p>

          {/* Stats row */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 16 }}>
            {/* Level breakdown */}
            <div style={{
              flex: "1 1 200px", minWidth: 180,
              background: "#f9fafb", borderRadius: 8, padding: "14px 16px",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
                <Layers size={14} color="var(--text-secondary)" />
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)" }}>需求等级分布</span>
              </div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                {(["S级", "A级", "B级", "C级"] as const).map((level) => {
                  const key = (level === "S级" ? "s_count" : level === "A级" ? "a_count" : level === "B级" ? "b_count" : "c_count") as keyof typeof analysis.level_breakdown
                  const count = analysis.level_breakdown[key] ?? 0
                  if (count === 0) return null
                  const s = LEVEL_STYLE[level]
                  return (
                    <span key={level} style={{
                      display: "inline-flex", alignItems: "center", gap: 4,
                      padding: "4px 10px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                      background: s.bg, color: s.color,
                    }}>
                      {level} × {count}
                    </span>
                  )
                })}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 8 }}>
                平均潜力分 <strong style={{ color: "var(--text)" }}>{analysis.avg_potential_score}</strong>
              </div>
            </div>

            {/* Hot tool types */}
            <div style={{
              flex: "1 1 200px", minWidth: 180,
              background: "#f9fafb", borderRadius: 8, padding: "14px 16px",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
                <Target size={14} color="var(--text-secondary)" />
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)" }}>热门工具方向</span>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {analysis.hot_tool_types?.map((t) => (
                  <span key={t.type} style={{
                    display: "inline-flex", alignItems: "center", gap: 4,
                    padding: "4px 10px", borderRadius: 6, fontSize: 12,
                    background: "var(--primary-light)", color: "var(--primary)",
                    fontWeight: 500,
                  }}>
                    {t.type}
                    <span style={{ opacity: 0.7, fontSize: 11 }}>({t.count}条)</span>
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Top recommendations */}
          {analysis.top_recommendations?.length > 0 && (
            <div style={{
              background: "#fefce8", borderRadius: 8, padding: "14px 16px",
              border: "1px solid #fde68a",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                <Zap size={14} color="#b45309" />
                <span style={{ fontSize: 12, fontWeight: 600, color: "#92400e" }}>首推需求</span>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {analysis.top_recommendations.map((title, i) => (
                  <span key={i} style={{
                    fontSize: 13, color: "#78350f",
                    padding: "3px 10px", background: "#fef3c7", borderRadius: 5,
                    fontWeight: 500,
                  }}>
                    #{i + 1} {title.length > 25 ? title.slice(0, 25) + "..." : title}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state: no active games */}
      {activeGames.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon"><Plus size={24} /></div>
          <p style={{ fontWeight: 500, marginBottom: 6 }}>还没有添加监控游戏</p>
          <p style={{ fontSize: 13, marginBottom: 20 }}>请先到「游戏管理」中添加需要挖掘需求的游戏，系统将仅针对编辑添加的游戏进行分析。</p>
        </div>
      ) : (
        <>
          {/* Trending games */}
          {data?.trending_games && data.trending_games.length > 0 && (
            <>
              <div className="section-header">
                <h2><TrendingUp size={17} /> 趋势游戏</h2>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  {data.trending_games.filter(g => activeGameNames.has(g.name)).length} 款活跃
                </span>
              </div>
              <div className="game-tags">
                {data.trending_games
                  .filter(g => activeGameNames.has(g.name))
                  .map((g) => (
                    <div key={g.id} className="game-tag">
                      <Gamepad2 size={14} color="var(--primary)" />
                      <span>{g.name}</span>
                      <span className="tag-genre">{g.genre}</span>
                      <span className="tag-count">{g.demand_count} 条</span>
                    </div>
                  ))}
              </div>
            </>
          )}

          {/* Today demands */}
          <div className="section-header">
            <h2><BarChart3 size={17} /> 今日需求排行</h2>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {data?.top_demands?.filter(d => activeGameNames.has(d.game_name)).length ?? 0} 条需求
            </span>
          </div>

          {!data?.top_demands || data.top_demands.filter(d => activeGameNames.has(d.game_name)).length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon"><RefreshCw size={24} /></div>
              <p style={{ fontWeight: 500, marginBottom: 6 }}>暂无需求数据</p>
              <p style={{ fontSize: 13, marginBottom: 20 }}>点击上方「立即分析」按钮，或等待每日凌晨 6:00 自动执行分析管线。</p>
              <button className="btn btn-primary" onClick={triggerPipeline} disabled={pipelineLoading}>
                {pipelineLoading ? <Loader2 className="spinner" size={16} /> : <RefreshCw size={16} />}
                运行首次分析
              </button>
            </div>
          ) : (
            <div className="demand-grid">
              {data.top_demands
                .filter((d) => activeGameNames.has(d.game_name))
                .sort((a, b) => b.potential_score - a.potential_score)
                .map((d) => (
                  <DemandCardView key={d.id} demand={d} onClick={() => onSelect(d)} />
                ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
