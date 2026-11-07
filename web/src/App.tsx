import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError } from './api'
import AlertCard, { type Decision } from './AlertCard'
import Fleet from './Fleet'
import ResultsPage from './Results'
import RetrofitPage from './Retrofit'
import { pretty, STAGE_LABEL, when } from './stage'
import TimelineChart from './Timeline'
import type { Alert, Asset, Results, Series, Timeline } from './types'

const TIER: Record<string, string> = { T0_LEGACY: 'T0', T1_RETROFIT: 'T1', T2_FULL: 'T2' }
const TIER_HELP: Record<string, string> = {
  T0_LEGACY: 'Legacy: motor current, discharge pressure, temperatures',
  T1_RETROFIT: 'Low-cost retrofit: adds suction pressure and a wireless vibration sensor',
  T2_FULL: 'Fully instrumented: adds flow, power, winding temperature, fast vibration',
}
const PREFERRED = ['discharge_pressure_kpa', 'motor_current_a', 'motor_power_kw']
const STORE = 'watchkeeper.decisions'
const THEME_KEY = 'watchkeeper.theme'
const THEMES = ['night', 'dusk', 'day'] as const
type Theme = (typeof THEMES)[number]
type Route = { name: 'fleet' } | { name: 'pump'; id: string } | { name: 'results' } | { name: 'retrofit' }

function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/')
  if (parts[0] === 'pump' && parts[1]) return { name: 'pump', id: decodeURIComponent(parts[1]) }
  if (parts[0] === 'results') return { name: 'results' }
  if (parts[0] === 'retrofit') return { name: 'retrofit' }
  return { name: 'fleet' }
}

function loadDecisions(): Record<string, Decision> {
  try {
    return JSON.parse(localStorage.getItem(STORE) ?? '{}')
  } catch {
    return {}
  }
}

function loadTheme(): Theme {
  try {
    const t = localStorage.getItem(THEME_KEY)
    if (t && (THEMES as readonly string[]).includes(t)) return t as Theme
  } catch {
    /* storage may be unavailable */
  }
  return 'night'
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash))
  const [theme, setTheme] = useState<Theme>(loadTheme)
  const [assets, setAssets] = useState<Asset[]>([])
  const [fleetAlerts, setFleetAlerts] = useState<Alert[]>([])
  const [results, setResults] = useState<Results | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [decisions, setDecisions] = useState<Record<string, Decision>>(loadDecisions)

  useEffect(() => {
    const on = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      /* the theme still applies for this visit */
    }
  }, [theme])

  useEffect(() => {
    api.assets().then(setAssets).catch((e) => setError(`Cannot reach the API: ${e.message}. Start it with "make api".`))
    api.allAlerts().then((r) => setFleetAlerts(r.alerts)).catch(() => undefined)
    api.results().then(setResults).catch(() => undefined)
  }, [])

  const go = (hash: string) => {
    window.location.hash = hash
  }

  const decide = useCallback((id: string, d: Decision | undefined) => {
    setDecisions((prev) => {
      const next = { ...prev }
      if (d) next[id] = d
      else delete next[id]
      try {
        localStorage.setItem(STORE, JSON.stringify(next))
      } catch {
        /* storage may be unavailable; the decision stays in memory */
      }
      return next
    })
  }, [])

  const navItem = (key: Route['name'], label: string, hash: string) => (
    <a key={key} href={hash} className={route.name === key ? 'nav on' : 'nav'} aria-current={route.name === key ? 'page' : undefined}>{label}</a>
  )

  return (
    <div className="shell">
      <header className="top">
        <div className="brand"><span className="mark" aria-hidden="true" />Watchkeeper</div>
        <nav aria-label="Sections">
          {navItem('fleet', 'Fleet', '#/')}
          {navItem('pump', 'Pump', route.name === 'pump' ? `#/pump/${route.id}` : '#/pump/PUMP-08')}
          {navItem('results', 'Results', '#/results')}
          {navItem('retrofit', 'Retrofit', '#/retrofit')}
        </nav>
        <span className="pill safe" title="This interface only reads data">Advice only · no write path</span>
        <label className="themepick">
          <span className="sr">Theme</span>
          <select value={theme} onChange={(e) => setTheme(e.target.value as Theme)} aria-label="Colour theme">
            <option value="night">Night watch</option>
            <option value="dusk">Dusk</option>
            <option value="day">Day</option>
          </select>
        </label>
      </header>

      {error && <div className="error" role="alert">{error}</div>}

      {route.name === 'fleet' && <main className="page"><Fleet assets={assets} alerts={fleetAlerts} onOpen={(id) => go(`#/pump/${id}`)} /></main>}
      {route.name === 'results' && <main className="page"><ResultsPage data={results} /></main>}
      {route.name === 'retrofit' && <main className="page"><RetrofitPage data={results} /></main>}
      {route.name === 'pump' && <PumpView assets={assets} assetId={route.id} onPick={(id) => go(`#/pump/${id}`)} decisions={decisions} decide={decide} setError={setError} />}
    </div>
  )
}

interface PumpProps {
  assets: Asset[]
  assetId: string
  onPick: (id: string) => void
  decisions: Record<string, Decision>
  decide: (id: string, d: Decision | undefined) => void
  setError: (m: string | null) => void
}

function PumpView({ assets, assetId, onPick, decisions, decide, setError }: PumpProps) {
  const [allAlerts, setAllAlerts] = useState<Alert[]>([])
  const [source, setSource] = useState<'engine' | 'mock'>('mock')
  const [tl, setTl] = useState<Timeline | null>(null)
  const [series, setSeries] = useState<Series | null>(null)
  const [seriesNote, setSeriesNote] = useState<string | null>(null)
  const [channel, setChannel] = useState<string>('discharge_pressure_kpa')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [cursor, setCursor] = useState<number | null>(null)
  const [playing, setPlaying] = useState(false)
  const timer = useRef<number | null>(null)

  const asset = useMemo(() => assets.find((a) => a.asset_id === assetId), [assets, assetId])

  useEffect(() => {
    setSelectedId(null)
    setCursor(null)
    setPlaying(false)
    Promise.all([api.alerts(assetId), api.timeline(assetId)])
      .then(([a, t]) => {
        setAllAlerts(a.alerts)
        setSource(a.source)
        setTl(t)
        setSelectedId(a.alerts[0]?.alert_id ?? null)
      })
      .catch((e) => setError(e.message))
  }, [assetId, setError])

  useEffect(() => {
    if (!asset) return
    const ch = asset.channels_available.includes(channel) ? channel : PREFERRED.find((c) => asset.channels_available.includes(c)) ?? asset.channels_available[0]
    if (ch !== channel) {
      setChannel(ch)
      return
    }
    setSeries(null)
    setSeriesNote('Loading signal…')
    api.series(assetId, ch).then((s) => {
      setSeries(s)
      setSeriesNote(null)
    }).catch((e: ApiError) => setSeriesNote(e.status === 403 ? 'Telemetry for the test pumps is not shown in this build' : e.message))
  }, [asset, assetId, channel])

  const t0 = tl ? Date.parse(tl.window_start_utc) : 0
  const t1 = tl ? Date.parse(tl.window_end_utc) : 0

  useEffect(() => {
    if (!playing || !tl) return
    timer.current = window.setInterval(() => {
      setCursor((c) => {
        const next = (c ?? t0) + 3600_000 * 2
        if (next >= t1) {
          setPlaying(false)
          return t1
        }
        return next
      })
    }, 90)
    return () => {
      if (timer.current !== null) window.clearInterval(timer.current)
    }
  }, [playing, tl, t0, t1])

  // Replay is causal by construction: a cursor only reveals alerts raised at or before it.
  const alerts = useMemo(() => (cursor === null ? allAlerts : allAlerts.filter((a) => Date.parse(a.alert_time_utc) <= cursor)), [allAlerts, cursor])
  const selected = alerts.find((a) => a.alert_id === selectedId) ?? null

  const incidents = useMemo(() => {
    const groups = new Map<string, Alert[]>()
    for (const a of alerts) {
      const key = a.incident_id ?? a.alert_id
      groups.set(key, [...(groups.get(key) ?? []), a])
    }
    return [...groups.entries()]
  }, [alerts])
  const sizeOf = (a: Alert) => allAlerts.filter((x) => (x.incident_id ?? x.alert_id) === (a.incident_id ?? a.alert_id)).length

  const groups: [string, Asset[]][] = [
    ['Training pumps', assets.filter((a) => a.split === 'train')],
    ['Validation pumps', assets.filter((a) => a.split === 'validation')],
    ['Test pumps (labels hidden)', assets.filter((a) => a.split === 'test')],
  ]

  return (
    <div className="pumpview">
      <aside className="side" aria-label="Pumps">
        {groups.map(([title, list]) => (
          <section key={title}>
            <h3>{title}</h3>
            <ul>
              {list.map((a) => (
                <li key={a.asset_id}>
                  <button className={a.asset_id === assetId ? 'pump active' : 'pump'} onClick={() => onPick(a.asset_id)}>
                    <span className="pid">{a.asset_id}</span>
                    <span className="psys">{a.system}</span>
                    <span className={`tier t${TIER[a.instrumentation_tier][1]}`} title={TIER_HELP[a.instrumentation_tier]}>{TIER[a.instrumentation_tier]}</span>
                    <span className="count" title="alerts">{a.alert_count}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </aside>

      <main className="main">
        {asset && (
          <>
            <section className="assethead">
              <h1>{asset.asset_id} <small>{asset.system}</small></h1>
              <p className="muted">
                {asset.site} · {asset.profile.replace(/_/g, ' ').toLowerCase()} · control {asset.control.replace(/_/g, ' ').toLowerCase()} ·
                {' '}commissioned {asset.commissioned_year} · {asset.motor_rated_kw} kW · {asset.fluid}
              </p>
              <p className="tiernote"><span className={`tier t${TIER[asset.instrumentation_tier][1]}`}>{TIER[asset.instrumentation_tier]}</span> {TIER_HELP[asset.instrumentation_tier]}</p>
              <div className="controls">
                <label className="chan">
                  Signal
                  <select value={channel} onChange={(e) => setChannel(e.target.value)}>
                    {asset.channels_available.map((c) => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
                  </select>
                </label>
                {tl && (
                  <div className="replay" role="group" aria-label="Replay">
                    <button onClick={() => { if (cursor === null || cursor >= t1) setCursor(t0); setPlaying((p) => !p) }}>{playing ? 'Pause' : cursor === null ? 'Replay' : 'Play'}</button>
                    <input type="range" min={t0} max={t1} step={3600_000} value={cursor ?? t1} aria-label="Replay time"
                           onChange={(e) => { setPlaying(false); setCursor(Number(e.target.value)) }} />
                    <span className="muted small">{cursor === null ? 'showing the whole week' : `only what was known by ${when(new Date(cursor).toISOString())}`}</span>
                    {cursor !== null && <button className="ghost" onClick={() => { setPlaying(false); setCursor(null) }}>Show all</button>}
                  </div>
                )}
              </div>
              <p className="muted small">Alerts from {source === 'engine' ? 'the detector (a model that did not train on this pump)' : 'mock examples'}.</p>
            </section>

            {tl && <TimelineChart tl={tl} series={series} seriesNote={seriesNote} channel={channel} alerts={alerts} selectedId={selectedId} onSelect={setSelectedId} cursor={cursor} />}

            <div className="lower">
              <section className="alertlist" aria-label="Alerts">
                <h3>Incidents ({incidents.length}) · alerts ({alerts.length})</h3>
                {alerts.length === 0 && <p className="muted">{cursor === null ? 'No alerts for this pump yet.' : 'Nothing has been raised yet at this point in the replay.'}</p>}
                {incidents.map(([key, list]) => (
                  <div key={key} className="incident">
                    {list.length > 1 && <p className="inchead">Incident {key.split('-').slice(-1)[0]} · {list.length} related alerts</p>}
                    <ul>
                      {list.map((a) => (
                        <li key={a.alert_id}>
                          <button className={a.alert_id === selectedId ? 'row active' : 'row'} onClick={() => setSelectedId(a.alert_id)}>
                            <i className={`dot ${a.event_class === 'SENSOR' ? 'sensor' : 'machine'}`} />
                            <span className="rt">{new Date(a.alert_time_utc).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })}</span>
                            <span className="rf">{pretty(a.fault_type)}</span>
                            <span className={`stagechip s-${a.stage ?? 'watch'}`}>{STAGE_LABEL[a.stage ?? 'watch']}</span>
                            {decisions[a.alert_id] && <span className={`dec ${decisions[a.alert_id]}`}>{decisions[a.alert_id]}</span>}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </section>
              {selected ? (
                <AlertCard alert={selected} incidentSize={sizeOf(selected)} decision={decisions[selected.alert_id]} onDecide={(d) => decide(selected.alert_id, d)} />
              ) : (
                <section className="card empty"><p className="muted">Select an alert to see the evidence behind it.</p></section>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
