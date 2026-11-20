import { useEffect, useRef, useState } from 'react'

/** Width of an element in CSS pixels, so SVG charts draw at 1:1 and text keeps its real size. */
export function useElementWidth<T extends HTMLElement>(fallback = 800) {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}
