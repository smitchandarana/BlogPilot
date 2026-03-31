import { useState, useEffect, useRef } from 'react'
import { ThumbsUp, MessageSquare, UserPlus, Eye, Mail, SkipForward } from 'lucide-react'
import { useWebSocket } from '../hooks/useWebSocket'
import { analytics } from '../api/client'

const ACTION_ICONS = {
  like: ThumbsUp,
  likes: ThumbsUp,
  comment: MessageSquare,
  comments: MessageSquare,
  connect: UserPlus,
  connections: UserPlus,
  visit: Eye,
  profile_visits: Eye,
  enrich: Mail,
  email_enrichment: Mail,
}

const RESULT_STYLES = {
  SUCCESS: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20',
  FAILED: 'bg-red-500/15 text-red-400 border border-red-500/20',
  SKIPPED: 'bg-slate-700/60 text-slate-400 border border-slate-600/30',
}

function timeAgo(ts) {
  const diff = Date.now() - new Date(ts).getTime()
  if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  return `${Math.floor(diff / 3600000)}h ago`
}

export default function ActivityFeed() {
  const [activities, setActivities] = useState([])
  const bottomRef = useRef(null)
  const { subscribe } = useWebSocket()

  // Load real history on mount
  useEffect(() => {
    analytics.recentActivity().then((res) => {
      setActivities(res.data.map((e) => ({ ...e, _ts: e.ts })))
    }).catch(() => {})
  }, [])

  useEffect(() => {
    const unsub = subscribe('activity', (data) => {
      setActivities((prev) => {
        const next = [
          ...prev,
          { id: Date.now(), action: data.action, target: data.target, result: data.result, _ts: new Date().toISOString() },
        ]
        return next.slice(-50)
      })
    })
    return unsub
  }, [subscribe])

  useEffect(() => {
    const container = bottomRef.current?.parentElement?.parentElement
    if (container) container.scrollTop = container.scrollHeight
  }, [activities])

  return (
    <div className="flex h-72 flex-col overflow-y-auto rounded-xl border border-slate-700/60 bg-slate-900/40 p-1">
      {activities.length === 0 && (
        <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
          No activity yet. Start the engine to begin.
        </div>
      )}
      <div className="flex flex-col gap-0.5">
        {activities.map((item) => {
          const Icon = ACTION_ICONS[item.action] || SkipForward
          return (
            <div
              key={item.id}
              className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors duration-150 hover:bg-slate-800/60"
            >
              <Icon className="h-3.5 w-3.5 shrink-0 text-slate-500" />
              <span className="flex-1 truncate text-sm text-slate-300">{item.target}</span>
              <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${RESULT_STYLES[item.result]}`}>
                {item.result}
              </span>
              <span className="w-16 text-right text-xs text-slate-500 tabular-nums">{timeAgo(item._ts)}</span>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
