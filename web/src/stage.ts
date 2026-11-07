import type { Stage } from './types'

export const STAGES: Stage[] = ['watch', 'possible', 'likely', 'very_likely']
export const STAGE_LABEL: Record<Stage, string> = { watch: 'Watch', possible: 'Possible', likely: 'Likely', very_likely: 'Very likely' }

export const stageRank = (s?: Stage): number => (s ? STAGES.indexOf(s) : -1)

export const pretty = (s: string) => s.replace(/_/g, ' ').toLowerCase()

export const when = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC'
