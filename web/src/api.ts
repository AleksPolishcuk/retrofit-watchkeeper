import { snapshotFile } from './snapshot'
import type { Alert, Archived, Asset, DataHealth, LiveItem, LiveState, Results, Series, Timeline, WhatIfResult } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export const SNAPSHOT = import.meta.env.VITE_SNAPSHOT === '1'

async function get<T>(path: string): Promise<T> {
  let url = path
  if (SNAPSHOT) {
    const f = snapshotFile(path)
    if (!f) throw new ApiError(404, 'not part of the static snapshot')
    url = `${import.meta.env.BASE_URL}snapshot/${f}`
  }
  const res = await fetch(url)
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
  archive: (asset_id: string) => get<Archived[]>(`/api/alerts/archive?${q({ asset_id })}`),
  live: () => get<LiveItem[]>('/api/live'),
  liveOne: (asset_id: string) => get<LiveState>(`/api/live/${encodeURIComponent(asset_id)}`),
  dataHealthNow: (asset_id: string) => get<DataHealth>(`/api/data-health?${q({ asset_id })}`),
  dataHealth: (asset_id: string, as_of: string) => get<DataHealth>(`/api/data-health?${q({ asset_id, as_of })}`),
  allAlerts: () => get<{ source: 'engine' | 'mock'; alerts: Alert[] }>('/api/alerts'),
  alerts: (asset_id: string) => get<{ source: 'engine' | 'mock'; alerts: Alert[] }>(`/api/alerts?${q({ asset_id })}`),
  timeline: (asset_id: string) => get<Timeline>(`/api/timeline?${q({ asset_id })}`),
  whatif: (asset_id: string, time_utc: string, fault_type: string) =>
    get<WhatIfResult>(`/api/whatif?${q({ asset_id, time_utc, fault_type })}`),
  series: (asset_id: string, channel: string, step_min = 15) =>
    get<Series>(`/api/series?${q({ asset_id, channel, step_min })}`),
}
