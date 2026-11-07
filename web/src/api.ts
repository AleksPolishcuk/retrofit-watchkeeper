import type { Alert, Asset, Results, Series, Timeline, WhatIfResult } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* keep status text */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

const q = (params: Record<string, string | number>) =>
  Object.entries(params)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&')

export const api = {
  assets: () => get<Asset[]>('/api/assets'),
  results: () => get<Results>('/api/results'),
  allAlerts: () => get<{ source: 'engine' | 'mock'; alerts: Alert[] }>('/api/alerts'),
  alerts: (asset_id: string) => get<{ source: 'engine' | 'mock'; alerts: Alert[] }>(`/api/alerts?${q({ asset_id })}`),
  timeline: (asset_id: string) => get<Timeline>(`/api/timeline?${q({ asset_id })}`),
  whatif: (asset_id: string, time_utc: string, fault_type: string) =>
    get<WhatIfResult>(`/api/whatif?${q({ asset_id, time_utc, fault_type })}`),
  series: (asset_id: string, channel: string, step_min = 15) =>
    get<Series>(`/api/series?${q({ asset_id, channel, step_min })}`),
}
