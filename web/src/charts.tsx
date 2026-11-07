import type { Series } from './types'

const hhmm = (ms: number) => new Date(ms).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })

interface Props {
  series: Series | null
  alertMs: number
  fromMs: number
  toMs: number
  label: string
  unit: string
  /** 0..1: how much of the time range has been drawn. Below 1 the chart is replaying the data as it arrived. */
  progress?: number
  height?: number
  note?: string
}

/** One channel around an alert. The dashed line is the moment the alert was raised; it only appears once the replay has reached it. */
export function SignalChart({ series, alertMs, fromMs, toMs, label, unit, progress = 1, height = 170, note }: Props) {
  const W = 640
  const H = height
  const L = 10
  const R = 10
  const T = 22
  const B = 24
  const pts: [number, number][] = []
  if (series) {
    series.t.forEach((t, i) => {
      const ms = Date.parse(t)
      if (ms >= fromMs && ms <= toMs) pts.push([ms, series.v[i]])
    })
  }
  if (pts.length < 2) {
    return (
      <div className="sig">
        <div className="sh">{label}</div>
        <p className="muted small" style={{ margin: '14px 0' }}>{series ? 'No data in this range.' : note ?? 'Loading…'}</p>
      </div>
    )
  }
  const lo = Math.min(...pts.map((p) => p[1]))
  const hi = Math.max(...pts.map((p) => p[1]))
  const span = hi - lo || 1
  const x = (ms: number) => L + ((ms - fromMs) / (toMs - fromMs)) * (W - L - R)
  const y = (v: number) => H - B - ((v - lo) / span) * (H - B - T)
  const cutMs = fromMs + progress * (toMs - fromMs)
  const shown = pts.filter(([ms]) => ms <= cutMs)
  const d = shown.map(([ms, v], i) => `${i ? 'L' : 'M'}${x(ms).toFixed(1)} ${y(v).toFixed(1)}`).join('')
  const ax = x(alertMs)
  const reached = cutMs >= alertMs
  const tagX = Math.min(Math.max(ax, L + 52), W - R - 52)
  return (
    <div className="sig">
      <div className="sh">{label}<span>{fmtRange(lo, hi)} {unit}</span></div>
      <svg className="sigsvg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${label} around the alert`}>
        {[0, 0.5, 1].map((f) => <line key={f} className="g" x1={L} x2={W - R} y1={T + f * (H - B - T)} y2={T + f * (H - B - T)} />)}
        {reached && <rect className="after" x={ax} y={T} width={Math.max(0, x(Math.min(cutMs, toMs)) - ax)} height={H - B - T} />}
        <path className="ln" d={d} />
        {shown.length > 0 && progress < 1 && <circle className="head" cx={x(shown[shown.length - 1][0])} cy={y(shown[shown.length - 1][1])} r={4.5} />}
        {reached && (
          <g>
            <line className="mk" x1={ax} x2={ax} y1={T - 2} y2={H - B} />
            <g className="tag"><rect x={tagX - 52} y={0} width={104} height={17} rx={8.5} /><text x={tagX} y={12.5} textAnchor="middle">Alert raised</text></g>
          </g>
        )}
        <text className="t" x={L} y={H - 7}>{hhmm(fromMs)}</text>
        <text className="t" x={W - R} y={H - 7} textAnchor="end">{hhmm(toMs)}</text>
      </svg>
    </div>
  )
}

const fmtRange = (lo: number, hi: number) => `${lo.toFixed(1)} to ${hi.toFixed(1)}`
