import { useState } from "react"
import { LayoutDashboard, ClipboardList, Gamepad2, Trophy, Search, MessageSquareWarning, Radio } from "lucide-react"
import DailyOverview from "./pages/DailyOverview"
import HistoryLeaderboard from "./pages/HistoryLeaderboard"
import DemandManagement from "./pages/DemandManagement"
import GameManagement from "./pages/GameManagement"
import SearchConfigPage from "./pages/SearchConfigPage"
import MonitoringData from "./pages/MonitoringData"
import DemandDetailPanel from "./components/DemandDetailPanel"
import type { DemandCard } from "./types"

const NAV_ITEMS = [
  { key: "overview", label: "今日需求", Icon: LayoutDashboard },
  { key: "history", label: "历史排行榜", Icon: Trophy },
  { key: "manage", label: "需求管理", Icon: ClipboardList },
  { key: "monitor", label: "监控数据", Icon: Radio },
  { key: "search", label: "搜索词配置", Icon: Search },
  { key: "games", label: "游戏管理", Icon: Gamepad2 },
] as const

function App() {
  const [view, setView] = useState<"overview" | "history" | "manage" | "monitor" | "search" | "games">("overview")
  const [selectedDemand, setSelectedDemand] = useState<DemandCard | null>(null)
  const [activeGameCount, setActiveGameCount] = useState(0)
  const [managedDemandCount, setManagedDemandCount] = useState(0)
  const [historyCount, setHistoryCount] = useState(0)

  const pageTitle =
    view === "overview" ? "今日需求总览"
      : view === "history" ? "历史需求排行榜"
      : view === "manage" ? "需求管理"
      : view === "monitor" ? "监控数据"
      : view === "search" ? "搜索词配置"
      : "游戏管理"

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-logo-row">
            <img src="/hykb-logo.png" alt="好游快爆" className="brand-logo" />
            <div className="brand-text">
          <h1>需求发生工具</h1>
          <div className="subtitle">好游快爆 · 智能挖掘</div>
            </div>
          </div>
        </div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ key, label, Icon }) => (
            <button
              key={key}
              className={`sidebar-nav-item${view === key ? " active" : ""}`}
              onClick={() => { setView(key); setSelectedDemand(null) }}
            >
              <Icon size={16} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="stat-row">
            <span>活跃游戏</span>
            <strong>{activeGameCount}</strong>
          </div>
          <div className="stat-row">
            <span>历史沉淀</span>
            <strong>{historyCount}</strong>
          </div>
          <div className="stat-row">
            <span>需求管理</span>
            <strong>{managedDemandCount}</strong>
          </div>
          <div className="sidebar-notice">
            <MessageSquareWarning size={18} style={{ color: '#fbbf24', flexShrink: 0, marginTop: 2, filter: 'drop-shadow(0 0 6px rgba(251,191,36,0.35))' }} />
            <p>使用问题或优化建议<br/><strong style={{ color: '#fbbf24', fontSize: '13px', letterSpacing: '0.04em' }}>◆ 提交拓展组-凌晨两点</strong></p>
          </div>
        </div>
      </aside>
      <main className="main-area">
        <header className="top-bar">
          <h1 className="page-title">{pageTitle}</h1>
        </header>
        <div className="content-scroll">
          {view === "overview" && (
            <DailyOverview
              onSelect={(d) => setSelectedDemand(d)}
              onGameCountChange={setActiveGameCount}
              onDemandCountChange={(n) => {}}
            />
          )}
          {view === "history" && (
            <HistoryLeaderboard
              onSelect={(d) => setSelectedDemand(d)}
              onCountChange={setHistoryCount}
            />
          )}
          {view === "manage" && (
            <DemandManagement
              onSelect={(d) => setSelectedDemand(d)}
              onCountChange={setManagedDemandCount}
            />
          )}
          {view === "monitor" && <MonitoringData />}
          {view === "search" && <SearchConfigPage />}
          {view === "games" && (
            <GameManagement onCountChange={setActiveGameCount} />
          )}
        </div>
      </main>
      {selectedDemand && (
        <DemandDetailPanel
          demand={selectedDemand}
          onClose={() => setSelectedDemand(null)}
        />
      )}
    </div>
  )
}

export default App
