import { useEffect, useState } from 'react'
import { api } from './api'
import { titleOf } from './plain'
import { STAGE_LABEL, when } from './stage'
import type { LiveItem, LiveState } from './types'

const HEALTH_LABEL: Record<string, string> = { OK: 'Data OK', BASELINE_LEARNING: 'Still learning', DEGRADED: 'Data degraded', INSUFFICIENT_DATA: 'Not enough data', NO_DATA: 'No data' }

/** Shown only while a live replay has been run (make live-demo). Polls the read-only API; the replay runner is a separate process. */
export default function LiveStrip() {
  const [state, setState] = useState<LiveState | null>(null)

  useEffect(() => {
    let alive = true
    let timer: number | undefined
    const tick = async () => {
      let next: LiveState | null = null
      try {
        const list: LiveItem[] = await api.live()
        const item = [...list].sort((a, b) => (b.updated_wall_utc ?? '').localeCompare(a.updated_wall_utc ?? ''))[0]
        if (item) next = await api.liveOne(item.asset_id)
      } catch {
        next = null
      }
      if (!alive) return
      setState(next)
      timer = window.setTimeout(tick, next?.status === 'running' ? 2500 : 10000)
    }
    tick()
    return () => {
      alive = false
      if (timer) window.clearTimeout(timer)
    }
  }, [])

  if (!state) return null
  const h = state.health
  const running = state.status === 'running'
  return (
    <section className="card live" aria-label="Live replay">
      <div className="livehead">
        <span className={`pulse ${running ? 'on' : ''}`} aria-hidden="true" />
        <h2>{running ? 'Live replay' : 'Live replay finished'}</h2>
        <span className="mono">{state.asset_id}</span>
        <span className="muted">as of <span className="mono">{state.as_of_utc ? when(state.as_of_utc) : 'no data yet'}</span></span>
        {h.status && <span className={`hchip h-${h.status}`}>{HEALTH_LABEL[h.status]}</span>}
      </div>
      <p className="muted livenote">
        Telemetry messages arrive one per second, are turned into one-minute readings and checked by the same detector as the recorded pumps below. Nothing is sent to the machine.
        {' '}{state.minutes} minutes received. The detector is re-run every {state.every_minutes} minutes and takes about {Math.round(state.latency.p50_ms)} ms per run on one CPU core.
      </p>
      {h.reasons && h.reasons.length > 0 && h.status !== 'OK' && (
        <ul className="livereasons">{h.reasons.slice(0, 3).map((r) => <li key={r}>{r}</li>)}</ul>
      )}
      {state.alerts.length === 0 ? (
        <p className="liveempty">No alert so far. Quiet is not proof of health: the data label next to the pump says whether the data are good enough to judge.</p>
      ) : (
        <ul className="livealerts">
          {state.alerts.slice(-4).reverse().map((a) => {
            const log = state.alert_log[a.alert_id]
            return (
              <li key={a.alert_id}>
                <span className={`stagechip s-${a.stage ?? 'watch'}`}>{STAGE_LABEL[a.stage ?? 'watch']}</span>
                <b>{titleOf(a)}</b>
                <span className="muted">raised <span className="mono">{when(a.alert_time_utc)}</span>
                  {log ? <>, shown {log.published_minutes_after_alert_time <= 0.5 ? 'as soon as the minute closed' : `${Math.round(log.published_minutes_after_alert_time)} min later`}</> : null}</span>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
