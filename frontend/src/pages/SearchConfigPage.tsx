import { useEffect, useState } from "react"
import {
  Search, Plus, Trash2, Loader2, SlidersHorizontal,
  ToggleLeft, ToggleRight, Check, X, Edit2, Globe, Hash
} from "lucide-react"
import { api } from "../api/client"
import type { SearchConfig, PlatformOption } from "../types"

export default function SearchConfigPage() {
  const [platforms, setPlatforms] = useState<PlatformOption[]>([])
  const [configs, setConfigs] = useState<SearchConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editKeywords, setEditKeywords] = useState("")
  const [editCrawlCount, setEditCrawlCount] = useState(50)
  const [editProxyUrl, setEditProxyUrl] = useState("")
  const [error, setError] = useState("")
  const [showAddForm, setShowAddForm] = useState(false)
  const [newPlatform, setNewPlatform] = useState("")
  const [newKeywords, setNewKeywords] = useState("")
  const [newCrawlCount, setNewCrawlCount] = useState(50)
  const [newProxyUrl, setNewProxyUrl] = useState("")

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [platformList, configList] = await Promise.all([
        api.getSearchConfigPlatforms(),
        api.getSearchConfigs(),
      ])
      setPlatforms(platformList)
      setConfigs(configList)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [])

  const toggleEnabled = async (cfg: SearchConfig) => {
    try {
      await api.updateSearchConfig(cfg.id, { enabled: !cfg.enabled })
      fetchAll()
    } catch {
      setError("操作失败")
    }
  }

  const startEdit = (cfg: SearchConfig) => {
    setEditingId(cfg.id)
    setEditKeywords(cfg.keywords)
    setEditCrawlCount(cfg.crawl_count || 50)
    setEditProxyUrl(cfg.proxy_url || "")
    setError("")
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditKeywords("")
    setEditCrawlCount(50)
    setEditProxyUrl("")
    setError("")
  }

  const saveEdit = async (cfg: SearchConfig) => {
    if (!editKeywords.trim()) { setError("关键词不能为空"); return }
    setSaving(true)
    try {
      await api.updateSearchConfig(cfg.id, {
        keywords: editKeywords,
        crawl_count: editCrawlCount,
        ...(isTapTapPlatform(cfg.platform) ? { proxy_url: editProxyUrl.trim() } : {}),
      })
      setEditingId(null)
      setEditKeywords("")
      setEditProxyUrl("")
      fetchAll()
    } catch (e: any) {
      setError(e?.message || "保存失败")
    } finally {
      setSaving(false)
    }
  }

  const deleteConfig = async (cfg: SearchConfig) => {
    if (!confirm(`确定删除 ${getPlatformLabel(cfg.platform)} 的搜索词配置？`)) return
    try {
      await api.deleteSearchConfig(cfg.id)
      fetchAll()
    } catch {
      setError("删除失败")
    }
  }

  const addConfig = async () => {
    if (!newPlatform) { setError("请选择平台"); return }
    if (!newKeywords.trim()) { setError("请输入搜索关键词"); return }
    setSaving(true)
    try {
      await api.createSearchConfig({
        platform: newPlatform,
        keywords: newKeywords,
        crawl_count: newCrawlCount,
        proxy_url: newPlatform === "taptap" ? newProxyUrl.trim() : null,
      })
      setShowAddForm(false)
      setNewPlatform("")
      setNewKeywords("")
      setNewCrawlCount(50)
      setNewProxyUrl("")
      setError("")
      fetchAll()
    } catch (e: any) {
      setError(e?.message || "添加失败")
    } finally {
      setSaving(false)
    }
  }

  const usedPlatforms = new Set(configs.map(c => c.platform))
  const availablePlatforms = platforms.filter(p => !usedPlatforms.has(p.key))
  const getPlatformLabel = (key: string) => platforms.find(p => p.key === key)?.label || key
  const enabledCount = configs.filter(c => c.enabled).length
  const isTapTapPlatform = (platform: string) => platform.trim().toLowerCase() === "taptap"
  const getSourceLabel = (cfg: SearchConfig) => cfg.source_key === "tap_kb_forum" ? "Tap+快爆后台" : "手工"

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
          配置各平台的搜索关键词，管线将自动基于这些词抓取全部游戏管理列表中的热门内容
        </span>
      </div>

      {/* Stats bar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12, marginBottom: 24,
        padding: "14px 20px", background: "var(--surface)",
        border: "1px solid var(--border)", borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)", flexWrap: "wrap",
      }}>
        <Globe size={16} color="var(--primary)" />
        <span style={{ fontSize: 13, fontWeight: 500 }}>全局搜索词</span>
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
          已配置 <strong style={{ color: "var(--text)" }}>{configs.length}</strong> 个平台 ·
          已启用 <strong style={{ color: "var(--green)" }}>{enabledCount}</strong> 个
        </span>
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
          应用于游戏管理列表中的所有活跃游戏
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
              新增全局搜索词配置
            </span>
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div>
              <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>平台</label>
              <select
                value={newPlatform}
                onChange={(e) => {
                  setNewPlatform(e.target.value)
                  if (e.target.value !== "taptap") setNewProxyUrl("")
                }}
                className="form-input"
                style={{ fontSize: 13, padding: "6px 28px 6px 10px", width: 140 }}
              >
                <option value="">选择平台</option>
                {availablePlatforms.map((p) => (
                  <option key={p.key} value={p.key}>{p.label}</option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 260 }}>
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
            <div style={{ width: 120 }}>
              <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>抓取条数</label>
              <input
                type="number"
                value={newCrawlCount}
                onChange={(e) => setNewCrawlCount(Number(e.target.value) || 50)}
                min={10}
                max={1000}
                className="form-input"
                style={{ width: "100%", fontSize: 13, padding: "6px 8px" }}
              />
            </div>
            {isTapTapPlatform(newPlatform) && (
              <div style={{ flex: "1 1 260px", minWidth: 260 }}>
                <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>代理地址（仅用于 TapTap）</label>
                <input
                  type="text"
                  value={newProxyUrl}
                  onChange={(e) => setNewProxyUrl(e.target.value)}
                  placeholder="例如：http://127.0.0.1:7897"
                  className="form-input"
                  style={{ width: "100%", fontSize: 13, padding: "6px 10px" }}
                />
              </div>
            )}
            <button className="btn btn-primary" onClick={addConfig} disabled={saving} style={{ fontSize: 12, padding: "6px 16px" }}>
              {saving ? <Loader2 className="spinner" size={14} /> : <Check size={14} />}
              确认添加
            </button>
            <button className="btn btn-ghost" onClick={() => { setShowAddForm(false); setNewPlatform(""); setNewCrawlCount(50); setNewProxyUrl(""); setError("") }} style={{ fontSize: 12, padding: "6px 12px" }}>
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

      {/* Config table */}
      {configs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon"><SlidersHorizontal size={24} /></div>
          <p style={{ fontWeight: 500, marginBottom: 6 }}>暂无搜索词配置</p>
          <p style={{ fontSize: 13, marginBottom: 20 }}>
            为各平台添加搜索关键词后，管线将自动抓取相关热门内容，应用于所有游戏管理列表中的游戏进行需求挖掘。
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
                <th style={{ width: "12%" }}>平台</th>
                <th style={{ width: "34%" }}>搜索关键词</th>
                <th style={{ width: "10%", textAlign: "center" }}>抓取条数</th>
                <th style={{ width: "14%" }}>代理配置</th>
                <th style={{ width: "10%", textAlign: "center" }}>状态</th>
                <th style={{ width: "10%", textAlign: "center" }}>更新时间</th>
                <th style={{ width: "10%", textAlign: "center" }}>操作</th>
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
                      <span style={{
                        display: "inline-block",
                        marginLeft: 6,
                        padding: "2px 6px",
                        borderRadius: 4,
                        background: cfg.source_key === "tap_kb_forum" ? "rgba(37,99,235,0.1)" : "#f3f4f6",
                        color: cfg.source_key === "tap_kb_forum" ? "#2563eb" : "var(--text-muted)",
                        fontSize: 10,
                      }}>
                        {getSourceLabel(cfg)}
                      </span>
                    </td>
                    <td>
                      {isEditing ? (
                        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                          <input
                            type="text"
                            value={editKeywords}
                            onChange={(e) => setEditKeywords(e.target.value)}
                            className="form-input"
                            style={{ flex: 1, minWidth: 140, fontSize: 13, padding: "5px 8px" }}
                            onKeyDown={(e) => e.key === "Enter" && saveEdit(cfg)}
                            autoFocus
                          />
                          <div style={{ display: "flex", gap: 4, alignItems: "center", flexShrink: 0 }}>
                            <label style={{ fontSize: 10, color: "var(--text-muted)" }}>条数</label>
                            <input
                              type="number"
                              value={editCrawlCount}
                              onChange={(e) => setEditCrawlCount(Number(e.target.value) || 50)}
                              min={10}
                              max={1000}
                              className="form-input"
                              style={{ width: 60, fontSize: 12, padding: "5px 6px" }}
                            />
                          </div>
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
                      <span style={{
                        display: "inline-flex", alignItems: "center", gap: 3,
                        fontSize: 13, fontWeight: 600, color: "var(--text)",
                      }}>
                        <Hash size={12} color="var(--text-muted)" />
                        {cfg.crawl_count || 50}条
                      </span>
                    </td>
                    <td>
                      {isTapTapPlatform(cfg.platform) ? (
                        isEditing ? (
                          <input
                            type="text"
                            value={editProxyUrl}
                            onChange={(e) => setEditProxyUrl(e.target.value)}
                            placeholder="http://127.0.0.1:7897"
                            className="form-input"
                            style={{ width: "100%", minWidth: 150, fontSize: 12, padding: "5px 8px" }}
                          />
                        ) : (
                          <span
                            title={cfg.proxy_url || "未配置代理"}
                            style={{
                              display: "inline-block",
                              maxWidth: 180,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                              color: cfg.proxy_url ? "var(--text-secondary)" : "var(--text-muted)",
                              fontSize: 12,
                            }}
                          >
                            {cfg.proxy_url || "未配置"}
                          </span>
                        )
                      ) : (
                        <span style={{ color: "var(--text-muted)", fontSize: 12 }}>仅 TapTap 使用</span>
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
                            title="编辑关键词、抓取条数和 TapTap 代理"
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
        搜索词为全局配置，自动应用于游戏管理列表中的所有活跃游戏。
        例如在「抖音」配置「配装计算器, 战备阈值」，设置抓取条数 100 后，管线会对所有活跃游戏抓取抖音上最近 100 条相关视频/帖子，纳入信号计算。
        每个平台只需配置一次，关键词用逗号分隔。抓取条数范围 10-1000 条，建议 50-200 条。
        TapTap（Tap接口配置，非本地IP采集）：TapTap 已停用本地采集，改走自建代理接口(1.117.17.251)每30分钟拉分组 Feed、翻2页、自动去重。配置方式：在 platform_search_configs 表按游戏新增 platform=taptap、keywords=TapTap分组group_id、game_id=归属游戏、enabled=1（每个 group 一条，挂对应游戏）。
      </div>
    </div>
  )
}
