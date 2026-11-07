import { useMemo } from 'react'
import { headline, pretty, STAGE_LABEL, stageRank, when } from './stage'
import type { Alert, Asset } from './types'

const TIER: Record<string, string> = { T0_LEGACY: 'T0', T1_RETROFIT: 'T1', T2_FULL: 'T2' }

interface Row {
  asset: Asset
  alerts: Alert[]
  incidents: number
  top: Alert | null
  last: string | null
}

interface Props {
  assets: Asset[]
  alerts: Alert[]
  onOpen: (id: string) => void
}

export default function Fleet({ assets, alerts, onOpen }: Props) {
  const rows: Row[] = useMemo(() => {
    const out = assets.map((asset) => {
      const mine = alerts.filter((a) => a.asset_id === asset.asset_id)
      const top = mine.reduce<Alert | null>((best, a) => (best === null || stageRank(a.stage) > stageRank(best.stage) ? a : best), null)
      return {
        asset,
        alerts: mine,
        incidents: new Set(mine.map((a) => a.incident_id ?? a.alert_id)).size,
        top,
        last: mine.length ? mine.map((a) => a.alert_time_utc).sort().slice(-1)[0] : null,
      }
    })
    return out.sort((a, b) => stageRank(b.top?.stage) - stageRank(a.top?.stage) || (b.last ?? '').localeCompare(a.last ?? ''))
  }, [assets, alerts])

  const machine = alerts.filter((a) => a.event_class === 'MACHINE').length
  const instrument = alerts.length - machine
  const served = rows.filter((r) => r.alerts.length > 0).length

  return (
    <section className="fleet" aria-label="Fleet overview">
      <h1>Fleet overview</h1>
      <p className="muted lead">
        {assets.length} cooling-water pumps, {served} with alerts: {machine} machine and {instrument} instrument. Advice only: nothing here can start, stop or change a pump.
      </p>
      <div className="tablewrap">
        <table className="fleettable">
          <thead>
            <tr><th>Pump</th><th>System</th><th>Instrumentation</th><th>Status</th><th>Incidents</th><th>Alerts</th><th>Latest</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.asset.asset_id} onClick={() => onOpen(r.asset.asset_id)}>
                <td><button className="linkish" onClick={() => onOpen(r.asset.asset_id)}>{r.asset.asset_id}</button></td>
                <td className="muted">{r.asset.system}</td>
                <td><span className={`tier t${TIER[r.asset.instrumentation_tier][1]}`}>{TIER[r.asset.instrumentation_tier]}</span></td>
                <td>
                  {r.top ? (
                    <span className="statuscell">
                      <span className={`stagechip s-${r.top.stage ?? 'watch'}`}>{STAGE_LABEL[r.top.stage ?? 'watch']}</span>
                      <span>{headline(r.top)}: {pretty(r.top.fault_type)}</span>
                    </span>
                  ) : (
                    <span className="muted">{r.asset.split === 'test' ? 'no alerts exported for this pump' : 'no alerts'}</span>
                  )}
                </td>
                <td className="num">{r.incidents}</td>
                <td className="num">{r.alerts.length}</td>
                <td className="muted">{r.last ? when(r.last) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Alerts for the nine public pumps come from a model that was not trained on them. The status word is the strongest level reached; open a pump to see the
        evidence and what limits our certainty.
      </p>
    </section>
  )
}
