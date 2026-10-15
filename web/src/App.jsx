import React, { useEffect, useState } from 'react'
import { api, store, fmtSecs, pct, labelText } from './api.js'
import { TrendChart, Histogram, ScoreBar } from './charts.jsx'

const Pill = ({ label }) => <span className={`pill ${label}`}>{labelText[label] || label}</span>
const short = (e) => e.split('@')[0]

function Login({ onKey }) {
  const [v, setV] = useState('')
  return (
    <div className="wrap">
      <div className="card login">
        <div className="logo">drift<span>line</span></div>
        <p className="muted">Paste your project API key to open the dashboard.</p>
        <input value={v} onChange={e => setV(e.target.value)} placeholder="dl_..." autoFocus
               onKeyDown={e => e.key === 'Enter' && v && onKey(v.trim())} />
        <button className="btn" disabled={!v} onClick={() => onKey(v.trim())}>Open</button>{' '}
        <button className="btn ghost" onClick={() => onKey('dl_demo_key')}>Use demo key</button>
      </div>
    </div>
  )
}

function Flags({ flags }) {
  if (!flags?.length) return <div className="empty">No flags. Control looks real.</div>
  return flags.map(f => (
    <div className="flag" key={f.code}>
      <div className={`dot ${f.severity}`} />
      <div><b>{f.title}</b><span>{f.detail}</span></div>
    </div>
  ))
}

function Overview({ k, days, open }) {
  const [d, setD] = useState(null), [dg, setDg] = useState(null), [err, setErr] = useState('')
  useEffect(() => {
    setD(null)
    Promise.all([api(`/v1/overview?days=${days}`, k), api(`/v1/digest?days=7`, k)])
      .then(([o, g]) => { setD(o); setDg(g) }).catch(e => setErr(e.message))
  }, [k, days])
  if (err) return <div className="err">{err}</div>
  if (!d) return <div className="empty">Loading…</div>
  if (!d.org.n) return <div className="card empty">No approvals yet. Check the Setup tab to send your first event.</div>
  const o = d.org
  return (
    <>
      <div className="grid g4">
        <div className="card kpi">
          <h3>Org trust score</h3>
          <div className="score-big"><span className={`v c-${o.label}`}>{Math.round(o.score)}</span><span className="of">/ 100</span></div>
          <Pill label={o.label} />
        </div>
        <div className="card kpi"><h3>Approvals</h3><div className="v">{o.n.toLocaleString()}</div><div className="l">last {days} days</div></div>
        <div className="card kpi"><h3>Median decision</h3><div className="v">{fmtSecs(o.median_seconds)}</div><div className="l">time from shown to decided</div></div>
        <div className="card kpi"><h3>Reject rate</h3><div className="v">{pct(o.reject_rate)}</div><div className="l">{d.flagged_count} approver{d.flagged_count === 1 ? '' : 's'} flagged</div></div>
      </div>

      <div className="grid g2 mt">
        <div className="card"><h3>Trust score, 7-day rolling</h3><TrendChart points={d.trend} /></div>
        <div className="card"><h3>Weekly digest</h3><pre className="digest">{dg?.text}</pre></div>
      </div>

      <div className="card mt">
        <h3>Approvers, worst first</h3>
        <table>
          <thead><tr><th>Approver</th><th>Status</th><th className="num">Score</th><th className="num">Actions</th>
            <th className="num">Median</th><th className="num">Rejected</th><th>Flags</th></tr></thead>
          <tbody>
            {d.approvers.map(a => (
              <tr className="click" key={a.approver} onClick={() => open(a.approver)}>
                <td>{a.approver}</td>
                <td><Pill label={a.label} /></td>
                <td className="num">{a.score != null ? Math.round(a.score) : '–'}</td>
                <td className="num">{a.n}</td>
                <td className="num">{fmtSecs(a.median_seconds)}</td>
                <td className="num">{pct(a.reject_rate)}</td>
                <td className="muted">{a.flags.map(f => f.title).join(' · ') || '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function Detail({ k, name, days, back }) {
  const [d, setD] = useState(null), [err, setErr] = useState('')
  useEffect(() => { setD(null); api(`/v1/approvers/${encodeURIComponent(name)}?days=${days}`, k).then(setD).catch(e => setErr(e.message)) }, [k, name, days])
  if (err) return <div className="err">{err}</div>
  if (!d) return <div className="empty">Loading…</div>
  const c = d.components
  return (
    <>
      <button className="link" onClick={back}>← All approvers</button>
      <div className="grid g2e mt">
        <div className="card">
          <h3>{d.approver}</h3>
          <div className="score-big"><span className={`v c-${d.label}`}>{Math.round(d.score)}</span><span className="of">/ 100</span>&nbsp;<Pill label={d.label} /></div>
          <div className="mt">
            <ScoreBar label="Review speed" value={c.speed} max={40} />
            <ScoreBar label="Rejects" value={c.rejects} max={30} />
            <ScoreBar label="Risk sensitivity" value={c.risk_sensitivity} max={30} />
          </div>
          <div className="muted">{d.n} actions · median {fmtSecs(d.median_seconds)} · p90 {fmtSecs(d.p90_seconds)} · {pct(d.reject_rate)} rejected</div>
        </div>
        <div className="card"><h3>Flags</h3><Flags flags={d.flags} /></div>
      </div>
      <div className="grid g2e mt">
        <div className="card"><h3>Trust score, 7-day rolling</h3><TrendChart points={d.trend} /></div>
        <div className="card"><h3>How long they take</h3><Histogram data={d.histogram} />
          <div className="muted">Median by risk: {Object.entries(d.median_by_risk).map(([r, s]) => `${r} ${fmtSecs(s)}`).join(' · ')}</div>
        </div>
      </div>
      <div className="card mt">
        <h3>Latest decisions</h3>
        <table>
          <thead><tr><th>When</th><th>Action</th><th>Risk</th><th>Decision</th><th className="num">Time</th></tr></thead>
          <tbody>{d.recent.map((e, i) => (
            <tr key={i}>
              <td className="muted">{new Date(e.ts * 1000).toLocaleString()}</td>
              <td className="mono">{e.action}{e.amount ? ` · $${e.amount.toLocaleString()}` : ''}</td>
              <td>{e.risk_name}</td><td>{e.decision}</td><td className="num">{fmtSecs(e.seconds)}</td>
            </tr>))}</tbody>
        </table>
      </div>
    </>
  )
}

function Setup({ k }) {
  const base = location.origin
  return (
    <div className="card">
      <h3>Send approvals from your app</h3>
      <p className="muted">Drop this into your existing approval step. It never blocks or throws in your flow.</p>
      <pre className="code">{`pip install ./sdk   # or copy driftline/__init__.py

import driftline
dl = driftline.Client(api_key="${k}", base_url="${base}")

review = dl.present(approver="maria@acme.com", action="wire_transfer",
                    risk="critical", amount=50_000)   # when the human sees it
...
review.approve()   # or review.reject(reason="wrong payee")`}</pre>
      <p className="muted mt">No SDK? Plain HTTP:</p>
      <pre className="code">{`curl -X POST ${base}/v1/approvals \\
  -H "X-Driftline-Key: ${k}" -H "Content-Type: application/json" \\
  -d '{"approver":"maria@acme.com","action":"wire_transfer","risk":"critical",
       "decision":"approve","shown_at":"2026-10-15T10:00:00Z","decided_at":"2026-10-15T10:00:02Z"}'`}</pre>
    </div>
  )
}

export default function App() {
  const [k, setK] = useState(store.get())
  const [tab, setTab] = useState('overview')
  const [who, setWho] = useState(null)
  const [days, setDays] = useState(30)
  if (!k) return <Login onKey={v => { store.set(v); setK(v) }} />
  const logout = () => { store.clear(); setK('') }
  return (
    <div className="wrap">
      <header className="top">
        <div className="logo">drift<span>line</span></div>
        <nav>
          <button className={tab === 'overview' ? 'on' : ''} onClick={() => { setTab('overview'); setWho(null) }}>Approval health</button>
          <button className={tab === 'setup' ? 'on' : ''} onClick={() => setTab('setup')}>Setup</button>
        </nav>
        <div className="spacer" />
        {tab === 'overview' && <div className="seg">{[7, 30, 60].map(n =>
          <button key={n} className={days === n ? 'on' : ''} onClick={() => setDays(n)}>{n}d</button>)}</div>}
        <button className="link" onClick={logout}>Sign out</button>
      </header>
      {tab === 'setup' ? <Setup k={k} />
        : who ? <Detail k={k} name={who} days={days} back={() => setWho(null)} />
        : <Overview k={k} days={days} open={setWho} />}
    </div>
  )
}
