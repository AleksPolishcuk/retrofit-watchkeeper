import { useEffect, useRef, useState } from 'react'

/** Width of an element in pixels, kept up to date. Charts use it as their drawing width so that text is drawn at its real size on every screen. */
export function useWidth<T extends HTMLElement>(initial = 640) {
  const ref = useRef<T>(null)
  const [w, setW] = useState(initial)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => setW(Math.max(240, Math.round(el.clientWidth)))
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, w] as const
}
