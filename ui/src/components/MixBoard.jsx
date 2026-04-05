import { useState, useRef } from 'react'
import { X, Loader2, Copy, Check, Send } from 'lucide-react'
import { content as contentApi } from '../api/client'

const STYLES = ['Thought Leadership', 'Story', 'Tips List', 'Question', 'Data Insight', 'Contrarian Take']
const TONES = ['Professional', 'Conversational', 'Bold', 'Educational']

const TAG_COLORS = {
  Hook:    { bg: 'bg-rose-500/20',    text: 'text-rose-300',    border: 'border-rose-400/40' },
  Stat:    { bg: 'bg-sky-500/20',     text: 'text-sky-300',     border: 'border-sky-400/40' },
  Story:   { bg: 'bg-amber-500/20',   text: 'text-amber-300',   border: 'border-amber-400/40' },
  Insight: { bg: 'bg-emerald-500/20', text: 'text-emerald-300', border: 'border-emerald-400/40' },
  Example: { bg: 'bg-violet-500/20',  text: 'text-violet-300',  border: 'border-violet-400/40' },
}
const TAGS = Object.keys(TAG_COLORS)

// Render text with highlighted segments as colored spans
function HighlightedText({ text, highlights, onRemoveHighlight }) {
  if (!highlights || highlights.length === 0) {
    return <span>{text}</span>
  }

  // Build segments: find all highlighted ranges in text
  const segments = []

  // Sort highlights by their position in the text (first occurrence)
  const positioned = highlights.map(h => ({
    ...h,
    index: text.indexOf(h.text),
  })).filter(h => h.index !== -1).sort((a, b) => a.index - b.index)

  let lastEnd = 0
  for (const h of positioned) {
    if (h.index < lastEnd) continue // skip overlapping
    if (h.index > lastEnd) {
      segments.push({ type: 'plain', text: text.slice(lastEnd, h.index) })
    }
    segments.push({ type: 'highlight', text: h.text, tag: h.tag, highlight: h })
    lastEnd = h.index + h.text.length
  }
  if (lastEnd < text.length) {
    segments.push({ type: 'plain', text: text.slice(lastEnd) })
  }

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.type === 'plain') return <span key={i}>{seg.text}</span>
        const tc = TAG_COLORS[seg.tag] || TAG_COLORS.Hook
        return (
          <span
            key={i}
            className={`cursor-pointer underline decoration-2 ${tc.text}`}
            style={{ textDecorationColor: 'currentColor' }}
            title={`${seg.tag} — click to remove`}
            onClick={() => onRemoveHighlight(seg.highlight)}
          >
            {seg.text}
          </span>
        )
      })}
    </>
  )
}

function PinnedCard({ item, onUnpin, onHighlight }) {
  const textRef = useRef(null)
  const [popover, setPopover] = useState(null) // {x, y, selectedText} or null

  const handleMouseUp = () => {
    const sel = window.getSelection()
    if (!sel || sel.isCollapsed) { setPopover(null); return }
    const selectedText = sel.toString().trim()
    if (!selectedText) { setPopover(null); return }
    // Check selection is within this card's text
    if (!textRef.current?.contains(sel.anchorNode)) { setPopover(null); return }
    const range = sel.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    const cardEl = textRef.current.closest('[data-card]')
    const cardRect = cardEl?.getBoundingClientRect() || { top: 0, left: 0 }
    setPopover({ x: rect.left - cardRect.left, y: rect.top - cardRect.top - 44, selectedText })
  }

  const handleTagClick = (tag) => {
    if (!popover?.selectedText) return
    const existing = item.highlights || []
    // Avoid exact duplicate
    if (existing.some(h => h.text === popover.selectedText && h.tag === tag)) {
      setPopover(null); return
    }
    onHighlight(item.id, [...existing, { text: popover.selectedText, tag }])
    setPopover(null)
    window.getSelection()?.removeAllRanges()
  }

  const handleRemoveHighlight = (highlight) => {
    const existing = item.highlights || []
    onHighlight(item.id, existing.filter(h => !(h.text === highlight.text && h.tag === highlight.tag)))
  }

  const sourceLabel = { LINKEDIN: 'LinkedIn', REDDIT: 'Reddit', RSS: 'RSS', HN: 'HN', MY_POST: 'My Post' }[item.source_type] || item.source_type
  const sourceBadge = {
    LINKEDIN: 'bg-sky-500/15 text-sky-400',
    REDDIT: 'bg-orange-500/15 text-orange-400',
    RSS: 'bg-blue-500/15 text-blue-400',
    HN: 'bg-amber-500/15 text-amber-400',
    MY_POST: 'bg-violet-500/15 text-violet-300',
  }[item.source_type] || 'bg-slate-700/40 text-slate-400'

  return (
    <div data-card className="relative rounded-lg border border-slate-700/40 bg-slate-800/40 p-3 flex flex-col gap-2">
      {/* Header row */}
      <div className="flex items-center justify-between gap-2">
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${sourceBadge}`}>{sourceLabel}</span>
        <button onClick={() => onUnpin(item.id)} className="text-slate-600 hover:text-slate-300 transition-colors">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Text area with selection tagging */}
      <div
        ref={textRef}
        className="relative text-xs text-slate-300 leading-relaxed cursor-text select-text"
        onMouseUp={handleMouseUp}
        title="Select text to tag"
      >
        <HighlightedText
          text={item.text}
          highlights={item.highlights || []}
          onRemoveHighlight={handleRemoveHighlight}
        />

        {/* Tag popover */}
        {popover && (
          <div
            className="absolute z-10 flex gap-1 rounded-lg border border-slate-600/60 bg-slate-800 shadow-lg p-1"
            style={{ left: Math.max(0, popover.x), top: popover.y }}
            onMouseDown={e => e.preventDefault()} // prevent selection loss
          >
            {TAGS.map(tag => {
              const tc = TAG_COLORS[tag]
              return (
                <button
                  key={tag}
                  onClick={() => handleTagClick(tag)}
                  className={`rounded px-2 py-0.5 text-[10px] font-medium border ${tc.bg} ${tc.text} ${tc.border} hover:opacity-80 transition-opacity`}
                >
                  {tag}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Existing highlights summary */}
      {(item.highlights?.length > 0) && (
        <div className="flex flex-wrap gap-1 mt-1">
          {item.highlights.map((h, i) => {
            const tc = TAG_COLORS[h.tag] || TAG_COLORS.Hook
            return (
              <span key={i} className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] border ${tc.bg} ${tc.text} ${tc.border}`}>
                {h.tag}: {h.text.slice(0, 30)}{h.text.length > 30 ? '…' : ''}
                <button onClick={() => handleRemoveHighlight(h)} className="ml-0.5 opacity-60 hover:opacity-100">×</button>
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function MixBoard({ pinnedItems, onUnpin, onHighlight, onSendToGenerator }) {
  const [brief, setBrief] = useState('')
  const [briefLoading, setBriefLoading] = useState(false)
  const [briefError, setBriefError] = useState(null)
  const [style, setStyle] = useState(STYLES[0])
  const [tone, setTone] = useState(TONES[0])
  const [wordCount, setWordCount] = useState(150)
  const [inlineResult, setInlineResult] = useState(null)
  const [generateLoading, setGenerateLoading] = useState(false)
  const [generateError, setGenerateError] = useState(null)
  const [copied, setCopied] = useState(false)

  const canBrief = pinnedItems.length > 0
  const canGenerate = brief.trim().length > 0

  const handleBuildBrief = async () => {
    setBriefLoading(true)
    setBriefError(null)
    try {
      const selections = pinnedItems.map(item => ({
        id: item.id,
        source_type: item.source_type,
        full_text: item.text,
        highlights: item.highlights || [],
      }))
      const res = await contentApi.synthesizeBrief(selections)
      setBrief(res.data.brief || '')
    } catch (e) {
      setBriefError(e.response?.data?.detail || 'Failed to build brief — try again')
    } finally {
      setBriefLoading(false)
    }
  }

  const handleGenerate = async () => {
    setGenerateLoading(true)
    setGenerateError(null)
    try {
      const myPostTopic = pinnedItems.find(i => i.source_type === 'MY_POST')?.title
      const topic = myPostTopic || pinnedItems[0]?.title || 'Business Intelligence'
      const res = await contentApi.generateFromBrief({
        brief,
        topic,
        style,
        tone,
        word_count: wordCount,
      })
      setInlineResult(res.data.post || res.data.generated_text || '')
    } catch (e) {
      setGenerateError(e.response?.data?.detail || 'Generation failed — try again')
    } finally {
      setGenerateLoading(false)
    }
  }

  const handleCopy = () => {
    if (!inlineResult) return
    navigator.clipboard.writeText(inlineResult)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Zone 1: Pinned Posts */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            Pinned Posts {pinnedItems.length > 0 && <span className="text-slate-600">({pinnedItems.length}/5)</span>}
          </h3>
          {pinnedItems.length === 0 && (
            <span className="text-[10px] text-slate-600">Pin posts from the left panel</span>
          )}
        </div>
        <div className="flex flex-col gap-2 max-h-64 overflow-y-auto pr-1">
          {pinnedItems.length === 0 && (
            <div className="rounded-lg border border-slate-700/30 border-dashed p-6 text-center text-xs text-slate-600">
              No posts pinned yet
            </div>
          )}
          {pinnedItems.map(item => (
            <PinnedCard
              key={item.id}
              item={item}
              onUnpin={onUnpin}
              onHighlight={onHighlight}
            />
          ))}
        </div>
      </div>

      {/* Zone 2: Synthesis Brief */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">Synthesis Brief</h3>
          <button
            onClick={handleBuildBrief}
            disabled={!canBrief || briefLoading}
            className="flex items-center gap-1.5 rounded-lg border border-violet-600/40 bg-violet-700/20 px-3 py-1.5 text-xs text-violet-300 hover:bg-violet-700/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            {briefLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            {briefLoading ? 'Building…' : 'Build Brief'}
          </button>
        </div>
        {briefError && (
          <p className="text-xs text-red-400">{briefError}</p>
        )}
        <div className="relative">
          <textarea
            value={brief}
            onChange={e => setBrief(e.target.value)}
            placeholder="Brief will appear here after clicking Build Brief. You can also type directly."
            rows={5}
            className="w-full rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-2 text-xs text-slate-200 placeholder-slate-600 resize-none focus:outline-none focus:ring-1 focus:ring-violet-500/60"
          />
          <span className="absolute bottom-2 right-2 text-[10px] text-slate-600 pointer-events-none">
            {brief.length}
          </span>
        </div>
      </div>

      {/* Zone 3: Generate Controls */}
      <div className="flex flex-col gap-3">
        <h3 className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">Generate</h3>

        {/* Controls row */}
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={style}
            onChange={e => setStyle(e.target.value)}
            className="rounded-lg border border-slate-700/60 bg-slate-800/60 px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:ring-1 focus:ring-violet-500/60 cursor-pointer"
          >
            {STYLES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select
            value={tone}
            onChange={e => setTone(e.target.value)}
            className="rounded-lg border border-slate-700/60 bg-slate-800/60 px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:ring-1 focus:ring-violet-500/60 cursor-pointer"
          >
            {TONES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <div className="flex items-center gap-1.5">
            <label className="text-[10px] text-slate-500">Words</label>
            <input
              type="number"
              value={wordCount}
              onChange={e => setWordCount(Math.max(80, Math.min(300, parseInt(e.target.value) || 150)))}
              min={80} max={300}
              className="w-16 rounded-lg border border-slate-700/60 bg-slate-800/60 px-2 py-1.5 text-xs text-slate-300 focus:outline-none focus:ring-1 focus:ring-violet-500/60 text-center"
            />
          </div>
        </div>

        {/* Buttons row */}
        <div className="flex gap-2">
          <button
            onClick={handleGenerate}
            disabled={!canGenerate || generateLoading}
            className="flex items-center gap-1.5 rounded-lg border border-violet-600/40 bg-violet-700/20 px-3 py-1.5 text-xs text-violet-300 hover:bg-violet-700/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            {generateLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            {generateLoading ? 'Generating…' : 'Generate here'}
          </button>
          <button
            onClick={() => onSendToGenerator(brief)}
            disabled={!canGenerate}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700/40 bg-slate-800/40 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-600/60 hover:text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            <Send className="h-3 w-3" />
            Send to Generator
          </button>
        </div>

        {generateError && (
          <p className="text-xs text-red-400">{generateError}
            <button onClick={handleGenerate} className="ml-2 underline text-red-300">Retry</button>
          </p>
        )}

        {/* Inline result */}
        {inlineResult && (
          <div className="rounded-lg border border-slate-700/50 bg-slate-900/60 p-3 flex flex-col gap-2">
            <pre className="text-xs text-slate-200 whitespace-pre-wrap font-sans leading-relaxed">{inlineResult}</pre>
            <div className="flex items-center gap-2 pt-1 border-t border-slate-700/40">
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 transition-colors"
              >
                {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
              <button
                onClick={() => onSendToGenerator(brief)}
                className="flex items-center gap-1 text-[11px] text-violet-400 hover:text-violet-300 transition-colors"
              >
                <Send className="h-3 w-3" />
                Send to Generator
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
