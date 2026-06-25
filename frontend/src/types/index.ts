export interface SignalSnapshot {
  repeat_question: number
  info_scatter: number
  grassroots_tool: number
  scarcity: number
  mechanism_complexity: number
  content_heat: number
  external_platform_tool: number
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

export interface ExperienceServerInsight {
  update_content: string
  leak_content: string
  recruitment_status: string
  recruitment_time: string
  current_stage: string
  recruitment_open: boolean
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
  demand_category: "tool" | "experience_server"
  experience_focus: string[]
  experience_insight: ExperienceServerInsight | null
  launched_tool_matches: string[]
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
  today_analysis_completed: boolean
  total_demands_today: number
  top_demands: DemandCard[]
  trending_games: { id: string; name: string; genre: string; demand_count: number }[]
  tool_type_distribution: Record<string, number>
  latest_report_summary: string
  daily_analysis: DailySummaryAnalysis
}

export interface DemandLevelBreakdown {
  s_count: number
  a_count: number
  b_count: number
  c_count: number
}

export interface DailySummaryAnalysis {
  total_demands: number
  avg_potential_score: number
  level_breakdown: DemandLevelBreakdown
  hot_tool_types: { type: string; count: number }[]
  hot_genres: { genre: string; count: number }[]
  signal_summary: Record<string, number>
  top_recommendations: string[]
  summary_text: string
}

export interface Game {
  id: string
  name: string
  genre: string
  publisher: string
  status: string
  haoyou_id: string
  cover_url: string
  priority_weight: number
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
  demand_category: "tool" | "experience_server"
  experience_focus: string[]
  experience_insight: ExperienceServerInsight | null
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

export interface PlatformOption {
  key: string
  label: string
}

export interface SearchConfig {
  id: string
  game_id: string | null
  platform: string
  keywords: string
  enabled: boolean
  crawl_count: number
  proxy_url: string | null
  source_key: string
  external_group: string
  external_id: string
  last_synced_at: string | null
  created_at: string
  updated_at: string
}
export interface MonitorContent {
  id: string
  game_id: string
  platform: string
  content_type: string
  source_id: string
  url: string
  title: string
  body: string
  author: string
  view_count: number
  like_count: number
  comment_count: number
  share_count: number
  hot_score: number
  published_at: string
  collected_at: string
  source_key: string
}

export interface MonitorContentList {
  total: number
  offset: number
  limit: number
  items: MonitorContent[]
}

export interface ContentStats {
  total: number
  days: number
  by_platform: Record<string, number>
  by_source: Record<string, number>
  by_date: { date: string; count: number }[]
}

export interface ExternalSyncStats {
  fetched: number
  inserted?: number
  duplicates?: number
  unmatched_games?: number
  invalid?: number
  upserted?: number
  skipped?: number
}

export interface TapKbNewRecord {
  platform: string
  game_name: string
  title: string
  url: string
  published_at: string
}

export interface TapKbSyncStatus {
  source_key: "tap_kb_forum"
  status: "idle" | "not_configured" | "completed" | "failed"
  message: string
  contents: ExternalSyncStats
  configs: ExternalSyncStats
  last_ids: Record<string, number>
  last_new_contents: number
  last_new_records: TapKbNewRecord[]
  has_unread_new_contents: boolean
  last_sync_reason: "startup" | "manual" | "pipeline" | "auto" | string
  acknowledged_at: string | null
  synced_at: string | null
}

export interface CrawlProgressReason {
  type: "platform_shortfall" | "duplicate" | "filtered_unrelated" | "partial_failed" | "failed" | "other"
  label: string
  count: number
  detail: string
}

export interface CrawlProgressDetail {
  target_count: number
  fetched_count: number
  ingested_count: number
  shortfall_count: number
  reasons: CrawlProgressReason[]
  summary: string
}

export interface CrawlProgressRecord {
  id: string
  platform: string
  keyword: string
  crawl_count: number
  status: "pending" | "running" | "completed" | "failed"
  items_fetched: number
  items_ingested: number
  error_msg: string | null
  result_detail: CrawlProgressDetail | null
  started_at: string | null
  completed_at: string | null
}

export interface CrawlProgress {
  total: number
  completed: number
  failed: number
  running: number
  pending: number
  records: CrawlProgressRecord[]
}

export interface PipelineIngestResult {
  status: "idle" | "mock" | "mock_no_configs" | "no_games" | "no_active_games" | "skipped_completed" | "crawled" | "failed"
  message: string
  ingested_count: number
  combos_total: number
  force_recrawl?: boolean
}

export interface PipelineRunResult {
  ok: boolean
  status: "completed" | "skipped" | "failed"
  message: string
  external_sync?: TapKbSyncStatus | null
  ingest: PipelineIngestResult
  signals_count: number
  demands_count: number
  report_id: string | null
}

export type RadarClueLevel = "urgent" | "important" | "watch"
export type RadarClueStatus = "pending" | "confirmed" | "dismissed" | "promoted"
export type RadarClueType =
  | "new_term"
  | "new_demand"
  | "experience_update"
  | "experience_leak"
  | "qualification_change"
  | "engagement_surge"
  | "external_solution"

export interface RadarEvidence {
  id: string
  platform: string
  title: string
  url: string
  published_at: string
}

export interface RadarCoverage {
  total_contents: number
  new_contents: number
  rule_completed: number
  model_completed: number
  pending: number
  failed: number
  collection_success: number
  collection_failed: number
}

export interface RadarClue {
  id: string
  game_id: string
  game_name: string
  type: RadarClueType
  level: RadarClueLevel
  status: RadarClueStatus
  title: string
  summary: string
  term: string
  trigger_reason: string
  evidence: RadarEvidence[]
  scores: Record<string, unknown>
  engagement: Record<string, unknown>
  suggested_tool_type: string
  total_score: number
  first_seen_at: string
  last_seen_at: string
  suppressed_until: string | null
  demand_id: string | null
}

export interface RadarSummary {
  urgent_count: number
  important_count: number
  watch_count: number
  surge_count: number
  confirmed_today: number
  coverage: RadarCoverage
  clues: RadarClue[]
}

export interface RadarGroupedTerm {
  id: string
  term: string
  level: RadarClueLevel
  total_score: number
  clue_type: RadarClueType
  demand_id: string | null
  status: RadarClueStatus
  merged_count: number
  keyword_priority: "level_1" | "level_2" | "level_3" | ""
  keyword_category: string
  matched_alias: string
  evidence_count: number
}

export interface RadarGameGroup {
  game_id: string
  game_name: string
  priority_weight: number
  count: number
  clues: RadarGroupedTerm[]
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  streaming?: boolean
  error?: boolean
}
