import { useState, useEffect } from 'react'
import { Wand2, RotateCcw, Send, CalendarDays, Loader2, Copy, Check, X } from 'lucide-react'
import { config as configApi, content as contentApi } from '../api/client'

const TOPICS = ['Business Intelligence', 'Data Analytics', 'Reporting Solutions', 'Dashboard Design', 'Power BI', 'Tableau']
const STYLES = ['Thought Leadership', 'Story', 'Tips List', 'Question', 'Data Insight', 'Contrarian Take']
const TONES = ['Professional', 'Conversational', 'Bold', 'Educational']

const STATUS_STYLES = {
  SCHEDULED: 'bg-violet-500/15 text-violet-300',
  PUBLISHED: 'bg-emerald-500/15 text-emerald-400',
  FAILED: 'bg-red-500/15 text-red-400',
  CANCELLED: 'bg-slate-500/15 text-slate-400',
}

const STATUS_LABELS = {
  SCHEDULED: 'Scheduled',
  PUBLISHED: 'Published',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
}

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export default function ContentStudio() {
  const [topic, setTopic] = useState(TOPICS[0])
  const [style, setStyle] = useState(STYLES[0])
  const [tone, setTone] = useState(TONES[0])
  const [wordCount, setWordCount] = useState(150)
  const [generating, setGenerating] = useState(false)
  const [generated, setGenerated] = useState('')
  const [copied, setCopied] = useState(false)

  const [showScheduler, setShowScheduler] = useState(false)
  const [scheduledAt, setScheduledAt] = useState('')
  const [scheduling, setScheduling] = useState(false)
  const [publishing, setPublishing] = useState(false)

  const [queue, setQueue] = useState([])
  const [queueLoading, setQueueLoading] = useState(true)

  useEffect(() => {
    fetchQueue()
    const id = setInterval(fetchQueue, 30_000)
    return () => clearInterval(id)
  }, [])

  const fetchQueue = async () => {
    try {
      const res = await contentApi.getQueue()
      setQueue(res.data || [])
    } catch {
      // keep existing data
    } finally {
      setQueueLoading(false)
    }
  }

  const generate = async () => {
    setGenerating(true)
    try {
      const res = await configApi.testPrompt('post', { topic, style, tone, word_count: wordCount })
      setGenerated(res.data.output || '')
    } catch {
      setGenerated(`[Mock] ${style} post about "${topic}" in a ${tone.toLowerCase()} tone.\n\nThe data doesn't lie — companies that invest in analytics report 2x faster decision-making.\n\nHere's what we've seen across 50+ implementations:\n\n1. Start with one KPI that matters\n2. Build the habit before the dashboard\n3. Let data ask the hard questions\n\nWhat metric are you watching most closely right now?\n\n#businessintelligence #dataanalytics #reporting`)
    } finally {
      setGenerating(false)
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(generated)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSchedule = async () => {
    if (!scheduledAt || !generated) return
    setScheduling(true)
    try {
      await contentApi.schedule({
        text: generated,
        topic,
        style,
        tone,
        scheduled_at: new Date(scheduledAt).toISOString(),
      })
      setShowScheduler(false)
      setScheduledAt('')
      fetchQueue()
    } catch (e) {
      alert('Failed to schedule: ' + (e.response?.data?.detail || e.message))
    } finally {
      setScheduling(false)
    }
  }

  const handlePublishNow = async () => {
    if (!generated) return
    if (!confirm('Post this to LinkedIn now?')) return
    setPublishing(true)
    try {
      await contentApi.publishNow({ text: generated, topic, style })
      alert('Post queued for publishing — check the queue for status.')
      fetchQueue()
    } catch (e) {
      alert('Failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setPublishing(false)
    }
  }

  const handleCancel = async (id) => {
    if (!confirm('Cancel this scheduled post?')) return
    try {
      await contentApi.cancel(id)
      fetchQueue()
    } catch (e) {
      alert('Could not cancel: ' + (e.response?.data?.detail || e.message))
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-100">Content Studio</h1>
        <p className="mt-0.5 text-sm text-slate-500">Generate and schedule LinkedIn posts with AI.</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left — Generator controls */}
        <div className="flex flex-col gap-5 rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Generate Post</h2>

          <div>
            <label className="mb-1.5 block text-xs text-slate-400">Topic</label>
            <select
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
            >
              {TOPICS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-xs text-slate-400">Style</label>
            <div className="grid grid-cols-2 gap-1.5">
              {STYLES.map((s) => (
                <button
                  key={s}
                  onClick={() => setStyle(s)}
                  className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                    style === s
                      ? 'border-violet-600/50 bg-violet-700/20 text-violet-300'
                      : 'border-slate-700/40 bg-slate-900/30 text-slate-400 hover:text-slate-300'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs text-slate-400">Tone</label>
            <div className="flex gap-1.5 flex-wrap">
              {TONES.map((t) => (
                <button
                  key={t}
                  onClick={() => setTone(t)}
                  className={`rounded-lg border px-3 py-1.5 text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                    tone === t
                      ? 'border-violet-600/50 bg-violet-700/20 text-violet-300'
                      : 'border-slate-700/40 bg-slate-900/30 text-slate-400 hover:text-slate-300'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="text-xs text-slate-400">Word Count</label>
              <span className="text-xs font-semibold tabular-nums text-violet-300">{wordCount}</span>
            </div>
            <input
              type="range" min={80} max={300} step={10}
              value={wordCount}
              onChange={(e) => setWordCount(Number(e.target.value))}
              className="w-full accent-violet-500"
            />
            <div className="mt-1 flex justify-between text-xs text-slate-500">
              <span>80</span><span>300</span>
            </div>
          </div>

          <button
            onClick={generate}
            disabled={generating}
            className="flex items-center justify-center gap-2 rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-medium text-white shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-[background,box-shadow] duration-200 hover:bg-violet-600 hover:shadow-[0_0_24px_rgba(124,58,237,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-60 active:scale-[0.98]"
          >
            {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
            {generating ? 'Generating…' : 'Generate Post'}
          </button>
        </div>

        {/* Right — Generated output */}
        <div className="flex flex-col gap-4 rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Generated Post</h2>
            {generated && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 rounded-lg border border-slate-700/40 px-2.5 py-1.5 text-xs text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            )}
          </div>

          <textarea
            value={generated}
            onChange={(e) => setGenerated(e.target.value)}
            placeholder="Generated post will appear here…"
            maxLength={3000}
            className="flex-1 min-h-[220px] resize-none rounded-lg border border-slate-700/60 bg-slate-900/60 p-3 text-sm leading-relaxed text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
          />

          <div className="flex items-center justify-between">
            <span className={`text-xs tabular-nums ${generated.length > 2700 ? 'text-amber-400' : 'text-slate-500'}`}>
              {generated.length} / 3000
            </span>
            <div className="flex gap-2">
              <button
                onClick={generate}
                disabled={generating || !generated}
                className="flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-900/40 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:text-slate-200 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Regenerate
              </button>
              <button
                onClick={() => setShowScheduler((v) => !v)}
                disabled={!generated}
                className="flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-900/40 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:text-slate-200 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              >
                <CalendarDays className="h-3.5 w-3.5" />
                Schedule
              </button>
              <button
                onClick={handlePublishNow}
                disabled={!generated || publishing}
                className="flex items-center gap-1.5 rounded-lg border border-violet-600/40 bg-violet-700/15 px-3 py-1.5 text-xs text-violet-300 transition-colors hover:bg-violet-700/25 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              >
                {publishing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                Post Now
              </button>
            </div>
          </div>

          {/* Inline schedule picker */}
          {showScheduler && (
            <div className="rounded-lg border border-slate-700/60 bg-slate-900/60 p-4 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Pick a date and time</span>
                <button onClick={() => setShowScheduler(false)} className="text-slate-500 hover:text-slate-300">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                className="w-full rounded-lg border border-slate-700/60 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              />
              <button
                onClick={handleSchedule}
                disabled={!scheduledAt || scheduling}
                className="flex items-center justify-center gap-2 rounded-lg bg-violet-700 px-4 py-2 text-xs font-medium text-white disabled:opacity-50 hover:bg-violet-600 transition-colors"
              >
                {scheduling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CalendarDays className="h-3.5 w-3.5" />}
                {scheduling ? 'Scheduling…' : 'Confirm Schedule'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Post queue — live from API */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Post Queue</h2>
          <button
            onClick={fetchQueue}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            Refresh
          </button>
        </div>
        <div className="overflow-x-auto">
          {queueLoading ? (
            <div className="py-8 text-center text-sm text-slate-500">Loading…</div>
          ) : queue.length === 0 ? (
            <div className="py-8 text-center text-sm text-slate-500">No posts in queue</div>
          ) : (
            <table className="w-full min-w-[600px] text-sm">
              <thead>
                <tr className="border-b border-slate-700/60">
                  {['Scheduled Time', 'Topic', 'Style', 'Status', ''].map((h) => (
                    <th key={h} className="pb-2 text-left text-xs font-medium uppercase tracking-wider text-slate-500 pr-4 last:pr-0">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/30">
                {queue.map((row) => (
                  <tr key={row.id}>
                    <td className="py-2.5 pr-4 text-slate-400 tabular-nums">{formatDate(row.scheduled_at)}</td>
                    <td className="py-2.5 pr-4 text-slate-300">{row.topic || '—'}</td>
                    <td className="py-2.5 pr-4 text-slate-400">{row.style || '—'}</td>
                    <td className="py-2.5 pr-4">
                      <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[row.status] || 'text-slate-400'}`}>
                        {STATUS_LABELS[row.status] || row.status}
                      </span>
                    </td>
                    <td className="py-2.5">
                      {row.status === 'SCHEDULED' && (
                        <button
                          onClick={() => handleCancel(row.id)}
                          className="text-xs text-red-400/70 hover:text-red-400 transition-colors"
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
