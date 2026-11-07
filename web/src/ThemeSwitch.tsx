import { useEffect, useState } from 'react'
import Icon from './icons'
import { THEMES, applyTheme, loadTheme } from './theme'
import type { Theme } from './theme'

/** Light, Dark or Auto. Three toggle buttons; the pressed one is the current choice. */
export default function ThemeSwitch({ compact = false, onDark = false }: { compact?: boolean; onDark?: boolean }) {
  const [theme, setTheme] = useState<Theme>(() => (document.documentElement.dataset.theme as Theme) || loadTheme())
  useEffect(() => {
    const sync = () => setTheme((document.documentElement.dataset.theme as Theme) || 'light')
    window.addEventListener('wk-theme', sync)
    return () => window.removeEventListener('wk-theme', sync)
  }, [])
  const pick = (t: Theme) => {
    applyTheme(t)
    setTheme(t)
  }
  return (
    <div className={`themesw${compact ? ' compact' : ''}${onDark ? ' ondark' : ''}`} role="group" aria-label="Colour theme">
      {THEMES.map((t) => (
        <button key={t.key} type="button" aria-pressed={theme === t.key} title={t.hint} aria-label={compact ? t.hint : undefined} className={theme === t.key ? 'on' : ''} onClick={() => pick(t.key)}>
          <Icon name={t.icon} />
          <span>{t.label}</span>
        </button>
      ))}
    </div>
  )
}
