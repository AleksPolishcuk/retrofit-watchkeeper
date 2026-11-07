import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import { LEVELS, attention, headline, levelCounts, levelOf, pumpRows } from './cases'
import type { Level } from './cases'
import Icon from './icons'
import LiveStrip from './LiveStrip'
import { HEALTH_LABEL, TIER_SHORT, incidentsOf, titleOf } from './plain'
import type { Review } from './reviews'
import { STAGE_LABEL, when } from './stage'
import type { Asset, Alert, DataHealth, Results, ReportSet, Series } from './types'
import { Donut, Spark } from './viz'

const PREFERRED = ['discharge_pressure_kpa', 'motor_current_a', 'motor_power_kw', 'fluid_temp_c']
const CHANNEL_NAME: Record<string, string> = { discharge_pressure_kpa: 'discharge pressure', motor_current_a: 'motor current', motor_power_kw: 'motor power', fluid_temp_c: 'fluid temperature' }

interface Visual {
  series: Series | null
  health: DataHealth | null
  channel: string | null
}
const loaders = new Map<string, Promise<Visual>>()
const done = new Map<string, Visual>()

/** The recorded week of one channel and the data check for each public pump. Loaded once per page load; the test pumps have no telemetry to show. */
function load(a: Asset): Promise<Visual> {
  let p = loaders.get(a.asset_id)
  if (!p) {
    const channel = PREFERRED.find((c) => a.channels_available.includes(c)) ?? null
    p = Promise.allSettled([channel ? api.series(a.asset_id, channel, 120) : Promise.reject(new Error('no channel')), api.dataHealthNow(a.asset_id)]).then(([s, h]) => {
      const v: Visual = { series: s.status === 'fulfilled' ? s.value : null, health: h.status === 'fulfilled' ? h.value : null, channel }
      done.set(a.asset_id, v)
      return v
    })
    loaders.set(a.asset_id, p)
  }
  return p
}

function useVisuals(assets: Asset[]) {
  const [, bump] = useState(0)
  useEffect(() => {
    let alive = true
    for (const a of assets.filter((x) => x.telemetry_served)) load(a).then(() => alive && bump((n) => n + 1))
    return () => { alive = false }
  }, [assets])
  return (id: string) => done.get(id)
}

const plural = (n: number, one: string, many: string) => (n === 1 ? one : many)

interface Props {
  assets: Asset[]
  alerts: Alert[]
  reviews: Record<string, Review>
  results: Results | null
}

export default function Overview({ assets, alerts, reviews, results }: Props) {
  const cases = useMemo(() => incidentsOf(alerts), [alerts])
  const h = headline(cases, reviews)
  const counts = levelCounts(cases, reviews)
  const rows = pumpRows(assets.map((a) => a.asset_id), cases, reviews)
  const first = attention(cases, reviews, 5)
  const visual = useVisuals(assets)
  const hold = results?.report ? (Object.entries(results.report).find(([k]) => k.startsWith('hold fleets'))?.[1] as ReportSet | undefined) : undefined
  const urgent = h.urgent > 0
  const link = (id: string | null) => (id ? `#/alerts/${encodeURIComponent(id)}` : '#/alerts')

  return (
    <div className="overview">
      <section className={`hero ${urgent ? 'urgent' : 'calm'}`} aria-labelledby="hero-title">
        <svg className="waves" viewBox="0 0 600 200" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">
          <path d="M0 150c60-30 110 30 170 0s110-30 170 0 110 30 170 0 70-20 90-10" />
          <path d="M0 120c60-30 110 30 170 0s110-30 170 0 110 30 170 0 70-20 90-10" />
          <path d="M0 90c60-30 110 30 170 0s110-30 170 0 110 30 170 0 70-20 90-10" />
        </svg>
        <div className="herobody">
          <span className="heroicon" aria-hidden="true"><Icon name={urgent ? 'alert' : 'check'} /></span>
          <div>
            <p className="heroeyebrow">Recorded simulated pumps, replayed as if live</p>
            <h1 id="hero-title">
              {alerts.length === 0 ? 'No alerts to show yet' : urgent ? `${h.urgent} ${plural(h.urgent, 'case needs', 'cases need')} a look first` : 'Nothing urgent right now'}
            </h1>
            <p className="herosub">
              {alerts.length === 0
                ? 'Start the API, or pull the committed alert files, and reload.'
                : urgent
                  ? `${plural(h.pumpsUrgent, '1 pump has', `${h.pumpsUrgent} pumps have`)} an open case at Likely or Very likely priority. ${h.open} cases are open in total.`
                  : `No open case at Likely or Very likely priority. ${h.open} lower-priority ${plural(h.open, 'case is', 'cases are')} still open.`}
            </p>
          </div>
        </div>
        <a className="btn herocta" href={link(h.topId)}>{urgent ? 'Review the first case' : 'Open the alerts'} <Icon name="next" /></a>
      </section>

      <LiveStrip />

      <section className="kpis4" aria-label="Key figures">
        <article className="kpi">
          <p className="kl">Open cases</p>
          <p className="kv">{h.open}<span> of {h.total}</span></p>
          <div className="stack" role="img" aria-label={LEVELS.map((l) => `${counts[l]} ${STAGE_LABEL[l]}`).join(', ')}>
            {LEVELS.map((l) => counts[l] > 0 && <i key={l} className={`s-${l}`} style={{ flex: counts[l] }} />)}
          </div>
        </article>
        <article className="kpi">
          <p className="kl">Need a look first</p>
          <p className={`kv ${urgent ? 'hot' : ''}`}>{h.urgent}</p>
          <p className="kn">Likely or Very likely, still open</p>
        </article>
        <article className="kpi">
          <p className="kl">Reviewed by people</p>
          <p className="kv">{h.reviewed}<span> of {h.total}</span></p>
          <p className="kn">Kept in this browser</p>
        </article>
        <a className="kpi link" href="#/proof">
          <p className="kl">Back-test score</p>
          <p className="kv">{hold ? hold.wk.composite.toFixed(1) : '—'}</p>
          <p className="kn">{hold?.b1 ? `organizers' baseline ${hold.b1.composite.toFixed(1)}` : 'see Proof'} · simulated pumps</p>
        </a>
      </section>

      <div className="split">
        <section className="panel" aria-labelledby="att-title">
          <div className="phead">
            <h2 id="att-title">Needs a look first</h2>
            <a className="more" href="#/alerts">All {h.open} open cases <Icon name="next" /></a>
          </div>
          {first.length === 0 ? (
            <p className="muted">{alerts.length === 0 ? 'No alerts loaded.' : 'No open cases. Everything has been reviewed or closed.'}</p>
          ) : (
            <ul className="attlist">
              {first.map((c) => (
                <li key={c.id}>
                  <a href={link(c.id)} className={`att s-${levelOf(c.head.stage)}`}>
                    <span className={`ticon ${c.head.event_class === 'SENSOR' ? 'sensor' : 'machine'}`} aria-hidden="true"><Icon name={c.head.event_class === 'SENSOR' ? 'sensor' : 'wrench'} /></span>
                    <span className="atxt">
                      <b>{titleOf(c.head)}</b>
                      <span className="muted small"><span className="mono">{c.head.asset_id}</span> · {when(c.head.alert_time_utc)}{c.members.length > 1 ? ` · +${c.members.length - 1} related` : ''}</span>
                    </span>
                    <span className={`stagechip s-${levelOf(c.head.stage)}`}>{STAGE_LABEL[levelOf(c.head.stage)]}</span>
                    <Icon name="next" />
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-labelledby="mix-title">
          <div className="phead"><h2 id="mix-title">Where the open cases are</h2></div>
          <div className="mix">
            <Donut counts={counts} />
            <ul className="legend2">
              {LEVELS.map((l: Level) => <li key={l}><i className={`dot2 ${l}`} aria-hidden="true" />{STAGE_LABEL[l]}<b>{counts[l]}</b></li>)}
            </ul>
          </div>
        </section>
      </div>

      <section className="panel" aria-labelledby="pumps-title">
        <div className="phead">
          <h2 id="pumps-title">Pumps</h2>
          <span className="muted small">Open cases per pump and the recorded week, with a tick at each case</span>
        </div>
        <div className="tablewrap flat">
          <table className="pumptable">
            <thead><tr><th>Pump</th><th>Highest priority</th><th>Open</th><th>Recorded week</th><th>Data check</th></tr></thead>
            <tbody>
              {rows.map((r) => {
                const a = assets.find((x) => x.asset_id === r.asset_id)
                const v = visual(r.asset_id)
                const marks = cases.filter((c) => c.head.asset_id === r.asset_id).map((c) => ({ at: c.head.alert_time_utc, level: levelOf(c.head.stage) }))
                return (
                  <tr key={r.asset_id}>
                    <td data-label="Pump">
                      <a className="pumplink" href={`#/alerts/${r.asset_id}`}>
                        <span className="mono">{r.asset_id}</span>
                        {a && <span className={`tier t${TIER_SHORT[a.instrumentation_tier]?.[1]}`}>{TIER_SHORT[a.instrumentation_tier]}</span>}
                        <span className="sys">{a?.system}</span>
                      </a>
                    </td>
                    <td data-label="Highest priority">{r.worst ? <span className={`stagechip s-${r.worst}`}>{STAGE_LABEL[r.worst]}</span> : <span className="muted">No open cases</span>}</td>
                    <td data-label="Open" className="num">{r.open}</td>
                    <td data-label="Recorded week" className="sparkcell">
                      {!a?.telemetry_served
                        ? <span className="muted small">Test pump: telemetry hidden</span>
                        : v?.series
                          ? <Spark t={v.series.t} v={v.series.v} marks={marks} label={`${CHANNEL_NAME[v.channel ?? ''] ?? 'signal'} over the recorded week, ${marks.length} cases marked`} />
                          : <span className="muted small">{v ? 'No signal to show' : 'Loading…'}</span>}
                      {a?.telemetry_served && v?.channel && v.series ? <span className="muted xs">{CHANNEL_NAME[v.channel]}</span> : null}
                    </td>
                    <td data-label="Data check">
                      {!a?.telemetry_served ? <span className="muted small">not computed</span> : v?.health ? <span className={`hchip h-${v.health.status}`}>{HEALTH_LABEL[v.health.status]}</span> : <span className="muted small">{v ? '—' : '…'}</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="muted small foot">A pump with no open cases is not called healthy: quiet can also mean the data are not good enough to judge, which is what the data check says.</p>
      </section>
    </div>
  )
}
