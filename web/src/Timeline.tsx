import { useMemo } from 'react'
import type { Alert, Series, Timeline } from './types'

const W = 1000
const PAD = 10
const SIG = { top: 14, bottom: 138 }
const EV = { top: 160, bottom: 192 }
const AL = { top: 214, bottom: 248 }
const AXIS_Y = 268
const H = 286

const classColor = (c: string) => (c === 'SENSOR' ? 'var(--sensor)' : 'var(--machine)')

interface Props {
  tl: Timeline
  series: Series | null
  seriesNote: string | null
  channel: string
  alerts: Alert[]
  selectedId: string | null
  onSelect: (id: string) => void
  cursor?: number | null
}

export default function TimelineChart({ tl, series, seriesNote, channel, alerts, selectedId, onSelect, cursor = null }: Props) {
  const t0 = Date.parse(tl.window_start_utc)
  const t1 = Date.parse(tl.window_end_utc)
  const x = (iso: string | number) => {
    const ms = typeof iso === 'number' ? iso : Date.parse(iso)
    return PAD + Math.min(1, Math.max(0, (ms - t0) / (t1 - t0))) * (W - 2 * PAD)
  }

  const path = useMemo(() => {
    if (!series || series.v.length < 2) return null
    const lo = Math.min(...series.v)
    const hi = Math.max(...series.v)
    const span = hi - lo || 1
    const y = (v: number) => SIG.bottom - 6 - ((v - lo) / span) * (SIG.bottom - SIG.top - 14)
    const d = series.t.map((t, i) => `${i ? 'L' : 'M'}${x(t).toFixed(1)} ${y(series.v[i]).toFixed(1)}`).join('')
    return { d, lo, hi }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, t0, t1])

  const days: number[] = []
  for (let t = Math.ceil(t0 / 86400000) * 86400000; t < t1; t += 86400000) days.push(t)
  const dayLabel = (t: number) => new Date(t).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })

  return (
    <figure className="timeline" aria-label={`Timeline for ${tl.asset_id}`}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img">
        {cursor !== null && (
          <defs><clipPath id="reveal"><rect x={0} y={0} width={x(cursor)} height={H} /></clipPath></defs>
        )}
        {/* lane labels */}
        <text className="lane" x={PAD} y={SIG.top + 8}>{channel.replace(/_/g, ' ')}</text>
        <text className="lane" x={PAD} y={EV.top - 6}>labelled events (training and validation pumps only)</text>
        <text className="lane" x={PAD} y={AL.top - 6}>Watchkeeper alerts</text>

        {/* day grid */}
        {days.map((t) => (
          <g key={t}>
            <line className="grid" x1={x(t)} x2={x(t)} y1={SIG.top} y2={AXIS_Y - 4} />
            <text className="tick" x={x(t) + 4} y={AXIS_Y + 12}>{dayLabel(t)}</text>
          </g>
        ))}

        {/* benign windows */}
        {tl.benign.map((b, i) => (
          <rect key={i} className="benign" x={x(b.start_utc)} y={SIG.top} width={Math.max(1.5, x(b.end_utc) - x(b.start_utc))} height={SIG.bottom - SIG.top}>
            <title>{b.benign_type.replace(/_/g, ' ').toLowerCase()} (normal but unusual)</title>
          </rect>
        ))}

        {/* signal */}
        {path ? (
          <>
            <path className="signal" d={path.d} clipPath={cursor !== null ? 'url(#reveal)' : undefined} />
            <text className="tick" x={W - PAD} y={SIG.top + 8} textAnchor="end">{path.hi.toFixed(1)} max</text>
            <text className="tick" x={W - PAD} y={SIG.bottom - 2} textAnchor="end">{path.lo.toFixed(1)} min</text>
          </>
        ) : (
          <text className="note" x={W / 2} y={(SIG.top + SIG.bottom) / 2} textAnchor="middle">{seriesNote ?? 'No signal'}</text>
        )}

        {/* labelled events */}
        {tl.events.map((e) => {
          const x0 = x(e.onset_utc)
          const x1 = e.end_utc ? x(e.end_utc) : x(t1)
          const w = Math.max(3, x1 - x0)
          return (
            <g key={e.event_id} opacity={e.observable ? 1 : 0.45}>
              <rect className="event" x={x0} y={EV.top} width={w} height={EV.bottom - EV.top} fill={classColor(e.event_class)}>
                <title>{`${e.fault_type} (${e.severity})${e.observable ? '' : ', not observable with this instrumentation'}`}</title>
              </rect>
              {w > 70 && <text className="eventlabel" x={x0 + 4} y={(EV.top + EV.bottom) / 2 + 4}>{e.fault_type.replace(/_/g, ' ').toLowerCase()}</text>}
              {e.action_deadline_utc && (
                <g>
                  <line className="deadline" x1={x(e.action_deadline_utc)} x2={x(e.action_deadline_utc)} y1={EV.top - 2} y2={EV.bottom + 2} />
                  <title>conventional limit reached here</title>
                </g>
              )}
            </g>
          )
        })}
        {!tl.labels_public && (
          <text className="note" x={W / 2} y={(EV.top + EV.bottom) / 2 + 4} textAnchor="middle">labels are held by the organizers for this pump</text>
        )}

        {/* alerts */}
        <line className="grid" x1={PAD} x2={W - PAD} y1={(AL.top + AL.bottom) / 2} y2={(AL.top + AL.bottom) / 2} />
        {alerts.map((a) => {
          const cx = x(a.alert_time_utc)
          const cy = (AL.top + AL.bottom) / 2
          const sel = a.alert_id === selectedId
          const unknown = a.fault_type === 'UNKNOWN'
          return (
            <g key={a.alert_id} className="marker" tabIndex={0} role="button" aria-label={`${a.fault_type} at ${a.alert_time_utc}`}
               onClick={() => onSelect(a.alert_id)} onKeyDown={(ev) => (ev.key === 'Enter' || ev.key === ' ') && onSelect(a.alert_id)}>
              {sel && <circle cx={cx} cy={cy} r={13} className="ring" />}
              <circle cx={cx} cy={cy} r={7} fill={unknown ? 'var(--panel)' : classColor(a.event_class)} stroke={classColor(a.event_class)} strokeWidth={2.5} opacity={0.35 + 0.65 * a.confidence} />
              <title>{`${a.fault_type.replace(/_/g, ' ').toLowerCase()}, confidence ${(a.confidence * 100).toFixed(0)}%`}</title>
            </g>
          )
        })}
        <line className="axis" x1={PAD} x2={W - PAD} y1={AXIS_Y - 4} y2={AXIS_Y - 4} />
        {cursor !== null && <line className="cursor" x1={x(cursor)} x2={x(cursor)} y1={SIG.top} y2={AXIS_Y - 4} />}
      </svg>
      <figcaption className="legend">
        <span><i style={{ background: 'var(--machine)' }} /> machine</span>
        <span><i style={{ background: 'var(--sensor)' }} /> instrument</span>
        <span><i className="hollow" /> unknown cause</span>
        <span><i className="dash" /> conventional limit (existing alarm would fire)</span>
        <span><i className="shade" /> normal but unusual period</span>
      </figcaption>
    </figure>
  )
}
