import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

/**
 * SuperUserRoute — allows admin and superuser roles.
 * Used for /campaigns and /leads (not /admin which is admin-only).
 */
export default function SuperUserRoute() {
  const { isAuthenticated, isSuperUser, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (!isSuperUser) return <Navigate to="/" replace />

  return <Outlet />
}
