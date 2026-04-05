import { useState, useEffect, useRef } from 'react'
import { admin, platformHealth } from '../api/platform'
import {
  Users, Server, Cpu, HardDrive, Activity,
  RefreshCw, Pause, Play, Trash2, Loader2,
  CheckCircle2, XCircle, AlertTriangle, Plus,
  Shield, Ban, Eye, EyeOff, Clock, FileText,
  RotateCcw, Key, UserCog, Wifi, WifiOff,
} from 'lucide-react'

// ── Style maps ────────────────────────────────────────────────────────────

const CONTAINER_STATUS_STYLE = {
  running:  'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  stopped:  'bg-slate-700/60 text-slate-400 border-slate-600/30',
  stopping: 'bg-slate-700/60 text-slate-400 border-slate-600/30',
  error:    'bg-red-500/15 text-red-400 border-red-500/20',
  starting: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  created:  'bg-blue-500/15 text-blue-400 border-blue-500/20',
}

const SUB_STATUS_STYLE = {
  active:    'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  pending:   'bg-amber-500/15 text-amber-400 border-amber-500/20',
  suspended: 'bg-red-500/15 text-red-400 border-red-500/20',
  cancelled: 'bg-slate-700/60 text-slate-400 border-slate-600/30',
  past_due:  'bg-orange-500/15 text-orange-400 border-orange-500/20',
}

const ROLE_STYLE = {
  admin:     'bg-violet-500/15 text-violet-400 border-violet-500/20',
  superuser: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  user:      'bg-slate-700/60 text-slate-400 border-slate-600/30',
}

const ROLE_CYCLE = { user: 'superuser', superuser: 'admin', admin: 'user' }

const HEALTH_ICON = {
  healthy:   <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
  unhealthy: <XCircle className="h-3.5 w-3.5 text-red-400" />,
  unknown:   <AlertTriangle className="h-3.5 w-3.5 text-slate-500" />,
}

// ── Utilities ─────────────────────────────────────────────────────────────

function timeAgo(isoString) {
  if (!isoString) return 'Never'
  const diff = (Date.now() - new Date(isoString).getTime()) / 1000
  if (diff < 60) return 'Just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function Badge({ text, styleClass }) {
  return (
    <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${styleClass}`}>
      {text}
    </span>
  )
}

function ActionBtn({ icon: Icon, tip, onClick, loading, danger, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      title={tip}
      className={`rounded-md p-1.5 transition-colors ${
        danger
          ? 'text-red-400/60 hover:bg-red-500/10 hover:text-red-400'
          : 'text-slate-500 hover:bg-slate-700 hover:text-slate-300'
      } disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      {loading
        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
        : <Icon className="h-3.5 w-3.5" />
      }
    </button>
  )
}

function StatCard({ icon: Icon, label, value, color, badge }) {
  return (
    <div className="relative flex flex-col gap-2 rounded-xl border border-slate-700/60 bg-slate-800/40 px-4 py-3">
      <Icon className={`h-4 w-4 ${color}`} />
      <div>
        <p className="text-xl font-semibold tabular-nums text-slate-100">{value}</p>
        <p className="mt-0.5 text-xs text-slate-500">{label}</p>
      </div>
      {badge != null && badge > 0 && (
        <span className="absolute right-2 top-2 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-bold text-slate-950">
          {badge}
        </span>
      )}
    </div>
  )
}

// ── Create User Modal ─────────────────────────────────────────────────────

function CreateUserModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    role: 'user',
    subscription_status: 'active',
    provision_container: false,
  })
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (field, value) => setForm(f => ({ ...f, [field]: value }))

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await admin.createUser(form)
      onCreated()
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-slate-700/60 bg-[#161b27] p-6 shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-100">Create User</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-slate-500 hover:bg-slate-700 hover:text-slate-300 transition"
          >
            <XCircle className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-4">
          {/* Name */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-400">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={e => set('name', e.target.value)}
              placeholder="Full name"
              className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 outline-none focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20 transition"
            />
          </div>

          {/* Email */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-400">Email</label>
            <input
              type="email"
              value={form.email}
              onChange={e => set('email', e.target.value)}
              placeholder="user@example.com"
              required
              className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 outline-none focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20 transition"
            />
          </div>

          {/* Password */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-400">Password</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={form.password}
                onChange={e => set('password', e.target.value)}
                placeholder="Min 8 characters"
                required
                className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 pr-9 text-sm text-slate-100 placeholder-slate-600 outline-none focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20 transition"
              />
              <button
                type="button"
                onClick={() => setShowPassword(s => !s)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition"
              >
                {showPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          {/* Role + Status row */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-400">Role</label>
              <select
                value={form.role}
                onChange={e => set('role', e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-100 outline-none focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20 transition"
              >
                <option value="user">User</option>
                <option value="superuser">Super User</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-400">Status</label>
              <select
                value={form.subscription_status}
                onChange={e => set('subscription_status', e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-100 outline-none focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20 transition"
              >
                <option value="active">Active</option>
                <option value="pending">Pending</option>
              </select>
            </div>
          </div>

          {/* Provision container */}
          <label className="flex cursor-pointer items-center gap-2.5">
            <input
              type="checkbox"
              checked={form.provision_container}
              onChange={e => set('provision_container', e.target.checked)}
              className="h-4 w-4 rounded border-slate-600 bg-slate-800 accent-violet-500"
            />
            <span className="text-sm text-slate-400">Provision container on creation</span>
          </label>

          {error && (
            <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex items-center gap-1.5 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition"
            >
              {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Create User
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── LinkedIn Credential Modal ─────────────────────────────────────────────

function LinkedInCredentialModal({ user, onClose, onSaved }) {
  const [email, setEmail] = useState(user?.container?.linkedin_email || '')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [error, setError] = useState('')
  const hasExisting = !!user?.container?.has_linkedin_password

  const handleSave = async (e) => {
    e.preventDefault()
    if (!email.trim()) {
      setError('Email is required')
      return
    }
    if (!password.trim() && !hasExisting) {
      setError('Password is required for new credentials')
      return
    }
    setError('')
    setLoading(true)
    try {
      await admin.setLinkedInCredentials(user.id, email.trim(), password)
      onSaved()
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save credentials')
    } finally {
      setLoading(false)
    }
  }

  const handleClear = async () => {
    if (!window.confirm(`Clear LinkedIn credentials for ${user.email}?`)) return
    setClearing(true)
    try {
      await admin.clearLinkedInCredentials(user.id)
      onSaved()
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to clear credentials')
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-slate-700/60 bg-[#161b27] p-6 shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-100">LinkedIn Credentials</h2>
            <p className="mt-0.5 text-xs text-slate-500">{user.email}</p>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-slate-500 hover:bg-slate-700 hover:text-slate-300 transition">
            <XCircle className="h-4 w-4" />
          </button>
        </div>

        <div className="mb-4 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/8 px-4 py-3 text-xs text-amber-300">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Password is stored in plaintext in the database. It is never returned via the API and is only used by the automation engine.</span>
        </div>

        {hasExisting && (
          <div className="mb-4 flex items-center gap-2 text-xs text-emerald-400">
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
            Credentials already saved — enter new values to replace
          </div>
        )}

        <form onSubmit={handleSave} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-400">LinkedIn Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="user@gmail.com"
              className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 outline-none focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20 transition"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-400">LinkedIn Password</label>
            <div className="relative">
              <input
                type={showPass ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder={hasExisting ? '••••••••  (leave blank to keep existing)' : '••••••••'}
                className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 pr-9 text-sm text-slate-100 placeholder-slate-600 outline-none focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20 transition"
              />
              <button
                type="button"
                onClick={() => setShowPass(s => !s)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition"
              >
                {showPass ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          {error && (
            <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">{error}</p>
          )}

          <div className="flex items-center justify-between gap-2 pt-1">
            {hasExisting && (
              <button
                type="button"
                onClick={handleClear}
                disabled={clearing}
                className="flex items-center gap-1.5 rounded-lg border border-red-500/30 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 disabled:opacity-50 transition"
              >
                {clearing && <Loader2 className="h-3 w-3 animate-spin" />}
                Clear Credentials
              </button>
            )}
            <div className="ml-auto flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !email.trim() || (!password.trim() && !hasExisting)}
                className="flex items-center gap-1.5 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition"
              >
                {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Save
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Users Tab ─────────────────────────────────────────────────────────────

function UsersTab({ users, onAction, isLoading, currentAdminId, onRefresh }) {
  const [showCreate, setShowCreate] = useState(false)
  const [linkedInUser, setLinkedInUser] = useState(null)

  const doAction = (userId, actionKey, fn, confirm_msg) => {
    if (confirm_msg && !window.confirm(confirm_msg)) return
    onAction(userId, actionKey, fn)
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">{users.length} user{users.length !== 1 ? 's' : ''}</p>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-violet-700 transition"
        >
          <Plus className="h-3.5 w-3.5" />
          Create User
        </button>
      </div>

      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700/40 text-left text-xs text-slate-500">
                <th className="px-5 py-2.5 font-medium">Name / Email</th>
                <th className="px-5 py-2.5 font-medium">Role</th>
                <th className="px-5 py-2.5 font-medium">Status</th>
                <th className="px-5 py-2.5 font-medium">Container</th>
                <th className="px-5 py-2.5 font-medium">Last Login</th>
                <th className="px-5 py-2.5 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => {
                const c = u.container
                const isSelf = u.id === currentAdminId
                const isRunning = c?.status === 'running'
                const isStopped = c && !isRunning
                const hasCont = !!c
                const isSuspended = u.subscription_status === 'suspended'

                return (
                  <tr key={u.id} className="border-b border-slate-700/20 hover:bg-slate-800/30 transition">
                    <td className="px-5 py-3">
                      <div className="font-medium text-slate-200">{u.name || '—'}</div>
                      <div className="text-xs text-slate-500">{u.email}</div>
                    </td>
                    <td className="px-5 py-3">
                      <Badge text={u.role} styleClass={ROLE_STYLE[u.role] || ROLE_STYLE.user} />
                    </td>
                    <td className="px-5 py-3">
                      <Badge
                        text={u.subscription_status}
                        styleClass={SUB_STATUS_STYLE[u.subscription_status] || SUB_STATUS_STYLE.cancelled}
                      />
                    </td>
                    <td className="px-5 py-3">
                      {hasCont ? (
                        <div className="flex flex-col gap-1">
                          <Badge
                            text={c.status}
                            styleClass={CONTAINER_STATUS_STYLE[c.status] || CONTAINER_STATUS_STYLE.stopped}
                          />
                          <div className="flex items-center gap-1 text-xs text-slate-600">
                            {HEALTH_ICON[c.health_status] || HEALTH_ICON.unknown}
                            <span>{c.health_status}</span>
                          </div>
                          {c.linkedin_email && (
                            <div className="flex items-center gap-1 text-[10px] text-slate-500">
                              <Key className="h-2.5 w-2.5 shrink-0" />
                              <span className="truncate max-w-[120px]" title={c.linkedin_email}>{c.linkedin_email}</span>
                            </div>
                          )}
                          {!c.linkedin_email && (
                            <div className="text-[10px] text-slate-700 italic">no linkedin creds</div>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-600">none</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-xs text-slate-400">
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3 text-slate-600" />
                        {timeAgo(u.last_login_at)}
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-0.5">
                        {/* Pause container */}
                        {hasCont && isRunning && (
                          <ActionBtn
                            icon={Pause}
                            tip="Pause container (stop container, keep account active)"
                            loading={isLoading(u.id, 'pause')}
                            onClick={() => doAction(u.id, 'pause', () => admin.pauseUser(u.id))}
                          />
                        )}
                        {/* Resume container */}
                        {hasCont && isStopped && u.is_active && (
                          <ActionBtn
                            icon={Play}
                            tip="Resume container"
                            loading={isLoading(u.id, 'resume')}
                            onClick={() => doAction(u.id, 'resume', () => admin.resumeUser(u.id))}
                          />
                        )}
                        {/* Restart container */}
                        {hasCont && (
                          <ActionBtn
                            icon={RotateCcw}
                            tip="Restart container"
                            loading={isLoading(u.id, 'restart')}
                            onClick={() => doAction(u.id, 'restart', () => admin.restartContainer(c.id))}
                          />
                        )}
                        {/* Provision container */}
                        {!hasCont && u.is_active && (
                          <ActionBtn
                            icon={Server}
                            tip="Provision container"
                            loading={isLoading(u.id, 'provision')}
                            onClick={() => doAction(u.id, 'provision', () => admin.provisionUser(u.id))}
                          />
                        )}
                        {/* Change role (cycles: user → superuser → admin → user) */}
                        {!isSelf && (
                          <ActionBtn
                            icon={UserCog}
                            tip={`Change role (currently ${u.role}) → next: ${ROLE_CYCLE[u.role] || 'user'}`}
                            loading={isLoading(u.id, 'role')}
                            onClick={() => {
                              const newRole = ROLE_CYCLE[u.role] || 'user'
                              if (!window.confirm(`Change ${u.email} role to "${newRole}"?`)) return
                              onAction(u.id, 'role', () => admin.changeRole(u.id, newRole))
                            }}
                          />
                        )}
                        {/* LinkedIn credentials */}
                        {hasCont && (
                          <ActionBtn
                            icon={Key}
                            tip={u.container?.has_linkedin_password ? `LinkedIn creds saved (${u.container?.linkedin_email || 'no email'}) — click to update` : 'Set LinkedIn credentials'}
                            loading={isLoading(u.id, 'linkedin')}
                            onClick={() => setLinkedInUser(u)}
                          />
                        )}
                        {/* Suspend / Unsuspend */}
                        {!isSelf && !isSuspended && (
                          <ActionBtn
                            icon={Ban}
                            tip="Suspend user"
                            loading={isLoading(u.id, 'suspend')}
                            danger
                            onClick={() => doAction(
                              u.id, 'suspend',
                              () => admin.suspend(u.id),
                              `Suspend ${u.email}?`
                            )}
                          />
                        )}
                        {!isSelf && isSuspended && (
                          <ActionBtn
                            icon={CheckCircle2}
                            tip="Unsuspend user"
                            loading={isLoading(u.id, 'unsuspend')}
                            onClick={() => doAction(u.id, 'unsuspend', () => admin.unsuspend(u.id))}
                          />
                        )}
                        {/* Delete */}
                        {!isSelf && (
                          <ActionBtn
                            icon={Trash2}
                            tip="Delete user permanently"
                            loading={isLoading(u.id, 'delete')}
                            danger
                            onClick={() => doAction(
                              u.id, 'delete',
                              () => admin.deleteUser(u.id),
                              `Permanently delete ${u.email} and all their data? This cannot be undone.`
                            )}
                          />
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
              {users.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-sm text-slate-500">
                    No users yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onCreated={onRefresh}
        />
      )}
      {linkedInUser && (
        <LinkedInCredentialModal
          user={linkedInUser}
          onClose={() => setLinkedInUser(null)}
          onSaved={onRefresh}
        />
      )}
    </div>
  )
}

// ── Pending Approvals Tab ─────────────────────────────────────────────────

function PendingTab({ users, onAction, isLoading }) {
  const pending = users.filter(u => u.subscription_status === 'pending' && !u.is_active)

  if (pending.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-slate-500">
        <CheckCircle2 className="h-8 w-8 text-emerald-500/40" />
        <p className="text-sm">No pending signups</p>
        <p className="text-xs text-slate-600">All signup requests have been handled</p>
      </div>
    )
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {pending.map(u => (
        <div
          key={u.id}
          className="flex flex-col gap-4 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate font-medium text-slate-200">{u.name || '(no name)'}</p>
              <p className="truncate text-xs text-slate-500">{u.email}</p>
            </div>
            <Badge text="pending" styleClass={SUB_STATUS_STYLE.pending} />
          </div>
          <div className="flex items-center gap-1 text-xs text-slate-600">
            <Clock className="h-3 w-3" />
            Joined {timeAgo(u.created_at)}
          </div>
          <div className="flex gap-2">
            <button
              disabled={isLoading(u.id, 'approve')}
              onClick={() => onAction(u.id, 'approve', () => admin.approveUser(u.id))}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 transition"
            >
              {isLoading(u.id, 'approve')
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <CheckCircle2 className="h-3.5 w-3.5" />
              }
              Approve
            </button>
            <button
              disabled={isLoading(u.id, 'reject')}
              onClick={() => {
                if (!window.confirm(`Reject signup from ${u.email}?`)) return
                onAction(u.id, 'reject', () => admin.rejectUser(u.id))
              }}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/20 disabled:opacity-50 transition"
            >
              {isLoading(u.id, 'reject')
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <XCircle className="h-3.5 w-3.5" />
              }
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Audit Log Tab ─────────────────────────────────────────────────────────

function AuditLogTab() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await admin.auditLog()
      setEntries(res.data)
      setLoaded(true)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load audit log')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const formatDetails = (details) => {
    if (!details || typeof details !== 'object') return '—'
    return Object.entries(details)
      .map(([k, v]) => `${k}: ${v}`)
      .join('  ·  ')
  }

  if (loading && !loaded) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-violet-400" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-slate-500">
        <AlertTriangle className="h-6 w-6 text-red-400/50" />
        <p className="text-sm text-red-400">{error}</p>
        <button
          onClick={load}
          className="text-xs text-slate-500 underline hover:text-slate-300"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">{entries.length} entries (latest 100)</p>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition disabled:opacity-40"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700/40 text-left text-xs text-slate-500">
                <th className="px-5 py-2.5 font-medium">Time</th>
                <th className="px-5 py-2.5 font-medium">Admin</th>
                <th className="px-5 py-2.5 font-medium">Action</th>
                <th className="px-5 py-2.5 font-medium">Details</th>
                <th className="px-5 py-2.5 font-medium">IP</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.id} className="border-b border-slate-700/20 hover:bg-slate-800/30 transition">
                  <td className="px-5 py-2.5 text-xs tabular-nums text-slate-500 whitespace-nowrap">
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                  <td className="px-5 py-2.5 text-xs text-slate-400">
                    {e.admin_email || e.user_id?.slice(0, 8) || '—'}
                  </td>
                  <td className="px-5 py-2.5">
                    <span className="rounded-md border border-violet-500/20 bg-violet-500/10 px-2 py-0.5 font-mono text-[10px] text-violet-300">
                      {e.action}
                    </span>
                  </td>
                  <td className="px-5 py-2.5 text-xs text-slate-500 max-w-xs truncate">
                    {formatDetails(e.details)}
                  </td>
                  <td className="px-5 py-2.5 text-xs tabular-nums text-slate-600">
                    {e.ip_address || '—'}
                  </td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-sm text-slate-500">
                    No audit log entries yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const [users, setUsers] = useState([])
  const [system, setSystem] = useState(null)
  const [tailscale, setTailscale] = useState(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState({})
  const [activeTab, setActiveTab] = useState('users')

  // Read current admin ID from token payload
  const currentAdminId = (() => {
    try {
      const token = localStorage.getItem('platform_token')
      if (!token) return null
      const payload = JSON.parse(atob(token.split('.')[1]))
      return payload.sub
    } catch {
      return null
    }
  })()

  const load = async () => {
    try {
      const [usersRes, systemRes, tsRes] = await Promise.allSettled([
        admin.users(),
        admin.system(),
        platformHealth.tailscale(),
      ])
      if (usersRes.status === 'fulfilled') setUsers(usersRes.value.data)
      if (systemRes.status === 'fulfilled') setSystem(systemRes.value.data)
      if (tsRes.status === 'fulfilled') setTailscale(tsRes.value.data)
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

  const doAction = async (userId, actionKey, fn) => {
    setActionLoading(p => ({ ...p, [`${userId}-${actionKey}`]: true }))
    try {
      await fn()
      await load()
    } catch (e) {
      alert(e.response?.data?.detail || 'Action failed')
    } finally {
      setActionLoading(p => ({ ...p, [`${userId}-${actionKey}`]: false }))
    }
  }

  const isLoading = (userId, actionKey) => !!actionLoading[`${userId}-${actionKey}`]

  const pendingCount = users.filter(u => u.subscription_status === 'pending' && !u.is_active).length

  const TABS = [
    { id: 'users', label: 'Users', icon: Users },
    { id: 'pending', label: 'Pending Approvals', icon: Clock, badge: pendingCount },
    { id: 'audit', label: 'Audit Log', icon: FileText },
  ]

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-violet-400" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Admin Dashboard</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Manage users, containers, and system resources
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* System Stats */}
      {system && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <StatCard
            icon={Users}
            label="Total Users"
            value={system.users}
            color="text-violet-400"
          />
          <StatCard
            icon={Server}
            label="Containers Running"
            value={`${system.containers_running}/${system.max_containers}`}
            color="text-emerald-400"
          />
          <StatCard
            icon={Server}
            label="Total Containers"
            value={system.containers_total}
            color="text-blue-400"
          />
          <StatCard
            icon={Cpu}
            label="CPU"
            value={`${system.cpu_percent}%`}
            color="text-amber-400"
          />
          <StatCard
            icon={Activity}
            label="RAM Used"
            value={`${system.memory.used_gb}/${system.memory.total_gb} GB`}
            color="text-red-400"
          />
          <StatCard
            icon={HardDrive}
            label="Disk"
            value={`${system.disk.used_gb}/${system.disk.total_gb} GB`}
            color="text-slate-400"
            badge={pendingCount}
          />
        </div>
      )}

      {/* Tailscale Status */}
      {tailscale && tailscale.enabled && (
        <div className={`flex items-center justify-between gap-3 rounded-xl border px-4 py-3 ${
          tailscale.connected
            ? 'border-emerald-500/20 bg-emerald-500/8'
            : 'border-red-500/30 bg-red-500/10'
        }`}>
          <div className="flex items-center gap-3">
            {tailscale.connected
              ? <Wifi className="h-4 w-4 shrink-0 text-emerald-400" />
              : <WifiOff className="h-4 w-4 shrink-0 text-red-400" />
            }
            <div>
              <p className={`text-sm font-medium ${tailscale.connected ? 'text-emerald-300' : 'text-red-300'}`}>
                {tailscale.connected ? 'Exit node online' : 'Exit node OFFLINE'}
              </p>
              <p className="text-xs text-slate-500">
                {tailscale.connected
                  ? `LinkedIn traffic exits via home IP (${tailscale.exit_node})`
                  : `All LinkedIn engines paused — traffic via Oracle IP blocked (${tailscale.exit_node})`
                }
              </p>
            </div>
          </div>
          {!tailscale.connected && tailscale.engines_paused_by_ts?.length > 0 && (
            <span className="shrink-0 rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-400">
              {tailscale.engines_paused_by_ts.length} engine{tailscale.engines_paused_by_ts.length !== 1 ? 's' : ''} paused
            </span>
          )}
          {tailscale.connected && tailscale.engines_paused_by_ts?.length === 0 && (
            <span className="shrink-0 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400">
              All engines active
            </span>
          )}
        </div>
      )}
      {tailscale && !tailscale.enabled && (
        <div className="flex items-center gap-3 rounded-xl border border-slate-700/40 bg-slate-800/30 px-4 py-3 text-xs text-slate-500">
          <WifiOff className="h-3.5 w-3.5 shrink-0" />
          Tailscale exit node not configured — containers use Oracle Cloud IP
        </div>
      )}

      {/* Warnings */}
      {system && system.memory.percent > 80 && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-300">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          RAM usage at {system.memory.percent}% — consider stopping idle containers
        </div>
      )}

      {pendingCount > 0 && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-300">
          <Clock className="h-4 w-4 shrink-0" />
          {pendingCount} signup{pendingCount !== 1 ? 's' : ''} waiting for approval —{' '}
          <button
            className="underline hover:no-underline"
            onClick={() => setActiveTab('pending')}
          >
            review now
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="rounded-xl border border-slate-700/60 bg-[#161b27] overflow-hidden">
        {/* Tab bar */}
        <div className="flex border-b border-slate-700/60">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative flex items-center gap-2 px-5 py-3 text-sm font-medium transition ${
                activeTab === tab.id
                  ? 'text-violet-400 border-b-2 border-violet-500'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              <tab.icon className="h-3.5 w-3.5" />
              {tab.label}
              {tab.badge != null && tab.badge > 0 && (
                <span className="flex h-4.5 min-w-[1.1rem] items-center justify-center rounded-full bg-amber-500 px-1 text-[9px] font-bold text-slate-950">
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="p-5">
          {activeTab === 'users' && (
            <UsersTab
              users={users}
              onAction={doAction}
              isLoading={isLoading}
              currentAdminId={currentAdminId}
              onRefresh={load}
            />
          )}
          {activeTab === 'pending' && (
            <PendingTab
              users={users}
              onAction={doAction}
              isLoading={isLoading}
            />
          )}
          {activeTab === 'audit' && (
            <AuditLogTab />
          )}
        </div>
      </div>
    </div>
  )
}
