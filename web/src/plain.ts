import { stageRank } from './stage'
import type { Alert } from './types'

/** Operator wording for each diagnosis. The technical name stays visible in small print. */
export const FAULT_TITLE: Record<string, string> = {
  SUCTION_STRAINER_CLOGGING: 'The suction strainer may be clogging',
  DISCHARGE_RESTRICTION: 'Something after the pump may be restricting the flow',
  IMPELLER_WEAR: 'The impeller may be wearing',
  AIR_ENTRAINMENT: 'Air may be getting into the pump',
  CAVITATION: 'The pump may be cavitating (vapour bubbles at the inlet)',
  BEARING_WEAR: 'A bearing may be wearing',
  MISALIGNMENT: 'The shaft may be misaligned',
  IMBALANCE: 'The rotor may be out of balance',
  SENSOR_DRIFT: 'An instrument may be drifting (not necessarily the machine)',
  SENSOR_STUCK: 'An instrument reading looks frozen',
  SENSOR_CALIBRATION_SHIFT: 'An instrument may be reading with an offset',
  SENSOR_NOISE_SPIKES: 'An instrument is giving noisy readings',
  COMMUNICATION_LOSS: 'Data stopped arriving from this pump',
  UNKNOWN: 'Something is off, but the cause is unclear',
}
export const titleOf = (a: Alert) => FAULT_TITLE[a.fault_type] ?? a.fault_type.replace(/_/g, ' ').toLowerCase()

export const CHANNEL: Record<string, [string, string]> = {
  motor_speed_rpm: ['Motor speed', 'rpm'], motor_current_a: ['Motor current', 'A'], motor_power_kw: ['Motor power', 'kW'],
  suction_pressure_kpa: ['Suction pressure', 'kPa'], discharge_pressure_kpa: ['Discharge pressure', 'kPa'], flow_m3_h: ['Flow', 'm³/h'],
  fluid_temp_c: ['Fluid temperature', '°C'], bearing_temp_c: ['Bearing temperature', '°C'], motor_winding_temp_c: ['Winding temperature', '°C'],
  vibration_rms_mm_s: ['Vibration', 'mm/s'], vibration_accel_rms_g: ['Vibration (acceleration)', 'g'], vibration_crest_factor: ['Vibration (crest factor)', ''],
  valve_position_pct: ['Valve position', '%'],
}
export const nameOf = (c: string) => CHANNEL[c]?.[0] ?? c.replace(/_/g, ' ')

/** How far from normal, in words. z is a robust standard deviation from the pump's own baseline at the same operating point. */
export function howFar(z: number): string {
  const m = Math.abs(z)
  const word = m < 3 ? 'slightly' : m < 5 ? 'clearly' : m < 10 ? 'far' : 'extremely far'
  return `${word} ${z < 0 ? 'below' : 'above'} normal`
}

export interface Incident {
  id: string
  head: Alert
  members: Alert[]
}

/** One row per incident: the strongest alert of each group (earliest if tied), newest and strongest first. */
export function incidentsOf(alerts: Alert[]): Incident[] {
  const groups = new Map<string, Alert[]>()
  for (const a of alerts) groups.set(a.incident_id ?? a.alert_id, [...(groups.get(a.incident_id ?? a.alert_id) ?? []), a])
  const out: Incident[] = []
  for (const [id, members] of groups) {
    const head = [...members].sort((x, y) => stageRank(y.stage) - stageRank(x.stage) || x.alert_time_utc.localeCompare(y.alert_time_utc))[0]
    out.push({ id, head, members })
  }
  return out.sort((a, b) => stageRank(b.head.stage) - stageRank(a.head.stage) || b.head.alert_time_utc.localeCompare(a.head.alert_time_utc))
}

export const median = (v: number[]) => {
  if (!v.length) return null
  const s = [...v].sort((a, b) => a - b)
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2
}

export const fmtNum = (x: number) => (Math.abs(x) >= 100 ? x.toFixed(0) : Math.abs(x) >= 10 ? x.toFixed(1) : x.toFixed(2))

export const HEALTH_LABEL: Record<string, string> = { OK: 'Data OK', BASELINE_LEARNING: 'Still learning', DEGRADED: 'Data degraded', INSUFFICIENT_DATA: 'Not enough data', NO_DATA: 'No data' }
