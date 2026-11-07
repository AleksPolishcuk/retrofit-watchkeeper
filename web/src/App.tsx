import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { Decision } from './decisions'
import Icon from './icons'
import Monitor from './Monitor'
import Proof from './Proof'
import RetrofitPage from './Retrofit'
import Value from './Value'
import type { Alert, Asset, Results } from './types'

const STORE = 'watchkeeper.decisions'
type Route = 'monitor' | 'value' | 'proof' | 'retrofit'

function parseRoute(hash: string): Route {
  const k = hash.replace(/^#\/?/, '').split('/')[0]
  return k === 'value' || k === 'proof' || k === 'retrofit' ? k : 'monitor'
}

function loadDecisions(): Record<string, Decision> {
  try {
    return JSON.parse(localStorage.getItem(STORE) ?? '{}')
  } catch {
    return {}
  }
}

const TABS: { key: Route; label: string; hint: string; hash: string }[] = [
  { key: 'monitor', label: 'Monitor', hint: 'See a pump, the evidence and what to do', hash: '#/' },
  { key: 'value', label: 'Value', hint: 'What it is worth to an operator', hash: '#/value' },
  { key: 'proof', label: 'Proof', hint: 'Does it work, is it safe, where does it fail', hash: '#/proof' },
  { key: 'retrofit', label: 'Retrofit', hint: 'What it needs and how it transfers', hash: '#/retrofit' },
]

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash))
  const [assets, setAssets] = useState<Asset[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [results, setResults] = useState<Results | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [decisions, setDecisions] = useState<Record<string, Decision>>(loadDecisions)

  useEffect(() => {
    const on = () => {
      setRoute(parseRoute(window.location.hash))
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  useEffect(() => {
    api.assets().then(setAssets).catch((e) => setError(`Cannot reach the API: ${e.message}. Start it with "make api".`))
    api.allAlerts().then((r) => setAlerts(r.alerts)).catch(() => undefined)
    api.results().then(setResults).catch(() => undefined)
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

  return (
    <div className="app">
      <header className="top">
        <div className="brand"><span className="mark" aria-hidden="true"><Icon name="shield" /></span>Watchkeeper</div>
        <nav aria-label="Sections">
          {TABS.map((t) => (
            <a key={t.key} href={t.hash} title={t.hint} className={route === t.key ? 'tab on' : 'tab'} aria-current={route === t.key ? 'page' : undefined}>{t.label}</a>
          ))}
        </nav>
        <span className="pill safe" title="This interface only reads data"><Icon name="shield" /> Advice only · it cannot control a machine</span>
      </header>
      <div className="strip">Recorded simulated pumps, replayed as if live. Nothing is connected to a real machine.</div>
      {error && <div className="error" role="alert">{error}</div>}
      <main className="page">
        {route === 'monitor' && <Monitor assets={assets} alerts={alerts} results={results} decisions={decisions} decide={decide} />}
        {route === 'value' && <Value data={results} />}
        {route === 'proof' && <Proof data={results} />}
        {route === 'retrofit' && <RetrofitPage data={results} />}
      </main>
    </div>
  )
}
