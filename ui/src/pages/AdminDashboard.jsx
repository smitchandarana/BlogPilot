import { useState, useEffect } from 'react'
import { admin } from '../api/platform'
import {
  Users, Server, Cpu, HardDrive, Activity,
  RefreshCw, Pause, Play, Trash2, Loader2,
  CheckCircle2, XCircle, AlertTriangle,
} from 'lucide-react'

const STATUS_STYLE = {
  running: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  stopped: 'bg-slate-700/60 text-slate-400 border-slate-600/30',
  error: 'bg-red-500/15 text-red-400 border-red-500/20',
  starting: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  created: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
}

const HEALTH_ICON = {
  healthy: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
  unhealthy: <XCircle className="h-3.5 w-3.5 text-red-400" />,
  unknown: <AlertTriangle className="h-3.5 w-3.5 text-slate-500" />,
}

export default function AdminDashboard() {
  const [users, setUsers] = useState([])
  const [system, setSystem] = useState(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState({})

  const load = async () => {
    try {
      const [usersRes, systemRes] = await Promise.all([
        admin.users(),
        admin.system(),
      ])
      setUsers(usersRes.data)
      setSystem(systemRes.data)
    } catch (e) {
      console.error('Admin load failed:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 15000)
    return () => clearInterval(interval)
  }, [])

  const doAction = async (userId, action, fn) => {
    setActionLoading(p => ({ ...p, [`${userId}-${action}`]: true }))
    try {
      await fn()
      await load()
    } catch (e) {
      alert(e.response?.data?.detail || 'Action failed')
    } finally {
      setActionLoading(p => ({ ...p, [`${userId}-${action}`]: false }))
    }
  }

  const isLoading = (userId, action) => actionLoading[`${userId}-${action}`]

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-violet-400" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Admin Dashboard</h1>
          <p className="mt-0.5 text-sm text-slate-500">Manage users, containers, and system resources</p>
        </div>
        <button onClick={load} className="flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition">
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </button>
      </div>

      {/* System Stats */}
      {system && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          <StatCard icon={Users} label="Users" value={system.users} color="text-violet-400" />
          <StatCard icon={Server} label="Containers Running" value={`${system.containers_running}/${system.max_containers}`} color="text-emerald-400" />
          <StatCard icon={Server} label="Total Containers" value={system.containers_total} color="text-blue-400" />
          <StatCard icon={Cpu} label="CPU" value={`${system.cpu_percent}%`} color="text-amber-400" />
          <StatCard icon={Activity} label="RAM Used" value={`${system.memory.used_gb}/${system.memory.total_gb} GB`} color="text-red-400" />
          <StatCard icon={HardDrive} label="Disk" value={`${system.disk.used_gb}/${system.disk.total_gb} GB`} color="text-slate-400" />
        </div>
      )}

      {/* RAM Warning */}
      {system && system.memory.percent > 80 && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-300">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          RAM usage at {system.memory.percent}% — consider stopping idle containers
        </div>
      )}

      {/* Users Table */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-700/60">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Users & Containers</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700/40 text-left text-xs text-slate-500">
                <th className="px-5 py-2.5 font-medium">User</th>
                <th className="px-5 py-2.5 font-medium">Role</th>
                <th className="px-5 py-2.5 font-medium">Subscription</th>
                <th className="px-5 py-2.5 font-medium">Container</th>
                <th className="px-5 py-2.5 font-medium">Health</th>
                <th className="px-5 py-2.5 font-medium">Engine</th>
                <th className="px-5 py-2.5 font-medium">Restarts</th>
                <th className="px-5 py-2.5 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => {
                const c = u.container
                return (
                  <tr key={u.id} className="border-b border-slate-700/20 hover:bg-slate-800/30 transition">
                    <td className="px-5 py-3">
                      <div className="text-slate-200 font-medium">{u.name || '—'}</div>
                      <div className="text-xs text-slate-500">{u.email}</div>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`text-xs font-medium ${u.role === 'admin' ? 'text-violet-400' : 'text-slate-400'}`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${
                        u.subscription_status === 'active' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' :
                        u.subscription_status === 'suspended' ? 'bg-red-500/15 text-red-400 border-red-500/20' :
                        'bg-slate-700/60 text-slate-400 border-slate-600/30'
                      }`}>
                        {u.subscription_status}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      {c ? (
                        <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[c.status] || STATUS_STYLE.stopped}`}>
                          {c.status}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-600">none</span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      {c ? HEALTH_ICON[c.health_status] || HEALTH_ICON.unknown : '—'}
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-400">
                      {c?.engine_state || '—'}
                    </td>
                    <td className="px-5 py-3 text-xs tabular-nums text-slate-400">
                      {c?.restart_count ?? '—'}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1">
                        {c && c.status === 'running' && (
                          <ActionBtn
                            icon={Pause} tip="Stop"
                            loading={isLoading(u.id, 'suspend')}
                            onClick={() => doAction(u.id, 'suspend', () => admin.suspend(u.id))}
                          />
                        )}
                        {u.subscription_status === 'suspended' && (
                          <ActionBtn
                            icon={Play} tip="Unsuspend"
                            loading={isLoading(u.id, 'unsuspend')}
                            onClick={() => doAction(u.id, 'unsuspend', () => admin.unsuspend(u.id))}
                          />
                        )}
                        {c && (
                          <ActionBtn
                            icon={RefreshCw} tip="Restart container"
                            loading={isLoading(u.id, 'restart')}
                            onClick={() => doAction(u.id, 'restart', () => admin.restartContainer(c.id || u.id))}
                          />
                        )}
                        {u.role !== 'admin' && (
                          <ActionBtn
                            icon={Trash2} tip="Delete user"
                            loading={isLoading(u.id, 'delete')}
                            danger
                            onClick={() => {
                              if (confirm(`Delete user ${u.email} and all their data?`)) {
                                doAction(u.id, 'delete', () => admin.deleteUser(u.id))
                              }
                            }}
                          />
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
              {users.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-5 py-8 text-center text-sm text-slate-500">No users yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-slate-700/60 bg-slate-800/40 px-4 py-3">
      <Icon className={`h-4 w-4 ${color}`} />
      <div>
        <p className="text-xl font-semibold tabular-nums text-slate-100">{value}</p>
        <p className="mt-0.5 text-xs text-slate-500">{label}</p>
      </div>
    </div>
  )
}

function ActionBtn({ icon: Icon, tip, onClick, loading, danger }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      title={tip}
      className={`rounded-md p-1.5 transition-colors ${
        danger
          ? 'text-red-400/60 hover:bg-red-500/10 hover:text-red-400'
          : 'text-slate-500 hover:bg-slate-700 hover:text-slate-300'
      } disabled:opacity-40`}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
    </button>
  )
}
