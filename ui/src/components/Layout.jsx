import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Settings2,
  Hash,
  Rss,
  PenTool,
  Target,
  Users,
  BarChart3,
  FileCode2,
  Settings,
  Zap,
  Shield,
  LogOut,
} from 'lucide-react'
import { useEngine } from '../hooks/useEngine'
import { useAuth } from '../contexts/AuthContext'

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/control', label: 'Engine Control', icon: Settings2 },
  { path: '/topics', label: 'Topics', icon: Hash },
  { path: '/feed', label: 'Feed', icon: Rss },
  { path: '/content', label: 'Content Studio', icon: PenTool },
  { path: '/campaigns', label: 'Campaigns', icon: Target },
  { path: '/leads', label: 'Leads', icon: Users },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/prompts', label: 'Prompts', icon: FileCode2 },
  { path: '/settings', label: 'Settings', icon: Settings },
]

function StatusDot({ status }) {
  const color =
    status === 'RUNNING'
      ? 'bg-emerald-400'
      : status === 'PAUSED'
      ? 'bg-amber-400'
      : 'bg-slate-500'
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${color} mr-2 flex-shrink-0`}
    />
  )
}

export default function Layout({ children }) {
  const { state } = useEngine()
  const { user, isAdmin, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-[#0f1117] text-slate-200">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-[#161b27] border-r border-slate-800 flex flex-col">
        {/* Logo */}
        <div className="px-4 py-5 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Zap size={18} className="text-violet-400" />
            <span className="text-sm font-semibold text-slate-100 leading-tight">
              LinkedIn AI<br />Growth Engine
            </span>
          </div>
        </div>

        {/* Engine status badge */}
        <div className="px-4 py-3 border-b border-slate-800">
          <div className="flex items-center text-xs text-slate-400">
            <StatusDot status={state.status} />
            <span className="capitalize">{state.status.toLowerCase()}</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-2">
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-violet-700/20 text-violet-300 border-r-2 border-violet-400'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
          {isAdmin && (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-violet-700/20 text-violet-300 border-r-2 border-violet-400'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`
              }
            >
              <Shield size={16} />
              Admin
            </NavLink>
          )}
        </nav>

        {/* User + Logout */}
        <div className="border-t border-slate-800 px-4 py-3">
          <div className="text-xs text-slate-500 truncate">{user?.email}</div>
          <button
            onClick={handleLogout}
            className="mt-2 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-200"
          >
            <LogOut size={14} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  )
}
