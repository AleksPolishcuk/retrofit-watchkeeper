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
