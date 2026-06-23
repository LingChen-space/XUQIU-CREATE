import type { HistoryLeaderboardOut } from '../types'
import type { MonitorContentList, ContentStats } from '../types'
import type { CrawlProgress, PipelineRunResult, TapKbSyncStatus } from '../types'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || `${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  getDashboardSummary: () => request<any>('/dashboard/summary'),
  getTodayDemands: (limit = 50) => request<any[]>(`/demands/today?limit=${limit}`),
  getDemands: (params: Record<string, string> = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request<any[]>(`/demands${qs ? '?' + qs : ''}`)
  },
  getHistoryLeaderboard: (minScore = 0, maxDays = 90, limit = 50) =>
    request<HistoryLeaderboardOut>(`/demands/history?min_score=${minScore}&max_days=${maxDays}&limit=${limit}`),
  getDemandDetail: (id: string) => request<any>(`/demands/${id}`),
  updateDemand: (id: string, data: { status?: string; notes?: string }) =>
    request<any>(`/demands/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  getLatestReport: () => request<any>('/reports/latest'),
  getReportByDate: (date: string) => request<any>(`/reports/${date}`),
  getGames: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request<any[]>(`/games${qs}`)
  },
  createGame: (data: any) => request<any>('/games', { method: 'POST', body: JSON.stringify(data) }),
  updateGame: (id: string, data: any) => request<any>(`/games/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteGame: (id: string) => request<any>(`/games/${id}`, { method: 'DELETE' }),
  triggerPipeline: (options: { force_recrawl?: boolean } = {}) =>
    request<PipelineRunResult>('/pipeline/run', { method: 'POST', body: JSON.stringify(options) }),
  health: () => request<any>('/health'),
  // 搜索词配置
  getSearchConfigPlatforms: () => request<any[]>('/search-configs/platforms'),
  getSearchConfigs: () => request<any[]>('/search-configs'),
  createSearchConfig: (data: { platform: string; keywords: string; enabled?: boolean; crawl_count?: number; proxy_url?: string | null }) =>
    request<any>('/search-configs', { method: 'POST', body: JSON.stringify(data) }),
  updateSearchConfig: (configId: string, data: { keywords?: string; enabled?: boolean; crawl_count?: number; proxy_url?: string | null }) =>
    request<any>(`/search-configs/${configId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteSearchConfig: (configId: string) =>
    request<any>(`/search-configs/${configId}`, { method: 'DELETE' }),
  // 监控数据
  getContents: (params: Record<string, string> = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request<MonitorContentList>(`/contents${qs ? '?' + qs : ''}`)
  },
  getContentStats: (days = 7) => request<ContentStats>(`/contents/stats?days=${days}`),

  // 采集进度
  getCrawlProgress: () => request<CrawlProgress>('/monitor/crawl/progress'),
  retryCrawl: (
    platform: string,
    keyword: string,
    crawlCount = 50,
    proxyMode: "auto" | "none" | "proxy" = "auto",
    douyinBrowserMethod: "method1" | "method2" = "method1",
  ) =>
    request<any>('/monitor/crawl/retry', {
      method: 'POST',
      body: JSON.stringify({
        platform,
        keyword,
        crawl_count: crawlCount,
        proxy_mode: proxyMode,
        douyin_browser_method: douyinBrowserMethod,
      }),
    }),
  startDouyinLogin: () => request<any>('/monitor/douyin/login', { method: 'POST' }),
  getDouyinLoginStatus: () => request<any>('/monitor/douyin/login'),
  syncTapKbForum: (options: { days?: number; force?: boolean } = {}) =>
    request<TapKbSyncStatus>('/external-monitors/tap-kb/sync', {
      method: 'POST',
      body: JSON.stringify({ days: options.days ?? 30, force: options.force ?? false }),
    }),
  getTapKbForumStatus: () => request<TapKbSyncStatus>('/external-monitors/tap-kb/status'),
  acknowledgeTapKbForum: () =>
    request<TapKbSyncStatus>('/external-monitors/tap-kb/ack', { method: 'POST' }),
}
