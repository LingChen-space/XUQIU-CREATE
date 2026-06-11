import { useState } from "react"
import { LayoutDashboard, ClipboardList, Gamepad2, Trophy } from "lucide-react"
import DailyOverview from "./pages/DailyOverview"
import HistoryLeaderboard from "./pages/HistoryLeaderboard"
import DemandManagement from "./pages/DemandManagement"
import GameManagement from "./pages/GameManagement"
import DemandDetailPanel from "./components/DemandDetailPanel"
import type { DemandCard } from "./types"

const NAV_ITEMS = [
  { key: "overview", label: "今日需求", Icon: LayoutDashboard },
  { key: "history", label: "历史排行榜", Icon: Trophy },
  { key: "manage", label: "需求管理", Icon: ClipboardList },
  { key: "games", label: "游戏管理", Icon: Gamepad2 },
] as const

function App() {
  const [view, setView] = useState<"overview" | "history" | "manage" | "games">("overview")
  const [selectedDemand, setSelectedDemand] = useState<DemandCard | null>(null)
  const [activeGameCount, setActiveGameCount] = useState(0)
  const [managedDemandCount, setManagedDemandCount] = useState(0)
  const [historyCount, setHistoryCount] = useState(0)

  const pageTitle =
    view === "overview" ? "今日需求总览"
      : view === "history" ? "历史需求排行榜"
      : view === "manage" ? "需求管理"
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
              className={`sidebar-nav-item ${view === key ? "active" : ""}`}
              onClick={() => { setView(key as typeof view); setSelectedDemand(null) }}
            >
              <Icon /><span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">数据更新 · 每日 06:00</div>
      </aside>

      <div className="main-area">
        <header className="top-bar">
          <span className="page-title">{pageTitle}</span>
          <span className="meta">
            <span>{new Date().toISOString().slice(0, 10)}</span>
            <span className="divider" />
            <span>监控 {activeGameCount} 款游戏</span>
            {view === "history" && (
              <>
                <span className="divider" />
                <span>{historyCount} 条沉淀</span>
              </>
            )}
            {view === "manage" && (
              <>
                <span className="divider" />
                <span>{managedDemandCount} 条需求</span>
              </>
            )}
          </span>
        </header>
        <div className="content-scroll">
          {view === "overview" && (
            <DailyOverview
              onSelect={setSelectedDemand}
              onGameCountChange={setActiveGameCount}
              onDemandCountChange={setManagedDemandCount}
            />
          )}
          {view === "history" && (
            <HistoryLeaderboard
              onSelect={setSelectedDemand}
              onCountChange={setHistoryCount}
            />
          )}
          {view === "manage" && (
            <DemandManagement
              onSelect={setSelectedDemand}
              onCountChange={setManagedDemandCount}
            />
          )}
          {view === "games" && (
            <GameManagement onCountChange={setActiveGameCount} />
          )}
        </div>
      </div>

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
