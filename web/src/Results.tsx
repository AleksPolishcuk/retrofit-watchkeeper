import type { Healthy, ReportSet, Results } from './types'
import { STAGE_LABEL, STAGES } from './stage'

const ORDER: [string, string][] = [
  ['hold fleets (24 pumps)', 'Untouched hold fleets (24 pumps, 82 events)'],
  ['tune fleets (16 pumps)', 'Tuning fleets (16 pumps, 48 events)'],
  ['9 public dev pumps', 'Public development pumps (9 pumps, 35 events)'],
  ['masked-clogging trap (3 pumps)', 'Masked-clogging trap (3 pumps, 6 events)'],
]
const f = (x: number | null | undefined, d = 2) => (x === null || x === undefined || Number.isNaN(x) ? '—' : x.toFixed(d))

function Chart({ sets }: { sets: [string, ReportSet][] }) {
  const W = 880
  const L = 345
  const rowH = 58
  const x = (v: number) => L + (v / 100) * (W - L - 20)
  const H = sets.length * rowH + 40
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Composite score of Watchkeeper, the organizers' baseline and a random-alert null, per evaluation set" className="rchart">
      {[0, 25, 50, 75, 100].map((v) => (
        <g key={v}>
          <line className="grid" x1={x(v)} x2={x(v)} y1={8} y2={H - 26} />
          <text className="tick" x={x(v)} y={H - 10} textAnchor="middle">{v}</text>
        </g>
      ))}
      {sets.map(([label, s], i) => {
        const y = 22 + i * rowH
        return (
          <g key={label}>
            <text className="rlabel" x={L - 12} y={y + 5} textAnchor="end">{label}</text>
            <rect className="bar wk" x={x(0)} y={y - 11} width={x(s.wk.composite) - x(0)} height={22} rx={3} />
            {s.wk.lo !== null && s.wk.hi !== null && (
              <g className="whisker"><line x1={x(s.wk.lo)} x2={x(s.wk.hi)} y1={y} y2={y} /><line x1={x(s.wk.lo)} x2={x(s.wk.lo)} y1={y - 6} y2={y + 6} /><line x1={x(s.wk.hi)} x2={x(s.wk.hi)} y1={y - 6} y2={y + 6} /></g>
            )}
            <text className="rval" x={x(s.wk.composite) - 6} y={y + 4} textAnchor="end">{s.wk.composite.toFixed(1)}</text>
            {s.b1 && <polygon className="b1mark" points={`${x(s.b1.composite)},${y - 14} ${x(s.b1.composite) + 6},${y - 8} ${x(s.b1.composite)},${y - 2} ${x(s.b1.composite) - 6},${y - 8}`}><title>organizers' baseline B1: {s.b1.composite.toFixed(1)}</title></polygon>}
            <line className="nullmark" x1={x(s.null_random_alerts)} x2={x(s.null_random_alerts)} y1={y + 6} y2={y + 20}><title>random alerts, same count and type mix: {s.null_random_alerts.toFixed(1)}</title></line>
          </g>
        )
      })}
    </svg>
  )
}

export default function ResultsPage({ data }: { data: Results | null }) {
  if (!data?.report) return <section><h1>Results</h1><p className="muted">No results file found. Run <code>make report</code>.</p></section>
  const sets = ORDER.filter(([k]) => k in (data.report ?? {})).map(([k, label]) => [label, (data.report as Record<string, ReportSet>)[k]] as [string, ReportSet])
  const hold = (data.report as Record<string, ReportSet>)['hold fleets (24 pumps)']
  const healthy = data.report['healthy'] as unknown as Healthy | undefined
  return (
    <section className="results" aria-label="Measured results">
      <h1>Measured results</h1>
      <p className="muted lead">
        Everything here is measured on simulated pumps with the organizers' own scorer. It shows how the method behaves on this benchmark, not how it would perform
        in a plant.
      </p>

      <div className="callouts">
        {hold && (
          <div className="callout">
            <b>{hold.wk.composite.toFixed(1)}</b>
            <span>on {hold.wk.events} events from fleets the method never saw (95% interval {f(hold.wk.lo, 0)} to {f(hold.wk.hi, 0)}). The organizers' baseline scores {f(hold.b1?.composite, 1)} on the same fleets; random alerts score {f(hold.null_random_alerts, 1)}.</span>
          </div>
        )}
        {healthy && (
          <div className="callout">
            <b>{healthy.per_pump_month.toFixed(1)}</b>
            <span>false alert episodes per pump-month on {healthy.pump_days.toFixed(0)} pump-days with no faults (upper 95% bound {healthy.upper95_per_pump_month.toFixed(1)}). Still above what an operator would like; see limits.</span>
          </div>
        )}
      </div>

      <h2>Composite score</h2>
      <Chart sets={sets} />
      <p className="legend">
        <span><i className="sw wk" /> Watchkeeper (whisker: 95% interval, resampling pumps)</span>
        <span><i className="sw b1" /> organizers' baseline</span>
        <span><i className="sw nl" /> random alerts</span>
      </p>

      <div className="tablewrap">
        <table className="fleettable">
          <thead><tr><th>Set</th><th>Composite</th><th>F1</th><th>Recall</th><th>Precision</th><th>Type recall</th><th>Class recall</th><th>False + repeat per pump-day</th></tr></thead>
          <tbody>
            {sets.map(([label, s]) => (
              <tr key={label}><td>{label}</td><td className="num">{s.wk.composite.toFixed(1)}</td><td className="num">{f(s.wk.f1)}</td><td className="num">{f(s.wk.recall)}</td><td className="num">{f(s.wk.prec)}</td><td className="num">{f(s.wk.type)}</td><td className="num">{f(s.wk.cls)}</td><td className="num">{f(s.wk.fa)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>

      {hold?.by_tier && (
        <>
          <h2>By instrumentation, untouched hold fleets</h2>
          <div className="tablewrap">
            <table className="fleettable">
              <thead><tr><th>Tier</th><th>Events</th><th>Found</th><th>Right fault type</th></tr></thead>
              <tbody>
                {Object.entries(hold.by_tier).map(([t, c]) => (
                  <tr key={t}><td>{t.replace('_', ' ').toLowerCase()}</td><td className="num">{c.events}</td><td className="num">{c.detected}</td><td className="num">{c.right_type}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {data.stages && (
        <>
          <h2>What the likelihood words mean</h2>
          <p className="muted">Alerts from back-tests on {data.stages.sets.join(' and ')}, counted by level. The words are never shown as percentages.</p>
          <div className="tablewrap">
            <table className="fleettable">
              <thead><tr><th>Level</th><th>Alerts</th><th>At a real event</th><th>Right fault type</th></tr></thead>
              <tbody>
                {STAGES.map((s) => (
                  <tr key={s}><td><span className={`stagechip s-${s}`}>{STAGE_LABEL[s]}</span></td><td className="num">{data.stages!.detail[s].alerts}</td><td className="num">{data.stages!.detail[s].at_a_real_event}</td><td className="num">{data.stages!.detail[s].right_type}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h2>Limits, stated plainly</h2>
      <ul className="limits">
        <li><b>Simulated data only.</b> The pumps come from a reduced-order simulator and fault growth is compressed into seven days. Nothing here is evidence of field performance.</li>
        <li><b>The fault type is often wrong.</b> Only about two in five faults are named correctly, and machine faults are often called instrument drift. The class (machine or instrument) is right more often than the type. The alert says which instrument to check first for that reason.</li>
        <li><b>Masked clogging is a weak spot.</b> On the trap fleets with a partly hidden suction signal we score below the organizers' baseline and never name the type.</li>
        <li><b>False alerts.</b> About {healthy ? healthy.per_pump_month.toFixed(1) : 'one'} per pump-month on healthy simulated pumps, caused mostly by operating points that the 24-hour baseline has not seen.</li>
        <li><b>Fusing weak signals across channels did not help.</b> We built and tested it; it found more events but added false alerts and no earlier warning, so it is switched off. The measured table is in <code>eval/results/signature.md</code>.</li>
        <li><b>Not certified, not a safety system.</b> It advises; a person decides.</li>
      </ul>
    </section>
  )
}
