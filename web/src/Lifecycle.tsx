import { useEffect, useState } from 'react'
import { api } from './api'
import Icon from './icons'
import { nameOf } from './plain'
import type { Incident } from './plain'
import { OUTCOME_LABEL, RECOVERY_HOURS, STATUSES, STATUS_LABEL, allowed, earlierSame, quietHoursAfter } from './reviews'
import type { Action, Review } from './reviews'
import { pretty, when } from './stage'
import type { Archived, Asset } from './types'

const FAULTS = [
  'SUCTION_STRAINER_CLOGGING', 'DISCHARGE_RESTRICTION', 'IMPELLER_WEAR', 'AIR_ENTRAINMENT', 'CAVITATION', 'BEARING_WEAR', 'MISALIGNMENT', 'IMBALANCE',
  'SENSOR_DRIFT', 'SENSOR_STUCK', 'SENSOR_CALIBRATION_SHIFT', 'SENSOR_NOISE_SPIKES',
]
const name = (t: string) => (t === 'OTHER' ? 'Something else (describe it in the note)' : pretty(t).replace(/^./, (c) => c.toUpperCase()))
const hours = (h: number) => (h < 10 ? h.toFixed(1) : Math.round(h).toString())
const stamp = (iso: string) => new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

interface Props {
  inc: Incident
  all: Incident[]
  asset: Asset
  review?: Review
  reviews: Record<string, Review>
  act: (a: Action) => void
}

/** Step 4 of the case: what a person decided and where the case stands. Kept in this browser; nothing is sent to the machine. */
export default function Lifecycle({ inc, all, asset, review, reviews, act }: Props) {
  const status = review?.status ?? 'open'
  const can = allowed(review)
  const [confirming, setConfirming] = useState(false)
  const [actual, setActual] = useState(inc.head.fault_type)
  const [note, setNote] = useState('')
  const [snaps, setSnaps] = useState<Archived[]>([])

  useEffect(() => {
    setConfirming(false)
    setActual(inc.head.fault_type)
    setNote('')
  }, [inc.id, inc.head.fault_type])

  useEffect(() => {
    let alive = true
    api.archive(asset.asset_id).then((r) => alive && setSnaps(r)).catch(() => alive && setSnaps([]))
    return () => { alive = false }
  }, [asset.asset_id])

  const earlier = earlierSame(inc, all, reviews)
  const quiet = status === 'recovery' ? quietHoursAfter(inc, all, asset.window_end_utc) : null
  const channels = [...new Set((inc.head.evidence ?? []).map((e) => e.channel))].map(nameOf)
  const at = STATUSES.indexOf(status)
  const options = [inc.head.fault_type, ...FAULTS.filter((f) => f !== inc.head.fault_type), 'OTHER']

  return (
    <div className="life">
      {earlier && (
        <p className="returnnote">
          <Icon name="alert" />
          <span>The same kind of problem was seen on this pump on <span className="mono">{when(earlier.incident.head.alert_time_utc)}</span>
          {earlier.review ? ` (${STATUS_LABEL[earlier.review.status].toLowerCase()}${earlier.review.outcome ? `: ${OUTCOME_LABEL[earlier.review.outcome].toLowerCase()}` : ''})` : ''}.
          This may be a return, not a new problem.</span>
        </p>
      )}

      <ol className="stepper" aria-label="Where this case stands">
        {STATUSES.map((s, i) => (
          <li key={s} className={i < at ? 'done' : i === at ? 'now' : ''} aria-current={i === at ? 'step' : undefined}>
            <i>{i < at ? <Icon name="check" /> : i + 1}</i>
            <span>{STATUS_LABEL[s]}</span>
          </li>
        ))}
      </ol>

      {status === 'open' && (
        <div className="decide" role="group" aria-label="Your decision">
          <button className="btn primary" onClick={() => act({ type: 'approve' })}><Icon name="check" /> Approve inspection</button>
          <button className="btn" onClick={() => act({ type: 'false_alarm' })}>Mark as false alarm</button>
        </div>
      )}

      {status === 'inspection' && !confirming && (
        <div className="lifepanel">
          <p><b>Inspection approved.</b> After the inspection, record what was found.</p>
          <div className="decide" role="group" aria-label="Inspection result">
            <button className="btn" onClick={() => act({ type: 'outcome', outcome: 'no_fault' })}>{OUTCOME_LABEL.no_fault}</button>
            <button className="btn" onClick={() => act({ type: 'outcome', outcome: 'further' })}>{OUTCOME_LABEL.further}</button>
            <button className="btn primary" onClick={() => setConfirming(true)}>{OUTCOME_LABEL.confirmed}</button>
          </div>
        </div>
      )}

      {status === 'inspection' && confirming && (
        <form className="lifepanel" onSubmit={(e) => { e.preventDefault(); act({ type: 'outcome', outcome: 'confirmed', actual: actual === 'OTHER' ? 'OTHER' : actual, note }); setConfirming(false) }}>
          <p><b>What was actually found?</b> The model suggested: <span className="mono">{name(inc.head.fault_type)}</span>.</p>
          <label className="field">Actual fault
            <select value={actual} onChange={(e) => setActual(e.target.value)}>
              {options.map((o) => <option key={o} value={o}>{name(o)}{o === inc.head.fault_type ? ' (model suggestion)' : ''}</option>)}
            </select>
          </label>
          <label className="field">Note (optional)
            <textarea value={note} maxLength={300} rows={2} onChange={(e) => setNote(e.target.value)} placeholder="Component, finding, work done" />
          </label>
          <div className="decide">
            <button className="btn primary" type="submit"><Icon name="check" /> Save: fault confirmed</button>
            <button className="btn" type="button" onClick={() => setConfirming(false)}>Cancel</button>
          </div>
        </form>
      )}

      {status === 'result' && review && (
        <div className="lifepanel">
          <p>
            <b>{review.outcome ? OUTCOME_LABEL[review.outcome] : 'Result recorded'}.</b>
            {review.outcome === 'confirmed' && review.actual && (
              <> Found: <span className="mono">{name(review.actual)}</span>. The model suggested <span className="mono">{name(review.fault_type)}</span>{review.actual === review.fault_type ? ': they match.' : review.actual === 'OTHER' ? '.' : ': different.'}</>
            )}
            {review.note ? <> Note: {review.note}</> : null}
          </p>
          <div className="decide">
            {can.includes('close') && <button className="btn primary" onClick={() => act({ type: 'close' })}><Icon name="check" /> Close the case</button>}
            {can.includes('reinspect') && <button className="btn primary" onClick={() => act({ type: 'reinspect' })}>Back to inspection</button>}
            {can.includes('start_recovery') && <button className="btn primary" onClick={() => act({ type: 'start_recovery' })}>Repair done: start the recovery check</button>}
          </div>
        </div>
      )}

      {status === 'recovery' && (
        <div className="lifepanel">
          <p>
            <b>Recovery check.</b> {channels.length ? <>These readings must be back in their normal range and stay there for <b>{RECOVERY_HOURS} hours</b>: {channels.join(', ')}.</> : <>The readings that raised this alert must be back in their normal range and stay there for <b>{RECOVERY_HOURS} hours</b>.</>}
            {' '}A person confirms; Watchkeeper does not decide that a repair worked.
          </p>
          {quiet && (
            <p className="muted small">
              {quiet.ended === 'next_alert'
                ? <>In the recorded data the same kind of alert came again after <b>{hours(quiet.hours)} h</b>.{quiet.hours < RECOVERY_HOURS ? ' That is shorter than the check requires.' : ''}</>
                : quiet.hours >= RECOVERY_HOURS
                  ? <>In the recorded data this pump raised no further alert of this kind for <b>{hours(quiet.hours)} h</b> after this one (to the end of the recording).</>
                  : <>The recording ends <b>{hours(quiet.hours)} h</b> after this alert, which is shorter than the check requires, so it cannot show whether the pump recovered.</>}
            </p>
          )}
          <div className="decide">
            <button className="btn primary" onClick={() => act({ type: 'confirm_recovery' })}><Icon name="check" /> Recovery confirmed: close the case</button>
            <button className="btn" onClick={() => act({ type: 'came_back' })}>The problem came back</button>
          </div>
        </div>
      )}

      {status === 'closed' && review && (
        <div className="lifepanel">
          <p>
            <b>Closed</b>{review.closed_reason === 'false_alarm' ? ': marked as a false alarm.' : review.closed_reason === 'no_fault' ? ': no fault found.' : review.closed_reason === 'recovered' ? ': recovery confirmed.' : '.'}
            {review.came_back_count > 0 ? ` The problem came back ${review.came_back_count} time${review.came_back_count > 1 ? 's' : ''} before.` : ''}
          </p>
          <div className="decide"><button className="btn" onClick={() => act({ type: 'reopen' })}>Reopen</button></div>
        </div>
      )}

      <p className="muted small">
        A person decides. The log is kept in this browser only and can be exported; Watchkeeper sends nothing to the machine, and existing alarms stay authoritative.
        {inc.head.model_version ? ` Model ${inc.head.model_version}.` : ''}
        {snaps.length > 0 ? ` Alert snapshots kept for this pump: ${snaps.map((s) => `${s.model_version} (${s.alerts} alerts)`).join(', ')}.` : ''}
      </p>

      {review && review.log.length > 0 && (
        <details className="more">
          <summary>History of this case ({review.log.length})</summary>
          <ol className="history">
            {review.log.map((l, i) => <li key={i}><span className="mono">{stamp(l.at)}</span> {l.event}{l.detail ? <span className="muted"> ({l.detail})</span> : null}</li>)}
          </ol>
        </details>
      )}
    </div>
  )
}
