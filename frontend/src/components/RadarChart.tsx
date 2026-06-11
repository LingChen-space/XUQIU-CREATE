import type { SignalSnapshot } from "../types"

const LABELS = ["重复提问", "信息分散", "民间工具", "资格稀缺", "机制复杂", "内容热度"]
const KEYS: (keyof SignalSnapshot)[] = [
  "repeat_question", "info_scatter", "grassroots_tool",
  "scarcity", "mechanism_complexity", "content_heat",
]

const SIZE = 200
const CX = SIZE / 2
const CY = SIZE / 2
const R = 76
const LEVELS = [0.2, 0.4, 0.6, 0.8, 1.0]

function polar(angle: number, radius: number): [number, number] {
  const rad = (angle * Math.PI) / 180 - Math.PI / 2
  return [CX + radius * Math.cos(rad), CY + radius * Math.sin(rad)]
}

export default function RadarChart({ signals }: { signals: SignalSnapshot }) {
  const values = KEYS.map((k) => Math.min(signals[k] || 0, 100) / 100)
  const N = KEYS.length
  const angleStep = 360 / N

  const gridPolygons = LEVELS.map((lvl) => {
    const pts = KEYS.map((_, i) => {
      const [x, y] = polar(i * angleStep, R * lvl)
      return `${x},${y}`
    }).join(" ")
    return <polygon key={lvl} points={pts} fill="none" stroke="#e5e7eb" strokeWidth={0.8} />
  })

  const axes = KEYS.map((_, i) => {
    const [x, y] = polar(i * angleStep, R)
    return <line key={i} x1={CX} y1={CY} x2={x} y2={y} stroke="#e5e7eb" strokeWidth={0.8} />
  })

  const dataPoints = values.map((v, i) => {
    const [x, y] = polar(i * angleStep, R * v)
    return `${x},${y}`
  }).join(" ")

  const labels = KEYS.map((_, i) => {
    const angle = i * angleStep
    const [x, y] = polar(angle, R + 18)
    let anchor: "start" | "middle" | "end" = "middle"
    if (angle === 0 || angle === 360) anchor = "middle"
    else if (angle < 180) anchor = "start"
    else anchor = "end"
    if (angle === 90) anchor = "middle"
    if (angle === 270) anchor = "middle"
    return (
      <text
        key={i}
        x={x}
        y={y}
        textAnchor={anchor}
        dominantBaseline="middle"
        fill="#6b7280"
        fontSize={11}
        fontWeight={500}
      >
        {LABELS[i]}
      </text>
    )
  })

  return (
    <div className="radar-container">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width={SIZE} height={SIZE}>
        {gridPolygons}
        {axes}
        <polygon points={dataPoints} fill="rgba(37,99,235,0.12)" stroke="#2563eb" strokeWidth={1.8} />
        {values.map((v, i) => {
          const [x, y] = polar(i * angleStep, R * v)
          return <circle key={i} cx={x} cy={y} r={3.5} fill="#2563eb" />
        })}
        {labels}
      </svg>
    </div>
  )
}
