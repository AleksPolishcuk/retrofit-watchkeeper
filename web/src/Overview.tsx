import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import { LEVELS, attention, headline, levelCounts, levelOf, pumpRows } from './cases'
import Icon from './icons'
import LiveStrip from './LiveStrip'
import { HEALTH_LABEL, incidentsOf, titleOf } from './plain'
import PumpArt from './PumpArt'
import type { Review } from './reviews'
import { STAGE_LABEL, when } from './stage'
import type { Alert, Asset, DataHealth, Series } from './types'
import { Donut, Spark } from './viz'

const PREFERRED = ['discharge_pressure_kpa', 'motor_current_a', 'motor_power_kw', 'fluid_temp_c']
const CHANNEL_NAME: Record<string, string> = { discharge_pressure_kpa: 'Discharge pressure', motor_current_a: 'Motor current', motor_power_kw: 'Motor power', fluid_temp_c: 'Fluid temperature' }

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
}

export default function Overview({ assets, alerts, reviews }: Props) {
  const cases = useMemo(() => incidentsOf(alerts), [alerts])
  const h = headline(cases, reviews)
  const counts = levelCounts(cases, reviews)
  const rows = pumpRows(assets.map((a) => a.asset_id), cases, reviews)
  const first = attention(cases, reviews, 4)
  const visual = useVisuals(assets)
  const urgent = h.urgent > 0
  const link = (id: string | null) => (id ? `#/alerts/${encodeURIComponent(id)}` : '#/alerts')
  const pumpsWithCases = rows.filter((r) => r.open > 0).length

  return (
    <div className="overview">
      <section className={`hero ${urgent ? 'urgent' : 'calm'}`} aria-labelledby="hero-title">
        <div className="herocopy">
          {alerts.length > 0 && (
            <span className={`heroicon ${urgent ? 'warn' : 'ok'}`} aria-hidden="true"><Icon name={urgent ? 'alert' : 'check'} /></span>
          )}
          <div className="herotext">
          <p className="heroeyebrow"><i aria-hidden="true" />Pump fleet · recorded simulation, replayed</p>
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
          <a className="btn primary herocta" href={link(h.topId)}>{urgent ? 'Review the first case' : 'Open the alerts'} <Icon name="next" /></a>
          </div>
        </div>
        <PumpArt className="heroart" />
      </section>

      <LiveStrip />

      <section className="kpirow" aria-label="Key figures">
        <article className="kpi">
          <span className="kicon" aria-hidden="true"><Icon name="bell" /></span>
          <div className="kbody">
            <p className="kl">Open cases</p>
            <p className="kv">{h.open}<span>of {h.total}</span></p>
            <p className="kn">Across {pumpsWithCases} {plural(pumpsWithCases, 'pump', 'pumps')}</p>
          </div>
        </article>
        <article className="kpi">
          <span className="kicon red" aria-hidden="true"><Icon name="alert" /></span>
          <div className="kbody">
            <p className="kl">Need a look first</p>
            <p className={`kv ${urgent ? 'hot' : ''}`}>{h.urgent}</p>
            <p className="kn">Likely or Very likely</p>
          </div>
        </article>
        <article className="kpi">
          <span className="kicon teal" aria-hidden="true"><Icon name="pump" /></span>
          <div className="kbody">
            <p className="kl">Monitored pumps</p>
            <p className="kv">{assets.length}</p>
            <p className="kn">{assets.filter((a) => a.telemetry_served).length} with telemetry shown</p>
          </div>
        </article>
        <article className="kpi">
          <span className="kicon green" aria-hidden="true"><Icon name="check" /></span>
          <div className="kbody">
            <p className="kl">Reviewed by people</p>
            <p className="kv">{h.reviewed}<span>of {h.total}</span></p>
            <p className="kn">Kept in this browser</p>
          </div>
        </article>
      </section>

      <div className="dash">
        <section className="panel" aria-labelledby="pumps-title">
          <div className="phead">
            <div>
              <h2 id="pumps-title">Pump overview</h2>
              <p className="psub">Choose a pump to see its open cases.</p>
            </div>
          </div>
          <div className="tablewrap flat">
            <table className="pumptable">
              <thead><tr><th>Pump</th><th>Condition</th><th>Trend · recorded week</th><th><span className="sr">Open</span></th></tr></thead>
              <tbody>
                {rows.map((r) => {
                  const a = assets.find((x) => x.asset_id === r.asset_id)
                  const v = visual(r.asset_id)
                  const marks = cases.filter((c) => c.head.asset_id === r.asset_id).map((c) => ({ at: c.head.alert_time_utc, level: levelOf(c.head.stage) }))
                  const dataNote = v?.health && v.health.status !== 'OK' ? <span className={`hchip h-${v.health.status}`}>{HEALTH_LABEL[v.health.status]}</span> : null
                  return (
                    <tr key={r.asset_id}>
                      <td data-label="Pump">
                        <a className="pumplink" href={`#/alerts/${r.asset_id}`}>
                          <span className="ptile" aria-hidden="true"><Icon name="pump" /></span>
                          <span className="ptext"><b className="mono">{r.asset_id}</b><span>{a?.system}</span></span>
                        </a>
                      </td>
                      <td data-label="Condition">
                        {r.worst ? <span className={`cond s-${r.worst}`}>{STAGE_LABEL[r.worst]}</span> : <span className="cond">No open cases</span>}
                        <span className="condsub">{r.open} open {plural(r.open, 'case', 'cases')} {dataNote}</span>
                      </td>
                      <td data-label="Trend" className="sparkcell">
                        {!a?.telemetry_served
                          ? <span className="muted small">Test pump: telemetry hidden</span>
                          : v?.series
                            ? <Spark t={v.series.t} v={v.series.v} marks={marks} label={`${CHANNEL_NAME[v.channel ?? ''] ?? 'Signal'} over the recorded week, ${marks.length} cases marked`} />
                            : <span className="muted small">{v ? 'No signal to show' : 'Loading…'}</span>}
                        {a?.telemetry_served && v?.channel && v.series ? <span className="xs">{CHANNEL_NAME[v.channel]}</span> : null}
                      </td>
                      <td><a className="go" href={`#/alerts/${r.asset_id}`} aria-label={`Open the cases of ${r.asset_id}`}><Icon name="next" /></a></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="muted small foot">A pump with no open cases is not called healthy: quiet can also mean the data are not good enough to judge, which the data check on each case says.</p>
        </section>

        <div className="dcol">
          <section className="panel" aria-labelledby="att-title">
            <div className="phead">
              <div>
                <h2 id="att-title">Active alerts</h2>
                <p className="psub">Highest priority first</p>
              </div>
              <a className="more" href="#/alerts">View all <Icon name="next" /></a>
            </div>
            {first.length === 0 ? (
              <p className="muted">{alerts.length === 0 ? 'No alerts loaded.' : 'No open cases. Everything has been reviewed or closed.'}</p>
            ) : (
              <ul className="attlist">
                {first.map((c) => (
                  <li key={c.id}>
                    <a href={link(c.id)} className="att">
                      <span className="atxt">
                        <b>{titleOf(c.head)}</b>
                        <span className="muted small"><span className="mono">{c.head.asset_id}</span> · {when(c.head.alert_time_utc)}</span>
                      </span>
                      <span className={`stagechip s-${levelOf(c.head.stage)}`}>{STAGE_LABEL[levelOf(c.head.stage)]}</span>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel" aria-labelledby="mix-title">
            <div className="phead">
              <div>
                <h2 id="mix-title">Fleet condition</h2>
                <p className="psub">Open cases by priority</p>
              </div>
            </div>
            <div className="mix">
              <Donut counts={counts} size={150} />
              <ul className="legend2">
                {LEVELS.map((l) => <li key={l}><i className={`dot2 ${l}`} aria-hidden="true" />{STAGE_LABEL[l]}<b>{counts[l]}</b></li>)}
              </ul>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
