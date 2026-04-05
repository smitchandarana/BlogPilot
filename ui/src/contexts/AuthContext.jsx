import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { auth as authApi, containers as containersApi } from '../api/platform'
import { setContainerBaseUrl } from '../api/client'
import { setWebSocketUrl } from '../hooks/useWebSocket'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)           // { id, email, name, role }
  const [containerInfo, setContainerInfo] = useState(null) // { port, status, token }
  const [loading, setLoading] = useState(true)

  // Computed URLs for the user's BlogPilot container
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost'
  const containerBaseUrl = containerInfo?.port
    ? user
      ? `${apiBaseUrl}/u/${user.id}`
      : null
    : null
  const containerWsUrl = containerBaseUrl
    ? containerBaseUrl.replace('http', 'ws') + '/ws'
    : null

  const _configureContainerUrls = useCallback((userId) => {
    const base = `${apiBaseUrl}/u/${userId}`
    setContainerBaseUrl(base)
    setWebSocketUrl(base.replace('http', 'ws') + '/ws')
  }, [apiBaseUrl])

  const login = useCallback(async (email, password) => {
    const res = await authApi.login(email, password)
    const data = res.data
    localStorage.setItem('platform_token', data.token)
    if (data.container_token) {
      localStorage.setItem('api_token', data.container_token)
    }
    setUser({ id: data.user_id, email: data.email, name: data.name, role: data.role })
    setContainerInfo({
      port: data.container_port,
      status: data.container_status,
      token: data.container_token,
    })
    // Wire frontend API client to user's container
    _configureContainerUrls(data.user_id)
    return data
  }, [_configureContainerUrls])

  const signup = useCallback(async (email, password, name) => {
    const res = await authApi.signup(email, password, name)
    const data = res.data
    if (data.pending_approval) {
      // Account awaiting admin approval — do NOT persist token or set user state
      return data
    }
    localStorage.setItem('platform_token', data.token)
    setUser({ id: data.user_id, email: data.email, name: data.name, role: data.role })
    setContainerInfo(null)
    return data
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('platform_token')
    localStorage.removeItem('api_token')
    setUser(null)
    setContainerInfo(null)
  }, [])

  const refreshContainerStatus = useCallback(async () => {
    try {
      const res = await containersApi.status()
      setContainerInfo(prev => ({
        ...prev,
        status: res.data.status,
        port: res.data.host_port || prev?.port,
      }))
    } catch { /* ignore */ }
  }, [])

  // Auto-logout when platform JWT expires mid-session (dispatched by platform.js interceptor)
  useEffect(() => {
    const handleUnauthorized = () => {
      localStorage.removeItem('platform_token')
      localStorage.removeItem('api_token')
      setUser(null)
      setContainerInfo(null)
    }
    window.addEventListener('platform:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('platform:unauthorized', handleUnauthorized)
  }, [])

  // Restore session on mount
  useEffect(() => {
    const token = localStorage.getItem('platform_token')
    if (!token) {
      setLoading(false)
      return
    }

    const restore = async () => {
      try {
        const meRes = await authApi.me()
        const u = meRes.data
        setUser({ id: u.id, email: u.email, name: u.name, role: u.role })
        _configureContainerUrls(u.id)
      } catch {
        // /me failed — token invalid, log out
        localStorage.removeItem('platform_token')
        localStorage.removeItem('api_token')
        setLoading(false)
        return
      }

      // Container status is best-effort — never log out over it
      try {
        const cRes = await containersApi.status()
        setContainerInfo({
          port: cRes.data.host_port,
          status: cRes.data.status,
          token: localStorage.getItem('api_token'),
        })
      } catch {
        /* no container yet or offline — containerInfo stays null */
      }

      setLoading(false)
    }

    restore()
  }, [])

  return (
    <AuthContext.Provider value={{
      user,
      containerInfo,
      containerBaseUrl,
      containerWsUrl,
      loading,
      isAuthenticated: !!user,
      isAdmin: user?.role === 'admin',
      isSuperUser: user?.role === 'superuser' || user?.role === 'admin',
      login,
      signup,
      logout,
      refreshContainerStatus,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
