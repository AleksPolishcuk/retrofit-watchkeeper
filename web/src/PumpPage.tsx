import { useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError } from './api'
import type { Decision } from './decisions'
import { SignalChart } from './charts'
import Icon from './icons'
import { basisText, headline, pretty, STAGE_LABEL, when } from './stage'
import TimelineChart from './Timeline'
import WhatIf from './WhatIf'
import type { Alert, Asset, Series, Timeline } from './types'

const TIER: Record<string, string> = { T0_LEGACY: 'T0', T1_RETROFIT: 'T1', T2_FULL: 'T2' }
const TIER_HELP: Record<string, string> = {
  T0_LEGACY: 'Legacy: motor current, discharge pressure, temperatures',
  T1_RETROFIT: 'Low-cost retrofit: adds suction pressure and a wireless vibration sensor',
  T2_FULL: 'Fully instrumented: adds flow, power, winding temperature, fast vibration',
}
const TIER_NOTE: Record<string, string> = {
  T0_LEGACY: 'Legacy instrumentation: fewer channels, so fewer causes can be told apart.',
  T1_RETROFIT: 'Retrofit instrumentation: vibration and bearing temperature arrive every few minutes.',
  T2_FULL: 'Fully instrumented pump.',
}
const META: Record<string, [string, string]> = {
  motor_speed_rpm: ['Motor speed', 'rpm'], motor_current_a: ['Motor current', 'A'], motor_power_kw: ['Motor power', 'kW'],
  suction_pressure_kpa: ['Suction pressure', 'kPa'], discharge_pressure_kpa: ['Discharge pressure', 'kPa'], flow_m3_h: ['Flow', 'm³/h'],
  fluid_temp_c: ['Fluid temperature', '°C'], bearing_temp_c: ['Bearing temperature', '°C'], motor_winding_temp_c: ['Winding temperature', '°C'],
  vibration_rms_mm_s: ['Vibration RMS', 'mm/s'], vibration_accel_rms_g: ['Vibration acceleration', 'g'], vibration_crest_factor: ['Vibration crest factor', ''],
  valve_position_pct: ['Valve position', '%'],
}
const DEFAULT_SIGNALS = ['vibration_rms_mm_s', 'discharge_pressure_kpa', 'motor_current_a', 'suction_pressure_kpa', 'bearing_temp_c']
const PREFERRED = ['discharge_pressure_kpa', 'motor_current_a', 'motor_power_kw']
const RANGES = { '6h': { label: '6 h', before: 6, after: 2, step: 5 }, '24h': { label: '24 h', before: 24, after: 6, step: 15 }, '3d': { label: '3 days', before: 72, after: 12, step: 60 }, week: { label: 'Whole week', before: 0, after: 0, step: 120 } } as const
type RangeKey = keyof typeof RANGES
type Tab = 'overview' | 'diagnostics' | 'evidence' | 'recommendations'
const TABS: [Tab, string][] = [['overview', 'Overview'], ['diagnostics', 'Diagnostics'], ['evidence', 'Evidence'], ['recommendations', 'Recommendations']]
const HOUR = 3600_000

interface Props {
  assets: Asset[]
  assetId: string
  alertId?: string
  decisions: Record<string, Decision>
  decide: (id: string, d: Decision | undefined) => void
  setError: (m: string | null) => void
  go: (hash: string) => void
}

function Kind({ a }: { a: Alert }) {
  return a.event_class === 'SENSOR'
    ? <span className="kind sensor"><Icon name="sensor" /> Instrument</span>
    : <span className="kind machine"><Icon name="wrench" /> Machine</span>
}

function Hero({ alert, size }: { alert: Alert; size: number }) {
  return (
    <div className={`hero h-${alert.stage ?? 'watch'}`}>
      <div className="top">
        <span className="eyebrow">{headline(alert)}</span>
        {alert.stage && <span className={`stagechip s-${alert.stage}`}>{STAGE_LABEL[alert.stage]}</span>}
      </div>
      <h2>{pretty(alert.fault_type)}</h2>
      <p className="muted" style={{ margin: 0 }}>
        <Kind a={alert} /> · {alert.asset_id} · raised {when(alert.alert_time_utc)}
        {alert.incident_id && <> · incident <code>{alert.incident_id.split('-').slice(-1)[0]}</code> ({size} alert{size === 1 ? '' : 's'})</>}
      </p>
      {alert.consequence && <p style={{ margin: '6px 0 0' }}>{alert.consequence}</p>}
      {alert.stage && <p className="basis" style={{ margin: 0 }}>{basisText(alert.stage_basis)}</p>}
    </div>
  )
}

export default function PumpPage({ assets, assetId, alertId, decisions, decide, setError, go }: Props) {
  const [allAlerts, setAllAlerts] = useState<Alert[]>([])
  const [source, setSource] = useState<'engine' | 'mock'>('mock')
  const [tl, setTl] = useState<Timeline | null>(null)
  const [series, setSeries] = useState<Series | null>(null)
  const [seriesNote, setSeriesNote] = useState<string | null>(null)
  const [channel, setChannel] = useState<string>('discharge_pressure_kpa')
  const [selectedId, setSelectedId] = useState<string | null>(alertId ?? null)
  const [cursor, setCursor] = useState<number | null>(null)
  const [playing, setPlaying] = useState(false)
  const [tab, setTab] = useState<Tab>('overview')
  const [filter, setFilter] = useState<'active' | 'reviewed'>('active')
  const [range, setRange] = useState<RangeKey>('24h')
  const [sig, setSig] = useState<Record<string, Series | 'none'>>({})
  const timer = useRef<number | null>(null)

  const asset = useMemo(() => assets.find((a) => a.asset_id === assetId), [assets, assetId])

  useEffect(() => {
    setCursor(null)
    setPlaying(false)
    setSig({})
    Promise.all([api.alerts(assetId), api.timeline(assetId)])
      .then(([a, t]) => {
        setAllAlerts(a.alerts)
        setSource(a.source)
        setTl(t)
        setSelectedId((cur) => (cur && a.alerts.some((x) => x.alert_id === cur) ? cur : a.alerts[0]?.alert_id ?? null))
      })
      .catch((e) => setError(e.message))
  }, [assetId, setError])

  useEffect(() => {
    if (alertId) setSelectedId(alertId)
  }, [alertId])

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
        const next = (c ?? t0) + HOUR * 2
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
  const selected = allAlerts.find((a) => a.alert_id === selectedId) ?? alerts[0] ?? null
  const sizeOf = (a: Alert) => allAlerts.filter((x) => (x.incident_id ?? x.alert_id) === (a.incident_id ?? a.alert_id)).length

  const visible = alerts.filter((a) => (filter === 'reviewed' ? decisions[a.alert_id] : !decisions[a.alert_id]))
  const incidents = useMemo(() => {
    const groups = new Map<string, Alert[]>()
    for (const a of visible) {
      const key = a.incident_id ?? a.alert_id
      groups.set(key, [...(groups.get(key) ?? []), a])
    }
    return [...groups.entries()]
  }, [visible])
  const nActive = alerts.filter((a) => !decisions[a.alert_id]).length
  const nReviewed = alerts.length - nActive

  // channels shown as evidence for the selected alert: the ones that drove it, then sensible defaults
  const signalChannels = useMemo(() => {
    if (!asset || !selected) return []
    const own = selected.evidence.map((e) => e.channel).filter((c) => META[c])
    const all = [...own, ...DEFAULT_SIGNALS].filter((c, i, arr) => arr.indexOf(c) === i && asset.channels_available.includes(c))
    return all.slice(0, 3)
  }, [asset, selected])

  const alertMs = selected ? Date.parse(selected.alert_time_utc) : 0
  const rg = RANGES[range]
  const fromMs = range === 'week' ? t0 : Math.max(t0, alertMs - rg.before * HOUR)
  const toMs = range === 'week' ? t1 : Math.min(t1, alertMs + rg.after * HOUR)

  useEffect(() => {
    if (tab !== 'evidence' || !asset?.telemetry_served) return
    signalChannels.forEach((c) => {
      const key = `${c}|${rg.step}`
      if (sig[key] !== undefined) return
      api.series(assetId, c, rg.step).then((s) => setSig((m) => ({ ...m, [key]: s }))).catch(() => setSig((m) => ({ ...m, [key]: 'none' })))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, signalChannels.join(','), rg.step, assetId, asset?.telemetry_served])

  const step = (d: number) => {
    const list = allAlerts
    const i = list.findIndex((a) => a.alert_id === selected?.alert_id)
    const n = list[Math.min(list.length - 1, Math.max(0, i + d))]
    if (n) setSelectedId(n.alert_id)
  }

  const picker = (
    <div className="pickrow">
      <button className="btn sm" onClick={() => step(-1)} aria-label="Previous alert"><Icon name="back" /></button>
      <select value={selected?.alert_id ?? ''} onChange={(e) => setSelectedId(e.target.value)} aria-label="Alert">
        {allAlerts.map((a) => <option key={a.alert_id} value={a.alert_id}>{when(a.alert_time_utc)} · {pretty(a.fault_type)} · {a.stage ? STAGE_LABEL[a.stage] : ''}</option>)}
      </select>
      <button className="btn sm" onClick={() => step(1)} aria-label="Next alert"><Icon name="next" /></button>
      <span className="muted small">{allAlerts.findIndex((a) => a.alert_id === selected?.alert_id) + 1} of {allAlerts.length}</span>
    </div>
  )

  const empty = <div className="card"><p className="muted" style={{ margin: 0 }}>No alerts for this pump{cursor !== null ? ' at this point of the replay' : ''}. Nothing stands out against its own normal.</p></div>

  if (!asset) return <p className="muted">Loading pump…</p>
  const decision = selected ? decisions[selected.alert_id] : undefined
  const top = allAlerts.reduce<Alert | null>((b, a) => (b === null || (a.stage && b.stage && ['watch', 'possible', 'likely', 'very_likely'].indexOf(a.stage) > ['watch', 'possible', 'likely', 'very_likely'].indexOf(b.stage)) ? a : b), null)

  return (
    <div>
      <a className="crumb" href="#/pumps" onClick={(e) => { e.preventDefault(); go('#/pumps') }}><Icon name="back" /> All pumps</a>
      <div className="pumphead">
        <div>
          <h1>{asset.asset_id} <span className="muted" style={{ fontSize: 16, fontWeight: 500 }}>{asset.system}</span>
            {top?.stage ? <span className={`stagechip s-${top.stage}`}>{STAGE_LABEL[top.stage]}</span> : <span className="stagechip none">No alerts</span>}
            <span className={`tier t${TIER[asset.instrumentation_tier][1]}`} title={TIER_HELP[asset.instrumentation_tier]}>{TIER[asset.instrumentation_tier]}</span>
          </h1>
          <p className="meta">{asset.site} · {asset.profile.replace(/_/g, ' ').toLowerCase()} · control {asset.control.replace(/_/g, ' ').toLowerCase()} · commissioned {asset.commissioned_year} · {asset.motor_rated_kw} kW · {asset.fluid}. {TIER_HELP[asset.instrumentation_tier]}.</p>
        </div>
        <div className="acts">
          <select value={assetId} onChange={(e) => go(`#/pump/${e.target.value}`)} aria-label="Switch pump">
            {assets.map((a) => <option key={a.asset_id} value={a.asset_id}>{a.asset_id} · {a.system}</option>)}
          </select>
          <button className="btn" onClick={() => window.print()}><Icon name="printer" /> Print report</button>
        </div>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map(([k, label]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{label}</button>)}
      </div>

      {tab === 'overview' && (
        <div className="cols">
          <div className="card alertlist" aria-label="Alerts">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
              <h2 style={{ margin: 0 }}>Alerts</h2>
              <div className="seg" role="group" aria-label="Filter">
                <button className={filter === 'active' ? 'on' : ''} onClick={() => setFilter('active')}>Active ({nActive})</button>
                <button className={filter === 'reviewed' ? 'on' : ''} onClick={() => setFilter('reviewed')}>Reviewed ({nReviewed})</button>
              </div>
            </div>
            {visible.length === 0 && <p className="muted small">{filter === 'reviewed' ? 'Nothing reviewed yet. Approve an inspection or mark a false alarm on an alert.' : cursor === null ? 'No active alerts.' : 'Nothing has been raised yet at this point of the replay.'}</p>}
            {incidents.map(([key, list]) => (
              <div key={key}>
                {list.length > 1 && <p className="inchead">Incident {key.split('-').slice(-1)[0]} · {list.length} related</p>}
                <ul>
                  {list.map((a) => (
                    <li key={a.alert_id}>
                      <button className={a.alert_id === selected?.alert_id ? 'row active' : 'row'} onClick={() => setSelectedId(a.alert_id)}>
                        <i className={`dot ${a.event_class === 'SENSOR' ? 'sensor' : 'machine'}`} title={a.event_class === 'SENSOR' ? 'instrument' : 'machine'} />
                        <span className="rt">{when(a.alert_time_utc)}</span>
                        <span className="rf">{pretty(a.fault_type)}</span>
                        <span className={`stagechip s-${a.stage ?? 'watch'}`}>{STAGE_LABEL[a.stage ?? 'watch']}</span>
                        {decisions[a.alert_id] && <span className={`dec ${decisions[a.alert_id]}`}>{decisions[a.alert_id] === 'approved' ? 'inspection approved' : 'marked false alarm'}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="stack">
            {selected ? <Hero alert={selected} size={sizeOf(selected)} /> : empty}
            <div className="card">
              <div className="controls">
                <label className="chan">Signal
                  <select value={channel} onChange={(e) => setChannel(e.target.value)}>
                    {asset.channels_available.map((c) => <option key={c} value={c}>{META[c]?.[0] ?? c.replace(/_/g, ' ')}</option>)}
                  </select>
                </label>
                {tl && (
                  <div className="replay" role="group" aria-label="Replay">
                    <button className="btn sm primary" onClick={() => { if (cursor === null || cursor >= t1) setCursor(t0); setPlaying((p) => !p) }}>
                      <Icon name={playing ? 'pause' : 'play'} /> {playing ? 'Pause' : cursor === null ? 'Replay' : 'Play'}
                    </button>
                    <input type="range" min={t0} max={t1} step={HOUR} value={cursor ?? t1} aria-label="Replay time" onChange={(e) => { setPlaying(false); setCursor(Number(e.target.value)) }} />
                    {cursor !== null && <button className="btn sm" onClick={() => { setPlaying(false); setCursor(null) }}>Show all</button>}
                  </div>
                )}
              </div>
              <p className="muted small" style={{ margin: '0 0 8px' }}>
                {cursor === null ? 'Whole recorded week.' : `Replay: only what was known by ${when(new Date(cursor).toISOString())}.`} Alerts from {source === 'engine' ? 'the detector (a model that did not train on this pump)' : 'mock examples'}.
              </p>
              {tl && <TimelineChart tl={tl} series={series} seriesNote={seriesNote} channel={channel} alerts={alerts} selectedId={selected?.alert_id ?? null} onSelect={setSelectedId} cursor={cursor} />}
            </div>
          </div>
        </div>
      )}

      {tab === 'diagnostics' && (selected ? (
        <div className="stack">
          {picker}
          <Hero alert={selected} size={sizeOf(selected)} />
          <div className="grid2">
            <div className="card"><h3>What it may mean</h3><p style={{ margin: 0 }}>{selected.consequence ?? 'Not described.'}</p></div>
            <div className="card"><h3>Check this first</h3><p style={{ margin: 0 }}>{selected.check ?? selected.recommended_action}</p></div>
            <div className="card">
              <h3>Machine or instrument?</h3>
              {selected.sensor_check ? <p style={{ margin: 0 }}><span className={`pill v-${selected.sensor_check.verdict}`}>{selected.sensor_check.verdict}</span> {selected.sensor_check.reason}</p> : <p className="muted" style={{ margin: 0 }}>Not assessed.</p>}
              {selected.alternatives && selected.alternatives.length > 0 && <p className="muted small" style={{ margin: '10px 0 0' }}>Also considered: {selected.alternatives.map((a) => pretty(a.fault_type)).join(', ')}</p>}
            </div>
            <div className="card">
              <h3>What limits our certainty</h3>
              <p>Data quality: <span className={`pill q-${selected.uncertainty?.data_quality ?? 'ok'}`}>{selected.uncertainty?.data_quality ?? 'ok'}</span></p>
              <p className="muted small">{(selected.uncertainty?.missing_channels ?? []).length > 0 ? `Not measured on this pump: ${(selected.uncertainty?.missing_channels ?? []).map((m) => m.replace(/_/g, ' ')).join(', ')}.` : 'All key channels are measured.'}</p>
              {selected.tier && <p className="muted small">{TIER_NOTE[selected.tier]}</p>}
              <p className="muted small" style={{ margin: 0 }}>Time to act: {selected.time_to_act ?? selected.time_to_act_note ?? 'not estimated'}. The stage word is a back-test count, not a probability.</p>
            </div>
          </div>
        </div>
      ) : empty)}

      {tab === 'evidence' && (selected ? (
        <div className="stack">
          {picker}
          <div className="cols">
            <div className="card">
              <h2>Evidence</h2>
              {selected.evidence.length === 0 ? <p className="muted">No single channel stands out.</p> : (
                <ul className="evidence">
                  {selected.evidence.map((e, i) => (
                    <li key={i}>
                      <code>{e.channel}</code>
                      <span>{e.text}</span>
                      {e.z !== null && <b className={e.z < 0 ? 'neg' : 'pos'}>{e.z > 0 ? '+' : ''}{e.z.toFixed(1)}σ</b>}
                    </li>
                  ))}
                </ul>
              )}
              <p className="muted small" style={{ marginTop: 10 }}>σ is a robust standard deviation from this pump's own baseline at the same operating regime.</p>
            </div>
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
                <h2 style={{ margin: 0 }}>Key signals around the alert</h2>
                <div className="seg" role="group" aria-label="Range">
                  {(Object.keys(RANGES) as RangeKey[]).map((k) => <button key={k} className={range === k ? 'on' : ''} onClick={() => setRange(k)}>{RANGES[k].label}</button>)}
                </div>
              </div>
              {!asset.telemetry_served ? <p className="muted">Telemetry for the test pumps is not shown in this build.</p> : (
                <div className="sigs">
                  {signalChannels.map((c) => {
                    const s = sig[`${c}|${rg.step}`]
                    return <SignalChart key={c} series={s && s !== 'none' ? s : null} alertMs={alertMs} fromMs={fromMs} toMs={toMs} label={META[c]?.[0] ?? c} unit={META[c]?.[1] ?? ''} />
                  })}
                </div>
              )}
              <p className="muted small" style={{ marginTop: 10 }}>The channels shown are the ones that drove this alert. The dashed line is when it was raised.</p>
            </div>
          </div>
        </div>
      ) : empty)}

      {tab === 'recommendations' && (selected ? (
        <div className="stack">
          {picker}
          <Hero alert={selected} size={sizeOf(selected)} />
          <div className="cols">
            <div className="card">
              <h2>What should you do?</h2>
              <ol className="steps" style={{ margin: 0, padding: 0, listStyle: 'none' }}>
                <li><div><b>Check this first</b>{selected.check ?? selected.recommended_action}</div></li>
                <li><div><b>Recommended action</b>{selected.recommended_action}</div></li>
                <li><div><b>Record your decision</b><span className="muted small">Kept in this browser only. Watchkeeper sends nothing to the machine.</span></div></li>
              </ol>
              <div className="decide" role="group" aria-label="Human decision" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 14 }}>
                <button className={decision === 'approved' ? 'btn on-ok' : 'btn primary'} onClick={() => decide(selected.alert_id, decision === 'approved' ? undefined : 'approved')}>
                  <Icon name="check" /> {decision === 'approved' ? 'Inspection approved' : 'Approve inspection'}
                </button>
                <button className={decision === 'rejected' ? 'btn on-bad' : 'btn'} onClick={() => decide(selected.alert_id, decision === 'rejected' ? undefined : 'rejected')}>
                  {decision === 'rejected' ? 'Marked as false alarm' : 'Mark as false alarm'}
                </button>
              </div>
              {selected.model_version && <p className="muted small" style={{ marginTop: 12, marginBottom: 0 }}>Advice only. Model <code>{selected.model_version}</code>. Existing alarms and trips stay authoritative.</p>}
            </div>
            <div className="card">
              <h2>What if?</h2>
              <p className="muted small">Compare the pump as it is with the pump after the matching maintenance action, in the organizers' sandbox.</p>
              <WhatIf key={selected.alert_id} alert={selected} />
            </div>
          </div>
        </div>
      ) : empty)}
    </div>
  )
}
