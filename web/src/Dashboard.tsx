import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import { Donut, Sparkline } from './charts'
import Icon from './icons'
import { pretty, STAGE_LABEL, STAGES, stageRank, when } from './stage'
import type { Alert, Asset, Healthy, ReportSet, Results, Stage } from './types'

const TIER: Record<string, string> = { T0_LEGACY: 'T0', T1_RETROFIT: 'T1', T2_FULL: 'T2' }
const PREFERRED = ['discharge_pressure_kpa', 'motor_current_a', 'motor_power_kw', 'fluid_temp_c']
const STAGE_COLOR: Record<Stage, string> = { watch: '#8a9bb3', possible: '#3b7bf0', likely: '#e59a1a', very_likely: '#d8383f' }

interface Props {
  assets: Asset[]
  alerts: Alert[]
  results: Results | null
  onOpen: (id: string, alertId?: string) => void
}

function PumpArt() {
  return (
    <svg className="art" viewBox="0 0 260 84" aria-hidden="true">
      <path className="pipe" d="M0 58h70M190 58h70M30 58V22h50" />
      <rect className="body2" x={72} y={36} width={44} height={44} rx={10} />
      <circle className="body" cx={138} cy={58} r={28} />
      <circle cx={138} cy={58} r={11} fill="var(--panel)" />
      <rect className="body" x={160} y={42} width={40} height={32} rx={8} />
    </svg>
  )
}

export default function Dashboard({ assets, alerts, results, onOpen }: Props) {
  const [trend, setTrend] = useState<Record<string, number[]>>({})

  useEffect(() => {
    assets.filter((a) => a.telemetry_served).forEach((a) => {
      const ch = PREFERRED.find((c) => a.channels_available.includes(c)) ?? a.channels_available[0]
      api.series(a.asset_id, ch, 180).then((s) => setTrend((t) => ({ ...t, [a.asset_id]: s.v }))).catch(() => undefined)
    })
  }, [assets])

  const rows = useMemo(() => {
    const out = assets.map((asset) => {
      const mine = alerts.filter((a) => a.asset_id === asset.asset_id)
      const top = mine.reduce<Alert | null>((best, a) => (best === null || stageRank(a.stage) > stageRank(best.stage) ? a : best), null)
      const t0 = Date.parse(asset.window_start_utc)
      const t1 = Date.parse(asset.window_end_utc)
      return {
        asset, mine, top,
        incidents: new Set(mine.map((a) => a.incident_id ?? a.alert_id)).size,
        ticks: mine.map((a) => (Date.parse(a.alert_time_utc) - t0) / (t1 - t0)),
      }
    })
    return out.sort((a, b) => stageRank(b.top?.stage) - stageRank(a.top?.stage) || b.mine.length - a.mine.length)
  }, [assets, alerts])

  const machine = alerts.filter((a) => a.event_class === 'MACHINE').length
  const instrument = alerts.length - machine
  const strong = alerts.filter((a) => stageRank(a.stage) >= 2)
  const strongPumps = new Set(strong.map((a) => a.asset_id)).size
  const levelCounts = STAGES.map((s) => ({ label: STAGE_LABEL[s], value: alerts.filter((a) => a.stage === s).length, color: STAGE_COLOR[s] }))
  const recent = [...alerts].sort((a, b) => stageRank(b.stage) - stageRank(a.stage) || b.alert_time_utc.localeCompare(a.alert_time_utc)).slice(0, 5)
  const hold = results?.report ? ((results.report as Record<string, ReportSet>)['hold fleets (24 pumps)'] as ReportSet | undefined) : undefined
  const healthy = results?.report?.healthy as unknown as Healthy | undefined
  const tone = strongPumps >= 3 ? 'urgent' : strongPumps > 0 ? 'attn' : ''
  const top = rows[0]?.top

  return (
    <section aria-label="Dashboard">
      <div className={`banner ${tone}`}>
        <div className="bico"><Icon name={strongPumps > 0 ? 'alert' : 'shield'} /></div>
        <div>
          <h1>{strong.length > 0 ? `${strong.length} alerts at Likely or above, on ${strongPumps} of ${assets.length} pumps` : alerts.length > 0 ? 'Alerts at Watch or Possible only' : 'No alerts in the recorded data'}</h1>
          <p>{alerts.length} alerts in the recorded weeks: {machine} machine, {instrument} instrument. Open a pump to see what we think, why, and what to check first.</p>
        </div>
        {top && <button className="btn primary" onClick={() => onOpen(top.asset_id, top.alert_id)}>Open strongest <Icon name="next" /></button>}
        <PumpArt />
      </div>

      <div className="kpis">
        <div className="card kpi">
          <div className="kico"><Icon name="pump" /></div>
          <b>{assets.length}</b><span>pumps monitored</span>
          <span className="small">T0 {assets.filter((a) => a.instrumentation_tier === 'T0_LEGACY').length} · T1 {assets.filter((a) => a.instrumentation_tier === 'T1_RETROFIT').length} · T2 {assets.filter((a) => a.instrumentation_tier === 'T2_FULL').length}</span>
        </div>
        <div className="card kpi">
          <div className="kico"><Icon name="bell" /></div>
          <b>{alerts.length}</b><span>alerts in the recorded week</span>
          <div className="bar" aria-hidden="true"><i className="m" style={{ width: `${(machine / Math.max(alerts.length, 1)) * 100}%` }} /><i className="s" style={{ width: `${(instrument / Math.max(alerts.length, 1)) * 100}%` }} /></div>
          <span className="small" style={{ gridColumn: '1 / -1' }}>{machine} machine · {instrument} instrument</span>
        </div>
        <div className="card kpi">
          <div className="kico"><Icon name="chart" /></div>
          <b>{hold ? hold.wk.composite.toFixed(1) : '—'}</b><span>score on untouched test fleets</span>
          <span className="small">baseline {hold?.b1 ? hold.b1.composite.toFixed(1) : '—'}, random alerts {hold ? hold.null_random_alerts.toFixed(1) : '—'}</span>
        </div>
        <div className="card kpi">
          <div className="kico"><Icon name="eye" /></div>
          <b>{healthy ? healthy.per_pump_month.toFixed(1) : '—'}</b><span>false alerts per pump-month</span>
          <span className="small">on healthy simulated pumps</span>
        </div>
      </div>

      <div className="dashgrid">
        <div className="card">
          <h2>Pump overview</h2>
          <div className="tablewrap">
            <table className="fleettable pumptable">
              <thead><tr><th>Pump</th><th>Status</th><th>Trend, recorded week</th><th>Check first</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.asset.asset_id} className="pumprow" tabIndex={0} onClick={() => onOpen(r.asset.asset_id, r.top?.alert_id)}
                      onKeyDown={(e) => e.key === 'Enter' && onOpen(r.asset.asset_id, r.top?.alert_id)}>
                    <td className="pumpname"><b>{r.asset.asset_id} <span className={`tier t${TIER[r.asset.instrumentation_tier][1]}`}>{TIER[r.asset.instrumentation_tier]}</span></b><span>{r.asset.system}</span></td>
                    <td>
                      {r.top ? <><span className={`stagechip s-${r.top.stage ?? 'watch'}`}>{STAGE_LABEL[r.top.stage ?? 'watch']}</span><span className="small muted" style={{ display: 'block', marginTop: 3 }}>{pretty(r.top.fault_type)} · {r.mine.length} alerts, {r.incidents} incidents</span></>
                        : <span className="stagechip none">No alerts</span>}
                    </td>
                    <td><Sparkline values={trend[r.asset.asset_id] ?? []} ticks={r.ticks} empty={r.asset.telemetry_served ? undefined : 'telemetry not shown'} /></td>
                    <td><span className="checkfirst">{r.top?.check ?? (r.asset.split === 'test' ? 'Labels and telemetry are held by the organizers.' : '—')}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small" style={{ marginTop: 10 }}>Orange ticks on a trend mark alerts. Alerts for the nine public pumps come from a model that was not trained on them; the three test pumps show the submitted alerts.</p>
        </div>

        <div className="stack">
          <div className="card recent">
            <h2>Strongest alerts</h2>
            <ul>
              {recent.map((a) => (
                <li key={a.alert_id} className="item">
                  <div className={`ico ${a.event_class === 'SENSOR' ? 'sensor' : 'machine'}`}><Icon name={a.event_class === 'SENSOR' ? 'sensor' : 'wrench'} label={a.event_class === 'SENSOR' ? 'instrument' : 'machine'} /></div>
                  <div>
                    <b>{a.asset_id} · {pretty(a.fault_type)}</b>
                    <span className="sub">{when(a.alert_time_utc)} · <span className={`stagechip s-${a.stage ?? 'watch'}`}>{STAGE_LABEL[a.stage ?? 'watch']}</span></span>
                  </div>
                  <button className="btn sm" onClick={() => onOpen(a.asset_id, a.alert_id)}>View</button>
                </li>
              ))}
              {recent.length === 0 && <li className="muted">No alerts yet.</li>}
            </ul>
          </div>
          <div className="card">
            <h2>Alerts by level</h2>
            <div className="donutwrap">
              <Donut parts={levelCounts} centre={String(alerts.length)} caption="alerts" />
              <ul className="dlegend">
                {levelCounts.map((p) => <li key={p.label}><i style={{ background: p.color }} />{p.label}<b>{p.value}</b></li>)}
              </ul>
            </div>
            <p className="muted small">Levels are back-test counts, not probabilities. See Results.</p>
          </div>
        </div>
      </div>
    </section>
  )
}
