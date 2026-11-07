import type { Healthy, ReportSet, Results } from './types'

const TIER_NAME: Record<string, string> = { T0_LEGACY: 'T0 · Legacy', T1_RETROFIT: 'T1 · Low-cost retrofit', T2_FULL: 'T2 · Fully instrumented' }
const TIER_SEES: Record<string, string> = {
  T0_LEGACY: 'Motor current, discharge pressure and temperatures. Enough to notice that something moved, rarely enough to say which part.',
  T1_RETROFIT: 'Adds suction pressure and a wireless vibration and bearing-temperature sensor that reports every few minutes. Good for bearing, alignment and strainer problems.',
  T2_FULL: 'Adds flow, power, winding temperature and fast vibration. The only tier where hydraulic faults can be told apart reliably.',
}
const pretty = (s: string) => s.replace(/_(kpa|a|kw|c|m3_h|pct|mm_s|g|rpm)$/, '').replace(/_/g, ' ')

function Architecture() {
  const box = (x: number, y: number, w: number, t: string, sub: string, cls = '') => (
    <g className={`abox ${cls}`}>
      <rect x={x} y={y} width={w} height={64} rx={8} />
      <text x={x + w / 2} y={y + 27} textAnchor="middle" className="at">{t}</text>
      <text x={x + w / 2} y={y + 47} textAnchor="middle" className="as">{sub}</text>
    </g>
  )
  return (
    <svg viewBox="0 0 900 190" role="img" aria-label="Data flows one way: existing sensors, a read-only gateway, Watchkeeper, advice shown to a person" className="arch">
      <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" className="arrowhead" /></marker></defs>
      {box(10, 20, 170, 'Pump and sensors', 'existing, unchanged')}
      {box(235, 20, 170, 'Gateway or historian', 'read-only copy of the data')}
      {box(460, 20, 190, 'Watchkeeper', 'runs on one CPU core', 'wk')}
      {box(705, 20, 185, 'Operator screen', 'advice and evidence')}
      {[[180, 235], [405, 460], [650, 705]].map(([a, b]) => <line key={a} x1={a} y1={52} x2={b - 4} y2={52} className="flow" markerEnd="url(#arr)" />)}
      <rect x={150} y={118} width={575} height={44} rx={8} className="nowrite" />
      <text x={442} y={145} textAnchor="middle" className="nw">No command path back to the pump, drive, valve, PLC or safety system</text>
      <line x1={797} y1={84} x2={797} y2={128} className="human" />
      <text x={797} y={150} textAnchor="middle" className="as">a person decides and acts</text>
    </svg>
  )
}

export default function RetrofitPage({ data }: { data: Results | null }) {
  const hold = data?.report ? ((data.report as Record<string, ReportSet>)['hold fleets (24 pumps)'] as ReportSet | undefined) : undefined
  const healthy = data?.report?.healthy as unknown as Healthy | undefined
  const fp = data?.footprint
  return (
    <section className="retrofit" aria-label="Retrofit and transfer">
      <h1>Retrofit: what it needs and what it does not touch</h1>
      <p className="muted lead">Watchkeeper is a read-only layer on top of data that already exists. It adds nothing to the control system.</p>

      <h2>Data flow</h2>
      <Architecture />

      <h2>What each instrumentation level can see</h2>
      <div className="tiers">
        {(data?.tiers ?? []).map((t) => {
          const c = hold?.by_tier?.[t.tier]
          return (
            <article key={t.tier} className="card tiercard">
              <h3>{TIER_NAME[t.tier]}</h3>
              <p>{TIER_SEES[t.tier]}</p>
              <p className="small muted"><b>Always measured:</b> {t.channels.map(pretty).join(', ')}.</p>
              {t.sometimes.length > 0 && <p className="small muted"><b>On some pumps:</b> {t.sometimes.map(pretty).join(', ')}.</p>}
              {c && <p className="small">Untouched hold fleets: {c.detected} of {c.events} events found, fault type right on {c.right_type}.</p>}
            </article>
          )
        })}
      </div>
      <p className="muted small">Fewer sensors give fewer causes that can be separated. Watchkeeper says so on each alert (what limits our certainty) instead of guessing. The counts above come from different mixes of faults on 5 to 10 pumps per level, so they show a direction and do not rank the levels; in particular they do not show that more sensors find fewer faults.</p>

      {data?.missing_sensor && (
        <>
          <h2>If a sensor is missing or fails</h2>
          <p className="muted">The frozen model on the untouched hold fleets (82 events) with whole channels removed from the data. The score falls gradually; no single missing channel breaks it.</p>
          <div className="tablewrap">
            <table className="fleettable">
              <thead><tr><th>Scenario</th><th>Composite</th><th>Change</th><th>Recall</th><th>Class recall</th></tr></thead>
              <tbody>
                {data.missing_sensor.map((r, i) => (
                  <tr key={r.scenario}>
                    <td>{r.scenario}</td>
                    <td className="num">{r.composite.toFixed(1)}</td>
                    <td className="num">{i === 0 ? '—' : (r.composite - data.missing_sensor![0].composite).toFixed(1)}</td>
                    <td className="num">{r.recall.toFixed(2)}</td>
                    <td className="num">{r['class recall'].toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">The vibration sensor and discharge pressure matter most; flow, power and the extra temperatures matter least. That agrees with the advice to start from what the drive and the motor starter already know.</p>
        </>
      )}

      <h2>What it needs on site</h2>
      <div className="tablewrap">
        <table className="fleettable">
          <tbody>
            <tr><th>Compute</th><td>{fp ? <>One CPU core, no GPU, no network. The model file is {fp.model_mb} MB; a full week of one pump ({fp.minutes_scored.toLocaleString('en-GB')} one-minute rows) is scored in {fp.score_s} s on a laptop (Python {fp.python}); a laptop-class process peaked at {fp.peak_rss_mb} MB including loading the whole data table.</> : 'Not measured yet.'}</td></tr>
            <tr><th>Data</th><td>One-minute averages of the pump's existing channels, read from a historian, gateway or MQTT feed. Timestamps in UTC.</td></tr>
            <tr><th>Per pump</th><td>An asset record (instrumentation, rated speed and power, suction static head) and about 24 hours of normal running to learn what normal looks like at each operating point.</td></tr>
            <tr><th>New operating point</th><td>A speed the pump has not run at before is learned for two hours before it is judged, so a healthy demand change does not raise an alert.</td></tr>
            <tr><th>Write access</th><td>None. The interface offers GET routes only, and the code has no path that sends anything to a machine.</td></tr>
          </tbody>
        </table>
      </div>

      <h2>Moving to another plant</h2>
      <ul className="limits">
        <li>The detector does not use pump names or site-specific thresholds. It learns each pump's own normal and compares the pump with itself.</li>
        <li>What does transfer: the baseline method, the rules for gaps and frozen values, the physical cavitation check, the incident grouping and the human-approval flow.</li>
        <li>What would need local work: the fault-type model was trained on simulated cooling-water pumps. Other pump types, fluids or drives need their own examples, and this has not been tested.</li>
        <li>False alerts on healthy simulated pumps are {healthy ? healthy.per_pump_month.toFixed(1) : 'about one'} per pump-month. In a real plant that would be tuned with the operators, not assumed.</li>
      </ul>
    </section>
  )
}
