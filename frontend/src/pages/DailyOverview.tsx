import { useEffect, useState } from "react"
import { RefreshCw, Loader2, BarChart3, Gamepad2, TrendingUp, Zap, FileText, Plus } from "lucide-react"
import { api } from "../api/client"
import type { DashboardSummary, DemandCard, Game } from "../types"
import DemandCardView from "../components/DemandCard"

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

  const fetchData = async () => {
    setLoading(true)
    try {
      const [summary, gameList] = await Promise.all([api.getDashboardSummary(), api.getGames()])
      setData(summary)
      setGames(gameList)
      const active = gameList.filter((g: Game) => g.status !== "已停运")
      onGameCountChange(active.length)
      onDemandCountChange(summary.total_demands_today)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const triggerPipeline = async () => {
    setPipelineLoading(true)
    try {
      await api.triggerPipeline()
      await fetchData()
    } finally {
      setPipelineLoading(false)
    }
  }

  const activeGames = games.filter((g) => g.status !== "已停运")
  const activeGameNames = new Set(activeGames.map((g) => g.name))
  const hotDemands = data?.top_demands?.filter((d) => d.potential_score >= 70).length ?? 0

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
