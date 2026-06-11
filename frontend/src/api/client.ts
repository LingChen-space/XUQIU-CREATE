import type { HistoryLeaderboardOut } from '../types'

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
  triggerPipeline: () => request<any>('/pipeline/run', { method: 'POST' }),
  health: () => request<any>('/health'),
  // 搜索词配置
  getSearchConfigPlatforms: () => request<any[]>('/search-configs/platforms'),
  getSearchConfigs: (gameId?: string) => {
    const qs = gameId ? '?game_id=' + encodeURIComponent(gameId) : ''
    return request<any[]>(`/search-configs${qs}`)
  },
  createSearchConfig: (gameId: string, data: { platform: string; keywords: string; enabled?: boolean }) =>
    request<any>(`/search-configs?game_id=${encodeURIComponent(gameId)}`, { method: 'POST', body: JSON.stringify(data) }),
  updateSearchConfig: (configId: string, data: { keywords?: string; enabled?: boolean }) =>
    request<any>(`/search-configs/${configId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteSearchConfig: (configId: string) =>
    request<any>(`/search-configs/${configId}`, { method: 'DELETE' }),
}
