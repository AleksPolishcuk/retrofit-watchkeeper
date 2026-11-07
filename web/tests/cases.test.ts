import assert from 'node:assert/strict'
import { test } from 'node:test'
import { attention, headline, levelCounts, levelOf, pumpRows, rankOf } from '../src/cases.ts'

const c = (id: string, asset: string, stage: string | undefined, t: string) => ({ id, head: { asset_id: asset, stage, alert_time_utc: t } })
const cases = [
  c('a', 'PUMP-01', 'very_likely', '2025-01-02T00:00:00Z'),
  c('b', 'PUMP-01', 'watch', '2025-01-03T00:00:00Z'),
  c('d', 'PUMP-02', 'likely', '2025-01-04T00:00:00Z'),
  c('e', 'PUMP-02', 'possible', '2025-01-05T00:00:00Z'),
  c('f', 'PUMP-03', undefined, '2025-01-06T00:00:00Z'),
]

test('a missing stage counts as Watch, as the priority filter does', () => {
  assert.equal(rankOf(undefined), 0)
  assert.equal(levelOf(undefined), 'watch')
  assert.equal(levelOf('very_likely'), 'very_likely')
})

test('counts cover open cases only, and closing a case removes it', () => {
  assert.deepEqual(levelCounts(cases, {}), { very_likely: 1, likely: 1, possible: 1, watch: 2 })
  assert.deepEqual(levelCounts(cases, { a: { status: 'closed' } }), { very_likely: 0, likely: 1, possible: 1, watch: 2 })
  assert.equal(levelCounts(cases, { a: { status: 'inspection' } }).very_likely, 1) // being inspected is still open
})

test('the pump rows say which pumps have open cases and never call a quiet pump healthy', () => {
  const rows = pumpRows(['PUMP-01', 'PUMP-02', 'PUMP-03', 'PUMP-04'], cases, { a: { status: 'closed' } })
  assert.deepEqual(rows.map((r) => [r.asset_id, r.open, r.worst]), [['PUMP-01', 1, 'watch'], ['PUMP-02', 2, 'likely'], ['PUMP-03', 1, 'watch'], ['PUMP-04', 0, null]])
  assert.ok(!('healthy' in rows[3]))
})

test('the attention list is strongest first, then most recent, and skips closed cases', () => {
  assert.deepEqual(attention(cases, {}, 3).map((x) => x.id), ['a', 'd', 'e'])
  assert.deepEqual(attention(cases, { a: { status: 'closed' } }, 2).map((x) => x.id), ['d', 'e'])
  assert.deepEqual(attention(cases, {}, 10).map((x) => x.id).slice(-2), ['f', 'b']) // watch cases, newest first
})

test('the headline counts what needs a look first and what a person has already acted on', () => {
  const h = headline(cases, { a: { status: 'inspection' }, d: { status: 'closed' } })
  assert.deepEqual(h, { total: 5, open: 4, urgent: 1, pumpsUrgent: 1, reviewed: 2, topId: 'a' })
  const none = headline(cases, { a: { status: 'closed' }, d: { status: 'closed' } })
  assert.equal(none.urgent, 0)
  assert.equal(none.pumpsUrgent, 0)
  assert.equal(headline([], {}).topId, null)
})
