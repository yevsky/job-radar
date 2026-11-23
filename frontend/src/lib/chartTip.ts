import type { CSSProperties } from 'react'

const UP = 'calc(-100% - 10px)'

/**
 * Where a chart tooltip sits above a point, as inline styles for `.chart-tip`. In the middle it
 * is centred on the point. Near an edge it hangs inwards from the point and never past the
 * chart's edge, so it isn't cut off and doesn't make the chart scroll sideways (a bar can sit
 * right at the edge, e.g. "Accepted" in the funnel).
 *
 * `fraction` is the point's position across the chart, 0 (left) to 1 (right).
 */
export function tipPosition(fraction: number): CSSProperties {
  const f = Math.min(1, Math.max(0, fraction))
  if (f < 0.2) return { left: `max(0px, calc(${f * 100}% - 16px))`, transform: `translateY(${UP})` }
  if (f > 0.8)
    return { right: `max(0px, calc(${(1 - f) * 100}% - 16px))`, transform: `translateY(${UP})` }
  return { left: `${f * 100}%`, transform: `translate(-50%, ${UP})` }
}
