import type { Alert } from './types'

export type Decision = 'approved' | 'rejected'

const pretty = (s: string) => s.replace(/_/g, ' ').toLowerCase()
const when = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC'

interface Props {
  alert: Alert
  decision: Decision | undefined
  onDecide: (d: Decision | undefined) => void
}

export default function AlertCard({ alert, decision, onDecide }: Props) {
  const verdict = alert.sensor_check?.verdict
  const quality = alert.uncertainty?.data_quality
  const missing = alert.uncertainty?.missing_channels ?? []
  return (
    <article className="card" aria-live="polite">
      <header className="cardhead">
        <div>
          <span className={`badge ${alert.event_class === 'SENSOR' ? 'sensor' : 'machine'}`}>
            {alert.event_class === 'SENSOR' ? 'instrument' : 'machine'}
          </span>
          <h2>{pretty(alert.fault_type)}</h2>
          <p className="muted">{alert.asset_id} · raised {when(alert.alert_time_utc)}</p>
        </div>
        <div className="conf" title="Model confidence">
          <div className="confbar"><div style={{ width: `${alert.confidence * 100}%` }} /></div>
          <strong>{(alert.confidence * 100).toFixed(0)}%</strong>
          <span className="muted">confidence</span>
        </div>
      </header>

      {alert.alternatives && alert.alternatives.length > 0 && (
        <p className="muted">
          Also considered:{' '}
          {alert.alternatives.map((a) => `${pretty(a.fault_type)} ${(a.p * 100).toFixed(0)}%`).join(', ')}
        </p>
      )}

      <section>
        <h3>Evidence</h3>
        {alert.evidence.length === 0 ? (
          <p className="muted">No single channel stands out.</p>
        ) : (
          <ul className="evidence">
            {alert.evidence.map((e, i) => (
              <li key={i}>
                <code>{e.channel}</code>
                <span>{e.text}</span>
                {e.z !== null && <b className={e.z < 0 ? 'neg' : 'pos'}>{e.z > 0 ? '+' : ''}{e.z.toFixed(1)}σ</b>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="two">
        <div>
          <h3>Machine or instrument?</h3>
          {alert.sensor_check ? (
            <p>
              <span className={`pill v-${verdict}`}>{verdict}</span> {alert.sensor_check.reason}
            </p>
          ) : (
            <p className="muted">Not assessed.</p>
          )}
        </div>
        <div>
          <h3>How sure are we?</h3>
          <p>
            Data quality: <span className={`pill q-${quality ?? 'ok'}`}>{quality ?? 'ok'}</span>
          </p>
          {missing.length > 0 ? (
            <p className="muted">Not measured on this pump: {missing.map((m) => m.replace(/_/g, ' ')).join(', ')}</p>
          ) : (
            <p className="muted">All key channels are measured.</p>
          )}
        </div>
      </section>

      <section className="action">
        <h3>Recommended action for a human</h3>
        <p>{alert.recommended_action}</p>
        {alert.what_if && (
          <p className="whatif">
            <b>Simulation only.</b> {alert.what_if.summary ?? 'A what-if comparison was run in the sandbox.'}
          </p>
        )}
        <div className="decide" role="group" aria-label="Human decision">
          <button className={decision === 'approved' ? 'on ok' : ''} onClick={() => onDecide(decision === 'approved' ? undefined : 'approved')}>
            Approve inspection
          </button>
          <button className={decision === 'rejected' ? 'on bad' : ''} onClick={() => onDecide(decision === 'rejected' ? undefined : 'rejected')}>
            Mark as false alarm
          </button>
        </div>
        <p className="muted small">Your decision is kept in this browser only. Watchkeeper never sends anything to the machine.</p>
      </section>
    </article>
  )
}
