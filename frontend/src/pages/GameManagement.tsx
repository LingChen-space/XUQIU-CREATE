import { useEffect, useState } from "react"
import { Plus, Search, Edit2, Trash2, Loader2, SlidersHorizontal, Gamepad2 } from "lucide-react"
import { api } from "../api/client"
import type { Game } from "../types"

const GENRES = ["RPG", "FPS", "MOBA", "策略", "休闲", "卡牌", "模拟经营", "吃鸡", "开放世界", "MMORPG", "其他"]
const STATUSES = ["热门", "在运营", "测试中", "已停运"]

const STATUS_CLASS: Record<string, string> = {
  "热门": "active", "在运营": "operating", "测试中": "testing", "已停运": "inactive",
}

interface Props { onCountChange: (n: number) => void }

export default function GameManagement({ onCountChange }: Props) {
  const [games, setGames] = useState<Game[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("全部")
  const [showForm, setShowForm] = useState(false)
  const [editingGame, setEditingGame] = useState<Game | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Game | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const fetchGames = async () => {
    setLoading(true)
    try {
      const list = await api.getGames()
      setGames(list)
      onCountChange(list.filter((g: Game) => g.status !== "已停运").length)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchGames() }, [])

  const openCreate = () => { setEditingGame(null); setError(""); setShowForm(true) }
  const openEdit = (g: Game) => { setEditingGame(g); setError(""); setShowForm(true) }

  const handleSave = async (form: Record<string, string>) => {
    setSaving(true)
    setError("")
    try {
      if (editingGame) {
        await api.updateGame(editingGame.id, form)
      } else {
        await api.createGame(form)
      }
      setShowForm(false)
      await fetchGames()
    } catch (e: any) {
      setError(e.message || "保存失败")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.deleteGame(deleteTarget.id)
      setDeleteTarget(null)
      await fetchGames()
    } catch (e: any) {
      setError(e.message || "删除失败")
    }
  }

  const filtered = games.filter((g) => {
    if (search && !g.name.includes(search) && !g.publisher.includes(search)) return false
    if (statusFilter !== "全部" && g.status !== statusFilter) return false
    return true
  })

  const activeCount = games.filter((g) => g.status !== "已停运").length

  return (
    <div>
      {/* Header */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "flex-start",
        marginBottom: 24
      }}>
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 600, color: "var(--text)", marginBottom: 4 }}>
            游戏管理
          </h2>
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
            维护监控游戏列表，仅「在运营」「热门」「测试中」的游戏会被挖掘需求
          </p>
        </div>
        <button className="btn btn-primary" onClick={openCreate}>
          <Plus size={16} /> 添加游戏
        </button>
      </div>

      {/* Toolbar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        marginBottom: 20, padding: "14px 20px", background: "var(--surface)",
        border: "1px solid var(--border)", borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)"
      }}>
        <div style={{ position: "relative" }}>
          <Search size={16} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
          <input type="text" placeholder="搜索游戏名或厂商..." value={search} onChange={(e) => setSearch(e.target.value)}
            className="form-input" style={{ paddingLeft: 36, width: 240 }} />
        </div>

        <div style={{ width: 1, height: 24, background: "var(--border)" }} />

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <SlidersHorizontal size={14} color="var(--text-muted)" />
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>状态</span>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="form-input" style={{ fontSize: 12, padding: "6px 28px 6px 10px" }}>
            <option value="全部">全部</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <span style={{ fontSize: 12, color: "var(--text-muted)", marginLeft: "auto" }}>
          共 {games.length} 款 · 活跃 {activeCount} 款
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
                <th>游戏名</th>
                <th>品类</th>
                <th>厂商</th>
                <th>状态</th>
                <th>备注</th>
                <th style={{ textAlign: "center", width: 100 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((g) => (
                <tr key={g.id}>
                  <td style={{ fontWeight: 500, fontSize: 14 }}>{g.name}</td>
                  <td style={{ color: "var(--text-secondary)" }}>{g.genre}</td>
                  <td style={{ color: "var(--text-secondary)" }}>{g.publisher || "-"}</td>
                  <td>
                    <span className={`game-status-tag ${STATUS_CLASS[g.status] || "inactive"}`}>
                      {g.status}
                    </span>
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: 12, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {g.notes || "-"}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
                      <button className="btn btn-outline btn-xs" onClick={() => openEdit(g)} title="编辑">
                        <Edit2 size={13} />
                      </button>
                      <button className="btn btn-danger btn-xs" onClick={() => setDeleteTarget(g)} title="删除">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-icon"><Gamepad2 size={24} /></div>
          <p style={{ fontWeight: 500 }}>暂无游戏</p>
          <p style={{ fontSize: 13, marginBottom: 20 }}>点击「添加游戏」开始维护监控列表，系统将仅针对编辑添加的游戏进行需求挖掘。</p>
          <button className="btn btn-primary" onClick={openCreate}>
            <Plus size={16} /> 添加第一款游戏
          </button>
        </div>
      )}

      {/* Game form modal */}
      {showForm && (
        <GameFormModal
          game={editingGame}
          onSave={handleSave}
          onClose={() => { setShowForm(false); setEditingGame(null); setError("") }}
          saving={saving}
          error={error}
        />
      )}

      {/* Delete confirm */}
      {deleteTarget && (
        <div className="modal-overlay">
          <div className="modal-box" style={{ width: 420 }}>
            <div className="modal-header">删除游戏</div>
            <div className="modal-body">
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", background: "var(--red-light)", borderRadius: 8 }}>
                <Trash2 size={18} color="var(--red)" />
                <div>
                  <p style={{ fontSize: 14, fontWeight: 600, color: "var(--red)" }}>{deleteTarget.name}</p>
                  <p style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>
                    删除后不再针对该游戏挖掘需求，已有数据不受影响
                  </p>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setDeleteTarget(null)}>取消</button>
              <button className="btn btn-danger" onClick={handleDelete}>确认删除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Game Form Modal ── */
function GameFormModal({ game, onSave, onClose, saving, error }: {
  game: Game | null; onSave: (f: Record<string, string>) => void; onClose: () => void; saving: boolean; error: string;
}) {
  const [form, setForm] = useState<Record<string, string>>({
    name: game?.name || "",
    genre: game?.genre || "其他",
    publisher: game?.publisher || "",
    status: game?.status || "在运营",
    haoyou_id: game?.haoyou_id || "",
    cover_url: game?.cover_url || "",
    description: game?.description || "",
    notes: game?.notes || "",
  })

  const set = (k: string, v: string) => setForm((prev) => ({ ...prev, [k]: v }))

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">{game ? "编辑游戏" : "添加游戏"}</div>
        <div className="modal-body">
          <div className="form-group">
            <label>游戏名称 *</label>
            <input className="form-input" value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="如：三角洲行动" autoFocus />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="form-group">
              <label>品类</label>
              <select className="form-input" value={form.genre} onChange={(e) => set("genre", e.target.value)}>
                {GENRES.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>状态</label>
              <select className="form-input" value={form.status} onChange={(e) => set("status", e.target.value)}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="form-group">
            <label>厂商</label>
            <input className="form-input" value={form.publisher} onChange={(e) => set("publisher", e.target.value)} placeholder="如：腾讯" />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="form-group">
              <label>好游快爆 ID</label>
              <input className="form-input" value={form.haoyou_id} onChange={(e) => set("haoyou_id", e.target.value)} placeholder="内部 ID" />
            </div>
            <div className="form-group">
              <label>封面图 URL</label>
              <input className="form-input" value={form.cover_url} onChange={(e) => set("cover_url", e.target.value)} placeholder="https://..." />
            </div>
          </div>
          <div className="form-group">
            <label>简介</label>
            <textarea className="form-input" value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="游戏简介..." rows={2} />
          </div>
          <div className="form-group">
            <label>编辑备注</label>
            <textarea className="form-input" value={form.notes} onChange={(e) => set("notes", e.target.value)} placeholder="内部备注信息..." rows={2} />
          </div>
          {error && (
            <div style={{ color: "var(--red)", fontSize: 12, background: "var(--red-light)", padding: "8px 12px", borderRadius: 6 }}>
              {error}
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose} disabled={saving}>取消</button>
          <button className="btn btn-primary" onClick={() => onSave(form)} disabled={saving || !form.name.trim()}>
            {saving ? <Loader2 className="spinner" size={14} /> : null}
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  )
}
