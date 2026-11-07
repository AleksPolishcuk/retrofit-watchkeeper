import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { snapshotFile } from '../src/snapshot.ts'

const cases: [string, string | null][] = JSON.parse(readFileSync(new URL('./snapshot-cases.json', import.meta.url), 'utf8'))

test('every API url the interface uses maps to the file name the exporter writes (shared with the Python test)', () => {
  for (const [url, file] of cases) assert.equal(snapshotFile(url), file, url)
})

test('names are safe file names', () => {
  for (const [, file] of cases) if (file) assert.match(file, /^[A-Za-z0-9._/-]+$/)
  assert.equal(snapshotFile('/api/data-health?asset_id=PUMP-06&as_of=2025-10-12T21%3A48%3A00Z'), 'data-health/PUMP-06__2025-10-12T21-48-00Z.json')
  assert.equal(snapshotFile('/api/series?asset_id=../../etc&channel=x&step_min=10'), 'series/..-..-etc__x__10.json')
})
