import { LEVELS, levelOf } from './cases'
import type { Level } from './cases'
import { STAGE_LABEL } from './stage'

/** A recorded week as a line, with a tick at the time of each case. No axes: it shows shape and when the cases fell, not values. */
export function Spark({ t, v, marks, label }: { t: string[]; v: (number | null)[]; marks: { at: string; level: Level }[]; label: string }) {
  const W = 160
  const H = 44
  const nums = v.filter((x): x is number => typeof x === 'number' && Number.isFinite(x))
  if (t.length < 2 || nums.length < 2) return <span className="muted small">no data</span>
  const lo = Math.min(...nums)
  const hi = Math.max(...nums)
  const span = hi - lo || 1
  const t0 = Date.parse(t[0])
  const t1 = Date.parse(t[t.length - 1])
  const x = (ms: number) => ((ms - t0) / (t1 - t0 || 1)) * (W - 4) + 2
  const y = (val: number) => H - 6 - ((val - lo) / span) * (H - 14)
  let d = ''
  let pen = false
  v.forEach((val, i) => {
    if (typeof val !== 'number' || !Number.isFinite(val)) {
      pen = false
      return
    }
    d += `${pen ? 'L' : 'M'}${x(Date.parse(t[i])).toFixed(1)} ${y(val).toFixed(1)} `
    pen = true
  })
  const inside = marks.filter((m) => Date.parse(m.at) >= t0 && Date.parse(m.at) <= t1)
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} preserveAspectRatio="none">
      {inside.map((m, i) => <line key={i} className={`mk s-${m.level}`} x1={x(Date.parse(m.at))} x2={x(Date.parse(m.at))} y1={2} y2={H - 2} />)}
      <path className="ln" d={d.trim()} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

/** Open cases by priority as a ring. The number in the middle is the total. */
export function Donut({ counts, size = 168 }: { counts: Record<Level, number>; size?: number }) {
  const total = LEVELS.reduce((n, l) => n + counts[l], 0)
  const r = 62
  const c = 2 * Math.PI * r
  let off = 0
  return (
    <svg className="donut" viewBox="0 0 168 168" width={size} height={size} role="img" aria-label={`${total} open cases: ${LEVELS.map((l) => `${counts[l]} ${STAGE_LABEL[l]}`).join(', ')}`}>
      <circle className="ring0" cx="84" cy="84" r={r} />
      {total > 0 && LEVELS.map((l) => {
        const len = (counts[l] / total) * c
        const seg = counts[l] > 0 ? <circle key={l} className={`seg s-${l}`} cx="84" cy="84" r={r} strokeDasharray={`${Math.max(len - 2, 0)} ${c - Math.max(len - 2, 0)}`} strokeDashoffset={-off} /> : null
        off += len
        return seg
      })}
      <text className="dn" x="84" y="82" textAnchor="middle">{total}</text>
      <text className="dl" x="84" y="104" textAnchor="middle">open cases</text>
    </svg>
  )
}

export { levelOf }
