import { useState } from 'react'

import type { ApplicationStats } from '@/api/applications'
import { formatShort } from '@/lib/format'
import { useElementWidth } from '@/lib/useElementWidth'

/**
 * One column per week: a wide pale bar for offers saved, a narrow bar inside it for applications
 * sent, and a dot above for replies that came in that week. The current week is outlined.
 * Hand-drawn SVG, like the funnel.
 */
const H = 210
const PAD_L = 28
const PAD_B = 26
const PAD_T = 26

const SAVED_FILL = 'color-mix(in srgb, var(--st-saved) 32%, transparent)'

/** Bar with rounded top corners, square at the baseline. */
function bar(x: number, y: number, w: number, h: number, r = 5): string {
  if (h <= 0) return ''
  const rr = Math.min(r, w / 2, h)
  return `M${x},${y + h} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h} Z`
}

export function WeeklyLegend() {
  return (
    <div className="legend">
      <span>
        <span className="dot" style={{ background: SAVED_FILL, width: 12, height: 12 }} />
        Saved
      </span>
      <span>
        <span className="dot" style={{ background: 'var(--st-applied)', width: 6, height: 12 }} />
        Applied
      </span>
      <span>
        <span className="dot" style={{ background: 'var(--st-screening)', borderRadius: '50%' }} />
        Got a reply
      </span>
    </div>
  )
}

const replies = (n: number) => `${n} ${n === 1 ? 'reply' : 'replies'}`

export function WeeklyChart({ weekly }: { weekly: ApplicationStats['weekly'] }) {
  const [active, setActive] = useState<number | null>(null)
  const [ref, measured] = useElementWidth<HTMLDivElement>()
  const W = Math.max(560, measured)
  if (weekly.length === 0) return <p className="muted">No activity in this period.</p>

  const max = Math.max(1, ...weekly.flatMap((w) => [w.saved, w.applied]))
  const ticks =
    max <= 4 ? Array.from({ length: max + 1 }, (_, i) => i) : [0, Math.round(max / 2), max]
  const plotW = W - PAD_L
  const slot = plotW / weekly.length
  const outerW = Math.min(30, slot - 8)
  const innerW = Math.max(4, Math.round(outerW * 0.45))
  const base = H - PAD_B
  const y = (v: number) => base - (v / max) * (base - PAD_T)
  const every = Math.ceil(weekly.length / 7)
  const last = weekly.length - 1

  return (
    <div className="chart-wrap">
      <div className="chart-inner" ref={ref} style={{ minWidth: 560 }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width={W}
          height={H}
          role="img"
          aria-label="Offers saved, applications sent and replies per week"
        >
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={PAD_L}
                x2={W}
                y1={y(t)}
                y2={y(t)}
                stroke="var(--border)"
                strokeWidth={1}
                strokeDasharray={t === 0 ? undefined : '2 4'}
              />
              <text
                x={0}
                y={y(t)}
                dominantBaseline="central"
                fill="var(--text-faint)"
                style={{ font: '400 12px var(--font-sans)' }}
              >
                {t}
              </text>
            </g>
          ))}
          {weekly.map((w, i) => {
            const cx = PAD_L + slot * i + slot / 2
            const top = y(Math.max(w.saved, w.applied))
            const empty = w.saved === 0 && w.applied === 0
            return (
              <g key={w.week_start}>
                {i === last && (
                  <rect
                    x={cx - slot / 2 + 3}
                    y={4}
                    width={slot - 6}
                    height={base - 2}
                    rx={8}
                    fill="none"
                    stroke="var(--accent)"
                    strokeDasharray="3 3"
                  />
                )}
                <rect
                  x={cx - slot / 2}
                  y={0}
                  width={slot}
                  height={base}
                  fill={active === i ? 'var(--surface-2)' : 'transparent'}
                  onMouseEnter={() => setActive(i)}
                  onMouseLeave={() => setActive(null)}
                />
                {empty ? (
                  <rect
                    x={cx - outerW / 2}
                    y={base - 2}
                    width={outerW}
                    height={2}
                    rx={1}
                    fill="var(--border-strong)"
                    pointerEvents="none"
                  />
                ) : (
                  <>
                    <path
                      d={bar(cx - outerW / 2, y(w.saved), outerW, base - y(w.saved), 6)}
                      fill={SAVED_FILL}
                      pointerEvents="none"
                    />
                    <path
                      d={bar(cx - innerW / 2, y(w.applied), innerW, base - y(w.applied), 3)}
                      fill="var(--st-applied)"
                      pointerEvents="none"
                    />
                  </>
                )}
                {w.replied > 0 && (
                  <g pointerEvents="none">
                    <circle
                      cx={cx}
                      cy={top - 11}
                      r={w.replied > 1 ? 8 : 4.5}
                      fill="var(--st-screening)"
                    />
                    {w.replied > 1 && (
                      <text
                        x={cx}
                        y={top - 11}
                        textAnchor="middle"
                        dominantBaseline="central"
                        fill="#fff"
                        style={{ font: '600 10px var(--font-sans)' }}
                      >
                        {w.replied}
                      </text>
                    )}
                  </g>
                )}
                {(i % every === 0 || i === last) && (
                  <text
                    x={i === last ? cx + slot / 2 - 2 : cx}
                    y={H - 6}
                    textAnchor={i === last ? 'end' : 'middle'}
                    fill={i === last ? 'var(--text)' : 'var(--text-muted)'}
                    style={{ font: `${i === last ? 600 : 400} 12px var(--font-sans)` }}
                  >
                    {i === last ? 'This week' : formatShort(`${w.week_start}T12:00:00`)}
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
            saved, {weekly[active].applied} applied, {replies(weekly[active].replied)}
          </div>
        )}
      </div>
    </div>
  )
}
