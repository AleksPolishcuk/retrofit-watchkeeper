import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { SignalChart } from './charts'
import Dropdown from './Dropdown'
import Icon from './icons'
import Lifecycle from './Lifecycle'
import { CHANNEL, HEALTH_LABEL, fmtNum, howFar, incidentsOf, median, nameOf, titleOf } from './plain'
import ReviewLog from './ReviewLog'
import { isClosed } from './cases'
import { useMedia } from './useMedia'
import { STATUS_LABEL } from './reviews'
import type { Action, Review } from './reviews'
import { STAGE_LABEL, STAGES, when } from './stage'
import TimelineChart from './Timeline'
import WhatIf from './WhatIf'
import type { Incident } from './plain'
import type { Alert, Asset, DataHealth, Results, Series, Stage, Timeline } from './types'

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
  focus: string | null // from the address: a pump id filters the list, a case id opens that case
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

export default function Monitor({ assets, alerts, focus, results, reviews, act, clearReviews }: Props) {
  const [pumpId, setPumpId] = useState('all')
  const [scope, setScope] = useState<'active' | 'resolved'>('active')
  const [mobileCase, setMobileCase] = useState(false)
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
  const scoped = useMemo(() => allIncidents.filter((i) => isClosed(i.id, reviews) === (scope === 'resolved')), [allIncidents, reviews, scope])
  const resolvedCount = allIncidents.filter((i) => isClosed(i.id, reviews)).length
  const activeCount = allIncidents.length - resolvedCount
  const countBy = (s: Stage) => scoped.filter((i) => (i.head.stage ?? 'watch') === s).length
  const casesByPump = useMemo(() => Object.fromEntries(assets.map((x) => [x.asset_id, incidentsOf(alerts.filter((a) => a.asset_id === x.asset_id)).filter((i) => !isClosed(i.id, reviews)).length])), [assets, alerts, reviews])
  const tierOf = (x: Asset) => ({ T0_LEGACY: 'T0', T1_RETROFIT: 'T1', T2_FULL: 'T2' }[x.instrumentation_tier])
  const pumpAsset = assets.find((x) => x.asset_id === pumpId)
  const orderedLevels = [...STAGES].reverse().filter((s) => levels.includes(s))
  const incidents = useMemo(() => (levels.length === 0 ? scoped : scoped.filter((i) => levels.includes(i.head.stage ?? 'watch'))), [scoped, levels])
  const narrow = useMedia('(max-width: 60em)')
  const shortList = narrow ? 3 : 7
  const list = showAll ? incidents : incidents.slice(0, shortList)
  // the case on show is the one picked, otherwise the first in the list (strongest priority first), so the list and the detail always agree
  const inc = incidents.find((i) => i.id === selectedId) ?? incidents[0] ?? null
  // opening a case starts its review log (first_seen); acting on it is always a person's click
  useEffect(() => {
    if (inc && (!narrow || mobileCase)) act(inc, { type: 'view' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inc?.id, narrow, mobileCase])

  // an address such as #/alerts/PUMP-04 or #/alerts/PUMP-04-INC02 (from the overview) selects a pump or opens a case
  useEffect(() => {
    if (!focus || assets.length === 0 || alerts.length === 0) return
    setLevels([])
    setShowAll(false)
    if (assets.some((x) => x.asset_id === focus)) {
      setPumpId(focus)
      setScope('active')
      setSelectedId(null)
      setMobileCase(false)
      return
    }
    const target = incidentsOf(alerts).find((i) => i.id === focus)
    if (target) {
      setPumpId('all')
      setScope(isClosed(target.id, reviews) ? 'resolved' : 'active')
      setSelectedId(target.id)
      setShowAll(true) // the opened case must be visible in the list
      setMobileCase(true)
      window.setTimeout(() => document.querySelector('.case.on')?.scrollIntoView({ block: 'nearest' }), 150)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus, assets.length, alerts.length])
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
      {!(narrow && mobileCase) && (
        <header className="pagehead">
          <h1>Alerts</h1>
          <p className="muted">Pick a case. You will see what the data show, how sure we are, and what to do first.</p>
        </header>
      )}

      <div className={`mgrid ${narrow ? (mobileCase ? 'show-case' : 'show-list') : ''}`}>
        <aside className="card caselist" aria-label="Things to look at">
          <div className="seg2" role="group" aria-label="Show open or resolved cases">
            <button aria-pressed={scope === 'active'} className={scope === 'active' ? 'on' : ''} onClick={() => { setScope('active'); setSelectedId(null); setShowAll(false) }}>Open <b>{activeCount}</b></button>
            <button aria-pressed={scope === 'resolved'} className={scope === 'resolved' ? 'on' : ''} onClick={() => { setScope('resolved'); setSelectedId(null); setShowAll(false) }}>Resolved <b>{resolvedCount}</b></button>
          </div>
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
            allCount={scoped.length}
            selected={levels}
            onChange={(v) => { setLevels(v as Stage[]); setShowAll(false) }}
            options={[...STAGES].reverse().map((s) => ({ value: s, dot: s, text: STAGE_LABEL[s], label: <span title={STAGE_WORDS[s]}>{STAGE_LABEL[s]}</span>, count: countBy(s) }))}
            summary={levels.length === 0
              ? <>All priorities <span className="cnt">{scoped.length}</span></>
              : <span className="ddline">{orderedLevels.map((s) => <i key={s} className={`dot2 ${s}`} aria-hidden="true" />)}{orderedLevels.map((s) => STAGE_LABEL[s]).join(', ')}<span className="cnt">{incidents.length}</span></span>}
          />
          <p className="hint">Numbers are cases.{levels.length > 0 ? ` Showing ${incidents.length} of ${scoped.length}.` : ''}</p>
          <details className="levelhelp">
            <summary>What do the priority levels mean?</summary>
            <ul>{[...STAGES].reverse().map((st) => <li key={st}><span className={`stagechip s-${st}`}>{STAGE_LABEL[st]}</span><span>{STAGE_WORDS[st]}</span></li>)}</ul>
          </details>
          <ul>
            {list.map((i) => (
              <li key={i.id}>
                <button aria-current={i.id === inc?.id && (!narrow || mobileCase) ? 'true' : undefined} className={`${i.id === inc?.id && (!narrow || mobileCase) ? 'case on' : 'case'} s-${i.head.stage ?? 'watch'}`} onClick={() => { setSelectedId(i.id); setMobileCase(true); if (narrow) window.scrollTo(0, 0) }}>
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
            {list.length === 0 && <li className="muted small">{levels.length > 0 ? 'No cases at this priority. Pick another level or clear the filter.' : scope === 'resolved' ? 'No resolved cases yet. A case moves here when you close it after an inspection.' : 'No open cases for this pump. Quiet is not proof of health: see the data check.'}</li>}
          </ul>
          {incidents.length > shortList && <button className="btn sm" onClick={() => setShowAll((v) => !v)}>{showAll ? 'Show fewer' : `Show all ${incidents.length}`}</button>}
          <ReviewLog incidents={incidentsOf(alerts)} reviews={reviews} clear={clearReviews} />
        </aside>

        {a && asset ? (
          <div className="flow">
            <div className="casehead" id="case-top">
              <div>
                {narrow && <button className="btn sm back" onClick={() => setMobileCase(false)}><Icon name="back" /> All alerts</button>}
                <p className="eyebrow"><span className="mono">{a.asset_id}</span> · {asset.system}</p>
                <h2 className="casetitle">{titleOf(a)}</h2>
                <p className="muted">Raised <span className="mono">{when(a.alert_time_utc)}</span>. <span className={`kind ${a.event_class === 'SENSOR' ? 'sensor' : 'machine'}`}><Icon name={a.event_class === 'SENSOR' ? 'sensor' : 'wrench'} /> {a.event_class === 'SENSOR' ? 'Instrument' : 'Machine'}</span>{inc && inc.members.length > 1 ? ` · ${inc.members.length} related alerts in this incident` : ''}</p>
              </div>
              {a.stage && <span className={`stagechip big s-${a.stage}`}>{STAGE_LABEL[a.stage]}</span>}
            </div>

            <section className="card dofirst" aria-label="Do this first">
              <p className="eyebrow">Do this first</p>
              <p className="what">{a.check ?? a.recommended_action}</p>
              <button className="btn" onClick={() => { const el = document.getElementById('decision'); el?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' }); el?.focus({ preventScroll: true }) }}>Go to the decision <Icon name="next" /></button>
            </section>

            <section className="card step" aria-labelledby="s1">
              <h3 id="s1"><b>1</b> What does the pump data show?</h3>
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
              <h3 id="s2"><b>2</b> What looks wrong?</h3>
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
              <h3 id="s3"><b>3</b> How sure are we?</h3>
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

            <section className="card step action" id="decision" tabIndex={-1} aria-labelledby="s4">
              <h3 id="s4"><b>4</b> What should I do?</h3>
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
