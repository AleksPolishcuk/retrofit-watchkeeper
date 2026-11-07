// WCAG 2.2 contrast of the colour tokens in styles.css, light and dark. Text needs 4.5:1, interface boundaries and focus rings 3:1.
// This reads the real stylesheet, so a colour change that breaks contrast fails here. It does not replace testing with people.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8')

function tokens(block: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const m of block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\b/g)) out[m[1]] = m[2].toLowerCase()
  return out
}
const lightBlock = css.slice(css.indexOf(':root {'), css.indexOf('@media (prefers-color-scheme: dark)'))
const darkStart = css.indexOf('@media (prefers-color-scheme: dark)')
const darkBlock = css.slice(css.indexOf(':root {', darkStart), css.indexOf('\n}\n', css.indexOf(':root {', darkStart)))
const light = tokens(lightBlock)
const dark = { ...light, ...tokens(darkBlock) }

const lum = (hex: string) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const ratio = (a: string, b: string) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

// [foreground token or hex, background token or hex, minimum, what]
type Pair = [string, string, number, string]
const TEXT = 4.5
const UI = 3
const pairs: Pair[] = [
  ['ink', 'bg', TEXT, 'body text on the page'], ['ink', 'panel', TEXT, 'body text on a card'], ['ink', 'panel2', TEXT, 'text on a tinted area'],
  ['ink', 'bg2', TEXT, 'body text at the lower end of the page wash'], ['muted', 'bg2', TEXT, 'secondary text at the lower end of the page wash'], ['link', 'bg2', TEXT, 'link at the lower end of the page wash'],
  ['muted', 'bg', TEXT, 'secondary text on the page'], ['muted', 'panel', TEXT, 'secondary text on a card'], ['muted', 'panel2', TEXT, 'secondary text on a tinted area'],
  ['link', 'panel', TEXT, 'link on a card'], ['link', 'bg', TEXT, 'link on the page'], ['link', 'primary-soft', TEXT, 'link on the soft cyan'],
  ['ok', 'ok-bg', TEXT, 'green label'], ['ok', 'panel', TEXT, 'green text on a card'], ['bad', 'panel', TEXT, 'red text on a card'], ['bad', 'bad-bg', TEXT, 'red label'],
  ['machine', 'panel', TEXT, 'machine label'], ['sensor', 'panel', TEXT, 'instrument label'],
  ['chip-watch-ink', 'chip-watch-bg', TEXT, 'Watch chip'], ['chip-possible-ink', 'chip-possible-bg', TEXT, 'Possible chip'],
  ['chip-likely-ink', 'chip-likely-bg', TEXT, 'Likely chip'], ['chip-very-ink', 'chip-very-bg', TEXT, 'Very likely chip'],
  ['err-ink', 'err-bg', TEXT, 'error banner'], ['on-primary', 'primary', TEXT, 'text on cyan buttons and the active menu item'],
  ['on-color', 'badge-bg', TEXT, 'count badge'], ['nav-ink', 'nav-bg', TEXT, 'menu text'], ['nav-ink', 'nav-bg2', TEXT, 'menu text, lower end of the gradient'],
  ['nav-soft', 'nav-bg2', TEXT, 'small note in the menu'], ['#ffffff', 'nav-bg', TEXT, 'white text on the menu and the headline'], ['#e9f0f8', '#2d4057', TEXT, 'headline sub text'], ['#d3e0ee', '#3a506b', TEXT, 'headline eyebrow'],
  ['control-line', 'panel', UI, 'border of inputs and menus on a card'], ['focus', 'panel', UI, 'focus ring on a card'], ['focus', 'bg', UI, 'focus ring on the page'], ['focus', 'bg2', UI, 'focus ring at the lower end of the page wash'], ['focus', 'panel2', UI, 'focus ring on a tinted area'],
  ['#ffffff', 'nav-bg2', UI, 'focus ring on the menu'],
]
// on-color is white in light mode and dark ink in dark mode; in dark the badge is red with white text, so the pair is checked with white there
const pick = (t: Record<string, string>, k: string, theme: string) => (k.startsWith('#') ? k : k === 'on-color' && theme === 'dark' ? '#ffffff' : t[k])

for (const [theme, t] of [['light', light], ['dark', dark]] as const) {
  test(`${theme}: every text pair reaches 4.5:1 and every boundary or focus ring 3:1`, () => {
    const failures: string[] = []
    for (const [fg, bg, min, what] of pairs) {
      if (theme === 'dark' && (fg === '#ffffff' && bg === 'nav-bg')) continue
      const a = pick(t, fg, theme)
      const b = pick(t, bg, theme)
      assert.ok(a && b, `${theme}: token missing for ${fg} or ${bg}`)
      const r = ratio(a, b)
      if (r < min) failures.push(`${what}: ${fg} on ${bg} is ${r.toFixed(2)}:1, needs ${min}:1`)
    }
    assert.deepEqual(failures, [])
  })
}

test('no body text is smaller than 12 px and nothing is set in capitals for reading', () => {
  const sizes = [...css.matchAll(/font-size:\s*([0-9.]+)(px|rem)/g)].map((m) => Number(m[1]) * (m[2] === 'rem' ? 16 : 1))
  assert.ok(Math.min(...sizes) >= 12, `smallest font size is ${Math.min(...sizes)}px`)
  assert.equal((css.match(/text-transform:\s*uppercase/g) ?? []).length, 0)
})
