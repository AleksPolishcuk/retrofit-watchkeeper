import { useState } from 'react'
import type { Decision } from './decisions'
import Icon from './icons'
import { pretty, STAGE_LABEL, stageRank, when } from './stage'
import type { Alert } from './types'

export default function Alerts({ alerts, decisions, onOpen }: { alerts: Alert[]; decisions: Record<string, Decision>; onOpen: (a: Alert) => void }) {
  const [filter, setFilter] = useState<'active' | 'reviewed'>('active')
  const [level, setLevel] = useState<'all' | 'likely'>('all')
  const [kind, setKind] = useState<'all' | 'MACHINE' | 'SENSOR'>('all')
  const list = alerts
    .filter((a) => (filter === 'reviewed' ? decisions[a.alert_id] : !decisions[a.alert_id]))
    .filter((a) => level === 'all' || stageRank(a.stage) >= 2)
    .filter((a) => kind === 'all' || a.event_class === kind)
    .sort((a, b) => stageRank(b.stage) - stageRank(a.stage) || b.alert_time_utc.localeCompare(a.alert_time_utc))
  const nActive = alerts.filter((a) => !decisions[a.alert_id]).length
  return (
    <section aria-label="Alerts">
      <h1>Alerts</h1>
      <p className="muted lead">Every alert from the recorded week, strongest first. An alert is a recommendation to look, not a command and not a probability.</p>
      <div className="controls">
        <div className="seg" role="group" aria-label="Status">
          <button className={filter === 'active' ? 'on' : ''} onClick={() => setFilter('active')}>Active ({nActive})</button>
          <button className={filter === 'reviewed' ? 'on' : ''} onClick={() => setFilter('reviewed')}>Reviewed ({alerts.length - nActive})</button>
        </div>
        <div className="seg" role="group" aria-label="Level">
          <button className={level === 'all' ? 'on' : ''} onClick={() => setLevel('all')}>All levels</button>
          <button className={level === 'likely' ? 'on' : ''} onClick={() => setLevel('likely')}>Likely and above</button>
        </div>
        <div className="seg" role="group" aria-label="Kind">
          <button className={kind === 'all' ? 'on' : ''} onClick={() => setKind('all')}>All</button>
          <button className={kind === 'MACHINE' ? 'on' : ''} onClick={() => setKind('MACHINE')}>Machine</button>
          <button className={kind === 'SENSOR' ? 'on' : ''} onClick={() => setKind('SENSOR')}>Instrument</button>
        </div>
      </div>
      <div className="card recent">
        <ul>
          {list.map((a) => (
            <li key={a.alert_id} className="item">
              <div className={`ico ${a.event_class === 'SENSOR' ? 'sensor' : 'machine'}`}><Icon name={a.event_class === 'SENSOR' ? 'sensor' : 'wrench'} label={a.event_class === 'SENSOR' ? 'instrument' : 'machine'} /></div>
              <div>
                <b>{a.asset_id} · {pretty(a.fault_type)}</b>
                <span className="sub">{when(a.alert_time_utc)} · <span className={`stagechip s-${a.stage ?? 'watch'}`}>{STAGE_LABEL[a.stage ?? 'watch']}</span>{decisions[a.alert_id] ? ` · ${decisions[a.alert_id] === 'approved' ? 'inspection approved' : 'marked false alarm'}` : ''}</span>
                {a.check && <span className="sub" style={{ marginTop: 3 }}>Check first: {a.check}</span>}
              </div>
              <button className="btn sm" onClick={() => onOpen(a)}>View</button>
            </li>
          ))}
          {list.length === 0 && <li className="muted" style={{ padding: 12 }}>Nothing matches these filters.</li>}
        </ul>
      </div>
    </section>
  )
}
