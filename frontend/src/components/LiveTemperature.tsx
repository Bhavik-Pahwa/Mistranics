import { useEffect, useRef, useState } from 'react'

type Source = 'physical' | 'simulation'
type Reading = {
  source: Source
  device_id: string
  sequence: number
  timestamp: string
  temperature: number | null
  sample_count: number
  sensor_status: string
  anomaly: {
    status: 'NORMAL' | 'ANOMALY' | 'WARMING_UP' | 'SENSOR_ERROR'
    method: string
    z_score: number | null
    baseline_mean: number | null
    baseline_std: number | null
    baseline_samples: number
  }
}
type Snapshot = {
  type: 'state'
  session_id: string
  revision: number
  source: Source
  mqtt_connected: boolean
  stream_status: 'LIVE' | 'DISCONNECTED' | 'SENSOR_ERROR'
  stale_after_seconds: number
  last_received_at: string | null
  latest: Reading | null
  history: Reading[]
}

const timeLabel = (value: string) => new Date(value).toLocaleTimeString()

export function LiveTemperature() {
  const [state, setState] = useState<Snapshot | null>(null)
  const [connected, setConnected] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [now, setNow] = useState(Date.now)
  const [heartbeat, setHeartbeat] = useState(0)
  const receivedAt = useRef(0)
  const request = useRef<AbortController | null>(null)

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | null = null
    let retry: ReturnType<typeof setTimeout>
    let attempts = 0
    let openedAt = Date.now()
    const connect = () => {
      if (disposed) return
      openedAt = Date.now()
      const url = new URL('/ws/telemetry', window.location.href)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(url)
      socket.onmessage = (event) => {
        if (disposed) return
        try {
          const next = JSON.parse(event.data) as Snapshot
          if (next.type !== 'state' || !Array.isArray(next.history)) throw new Error('Invalid state')
          receivedAt.current = Date.now()
          setHeartbeat(receivedAt.current)
          attempts = 0
          setConnected(true)
          setState((previous) => previous?.session_id === next.session_id && previous.revision > next.revision
            ? previous : next)
        } catch {
          setError('Invalid telemetry response. Reconnecting…')
          socket?.close()
        }
      }
      socket.onerror = () => socket?.close()
      socket.onclose = () => {
        if (disposed) return
        setConnected(false)
        retry = setTimeout(connect, Math.min(1000 * 2 ** attempts++, 10000))
      }
    }
    connect()
    const clock = setInterval(() => {
      const current = Date.now()
      setNow(current)
      // Detect half-open sockets even when the browser hasn't emitted onclose.
      if (current - Math.max(openedAt, receivedAt.current) > 5000 && socket && socket.readyState < 2) {
        setConnected(false)
        socket.close()
      }
    }, 1000)
    return () => {
      disposed = true
      clearTimeout(retry)
      clearInterval(clock)
      request.current?.abort()
      socket?.close()
    }
  }, [])

  async function selectSource(source: Source) {
    if (!state || source === state.source) return
    setPending(true)
    setError('')
    const controller = new AbortController()
    request.current = controller
    const timeout = setTimeout(() => controller.abort(), 8000)
    const session = state.session_id
    try {
      const response = await fetch('/api/source', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source }), signal: controller.signal,
      })
      if (!response.ok) throw new Error(`Source selection failed (${response.status})`)
      const next = await response.json() as Snapshot
      // A slow HTTP response must not overwrite a newer WebSocket/source update.
      setState((previous) => previous && (previous.session_id !== session ||
        (previous.session_id === next.session_id && previous.revision > next.revision)) ? previous : next)
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Source selection failed')
      else setError('Source selection timed out. Check the backend connection.')
    } finally {
      clearTimeout(timeout)
      setPending(false)
    }
  }

  const latest = state?.latest
  const transportLive = connected && now - heartbeat < 5000
  const readingFresh = state?.last_received_at &&
    now - Date.parse(state.last_received_at) < state.stale_after_seconds * 1000 &&
    latest && now - Date.parse(latest.timestamp) < state.stale_after_seconds * 1000
  const stream = transportLive && readingFresh ? state?.stream_status : 'DISCONNECTED'
  const status = stream === 'DISCONNECTED' ? 'DISCONNECTED' : latest?.anomaly.status ?? 'DISCONNECTED'
  const color = status === 'ANOMALY' || status === 'SENSOR_ERROR' ? 'text-rose-700 bg-rose-50' :
    status === 'NORMAL' ? 'text-emerald-700 bg-emerald-50' : 'text-amber-800 bg-amber-50'
  const history = state?.history ?? []
  const values = history.flatMap((p) => p.temperature === null ? [] : [p.temperature])
  const low = values.length ? Math.floor(Math.min(...values) - 1) : 0
  const high = values.length ? Math.ceil(Math.max(...values) + 1) : 1
  const firstTime = history.length ? Date.parse(history[0].timestamp) : 0
  const span = history.length > 1 ? Date.parse(history[history.length - 1].timestamp) - firstTime : 3000
  const points = history.map((reading) => ({
    reading, x: 48 + (Date.parse(reading.timestamp) - firstTime) / Math.max(span, 1) * 540,
    y: reading.temperature === null ? null : 150 - (reading.temperature - low) / (high - low) * 120,
  }))
  const path = points.map((p, index) => {
    if (p.y === null) return ''
    const command = index > 0 && points[index - 1].y !== null ? 'L' : 'M'
    return `${command}${p.x},${p.y}`
  }).join(' ')

  return (
    <section aria-label="Live temperature telemetry" className="apple-card flex h-full min-h-0 flex-col gap-2 overflow-auto rounded-2xl p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-bold text-slate-900">INDUX · Temperature</h2>
        <label className="flex items-center gap-2 text-xs text-slate-600">
          Data source
          <select aria-label="Telemetry data source" disabled={!state || pending}
            value={state?.source ?? 'physical'} onChange={(event) => void selectSource(event.target.value as Source)}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-slate-900 disabled:opacity-50">
            <option value="physical">Physical Sensor</option><option value="simulation">Simulation</option>
          </select>
        </label>
      </div>
      {error && <p role="alert" className="text-xs text-rose-700">{error}</p>}
      {state?.source === 'simulation' && <a href="/simulator" target="_blank" rel="noreferrer" className="text-xs text-blue-700 underline">Open motor simulator ↗</a>}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <strong className="text-2xl text-slate-900" data-testid="temperature-value">
            {latest?.temperature == null ? '—' : latest.temperature.toFixed(2)} °C
          </strong>
          <span className="ml-2 text-xs text-slate-600">{state ? state.source === 'physical' ? 'Physical Sensor' : 'Simulation' : 'Connecting to backend…'}</span>
          <p className="text-[11px] text-slate-500">{latest ? `${latest.device_id} · ${latest.sample_count} samples · ${timeLabel(latest.timestamp)}` : 'Waiting for a completed three-second window'}</p>
        </div>
        <span role="status" className={`rounded-lg px-2 py-1 text-xs font-bold ${color}`}>
          {pending ? 'Switching…' : status.replaceAll('_', ' ')}
        </span>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-600">
        <span>MQTT: {transportLive ? state?.mqtt_connected ? 'Connected' : 'Disconnected' : 'Unknown'}</span>
        <span>Stream: {stream === 'LIVE' ? 'Live' : stream === 'SENSOR_ERROR' ? 'Sensor error' : 'Stale / disconnected'}</span>
        <span>WebSocket: {transportLive ? 'Connected' : 'Disconnected · retrying'}</span>
      </div>
      <div className="relative min-h-[120px] flex-1">
        <svg viewBox="0 0 640 180" className="h-full min-h-[120px] w-full" role="img" aria-label="Temperature in degrees Celsius over time. Red points mark statistical anomalies.">
          <text x="8" y="16" fontSize="10" fill="#475569">°C</text>
          {[0, 0.5, 1].map((fraction) => <g key={fraction}>
            <line x1="48" x2="588" y1={150 - fraction * 120} y2={150 - fraction * 120} stroke="#e2e8f0" />
            <text x="40" y={154 - fraction * 120} fontSize="10" textAnchor="end" fill="#475569">{(low + fraction * (high - low)).toFixed(1)}</text>
          </g>)}
          <path d={path} fill="none" stroke="#2563eb" strokeWidth="2" />
          {points.map(({ reading, x, y }) => y === null ? null : <circle key={reading.sequence} cx={x} cy={y}
            r={reading.anomaly.status === 'ANOMALY' ? 4 : 2.5}
            fill={reading.anomaly.status === 'ANOMALY' ? '#e11d48' : '#2563eb'}>
            <title>{`${timeLabel(reading.timestamp)} · ${reading.temperature?.toFixed(2)} °C · ${reading.anomaly.status.replaceAll('_', ' ')}`}</title>
          </circle>)}
          {points.length > 0 && <>
            <text x="48" y="174" fontSize="10" textAnchor="start" fill="#475569">{timeLabel(points[0].reading.timestamp)}</text>
            {points.length > 1 && <text x="588" y="174" fontSize="10" textAnchor="end" fill="#475569">{timeLabel(points[points.length - 1].reading.timestamp)}</text>}
          </>}
        </svg>
        {history.length === 0 && <p className="absolute inset-0 flex items-center justify-center text-xs text-slate-500">No telemetry for the selected source</p>}
      </div>
      <p className="text-[11px] text-slate-600">STATISTICAL_Z_SCORE · Baseline: {latest?.anomaly.baseline_samples ?? 0} previous windows
        {latest?.anomaly.z_score != null && ` · Z: ${latest.anomaly.z_score.toFixed(2)} · Mean: ${latest.anomaly.baseline_mean?.toFixed(2)} °C · Std: ${latest.anomaly.baseline_std?.toFixed(2)} °C`}
      </p>
      {status === 'ANOMALY' && <p className="text-xs font-semibold text-rose-700">Statistical anomaly at {latest && timeLabel(latest.timestamp)}. A deviation is not a confirmed mechanical fault.</p>}
    </section>
  )
}
