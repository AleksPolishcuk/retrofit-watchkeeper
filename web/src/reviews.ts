// Incident review log. Pure logic with no React and no network: it is kept in this browser only (localStorage) and can be exported.
// Watchkeeper never writes to a machine and the API never writes: this log records what a person decided about an alert.

export type Status = 'open' | 'inspection' | 'result' | 'recovery' | 'closed'
export type Outcome = 'no_fault' | 'further' | 'confirmed' | 'false_alarm'
export type ClosedReason = 'no_fault' | 'false_alarm' | 'recovered'

export const STATUSES: Status[] = ['open', 'inspection', 'result', 'recovery', 'closed']
export const STATUS_LABEL: Record<Status, string> = { open: 'Open', inspection: 'On inspection', result: 'Result recorded', recovery: 'Recovery check', closed: 'Closed' }
export const OUTCOME_LABEL: Record<Outcome, string> = { no_fault: 'No fault found', further: 'Needs further inspection', confirmed: 'Fault confirmed', false_alarm: 'Marked as false alarm' }
/** How long the readings that raised the alert must stay normal before a person closes the case. A pilot setting to adjust per pump, not a result. */
export const RECOVERY_HOURS = 24
export const STORE = 'watchkeeper.reviews.v1'

export interface LogEntry {
  at: string
  event: string
  detail?: string
}

export interface Review {
  incident_id: string
  asset_id: string
  fault_type: string // what the model suggested when the case was first opened
  model_version?: string
  status: Status
  first_seen: string
  first_decision_at?: string
  outcome?: Outcome
  outcome_at?: string
  actual?: string // what was actually found, when a fault was confirmed
  note?: string
  recovery_started_at?: string
  closed_at?: string
  closed_reason?: ClosedReason
  came_back_count: number
  log: LogEntry[]
}

export type Action =
  | { type: 'view' }
  | { type: 'approve' }
  | { type: 'false_alarm' }
  | { type: 'outcome'; outcome: 'no_fault' | 'further' | 'confirmed'; actual?: string; note?: string }
  | { type: 'close' }
  | { type: 'reinspect' }
  | { type: 'start_recovery' }
  | { type: 'confirm_recovery' }
  | { type: 'came_back' }
  | { type: 'reopen' }

/** The parts of an incident this module needs (matches Incident in plain.ts). */
export interface IncidentLike {
  id: string
  head: { alert_id: string; asset_id: string; fault_type: string; alert_time_utc: string; model_version?: string; evidence?: { channel: string }[] }
  members: { alert_id: string; alert_time_utc: string }[]
}

export function newReview(inc: IncidentLike, now: string): Review {
  return {
    incident_id: inc.id,
    asset_id: inc.head.asset_id,
    fault_type: inc.head.fault_type,
    model_version: inc.head.model_version,
    status: 'open',
    first_seen: now,
    came_back_count: 0,
    log: [{ at: now, event: 'Case opened in this browser' }],
  }
}

/** Which actions make sense now. The interface shows only these. */
export function allowed(r: Review | undefined): Action['type'][] {
  const s = r?.status ?? 'open'
  if (s === 'open') return ['approve', 'false_alarm']
  if (s === 'inspection') return ['outcome']
  if (s === 'result') return r?.outcome === 'no_fault' ? ['close'] : r?.outcome === 'further' ? ['reinspect'] : r?.outcome === 'confirmed' ? ['start_recovery'] : []
  if (s === 'recovery') return ['confirm_recovery', 'came_back']
  return ['reopen']
}

function add(r: Review, now: string, event: string, detail?: string): LogEntry[] {
  return [...r.log, detail ? { at: now, event, detail } : { at: now, event }]
}

/** One step of the lifecycle. An action that does not fit the current status returns the same review unchanged. */
export function apply(prev: Review | undefined, inc: IncidentLike, action: Action, now: string): Review {
  const r = prev ?? newReview(inc, now)
  if (action.type === 'view') return r
  if (!allowed(r).includes(action.type)) return r
  switch (action.type) {
    case 'approve':
      return { ...r, status: 'inspection', first_decision_at: r.first_decision_at ?? now, log: add(r, now, 'Inspection approved') }
    case 'false_alarm':
      return { ...r, status: 'closed', outcome: 'false_alarm', outcome_at: now, closed_at: now, closed_reason: 'false_alarm', first_decision_at: r.first_decision_at ?? now, log: add(r, now, 'Marked as false alarm, case closed') }
    case 'outcome': {
      const detail = action.outcome === 'confirmed' && action.actual ? `found: ${action.actual}` : undefined
      return { ...r, status: 'result', outcome: action.outcome, outcome_at: now, actual: action.outcome === 'confirmed' ? action.actual : undefined, note: action.note?.trim() || undefined, log: add(r, now, `Inspection result: ${OUTCOME_LABEL[action.outcome]}`, detail) }
    }
    case 'close':
      return { ...r, status: 'closed', closed_at: now, closed_reason: 'no_fault', log: add(r, now, 'Case closed: no fault found') }
    case 'reinspect':
      return { ...r, status: 'inspection', outcome: undefined, actual: undefined, log: add(r, now, 'Back to inspection') }
    case 'start_recovery':
      return { ...r, status: 'recovery', recovery_started_at: now, log: add(r, now, 'Repair done, recovery check started', `${RECOVERY_HOURS} h of normal readings needed`) }
    case 'confirm_recovery':
      return { ...r, status: 'closed', closed_at: now, closed_reason: 'recovered', log: add(r, now, 'Recovery confirmed, case closed') }
    case 'came_back':
      return { ...r, status: 'inspection', outcome: undefined, actual: undefined, recovery_started_at: undefined, came_back_count: r.came_back_count + 1, log: add(r, now, 'The problem came back, back to inspection') }
    case 'reopen':
      return { ...r, status: 'open', outcome: undefined, actual: undefined, closed_at: undefined, closed_reason: undefined, log: add(r, now, 'Case reopened') }
  }
}

/** An earlier case of the same kind on the same pump: the new one may be a return, not a new problem. */
export function earlierSame(inc: IncidentLike, all: IncidentLike[], reviews: Record<string, Review>): { incident: IncidentLike; review?: Review } | null {
  const before = all
    .filter((o) => o.id !== inc.id && o.head.asset_id === inc.head.asset_id && o.head.fault_type === inc.head.fault_type && o.head.alert_time_utc < inc.head.alert_time_utc)
    .sort((a, b) => b.head.alert_time_utc.localeCompare(a.head.alert_time_utc))[0]
  return before ? { incident: before, review: reviews[before.id] } : null
}

/** In the recorded data: how long the pump stayed quiet (no alert of this kind) after the last alert of the case. */
export function quietHoursAfter(inc: IncidentLike, all: IncidentLike[], windowEnd?: string | null): { hours: number; ended: 'next_alert' | 'window_end' } | null {
  const times = inc.members.map((m) => m.alert_time_utc).sort()
  const last = times.length ? times[times.length - 1] : inc.head.alert_time_utc
  const later = all
    .filter((o) => o.id !== inc.id && o.head.asset_id === inc.head.asset_id && o.head.fault_type === inc.head.fault_type)
    .flatMap((o) => o.members.map((m) => m.alert_time_utc))
    .filter((t) => t > last)
    .sort()[0]
  const end = later ?? windowEnd
  if (!end) return null
  const hours = (Date.parse(end) - Date.parse(last)) / 3_600_000
  return Number.isFinite(hours) ? { hours: Math.max(0, hours), ended: later ? 'next_alert' : 'window_end' } : null
}

export interface Summary {
  cases: number
  open: number
  inspection: number
  result: number
  recovery: number
  closed: number
  reviewed: number // any case a person has acted on
  confirmed: number
  no_fault: number
  false_alarm: number
  further: number
  confirmed_share: number | null // confirmed among the cases with a final judgement (confirmed, no fault, false alarm)
  median_minutes_to_decision: number | null
}

const medianOf = (v: number[]) => {
  if (!v.length) return null
  const s = [...v].sort((a, b) => a - b)
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2
}

export function summarize(incidents: IncidentLike[], reviews: Record<string, Review>): Summary {
  const out: Summary = { cases: incidents.length, open: 0, inspection: 0, result: 0, recovery: 0, closed: 0, reviewed: 0, confirmed: 0, no_fault: 0, false_alarm: 0, further: 0, confirmed_share: null, median_minutes_to_decision: null }
  const minutes: number[] = []
  for (const i of incidents) {
    const r = reviews[i.id]
    const s: Status = r?.status ?? 'open'
    out[s] += 1
    if (!r) continue
    if (r.first_decision_at) {
      out.reviewed += 1
      const m = (Date.parse(r.first_decision_at) - Date.parse(r.first_seen)) / 60_000
      if (Number.isFinite(m)) minutes.push(Math.max(0, m))
    }
    if (r.outcome) out[r.outcome] += 1
  }
  const final = out.confirmed + out.no_fault + out.false_alarm
  out.confirmed_share = final > 0 ? out.confirmed / final : null
  out.median_minutes_to_decision = medianOf(minutes)
  return out
}

/** Old builds kept one decision per alert. A case gets a review from them once, so nothing a person marked is lost. */
export function migrateDecisions(old: Record<string, 'approved' | 'rejected'>, incidents: IncidentLike[], now: string): Record<string, Review> {
  const out: Record<string, Review> = {}
  for (const i of incidents) {
    const d = i.members.map((m) => old[m.alert_id]).find(Boolean)
    if (!d) continue
    let r = newReview(i, now)
    r = { ...r, log: [{ at: now, event: 'Imported from an earlier decision in this browser' }] }
    r = apply(r, i, d === 'approved' ? { type: 'approve' } : { type: 'false_alarm' }, now)
    out[i.id] = r
  }
  return out
}

const CSV_COLUMNS: (keyof Review)[] = ['incident_id', 'asset_id', 'fault_type', 'model_version', 'status', 'outcome', 'actual', 'note', 'first_seen', 'first_decision_at', 'outcome_at', 'recovery_started_at', 'closed_at', 'closed_reason', 'came_back_count']

const cell = (v: unknown) => {
  const s = v === undefined || v === null ? '' : String(v)
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function toCsv(reviews: Review[]): string {
  const rows = [...reviews].sort((a, b) => a.first_seen.localeCompare(b.first_seen))
  return [CSV_COLUMNS.join(','), ...rows.map((r) => CSV_COLUMNS.map((c) => cell(r[c])).join(','))].join('\n') + '\n'
}

export function toJson(reviews: Review[]): string {
  return JSON.stringify({ kind: 'watchkeeper-review-log', version: 1, note: 'Kept in one browser. Watchkeeper never writes to a machine.', reviews }, null, 2) + '\n'
}

export function load(): Record<string, Review> {
  try {
    const v = JSON.parse(localStorage.getItem(STORE) ?? '{}')
    return v && typeof v === 'object' ? v : {}
  } catch {
    return {}
  }
}

export function save(reviews: Record<string, Review>): void {
  try {
    localStorage.setItem(STORE, JSON.stringify(reviews))
  } catch {
    /* storage may be unavailable; the log stays in memory for this session */
  }
}
