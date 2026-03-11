import { useState, useEffect } from 'react'
import { X, AlertTriangle, ScanLine, ThumbsUp, MessageSquare, Eye, Mail, Users } from 'lucide-react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useEngine } from '../hooks/useEngine'
import EngineToggle from '../components/EngineToggle'
import BudgetBar from '../components/BudgetBar'
import ActivityFeed from '../components/ActivityFeed'

const STAT_DEFS = [
  { key: 'posts_scanned', label: 'Posts Scanned', icon: ScanLine, color: 'text-violet-400' },
  { key: 'liked', label: 'Liked', icon: ThumbsUp, color: 'text-emerald-400' },
  { key: 'commented', label: 'Commented', icon: MessageSquare, color: 'text-blue-400' },
  { key: 'profiles_visited', label: 'Profiles Visited', icon: Eye, color: 'text-amber-400' },
  { key: 'emails_found', label: 'Emails Found', icon: Mail, color: 'text-pink-400' },
  { key: 'leads', label: 'Leads', icon: Users, color: 'text-cyan-400' },
]

const BUDGET_DEFAULTS = [
  { actionType: 'likes', count: 8, limit: 30, label: 'Likes' },
  { actionType: 'comments', count: 3, limit: 12, label: 'Comments' },
  { actionType: 'connections', count: 5, limit: 15, label: 'Connections' },
  { actionType: 'profile_visits', count: 18, limit: 50, label: 'Profile Visits' },
  { actionType: 'inmails', count: 0, limit: 5, label: 'InMails' },
  { actionType: 'posts_published', count: 1, limit: 5, label: 'Posts Published' },
]

export default function Dashboard() {
  const { state } = useEngine()
  const { subscribe } = useWebSocket()

  const [stats, setStats] = useState({
    posts_scanned: 42,
    liked: 8,
    commented: 3,
    profiles_visited: 18,
    emails_found: 4,
    leads: 7,
  })

  const [budgets, setBudgets] = useState(BUDGET_DEFAULTS)
  const [alert, setAlert] = useState(null)

  useEffect(() => {
    const unsub = subscribe('stats_update', (data) => {
      setStats((prev) => ({ ...prev, ...data }))
    })
    return unsub
  }, [subscribe])

  useEffect(() => {
    const unsub = subscribe('budget_update', (data) => {
      setBudgets((prev) =>
        prev.map((b) =>
          b.actionType === data.action_type ? { ...b, count: data.count, limit: data.limit } : b
        )
      )
    })
    return unsub
  }, [subscribe])

  useEffect(() => {
    const unsub = subscribe('alert', (data) => {
      setAlert(data)
    })
    return unsub
  }, [subscribe])

  const uptimeFmt = () => {
    const s = state.uptime
    if (s < 60) return `${s}s`
    if (s < 3600) return `${Math.floor(s / 60)}m`
    return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-100">Dashboard</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Engine uptime: <span className="text-slate-300">{uptimeFmt()}</span>
          {state.tasksQueued > 0 && (
            <span className="ml-3 text-slate-500">
              {state.tasksQueued} task{state.tasksQueued !== 1 ? 's' : ''} queued
            </span>
          )}
        </p>
      </div>

      {alert && (
        <div
          className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${
            alert.level === 'critical'
              ? 'border-red-500/30 bg-red-500/10 text-red-300'
              : alert.level === 'warning'
                ? 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                : 'border-violet-500/30 bg-violet-500/10 text-violet-300'
          }`}
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span className="flex-1 text-sm">{alert.message}</span>
          <button
            onClick={() => setAlert(null)}
            className="rounded p-0.5 opacity-60 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-current"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <EngineToggle />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {STAT_DEFS.map(({ key, label, icon: Icon, color }) => (
          <div
            key={key}
            className="flex flex-col gap-2 rounded-xl border border-slate-700/60 bg-slate-800/40 px-4 py-3"
          >
            <Icon className={`h-4 w-4 ${color}`} />
            <div>
              <p className="text-2xl font-semibold tabular-nums text-slate-100">{stats[key]}</p>
              <p className="mt-0.5 text-xs text-slate-500">{label}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">
          Daily Budget
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {budgets.map((b) => (
            <BudgetBar key={b.actionType} {...b} />
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">
          Live Activity
        </h2>
        <ActivityFeed />
      </div>
    </div>
  )
}
