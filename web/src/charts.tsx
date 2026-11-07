import type { Series } from './types'

/** Small trend line for tables. `ticks` are 0..1 positions of alerts along the line. */
export function Sparkline({ values, ticks = [], w = 130, h = 34, empty }: { values: number[]; ticks?: number[]; w?: number; h?: number; empty?: string }) {
  if (values.length < 2) {
    return (
      <svg className="spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label={empty ?? 'no trend available'}>
        <line x1={0} x2={w} y1={h / 2} y2={h / 2} stroke="var(--line)" strokeDasharray="3 3" />
        {ticks.map((t, i) => <line key={i} className="tick" x1={2 + t * (w - 4)} x2={2 + t * (w - 4)} y1={4} y2={h - 4} />)}
        {empty && <text className="none" x={w / 2} y={h - 3} textAnchor="middle">{empty}</text>}
      </svg>
    )
  }
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const span = hi - lo || 1
  const x = (i: number) => 2 + (i / (values.length - 1)) * (w - 4)
  const y = (v: number) => h - 4 - ((v - lo) / span) * (h - 8)
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join('')
  return (
    <svg className="spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label="trend over the recorded week, alerts marked">
      {ticks.map((t, i) => <line key={i} className="tick" x1={2 + t * (w - 4)} x2={2 + t * (w - 4)} y1={2} y2={h - 2} />)}
      <path className="ln" d={d} />
    </svg>
  )
}

export interface Part {
  label: string
  value: number
  color: string
}

export function Donut({ parts, centre, caption }: { parts: Part[]; centre: string; caption: string }) {
  const total = parts.reduce((s, p) => s + p.value, 0) || 1
  const R = 52
  const C = 2 * Math.PI * R
  let acc = 0
  return (
    <svg className="donut" width={150} height={150} viewBox="0 0 150 150" role="img" aria-label={`${caption}: ${parts.map((p) => `${p.label} ${p.value}`).join(', ')}`}>
      <circle className="c" cx={75} cy={75} r={R} stroke="var(--panel2)" />
      {parts.filter((p) => p.value > 0).map((p) => {
        const len = (p.value / total) * C
        const el = <circle key={p.label} className="c" cx={75} cy={75} r={R} stroke={p.color} strokeDasharray={`${Math.max(len - 2, 0.5)} ${C}`} strokeDashoffset={-acc} transform="rotate(-90 75 75)" />
        acc += len
        return el
      })}
      <text x={75} y={78} textAnchor="middle" fontSize={30}>{centre}</text>
      <text className="sub" x={75} y={96} textAnchor="middle">{caption}</text>
    </svg>
  )
}

const hhmm = (ms: number) => new Date(ms).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })

/** One channel around an alert: the line, a dashed marker where the alert was raised and a faint area after it. */
export function SignalChart({ series, alertMs, fromMs, toMs, label, unit }: { series: Series | null; alertMs: number; fromMs: number; toMs: number; label: string; unit: string }) {
  const W = 560
  const H = 150
  const L = 8
  const R = 8
  const T = 14
  const B = 22
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
        <p className="muted small" style={{ margin: '14px 0' }}>{series ? 'No data in this range.' : 'Loading…'}</p>
      </div>
    )
  }
  const lo = Math.min(...pts.map((p) => p[1]))
  const hi = Math.max(...pts.map((p) => p[1]))
  const span = hi - lo || 1
  const x = (ms: number) => L + ((ms - fromMs) / (toMs - fromMs)) * (W - L - R)
  const y = (v: number) => H - B - ((v - lo) / span) * (H - B - T)
  const d = pts.map(([ms, v], i) => `${i ? 'L' : 'M'}${x(ms).toFixed(1)} ${y(v).toFixed(1)}`).join('')
  const ax = x(alertMs)
  const inside = alertMs >= fromMs && alertMs <= toMs
  return (
    <div className="sig">
      <div className="sh">{label}<span>{lo.toFixed(1)} to {hi.toFixed(1)} {unit}</span></div>
      <svg className="sigsvg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${label} around the alert`}>
        {[0, 0.5, 1].map((f) => <line key={f} className="g" x1={L} x2={W - R} y1={T + f * (H - B - T)} y2={T + f * (H - B - T)} />)}
        {inside && <rect className="after" x={ax} y={T} width={Math.max(0, W - R - ax)} height={H - B - T} />}
        <path className="ln" d={d} />
        {inside && (
          <g>
            <line className="mk" x1={ax} x2={ax} y1={T - 4} y2={H - B} />
            <g className="tag"><rect x={Math.min(Math.max(ax - 24, L), W - R - 48)} y={0} width={48} height={14} rx={7} /><text x={Math.min(Math.max(ax, L + 24), W - R - 24)} y={10.5} textAnchor="middle">Alert</text></g>
          </g>
        )}
        <text className="t" x={L} y={H - 6}>{hhmm(fromMs)}</text>
        <text className="t" x={W - R} y={H - 6} textAnchor="end">{hhmm(toMs)}</text>
      </svg>
    </div>
  )
}
