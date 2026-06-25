import { useEffect, useState } from "react"
import { Eye, Loader2, Radar, Rocket, ShieldAlert } from "lucide-react"

import { api } from "../api/client"
import type { RadarClueLevel, RadarGameGroup, RadarGroupedTerm } from "../types"


const LEVEL_LABEL: Record<RadarClueLevel, string> = {
  urgent: "紧急",
  important: "重要",
  watch: "观察",
}

const PRIORITY_LABEL: Record<string, string> = {
  level_1: "一级核心",
  level_2: "二级长尾",
  level_3: "三级热点",
}

export default function RadarPage() {
  const [groups, setGroups] = useState<RadarGameGroup[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [busyId, setBusyId] = useState<string | null>(null)
  const [toast, setToast] = useState("")

  // 过滤：days="" 全部 / minScore="0" 不限 / perGame="" 全部
  const [days, setDays] = useState("")
  const [minScore, setMinScore] = useState("0")
  const [perGame, setPerGame] = useState("10")
  const [keywordPriority, setKeywordPriority] = useState("")
  const [keywordCategory, setKeywordCategory] = useState("")

  const refresh = async (showLoading = false) => {
    if (showLoading) setLoading(true)
    try {
      const params: { days?: number; min_score?: number; per_game?: number } = {}
      if (days) params.days = Number(days)
      if (Number(minScore) > 0) params.min_score = Number(minScore)
      if (perGame) params.per_game = Number(perGame)
      setGroups(await api.getRadarCluesGrouped(params))
      setError("")
    } catch {
      setError("需求雷达读取失败，请检查后端扫描状态")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh(true)
    const timer = setInterval(() => refresh(false), 60_000)
    return () => clearInterval(timer)
  }, [days, minScore, perGame])

  const promote = async (term: RadarGroupedTerm) => {
    setBusyId(term.id)
    try {
      await api.promoteRadarClue(term.id)
      setToast(`已将「${term.term}」升级为正式需求`)
      await refresh(false)
    } catch {
      setToast("升级失败，请重试")
    } finally {
      setBusyId(null)
      setTimeout(() => setToast(""), 3000)
    }
  }

  if (loading) {
    return (
      <div className="radar-page radar-page-loading">
        <Loader2 className="spinner" size={18} />
        正在读取需求雷达…
      </div>
    )
  }

  if (!groups) {
    return (
      <div className="radar-page radar-page-error">
        <ShieldAlert size={18} />
        {error || "雷达数据不可用"}
      </div>
    )
  }

  const categories = Array.from(new Set(
    groups.flatMap((group) => group.clues.map((term) => term.keyword_category).filter(Boolean))
  ))
  const visibleGroups = groups
    .map((group) => {
      const clues = group.clues.filter((term) =>
        (!keywordPriority || term.keyword_priority === keywordPriority)
        && (!keywordCategory || term.keyword_category === keywordCategory)
      )
      return { ...group, clues, count: clues.length }
    })
    .filter((group) => group.count > 0)
  const totalTerms = visibleGroups.reduce((sum, g) => sum + g.count, 0)

  return (
    <div className="radar-page">
      {toast && <div className="radar-page-toast">{toast}</div>}

      <div className="radar-page-filters">
        <label>时间
          <select value={days} onChange={(e) => setDays(e.target.value)}>
            <option value="">全部</option>
            <option value="7">近7天</option>
            <option value="30">近30天</option>
            <option value="90">近90天</option>
          </select>
        </label>
        <label>最低分
          <select value={minScore} onChange={(e) => setMinScore(e.target.value)}>
            <option value="0">不限</option>
            <option value="30">≥30</option>
            <option value="50">≥50</option>
            <option value="70">≥70</option>
          </select>
        </label>
        <label>每游戏
          <select value={perGame} onChange={(e) => setPerGame(e.target.value)}>
            <option value="10">前10</option>
            <option value="20">前20</option>
            <option value="50">前50</option>
            <option value="">全部</option>
          </select>
        </label>
        <label>词级
          <select value={keywordPriority} onChange={(e) => setKeywordPriority(e.target.value)}>
            <option value="">全部</option>
            <option value="level_1">一级核心</option>
            <option value="level_2">二级长尾</option>
            <option value="level_3">三级热点</option>
          </select>
        </label>
        <label>类别
          <select value={keywordCategory} onChange={(e) => setKeywordCategory(e.target.value)}>
            <option value="">全部</option>
            {categories.map((category) => <option value={category} key={category}>{category}</option>)}
          </select>
        </label>
      </div>

      <div className="radar-page-overview">
        <span><Radar size={14} /> {visibleGroups.length} 个游戏 · {totalTerms} 个标准需求词</span>
        <span className="radar-page-hint">严格按业务词库识别；固定近义词统一归一到标准词</span>
      </div>

      {visibleGroups.length === 0 ? (
        <div className="radar-page-empty">
          <Eye size={18} />
          当前过滤条件下暂无需求词
        </div>
      ) : (
        <div className="radar-page-groups">
          {visibleGroups.map((g) => (
            <section className="radar-game-group" key={g.game_id}>
              <header className="radar-game-group-head">
                <span className="radar-game-name">{g.game_name}</span>
                <span className="radar-game-count">{g.count} 词</span>
                {g.priority_weight >= 3 && <span className="radar-game-priority">高优</span>}
              </header>
              <div className="radar-term-chips">
                {g.clues.map((term) => (
                  <div className={`radar-term-chip ${term.level}`} key={term.id}>
                    <span className={`radar-level-badge ${term.level}`}>{LEVEL_LABEL[term.level]}</span>
                    <span className="radar-term-text" title={term.term}>{term.term}</span>
                    {term.keyword_priority && (
                      <span className={`radar-keyword-priority ${term.keyword_priority}`}>
                        {PRIORITY_LABEL[term.keyword_priority]}
                      </span>
                    )}
                    {term.keyword_category && (
                      <span className="radar-keyword-category" title={term.keyword_category}>
                        {term.keyword_category.includes("工具") ? "工具" : term.keyword_category.includes("攻略") ? "攻略" : "热点"}
                      </span>
                    )}
                    <span className="radar-term-score">{Math.round(term.total_score)}</span>
                    <span className="radar-term-evidence" title={`独立证据 ${term.evidence_count} 条`}>
                      {term.evidence_count}证据
                    </span>
                    {term.merged_count > 1 && (
                      <span className="radar-term-merged" title={`${term.merged_count} 条近义线索合并`}>
                        {term.merged_count}条
                      </span>
                    )}
                    <button
                      className="btn btn-primary btn-xs radar-term-promote"
                      disabled={busyId === term.id}
                      onClick={() => promote(term)}
                    >
                      {busyId === term.id ? <Loader2 className="spinner" size={11} /> : <Rocket size={11} />}
                      升级
                    </button>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
