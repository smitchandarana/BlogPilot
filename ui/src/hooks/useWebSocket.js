import { useEffect, useRef, useState, useCallback } from 'react'

const WS_URL = 'ws://localhost:8000/ws'
const MAX_BACKOFF_MS = 30000

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState(null)
  const wsRef = useRef(null)
  const listenersRef = useRef({})
  const retryTimeoutRef = useRef(null)
  const backoffRef = useRef(1000)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
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

    ws.onclose = () => {
      setIsConnected(false)
      wsRef.current = null
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
