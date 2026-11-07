// Run with: node --test web/tests   (Node 22.18 or newer strips the types itself)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  RECOVERY_HOURS, allowed, apply, earlierSame, migrateDecisions, quietHoursAfter, summarize, toCsv, toJson,
  type IncidentLike, type Review,
} from '../src/reviews.ts'

const inc = (id: string, asset = 'PUMP-08', fault = 'BEARING_WEAR', times = ['2025-09-10T09:33:00Z']): IncidentLike => ({
  id,
  head: { alert_id: `${id}-a`, asset_id: asset, fault_type: fault, alert_time_utc: times[0], model_version: 'wk-test' },
  members: times.map((t, k) => ({ alert_id: k === 0 ? `${id}-a` : `${id}-a${k}`, alert_time_utc: t })),
})
const T = (m: number) => new Date(Date.UTC(2026, 10, 7, 12, m)).toISOString()

test('a case starts open and the full path to closed is possible', () => {
  const i = inc('i1')
  let r = apply(undefined, i, { type: 'view' }, T(0))
  assert.equal(r.status, 'open')
  assert.deepEqual(allowed(r), ['approve', 'false_alarm'])
  r = apply(r, i, { type: 'approve' }, T(5))
  assert.equal(r.status, 'inspection')
  r = apply(r, i, { type: 'outcome', outcome: 'confirmed', actual: 'BEARING_WEAR', note: ' found play ' }, T(30))
  assert.equal(r.status, 'result')
  assert.equal(r.actual, 'BEARING_WEAR')
  assert.equal(r.note, 'found play')
  r = apply(r, i, { type: 'start_recovery' }, T(40))
  assert.equal(r.status, 'recovery')
  r = apply(r, i, { type: 'confirm_recovery' }, T(50))
  assert.equal(r.status, 'closed')
  assert.equal(r.closed_reason, 'recovered')
  assert.equal(r.log.length, 5)
  assert.deepEqual(r.log.map((l) => l.at), [T(0), T(5), T(30), T(40), T(50)])
})

test('an action that does not fit the status changes nothing', () => {
  const i = inc('i2')
  const r = apply(undefined, i, { type: 'view' }, T(0))
  assert.equal(apply(r, i, { type: 'confirm_recovery' }, T(1)), r)
  assert.equal(apply(r, i, { type: 'outcome', outcome: 'confirmed', actual: 'X' }, T(1)), r)
  assert.equal(apply(r, i, { type: 'close' }, T(1)), r)
  const done = apply(r, i, { type: 'false_alarm' }, T(2))
  assert.equal(done.status, 'closed')
  assert.equal(apply(done, i, { type: 'approve' }, T(3)), done)
  assert.deepEqual(allowed(done), ['reopen'])
})

test('no fault found closes; needs further inspection goes back; reopen starts again', () => {
  const i = inc('i3')
  let r = apply(apply(undefined, i, { type: 'approve' }, T(1)), i, { type: 'outcome', outcome: 'further' }, T(2))
  assert.deepEqual(allowed(r), ['reinspect'])
  r = apply(r, i, { type: 'reinspect' }, T(3))
  assert.equal(r.status, 'inspection')
  assert.equal(r.outcome, undefined)
  r = apply(r, i, { type: 'outcome', outcome: 'no_fault' }, T(4))
  assert.deepEqual(allowed(r), ['close'])
  r = apply(r, i, { type: 'close' }, T(5))
  assert.equal(r.closed_reason, 'no_fault')
  r = apply(r, i, { type: 'reopen' }, T(6))
  assert.equal(r.status, 'open')
  assert.equal(r.closed_at, undefined)
})

test('a problem that comes back during the recovery check returns to inspection and is counted', () => {
  const i = inc('i4')
  let r = apply(apply(undefined, i, { type: 'approve' }, T(1)), i, { type: 'outcome', outcome: 'confirmed', actual: 'X' }, T(2))
  r = apply(apply(r, i, { type: 'start_recovery' }, T(3)), i, { type: 'came_back' }, T(4))
  assert.equal(r.status, 'inspection')
  assert.equal(r.came_back_count, 1)
  assert.equal(r.recovery_started_at, undefined)
})

test('the actual finding is kept only for a confirmed fault', () => {
  const i = inc('i5')
  const r = apply(apply(undefined, i, { type: 'approve' }, T(1)), i, { type: 'outcome', outcome: 'no_fault', actual: 'IGNORED' }, T(2))
  assert.equal(r.actual, undefined)
})

test('an earlier case of the same kind on the same pump is found, other pumps and kinds are not', () => {
  const a = inc('a', 'PUMP-08', 'BEARING_WEAR', ['2025-09-10T09:33:00Z'])
  const b = inc('b', 'PUMP-08', 'BEARING_WEAR', ['2025-09-13T04:44:00Z'])
  const c = inc('c', 'PUMP-09', 'BEARING_WEAR', ['2025-09-11T04:44:00Z'])
  const d = inc('d', 'PUMP-08', 'MISALIGNMENT', ['2025-09-11T04:44:00Z'])
  const reviews: Record<string, Review> = { a: apply(undefined, a, { type: 'false_alarm' }, T(1)) }
  const hit = earlierSame(b, [a, b, c, d], reviews)
  assert.equal(hit?.incident.id, 'a')
  assert.equal(hit?.review?.closed_reason, 'false_alarm')
  assert.equal(earlierSame(a, [a, b, c, d], reviews), null)
})

test('quiet hours run to the next alert of the same kind, or to the end of the recorded data', () => {
  const a = inc('a', 'PUMP-08', 'BEARING_WEAR', ['2025-09-10T09:00:00Z', '2025-09-10T10:00:00Z'])
  const b = inc('b', 'PUMP-08', 'BEARING_WEAR', ['2025-09-10T16:00:00Z'])
  assert.deepEqual(quietHoursAfter(a, [a, b], '2025-09-15T00:00:00Z'), { hours: 6, ended: 'next_alert' })
  assert.deepEqual(quietHoursAfter(b, [a, b], '2025-09-11T16:00:00Z'), { hours: 24, ended: 'window_end' })
  assert.equal(quietHoursAfter(b, [a, b], null), null)
  assert.equal(RECOVERY_HOURS, 24)
})

test('the summary counts statuses, outcomes, the confirmed share and the time to the first decision', () => {
  const list = [inc('1'), inc('2'), inc('3'), inc('4'), inc('5')]
  const rv: Record<string, Review> = {}
  rv['1'] = apply(apply(apply(undefined, list[0], { type: 'view' }, T(0)), list[0], { type: 'approve' }, T(10)), list[0], { type: 'outcome', outcome: 'confirmed', actual: 'X' }, T(40))
  rv['2'] = apply(apply(apply(undefined, list[1], { type: 'view' }, T(0)), list[1], { type: 'approve' }, T(20)), list[1], { type: 'outcome', outcome: 'no_fault' }, T(30))
  rv['3'] = apply(apply(undefined, list[2], { type: 'view' }, T(0)), list[2], { type: 'false_alarm' }, T(30))
  rv['4'] = apply(undefined, list[3], { type: 'view' }, T(0))
  const s = summarize(list, rv)
  assert.equal(s.cases, 5)
  assert.equal(s.open, 2) // case 4 viewed only, case 5 never opened
  assert.equal(s.result, 2)
  assert.equal(s.closed, 1)
  assert.equal(s.reviewed, 3)
  assert.equal(s.confirmed, 1)
  assert.equal(s.no_fault, 1)
  assert.equal(s.false_alarm, 1)
  assert.equal(s.confirmed_share, 1 / 3)
  assert.equal(s.median_minutes_to_decision, 20) // 10, 20, 30 minutes
  assert.equal(summarize([], {}).confirmed_share, null)
})

test('decisions from earlier builds become reviews once', () => {
  const list = [inc('1'), inc('2'), inc('3', 'PUMP-08', 'BEARING_WEAR', ['2025-09-10T09:33:00Z', '2025-09-10T10:33:00Z'])]
  const out = migrateDecisions({ '1-a': 'approved', '2-a': 'rejected', '3-a1': 'approved' }, list, T(0))
  assert.equal(out['1'].status, 'inspection')
  assert.equal(out['2'].status, 'closed')
  assert.equal(out['2'].closed_reason, 'false_alarm')
  assert.equal(out['3'].status, 'inspection') // a decision on a later member of the incident counts
  assert.equal(Object.keys(out).length, 3)
})

test('exports: CSV quotes commas, quotes and line breaks; JSON round-trips', () => {
  const i = inc('i1')
  let r = apply(apply(undefined, i, { type: 'approve' }, T(1)), i, { type: 'outcome', outcome: 'confirmed', actual: 'BEARING_WEAR', note: 'worn, "play" on\nDE side' }, T(2))
  r = { ...r }
  const csv = toCsv([r])
  const [head, ...rows] = csv.trim().split('\n')
  assert.ok(head.startsWith('incident_id,asset_id,fault_type'))
  assert.ok(csv.includes('"worn, ""play"" on\nDE side"'))
  assert.equal(rows.length >= 1, true)
  const parsed = JSON.parse(toJson([r]))
  assert.equal(parsed.kind, 'watchkeeper-review-log')
  assert.deepEqual(parsed.reviews[0], JSON.parse(JSON.stringify(r)))
})
