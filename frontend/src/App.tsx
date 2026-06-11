import { useState } from "react"
import { LayoutDashboard, ClipboardList, Gamepad2, Trophy, Search } from "lucide-react"
import DailyOverview from "./pages/DailyOverview"
import HistoryLeaderboard from "./pages/HistoryLeaderboard"
import DemandManagement from "./pages/DemandManagement"
import GameManagement from "./pages/GameManagement"
import SearchConfigPage from "./pages/SearchConfigPage"
import DemandDetailPanel from "./components/DemandDetailPanel"
import type { DemandCard } from "./types"

const NAV_ITEMS = [
  { key: "overview", label: "今日需求", Icon: LayoutDashboard },
  { key: "history", label: "历史排行榜", Icon: Trophy },
  { key: "manage", label: "需求管理", Icon: ClipboardList },
  { key: "search", label: "搜索词配置", Icon: Search },
  { key: "games", label: "游戏管理", Icon: Gamepad2 },
] as const

function App() {
  const [view, setView] = useState<"overview" | "history" | "manage" | "search" | "games">("overview")
  const [selectedDemand, setSelectedDemand] = useState<DemandCard | null>(null)
  const [activeGameCount, setActiveGameCount] = useState(0)
  const [managedDemandCount, setManagedDemandCount] = useState(0)
  const [historyCount, setHistoryCount] = useState(0)

  const pageTitle =
    view === "overview" ? "今日需求总览"
      : view === "history" ? "历史需求排行榜"
      : view === "manage" ? "需求管理"
      : view === "search" ? "搜索词配置"
      : "游戏管理"

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1>需求发生工具</h1>
          <div className="subtitle">好游快爆 · 智能挖掘</div>
        </div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ key, label, Icon }) => (
            <button
              key={key}
              className={`nav-item${view === key ? " active" : ""}`}
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
        </div>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <h1>{pageTitle}</h1>
        </header>
        <div className="page-body">
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
          {view === "search" && <SearchConfigPage />}
          {view === "games" && (
            <GameManagement onCountChange={setActiveGameCount} />
          )}
        </div>
      </main>
      {selectedDemand && (
        <aside className="detail-panel">
          <DemandDetailPanel
            demand={selectedDemand}
            onClose={() => setSelectedDemand(null)}
            onUpdated={() => setSelectedDemand(null)}
          />
        </aside>
      )}
    </div>
  )
}

export default App
