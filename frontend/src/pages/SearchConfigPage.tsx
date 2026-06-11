import { useEffect, useState, useCallback } from "react"
import {
  Search, Plus, Trash2, Loader2, Gamepad2, SlidersHorizontal,
  ToggleLeft, ToggleRight, Check, X, Edit2
} from "lucide-react"
import { api } from "../api/client"
import type { Game, SearchConfig, PlatformOption } from "../types"

export default function SearchConfigPage() {
  const [games, setGames] = useState<Game[]>([])
  const [platforms, setPlatforms] = useState<PlatformOption[]>([])
  const [configs, setConfigs] = useState<SearchConfig[]>([])
  const [selectedGameId, setSelectedGameId] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editKeywords, setEditKeywords] = useState("")
  const [error, setError] = useState("")
  const [showAddForm, setShowAddForm] = useState(false)
  const [newPlatform, setNewPlatform] = useState("")
  const [newKeywords, setNewKeywords] = useState("")

  const activeGames = games.filter((g) => g.status !== "已停运")

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [gameList, platformList] = await Promise.all([
        api.getGames(),
        api.getSearchConfigPlatforms(),
      ])
      setGames(gameList)
      setPlatforms(platformList)
      if (!selectedGameId && gameList.length > 0) {
        const first = gameList.find((g: Game) => g.status !== "已停运")
        if (first) setSelectedGameId(first.id)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchConfigs = useCallback(async () => {
    if (!selectedGameId) { setConfigs([]); return }
    try {
      const list = await api.getSearchConfigs(selectedGameId)
      setConfigs(list)
    } catch {
      setConfigs([])
    }
  }, [selectedGameId])

  useEffect(() => { fetchData() }, [])
  useEffect(() => { fetchConfigs() }, [selectedGameId])

  const selectedGame = games.find((g) => g.id === selectedGameId)

  const toggleEnabled = async (cfg: SearchConfig) => {
    try {
      await api.updateSearchConfig(cfg.id, { enabled: !cfg.enabled })
      fetchConfigs()
    } catch {
      setError("操作失败")
    }
  }

  const startEdit = (cfg: SearchConfig) => {
    setEditingId(cfg.id)
    setEditKeywords(cfg.keywords)
    setError("")
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditKeywords("")
    setError("")
  }

  const saveEdit = async (cfg: SearchConfig) => {
    if (!editKeywords.trim()) { setError("关键词不能为空"); return }
    setSaving(true)
    try {
      await api.updateSearchConfig(cfg.id, { keywords: editKeywords })
      setEditingId(null)
      setEditKeywords("")
      fetchConfigs()
    } catch (e: any) {
      setError(e?.message || "保存失败")
    } finally {
      setSaving(false)
    }
  }

  const deleteConfig = async (cfg: SearchConfig) => {
    if (!confirm(`确定删除 ${platforms.find(p => p.key === cfg.platform)?.label || cfg.platform} 的搜索词配置？`)) return
    try {
      await api.deleteSearchConfig(cfg.id)
      fetchConfigs()
    } catch {
      setError("删除失败")
    }
  }

  const addConfig = async () => {
    if (!newPlatform) { setError("请选择平台"); return }
    if (!newKeywords.trim()) { setError("请输入搜索关键词"); return }
    setSaving(true)
    try {
      await api.createSearchConfig(selectedGameId!, {
        platform: newPlatform,
        keywords: newKeywords,
      })
      setShowAddForm(false)
      setNewPlatform("")
      setNewKeywords("")
      setError("")
      fetchConfigs()
    } catch (e: any) {
      setError(e?.message || "添加失败")
    } finally {
      setSaving(false)
    }
  }

  // Which platforms already have configs (to exclude from add dropdown)
  const usedPlatforms = new Set(configs.map(c => c.platform))
  const availablePlatforms = platforms.filter(p => !usedPlatforms.has(p.key))

  const getPlatformLabel = (key: string) => platforms.find(p => p.key === key)?.label || key

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "60vh" }}>
        <Loader2 className="spinner" size={28} color="var(--primary)" />
      </div>
    )
  }

  return (
    <div>
      <div className="section-header">
        <h2><Search size={17} /> 搜索词配置</h2>
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
          为每款游戏配置各平台的搜索关键词，管线将自动基于这些词抓取内容
        </span>
      </div>

      {/* Game selector */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12, marginBottom: 24,
        padding: "14px 20px", background: "var(--surface)",
        border: "1px solid var(--border)", borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)", flexWrap: "wrap",
      }}>
        <Gamepad2 size={16} color="var(--text-muted)" />
        <span style={{ fontSize: 13, fontWeight: 500, whiteSpace: "nowrap" }}>选择游戏：</span>
        <select
          value={selectedGameId}
          onChange={(e) => { setSelectedGameId(e.target.value); setShowAddForm(false) }}
          className="form-input"
          style={{ fontSize: 13, padding: "6px 32px 6px 10px", width: "auto", minWidth: 180 }}
        >
          {activeGames.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name} ({g.genre})
            </option>
          ))}
        </select>
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
          已配置 {configs.length} 个平台
        </span>
        <div style={{ marginLeft: "auto" }}>
          {availablePlatforms.length > 0 && !showAddForm && (
            <button className="btn btn-primary" onClick={() => setShowAddForm(true)} style={{ fontSize: 12, padding: "6px 14px" }}>
              <Plus size={14} /> 新增平台搜索词
            </button>
          )}
        </div>
      </div>

      {/* Add form */}
      {showAddForm && (
        <div style={{
          marginBottom: 20, padding: "16px 20px",
          background: "#f0fdf4", border: "1px solid #bbf7d0",
          borderRadius: "var(--radius-lg)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <Plus size={14} color="var(--green)" />
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--green)" }}>
              为 {selectedGame?.name} 新增搜索词配置
            </span>
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>平台</label>
              <select
                value={newPlatform}
                onChange={(e) => setNewPlatform(e.target.value)}
                className="form-input"
                style={{ fontSize: 13, padding: "6px 28px 6px 10px", width: 140 }}
              >
                <option value="">选择平台</option>
                {availablePlatforms.map((p) => (
                  <option key={p.key} value={p.key}>{p.label}</option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 280 }}>
              <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>搜索关键词（逗号分隔，可多个）</label>
              <input
                type="text"
                value={newKeywords}
                onChange={(e) => setNewKeywords(e.target.value)}
                placeholder="例如：配装计算器, 战备阈值, 最强配装"
                className="form-input"
                style={{ width: "100%", fontSize: 13, padding: "6px 10px" }}
                onKeyDown={(e) => e.key === "Enter" && addConfig()}
              />
            </div>
            <button className="btn btn-primary" onClick={addConfig} disabled={saving} style={{ fontSize: 12, padding: "6px 16px" }}>
              {saving ? <Loader2 className="spinner" size={14} /> : <Check size={14} />}
              确认添加
            </button>
            <button className="btn btn-ghost" onClick={() => { setShowAddForm(false); setError("") }} style={{ fontSize: 12, padding: "6px 12px" }}>
              <X size={14} /> 取消
            </button>
          </div>
        </div>
      )}

      {error && (
        <div style={{
          marginBottom: 16, padding: "10px 16px", background: "var(--red-light)",
          color: "var(--red)", borderRadius: 8, fontSize: 13,
        }}>
          {error} <button onClick={() => setError("")} style={{ marginLeft: 12, fontSize: 11, textDecoration: "underline", background: "none", border: "none", cursor: "pointer", color: "var(--red)" }}>关闭</button>
        </div>
      )}

      {/* Config cards */}
      {configs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon"><SlidersHorizontal size={24} /></div>
          <p style={{ fontWeight: 500, marginBottom: 6 }}>暂无搜索词配置</p>
          <p style={{ fontSize: 13, marginBottom: 20 }}>
            为「{selectedGame?.name || "所选游戏"}」添加平台搜索词后，管线将自动抓取相关热门内容用于需求挖掘。
          </p>
          {availablePlatforms.length > 0 && (
            <button className="btn btn-primary" onClick={() => setShowAddForm(true)}>
              <Plus size={14} /> 新增平台搜索词
            </button>
          )}
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "15%" }}>平台</th>
                <th style={{ width: "45%" }}>搜索关键词</th>
                <th style={{ width: "12%", textAlign: "center" }}>状态</th>
                <th style={{ width: "15%", textAlign: "center" }}>更新时间</th>
                <th style={{ width: "13%", textAlign: "center" }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {configs.map((cfg) => {
                const isEditing = editingId === cfg.id
                const pltLabel = getPlatformLabel(cfg.platform)
                return (
                  <tr key={cfg.id}>
                    <td>
                      <span style={{
                        display: "inline-block",
                        padding: "4px 12px", borderRadius: 5,
                        background: "var(--primary-light)", color: "var(--primary)",
                        fontSize: 12, fontWeight: 600,
                      }}>
                        {pltLabel}
                      </span>
                    </td>
                    <td>
                      {isEditing ? (
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <input
                            type="text"
                            value={editKeywords}
                            onChange={(e) => setEditKeywords(e.target.value)}
                            className="form-input"
                            style={{ flex: 1, fontSize: 13, padding: "5px 8px" }}
                            onKeyDown={(e) => e.key === "Enter" && saveEdit(cfg)}
                            autoFocus
                          />
                          <button onClick={() => saveEdit(cfg)} disabled={saving}
                            style={{ padding: "4px 8px", border: "none", borderRadius: 4, cursor: "pointer", background: "var(--green)", color: "#fff" }}
                          >
                            <Check size={14} />
                          </button>
                          <button onClick={cancelEdit}
                            style={{ padding: "4px 8px", border: "none", borderRadius: 4, cursor: "pointer", background: "#e5e7eb", color: "var(--text)" }}
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          {cfg.keywords.split(",").map((kw, i) => (
                            <span key={i} style={{
                              display: "inline-block",
                              padding: "2px 8px", borderRadius: 4,
                              background: "#f3f4f6", color: "var(--text-secondary)",
                              fontSize: 12,
                            }}>
                              {kw.trim()}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <button
                        onClick={() => toggleEnabled(cfg)}
                        style={{
                          background: "none", border: "none", cursor: "pointer",
                          padding: 2, display: "inline-flex", alignItems: "center", gap: 4,
                          fontSize: 12, color: cfg.enabled ? "var(--green)" : "var(--text-muted)",
                        }}
                        title={cfg.enabled ? "已启用，点击停用" : "已停用，点击启用"}
                      >
                        {cfg.enabled ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                        {cfg.enabled ? "启用" : "停用"}
                      </button>
                    </td>
                    <td style={{ textAlign: "center", fontSize: 11, color: "var(--text-muted)" }}>
                      {cfg.updated_at?.slice(0, 10)}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <div style={{ display: "flex", gap: 4, justifyContent: "center" }}>
                        {!isEditing && (
                          <button onClick={() => startEdit(cfg)}
                            style={{ padding: "4px 8px", border: "none", borderRadius: 4, cursor: "pointer", background: "var(--primary-light)", color: "var(--primary)" }}
                            title="编辑关键词"
                          >
                            <Edit2 size={14} />
                          </button>
                        )}
                        <button onClick={() => deleteConfig(cfg)}
                          style={{ padding: "4px 8px", border: "none", borderRadius: 4, cursor: "pointer", background: "var(--red-light)", color: "var(--red)" }}
                          title="删除配置"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Hint */}
      <div style={{
        marginTop: 24, padding: "14px 18px",
        background: "var(--surface)", border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)", fontSize: 12, color: "var(--text-muted)",
        lineHeight: 1.6,
      }}>
        <strong style={{ color: "var(--text-secondary)" }}>使用说明：</strong>
        搜索词配置后，每日需求挖掘管线会自动基于配置的关键词抓取对应平台的热门内容。
        例如「三角洲行动」在「抖音」配置「配装计算器, 战备阈值」，管线会抓取抖音上三角洲行动配装计算器相关视频/帖子，纳入信号计算。
        每个平台只需配置一次，关键词用逗号分隔。
      </div>
    </div>
  )
}
