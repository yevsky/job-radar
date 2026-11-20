import { useState, type MouseEvent } from 'react'

import type { ApplicationStats } from '@/api/applications'
import type { ApplicationStatus, FunnelStage } from '@/api/enums'
import { pct } from '@/lib/format'
import { useElementWidth } from '@/lib/useElementWidth'
import { statusColor, statusLabel } from '@/lib/labels'

/**
 * Sankey-style funnel drawn by hand in SVG (no chart library).
 * The main band runs along the top from stage to stage; under each stage, smaller bands
 * peel off to where the applications that stopped there are now (waiting, rejected, …).
 */
const NODE = 12
const MAX_BAND = 150
const OUT_GAP = 14

/** Wording for applications still sitting in the stage they stopped at. */
const STILL: Record<FunnelStage, string> = {
  applied: 'waiting',
  screening: 'in screening',
  interview: 'interviewing',
  offer: 'deciding',
  accepted: 'accepted',
}

const outcomeLabel = (stage: FunnelStage, status: ApplicationStatus) =>
  status === stage ? STILL[stage] : statusLabel[status].toLowerCase()

/** A filled band between two vertical segments, with smooth S-curves. */
function band(x0: number, y0a: number, y0b: number, x1: number, y1a: number, y1b: number): string {
  const mx = (x0 + x1) / 2
  return `M${x0},${y0a} C${mx},${y0a} ${mx},${y1a} ${x1},${y1a} L${x1},${y1b} C${mx},${y1b} ${mx},${y0b} ${x0},${y0b} Z`
}

interface Tip {
  x: number
  y: number
  text: string
}

export function FunnelChart({ stats }: { stats: ApplicationStats }) {
  const [tip, setTip] = useState<Tip | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [ref, measured] = useElementWidth<HTMLDivElement>()
  const W = Math.max(640, measured)
  const stages = stats.funnel
  const total = stages[0]?.reached ?? 0
  if (!total) return <p className="muted">No applications sent in this period yet.</p>

  const k = MAX_BAND / total
  const h = (n: number) => (n > 0 ? Math.max(n * k, 3) : 0)
  const xs = stages.map((_, i) => (i / (stages.length - 1)) * (W - NODE))

  const shapes: { id: string; d: string; color: string; text: string }[] = []
  const nodes: { id: string; x: number; y: number; h: number; color: string; text: string }[] = []
  const labels: { x: number; y: number; text: string }[] = []
  let height = MAX_BAND

  stages.forEach((s, i) => {
    const color = statusColor(s.stage)
    nodes.push({
      id: `n-${s.stage}`,
      x: xs[i],
      y: 0,
      h: h(s.reached),
      color,
      text: `${s.reached} reached ${statusLabel[s.stage].toLowerCase()}`,
    })
    const next = stages[i + 1]
    if (!next) return

    if (next.reached > 0) {
      shapes.push({
        id: `f-${s.stage}`,
        d: band(xs[i] + NODE, 0, h(next.reached), xs[i + 1], 0, h(next.reached)),
        color: statusColor(next.stage),
        text: `${next.reached} of ${s.reached} moved on to ${statusLabel[next.stage].toLowerCase()} (${pct(next.reached, s.reached)}%)`,
      })
    }

    // Outcomes peel off below the onward band, and land between this column and the next.
    let sourceY = h(next.reached)
    let targetY = h(s.reached) + 22
    const tx = xs[i] + (xs[i + 1] - xs[i]) * 0.5
    stats.outcomes
      .filter((o) => o.stage === s.stage && o.count > 0)
      .sort((a, b) => (a.status === s.stage ? -1 : b.status === s.stage ? 1 : 0))
      .forEach((o) => {
        const oh = h(o.count)
        const label = `${o.count} ${outcomeLabel(s.stage, o.status)}`
        const oColor = statusColor(o.status === 'applied' ? 'applied' : o.status)
        shapes.push({
          id: `o-${s.stage}-${o.status}`,
          d: band(xs[i] + NODE, sourceY, sourceY + oh, tx, targetY, targetY + oh),
          color: oColor,
          text: `${label} (stopped at ${statusLabel[s.stage].toLowerCase()})`,
        })
        nodes.push({
          id: `on-${s.stage}-${o.status}`,
          x: tx,
          y: targetY,
          h: oh,
          color: oColor,
          text: label,
        })
        labels.push({ x: tx + NODE + 8, y: targetY + oh / 2, text: label })
        sourceY += oh
        targetY += oh + OUT_GAP
        height = Math.max(height, targetY)
      })
  })

  function show(e: MouseEvent, id: string, text: string) {
    const box = (e.currentTarget.closest('.chart-inner') as HTMLElement).getBoundingClientRect()
    setHover(id)
    setTip({ x: e.clientX - box.left, y: e.clientY - box.top, text })
  }
  const hide = () => {
    setHover(null)
    setTip(null)
  }

  return (
    <div className="chart-wrap">
      <div className="chart-inner" ref={ref}>
        <div className="funnel-heads" aria-hidden>
          {stages.map((s, i) => {
            const last = i === stages.length - 1
            const prev = stages[i - 1]
            return (
              <div
                key={s.stage}
                className="funnel-head"
                style={last ? { right: 0, textAlign: 'right' } : { left: `${(xs[i] / W) * 100}%` }}
              >
                <div>{statusLabel[s.stage]}</div>
                <div className="stat-num">{s.reached}</div>
                <div className="small muted">
                  {i === 0
                    ? 'Everything you sent'
                    : s.reached
                      ? `${pct(s.reached, prev.reached)}% of ${statusLabel[prev.stage].toLowerCase()}`
                      : 'None yet'}
                </div>
              </div>
            )
          })}
        </div>
        <svg
          viewBox={`0 0 ${W} ${height + 8}`}
          width={W}
          height={height + 8}
          role="img"
          aria-label={`Funnel: ${stages.map((s) => `${s.reached} ${s.stage}`).join(', ')}`}
        >
          {shapes.map((s) => (
            <path
              key={s.id}
              d={s.d}
              fill={s.color}
              opacity={hover === s.id ? 0.55 : 0.28}
              onMouseMove={(e) => show(e, s.id, s.text)}
              onMouseLeave={hide}
            />
          ))}
          {nodes.map((n) =>
            n.h > 0 ? (
              <rect
                key={n.id}
                x={n.x}
                y={n.y}
                width={NODE}
                height={n.h}
                rx={2}
                fill={n.color}
                onMouseMove={(e) => show(e, n.id, n.text)}
                onMouseLeave={hide}
              />
            ) : (
              <line
                key={n.id}
                x1={n.x}
                x2={n.x + NODE}
                y1={1}
                y2={1}
                stroke="var(--border-strong)"
                strokeWidth={2}
              />
            ),
          )}
          {labels.map((l) => (
            <text
              key={l.text + l.y}
              x={l.x}
              y={l.y}
              dominantBaseline="central"
              fill="var(--text)"
              style={{ font: '400 15px var(--font-sans)' }}
            >
              {l.text}
            </text>
          ))}
        </svg>
        {tip && (
          <div className="chart-tip" style={{ left: tip.x, top: tip.y }}>
            {tip.text}
          </div>
        )}
      </div>
    </div>
  )
}
