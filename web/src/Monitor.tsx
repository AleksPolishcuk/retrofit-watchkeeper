import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { SignalChart } from './charts'
import type { Decision } from './decisions'
import Icon from './icons'
import { CHANNEL, fmtNum, howFar, incidentsOf, median, nameOf, titleOf } from './plain'
import { STAGE_LABEL, STAGES, stageRank, when } from './stage'
import TimelineChart from './Timeline'
import WhatIf from './WhatIf'
import type { Alert, Asset, Results, Series, Stage, Timeline } from './types'

const HOUR = 3600_000
const DEFAULT_SIGNALS = ['vibration_rms_mm_s', 'discharge_pressure_kpa', 'motor_current_a', 'suction_pressure_kpa', 'bearing_temp_c']
const STAGE_WORDS: Record<Stage, string> = {
  watch: 'Something moved. Keep an eye on it.',
  possible: 'Worth a look when convenient.',
  likely: 'Investigation recommended.',
  very_likely: 'Investigate soon.',
}
const TIER_NOTE: Record<string, string> = {
  T0_LEGACY: 'This pump has only legacy sensors, so fewer causes can be told apart.',
  T1_RETROFIT: 'This pump has retrofit sensors; vibration and bearing temperature arrive every few minutes.',
  T2_FULL: 'This pump is fully instrumented.',
}

interface Props {
  assets: Asset[]
  alerts: Alert[]
  results: Results | null
  decisions: Record<string, Decision>
  decide: (id: string, d: Decision | undefined) => void
}

function Meter({ stage }: { stage: Stage }) {
  const at = STAGES.indexOf(stage)
  return (
    <div className="meter" role="img" aria-label={`Level ${STAGE_LABEL[stage]} of four: Watch, Possible, Likely, Very likely`}>
      {STAGES.map((s, i) => (
        <div key={s} className={`seg s-${s} ${i <= at ? 'on' : ''} ${i === at ? 'cur' : ''}`}>
          <i />
          <span>{STAGE_LABEL[s]}</span>
        </div>
      ))}
    </div>
  )
}

export default function Monitor({ assets, alerts, results, decisions, decide }: Props) {
  const [pumpId, setPumpId] = useState('all')
  const [showAll, setShowAll] = useState(false)
  const [levels, setLevels] = useState<Stage[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [sig, setSig] = useState<Record<string, Series | 'none'>>({})
  const [progress, setProgress] = useState(1)
  const [playing, setPlaying] = useState(false)
  const [tl, setTl] = useState<Timeline | null>(null)
  const [tlSeries, setTlSeries] = useState<Series | null>(null)
  const [techOpen, setTechOpen] = useState(false)
  const timer = useRef<number | null>(null)

  const allIncidents = useMemo(() => incidentsOf(pumpId === 'all' ? alerts : alerts.filter((a) => a.asset_id === pumpId)), [alerts, pumpId])
  const countBy = (s: Stage) => allIncidents.filter((i) => i.head.stage === s).length
  const incidents = useMemo(() => (levels.length === 0 ? allIncidents : allIncidents.filter((i) => i.head.stage && levels.includes(i.head.stage))), [allIncidents, levels])
  const toggleLevel = (s: Stage) => {
    setLevels((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]))
    setShowAll(false)
  }
  const narrow = typeof window !== 'undefined' && window.matchMedia('(max-width: 960px)').matches
  const shortList = narrow ? 3 : 7
  const list = showAll ? incidents : incidents.slice(0, shortList)
  // the first case a visitor sees should have data to look at: prefer a strong machine case on a pump whose telemetry is shown
  const served = (i: { head: Alert }) => assets.find((x) => x.asset_id === i.head.asset_id)?.telemetry_served
  const DEMO = ['SUCTION_STRAINER_CLOGGING', 'BEARING_WEAR', 'MISALIGNMENT', 'IMBALANCE', 'IMPELLER_WEAR']   // slow faults whose drift is visible in the data
  const fallback = incidents.find((i) => served(i) && DEMO.includes(i.head.fault_type) && i.head.evidence.length >= 2) ?? incidents.find((i) => served(i) && i.head.event_class === 'MACHINE' && stageRank(i.head.stage) >= 2) ?? incidents.find((i) => served(i)) ?? incidents[0] ?? null
  const inc = incidents.find((i) => i.id === selectedId) ?? fallback
  const a = inc?.head ?? null
  const asset = a ? assets.find((x) => x.asset_id === a.asset_id) ?? null : null

  useEffect(() => {
    setProgress(1)
    setPlaying(false)
    setTechOpen(false)
    setTl(null)
    setTlSeries(null)
  }, [a?.alert_id])

  const alertMs = a ? Date.parse(a.alert_time_utc) : 0
  const t0 = asset ? Date.parse(asset.window_start_utc) : 0
  const t1 = asset ? Date.parse(asset.window_end_utc) : 0
  const fromMs = Math.max(t0, alertMs - 36 * HOUR)
  const toMs = Math.min(t1, alertMs + 12 * HOUR)

  const channels = useMemo(() => {
    if (!asset || !a) return []
    const own = a.evidence.map((e) => e.channel).filter((c) => CHANNEL[c])
    return [...own, ...DEFAULT_SIGNALS].filter((c, i, arr) => arr.indexOf(c) === i && asset.channels_available.includes(c)).slice(0, 3)
  }, [asset, a])

  useEffect(() => {
    if (!asset?.telemetry_served) return
    channels.forEach((c) => {
      const key = `${asset.asset_id}|${c}`
      if (sig[key] !== undefined) return
      api.series(asset.asset_id, c, 10).then((s) => setSig((m) => ({ ...m, [key]: s }))).catch(() => setSig((m) => ({ ...m, [key]: 'none' })))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channels.join(','), asset?.asset_id, asset?.telemetry_served])

  useEffect(() => {
    if (!playing) return
    timer.current = window.setInterval(() => {
      setProgress((p) => {
        const n = p + 0.014
        if (n >= 1) {
          setPlaying(false)
          return 1
        }
        return n
      })
    }, 45)
    return () => {
      if (timer.current !== null) window.clearInterval(timer.current)
    }
  }, [playing])

  const seriesOf = (c: string) => {
    const s = asset ? sig[`${asset.asset_id}|${c}`] : undefined
    return s && s !== 'none' ? s : null
  }

  // "now" against "typical earlier in the recorded week", for the evidence rows
  const compare = (c: string): { now: number; usual: number } | null => {
    const s = seriesOf(c)
    if (!s) return null
    const near: number[] = []
    const before: number[] = []
    s.t.forEach((t, i) => {
      const ms = Date.parse(t)
      if (Math.abs(ms - alertMs) <= HOUR / 2) near.push(s.v[i])
      else if (ms <= alertMs - 6 * HOUR) before.push(s.v[i])
    })
    const now = median(near)
    const usual = before.length >= 20 ? median(before) : null
    return now !== null && usual !== null ? { now, usual } : null
  }

  const openTech = (open: boolean) => {
    setTechOpen(open)
    if (!open || !a || !asset) return
    api.timeline(asset.asset_id).then(setTl).catch(() => undefined)
    const ch = channels[0] ?? 'discharge_pressure_kpa'
    if (asset.telemetry_served) api.series(asset.asset_id, ch, 60).then(setTlSeries).catch(() => undefined)
  }

  const play = () => {
    setProgress(0.01)
    setPlaying(true)
  }

  const decision = a ? decisions[a.alert_id] : undefined
  const detail = a?.stage && results?.stages ? results.stages.detail[a.stage] : null
  const pumpAlerts = a ? alerts.filter((x) => x.asset_id === a.asset_id) : []

  return (
    <div className="monitor">
      <p className="intro">
        Watchkeeper reads a pump's existing sensor data, notices when something moves away from that pump's own normal, shows the evidence and how sure it is,
        and tells the operator what to check. It never controls the machine.
      </p>

      <div className="mgrid">
        <aside className="card caselist" aria-label="Things to look at">
          <h2>Needs a look</h2>
          <label className="pick">
            <span className="sr">Pump</span>
            <select value={pumpId} onChange={(e) => { setPumpId(e.target.value); setSelectedId(null); setShowAll(false) }} aria-label="Pump">
              <option value="all">All {assets.length} pumps</option>
              {assets.map((x) => <option key={x.asset_id} value={x.asset_id}>{x.asset_id} · {x.system}</option>)}
            </select>
          </label>
          <div className="prio" role="group" aria-label="Filter by priority">
            <h3>Priority</h3>
            <div className="chips">
              <button className="fchip all" aria-pressed={levels.length === 0} onClick={() => { setLevels([]); setShowAll(false) }}>All <b>{allIncidents.length}</b></button>
              {[...STAGES].reverse().map((s) => (
                <button key={s} className={`fchip s-${s}`} aria-pressed={levels.includes(s)} onClick={() => toggleLevel(s)} title={STAGE_WORDS[s]}>
                  <i aria-hidden="true" />{STAGE_LABEL[s]} <b>{countBy(s)}</b>
                </button>
              ))}
            </div>
            <p className="hint">Priority is the evidence level. Pick one or more; none picked shows all.{levels.length > 0 ? ` Showing ${incidents.length} of ${allIncidents.length}.` : ''}</p>
          </div>
          <ul>
            {list.map((i) => (
              <li key={i.id}>
                <button className={`${i.id === inc?.id ? 'case on' : 'case'} s-${i.head.stage ?? 'watch'}`} onClick={() => { setSelectedId(i.id); if (narrow) window.setTimeout(() => document.getElementById('case-top')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50) }}>
                  <span className="ct">{titleOf(i.head)}</span>
                  <span className="cm">
                    <span className={`stagechip s-${i.head.stage ?? 'watch'}`}>{STAGE_LABEL[i.head.stage ?? 'watch']}</span>
                    <span className="mono">{i.head.asset_id} · {when(i.head.alert_time_utc)}</span>
                    {i.members.length > 1 && ` · +${i.members.length - 1} related`}
                    {decisions[i.head.alert_id] && <span className="done"> · <Icon name="check" /> reviewed</span>}
                  </span>
                </button>
              </li>
            ))}
            {list.length === 0 && <li className="muted small">{levels.length > 0 ? 'No cases at this priority. Pick another level or clear the filter.' : 'No alerts for this pump. Nothing stands out against its own normal.'}</li>}
          </ul>
          {incidents.length > shortList && <button className="btn sm" onClick={() => setShowAll((v) => !v)}>{showAll ? 'Show fewer' : `Show all ${incidents.length}`}</button>}
        </aside>

        {a && asset ? (
          <div className="flow">
            <div className="casehead" id="case-top">
              <div>
                <p className="eyebrow"><span className="mono">{a.asset_id}</span> · {asset.system}</p>
                <h1>{titleOf(a)}</h1>
                <p className="muted">Raised <span className="mono">{when(a.alert_time_utc)}</span>. <span className={`kind ${a.event_class === 'SENSOR' ? 'sensor' : 'machine'}`}><Icon name={a.event_class === 'SENSOR' ? 'sensor' : 'wrench'} /> {a.event_class === 'SENSOR' ? 'Instrument' : 'Machine'}</span>{inc && inc.members.length > 1 ? ` · ${inc.members.length} related alerts in this incident` : ''}</p>
              </div>
              {a.stage && <span className={`stagechip big s-${a.stage}`}>{STAGE_LABEL[a.stage]}</span>}
            </div>

            <section className="card step" aria-labelledby="s1">
              <h2 id="s1"><b>1</b> What does the pump data show?</h2>
              {asset.telemetry_served ? (
                <>
                  <div className="replaybar">
                    <button className="btn primary" onClick={play} disabled={playing}><Icon name="play" /> {playing ? 'Playing…' : 'Watch it happen'}</button>
                    <span className="muted small">The line is drawn as the data arrived. At the dashed line Watchkeeper raised the alert; nothing after that moment was used.</span>
                  </div>
                  <div className="sigs">
                    {channels.map((c, i) => <SignalChart key={c} series={seriesOf(c)} alertMs={alertMs} fromMs={fromMs} toMs={toMs} label={nameOf(c)} unit={CHANNEL[c]?.[1] ?? ''} progress={progress} height={i === 0 ? 190 : 140} />)}
                  </div>
                </>
              ) : (
                <p className="muted">Telemetry for the three test pumps is hidden by the organizers. The alert below is the one we submitted for this pump.</p>
              )}
            </section>

            <section className="card step" aria-labelledby="s2">
              <h2 id="s2"><b>2</b> What looks wrong?</h2>
              <ul className="found">
                {a.evidence.slice(0, 3).map((e, i) => {
                  const c = CHANNEL[e.channel] ? compare(e.channel) : null
                  return (
                    <li key={i}>
                      <b>{CHANNEL[e.channel] ? nameOf(e.channel) : e.channel === 'GATEWAY' ? 'Data connection' : e.channel === 'n/a' ? 'Pattern' : e.channel}</b>
                      {e.z !== null ? (
                        <span className={`dev ${e.z < 0 ? 'down' : 'up'}`}>{e.z < 0 ? '↓' : '↑'} {howFar(e.z)}</span>
                      ) : null}
                      <span className="muted">
                        {c ? <>Now about <span className="mono">{fmtNum(c.now)} {CHANNEL[e.channel]?.[1] ?? ''}</span>; earlier in the week typically <span className="mono">{fmtNum(c.usual)}</span>.</> : e.text}
                      </span>
                    </li>
                  )
                })}
                {a.evidence.length === 0 && <li className="muted">No single channel stands out; the pattern across channels did.</li>}
              </ul>
              <p><b>Machine or instrument?</b> {a.sensor_check ? (a.sensor_check.verdict === 'sensor' ? 'Probably the instrument. One reading moved while related readings did not, so check the sensor before repairing anything.' : a.sensor_check.verdict === 'machine' ? 'Probably the machine. Several related readings moved together.' : 'Unclear from this data.') : 'Not assessed.'}</p>
              {a.consequence && <p className="muted"><b style={{ color: 'var(--ink)' }}>What it may mean.</b> {a.consequence}</p>}
            </section>

            <section className="card step" aria-labelledby="s3">
              <h2 id="s3"><b>3</b> How sure are we?</h2>
              {a.stage && (
                <>
                  <Meter stage={a.stage} />
                  <p style={{ marginTop: 10 }}><b>{STAGE_LABEL[a.stage]}.</b> {STAGE_WORDS[a.stage]}</p>
                  <p className="muted">
                    This is a back-test count, not a probability. {detail
                      ? `In tests on simulated pumps, ${detail.at_a_real_event} of ${detail.alerts} alerts at this level pointed at a real problem and ${detail.right_type} named the right cause.`
                      : ''}
                  </p>
                </>
              )}
              <div className="limits2">
                <p><b>What we cannot see.</b> {(a.uncertainty?.missing_channels ?? []).length > 0 ? `Not measured on this pump: ${(a.uncertainty?.missing_channels ?? []).map(nameOf).join(', ')}.` : 'All key channels are measured on this pump.'} {a.tier ? TIER_NOTE[a.tier] : ''}</p>
                <p><b>Time to act.</b> Not estimated. Watchkeeper does not predict when a fault will become critical.</p>
                {a.alternatives && a.alternatives.length > 0 && <p><b>Also possible.</b> {a.alternatives.map((x) => titleOf({ ...a, fault_type: x.fault_type })).join('; ')}.</p>}
              </div>
            </section>

            <section className="card step action" aria-labelledby="s4">
              <h2 id="s4"><b>4</b> What should I do?</h2>
              <ol className="todo">
                <li><b>Check first</b><span>{a.check ?? a.recommended_action}</span></li>
                <li><b>Then</b><span>{a.recommended_action}</span></li>
              </ol>
              <div className="decide" role="group" aria-label="Your decision">
                <button className={decision === 'approved' ? 'btn on-ok' : 'btn primary'} onClick={() => decide(a.alert_id, decision === 'approved' ? undefined : 'approved')}>
                  <Icon name="check" /> {decision === 'approved' ? 'Inspection approved' : 'Approve inspection'}
                </button>
                <button className={decision === 'rejected' ? 'btn on-bad' : 'btn'} onClick={() => decide(a.alert_id, decision === 'rejected' ? undefined : 'rejected')}>
                  {decision === 'rejected' ? 'Marked as false alarm' : 'Mark as false alarm'}
                </button>
              </div>
              <p className="muted small">A person decides. The decision is kept in this browser only; Watchkeeper sends nothing to the machine, and existing alarms stay authoritative.{a.model_version ? ` Model ${a.model_version}.` : ''}</p>
              <details className="more">
                <summary>Try it in the simulator: what if we do this?</summary>
                <WhatIf key={a.alert_id} alert={a} />
              </details>
            </section>

            <details className="more card" onToggle={(e) => openTech((e.target as HTMLDetailsElement).open)}>
              <summary>Technical view: the whole week with the organizers' labels</summary>
              {techOpen && tl ? (
                <TimelineChart tl={tl} series={tlSeries} seriesNote={asset.telemetry_served ? 'Loading…' : 'Telemetry for the test pumps is hidden'} channel={channels[0] ?? 'discharge_pressure_kpa'} alerts={pumpAlerts} selectedId={a.alert_id} onSelect={(id) => { const t = allIncidents.find((i) => i.members.some((m) => m.alert_id === id)); if (t) { if (levels.length && t.head.stage && !levels.includes(t.head.stage)) setLevels([]); setSelectedId(t.id) } }} cursor={null} />
              ) : <p className="muted small">Loading…</p>}
            </details>
          </div>
        ) : (
          <div className="card"><p className="muted" style={{ margin: 0 }}>Nothing to show. Choose a case on the left or change the priority filter.</p></div>
        )}
      </div>
    </div>
  )
}
