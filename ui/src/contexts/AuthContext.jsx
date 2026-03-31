import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { auth as authApi, containers as containersApi } from '../api/platform'

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
    return data
  }, [])

  const signup = useCallback(async (email, password, name) => {
    const res = await authApi.signup(email, password, name)
    const data = res.data
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

  // Restore session on mount
  useEffect(() => {
    const token = localStorage.getItem('platform_token')
    if (!token) {
      setLoading(false)
      return
    }
    authApi.me()
      .then(res => {
        setUser({
          id: res.data.id,
          email: res.data.email,
          name: res.data.name,
          role: res.data.role,
        })
        return containersApi.status()
      })
      .then(res => {
        setContainerInfo({
          port: res.data.host_port,
          status: res.data.status,
          token: localStorage.getItem('api_token'),
        })
      })
      .catch(() => {
        localStorage.removeItem('platform_token')
        localStorage.removeItem('api_token')
      })
      .finally(() => setLoading(false))
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
