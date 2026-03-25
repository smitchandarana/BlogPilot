import { useState, useEffect, useRef, useCallback } from 'react'
import { Search, Loader2, Check, Lightbulb } from 'lucide-react'
import { content as contentApi } from '../api/client'

const SOURCE_BADGE = {
  LINKEDIN: 'bg-sky-500/15 text-sky-400',
  REDDIT: 'bg-orange-500/15 text-orange-400',
  RSS: 'bg-blue-500/15 text-blue-400',
  HN: 'bg-amber-500/15 text-amber-400',
  MY_POST: 'bg-violet-500/15 text-violet-300',
}
const SOURCE_LABEL = {
  LINKEDIN: 'LinkedIn', REDDIT: 'Reddit', RSS: 'RSS', HN: 'HN', MY_POST: 'My Post',
}

const SOURCES = ['all', 'linkedin', 'reddit', 'rss', 'my_posts']
const SOURCE_CHIP_LABELS = { all: 'All', linkedin: 'LinkedIn', reddit: 'Reddit', rss: 'RSS', my_posts: 'My Posts' }

function formatShortDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  } catch { return '' }
}

export default function IdeaPoolPanel({ pinnedItems, onPin }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [topicInput, setTopicInput] = useState('')
  const [activeTopic, setActiveTopic] = useState('')
  const [activeSource, setActiveSource] = useState('all')
  const debounceRef = useRef(null)

  const pinnedIds = new Set(pinnedItems.map(p => p.id))
  const atMax = pinnedItems.length >= 5

  const fetchPool = useCallback(async (q, source, topic) => {
    setLoading(true)
    try {
      const params = { limit: 30 }
      if (q) params.q = q
      if (source && source !== 'all') params.source = source
      if (topic) params.topic = topic
      const res = await contentApi.ideaPool(params)
      setItems(res.data)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPool('', 'all', '')
    return () => clearTimeout(debounceRef.current)
  }, [fetchPool])

  const handleSearchChange = (e) => {
    const q = e.target.value
    setSearchQuery(q)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      fetchPool(q, activeSource, activeTopic)
    }, 300)
  }

  const handleSourceClick = (src) => {
    setActiveSource(src)
    fetchPool(searchQuery, src, activeTopic)
  }

  const handleSurfaceIdeas = () => {
    setActiveTopic(topicInput)
    fetchPool(searchQuery, activeSource, topicInput)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSurfaceIdeas()
  }

  const isEmpty = !loading && items.length === 0

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500 pointer-events-none" />
        <input
          type="text"
          value={searchQuery}
          onChange={handleSearchChange}
          placeholder="Search posts…"
          className="w-full rounded-lg border border-slate-700/60 bg-slate-800/60 pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-violet-500/60"
        />
      </div>

      {/* Topic surfacing */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Lightbulb className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500 pointer-events-none" />
          <input
            type="text"
            value={topicInput}
            onChange={e => setTopicInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Surface ideas by topic…"
            className="w-full rounded-lg border border-slate-700/60 bg-slate-800/60 pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-violet-500/60"
          />
        </div>
        <button
          onClick={handleSurfaceIdeas}
          disabled={!topicInput.trim()}
          className="shrink-0 rounded-lg border border-violet-600/40 bg-violet-700/20 px-3 py-2 text-xs text-violet-300 hover:bg-violet-700/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
        >
          Surface
        </button>
      </div>

      {/* Source chips */}
      <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-none">
        {SOURCES.map(src => (
          <button
            key={src}
            onClick={() => handleSourceClick(src)}
            className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
              activeSource === src
                ? 'bg-violet-600/30 text-violet-200 border border-violet-500/40'
                : 'bg-slate-800/60 text-slate-400 border border-slate-700/40 hover:text-slate-200'
            }`}
          >
            {SOURCE_CHIP_LABELS[src]}
          </button>
        ))}
      </div>

      {/* Card list */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-2 pr-1 min-h-0">
        {loading && (
          <div className="flex items-center justify-center gap-2 py-12 text-xs text-slate-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
          </div>
        )}
        {!loading && isEmpty && activeSource === 'linkedin' && (
          <p className="text-center py-12 text-xs text-slate-500 leading-relaxed">
            No posts scanned yet — start the engine to scan LinkedIn
          </p>
        )}
        {!loading && isEmpty && activeSource !== 'linkedin' && (
          <p className="text-center py-12 text-xs text-slate-500">
            No posts found — try a different keyword or source
          </p>
        )}
        {!loading && items.map(item => {
          const isPinned = pinnedIds.has(item.id)
          const disablePin = atMax && !isPinned
          const displayText = item.title || item.text.slice(0, 80) + (item.text.length > 80 ? '…' : '')
          const badgeClass = SOURCE_BADGE[item.source_type] || 'bg-slate-700/40 text-slate-400'
          const badgeLabel = SOURCE_LABEL[item.source_type] || item.source_type

          return (
            <div
              key={item.id}
              className="rounded-lg border border-slate-700/40 bg-slate-800/40 p-3 flex flex-col gap-2 hover:border-slate-600/60 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${badgeClass}`}>
                      {badgeLabel}
                    </span>
                    <span className="text-[10px] text-slate-600">{item.engagement_score > 0 ? `${item.engagement_score.toFixed(0)} eng` : ''}</span>
                    <span className="text-[10px] text-slate-600 ml-auto">{formatShortDate(item.date)}</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-snug line-clamp-2">{displayText}</p>
                </div>
              </div>
              <div className="flex justify-end">
                {isPinned ? (
                  <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
                    <Check className="h-3 w-3" /> Pinned
                  </span>
                ) : (
                  <button
                    onClick={() => onPin(item)}
                    disabled={disablePin}
                    title={disablePin ? 'Unpin a post to add another' : 'Pin this post'}
                    className="text-[11px] text-slate-400 hover:text-violet-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500"
                  >
                    Pin
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
