export interface SignalSnapshot {
  repeat_question: number
  info_scatter: number
  grassroots_tool: number
  scarcity: number
  mechanism_complexity: number
  content_heat: number
}

export interface LLMAnalysis {
  high_freq_questions: string[]
  info_gap: string
  tool_feasibility: number
  reasoning: string
  tool_type_suggestion: string
}

export interface EvidencePost {
  id: string
  platform: string
  url: string
  title: string
  relevance: string
}

export interface DemandCard {
  id: string
  game_id: string
  game_name: string
  game_genre: string
  tool_type: string
  title: string
  description: string
  potential_score: number
  tool_feasibility: number
  status: string
  signals: SignalSnapshot
  llm_reasoning: string
  demand_date: string
  demand_level: string
  created_at: string
}

export interface DemandDetail extends DemandCard {
  game_publisher: string
  llm_analysis: LLMAnalysis
  evidence_posts: EvidencePost[]
  similar_past_demands: { id: string; title: string; demand_date: string; potential_score: number }[]
  notes: string
}

export interface DashboardSummary {
  today_date: string
  total_demands_today: number
  top_demands: DemandCard[]
  trending_games: { id: string; name: string; genre: string; demand_count: number }[]
  tool_type_distribution: Record<string, number>
  latest_report_summary: string
}

export interface Game {
  id: string
  name: string
  genre: string
  publisher: string
  status: string
  haoyou_id: string
  cover_url: string
  description: string
  notes: string
  created_at: string
  updated_at: string
}

export interface DemandHistoryCard {
  id: string
  game_id: string
  game_name: string
  game_genre: string
  tool_type: string
  title: string
  description: string
  potential_score: number
  tool_feasibility: number
  status: string
  demand_level: string
  demand_date: string
  created_at: string
  llm_reasoning: string
  signal_scores: Record<string, number>
}

export interface HistoryLeaderboardOut {
  date_range_start: string
  date_range_end: string
  total_ranked: number
  leaderboard: DemandHistoryCard[]
}
