import { useState, useEffect, useRef } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { engine as engineApi } from '../api/client'
import { Activity, ScrollText, Circle } from 'lucide-react'

// ── Runtime event level styles ────────────────────────────────────────────
const LEVEL_STYLES = {
  info:    'text-slate-300',
  success: 'text-emerald-400',
  warning: 'text-amber-400',
  error:   'text-red-400',
}
const LEVEL_DOT = {
  info:    'bg-slate-500',
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
  error:   'bg-red-500',
}

// ── Log level styles ──────────────────────────────────────────────────────
const LOG_LEVEL_STYLES = {
  DEBUG:    'text-slate-600',
  INFO:     'text-slate-400',
  WARNING:  'text-amber-400',
  ERROR:    'text-red-400',
  CRITICAL: 'text-red-300 font-semibold',
}
const LOG_LEVEL_BADGE = {
  DEBUG:    'text-slate-600',
  INFO:     'text-blue-500',
  WARNING:  'text-amber-500',
  ERROR:    'text-red-500',
  CRITICAL: 'text-red-400',
}

function timeNow() {
  const d = new Date()
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function shortModule(mod) {
  if (!mod) return ''
  const parts = mod.split('.')
  return parts[parts.length - 1]
}

// ── Runtime Events pane ───────────────────────────────────────────────────
function RuntimeEvents() {
  const [events, setEvents] = useState([])
  const bottomRef = useRef(null)
  const { subscribe } = useWebSocket()

  useEffect(() => {
    const unsub = subscribe('runtime_event', (data) => {
      setEvents((prev) => {
        const next = [
          ...prev,
          {
            id: Date.now() + Math.random(),
            message: data.message || '',
            level: data.level || 'info',
            ts: timeNow(),
          },
        ]
        return next.slice(-200)
      })
    })
    return unsub
  }, [subscribe])

  // Also capture activity events as runtime events
  useEffect(() => {
    const unsub = subscribe('activity', (data) => {
      const result = data.result || ''
      const level = result === 'SUCCESS' ? 'success' : result === 'FAILED' ? 'error' : 'info'
      const action = (data.action || '').replace('_', ' ').toLowerCase()
      setEvents((prev) => {
        const next = [
          ...prev,
          {
            id: Date.now() + Math.random(),
            message: `${action} → ${data.target || ''} [${result}]`,
            level,
            ts: timeNow(),
          },
        ]
        return next.slice(-200)
      })
    })
    return unsub
  }, [subscribe])

  useEffect(() => {
    const container = bottomRef.current?.parentElement
    if (container) container.scrollTop = container.scrollHeight
  }, [events])

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b border-slate-700/60 px-3 py-2">
        <Activity className="h-3.5 w-3.5 text-violet-400" />
        <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">
          Runtime Events
        </span>
        {events.length > 0 && (
          <span className="ml-auto text-[10px] text-slate-600">{events.length} events</span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-1 font-mono text-xs">
        {events.length === 0 ? (
          <div className="flex h-full items-center justify-center text-slate-600">
            Waiting for engine activity…
          </div>
        ) : (
          events.map((ev) => (
            <div key={ev.id} className="flex items-start gap-2 py-0.5">
              <span className="mt-1.5 shrink-0">
                <span className={`inline-block h-1.5 w-1.5 rounded-full ${LEVEL_DOT[ev.level] || LEVEL_DOT.info}`} />
              </span>
              <span className="w-[72px] shrink-0 text-slate-600">{ev.ts}</span>
              <span className={`flex-1 ${LEVEL_STYLES[ev.level] || LEVEL_STYLES.info}`}>
                {ev.message}
              </span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── Log pane ──────────────────────────────────────────────────────────────
function LogPane() {
  const [lines, setLines] = useState([])
  const [autoScroll, setAutoScroll] = useState(true)
  const bottomRef = useRef(null)
  const containerRef = useRef(null)

  const fetchLogs = async () => {
    try {
      const res = await engineApi.logs(150)
      setLines(Array.isArray(res.data) ? res.data : [])
    } catch {
      // ignore — server may not be up
    }
  }

  useEffect(() => {
    fetchLogs()
    const interval = setInterval(fetchLogs, 3000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [lines, autoScroll])

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    setAutoScroll(atBottom)
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden border-t border-slate-700/60">
      <div className="flex items-center gap-2 border-b border-slate-700/60 px-3 py-2">
        <ScrollText className="h-3.5 w-3.5 text-slate-500" />
        <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">
          Engine Log
        </span>
        {!autoScroll && (
          <button
            onClick={() => { setAutoScroll(true); if (containerRef.current) containerRef.current.scrollTop = containerRef.current.scrollHeight }}
            className="ml-auto text-[10px] text-violet-400 hover:text-violet-300"
          >
            ↓ Jump to bottom
          </button>
        )}
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-2 py-1 font-mono text-[11px]"
      >
        {lines.length === 0 ? (
          <div className="flex h-full items-center justify-center text-slate-600">
            No log entries yet
          </div>
        ) : (
          lines.map((line, i) => (
            <div key={i} className="flex items-start gap-2 py-[1px] hover:bg-slate-800/30">
              <span className="w-[62px] shrink-0 text-slate-700">
                {line.ts ? line.ts.substring(11, 19) : ''}
              </span>
              <span className={`w-14 shrink-0 font-semibold ${LOG_LEVEL_BADGE[line.level] || LOG_LEVEL_BADGE.INFO}`}>
                {line.level}
              </span>
              <span className="w-28 shrink-0 truncate text-slate-600">
                {shortModule(line.module)}
              </span>
              <span className={`flex-1 break-all ${LOG_LEVEL_STYLES[line.level] || LOG_LEVEL_STYLES.INFO}`}>
                {line.message}
              </span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────
export default function EngineRuntimePanel() {
  return (
    <div className="flex h-[480px] flex-col overflow-hidden rounded-xl border border-slate-700/60 bg-slate-900/60">
      {/* Top 45%: runtime events */}
      <div className="flex h-[200px] flex-col overflow-hidden">
        <RuntimeEvents />
      </div>
      {/* Bottom 55%: log */}
      <div className="flex flex-[1] flex-col overflow-hidden">
        <LogPane />
      </div>
    </div>
  )
}
