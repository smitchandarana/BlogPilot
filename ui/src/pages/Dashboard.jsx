import { useState, useEffect } from 'react'
import { X, AlertTriangle, ScanLine, ThumbsUp, MessageSquare, Eye, Mail, Users, Brain, Layers, Cpu, PlayCircle, Loader2, CheckCircle2, XCircle, RotateCcw, Search, Lightbulb, GitBranch, MessageCircle } from 'lucide-react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useEngine } from '../hooks/useEngine'
import EngineToggle from '../components/EngineToggle'
import BudgetBar from '../components/BudgetBar'
import ActivityFeed from '../components/ActivityFeed'
import PreviewQueue from '../components/PreviewQueue'
import FirstRunWizard from '../components/FirstRunWizard'
import { analytics, engine as engineApi, intelligence as intelligenceApi, research as researchApi, config as configApi } from '../api/client'

const STAT_DEFS = [
  { key: 'posts_scanned', label: 'Posts Scanned', icon: ScanLine, color: 'text-violet-400' },
  { key: 'liked', label: 'Liked', icon: ThumbsUp, color: 'text-emerald-400' },
  { key: 'commented', label: 'Commented', icon: MessageSquare, color: 'text-blue-400' },
  { key: 'profiles_visited', label: 'Profiles Visited', icon: Eye, color: 'text-amber-400' },
  { key: 'emails_found', label: 'Emails Found', icon: Mail, color: 'text-blue-400' },
  { key: 'leads', label: 'Leads', icon: Users, color: 'text-emerald-400' },
]

const BUDGET_LABELS = {
  likes: 'Likes',
  comments: 'Comments',
  connections: 'Connections',
  profile_visits: 'Profile Visits',
  inmails: 'InMails',
  posts_published: 'Posts Published',
}

export default function Dashboard() {
  const { state } = useEngine()
  const { subscribe } = useWebSocket()

  // First-run wizard: skip if localStorage marks it done OR if backend already has keys saved.
  // The backend check handles second launches on new machines / after EXE reinstall.
  const [wizardDone, setWizardDone] = useState(
    () => localStorage.getItem('firstRunComplete') === 'true'
  )

  useEffect(() => {
    if (wizardDone) return
    configApi.setupStatus()
      .then((res) => {
        if (res.data?.complete) {
          localStorage.setItem('firstRunComplete', 'true')
          setWizardDone(true)
        }
      })
      .catch(() => {}) // server may not be up yet — wizard stays visible
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const [stats, setStats] = useState({
    posts_scanned: 0,
    liked: 0,
    commented: 0,
    profiles_visited: 0,
    emails_found: 0,
    leads: 0,
  })

  const [budgets, setBudgets] = useState([])
  const [alert, setAlert] = useState(null)
  const [intelligenceStatus, setIntelligenceStatus] = useState(null)
  const [taskStatus, setTaskStatus] = useState({}) // { [taskId]: 'idle'|'running'|'done'|'error' }
  const [taskResult, setTaskResult] = useState({}) // { [taskId]: string }

  const BG_TASKS = [
    {
      id: 'feed_scan',
      label: 'Feed Scan',
      description: 'Scan LinkedIn feed for new posts',
      icon: Search,
      run: () => engineApi.scanNow(),
      requiresRunning: true,
    },
    {
      id: 'topic_research',
      label: 'Topic Research',
      description: 'Fetch Reddit, RSS & HN snippets',
      icon: ScanLine,
      run: () => researchApi.trigger(),
    },
    {
      id: 'content_extraction',
      label: 'Content Extraction',
      description: 'Extract insights via OpenRouter AI',
      icon: Lightbulb,
      run: async () => {
        const res = await intelligenceApi.extract()
        return `${res.data.insights_created} insights created`
      },
    },
    {
      id: 'topic_rotation',
      label: 'Topic Rotation',
      description: 'Rotate low-performing topics',
      icon: GitBranch,
      run: () => configApi.runIteration(),
    },
    {
      id: 'comment_monitor',
      label: 'Comment Monitor',
      description: 'Check comments for replies',
      icon: MessageCircle,
      run: () => engineApi.runCommentMonitor(),
    },
  ]

  const runTask = async (task) => {
    if (taskStatus[task.id] === 'running') return
    setTaskStatus((p) => ({ ...p, [task.id]: 'running' }))
    setTaskResult((p) => ({ ...p, [task.id]: '' }))
    try {
      const msg = await task.run()
      setTaskStatus((p) => ({ ...p, [task.id]: 'done' }))
      setTaskResult((p) => ({ ...p, [task.id]: typeof msg === 'string' ? msg : 'Done' }))
      setTimeout(() => setTaskStatus((p) => ({ ...p, [task.id]: 'idle' })), 4000)
    } catch (e) {
      const detail = e?.response?.data?.detail || e?.message || 'Failed'
      setTaskStatus((p) => ({ ...p, [task.id]: 'error' }))
      setTaskResult((p) => ({ ...p, [task.id]: detail }))
      setTimeout(() => setTaskStatus((p) => ({ ...p, [task.id]: 'idle' })), 6000)
    }
  }

  // Fetch daily stats + budget on mount, refresh every 30s
  useEffect(() => {
    const load = async () => {
      try {
        const [dailyRes, statusRes] = await Promise.all([
          analytics.daily(),
          engineApi.status(),
        ])
        const d = dailyRes.data
        const actions = d.actions || {}
        setStats({
          posts_scanned: d.posts_scanned ?? 0,
          liked: actions.likes ?? 0,
          commented: actions.comments ?? 0,
          profiles_visited: actions.profile_visits ?? 0,
          emails_found: d.emails_found ?? 0,
          leads: d.leads_total ?? 0,
        })
        const budgetMap = statusRes.data?.budget_used ?? {}
        const rows = Object.entries(BUDGET_LABELS).map(([actionType, label]) => ({
          actionType,
          label,
          count: budgetMap[actionType]?.count ?? 0,
          limit: budgetMap[actionType]?.limit ?? 0,
        }))
        if (rows.length > 0) setBudgets(rows)
      } catch (e) {
        // silently ignore — engine may not be running
      }
    }
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    intelligenceApi.status().then(res => setIntelligenceStatus(res.data)).catch(() => {})
  }, [])

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
    <>
    {!wizardDone && (
      <FirstRunWizard
        onComplete={() => {
          localStorage.setItem('firstRunComplete', 'true')
          setWizardDone(true)
        }}
      />
    )}
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
          {alert.level === 'critical' && (
            <button
              onClick={async () => {
                try {
                  await engineApi.resetCircuitBreaker()
                  setAlert(null)
                } catch {}
              }}
              className="rounded-md border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-300 transition-colors hover:bg-red-500/20"
            >
              Reset Circuit Breaker
            </button>
          )}
          <button
            onClick={() => setAlert(null)}
            className="rounded p-0.5 opacity-60 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-current"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <EngineToggle />

      <PreviewQueue />

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

      {intelligenceStatus && (
        <div className="rounded-xl border border-violet-700/20 bg-violet-950/10 px-4 py-3">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Brain className="h-3.5 w-3.5 text-violet-400" />
              <span className="text-xs font-semibold text-violet-300">Content Intelligence</span>
            </div>
            <div className="flex items-center gap-5 flex-wrap">
              <div className="flex items-center gap-1.5">
                <Layers className="h-3 w-3 text-slate-500" />
                <span className="text-xs tabular-nums text-slate-300">{intelligenceStatus.total_insights}</span>
                <span className="text-[10px] text-slate-600">insights</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Cpu className="h-3 w-3 text-slate-500" />
                <span className="text-xs tabular-nums text-slate-300">{intelligenceStatus.total_patterns}</span>
                <span className="text-[10px] text-slate-600">patterns</span>
              </div>
              {intelligenceStatus.unprocessed_snippets > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
                  <span className="text-[10px] text-amber-400">{intelligenceStatus.unprocessed_snippets} snippets pending extraction</span>
                </div>
              )}
              {intelligenceStatus.last_extraction && (
                <span className="text-[10px] text-slate-600">
                  Last extracted: {new Date(intelligenceStatus.last_extraction).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Background Tasks */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">
          Background Tasks
        </h2>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {BG_TASKS.map((task) => {
            const status = taskStatus[task.id] || 'idle'
            const result = taskResult[task.id] || ''
            const Icon = task.icon
            const disabled = status === 'running' || (task.requiresRunning && state.status !== 'RUNNING')
            return (
              <button
                key={task.id}
                onClick={() => runTask(task)}
                disabled={disabled}
                className={`group relative flex flex-col gap-2 rounded-lg border px-4 py-3 text-left transition-all focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-400
                  ${status === 'done' ? 'border-emerald-500/40 bg-emerald-500/5' :
                    status === 'error' ? 'border-red-500/40 bg-red-500/5' :
                    status === 'running' ? 'border-violet-500/40 bg-violet-500/5' :
                    'border-slate-700/60 bg-slate-800/20 hover:border-slate-600 hover:bg-slate-800/60'}
                  disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                <div className="flex items-center justify-between gap-2">
                  <Icon className={`h-4 w-4 shrink-0
                    ${status === 'done' ? 'text-emerald-400' :
                      status === 'error' ? 'text-red-400' :
                      status === 'running' ? 'text-violet-400' :
                      'text-slate-400 group-hover:text-slate-300'}`}
                  />
                  {status === 'running' ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-violet-400" />
                  ) : status === 'done' ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  ) : status === 'error' ? (
                    <XCircle className="h-3.5 w-3.5 text-red-400" />
                  ) : (
                    <PlayCircle className="h-3.5 w-3.5 text-slate-600 group-hover:text-slate-400 transition-colors" />
                  )}
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-200">{task.label}</p>
                  <p className="mt-0.5 text-[10px] leading-tight text-slate-500">
                    {result && status !== 'idle' ? result : task.description}
                  </p>
                </div>
                {task.requiresRunning && state.status !== 'RUNNING' && (
                  <span className="absolute right-2 top-2 rounded px-1 py-0.5 text-[9px] font-medium bg-slate-700/60 text-slate-500">needs engine</span>
                )}
              </button>
            )
          })}
        </div>
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
    </>
  )
}
