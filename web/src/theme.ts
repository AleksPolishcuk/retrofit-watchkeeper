// Light is the default. The person can choose Dark, or Auto to follow the system. The choice is kept in this browser only.
export type Theme = 'light' | 'dark' | 'auto'
export const THEME_STORE = 'watchkeeper.theme'
export const THEMES: { key: Theme; label: string; hint: string; icon: string }[] = [
  { key: 'light', label: 'Light', hint: 'Light theme', icon: 'sun' },
  { key: 'dark', label: 'Dark', hint: 'Dark theme', icon: 'moon' },
  { key: 'auto', label: 'Auto', hint: 'Match the system setting', icon: 'half' },
]

export function loadTheme(): Theme {
  try {
    const v = localStorage.getItem(THEME_STORE)
    return v === 'dark' || v === 'auto' ? v : 'light'
  } catch {
    return 'light'
  }
}

export function applyTheme(t: Theme): void {
  document.documentElement.dataset.theme = t
  window.dispatchEvent(new Event('wk-theme')) // the switch appears in the menu, the rail and the phone bar: keep them in step
  try {
    localStorage.setItem(THEME_STORE, t)
  } catch {
    /* storage may be unavailable; the choice then lasts for this visit only */
  }
}
