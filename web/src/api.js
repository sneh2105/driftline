const KEY = 'driftline_key'

export const store = {
  get() { try { return localStorage.getItem(KEY) || '' } catch { return '' } },
  set(v) { try { localStorage.setItem(KEY, v) } catch {} },
  clear() { try { localStorage.removeItem(KEY) } catch {} },
}

export async function api(path, key) {
  const r = await fetch(path, { headers: { 'X-Driftline-Key': key } })
  if (r.status === 401) throw Object.assign(new Error('Invalid API key'), { auth: true })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

export const fmtSecs = (s) => {
  if (s == null) return '–'
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)}s`
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}
export const pct = (x) => (x == null ? '–' : `${(x * 100).toFixed(1)}%`)
export const labelText = { healthy: 'Healthy', watch: 'Watch', rubber_stamp: 'Rubber-stamping', no_data: 'No data' }
