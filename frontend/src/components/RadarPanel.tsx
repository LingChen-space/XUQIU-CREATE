import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  BellRing,
  Check,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Eye,
  Flame,
  Loader2,
  Radar,
  Rocket,
  ShieldAlert,
  X,
} from "lucide-react"

import { api } from "../api/client"
import type { RadarClue, RadarClueLevel, RadarSummary } from "../types"


const LEVEL_LABEL: Record<RadarClueLevel, string> = {
  urgent: "紧急",
  important: "重要",
  watch: "观察",
}

const TYPE_LABEL: Record<RadarClue["type"], string> = {
  new_term: "新词/新实体",
  new_demand: "疑似新需求",
  experience_update: "体验服更新",
  experience_leak: "体验服爆料",
  qualification_change: "资格变化",
  engagement_surge: "互动突增",
  external_solution: "外部解决方案",
}

const LEVEL_ORDER: RadarClueLevel[] = ["urgent", "important", "watch"]

interface Props {
  onDemandPromoted?: () => void
}

export default function RadarPanel({ onDemandPromoted }: Props) {
  const [data, setData] = useState<RadarSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [watchExpanded, setWatchExpanded] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState("")

  const refresh = async (showLoading = false) => {
    if (showLoading) setLoading(true)
    try {
      setData(await api.getRadarSummary())
      setError("")
    } catch {
      setError("早期需求雷达暂时无法读取，请检查后端扫描状态")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh(true)
    const timer = setInterval(() => refresh(false), 60_000)
    return () => clearInterval(timer)
  }, [])

  const grouped = useMemo(() => {
    const result: Record<RadarClueLevel, RadarClue[]> = {
      urgent: [],
      important: [],
      watch: [],
    }
    for (const clue of data?.clues ?? []) result[clue.level].push(clue)
    return result
  }, [data])

  const operate = async (
    clue: RadarClue,
    action: "confirm" | "dismiss" | "promote",
  ) => {
    setBusyId(clue.id)
    try {
      if (action === "confirm") await api.confirmRadarClue(clue.id)
      if (action === "dismiss") await api.dismissRadarClue(clue.id)
      if (action === "promote") {
        await api.promoteRadarClue(clue.id)
        onDemandPromoted?.()
      }
      await refresh(false)
    } finally {
      setBusyId(null)
    }
  }

  if (loading) {
    return (
      <section className="radar-panel radar-panel-loading">
        <Loader2 className="spinner" size={18} />
        正在读取早期需求雷达…
      </section>
    )
  }

  if (!data) {
    return (
      <section className="radar-panel radar-panel-error">
        <ShieldAlert size={18} />
        {error || "雷达数据不可用"}
      </section>
    )
  }

  const coverageRisk = data.coverage.pending + data.coverage.failed + data.coverage.collection_failed

  return (
    <section className="radar-panel">
      <div className="radar-panel-header">
        <div>
          <div className="radar-title">
            <span className="radar-live-dot" />
            <Radar size={18} />
            早期需求雷达
          </div>
          <p>单条新词、体验服事件、隐性需求与互动突增会先在这里等待验证</p>
        </div>
        <div className="radar-summary-chips">
          <span className="radar-chip urgent">紧急 {data.urgent_count}</span>
          <span className="radar-chip important">重要 {data.important_count}</span>
          <span className="radar-chip watch">观察 {data.watch_count}</span>
          <span className="radar-chip surge"><Flame size={12} />突增 {data.surge_count}</span>
          <span className="radar-chip confirmed">今日确认 {data.confirmed_today}</span>
        </div>
      </div>

      <div className={`radar-coverage ${coverageRisk > 0 ? "has-risk" : ""}`}>
        <span>
          扫描覆盖：规则 {data.coverage.rule_completed}/{data.coverage.total_contents}
          ，模型 {data.coverage.model_completed}/{data.coverage.total_contents}
        </span>
        <span>今日新内容 {data.coverage.new_contents}</span>
        <span>待扫描 {data.coverage.pending}</span>
        <span>扫描失败 {data.coverage.failed}</span>
        <span>采集异常 {data.coverage.collection_failed}</span>
        {coverageRisk > 0 && <AlertTriangle size={14} />}
      </div>

      {data.clues.length === 0 ? (
        <div className="radar-empty">
          <Eye size={18} />
          暂无待验证线索，雷达仍在持续扫描
        </div>
      ) : (
        <div className="radar-levels">
          {LEVEL_ORDER.map((level) => {
            const clues = grouped[level]
            if (clues.length === 0) return null
            const collapsed = level === "watch" && !watchExpanded
            return (
              <div className={`radar-level radar-level-${level}`} key={level}>
                <button
                  type="button"
                  className="radar-level-heading"
                  onClick={() => level === "watch" && setWatchExpanded((value) => !value)}
                >
                  <span>{LEVEL_LABEL[level]}线索 · {clues.length}</span>
                  {level === "watch" && (
                    watchExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />
                  )}
                </button>
                {!collapsed && (
                  <div className="radar-clue-list">
                    {clues.map((clue) => (
                      <RadarClueCard
                        key={clue.id}
                        clue={clue}
                        busy={busyId === clue.id}
                        onOperate={operate}
                      />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

function RadarClueCard({
  clue,
  busy,
  onOperate,
}: {
  clue: RadarClue
  busy: boolean
  onOperate: (clue: RadarClue, action: "confirm" | "dismiss" | "promote") => void
}) {
  return (
    <article className={`radar-clue-card ${clue.level}`}>
      <div className="radar-clue-main">
        <div className="radar-clue-meta">
          <span className={`radar-level-badge ${clue.level}`}>{LEVEL_LABEL[clue.level]}</span>
          <span className="radar-game-badge">{clue.game_name}</span>
          <span>{TYPE_LABEL[clue.type]}</span>
          <span>评分 {Math.round(clue.total_score)}</span>
        </div>
        <h4>{clue.title}</h4>
        <p>{clue.summary || clue.trigger_reason}</p>
        <div className="radar-reason">{clue.trigger_reason}</div>
        {clue.evidence.length > 0 && (
          <div className="radar-evidence-list">
            {clue.evidence.slice(0, 3).map((item) => (
              item.url ? (
                <a key={item.id} href={item.url} target="_blank" rel="noreferrer">
                  <span>{item.platform}</span>
                  {item.title || "查看原文"}
                  <ExternalLink size={12} />
                </a>
              ) : (
                <span className="radar-evidence-no-link" key={item.id}>
                  {item.platform} · {item.title}
                </span>
              )
            ))}
          </div>
        )}
      </div>
      <div className="radar-actions">
        <button disabled={busy} onClick={() => onOperate(clue, "confirm")} className="btn btn-outline btn-xs">
          {busy ? <Loader2 className="spinner" size={12} /> : <Check size={12} />}
          确认线索
        </button>
        <button disabled={busy} onClick={() => onOperate(clue, "promote")} className="btn btn-primary btn-xs">
          <Rocket size={12} />
          升级需求
        </button>
        <button disabled={busy} onClick={() => onOperate(clue, "dismiss")} className="btn btn-ghost btn-xs">
          <X size={12} />
          忽略30天
        </button>
      </div>
    </article>
  )
}
