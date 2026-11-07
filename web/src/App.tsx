import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import Alerts from './Alerts'
import Dashboard from './Dashboard'
import type { Decision } from './decisions'
import Icon from './icons'
import PumpPage from './PumpPage'
import Pumps from './Pumps'
import ResultsPage from './Results'
import RetrofitPage from './Retrofit'
import { stageRank } from './stage'
import type { Alert, Asset, Results } from './types'

const STORE = 'watchkeeper.decisions'
const THEME_KEY = 'watchkeeper.theme'
const THEMES = ['day', 'dusk', 'night'] as const
type Theme = (typeof THEMES)[number]
type Route = { name: 'dashboard' } | { name: 'pumps' } | { name: 'alerts' } | { name: 'pump'; id: string; alertId?: string } | { name: 'results' } | { name: 'retrofit' }

function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/')
  if (parts[0] === 'pump' && parts[1]) return { name: 'pump', id: decodeURIComponent(parts[1]), alertId: parts[2] ? decodeURIComponent(parts[2]) : undefined }
  if (parts[0] === 'pumps') return { name: 'pumps' }
  if (parts[0] === 'alerts') return { name: 'alerts' }
  if (parts[0] === 'results') return { name: 'results' }
  if (parts[0] === 'retrofit') return { name: 'retrofit' }
  return { name: 'dashboard' }
}

function loadDecisions(): Record<string, Decision> {
  try {
    return JSON.parse(localStorage.getItem(STORE) ?? '{}')
  } catch {
    return {}
  }
}

function loadTheme(): Theme {
  try {
    const t = localStorage.getItem(THEME_KEY)
    if (t && (THEMES as readonly string[]).includes(t)) return t as Theme
  } catch {
    /* storage may be unavailable */
  }
  return 'day'
}

const NAV: { key: Route['name']; label: string; hash: string; icon: string }[] = [
  { key: 'dashboard', label: 'Dashboard', hash: '#/', icon: 'home' },
  { key: 'pumps', label: 'Pumps', hash: '#/pumps', icon: 'pump' },
  { key: 'alerts', label: 'Alerts', hash: '#/alerts', icon: 'bell' },
  { key: 'results', label: 'Results', hash: '#/results', icon: 'chart' },
  { key: 'retrofit', label: 'Retrofit', hash: '#/retrofit', icon: 'plug' },
]
const TITLE: Record<Route['name'], [string, string]> = {
  dashboard: ['Pump monitoring', 'Early detection, with the evidence and what limits it'],
  pumps: ['Pumps', 'What is measured on each pump'],
  alerts: ['Alerts', 'Strongest first; every one says what to check'],
  pump: ['Pump detail', 'What is going on, why we think so, what to do'],
  results: ['Measured results', 'On simulated pumps, with the limits stated'],
  retrofit: ['Retrofit', 'What it needs and what it never touches'],
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash))
  const [theme, setTheme] = useState<Theme>(loadTheme)
  const [assets, setAssets] = useState<Asset[]>([])
  const [fleetAlerts, setFleetAlerts] = useState<Alert[]>([])
  const [results, setResults] = useState<Results | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [decisions, setDecisions] = useState<Record<string, Decision>>(loadDecisions)

  useEffect(() => {
    const on = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      /* the theme still applies for this visit */
    }
  }, [theme])

  useEffect(() => {
    api.assets().then(setAssets).catch((e) => setError(`Cannot reach the API: ${e.message}. Start it with "make api".`))
    api.allAlerts().then((r) => setFleetAlerts(r.alerts)).catch(() => undefined)
    api.results().then(setResults).catch(() => undefined)
  }, [])

  const go = useCallback((hash: string) => {
    window.location.hash = hash
    window.scrollTo(0, 0)
  }, [])

  const decide = useCallback((id: string, d: Decision | undefined) => {
    setDecisions((prev) => {
      const next = { ...prev }
      if (d) next[id] = d
      else delete next[id]
      try {
        localStorage.setItem(STORE, JSON.stringify(next))
      } catch {
        /* storage may be unavailable; the decision stays in memory */
      }
      return next
    })
  }, [])

  const openPump = (id: string, alertId?: string) => go(`#/pump/${encodeURIComponent(id)}${alertId ? '/' + encodeURIComponent(alertId) : ''}`)
  const urgent = fleetAlerts.filter((a) => stageRank(a.stage) >= 2 && !decisions[a.alert_id]).length
  const activeKey: Route['name'] = route.name
  const [title, sub] = TITLE[route.name]

  return (
    <div className="shell">
      <aside className="sidebar" aria-label="Main">
        <div className="brand"><span className="mark" aria-hidden="true"><Icon name="shield" /></span>Watchkeeper</div>
        <nav className="sidenav" aria-label="Sections">
          {NAV.map((n) => (
            <a key={n.key} href={n.hash} className={activeKey === n.key || (n.key === 'pumps' && route.name === 'pump') ? 'on' : ''} aria-current={activeKey === n.key ? 'page' : undefined}>
              <Icon name={n.icon} /> {n.label}
              {n.key === 'alerts' && urgent > 0 && <span className="badge-n" title="active alerts at Likely or above">{urgent}</span>}
            </a>
          ))}
        </nav>
        <div className="sidefoot">
          <b><span className="dot-live" aria-hidden="true" /> Synthetic data</b>
          <p>Recorded pumps replayed from the organizers' simulator. Nothing here is live and nothing is connected to a machine.</p>
        </div>
      </aside>

      <div className="content">
        <header className="topbar">
          <div className="ttl"><b>{title}</b><span>{sub}</span></div>
          <span className="pill sim">Recorded replay</span>
          <span className="pill safe" title="This interface only reads data"><Icon name="shield" /> Advice only · no write path</span>
          <label>
            <span className="sr">Colour theme</span>
            <select value={theme} onChange={(e) => setTheme(e.target.value as Theme)} aria-label="Colour theme">
              <option value="day">Day</option>
              <option value="dusk">Dusk</option>
              <option value="night">Night watch</option>
            </select>
          </label>
        </header>

        {error && <div className="error" role="alert">{error}</div>}

        <main className="page">
          {route.name === 'dashboard' && <Dashboard assets={assets} alerts={fleetAlerts} results={results} onOpen={openPump} />}
          {route.name === 'pumps' && <Pumps assets={assets} alerts={fleetAlerts} onOpen={(id) => openPump(id)} />}
          {route.name === 'alerts' && <Alerts alerts={fleetAlerts} decisions={decisions} onOpen={(a) => openPump(a.asset_id, a.alert_id)} />}
          {route.name === 'results' && <ResultsPage data={results} />}
          {route.name === 'retrofit' && <RetrofitPage data={results} />}
          {route.name === 'pump' && <PumpPage assets={assets} assetId={route.id} alertId={route.alertId} decisions={decisions} decide={decide} setError={setError} go={go} />}
        </main>
      </div>

      <nav className="bottomnav" aria-label="Sections">
        {NAV.map((n) => (
          <a key={n.key} href={n.hash} className={activeKey === n.key || (n.key === 'pumps' && route.name === 'pump') ? 'on' : ''}>
            <Icon name={n.icon} />{n.label}
            {n.key === 'alerts' && urgent > 0 && <span className="badge-n">{urgent}</span>}
          </a>
        ))}
      </nav>
    </div>
  )
}
