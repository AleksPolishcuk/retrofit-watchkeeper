import Icon from './icons'
import { pretty, STAGE_LABEL, stageRank } from './stage'
import type { Alert, Asset } from './types'

const TIER: Record<string, string> = { T0_LEGACY: 'T0', T1_RETROFIT: 'T1', T2_FULL: 'T2' }
const TIER_HELP: Record<string, string> = {
  T0_LEGACY: 'Legacy: motor current, discharge pressure, temperatures',
  T1_RETROFIT: 'Low-cost retrofit: adds suction pressure and a wireless vibration sensor',
  T2_FULL: 'Fully instrumented: adds flow, power, winding temperature, fast vibration',
}

export default function Pumps({ assets, alerts, onOpen }: { assets: Asset[]; alerts: Alert[]; onOpen: (id: string) => void }) {
  return (
    <section aria-label="Pumps">
      <h1>Pumps</h1>
      <p className="muted lead">Twelve simulated cooling-water pumps at four fictional plants. The instrumentation level decides what can be seen: T0 legacy, T1 low-cost retrofit, T2 full.</p>
      <div className="tiers">
        {assets.map((a) => {
          const mine = alerts.filter((x) => x.asset_id === a.asset_id)
          const top = mine.reduce<Alert | null>((b, x) => (b === null || stageRank(x.stage) > stageRank(b.stage) ? x : b), null)
          return (
            <article key={a.asset_id} className="card tiercard">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0, fontFamily: 'var(--mono)' }}>{a.asset_id}</h3>
                <span className={`tier t${TIER[a.instrumentation_tier][1]}`} title={TIER_HELP[a.instrumentation_tier]}>{TIER[a.instrumentation_tier]}</span>
                {top ? <span className={`stagechip s-${top.stage ?? 'watch'}`}>{STAGE_LABEL[top.stage ?? 'watch']}</span> : <span className="stagechip none">No alerts</span>}
              </div>
              <p style={{ margin: '8px 0 2px', fontWeight: 600 }}>{a.system}</p>
              <p className="muted small">{a.site} · {a.motor_rated_kw} kW · {a.fluid} · commissioned {a.commissioned_year}</p>
              <p className="muted small">{a.channels_available.length} channels measured · {mine.length} alerts{top ? ` · strongest: ${pretty(top.fault_type)}` : ''}</p>
              <button className="btn sm" onClick={() => onOpen(a.asset_id)}>Open <Icon name="next" /></button>
            </article>
          )
        })}
      </div>
    </section>
  )
}
