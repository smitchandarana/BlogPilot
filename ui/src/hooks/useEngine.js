import { useState, useEffect, useCallback } from 'react'
import { engine as engineApi } from '../api/client'
import { useWebSocket } from './useWebSocket'

export function useEngine() {
  const [state, setState] = useState({
    status: 'STOPPED',
    uptime: 0,
    tasksQueued: 0,
    activeWorkers: 0,
  })
  const [loading, setLoading] = useState(false)
  const { subscribe } = useWebSocket()

  // Fetch initial status
  useEffect(() => {
    engineApi
      .status()
      .then((res) => {
        const d = res.data
        setState({
          status: d.state || 'STOPPED',
          uptime: d.uptime_seconds || 0,
          tasksQueued: d.tasks_queued || 0,
          activeWorkers: d.active_workers || 0,
        })
      })
      .catch(() => {})
  }, [])

  // Listen for state changes over WebSocket
  useEffect(() => {
    const unsub = subscribe('engine_state', (data) => {
      setState((prev) => ({ ...prev, status: data.state }))
    })
    return unsub
  }, [subscribe])

  const start = useCallback(async () => {
    setLoading(true)
    try {
      const res = await engineApi.start()
      setState((prev) => ({ ...prev, status: res.data.state }))
    } finally {
      setLoading(false)
    }
  }, [])

  const stop = useCallback(async () => {
    setLoading(true)
    try {
      const res = await engineApi.stop()
      setState((prev) => ({ ...prev, status: res.data.state }))
    } finally {
      setLoading(false)
    }
  }, [])

  const pause = useCallback(async () => {
    setLoading(true)
    try {
      const res = await engineApi.pause()
      setState((prev) => ({ ...prev, status: res.data.state }))
    } finally {
      setLoading(false)
    }
  }, [])

  const resume = useCallback(async () => {
    setLoading(true)
    try {
      const res = await engineApi.resume()
      setState((prev) => ({ ...prev, status: res.data.state }))
    } finally {
      setLoading(false)
    }
  }, [])

  return { state, loading, start, stop, pause, resume }
}
