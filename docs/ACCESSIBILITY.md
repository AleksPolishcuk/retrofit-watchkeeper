# Accessibility and ease of use

Watchkeeper is meant to be used by a new operator without training. This note says what was checked, what was changed because of it, and what has **not** been verified. It is not a conformance claim: no formal audit and no testing with assistive-technology users has been done.

## How it was checked

| Check | How | Result |
|---|---|---|
| Automated rules (WCAG 2.0 to 2.2 A and AA, plus best practice) | axe-core 4.14 run in the browser on all five pages, light and dark, and on an open case | **0 violations** after the fixes. Before: color contrast on the count badge (3.7:1) and the green labels (4.35:1), and a skipped heading level on Value. axe reports some text on gradients as "could not be determined"; those pairs are covered by the contrast test below |
| Colour contrast of every token | `web/tests/contrast.test.ts` reads `styles.css` and fails if a text pair is below 4.5:1 or a boundary or focus ring below 3:1, in light and dark | passes; runs in `make test` |
| Keyboard | Tab through the page: a skip button is first, then the menu, then the content; menus open with Enter and close with Escape; every control shows a 3 px focus ring (dark teal on the page, white on the dark menu and headline) | works |
| Reflow | 320 px wide, all pages, light | no horizontal page scroll (tables scroll inside their own box on narrow screens or turn into cards) |
| Text size | text sizes are in `rem` and breakpoints in `em`, so a larger default text size in the browser enlarges the text and switches to the narrow layouts earlier; browser zoom also works | checked by setting the root text size to 200 percent |
| Colour is not the only signal | priority is a word on every chip, machine and instrument have an icon and a label, the donut and the figures list their numbers in text | by design |
| Motion | the pulse and transitions switch off when the system asks for reduced motion | by design |
| Theme | Light is the default whatever the system setting is; a Light, Dark and Auto switch (three toggle buttons) is in the menu, the tablet rail and the phone top bar; Auto follows the system. axe was run again with the switch in place, light and dark | 0 violations |

## What was changed because of the audit

- Focus ring: it was cyan on white (2:1). It is now 3 px dark teal (6:1), and white on dark surfaces.
- Skip button as the first control, focus moves to the page content when the page changes, and the browser tab title names the page.
- Headings: one `h1` per page; the case title is an `h2` and its four steps are `h3` (there were two `h1` and skipped levels).
- Open and Resolved are toggle buttons with `aria-pressed`; the selected case has `aria-current`; the case status is announced politely when it changes.
- Chips and labels are sentence case, not capitals (capitals are harder to read for many people); nothing is set below 12 px; buttons and toggles are 40 to 44 px high.
- Contrast: green, amber, red and blue labels and the count badge were darkened to pass 4.5:1; borders of inputs and menus are 3:1.
- Forced-colors (Windows high contrast) gets plain borders and a visible selection.

## Made simpler for a new person

- The first screen says what to do: how many cases need a look first, with one button to the strongest case.
- Three key figures instead of four, and no jargon in the pump table (no instrumentation level, "Data OK" is quiet, only a problem is highlighted).
- Every case starts with **Do this first**, one sentence with a button to the decision, before the charts.
- A short "What do the priority levels mean?" under the Priority menu.
- A pump with no open case is called "No open cases", never "healthy".

## Not verified, and known limits

- Not tested with a screen reader (VoiceOver, NVDA, TalkBack) by a person, and not tested with voice control or switch access.
- The line charts have a text summary (`aria-label`) but no data table. The small week charts on Overview are decorative: the open cases are listed in the same row.
- Some pixel-sized values remain inside the SVG charts; their text does not follow the browser's default text size.
- The interface is English only.
- A real plant would also need to test glare, gloves and shared screens, and read-aloud of alerts, which a prototype cannot answer.

## Run the audit again

```bash
cd web && npm install --no-save axe-core && mkdir -p public && cp node_modules/axe-core/axe.min.js public/
```

Start `make api` and `make web`, open the page, load `/axe.min.js` in the console and run `axe.run(document)`. Remove `web/public` afterwards. The contrast test needs no browser: `cd web && npm test`.
