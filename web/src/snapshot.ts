// Static snapshot mode: when the interface is built with VITE_SNAPSHOT=1 it reads the saved answers of the read-only API from /snapshot/*.json instead of
// calling a server. The names must match src/watchkeeper/snapshot.py (checked against tests/snapshot-cases.json by both test suites).

const safe = (s: string) => s.replace(/[^A-Za-z0-9._-]/g, '-')

/** File under /snapshot for an API path such as /api/series?asset_id=PUMP-01&channel=x&step_min=10, or null when it is not part of the snapshot (live replay). */
export function snapshotFile(url: string): string | null {
  const [path, query = ''] = url.split('?')
  const q = new URLSearchParams(query)
  const has = (...k: string[]) => k.every((x) => q.get(x))
  const p = path.replace(/\/+$/, '')
  if (p === '/api/assets') return 'assets.json'
  if (p === '/api/results') return 'results.json'
  if (p === '/api/health') return 'health.json'
  if (p === '/api/alerts') return q.get('asset_id') ? `alerts/${safe(q.get('asset_id')!)}.json` : 'alerts.json'
  if (p === '/api/alerts/archive') return `archive/${safe(q.get('asset_id') ?? 'all')}.json`
  if (p === '/api/timeline' && has('asset_id')) return `timeline/${safe(q.get('asset_id')!)}.json`
  if (p === '/api/series' && has('asset_id', 'channel', 'step_min')) return `series/${safe(q.get('asset_id')!)}__${safe(q.get('channel')!)}__${safe(q.get('step_min')!)}.json`
  if (p === '/api/data-health' && has('asset_id')) return q.get('as_of') ? `data-health/${safe(q.get('asset_id')!)}__${safe(q.get('as_of')!)}.json` : `data-health/${safe(q.get('asset_id')!)}.json`
  if (p === '/api/whatif' && has('asset_id', 'time_utc', 'fault_type')) return `whatif/${safe(q.get('asset_id')!)}__${safe(q.get('time_utc')!)}__${safe(q.get('fault_type')!)}.json`
  return null
}
