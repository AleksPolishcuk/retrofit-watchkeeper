import assert from 'node:assert/strict'
import { test } from 'node:test'
import { NOT_BUILT, SCENARIOS, STATUS_WORD, tally } from '../src/scenarios.ts'

test('all 18 situations are listed once, in order, with a known status and a stated place of evidence', () => {
  assert.deepEqual(SCENARIOS.map((s) => s.id), Array.from({ length: 18 }, (_, i) => `A${String(i + 1).padStart(2, '0')}`))
  for (const s of SCENARIOS) {
    assert.ok(s.status in STATUS_WORD, s.id)
    assert.ok(s.situation.length > 5 && s.now.length > 20 && s.where.length > 3, s.id)
  }
})

test('the tally adds up and the known gaps are not hidden', () => {
  const t = tally()
  assert.equal(t.handled + t.partly + t.gap, 18)
  assert.ok(t.gap >= 2)
  assert.deepEqual(SCENARIOS.filter((s) => s.status === 'gap').map((s) => s.id), ['A06', 'A12'])
  assert.ok(NOT_BUILT.length >= 5)
})
