import { useEffect, useState } from "react"
import {
  Search, Filter, Loader2, ExternalLink, Eye, ThumbsUp, MessageSquare,
  Calendar, BarChart3, Clock, RefreshCw, Database
} from "lucide-react"
import { api } from "../api/client"
import type { MonitorContent, ContentStats } from "../types"

const PLATFORM_MAP: Record<string, { label: string; color: string; bg: string }> = {
  "B站": { label: "B站", color: "#fb7299", bg: "rgba(251,114,153,0.1)" },
  "抖音": { label: "抖音", color: "#fe2c55", bg: "rgba(254,44,85,0.1)" },
  "TapTap": { label: "TapTap", color: "#15bfff", bg: "rgba(21,191,255,0.1)" },
  "小黑盒": { label: "小黑盒", color: "#00c091", bg: "rgba(0,192,145,0.1)" },
  "NGA": { label: "NGA", color: "#f4a460", bg: "rgba(244,164,96,0.1)" },
  "微博": { label: "微博", color: "#e6162d", bg: "rgba(230,22,45,0.1)" },
  "贴吧": { label: "贴吧", color: "#3385ff", bg: "rgba(51,133,255,0.1)" },
  "其他": { label: "其他", color: "#888", bg: "rgba(136,136,136,0.1)" },
}

const CONTENT_TYPE_MAP: Record<string, string> = {
  "视频": "视频", "帖子": "帖子", "评论": "评论", "搜索词": "搜索词",
}

export default function MonitoringData() {
  const [contents, setContents] = useState<MonitorContent[]>([])
  const [stats, setStats] = useState<ContentStats | null>(null)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  // Filters
  const [search, setSearch] = useState("")
  const [platformFilter, setPlatformFilter] = useState("全部")
  const [daysFilter, setDaysFilter] = useState(7)
  const [page, setPage] = useState(0)
  const pageSize = 50

  const fetchContents = async (showLoading = true) => {
    if (showLoading) setLoading(true)
    try {
      const params: Record<string, string> = {
        days: String(daysFilter),
        limit: String(pageSize),
        offset: String(page * pageSize),
      }
      if (platformFilter !== "全部") params.platform = platformFilter
      if (search.trim()) params.search = search.trim()

      const result = await api.getContents(params)
      setContents(result.items)
      setTotal(result.total)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  const fetchStats = async () => {
    try {
      const s = await api.getContentStats(daysFilter)
      setStats(s)
    } catch {}
  }

  useEffect(() => { fetchContents(); fetchStats() }, [page, platformFilter, daysFilter])
  useEffect(() => {
    const t = setTimeout(() => { setPage(0); fetchContents() }, 400)
    return () => clearTimeout(t)
  }, [search])

  const totalPages = Math.ceil(total / pageSize)

  const formatNumber = (n: number) => {
    if (n >= 10000) return (n / 10000).toFixed(1) + "万"
    if (n >= 1000) return (n / 1000).toFixed(1) + "k"
    return String(n)
  }

  const formatTime = (iso: string) => {
    if (!iso) return "-"
    const d = new Date(iso)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    if (diff < 60000) return "刚刚"
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
    return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    setPage(0)
    await fetchContents(false)
    await fetchStats()
  }

  return (
    <div>
      {/* Header */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "flex-start",
        marginBottom: 20
      }}>
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 600, color: "var(--text)", marginBottom: 4 }}>
            监控数据
          </h2>
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
            本地存储的所有平台采集内容，支持按平台/日期/关键词筛选浏览
          </p>
        </div>
        <button className="btn btn-outline" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? <Loader2 className="spinner" size={16} /> : <RefreshCw size={16} />}
          <span style={{ marginLeft: 6 }}>刷新</span>
        </button>
      </div>

      {/* Stats cards */}
      {stats && (
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 12, marginBottom: 20
        }}>
          <StatCard
            icon={<Database size={16} />}
            label="累计采集"
            value={formatNumber(stats.total)}
            color="var(--primary)"
          />
          {Object.entries(PLATFORM_MAP).map(([key, cfg]) => {
            const count = stats.by_platform[key] || 0
            if (count === 0) return null
            return (
              <StatCard
                key={key}
                icon={<span style={{
                  display: "inline-block", width: 16, height: 16, borderRadius: 4,
                  background: cfg.color, fontSize: 10, color: "#fff",
                  textAlign: "center", lineHeight: "16px"
                }}>{cfg.label[0]}</span>}
                label={cfg.label}
                value={String(count)}
                color={cfg.color}
              />
            )
          })}
        </div>
      )}

      {/* Toolbar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
        marginBottom: 20, padding: "14px 20px", background: "var(--surface)",
        border: "1px solid var(--border)", borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)"
      }}>
        {/* Search */}
        <div style={{ position: "relative" }}>
          <Search size={16} style={{
            position: "absolute", left: 12, top: "50%",
            transform: "translateY(-50%)", color: "var(--text-muted)"
          }} />
          <input
            type="text" placeholder="搜索标题关键词..." value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="form-input" style={{ paddingLeft: 36, width: 260 }}
          />
        </div>

        <div style={{ width: 1, height: 24, background: "var(--border)" }} />

        {/* Platform filter */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Filter size={14} color="var(--text-muted)" />
          <select
            value={platformFilter} onChange={(e) => { setPlatformFilter(e.target.value); setPage(0) }}
            className="form-input" style={{ fontSize: 12, padding: "6px 28px 6px 10px" }}
          >
            <option value="全部">全部平台</option>
            {Object.entries(PLATFORM_MAP).map(([key, cfg]) => (
              <option key={key} value={key}>{cfg.label}</option>
            ))}
          </select>
        </div>

        <div style={{ width: 1, height: 24, background: "var(--border)" }} />

        {/* Days filter */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Calendar size={14} color="var(--text-muted)" />
          <select
            value={daysFilter} onChange={(e) => { setDaysFilter(Number(e.target.value)); setPage(0) }}
            className="form-input" style={{ fontSize: 12, padding: "6px 28px 6px 10px" }}
          >
            <option value={1}>今天</option>
            <option value={3}>近3天</option>
            <option value={7}>近7天</option>
            <option value={30}>近30天</option>
            <option value={90}>近90天</option>
          </select>
        </div>

        <span style={{ fontSize: 12, color: "var(--text-muted)", marginLeft: "auto" }}>
          共 {total} 条记录
        </span>
      </div>

      {/* Content table */}
      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
          <Loader2 className="spinner" size={24} color="var(--primary)" />
        </div>
      ) : contents.length > 0 ? (
        <>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 80 }}>平台</th>
                  <th style={{ width: 70 }}>类型</th>
                  <th>标题</th>
                  <th style={{ width: 60 }}>浏览</th>
                  <th style={{ width: 60 }}>点赞</th>
                  <th style={{ width: 60 }}>评论</th>
                  <th style={{ width: 70 }}>热度</th>
                  <th style={{ width: 90 }}>采集时间</th>
                  <th style={{ width: 60, textAlign: "center" }}>链接</th>
                </tr>
              </thead>
              <tbody>
                {contents.map((c) => {
                  const platformCfg = PLATFORM_MAP[c.platform] || PLATFORM_MAP["其他"]
                  return (
                    <tr key={c.id}>
                      <td>
                        <span style={{
                          display: "inline-flex", alignItems: "center", gap: 5,
                          padding: "2px 8px", borderRadius: 4, fontSize: 11,
                          fontWeight: 600, background: platformCfg.bg, color: platformCfg.color,
                        }}>
                          {c.platform}
                        </span>
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                        {CONTENT_TYPE_MAP[c.content_type] || c.content_type}
                      </td>
                      <td>
                        <div style={{ maxWidth: 360 }}>
                          <p style={{
                            fontSize: 13, fontWeight: 500, color: "var(--text)",
                            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                          }}>
                            {c.title || "(无标题)"}
                          </p>
                          {c.body && (
                            <p style={{
                              fontSize: 11, color: "var(--text-muted)", marginTop: 2,
                              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                            }}>
                              {c.body}
                            </p>
                          )}
                        </div>
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                        <Eye size={12} style={{ marginRight: 3, verticalAlign: -1 }} />
                        {formatNumber(c.view_count)}
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                        <ThumbsUp size={12} style={{ marginRight: 3, verticalAlign: -1 }} />
                        {formatNumber(c.like_count)}
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                        <MessageSquare size={12} style={{ marginRight: 3, verticalAlign: -1 }} />
                        {formatNumber(c.comment_count)}
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <div style={{
                            flex: 1, height: 4, borderRadius: 2, background: "var(--border)",
                            overflow: "hidden",
                          }}>
                            <div style={{
                              height: "100%", borderRadius: 2,
                              background: c.hot_score >= 70 ? "var(--red)" :
                                c.hot_score >= 40 ? "var(--amber)" : "var(--green)",
                              width: `${Math.min(100, c.hot_score)}%`,
                            }} />
                          </div>
                          <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text)", minWidth: 24, textAlign: "right" }}>
                            {c.hot_score.toFixed(0)}
                          </span>
                        </div>
                      </td>
                      <td style={{ fontSize: 11, color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                        <Clock size={11} style={{ marginRight: 3, verticalAlign: -1 }} />
                        {formatTime(c.collected_at)}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        {c.url ? (
                          <a href={c.url} target="_blank" rel="noreferrer"
                            style={{ color: "var(--primary)", display: "inline-flex", alignItems: "center" }}
                            title="打开原文"
                          >
                            <ExternalLink size={13} />
                          </a>
                        ) : (
                          <span style={{ color: "var(--text-muted)", fontSize: 11 }}>-</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{
              display: "flex", justifyContent: "center", alignItems: "center",
              gap: 8, marginTop: 16
            }}>
              <button className="btn btn-outline btn-xs" disabled={page <= 0}
                onClick={() => setPage(page - 1)}>上一页</button>
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {page + 1} / {totalPages}
              </span>
              <button className="btn btn-outline btn-xs" disabled={page >= totalPages - 1}
                onClick={() => setPage(page + 1)}>下一页</button>
            </div>
          )}
        </>
      ) : (
        <div className="empty-state">
          <div className="empty-icon"><Database size={24} /></div>
          <p style={{ fontWeight: 500 }}>暂无监控数据</p>
          <p style={{ fontSize: 13, marginBottom: 16 }}>
            {platformFilter !== "全部" || search
              ? "当前筛选条件下没有匹配的采集内容，试试扩大筛选范围"
              : "还未采集过数据，请确认监控服务已启动并在搜索词配置中触发抓取"
            }
          </p>
          {platformFilter !== "全部" || search ? (
            <button className="btn btn-outline" onClick={() => {
              setPlatformFilter("全部"); setSearch(""); setDaysFilter(7); setPage(0)
            }}>
              重置筛选
            </button>
          ) : null}
        </div>
      )}
    </div>
  )
}

/* ── Stat Card ── */
function StatCard({ icon, label, value, color }: {
  icon: React.ReactNode; label: string; value: string; color: string;
}) {
  return (
    <div style={{
      padding: "14px 16px", background: "var(--surface)",
      border: "1px solid var(--border)", borderRadius: "var(--radius-lg)",
      boxShadow: "var(--shadow-sm)", display: "flex", alignItems: "center", gap: 12,
    }}>
      <div style={{
        width: 34, height: 34, borderRadius: 8,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: `${color}15`, color: color,
      }}>
        {icon}
      </div>
      <div>
        <p style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 2 }}>{label}</p>
        <p style={{ fontSize: 18, fontWeight: 700, color: "var(--text)", lineHeight: 1.1 }}>{value}</p>
      </div>
    </div>
  )
}
