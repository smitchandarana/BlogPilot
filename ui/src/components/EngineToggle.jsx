import { useState } from 'react'
import { Loader2, Play, Square, Pause, RotateCcw, Radar } from 'lucide-react'
import { useEngine } from '../hooks/useEngine'
import { engine as engineApi } from '../api/client'

export default function EngineToggle() {
  const { state, loading, start, stop, pause, resume } = useEngine()
  const status = state.status
  const [scanning, setScanning] = useState(false)

  const handleScanNow = async () => {
    setScanning(true)
    try {
      await engineApi.scanNow()
    } catch (e) {
      console.error('Scan now failed:', e)
    } finally {
      setTimeout(() => setScanning(false), 2000)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-3 rounded-xl border border-slate-700 bg-slate-800/60 px-8 py-5">
        <Loader2 className="h-5 w-5 animate-spin text-violet-400" />
        <span className="text-sm font-medium text-slate-300">Applying…</span>
      </div>
    )
  }

  if (status === 'STOPPED' || status === 'ERROR') {
    return (
      <button
        onClick={start}
        className="group flex w-full items-center justify-center gap-3 rounded-xl border border-violet-600/40 bg-violet-700/20 px-8 py-5 text-violet-300 shadow-[0_0_24px_rgba(124,58,237,0.12)] transition-[background,box-shadow] duration-200 hover:bg-violet-700/30 hover:shadow-[0_0_32px_rgba(124,58,237,0.22)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 active:scale-[0.99]"
      >
        <Play className="h-5 w-5 fill-current" />
        <span className="text-base font-semibold tracking-tight">
          {status === 'ERROR' ? 'Restart Engine' : 'Start Engine'}
        </span>
      </button>
    )
  }

  if (status === 'RUNNING') {
    return (
      <div className="flex w-full gap-3">
        <button
          onClick={handleScanNow}
          disabled={scanning}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-cyan-600/40 bg-cyan-500/10 px-6 py-4 text-cyan-300 transition-[background] duration-200 hover:bg-cyan-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none"
        >
          {scanning
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <Radar className="h-4 w-4" />}
          <span className="font-semibold">{scanning ? 'Scanning…' : 'Scan Now'}</span>
        </button>
        <button
          onClick={pause}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-amber-600/40 bg-amber-500/10 px-6 py-4 text-amber-300 transition-[background] duration-200 hover:bg-amber-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 active:scale-[0.99]"
        >
          <Pause className="h-4 w-4 fill-current" />
          <span className="font-semibold">Pause</span>
        </button>
        <button
          onClick={stop}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-red-600/40 bg-red-500/10 px-6 py-4 text-red-300 transition-[background] duration-200 hover:bg-red-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 active:scale-[0.99]"
        >
          <Square className="h-4 w-4 fill-current" />
          <span className="font-semibold">Stop</span>
        </button>
      </div>
    )
  }

  if (status === 'PAUSED') {
    return (
      <div className="flex w-full gap-3">
        <button
          onClick={resume}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-emerald-600/40 bg-emerald-500/10 px-6 py-4 text-emerald-300 transition-[background] duration-200 hover:bg-emerald-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 active:scale-[0.99]"
        >
          <RotateCcw className="h-4 w-4" />
          <span className="font-semibold">Resume</span>
        </button>
        <button
          onClick={stop}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-red-600/40 bg-red-500/10 px-6 py-4 text-red-300 transition-[background] duration-200 hover:bg-red-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 active:scale-[0.99]"
        >
          <Square className="h-4 w-4 fill-current" />
          <span className="font-semibold">Stop</span>
        </button>
      </div>
    )
  }

  return null
}
