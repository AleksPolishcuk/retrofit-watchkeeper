import { useState } from 'react'
import type { Incident } from './plain'
import { summarize, toCsv, toJson } from './reviews'
import type { Review } from './reviews'

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const pct = (x: number | null) => (x === null ? 'n/a' : `${Math.round(x * 100)} %`)
const minutes = (m: number | null) => (m === null ? 'n/a' : m < 1 ? 'under a minute' : m < 90 ? `${Math.round(m)} min` : `${(m / 60).toFixed(1)} h`)

/** What the people using this browser decided about the cases, with an export. Kept in this browser only. */
export default function ReviewLog({ incidents, reviews, clear }: { incidents: Incident[]; reviews: Record<string, Review>; clear: () => void }) {
  const [sure, setSure] = useState(false)
  const s = summarize(incidents, reviews)
  const all = Object.values(reviews)
  const day = new Date().toISOString().slice(0, 10)
  return (
    <details className="more reviewlog">
      <summary>Review log in this browser ({s.reviewed} of {s.cases} cases acted on)</summary>
      <dl className="kpis">
        <div><dt>Open</dt><dd>{s.open}</dd></div>
        <div><dt>On inspection</dt><dd>{s.inspection}</dd></div>
        <div><dt>Result recorded</dt><dd>{s.result}</dd></div>
        <div><dt>Recovery check</dt><dd>{s.recovery}</dd></div>
        <div><dt>Closed</dt><dd>{s.closed}</dd></div>
      </dl>
      <p className="small">
        Judged: <b>{s.confirmed}</b> fault confirmed, <b>{s.no_fault}</b> no fault found, <b>{s.false_alarm}</b> false alarm{s.further ? `, ${s.further} need further inspection` : ''}.
        Confirmed share of the judged cases: <b>{pct(s.confirmed_share)}</b>. Median time from first looking at a case to the first decision: <b>{minutes(s.median_minutes_to_decision)}</b>.
      </p>
      <p className="muted small">These figures come from this browser's log, not from a plant. With a handful of cases they show how the log works, not how good the alerts are.</p>
      <div className="decide">
        <button className="btn sm" disabled={all.length === 0} onClick={() => download(`watchkeeper-review-log-${day}.csv`, toCsv(all), 'text/csv')}>Export CSV</button>
        <button className="btn sm" disabled={all.length === 0} onClick={() => download(`watchkeeper-review-log-${day}.json`, toJson(all), 'application/json')}>Export JSON</button>
        {!sure
          ? <button className="btn sm" disabled={all.length === 0} onClick={() => setSure(true)}>Clear the log</button>
          : <button className="btn sm on-bad" onClick={() => { clear(); setSure(false) }}>Yes, clear {all.length} entries</button>}
      </div>
    </details>
  )
}
