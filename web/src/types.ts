export type Tier = 'T0_LEGACY' | 'T1_RETROFIT' | 'T2_FULL'

export interface Asset {
  asset_id: string
  split: 'train' | 'validation' | 'test'
  site: string
  system: string
  profile: string
  control: string
  instrumentation_tier: Tier
  window_start_utc: string
  window_end_utc: string
  commissioned_year: number
  motor_rated_kw: number
  fluid: string
  channels_available: string[]
  alert_count: number
  alert_source: 'engine' | 'mock'
  telemetry_served: boolean
}

export interface Evidence {
  channel: string
  text: string
  z: number | null
}

export type Stage = 'watch' | 'possible' | 'likely' | 'very_likely'

export interface StageBasis {
  n: number
  correct: number
  source: string
}

export interface Alert {
  alert_id: string
  asset_id: string
  alert_time_utc: string
  event_class: 'MACHINE' | 'SENSOR'
  fault_type: string
  confidence: number
  alternatives?: { fault_type: string; p: number }[]
  evidence: Evidence[]
  sensor_check?: { verdict: 'machine' | 'sensor' | 'unclear'; reason: string }
  uncertainty?: { missing_channels?: string[]; data_quality?: 'ok' | 'degraded' | 'poor' }
  recommended_action: string
  requires_human_approval: true
  what_if?: { simulation_only?: boolean; action?: string; summary?: string } | null
  source?: string
  incident_id?: string
  consequence?: string
  check?: string
  time_to_act?: string | null
  time_to_act_note?: string
  stage?: Stage
  stage_basis?: StageBasis | null
  model_version?: string
  tier?: Tier
}

export interface LabelEvent {
  event_id: string
  event_class: 'MACHINE' | 'SENSOR'
  fault_type: string
  onset_utc: string
  detectable_utc: string | null
  action_deadline_utc: string | null
  end_utc: string | null
  severity: string
  observable: boolean
}

export interface BenignWindow {
  benign_type: string
  start_utc: string
  end_utc: string
}

export interface Timeline {
  asset_id: string
  window_start_utc: string
  window_end_utc: string
  labels_public: boolean
  events: LabelEvent[]
  benign: BenignWindow[]
}

export interface Series {
  asset_id: string
  channel: string
  step_min: number
  t: string[]
  v: number[]
}

export interface WhatIfResult {
  available: boolean
  simulation_only: true
  message?: string
  accepted?: boolean
  rejection_reasons?: string[]
  warnings?: string[]
  action?: string
  assumed_condition?: string
  rows?: { label: string; unit: string; baseline: number | null; proposed: number | null }[]
  intervention?: { stop_h: number; labour_h: number; parts_eur: number; estimated_cost_eur: number } | null
  caveats?: string[]
}

export interface ReportRow {
  set: string
  method: string
  composite: number
  lo: number | null
  hi: number | null
  f1: number
  recall: number
  prec: number
  fa: number
  type: number
  cls: number
  events: number
}

export interface Counts {
  events: number
  detected: number
  right_type: number
}

export interface ReportSet {
  wk: ReportRow
  b1?: ReportRow
  null_random_alerts: number
  by_tier?: Record<string, Counts>
  by_type?: Record<string, Counts>
}

export interface Healthy {
  pump_days: number
  alerts: number
  false_episodes: number
  per_pump_day: number
  per_pump_month: number
  upper95_per_pump_month: number
}

export interface Footprint {
  model_file: string
  model_mb: number
  load_s: number
  minutes_scored: number
  score_s: number
  ms_per_pump_minute: number
  peak_rss_mb: number
  python: string
}

export interface Results {
  report: Record<string, ReportSet | Healthy> | null
  stages: { edges: number[]; sets: string[]; basis: Record<Stage, StageBasis>; detail: Record<Stage, { alerts: number; at_a_real_event: number; right_class: number; right_type: number }>; note: string } | null
  footprint: Footprint | null
  business: Business | null
  missing_sensor: { scenario: string; composite: number; recall: number; 'type recall': number; 'class recall': number }[] | null
  tiers: { tier: Tier; pumps: number; channels: string[]; sometimes: string[] }[]
}

export interface Business {
  measured: { events: number; recall: number; events_with_limit: number; caught_before_limit: number; lead_hours: number[]; false_per_pump_day: number; repeat_per_pump_day: number; pump_days: number }
  assumptions: Record<string, { value: number; unit: string; basis: string }>
  base: Record<'organizers_convention' | 'refined', { benefit: number; nuisance: number; net: number; payback_yr: number | null }>
  sites: { name: string; downtime_eur_h: number; faults_per_year: number; benefit: number; nuisance: number; net: number; payback_yr: number | null }[]
}
