import { useCallback, useEffect, useRef, useState } from 'react'
import { SNAPSHOT, api } from './api'
import type { Decision } from './decisions'
import { headline } from './cases'
import { incidentsOf } from './plain'
import { STORE as REVIEW_STORE, apply, load as loadReviews, migrateDecisions, save as saveReviews } from './reviews'
import type { Action, Review } from './reviews'
import Icon from './icons'
import ThemeSwitch from './ThemeSwitch'
import Monitor from './Monitor'
import Overview from './Overview'
import Proof from './Proof'
import RetrofitPage from './Retrofit'
import Value from './Value'
import type { Alert, Asset, Results } from './types'
import type { Incident } from './plain'

const STORE = 'watchkeeper.decisions'
type Route = 'overview' | 'alerts' | 'value' | 'proof' | 'retrofit'
interface Parsed { key: Route; param: string | null }

/** `#/alerts/PUMP-04` filters the alerts to one pump, `#/alerts/PUMP-04-INC02` opens one case. `#/monitor` is the old name of the alerts page. */
function parseRoute(hash: string): Parsed {
  const parts = hash.replace(/^#\/?/, '').split('/')
  const rest = parts.slice(1).join('/')
  let param: string | null = null
  try {
    param = rest ? decodeURIComponent(rest) : null
  } catch {
    param = null
  }
  const k = parts[0]
  if (k === 'alerts' || k === 'monitor') return { key: 'alerts', param }
  if (k === 'value' || k === 'proof' || k === 'retrofit') return { key: k, param: null }
  return { key: 'overview', param: null }
}

function loadOldDecisions(): Record<string, Decision> {
  try {
    return JSON.parse(localStorage.getItem(STORE) ?? '{}')
  } catch {
    return {}
  }
}

const TABS: { key: Route; label: string; hint: string; hash: string; icon: string }[] = [
  { key: 'overview', label: 'Overview', hint: 'What needs a look first', hash: '#/', icon: 'home' },
  { key: 'alerts', label: 'Alerts', hint: 'Open a case: the data, the evidence, what to do', hash: '#/alerts', icon: 'bell' },
  { key: 'value', label: 'Value', hint: 'What it is worth to an operator', hash: '#/value', icon: 'chart' },
  { key: 'proof', label: 'Proof', hint: 'Does it work, is it safe, where does it fail', hash: '#/proof', icon: 'shield' },
  { key: 'retrofit', label: 'Retrofit', hint: 'What it needs and how it transfers', hash: '#/retrofit', icon: 'plug' },
]

export default function App() {
  const [route, setRoute] = useState<Parsed>(() => parseRoute(window.location.hash))
  const [assets, setAssets] = useState<Asset[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [alertSource, setAlertSource] = useState<'engine' | 'mock' | null>(null)
  const [results, setResults] = useState<Results | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reviews, setReviews] = useState<Record<string, Review>>(loadReviews)
  const mainRef = useRef<HTMLElement>(null)
  const first = useRef(true)

  useEffect(() => {
    const on = () => {
      setRoute(parseRoute(window.location.hash))
      window.scrollTo(0, 0)
      // a new page starts at the top of the content, so a keyboard or screen-reader user is not left in the menu
      window.requestAnimationFrame(() => mainRef.current?.focus({ preventScroll: true }))
    }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  useEffect(() => {
    api.assets().then(setAssets).catch((e) => setError(`Cannot reach the API: ${e.message}. Start it with "make api".`))
    api.allAlerts().then((r) => { setAlerts(r.alerts); setAlertSource(r.source) }).catch(() => undefined)
    api.results().then(setResults).catch(() => undefined)
  }, [])

  // decisions kept by earlier builds (one per alert) become reviews once, so nothing a person marked is lost
  useEffect(() => {
    if (alerts.length === 0 || localStorage.getItem(REVIEW_STORE) !== null) return
    const old = loadOldDecisions()
    if (Object.keys(old).length === 0) return
    const migrated = migrateDecisions(old, incidentsOf(alerts), new Date().toISOString())
    setReviews((prev) => {
      const merged = { ...migrated, ...prev } // a case already opened in this session keeps its newer record
      saveReviews(merged)
      return merged
    })
  }, [alerts])

  const act = useCallback((inc: Incident, action: Action) => {
    setReviews((prev) => {
      const next = apply(prev[inc.id], inc, action, new Date().toISOString())
      if (next === prev[inc.id]) return prev
      const all = { ...prev, [inc.id]: next }
      saveReviews(all)
      return all
    })
  }, [])

  const clearReviews = useCallback(() => {
    setReviews({})
    saveReviews({})
  }, [])

  const pageName = TABS.find((t) => t.key === route.key)?.label ?? 'Overview'
  useEffect(() => {
    document.title = `${pageName} · Watchkeeper`
    first.current = false
  }, [pageName])

  const urgent = headline(incidentsOf(alerts), reviews).urgent
  const link = (t: (typeof TABS)[number], cls: string) => (
    <a key={t.key} href={t.hash} title={t.hint} className={`${cls}${route.key === t.key ? ' on' : ''}`} aria-current={route.key === t.key ? 'page' : undefined}>
      <Icon name={t.icon} />
      <span>{t.label}</span>
      {t.key === 'alerts' && urgent > 0 && <b className="badge" aria-label={`${urgent} cases need a look first`}>{urgent}</b>}
    </a>
  )
  const tab = (k: Route) => TABS.find((t) => t.key === k)!
  const crumb = TABS.find((t) => t.key === route.key)

  return (
    <div className="app">
      <button className="skip" onClick={() => mainRef.current?.focus()}>Skip to the main content</button>
      <aside className="side" aria-label="Watchkeeper menu">
        <a className="brand" href="#/"><span className="mark" aria-hidden="true"><Icon name="shield" /></span><span className="bn"><b>Watch<i>keeper</i></b><small>Pump monitoring</small></span></a>
        <p className="navlabel">Monitoring</p>
        <nav className="sidenav" aria-label="Monitoring">{(['overview', 'alerts'] as Route[]).map((k) => link(tab(k), 'sl'))}</nav>
        <p className="navlabel">Evidence</p>
        <nav className="sidenav" aria-label="Evidence">{(['value', 'proof', 'retrofit'] as Route[]).map((k) => link(tab(k), 'sl'))}</nav>
        <div className="sidefoot">
          <b><i className="rdot" aria-hidden="true" />Replay mode</b>
          <small>Recorded simulated data, replayed as if live</small>
        </div>
      </aside>
      <header className="mtop">
        <a className="brand" href="#/"><span className="mark" aria-hidden="true"><Icon name="shield" /></span><span className="bn"><b>Watch<i>keeper</i></b></span></a>
        <ThemeSwitch compact onDark />
      </header>
      <main className="page" id="main" ref={mainRef} tabIndex={-1} aria-label={pageName}>
        <p className="sr" role="status" aria-live="polite">{pageName}</p>
        <div className="topbar">
          <p className="crumb"><b>{crumb?.label}</b><span>{crumb?.hint}</span></p>
          <div className="chips">
            <span className="chip"><i className="rdot" aria-hidden="true" />Replay mode</span>
            <span className="chip safe" title="This interface only reads data"><Icon name="shield" />Advice only · cannot control a machine</span>
            <ThemeSwitch compact />
          </div>
        </div>
        {error && <div className="error" role="alert">{error}</div>}
        {(route.key === 'overview' || route.key === 'alerts') && alertSource === 'mock' && (
          <p className="alertwarn" role="alert"><b>These are demo alerts, not engine output.</b> The alert files are missing, so there are no priority levels. Run <code>make alerts</code> (or pull the committed <code>artifacts/alerts</code>), restart the API and reload.</p>
        )}
        {(route.key === 'overview' || route.key === 'alerts') && alertSource === 'engine' && alerts.some((x) => !x.stage) && (
          <p className="alertwarn" role="alert"><b>Some alert files are from an older engine version and have no priority level.</b> They are listed as Watch. Run <code>make alerts</code>, restart the API and reload.</p>
        )}
        {route.key === 'overview' && <Overview assets={assets} alerts={alerts} reviews={reviews} />}
        {route.key === 'alerts' && <Monitor assets={assets} alerts={alerts} focus={route.param} results={results} reviews={reviews} act={act} clearReviews={clearReviews} />}
        {route.key === 'value' && <Value data={results} />}
        {route.key === 'proof' && <Proof data={results} />}
        {route.key === 'retrofit' && <RetrofitPage data={results} />}
        <footer className="legal">
          Data: "RETROFIT AI 2026 synthetic pump benchmark, Since AI Hackathon 2026" (CC BY 4.0). Simulated pumps; nothing here is field evidence and nothing is connected to a machine.
          {SNAPSHOT ? ' This page is a static snapshot of the read-only API; the live replay needs a running server.' : ''}
        </footer>
      </main>
      <nav className="tabbar" aria-label="Sections">{TABS.map((t) => link(t, 'tb'))}</nav>
    </div>
  )
}
