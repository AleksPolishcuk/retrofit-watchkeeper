import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, ApiError } from './api'
import AlertCard, { type Decision } from './AlertCard'
import TimelineChart from './Timeline'
import type { Alert, Asset, Series, Timeline } from './types'

const TIER: Record<string, string> = { T0_LEGACY: 'T0', T1_RETROFIT: 'T1', T2_FULL: 'T2' }
const TIER_HELP: Record<string, string> = {
  T0_LEGACY: 'Legacy: motor current, discharge pressure, temperatures',
  T1_RETROFIT: 'Low-cost retrofit: adds suction pressure and a wireless vibration sensor',
  T2_FULL: 'Fully instrumented: adds flow, power, winding temperature, fast vibration',
}
const PREFERRED = ['discharge_pressure_kpa', 'motor_current_a', 'motor_power_kw']
const STORE = 'watchkeeper.decisions'

function loadDecisions(): Record<string, Decision> {
  try {
    return JSON.parse(localStorage.getItem(STORE) ?? '{}')
  } catch {
    return {}
  }
}

export default function App() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [assetId, setAssetId] = useState<string>('PUMP-08')
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [source, setSource] = useState<'engine' | 'mock'>('mock')
  const [tl, setTl] = useState<Timeline | null>(null)
  const [series, setSeries] = useState<Series | null>(null)
  const [seriesNote, setSeriesNote] = useState<string | null>(null)
  const [channel, setChannel] = useState<string>('discharge_pressure_kpa')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [decisions, setDecisions] = useState<Record<string, Decision>>(loadDecisions)

  const asset = useMemo(() => assets.find((a) => a.asset_id === assetId), [assets, assetId])

  useEffect(() => {
    api.assets().then(setAssets).catch((e) => setError(`Cannot reach the API: ${e.message}. Start it with "make api".`))
  }, [])

  useEffect(() => {
    if (!assetId) return
    setSelectedId(null)
    Promise.all([api.alerts(assetId), api.timeline(assetId)])
      .then(([a, t]) => {
        setAlerts(a.alerts)
        setSource(a.source)
        setTl(t)
        setSelectedId(a.alerts[0]?.alert_id ?? null)
      })
      .catch((e) => setError(e.message))
  }, [assetId])

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

  const selected = alerts.find((a) => a.alert_id === selectedId) ?? null
  const groups: [string, Asset[]][] = [
    ['Training pumps', assets.filter((a) => a.split === 'train')],
    ['Validation pumps', assets.filter((a) => a.split === 'validation')],
    ['Test pumps (labels hidden)', assets.filter((a) => a.split === 'test')],
  ]

  return (
    <div className="app">
      <header className="top">
        <div className="brand"><span className="mark" aria-hidden="true" />Watchkeeper</div>
        <span className="pill safe" title="This interface only reads data">Advice only · no write path</span>
        <span className={`pill src-${source}`} title="Where the alerts shown come from">
          alerts: {source === 'engine' ? 'detector output' : 'mock examples'}
        </span>
      </header>

      {error && <div className="error" role="alert">{error}</div>}

      <aside className="side" aria-label="Pumps">
        {groups.map(([title, list]) => (
          <section key={title}>
            <h3>{title}</h3>
            <ul>
              {list.map((a) => (
                <li key={a.asset_id}>
                  <button className={a.asset_id === assetId ? 'pump active' : 'pump'} onClick={() => setAssetId(a.asset_id)}>
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
              <label className="chan">
                Signal
                <select value={channel} onChange={(e) => setChannel(e.target.value)}>
                  {asset.channels_available.map((c) => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
                </select>
              </label>
            </section>

            {tl && <TimelineChart tl={tl} series={series} seriesNote={seriesNote} channel={channel} alerts={alerts} selectedId={selectedId} onSelect={setSelectedId} />}

            <div className="lower">
              <section className="alertlist" aria-label="Alerts">
                <h3>Alerts ({alerts.length})</h3>
                {alerts.length === 0 && <p className="muted">No alerts for this pump yet.</p>}
                <ul>
                  {alerts.map((a) => (
                    <li key={a.alert_id}>
                      <button className={a.alert_id === selectedId ? 'row active' : 'row'} onClick={() => setSelectedId(a.alert_id)}>
                        <i className={`dot ${a.event_class === 'SENSOR' ? 'sensor' : 'machine'}`} />
                        <span className="rt">{new Date(a.alert_time_utc).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })}</span>
                        <span className="rf">{a.fault_type.replace(/_/g, ' ').toLowerCase()}</span>
                        <span className="rc">{(a.confidence * 100).toFixed(0)}%</span>
                        {decisions[a.alert_id] && <span className={`dec ${decisions[a.alert_id]}`}>{decisions[a.alert_id]}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
              {selected ? (
                <AlertCard alert={selected} decision={decisions[selected.alert_id]} onDecide={(d) => decide(selected.alert_id, d)} />
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
