import { useState } from 'react'

import type { ApplicationStats } from '@/api/applications'
import { formatShort } from '@/lib/format'
import { useElementWidth } from '@/lib/useElementWidth'

/** Grouped bars per week: offers saved vs applications sent. Hand-drawn SVG. */
const H = 200
const PAD_L = 28
const PAD_B = 26

const SERIES = [
  { key: 'saved', label: 'Saved', color: 'var(--st-offer)' },
  { key: 'applied', label: 'Applied', color: 'var(--st-applied)' },
] as const

/** Bar with 4px rounded top, square at the baseline. */
function bar(x: number, y: number, w: number, h: number): string {
  if (h <= 0) return ''
  const r = Math.min(4, w / 2, h)
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`
}

export function WeeklyLegend() {
  return (
    <div className="legend">
      {SERIES.map((s) => (
        <span key={s.key}>
          <span className="dot" style={{ background: s.color }} />
          {s.label}
        </span>
      ))}
    </div>
  )
}

export function WeeklyChart({ weekly }: { weekly: ApplicationStats['weekly'] }) {
  const [active, setActive] = useState<number | null>(null)
  const [ref, measured] = useElementWidth<HTMLDivElement>()
  const W = Math.max(640, measured)
  if (weekly.length === 0) return <p className="muted">No activity in this period.</p>

  const max = Math.max(1, ...weekly.flatMap((w) => [w.saved, w.applied]))
  const ticks =
    max <= 4 ? Array.from({ length: max + 1 }, (_, i) => i) : [0, Math.round(max / 2), max]
  const plotW = W - PAD_L
  const slot = plotW / weekly.length
  const barW = Math.min(14, (slot - 10) / 2)
  const y = (v: number) => H - PAD_B - (v / max) * (H - PAD_B - 10)
  const every = Math.ceil(weekly.length / 8)

  return (
    <div className="chart-wrap">
      <div className="chart-inner" ref={ref}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width={W}
          height={H}
          role="img"
          aria-label="Offers saved and applications sent per week"
        >
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD_L} x2={W} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeWidth={1} />
              <text
                x={0}
                y={y(t)}
                dominantBaseline="central"
                fill="var(--text-muted)"
                style={{ font: '400 13px var(--font-sans)' }}
              >
                {t}
              </text>
            </g>
          ))}
          {weekly.map((w, i) => {
            const cx = PAD_L + slot * i + slot / 2
            return (
              <g key={w.week_start}>
                <rect
                  x={cx - slot / 2}
                  y={0}
                  width={slot}
                  height={H - PAD_B}
                  fill={active === i ? 'var(--surface-2)' : 'transparent'}
                  onMouseEnter={() => setActive(i)}
                  onMouseLeave={() => setActive(null)}
                />
                {SERIES.map((s, j) => {
                  const v = w[s.key]
                  const x = cx - barW - 1 + j * (barW + 2)
                  return (
                    <path
                      key={s.key}
                      d={bar(x, y(v), barW, H - PAD_B - y(v))}
                      fill={s.color}
                      pointerEvents="none"
                    />
                  )
                })}
                {i % every === 0 && (
                  <text
                    x={cx}
                    y={H - 6}
                    textAnchor="middle"
                    fill="var(--text-muted)"
                    style={{ font: '400 13px var(--font-sans)' }}
                  >
                    {formatShort(`${w.week_start}T12:00:00`)}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
        {active !== null && (
          <div
            className="chart-tip"
            style={{ left: `${((PAD_L + slot * active + slot / 2) / W) * 100}%`, top: 10 }}
          >
            Week of {formatShort(`${weekly[active].week_start}T12:00:00`)}: {weekly[active].saved}{' '}
            saved, {weekly[active].applied} applied
          </div>
        )}
      </div>
    </div>
  )
}
