import { useState } from 'react'
import { api } from './api'
import type { Alert, WhatIfResult } from './types'

const fmt = (v: number | null, unit: string) =>
  v === null ? '-' : `${Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2)}${unit && unit !== 'x' ? ' ' + unit : ''}`

function change(a: number | null, b: number | null) {
  if (a === null || b === null || a === 0) return null
  const pct = ((b - a) / Math.abs(a)) * 100
  return Math.abs(pct) < 0.5 ? 'no change' : `${pct > 0 ? '+' : ''}${pct.toFixed(0)}%`
}

export default function WhatIf({ alert }: { alert: Alert }) {
  const [res, setRes] = useState<WhatIfResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const run = () => {
    setBusy(true)
    setErr(null)
    api
      .whatif(alert.asset_id, alert.alert_time_utc, alert.fault_type)
      .then(setRes)
      .catch((e) => setErr(e.message))
      .finally(() => setBusy(false))
  }

  return (
    <div className="whatifpanel">
      <div className="whatifhead">
        <button onClick={run} disabled={busy} className="sim">
          {busy ? 'Simulating…' : res ? 'Run again' : 'Compare in the simulator'}
        </button>
        <span className="pill sim">simulation only</span>
      </div>
      {err && <p className="muted small">Could not run the simulation: {err}</p>}
      {res && !res.available && <p className="muted small">{res.message}</p>}
      {res && res.available && !res.accepted && (
        <p className="muted small">The sandbox refused this comparison: {(res.rejection_reasons ?? []).join('; ')}</p>
      )}
      {res && res.available && res.accepted && (
        <>
          <p className="muted small">
            What if a human carried out <b>{res.action?.replace(/_/g, ' ')}</b> now? Assumed condition: {res.assumed_condition}.
          </p>
          <table className="whatiftable">
            <thead>
              <tr><th>Quantity</th><th>As it is</th><th>After the action</th><th>Change</th></tr>
            </thead>
            <tbody>
              {(res.rows ?? []).map((r) => (
                <tr key={r.label}>
                  <td>{r.label}</td>
                  <td>{fmt(r.baseline, r.unit)}</td>
                  <td>{fmt(r.proposed, r.unit)}</td>
                  <td className="muted">{change(r.baseline, r.proposed) ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {res.intervention && (
            <p className="muted small">
              Work estimate: {res.intervention.stop_h} h stop, {res.intervention.labour_h} h labour, parts EUR {res.intervention.parts_eur}, about EUR{' '}
              {res.intervention.estimated_cost_eur} in total (illustrative).
            </p>
          )}
          {(res.warnings ?? []).map((w, i) => <p key={i} className="muted small">Warning: {w}</p>)}
          <p className="muted small">
            Reduced-order simulator on public nameplate data, not a digital twin. Nothing is sent to the machine.
          </p>
        </>
      )}
    </div>
  )
}
