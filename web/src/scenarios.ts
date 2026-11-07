// The 18 controlled verification situations of the organizers' enterprise reference (A01 to A18) and what Watchkeeper does in each now.
// Evidence: eval/results/scenarios_probe.md (real minute features of quiet simulated pumps, perturbed), eval/results/data_quality_gate.md
// (options that were gated), tests/test_scenarios.py, tests/test_ingest.py and web/tests/reviews.test.ts. Keep this list honest: a gap stays a gap.

export type ScenarioStatus = 'handled' | 'partly' | 'gap'

export interface Scenario {
  id: string
  situation: string
  now: string
  status: ScenarioStatus
  where: string
}

export const STATUS_WORD: Record<ScenarioStatus, string> = { handled: 'Handled', partly: 'Partly', gap: 'Known gap' }

export const SCENARIOS: Scenario[] = [
  { id: 'A01', situation: 'Stable running, good data', status: 'handled', where: 'scenarios_probe, tests/test_scenarios.py',
    now: 'No alert. The data check shows when the last reading arrived and that every expected channel is fresh.' },
  { id: 'A02', situation: 'Gateway silent for a while', status: 'handled', where: 'scenarios_probe, tests/test_scenarios.py',
    now: 'Four minutes of silence raises no alert by design (the rule needs eight), but the data check names any gap over three minutes. Twelve minutes raises "data stopped arriving".' },
  { id: 'A03', situation: 'One channel stops while the gateway stays alive', status: 'partly', where: 'tests/test_scenarios.py',
    now: 'No alert, because a missing channel is not a machine fault. The data check names the silent channel and when it stopped.' },
  { id: 'A04', situation: 'The drive\'s speed signal disappears', status: 'handled', where: 'scenarios_probe, data_quality_gate',
    now: 'Operating-point checks are suspended instead of starting a new regime. Without this, five false alerts appeared over four days; with it, none. Identical results on every evaluation set.' },
  { id: 'A05', situation: 'A deviation lasting 8 minutes', status: 'handled', where: 'scenarios_probe',
    now: 'No alert, by design: a deviation must last 12 minutes.' },
  { id: 'A06', situation: 'A large deviation lasting 20 minutes', status: 'gap', where: 'scenarios_probe, data_quality_gate',
    now: 'The trigger fires but the classifier calls it normal (70 to 74 percent), so no alert is raised. An option that reports it as "unexplained" adds 2 to 7 false alerts per 294 pump-days, failed the gate and stays off.' },
  { id: 'A07', situation: 'The same problem returns after it looked normal', status: 'partly', where: 'web/tests/reviews.test.ts',
    now: 'A new case of a kind already seen on the same pump is flagged as a possible return, with the earlier case\'s status. Repeated alerts of one kind are still merged for 12 hours.' },
  { id: 'A08', situation: 'A sensor shift and a hydraulic problem together', status: 'partly', where: 'not tested on a perturbation',
    now: 'One fault type is named per episode, so a mixed case is reported as one problem. This was not tested.' },
  { id: 'A09', situation: 'Standing still for the first day, then a deviation', status: 'handled', where: 'tests/test_scenarios.py',
    now: 'The pump is shown as "still learning" with the minutes seen so far, and a new operating point is learned for two hours before it is judged.' },
  { id: 'A10', situation: 'Retrofit pump, a few abnormal wireless vibration samples', status: 'handled', where: 'scenarios_probe',
    now: '28 abnormal samples, five minutes apart, raise a misalignment alert.' },
  { id: 'A11', situation: 'Readings flagged out of range', status: 'partly', where: 'tests/test_scenarios.py',
    now: 'Quality flags are counted and named in the data check. The detector does not use them, so alerts do not change.' },
  { id: 'A12', situation: 'A value constant inside each minute but changing between minutes', status: 'gap', where: 'data_quality_gate',
    now: 'Called a frozen instrument. A stricter rule would not, but it lost real frozen-sensor events on the tuning fleets (59.9 to 57.7), so it stays off.' },
  { id: 'A13', situation: 'A deviation in the first minutes after a start', status: 'handled', where: 'tests/test_scenarios.py',
    now: 'A start is announced, thermal channels are ignored for 60 minutes, and no alert is raised.' },
  { id: 'A14', situation: 'The same minute arrives twice', status: 'handled', where: 'scenarios_probe, tests/test_ingest.py',
    now: 'The first version crashed. Repeated minutes are now dropped, conflicting copies are counted, and the counts are shown.' },
  { id: 'A15', situation: 'A deviation lasting more than 12 hours', status: 'partly', where: 'scenarios_probe, data_quality_gate',
    now: 'Reminders merge into one incident. A deviation that the classifier calls normal is still not reported unless the 12-hour option is on, and it is off.' },
  { id: 'A16', situation: 'Normal again after a deviation', status: 'handled', where: 'web/tests/reviews.test.ts',
    now: 'The review log has a recovery check: the readings that raised the alert must stay normal for 24 hours, and a person confirms. Watchkeeper does not decide that a repair worked.' },
  { id: 'A17', situation: 'The model changes after a work order', status: 'handled', where: 'tests/test_alert_archive.py',
    now: 'Alert snapshots are kept per model version and never overwritten.' },
  { id: 'A18', situation: 'Rows arrive but every measurement is missing', status: 'handled', where: 'tests/test_scenarios.py',
    now: 'The data check says "not enough data": nothing can be evaluated. A quiet detector is never read as a healthy pump.' },
]

/** Things a plant pilot would need that this prototype does not build, with the reason. */
export const NOT_BUILT: [string, string][] = [
  ['Roles, single sign-on, plant-network access', 'The interface only reads, so access belongs in the pilot\'s network and proxy. Home-made roles without real requirements would give a false sense of safety.'],
  ['Work orders and maintenance-system integration', 'Needs a named system. Without one it would be a mock-up.'],
  ['Escalation, assignment and simultaneous editing', 'Needs users, shifts and owners. The review log is one person in one browser.'],
  ['Standby pumps and criticality ranking', 'The data pack has no topology or criticality, so a priority cannot be computed honestly.'],
  ['Seal leakage and electrical faults', 'They are not in the benchmark. Watchkeeper says so rather than guessing.'],
  ['An incremental scorer', 'The detector is re-run on all minutes received so far; one run takes 1 to 3 seconds for up to a week of history and grows with it.'],
]

export const tally = (list: Scenario[] = SCENARIOS): Record<ScenarioStatus, number> =>
  list.reduce((acc, s) => ({ ...acc, [s.status]: acc[s.status] + 1 }), { handled: 0, partly: 0, gap: 0 })
