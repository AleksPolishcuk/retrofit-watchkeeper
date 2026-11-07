// What the overview shows, derived from the alerts and the review log. Pure functions, no React and no network.
// Nothing here invents a health figure: a pump is described only by the open cases it has and their priority.

export type Level = 'watch' | 'possible' | 'likely' | 'very_likely'
export const LEVELS: Level[] = ['very_likely', 'likely', 'possible', 'watch'] // strongest first
export const URGENT: Level[] = ['very_likely', 'likely']

/** A missing stage counts as Watch, the same as the priority filter does. */
export const rankOf = (s?: string): number => (s === 'very_likely' ? 3 : s === 'likely' ? 2 : s === 'possible' ? 1 : 0)
export const levelOf = (s?: string): Level => LEVELS[3 - rankOf(s)]

export interface CaseLike {
  id: string
  head: { asset_id: string; stage?: string; alert_time_utc: string }
}
type Reviews = Record<string, { status: string }>

export const isClosed = (id: string, reviews: Reviews) => reviews[id]?.status === 'closed'
export const openCases = <T extends CaseLike>(cases: T[], reviews: Reviews): T[] => cases.filter((c) => !isClosed(c.id, reviews))

const zero = (): Record<Level, number> => ({ very_likely: 0, likely: 0, possible: 0, watch: 0 })

export function levelCounts(cases: CaseLike[], reviews: Reviews): Record<Level, number> {
  const out = zero()
  for (const c of openCases(cases, reviews)) out[levelOf(c.head.stage)] += 1
  return out
}

export interface PumpRow {
  asset_id: string
  open: number
  worst: Level | null // null: no open case
  counts: Record<Level, number>
}

/** One row per pump, in the order given. A pump without open cases says so; it is not called healthy. */
export function pumpRows(assetIds: string[], cases: CaseLike[], reviews: Reviews): PumpRow[] {
  return assetIds.map((id) => {
    const mine = openCases(cases.filter((c) => c.head.asset_id === id), reviews)
    const counts = zero()
    for (const c of mine) counts[levelOf(c.head.stage)] += 1
    const worst = LEVELS.find((l) => counts[l] > 0) ?? null
    return { asset_id: id, open: mine.length, worst, counts }
  })
}

/** The open cases to look at first: strongest priority, then the most recent. */
export function attention<T extends CaseLike>(cases: T[], reviews: Reviews, n: number): T[] {
  return openCases(cases, reviews)
    .sort((a, b) => rankOf(b.head.stage) - rankOf(a.head.stage) || b.head.alert_time_utc.localeCompare(a.head.alert_time_utc))
    .slice(0, n)
}

export interface Headline {
  total: number
  open: number
  urgent: number // open cases at Likely or Very likely
  pumpsUrgent: number // pumps with at least one such case
  reviewed: number // cases a person has acted on (any status other than open)
  topId: string | null
}

export function headline(cases: CaseLike[], reviews: Reviews): Headline {
  const open = openCases(cases, reviews)
  const urgent = open.filter((c) => rankOf(c.head.stage) >= 2)
  return {
    total: cases.length,
    open: open.length,
    urgent: urgent.length,
    pumpsUrgent: new Set(urgent.map((c) => c.head.asset_id)).size,
    reviewed: cases.filter((c) => (reviews[c.id]?.status ?? 'open') !== 'open').length,
    topId: attention(cases, reviews, 1)[0]?.id ?? null,
  }
}
