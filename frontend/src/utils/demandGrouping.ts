import type { DemandCard } from "../types"

export interface DemandGameGroup {
  gameId: string
  gameName: string
  gameGenre: string
  demands: DemandCard[]
  count: number
  topScore: number
  categories: string[]
  topDemand: DemandCard
}

export const DEMAND_CATEGORY_LABELS: Record<DemandCard["demand_category"], string> = {
  tool: "工具需求",
  experience_server: "体验服需求",
}

export function getDemandDisplayTitle(demand: DemandCard) {
  if (demand.demand_category === "experience_server" && demand.experience_focus?.length > 0) {
    return `${demand.game_name} · ${demand.experience_focus.join(" / ")}`
  }
  return demand.title
}

export function getDemandBranchTitle(demand: DemandCard) {
  const fallback = demand.experience_focus?.join(" / ") || demand.title
  const displayTitle = getDemandDisplayTitle(demand).trim()
  const gameName = demand.game_name.trim()

  if (!gameName || !displayTitle.startsWith(gameName)) return displayTitle || fallback

  const branchTitle = displayTitle
    .slice(gameName.length)
    .replace(/^[\s·:：|｜\-—]+/, "")
    .trim()

  return branchTitle || fallback
}

export function groupDemandsByGame(demands: DemandCard[]): DemandGameGroup[] {
  const grouped = new Map<string, DemandCard[]>()

  demands.forEach((demand) => {
    const key = demand.game_id || demand.game_name
    const items = grouped.get(key) || []
    items.push(demand)
    grouped.set(key, items)
  })

  return Array.from(grouped.entries())
    .map(([gameId, items]) => {
      const sortedDemands = [...items].sort(compareDemandPriority)
      const topDemand = sortedDemands[0]
      const categories = Array.from(
        new Set(sortedDemands.map((demand) => DEMAND_CATEGORY_LABELS[demand.demand_category] || "需求"))
      )

      return {
        gameId,
        gameName: topDemand.game_name,
        gameGenre: topDemand.game_genre,
        demands: sortedDemands,
        count: sortedDemands.length,
        topScore: Math.round(topDemand.potential_score),
        categories,
        topDemand,
      }
    })
    .sort((a, b) => {
      if (b.topScore !== a.topScore) return b.topScore - a.topScore
      if (b.count !== a.count) return b.count - a.count
      return a.gameName.localeCompare(b.gameName, "zh-CN")
    })
}

function compareDemandPriority(a: DemandCard, b: DemandCard) {
  if (b.potential_score !== a.potential_score) return b.potential_score - a.potential_score
  return new Date(b.demand_date).getTime() - new Date(a.demand_date).getTime()
}
