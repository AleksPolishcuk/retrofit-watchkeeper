import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import Icon from './icons'

export interface DropdownOption {
  value: string
  label: ReactNode
  /** short plain-text name, for the accessible description */
  text: string
  /** priority dot: a stage key such as "likely" */
  dot?: string
  count?: number
}

interface Props {
  label: string
  options: DropdownOption[]
  selected: string[]
  onChange: (next: string[]) => void
  multiple?: boolean
  /** multiple only: first row that clears the selection, for example "All priorities" */
  allLabel?: string
  allCount?: number
  /** content of the closed button */
  summary: ReactNode
  /** the panel is at least this wide in pixels, even when the button is narrower */
  minPanelWidth?: number
}

/** A styled listbox that replaces the browser's own select. Keyboard: arrows, Home, End, Enter or Space to choose, Escape to close. The panel is drawn in the page body so that no scrolling parent can clip it. */
export default function Dropdown({ label, options, selected, onChange, multiple = false, allLabel, allCount, summary, minPanelWidth = 0 }: Props) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [pos, setPos] = useState<{ top?: number; bottom?: number; left: number; width: number; maxH: number } | null>(null)
  const btn = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLUListElement>(null)
  const id = useId().replace(/:/g, '')
  const rows: DropdownOption[] = multiple && allLabel ? [{ value: '', label: allLabel, text: allLabel, count: allCount }, ...options] : options
  const isSel = (v: string) => (v === '' ? selected.length === 0 : selected.includes(v))

  const place = useCallback(() => {
    const el = btn.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const below = window.innerHeight - r.bottom - 12
    const above = r.top - 12
    const flip = below < 240 && above > below
    const width = Math.min(Math.max(r.width, minPanelWidth), window.innerWidth - 16)
    const left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8))
    setPos(flip
      ? { bottom: window.innerHeight - r.top + 6, left, width, maxH: Math.min(360, above) }
      : { top: r.bottom + 6, left, width, maxH: Math.min(360, below) })
  }, [minPanelWidth])

  useLayoutEffect(() => {
    if (open) place()
  }, [open, place])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (!btn.current?.contains(t) && !list.current?.contains(t)) setOpen(false)
    }
    window.addEventListener('mousedown', onDown)
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      window.removeEventListener('mousedown', onDown)
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [open, place])

  useEffect(() => {
    if (!open) return
    setActive(Math.max(0, rows.findIndex((r) => isSel(r.value))))
    const t = window.setTimeout(() => list.current?.focus(), 0)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (open) document.getElementById(`${id}-o${active}`)?.scrollIntoView({ block: 'nearest' })
  }, [active, open, id])

  const choose = (v: string) => {
    if (!multiple) {
      onChange([v])
      setOpen(false)
      btn.current?.focus()
      return
    }
    if (v === '') onChange([])
    else onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v])
  }

  const onListKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(rows.length - 1, a + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(0, a - 1)) }
    else if (e.key === 'Home') { e.preventDefault(); setActive(0) }
    else if (e.key === 'End') { e.preventDefault(); setActive(rows.length - 1) }
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(rows[active].value) }
    else if (e.key === 'Escape') { e.preventDefault(); setOpen(false); btn.current?.focus() }
    else if (e.key === 'Tab') setOpen(false)
  }

  return (
    <div className="dd">
      <span className="ddlabel" id={`${id}-l`}>{label}</span>
      <button
        ref={btn}
        type="button"
        className="ddbtn"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-labelledby={`${id}-l ${id}-v`}
        onClick={(e) => { if (e.detail === 0 && open) return; setOpen((o) => !o) }}
        onKeyDown={(e) => {
          if (!open) {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); setOpen(true) }
            return
          }
          // keys typed before focus has moved into the open list are handled the same way
          if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' ', 'Escape'].includes(e.key)) onListKey(e)
        }}
      >
        <span className="val" id={`${id}-v`}>{summary}</span>
        <Icon name="chevron" />
      </button>
      {open && pos && createPortal(
        <ul
          ref={list}
          className="ddpanel"
          role="listbox"
          aria-multiselectable={multiple || undefined}
          aria-labelledby={`${id}-l`}
          aria-activedescendant={`${id}-o${active}`}
          tabIndex={-1}
          onKeyDown={onListKey}
          style={{ left: pos.left, width: pos.width, top: pos.top, bottom: pos.bottom, maxHeight: pos.maxH }}
        >
          {rows.map((r, i) => (
            <li key={r.value || 'all'} id={`${id}-o${i}`} role="option" aria-selected={isSel(r.value)} aria-label={r.text}
                className={`ddopt${i === active ? ' active' : ''}${isSel(r.value) ? ' sel' : ''}`}
                onMouseEnter={() => setActive(i)} onClick={() => choose(r.value)}>
              {multiple && <span className={`ddbox${isSel(r.value) ? ' on' : ''}`} aria-hidden="true">{isSel(r.value) && <Icon name="check" />}</span>}
              {r.dot && <i className={`dot2 ${r.dot}`} aria-hidden="true" />}
              <span className="ddtxt">{r.label}</span>
              {r.count !== undefined && <span className="cnt">{r.count}</span>}
              {!multiple && isSel(r.value) && <span className="ddtick" aria-hidden="true"><Icon name="check" /></span>}
            </li>
          ))}
        </ul>,
        document.body,
      )}
    </div>
  )
}
