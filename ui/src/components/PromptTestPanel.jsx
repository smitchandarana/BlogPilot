import { useState, useEffect } from 'react'
import { Play, Copy, Check, Loader2 } from 'lucide-react'
import { config as configApi } from '../api/client'

function extractVars(text) {
  const matches = text.match(/\{(\w+)\}/g) || []
  return [...new Set(matches.map((m) => m.slice(1, -1)))]
}

export default function PromptTestPanel({ promptName, promptText }) {
  const [vars, setVars] = useState({})
  const [output, setOutput] = useState('')
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const detectedVars = extractVars(promptText || '')

  useEffect(() => {
    setVars((prev) => {
      const next = {}
      detectedVars.forEach((v) => { next[v] = prev[v] || '' })
      return next
    })
  }, [promptText])

  const handleTest = async () => {
    setLoading(true)
    try {
      const res = await configApi.testPrompt(promptName, vars)
      setOutput(res.data.output || '')
    } catch {
      setOutput('[Error] Could not reach backend. Make sure the API server is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(output)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex flex-col gap-4">
      {detectedVars.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {detectedVars.map((v) => (
            <div key={v}>
              <label className="mb-1 block text-xs text-slate-400">{'{' + v + '}'}</label>
              <input
                value={vars[v] || ''}
                onChange={(e) => setVars((prev) => ({ ...prev, [v]: e.target.value }))}
                placeholder={`Sample ${v}…`}
                className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-1.5 text-sm text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              />
            </div>
          ))}
        </div>
      )}

      <button
        onClick={handleTest}
        disabled={loading}
        className="flex items-center justify-center gap-2 rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white shadow-[0_0_16px_rgba(124,58,237,0.15)] transition-[background,box-shadow] duration-200 hover:bg-violet-600 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 active:scale-[0.98]"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        {loading ? 'Running…' : 'Run Test'}
      </button>

      {(output || loading) && (
        <div className="relative rounded-xl border border-slate-700/60 bg-slate-900/60">
          <div className="flex items-center justify-between border-b border-slate-700/40 px-4 py-2">
            <span className="text-xs text-slate-500">Output</span>
            {output && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-xs text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            )}
          </div>
          <div className="min-h-[80px] p-4">
            {loading ? (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating…
              </div>
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{output}</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
