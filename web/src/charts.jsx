import React from 'react'

const W = 640, H = 200, PAD = { l: 34, r: 10, t: 10, b: 22 }

// Trend line of 0-100 scores with healthy/watch bands. null scores break the line.
export function TrendChart({ points }) {
  const pts = points || []
  if (pts.filter(p => p.score != null).length < 2) return <div className="empty">Not enough data yet</div>
  const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b
  const x = i => PAD.l + (i / Math.max(1, pts.length - 1)) * iw
  const y = v => PAD.t + (1 - v / 100) * ih
  let d = '', pen = false
  pts.forEach((p, i) => {
    if (p.score == null) { pen = false; return }
    d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.score).toFixed(1)}`
    pen = true
  })
  const tick = (i) => new Date(pts[i].ts * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const last = [...pts].reverse().find(p => p.score != null)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Trust score over time">
      <rect x={PAD.l} y={y(100)} width={iw} height={y(70) - y(100)} fill="var(--good-bg)" opacity=".6" />
      <rect x={PAD.l} y={y(40)} width={iw} height={y(0) - y(40)} fill="var(--bad-bg)" opacity=".6" />
      {[0, 25, 50, 75, 100].map(v => (
        <g key={v}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} stroke="var(--grid)" />
          <text x={PAD.l - 6} y={y(v) + 4} textAnchor="end">{v}</text>
        </g>
      ))}
      {[0, Math.floor(pts.length / 2), pts.length - 1].map(i => (
        <text key={i} x={x(i)} y={H - 6} textAnchor={i === 0 ? 'start' : i === pts.length - 1 ? 'end' : 'middle'}>{tick(i)}</text>
      ))}
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      {last && <circle cx={x(pts.indexOf(last))} cy={y(last.score)} r="4" fill="var(--accent)" />}
    </svg>
  )
}

export function Histogram({ data }) {
  const max = Math.max(1, ...data.map(d => d.count))
  const bw = 80, gap = 14, h = 120
  const w = data.length * (bw + gap)
  return (
    <svg viewBox={`0 -16 ${w} ${h + 50}`} width="100%" role="img" aria-label="Decision time distribution">
      {data.map((d, i) => {
        const bh = (d.count / max) * h
        const warn = i < 2
        return (
          <g key={d.bucket} transform={`translate(${i * (bw + gap)},0)`}>
            <rect x="0" y={h - bh} width={bw} height={bh} rx="3" fill={warn ? 'var(--bad)' : 'var(--accent)'} opacity={warn ? .85 : .75} />
            <text x={bw / 2} y={h - bh - 5} textAnchor="middle">{d.count || ''}</text>
            <text x={bw / 2} y={h + 16} textAnchor="middle">{d.bucket}</text>
          </g>
        )
      })}
    </svg>
  )
}

export function ScoreBar({ value, max, label }) {
  return (
    <div className="comp">
      <span>{label}</span>
      <div className="bar"><i style={{ width: `${(value / max) * 100}%` }} /></div>
      <span className="mono" style={{ textAlign: 'right' }}>{value}/{max}</span>
    </div>
  )
}
