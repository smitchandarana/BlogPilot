import { useState, useEffect, useCallback } from 'react'
import { ExternalLink, RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react'
import { analytics, config as configApi } from '../api/client'

const MODES = [
  { value: 'like_only', label: 'Like Only', desc: 'Like relevant posts, never comment' },
  { value: 'comment_only', label: 'Comment Only', desc: 'Comment on relevant posts, never like' },
  { value: 'like_and_comment', label: 'Like + Comment', desc: 'Always do both for relevant posts' },
  { value: 'smart', label: 'Smart', desc: 'Score 6-7: like. Score 8+: like + comment' },
]

const RESULT_STYLES = {
  SUCCESS: 'bg-emerald-500/15 text-emerald-400',
  ACTED: 'bg-emerald-500/15 text-emerald-400',
  FAILED: 'bg-red-500/15 text-red-400',
  SKIPPED: 'bg-slate-700/60 text-slate-400',
}

function ScoreBadge({ score }) {
  const color = score >= 8 ? 'text-emerald-400' : score >= 6 ? 'text-amber-400' : 'text-slate-500'
  return <span className={`font-semibold tabular-nums ${color}`}>{score}</span>
}

function DataTable({ headers, rows, renderRow, emptyMsg = 'No data yet.' }) {
  if (!rows.length) {
    return <p className="py-6 text-center text-sm text-slate-500">{emptyMsg}</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[600px] text-sm">
        <thead>
          <tr className="border-b border-slate-700/60">
            {headers.map((h) => (
              <th key={h} className="pb-2 text-left text-xs font-medium uppercase tracking-wider text-slate-500 pr-4 last:pr-0">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700/30">
          {rows.map((row, i) => renderRow(row, i))}
        </tbody>
      </table>
    </div>
  )
}

function timeAgo(isoStr) {
  if (!isoStr) return ''
  const diff = Date.now() - new Date(isoStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function FeedEngagement() {
  const [mode, setMode] = useState('smart')
  const [previewComments, setPreviewComments] = useState(true)
  const [viralThreshold, setViralThreshold] = useState(50)
  const [minScore, setMinScore] = useState(6)
  const [recentPosts, setRecentPosts] = useState([])
  const [skippedPosts, setSkippedPosts] = useState([])
  const [comments, setComments] = useState([])
  const [loading, setLoading] = useState(true)
  const [saveState, setSaveState] = useState(null) // null | 'saving' | 'saved' | 'error'

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [actedRes, skippedRes, commentsRes] = await Promise.all([
        analytics.actedPosts(20),
        analytics.skippedPosts(20),
        analytics.commentHistory(20),
      ])
      setRecentPosts(actedRes.data || [])
      setSkippedPosts(skippedRes.data || [])
      setComments(commentsRes.data || [])
    } catch {
      // keep existing data on error
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let isMounted = true
    loadData()
    configApi.getSettings().then((res) => {
      if (!isMounted) return
      const d = res.data
      if (d?.feed_engagement?.mode) setMode(d.feed_engagement.mode)
      if (d?.feed_engagement?.preview_comments != null) setPreviewComments(d.feed_engagement.preview_comments)
      if (d?.viral_detection?.likes_per_hour_threshold) setViralThreshold(d.viral_detection.likes_per_hour_threshold)
      if (d?.feed_engagement?.min_relevance_score != null) setMinScore(d.feed_engagement.min_relevance_score)
    }).catch(() => {})
    return () => { isMounted = false }
  }, [loadData])

  const handleSaveSettings = async (overrides = {}) => {
    setSaveState('saving')
    try {
      await configApi.updateSettings({
        feed_engagement: { mode, preview_comments: previewComments, min_relevance_score: minScore, ...overrides.feed_engagement },
        viral_detection: { likes_per_hour_threshold: viralThreshold, ...overrides.viral_detection },
      })
      setSaveState('saved')
      setTimeout(() => setSaveState(null), 2500)
    } catch {
      setSaveState('error')
      setTimeout(() => setSaveState(null), 3000)
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-100">Feed Engagement</h1>
          <p className="mt-0.5 text-sm text-slate-500">Configure how the engine interacts with LinkedIn feed posts.</p>
        </div>
        <div className="flex items-center gap-3">
          {saveState === 'saved' && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <CheckCircle2 className="h-3.5 w-3.5" /> Saved
            </span>
          )}
          {saveState === 'error' && (
            <span className="flex items-center gap-1.5 text-xs text-red-400">
              <AlertTriangle className="h-3.5 w-3.5" /> Save failed
            </span>
          )}
          {saveState === 'saving' && (
            <span className="text-xs text-slate-500">Saving…</span>
          )}
          <button onClick={loadData} className="flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-2 text-xs text-slate-400 hover:text-slate-200 transition-colors">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </div>

      {/* Settings row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Engagement mode */}
        <div className="col-span-2 rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Engagement Mode</h2>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {MODES.map((m) => (
              <label
                key={m.value}
                className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors duration-150 ${
                  mode === m.value
                    ? 'border-violet-600/50 bg-violet-700/15'
                    : 'border-slate-700/40 bg-slate-900/30 hover:border-slate-600/60'
                }`}
              >
                <input type="radio" name="mode" value={m.value} checked={mode === m.value}
                  onChange={() => { setMode(m.value); handleSaveSettings({ feed_engagement: { mode: m.value } }) }}
                  className="mt-0.5 accent-violet-500" />
                <div>
                  <p className={`text-sm font-medium ${mode === m.value ? 'text-violet-300' : 'text-slate-300'}`}>{m.label}</p>
                  <p className="mt-0.5 text-xs text-slate-500">{m.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Quick settings */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Quick Settings</h2>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-300">Preview Comments</p>
                <p className="text-xs text-slate-500">Show before posting</p>
              </div>
              <button role="switch" aria-checked={previewComments}
                onClick={() => { const next = !previewComments; setPreviewComments(next); handleSaveSettings({ feed_engagement: { preview_comments: next } }) }}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${previewComments ? 'bg-violet-600' : 'bg-slate-700'}`}>
                <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform duration-200 ${previewComments ? 'translate-x-4' : 'translate-x-1'}`} />
              </button>
            </div>
            <div>
              <label className="mb-1.5 block text-xs text-slate-400">Min Relevance Score (0–10)</label>
              <div className="flex items-center gap-3">
                <input type="range" min={0} max={10} step={0.5} value={minScore}
                  onChange={(e) => setMinScore(Number(e.target.value))}
                  onMouseUp={handleSaveSettings}
                  onTouchEnd={handleSaveSettings}
                  className="flex-1 accent-violet-500" />
                <span className="w-6 text-right text-sm font-semibold tabular-nums text-violet-300">{minScore}</span>
              </div>
              <p className="mt-1 text-[10px] text-slate-600">Posts below this score are skipped</p>
            </div>
            <div>
              <label className="mb-1.5 block text-xs text-slate-400">Viral Threshold (likes/hr)</label>
              <input type="number" min={10} max={500} value={viralThreshold}
                onChange={(e) => setViralThreshold(Number(e.target.value))}
                onBlur={handleSaveSettings}
                className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40" />
            </div>
          </div>
        </div>
      </div>

      {/* Recent posts table */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Recent Posts</h2>
        <DataTable
          headers={['Author', 'Post', 'Score', 'Action', 'Result', 'Time']}
          rows={recentPosts}
          emptyMsg="No posts processed yet. Start the engine to begin scanning."
          renderRow={(row, i) => (
            <tr key={i} className="group">
              <td className="py-2.5 pr-4 text-slate-300">{row.author}</td>
              <td className="py-2.5 pr-4 max-w-[220px] truncate text-slate-400">{row.snippet}</td>
              <td className="py-2.5 pr-4"><ScoreBadge score={row.score} /></td>
              <td className="py-2.5 pr-4 text-xs text-slate-400">{row.action}</td>
              <td className="py-2.5 pr-4">
                <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${RESULT_STYLES[row.result] || RESULT_STYLES.SKIPPED}`}>{row.result}</span>
              </td>
              <td className="py-2.5 text-xs text-slate-500 tabular-nums">{timeAgo(row.time)}</td>
            </tr>
          )}
        />
      </div>

      {/* Skipped posts */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Skipped Posts</h2>
        <DataTable
          headers={['Author', 'Post', 'Score', 'Reason', 'Time']}
          rows={skippedPosts}
          emptyMsg="No skipped posts yet."
          renderRow={(row, i) => (
            <tr key={i}>
              <td className="py-2.5 pr-4 text-slate-300">{row.author}</td>
              <td className="py-2.5 pr-4 max-w-[200px] truncate text-slate-400">{row.snippet}</td>
              <td className="py-2.5 pr-4"><ScoreBadge score={row.score} /></td>
              <td className="py-2.5 pr-4 text-xs text-slate-500">{row.reason}</td>
              <td className="py-2.5 text-xs text-slate-500 tabular-nums">{timeAgo(row.time)}</td>
            </tr>
          )}
        />
      </div>

      {/* Comment history */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Comment History</h2>
        <DataTable
          headers={['Author', 'Comment', 'Post', 'Time']}
          rows={comments}
          emptyMsg="No comments posted yet."
          renderRow={(row, i) => (
            <tr key={i}>
              <td className="py-2.5 pr-4 text-slate-300 whitespace-nowrap">{row.author}</td>
              <td className="py-2.5 pr-4 max-w-[320px] text-slate-400 leading-relaxed">{row.comment}</td>
              <td className="py-2.5 pr-4">
                <a href={row.link} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300">
                  View <ExternalLink className="h-3 w-3" />
                </a>
              </td>
              <td className="py-2.5 text-xs text-slate-500 tabular-nums">{timeAgo(row.time)}</td>
            </tr>
          )}
        />
      </div>
    </div>
  )
}
