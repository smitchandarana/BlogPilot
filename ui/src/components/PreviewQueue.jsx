/**
 * PreviewQueue — displays AI-generated comments awaiting human approval.
 *
 * Shown on the Dashboard when preview_comments=true (the default).
 * Each card shows the post author, a snippet of the post, and the AI comment.
 * The user can edit the comment, then Approve (queues the post to LinkedIn)
 * or Reject (marks it SKIPPED with no action).
 *
 * Data sources:
 *   - On mount: GET /engine/pending-previews (persisted PREVIEW posts from DB)
 *   - Live:     WebSocket "post_preview" event (new previews as the engine runs)
 *
 * On approve: POST /engine/approve-comment  → worker posts the comment on LinkedIn
 * On reject:  POST /engine/reject-comment   → marks post SKIPPED in DB
 */

import { useState, useEffect, useCallback } from 'react'
import { Check, X, Edit3, ExternalLink, Clock, Loader2, MessageSquare } from 'lucide-react'
import { engine as engineApi } from '../api/client'
import { useWebSocket } from '../hooks/useWebSocket'

function ScorePill({ score }) {
  const color =
    score >= 8 ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' :
    score >= 6 ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' :
                 'bg-slate-700/60 text-slate-400 border-slate-600/30'
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold tabular-nums ${color}`}>
      {score.toFixed(1)}
    </span>
  )
}

function PreviewCard({ item, onApprove, onReject }) {
  const [editing, setEditing] = useState(false)
  const [commentText, setCommentText] = useState(item.comment)
  const [status, setStatus] = useState('idle') // idle | approving | approved | rejected

  const handleApprove = async () => {
    setStatus('approving')
    try {
      await onApprove(item.post_id, commentText)
      setStatus('approved')
    } catch {
      setStatus('idle')
    }
  }

  const handleReject = async () => {
    setStatus('rejected')
    try {
      await onReject(item.post_id)
    } catch {
      setStatus('idle')
    }
  }

  if (status === 'approved') {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-400">
        <Check className="h-4 w-4 shrink-0" />
        Comment queued for posting on <span className="font-medium ml-1">{item.author}</span>'s post
      </div>
    )
  }

  if (status === 'rejected') {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-slate-700/40 bg-slate-800/30 px-4 py-3 text-sm text-slate-500">
        <X className="h-4 w-4 shrink-0" />
        Rejected — <span className="font-medium ml-1">{item.author}</span>'s post skipped
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-violet-500/20 bg-slate-800/60 p-4 ring-1 ring-violet-500/10">
      {/* Header */}
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 shrink-0 text-violet-400" />
          <span className="text-sm font-medium text-slate-200">{item.author}</span>
          <ScorePill score={item.score} />
        </div>
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-violet-400 transition-colors"
        >
          View post <ExternalLink className="h-3 w-3" />
        </a>
      </div>

      {/* Post snippet */}
      <p className="mb-3 text-xs leading-relaxed text-slate-500 line-clamp-2">
        {item.snippet}
      </p>

      {/* AI comment — editable */}
      <div className="mb-3">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
            AI Comment
          </span>
          <button
            onClick={() => setEditing(!editing)}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-violet-400 transition-colors"
          >
            <Edit3 className="h-3 w-3" />
            {editing ? 'Done' : 'Edit'}
          </button>
        </div>
        {editing ? (
          <textarea
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            rows={4}
            className="w-full resize-none rounded-lg border border-violet-500/40 bg-slate-900/80 px-3 py-2 text-sm leading-relaxed text-slate-200 focus:border-violet-500/70 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
          />
        ) : (
          <p
            className="cursor-text rounded-lg border border-slate-700/50 bg-slate-900/40 px-3 py-2 text-sm leading-relaxed text-slate-300"
            onClick={() => setEditing(true)}
          >
            {commentText || <span className="text-slate-500 italic">No comment generated</span>}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleApprove}
          disabled={status === 'approving' || !commentText.trim()}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
        >
          {status === 'approving' ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Queuing…
            </>
          ) : (
            <>
              <Check className="h-3.5 w-3.5" />
              Approve & Post
            </>
          )}
        </button>
        <button
          onClick={handleReject}
          disabled={status === 'approving'}
          className="flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-red-500/40 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/40"
        >
          <X className="h-3.5 w-3.5" />
          Reject
        </button>
      </div>
    </div>
  )
}

export default function PreviewQueue() {
  const [previews, setPreviews] = useState([])
  const [loading, setLoading] = useState(true)
  const { subscribe } = useWebSocket()

  // Load existing PREVIEW posts from DB on mount
  const loadPending = useCallback(async () => {
    setLoading(true)
    try {
      const res = await engineApi.pendingPreviews()
      setPreviews(res.data || [])
    } catch {
      // backend may not be running yet — silent fail
      setPreviews([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPending()
  }, [loadPending])

  // Subscribe to live post_preview events from the running engine
  useEffect(() => {
    const unsub = subscribe('post_preview', (data) => {
      setPreviews((prev) => {
        // Avoid duplicate if the post is already in the queue
        if (prev.some((p) => p.post_id === data.post_id || p.url === data.url)) {
          return prev
        }
        return [
          {
            post_id: data.post_id || data.url,
            url: data.url,
            author: data.author,
            snippet: data.text || '',
            comment: data.comment || '',
            score: data.score || 0,
            created_at: new Date().toISOString(),
          },
          ...prev,
        ]
      })
    })
    return unsub
  }, [subscribe])

  const handleApprove = useCallback(async (post_id, comment_text) => {
    await engineApi.approveComment(post_id, comment_text)
    // Card stays visible showing "approved" state — it removes itself via status
  }, [])

  const handleReject = useCallback(async (post_id) => {
    await engineApi.rejectComment(post_id)
    // Card stays visible showing "rejected" state
  }, [])

  // Don't render the panel at all if there's nothing to show and loading is done
  if (!loading && previews.length === 0) {
    return null
  }

  return (
    <div className="rounded-xl border border-violet-500/20 bg-slate-800/40 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-violet-400">
            Comment Approval Queue
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Review AI-generated comments before they're posted on LinkedIn
          </p>
        </div>
        {previews.length > 0 && (
          <span className="rounded-full border border-violet-500/30 bg-violet-500/15 px-2.5 py-0.5 text-xs font-semibold text-violet-300">
            {previews.length} pending
          </span>
        )}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-4 text-sm text-slate-500">
          <Clock className="h-4 w-4 animate-pulse" />
          Loading pending previews…
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {previews.map((item) => (
            <PreviewCard
              key={item.post_id || item.url}
              item={item}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}
        </div>
      )}
    </div>
  )
}
