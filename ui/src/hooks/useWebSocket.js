import { useEffect, useRef, useState, useCallback } from 'react'

const _defaultWsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
const _defaultApiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const MAX_BACKOFF_MS = 30000

// Allow runtime override (called by AuthContext for multi-tenant routing)
let _wsUrlOverride = null
export function setWebSocketUrl(url) { _wsUrlOverride = url }

async function _getToken() {
  const stored = localStorage.getItem('api_token')
  if (stored) return stored
  // Token not yet bootstrapped — fetch it now
  try {
    const res = await fetch(`${_defaultApiUrl}/auth/token`)
    if (res.ok) {
      const data = await res.json()
      if (data?.token) {
        localStorage.setItem('api_token', data.token)
        return data.token
      }
    }
  } catch { /* server may not be up yet */ }
  return null
}

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState(null)
  const wsRef = useRef(null)
  const listenersRef = useRef({})
  const retryTimeoutRef = useRef(null)
  const backoffRef = useRef(1000)

  const connect = useCallback(async () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const token = await _getToken()
    if (!token) {
      // No token yet — retry after 2s
      retryTimeoutRef.current = setTimeout(connect, 2000)
      return
    }

    const wsBase = _wsUrlOverride || _defaultWsUrl
    const url = `${wsBase}?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      backoffRef.current = 1000
    }

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        setLastEvent(msg)
        const handlers = listenersRef.current[msg.event] || []
        handlers.forEach((fn) => fn(msg.data))
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = (ev) => {
      setIsConnected(false)
      wsRef.current = null
      // If closed with 1008 (policy violation = bad token), clear stored token
      if (ev.code === 1008) {
        localStorage.removeItem('api_token')
      }
      // Exponential backoff reconnect
      retryTimeoutRef.current = setTimeout(() => {
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS)
        connect()
      }, backoffRef.current)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(retryTimeoutRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [connect])

  const subscribe = useCallback((event, callback) => {
    if (!listenersRef.current[event]) {
      listenersRef.current[event] = []
    }
    listenersRef.current[event].push(callback)
    return () => unsubscribe(event, callback)
  }, [])

  const unsubscribe = useCallback((event, callback) => {
    if (listenersRef.current[event]) {
      listenersRef.current[event] = listenersRef.current[event].filter(
        (fn) => fn !== callback
      )
    }
  }, [])

  return { isConnected, lastEvent, subscribe, unsubscribe }
}
