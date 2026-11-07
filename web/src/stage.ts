import type { Alert, Stage, StageBasis } from './types'

export const STAGES: Stage[] = ['watch', 'possible', 'likely', 'very_likely']
export const STAGE_LABEL: Record<Stage, string> = { watch: 'Watch', possible: 'Possible', likely: 'Likely', very_likely: 'Very likely' }

export const stageRank = (s?: Stage): number => (s ? STAGES.indexOf(s) : -1)

/** Advisory wording: an alert is a recommendation to look, never a command and never a probability. */
export const headline = (a: Alert): string => (stageRank(a.stage) >= 2 ? 'Investigation recommended' : 'Worth a look')

export const basisText = (b?: StageBasis | null): string =>
  b && b.n > 0
    ? `In back-testing on simulated fleets, ${b.correct} of ${b.n} alerts at this level named the right fault type.`
    : 'No back-test count is available for this level.'

export const pretty = (s: string) => s.replace(/_/g, ' ').toLowerCase()

export const when = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC'
