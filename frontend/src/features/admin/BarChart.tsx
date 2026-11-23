import type { DayCount } from '@/api/admin'
import { formatShort } from '@/lib/format'

const H = 140
const BAR_GAP = 6
const LABEL_H = 20

/** Small single-series bar chart (hand-drawn SVG, like the dashboard charts). */
export function BarChart({ data, label }: { data: DayCount[]; label: string }) {
  const max = Math.max(1, ...data.map((d) => d.count))
  const width = 100 / Math.max(data.length, 1)
  return (
    <figure className="stack" style={{ margin: 0, gap: 6 }}>
      <svg
        viewBox={`0 0 100 ${H + LABEL_H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={label}
        style={{ width: '100%', height: H + LABEL_H }}
      >
        {data.map((d, i) => {
          const h = (d.count / max) * (H - 14)
          return (
            <g key={d.day}>
              <title>{`${formatShort(d.day)}: ${d.count}`}</title>
              <rect
                x={i * width + BAR_GAP / 10}
                y={H - h}
                width={width - BAR_GAP / 5}
                height={Math.max(h, d.count > 0 ? 1 : 0)}
                rx={0.8}
                fill="var(--st-applied)"
              />
            </g>
          )
        })}
        <line x1={0} x2={100} y1={H} y2={H} stroke="var(--border)" strokeWidth={0.3} />
      </svg>
      <div className="row small muted" style={{ justifyContent: 'space-between' }}>
        <span>{data[0] && formatShort(data[0].day)}</span>
        <span>{data.at(-1) && formatShort(data.at(-1)!.day)}</span>
      </div>
    </figure>
  )
}
