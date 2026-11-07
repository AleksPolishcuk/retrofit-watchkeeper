import { STAGE_LABEL, STAGES } from './stage'
import { useWidth } from './useWidth'
import type { Healthy, ReportSet, Results } from './types'

const ORDER: [string, string][] = [
  ['hold fleets (24 pumps)', 'Untouched hold fleets · 24 pumps, 82 events'],
  ['tune fleets (16 pumps)', 'Tuning fleets · 16 pumps, 48 events'],
  ['9 public dev pumps', 'Public pumps · 9 pumps, 35 events'],
  ['masked-clogging trap (3 pumps)', 'Masked-clogging trap · 3 pumps, 6 events'],
]
const f = (x: number | null | undefined, d = 2) => (x === null || x === undefined || Number.isNaN(x) ? '—' : x.toFixed(d))

function Chart({ sets }: { sets: [string, ReportSet][] }) {
  const [box, W] = useWidth<HTMLDivElement>(860)
  const narrow = W < 620                              // on a phone the label goes above its bar so that text keeps its real size
  const L = narrow ? 12 : 330
  const rowH = narrow ? 76 : 54
  const x = (v: number) => L + (v / 100) * (W - L - 24)
  const H = sets.length * rowH + 40
  return (
    <div ref={box} className="chartbox">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Score of Watchkeeper, the organizers' baseline and random alerts, per evaluation set" className="rchart">
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line className="grid" x1={x(v)} x2={x(v)} y1={8} y2={H - 28} />
            <text className="tick" x={x(v)} y={H - 10} textAnchor="middle">{v}</text>
          </g>
        ))}
        {sets.map(([label, s], i) => {
          const y = (narrow ? 44 : 28) + i * rowH
          return (
            <g key={label}>
              {narrow
                ? <text className="rlabel" x={L} y={y - 22} textAnchor="start">{label}</text>
                : <text className="rlabel" x={L - 12} y={y + 5} textAnchor="end">{label}</text>}
              <rect className="bar wk" x={x(0)} y={y - 12} width={Math.max(0, x(s.wk.composite) - x(0))} height={24} rx={4} />
              {s.wk.lo !== null && s.wk.hi !== null && (
                <g className="whisker"><line x1={x(s.wk.lo)} x2={x(s.wk.hi)} y1={y} y2={y} /><line x1={x(s.wk.lo)} x2={x(s.wk.lo)} y1={y - 6} y2={y + 6} /><line x1={x(s.wk.hi)} x2={x(s.wk.hi)} y1={y - 6} y2={y + 6} /></g>
              )}
              <text className="rval" x={x(0) + 10} y={y + 5} textAnchor="start">{s.wk.composite.toFixed(1)}</text>
              {s.b1 && <polygon className="b1mark" points={`${x(s.b1.composite)},${y - 17} ${x(s.b1.composite) + 6},${y - 11} ${x(s.b1.composite)},${y - 5} ${x(s.b1.composite) - 6},${y - 11}`}><title>organizers' baseline: {s.b1.composite.toFixed(1)}</title></polygon>}
              <line className="nullmark" x1={x(s.null_random_alerts)} x2={x(s.null_random_alerts)} y1={y + 8} y2={y + 22}><title>random alerts: {s.null_random_alerts.toFixed(1)}</title></line>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

const CHECKS: [string, string, string][] = [
  ['It only uses the past', 'Every alert uses data up to its own timestamp. A test cuts the telemetry at several points and requires the earlier alerts to stay identical. The organizers\' own baseline fails that test; ours passes.', 'tests/test_evalkit.py'],
  ['It cannot touch the machine', 'The interface has read-only routes and nothing in the code sends a command to a pump, drive, valve, PLC or safety system. A test fails if a write route is ever added.', 'tests/test_api.py'],
  ['A person decides', 'Every alert is advice. Approving an inspection or marking a false alarm is recorded in the browser only. Existing alarms and trips stay authoritative.', 'src/watchkeeper/alerts'],
  ['It shows its evidence', 'Each alert lists the channels that moved, how far, and what could not be seen on that pump (missing sensors, instrumentation level).', 'docs/alert.schema.json'],
  ['It does not pretend to be certain', 'Likelihood is four words backed by back-test counts, never a percentage. Time to act is "not estimated" because we cannot predict it.', 'models/stages.json'],
  ['Test pumps were never used', 'The three test pumps were never loaded by any evaluation code. Their alerts were written once, from a frozen model at a tagged commit with the model hash recorded.', 'submission/predictions_test.meta.json'],
  ['Negative results are kept', 'A signal-fusion detector and a slow-change detector were built, tested, found not to help, and switched off. The table is published.', 'eval/results/signature.md'],
]

export default function Proof({ data }: { data: Results | null }) {
  if (!data?.report) return <section><h1>Can you trust it?</h1><p className="muted">No results file found. Run <code>make report</code>.</p></section>
  const rep = data.report as Record<string, ReportSet>
  const keyOf = (k: string) => (k in rep ? k : Object.keys(rep).find((x) => x.startsWith(k.split(' (')[0])) ?? k)
  const sets = ORDER.map(([k, label]) => [label, rep[keyOf(k)]] as [string, ReportSet]).filter(([, s]) => s)
  const hold = rep['hold fleets (24 pumps)']
  const healthy = data.report['healthy'] as unknown as Healthy | undefined
  return (
    <section aria-label="Technical quality, reliability and safety">
      <h1>Can you trust it?</h1>
      <p className="lead muted">Measured on simulated pumps with the organizers' own scorer. It shows how the method behaves on this benchmark, not how it would behave in a plant.</p>

      <h2>1. Does it work?</h2>
      <div className="callouts">
        {hold && <div className="card callout"><b>{hold.wk.composite.toFixed(1)}</b><span>on {hold.wk.events} faults on pumps the method never saw (95% interval {f(hold.wk.lo, 0)} to {f(hold.wk.hi, 0)}). The organizers' baseline scores {f(hold.b1?.composite, 1)}; random alerts score {f(hold.null_random_alerts, 1)}.</span></div>}
        {healthy && <div className="card callout"><b>{healthy.per_pump_month.toFixed(1)}</b><span>false alert episodes per pump-month on {healthy.pump_days.toFixed(0)} pump-days with no faults (95% upper bound {healthy.upper95_per_pump_month.toFixed(1)}).</span></div>}
      </div>
      <Chart sets={sets} />
      <p className="legend">
        <span><i className="sw wk" /> Watchkeeper (line: 95% interval)</span>
        <span><i className="sw b1" /> organizers' baseline</span>
        <span><i className="sw nl" /> random alerts</span>
      </p>

      <h2>2. Is it safe to use?</h2>
      <div className="checks">
        {CHECKS.map(([t, d, where]) => (
          <div key={t} className="card check"><h3>{t}</h3><p>{d}</p><code>{where}</code></div>
        ))}
      </div>

      <h2>3. Does it say when it is unsure?</h2>
      {data.stages && (
        <div className="tablewrap">
          <table className="fleettable">
            <thead><tr><th>Level</th><th>Alerts in back-tests</th><th>Pointed at a real problem</th><th>Named the right cause</th></tr></thead>
            <tbody>
              {STAGES.map((s) => (
                <tr key={s}><td><span className={`stagechip s-${s}`}>{STAGE_LABEL[s]}</span></td><td className="num">{data.stages!.detail[s].alerts}</td><td className="num">{data.stages!.detail[s].at_a_real_event}</td><td className="num">{data.stages!.detail[s].right_type}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data.missing_sensor && (
        <>
          <p className="muted" style={{ marginTop: 14 }}>When a sensor is missing the score falls gradually (untouched fleets, 82 faults):</p>
          <div className="tablewrap">
            <table className="fleettable">
              <thead><tr><th>Missing</th><th>Score</th><th>Change</th></tr></thead>
              <tbody>
                {data.missing_sensor.map((r, i) => (
                  <tr key={r.scenario}><td>{r.scenario}</td><td className="num">{r.composite.toFixed(1)}</td><td className="num">{i === 0 ? '—' : (r.composite - data.missing_sensor![0].composite).toFixed(1)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h2>4. Where does it fail?</h2>
      <ul className="limits">
        <li><b>Simulated data only.</b> A reduced-order simulator, fault growth compressed into seven days. Nothing here is field evidence.</li>
        <li><b>The exact cause is often wrong.</b> Only about two in five faults get the right type; machine faults are often called instrument drift. The class (machine or instrument) is right about three times in five, which is why each alert says what to check first.</li>
        <li><b>Masked clogging.</b> On the trap fleets, where the suction signal is partly hidden, the score is below the organizers' baseline and the type is never named.</li>
        <li><b>False alerts remain</b>, mostly at operating points the first 24 hours did not include.</li>
        <li><b>Not certified, not a safety system.</b> It advises; a person decides.</li>
      </ul>

      <details className="more card">
        <summary>All numbers for all sets</summary>
        <div className="tablewrap">
          <table className="fleettable">
            <thead><tr><th>Set</th><th>Score</th><th>F1</th><th>Recall</th><th>Precision</th><th>Type recall</th><th>Class recall</th><th>False + repeat per pump-day</th></tr></thead>
            <tbody>
              {sets.map(([label, s]) => (
                <tr key={label}><td>{label}</td><td className="num">{s.wk.composite.toFixed(1)}</td><td className="num">{f(s.wk.f1)}</td><td className="num">{f(s.wk.recall)}</td><td className="num">{f(s.wk.prec)}</td><td className="num">{f(s.wk.type)}</td><td className="num">{f(s.wk.cls)}</td><td className="num">{f(s.wk.fa)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  )
}
