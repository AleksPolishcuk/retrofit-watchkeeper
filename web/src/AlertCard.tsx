import { basisText, headline, pretty, STAGE_LABEL, when } from './stage'
import type { Alert } from './types'
import WhatIf from './WhatIf'

export type Decision = 'approved' | 'rejected'

const TIER_NOTE: Record<string, string> = {
  T0_LEGACY: 'Legacy instrumentation: fewer channels, so fewer causes can be told apart.',
  T1_RETROFIT: 'Retrofit instrumentation: vibration and bearing temperature arrive every few minutes.',
  T2_FULL: 'Fully instrumented pump.',
}

interface Props {
  alert: Alert
  incidentSize: number
  decision: Decision | undefined
  onDecide: (d: Decision | undefined) => void
}

export default function AlertCard({ alert, incidentSize, decision, onDecide }: Props) {
  const verdict = alert.sensor_check?.verdict
  const quality = alert.uncertainty?.data_quality
  const missing = alert.uncertainty?.missing_channels ?? []
  const stage = alert.stage
  return (
    <article className="card" aria-live="polite">
      <header className="cardhead">
        <div>
          <p className={`headline h-${stage ?? 'watch'}`}>{headline(alert)}</p>
          <h2>{pretty(alert.fault_type)}</h2>
          <p className="muted">
            <span className={`badge ${alert.event_class === 'SENSOR' ? 'sensor' : 'machine'}`}>{alert.event_class === 'SENSOR' ? 'instrument' : 'machine'}</span>
            {' '}{alert.asset_id} · raised {when(alert.alert_time_utc)}
            {alert.incident_id && <> · incident <code>{alert.incident_id.split('-').slice(-1)[0]}</code> ({incidentSize} alert{incidentSize === 1 ? '' : 's'})</>}
          </p>
        </div>
        {stage && (
          <div className="stagebox" title="Back-tested level, not a probability">
            <span className={`stagechip s-${stage}`}>{STAGE_LABEL[stage]}</span>
            <span className="muted small">{basisText(alert.stage_basis)}</span>
          </div>
        )}
      </header>

      {alert.consequence && (
        <section className="two">
          <div>
            <h3>What it may mean</h3>
            <p>{alert.consequence}</p>
          </div>
          <div>
            <h3>Check this first</h3>
            <p>{alert.check}</p>
          </div>
        </section>
      )}

      {alert.alternatives && alert.alternatives.length > 0 && (
        <p className="muted small">Also considered: {alert.alternatives.map((a) => pretty(a.fault_type)).join(', ')}</p>
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
            <p><span className={`pill v-${verdict}`}>{verdict}</span> {alert.sensor_check.reason}</p>
          ) : (
            <p className="muted">Not assessed.</p>
          )}
        </div>
        <div>
          <h3>What limits our certainty</h3>
          <p>Data quality: <span className={`pill q-${quality ?? 'ok'}`}>{quality ?? 'ok'}</span></p>
          {missing.length > 0 ? (
            <p className="muted small">Not measured on this pump: {missing.map((m) => m.replace(/_/g, ' ')).join(', ')}</p>
          ) : (
            <p className="muted small">All key channels are measured.</p>
          )}
          {alert.tier && <p className="muted small">{TIER_NOTE[alert.tier]}</p>}
          <p className="muted small">Time to act: {alert.time_to_act ?? alert.time_to_act_note ?? 'not estimated'}.</p>
        </div>
      </section>

      <section className="action">
        <h3>Recommended action for a human</h3>
        <p>{alert.recommended_action}</p>
        <WhatIf key={alert.alert_id} alert={alert} />
        {alert.what_if && (
          <p className="whatif"><b>Simulation only.</b> {alert.what_if.summary ?? 'A what-if comparison was run in the sandbox.'}</p>
        )}
        <div className="decide" role="group" aria-label="Human decision">
          <button className={decision === 'approved' ? 'on ok' : ''} onClick={() => onDecide(decision === 'approved' ? undefined : 'approved')}>
            Approve inspection
          </button>
          <button className={decision === 'rejected' ? 'on bad' : ''} onClick={() => onDecide(decision === 'rejected' ? undefined : 'rejected')}>
            Mark as false alarm
          </button>
        </div>
        <p className="muted small">
          Your decision is kept in this browser only. Watchkeeper never sends anything to the machine.
          {alert.model_version && <> Model <code>{alert.model_version}</code>.</>}
        </p>
      </section>
    </article>
  )
}
