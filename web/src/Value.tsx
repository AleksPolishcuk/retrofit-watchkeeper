import { median } from './plain'
import type { Healthy, ReportSet, Results } from './types'

const eur = (x: number) => `${x < 0 ? '−' : ''}EUR ${Math.abs(Math.round(x)).toLocaleString('en-GB')}`
const yrs = (x: number | null) => (x === null ? 'never' : `${x.toFixed(1)} years`)

export default function Value({ data }: { data: Results | null }) {
  const b = data?.business
  const hold = data?.report ? ((data.report as Record<string, ReportSet>)['hold fleets (24 pumps)'] as ReportSet | undefined) : undefined
  const healthy = data?.report?.healthy as unknown as Healthy | undefined
  const leads = b?.measured.lead_hours ?? []
  const med = median(leads)
  return (
    <section aria-label="Operational value">
      <h1>What it is worth to an operator</h1>
      <p className="lead muted">Four things an operator gets, each measured on simulated pumps with the organizers' scorer. None of this is field evidence.</p>

      <div className="outcomes">
        <div className="card outcome">
          <b>{b ? `${b.measured.caught_before_limit} of ${b.measured.events_with_limit}` : '—'}</b>
          <h3>Earlier than the alarm</h3>
          <p>Of the faults that went on to reach the plant's usual alarm limit, this many were flagged before it{leads.length ? `, by ${Math.min(...leads).toFixed(1)} to ${Math.max(...leads).toFixed(0)} hours (median ${med?.toFixed(0)} h)` : ''}. The rest were flagged at or after the limit.</p>
        </div>
        <div className="card outcome">
          <b>{hold ? `${Math.round(hold.wk.cls * 100)}%` : '—'}</b>
          <h3>Looks in the right place</h3>
          <p>Faults sorted correctly into machine or instrument{hold?.b1 ? ` (the simple baseline: ${Math.round(hold.b1.cls * 100)}%)` : ''}. Every alert says what to check first, so a drifting sensor does not trigger a repair.</p>
        </div>
        <div className="card outcome">
          <b>{healthy ? healthy.per_pump_month.toFixed(1) : '—'}</b>
          <h3>False alerts per pump-month</h3>
          <p>On healthy simulated pumps, with 95% certainty no more than {healthy ? healthy.upper95_per_pump_month.toFixed(1) : '—'}. Still more than a plant would like; it would be tuned with operators.</p>
        </div>
        <div className="card outcome">
          <b>{hold ? `${hold.wk.composite.toFixed(0)} vs ${hold.b1?.composite.toFixed(0)}` : '—'}</b>
          <h3>Better than a simple rule</h3>
          <p>Score on 24 pumps the method never saw, against the organizers' mode-aware baseline. The plant's own alarms score 23 on the organizers' validation split.</p>
        </div>
      </div>

      <h2>What it could be worth in money (illustrative)</h2>
      {b ? (
        <>
          <p className="muted">Every money figure is an assumption (organizers' worked example, EUR 4,500 installed, 0.6 developing faults per pump per year). Only the detection numbers above are measured.</p>
          <div className="tablewrap">
            <table className="fleettable">
              <thead><tr><th>Where the pump runs</th><th>Downtime per hour</th><th>Net per year</th><th>Pays back in</th></tr></thead>
              <tbody>
                {b.sites.map((s) => (
                  <tr key={s.name}><td>{s.name}</td><td className="num">{eur(s.downtime_eur_h)}</td><td className="num">{eur(s.net)}</td><td className="num">{yrs(s.payback_yr)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small" style={{ marginTop: 8 }}>
            Reading: monitoring alone pays for a pump that has no spare and costly downtime. For a pump with a standby it does not, and the value there is avoided repair cost and crew time. Under the organizers' stricter convention (every alert costs EUR 120 to check) even the first case is {eur(b.base.organizers_convention.net)} per year at today's alert rate. Details and sensitivity: <code>docs/business_case.md</code>.
          </p>
        </>
      ) : <p className="muted">No business case file found. Run <code>python eval/run_business_case.py</code>.</p>}

      <h2>How a plant would use it</h2>
      <ol className="plainlist">
        <li><b>Shadow mode.</b> Read-only data for 4 to 8 weeks. Alerts are logged and compared with what operators actually did. Nobody is asked to act yet.</li>
        <li><b>Advisory pilot.</b> Alerts go to a named role with the evidence view. Approve or mark as false alarm; that feedback is what lowers the false-alert rate.</li>
        <li><b>Review.</b> Decide on scale-up from avoided stops and repairs minus nuisance, then an independent engineering and regulatory check before any operational use.</li>
      </ol>
    </section>
  )
}
