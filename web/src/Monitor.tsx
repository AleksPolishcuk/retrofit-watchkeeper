import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { SignalChart } from './charts'
import Dropdown from './Dropdown'
import Icon from './icons'
import Lifecycle from './Lifecycle'
import LiveStrip from './LiveStrip'
import { CHANNEL, fmtNum, howFar, incidentsOf, median, nameOf, titleOf } from './plain'
import ReviewLog from './ReviewLog'
import { STATUS_LABEL } from './reviews'
import type { Action, Review } from './reviews'
import { STAGE_LABEL, STAGES, stageRank, when } from './stage'
import TimelineChart from './Timeline'
import WhatIf from './WhatIf'
import type { Incident } from './plain'
import type { Alert, Asset, DataHealth, Results, Series, Stage, Timeline } from './types'

const HOUR = 3600_000
const DEFAULT_SIGNALS = ['vibration_rms_mm_s', 'discharge_pressure_kpa', 'motor_current_a', 'suction_pressure_kpa', 'bearing_temp_c']
const HEALTH_LABEL: Record<string, string> = { OK: 'Data OK', BASELINE_LEARNING: 'Still learning', DEGRADED: 'Data degraded', INSUFFICIENT_DATA: 'Not enough data', NO_DATA: 'No data' }
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
  reviews: Record<string, Review>
  act: (inc: Incident, action: Action) => void
  clearReviews: () => void
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

export default function Monitor({ assets, alerts, results, reviews, act, clearReviews }: Props) {
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
  const [health, setHealth] = useState<DataHealth | 'hidden' | null>(null)
  const timer = useRef<number | null>(null)

  const allIncidents = useMemo(() => incidentsOf(pumpId === 'all' ? alerts : alerts.filter((a) => a.asset_id === pumpId)), [alerts, pumpId])
  const countBy = (s: Stage) => allIncidents.filter((i) => i.head.stage === s).length
  const casesByPump = useMemo(() => Object.fromEntries(assets.map((x) => [x.asset_id, incidentsOf(alerts.filter((a) => a.asset_id === x.asset_id)).length])), [assets, alerts])
  const tierOf = (x: Asset) => ({ T0_LEGACY: 'T0', T1_RETROFIT: 'T1', T2_FULL: 'T2' }[x.instrumentation_tier])
  const pumpAsset = assets.find((x) => x.asset_id === pumpId)
  const orderedLevels = [...STAGES].reverse().filter((s) => levels.includes(s))
  const incidents = useMemo(() => (levels.length === 0 ? allIncidents : allIncidents.filter((i) => i.head.stage && levels.includes(i.head.stage))), [allIncidents, levels])
  const narrow = typeof window !== 'undefined' && window.matchMedia('(max-width: 960px)').matches
  const shortList = narrow ? 3 : 7
  const list = showAll ? incidents : incidents.slice(0, shortList)
  // the first case a visitor sees should have data to look at: prefer a strong machine case on a pump whose telemetry is shown
  const served = (i: { head: Alert }) => assets.find((x) => x.asset_id === i.head.asset_id)?.telemetry_served
  const DEMO = ['SUCTION_STRAINER_CLOGGING', 'BEARING_WEAR', 'MISALIGNMENT', 'IMBALANCE', 'IMPELLER_WEAR']   // slow faults whose drift is visible in the data
  const fallback = incidents.find((i) => served(i) && DEMO.includes(i.head.fault_type) && i.head.evidence.length >= 2) ?? incidents.find((i) => served(i) && i.head.event_class === 'MACHINE' && stageRank(i.head.stage) >= 2) ?? incidents.find((i) => served(i)) ?? incidents[0] ?? null
  const inc = incidents.find((i) => i.id === selectedId) ?? fallback
  // opening a case starts its review log (first_seen); acting on it is always a person's click
  useEffect(() => {
    if (inc) act(inc, { type: 'view' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inc?.id])
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

  // was the pump's data good at the moment of the alert? (public pumps only)
  useEffect(() => {
    setHealth(null)
    if (!a || !asset) return
    if (!asset.telemetry_served) {
      setHealth('hidden')
      return
    }
    let live = true
    api.dataHealth(asset.asset_id, a.alert_time_utc).then((h) => live && setHealth(h)).catch(() => live && setHealth('hidden'))
    return () => { live = false }
  }, [a?.alert_id, asset?.asset_id, asset?.telemetry_served])
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

  const review = inc ? reviews[inc.id] : undefined
  const detail = a?.stage && results?.stages ? results.stages.detail[a.stage] : null
  const pumpAlerts = a ? alerts.filter((x) => x.asset_id === a.asset_id) : []

  return (
    <div className="monitor">
      <p className="intro">
        Watchkeeper reads a pump's existing sensor data, notices when something moves away from that pump's own normal, shows the evidence and how sure it is,
        and tells the operator what to check. It never controls the machine.
      </p>

      <LiveStrip />

      <div className="mgrid">
        <aside className="card caselist" aria-label="Things to look at">
          <h2>Needs a look</h2>
          <Dropdown
            label="Pump"
            minPanelWidth={360}
            selected={[pumpId]}
            onChange={([v]) => { setPumpId(v); setSelectedId(null); setShowAll(false) }}
            options={[
              { value: 'all', text: `All ${assets.length} pumps`, label: <span className="ddline"><b>All {assets.length} pumps</b></span>, count: alerts.length ? incidentsOf(alerts).length : 0 },
              ...assets.map((x) => ({
                value: x.asset_id,
                text: `${x.asset_id}, ${x.system}`,
                label: <span className="ddline"><span className="mono">{x.asset_id}</span><span className={`tier t${tierOf(x)?.[1]}`}>{tierOf(x)}</span><span className="sys">{x.system}</span></span>,
                count: casesByPump[x.asset_id] ?? 0,
              })),
            ]}
            summary={pumpAsset
              ? <span className="ddline"><span className="mono">{pumpAsset.asset_id}</span><span className="sys">{pumpAsset.system}</span></span>
              : <>All {assets.length} pumps</>}
          />
          <Dropdown
            label="Priority"
            multiple
            allLabel="All priorities"
            allCount={allIncidents.length}
            selected={levels}
            onChange={(v) => { setLevels(v as Stage[]); setShowAll(false) }}
            options={[...STAGES].reverse().map((s) => ({ value: s, dot: s, text: STAGE_LABEL[s], label: <span title={STAGE_WORDS[s]}>{STAGE_LABEL[s]}</span>, count: countBy(s) }))}
            summary={levels.length === 0
              ? <>All priorities <span className="cnt">{allIncidents.length}</span></>
              : <span className="ddline">{orderedLevels.map((s) => <i key={s} className={`dot2 ${s}`} aria-hidden="true" />)}{orderedLevels.map((s) => STAGE_LABEL[s]).join(', ')}<span className="cnt">{incidents.length}</span></span>}
          />
          <p className="hint">Priority is the evidence level; pick one or more. Numbers are cases.{levels.length > 0 ? ` Showing ${incidents.length} of ${allIncidents.length}.` : ''}</p>
          <ul>
            {list.map((i) => (
              <li key={i.id}>
                <button className={`${i.id === inc?.id ? 'case on' : 'case'} s-${i.head.stage ?? 'watch'}`} onClick={() => { setSelectedId(i.id); if (narrow) window.setTimeout(() => document.getElementById('case-top')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50) }}>
                  <span className="ct">{titleOf(i.head)}</span>
                  <span className="cm">
                    <span className={`stagechip s-${i.head.stage ?? 'watch'}`}>{STAGE_LABEL[i.head.stage ?? 'watch']}</span>
                    <span className="mono">{i.head.asset_id} · {when(i.head.alert_time_utc)}</span>
                    {i.members.length > 1 && ` · +${i.members.length - 1} related`}
                    {reviews[i.id] && reviews[i.id].status !== 'open' && <span className={`status-chip ${reviews[i.id].status}`}>{STATUS_LABEL[reviews[i.id].status]}</span>}
                  </span>
                </button>
              </li>
            ))}
            {list.length === 0 && <li className="muted small">{levels.length > 0 ? 'No cases at this priority. Pick another level or clear the filter.' : 'No alerts for this pump. Nothing stands out against its own normal.'}</li>}
          </ul>
          {incidents.length > shortList && <button className="btn sm" onClick={() => setShowAll((v) => !v)}>{showAll ? 'Show fewer' : `Show all ${incidents.length}`}</button>}
          <ReviewLog incidents={incidentsOf(alerts)} reviews={reviews} clear={clearReviews} />
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
                  <div className={`dcheck ${health && health !== 'hidden' ? 'h-' + health.status : ''}`} role="status">
                    <b>Data check at the time of the alert:</b>{' '}
                    {health === null && <span className="muted">checking…</span>}
                    {health === 'hidden' && <span className="muted">not available for this pump.</span>}
                    {health && health !== 'hidden' && (
                      <>
                        <span className={`hchip h-${health.status}`}>{HEALTH_LABEL[health.status]}</span>
                        <ul>
                          {health.reasons.slice(0, 4).map((r, i) => <li key={i}>{r}</li>)}
                          {health.checks.map((c, i) => <li key={`c${i}`}>{c.message}</li>)}
                        </ul>
                        {health.hygiene && (health.hygiene.duplicates_dropped > 0 || health.hygiene.out_of_order > 0) && (
                          <p className="muted small">Input clean-up: {health.hygiene.duplicates_dropped} repeated minute(s) dropped, {health.hygiene.conflicts} with conflicting values, {health.hygiene.out_of_order} out of order.</p>
                        )}
                      </>
                    )}
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
              {inc && <Lifecycle inc={inc} all={allIncidents} asset={asset} review={review} reviews={reviews} act={(x) => act(inc, x)} />}
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
