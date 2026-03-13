import { useState, useEffect } from 'react'
import { Wand2, RotateCcw, Send, CalendarDays, Loader2, Copy, Check, X, Search, ChevronDown, ChevronUp, AlertTriangle, Sparkles, Lightbulb, ExternalLink, Trash2 } from 'lucide-react'
import { config as configApi, content as contentApi, research as researchApi } from '../api/client'

const DEFAULT_TOPICS = ['Business Intelligence', 'Data Analytics', 'Reporting Solutions', 'Dashboard Design', 'Power BI', 'Tableau']
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

const SOURCE_STYLES = {
  REDDIT: 'bg-orange-500/15 text-orange-400',
  RSS: 'bg-blue-500/15 text-blue-400',
  HN: 'bg-amber-500/15 text-amber-400',
  LINKEDIN: 'bg-sky-500/15 text-sky-400',
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

function ScoreBar({ score, label, color }) {
  const pct = Math.min(100, Math.max(0, score * 10))
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-slate-500 w-16 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-slate-700/50 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] tabular-nums text-slate-400 w-6 text-right">{score.toFixed(1)}</span>
    </div>
  )
}

function ResearchTopicCard({ topic, onGenerate, onDismiss }) {
  const [expanded, setExpanded] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [snippets, setSnippets] = useState(null)

  const scoreColor = topic.composite_score >= 7 ? 'bg-emerald-500' :
    topic.composite_score >= 5 ? 'bg-amber-500' : 'bg-red-500'

  const handleExpand = async () => {
    if (!expanded && !snippets) {
      setLoadingDetail(true)
      try {
        const res = await researchApi.topicDetail(topic.id)
        setSnippets(res.data.snippets || [])
      } catch { setSnippets([]) }
      finally { setLoadingDetail(false) }
    }
    setExpanded(!expanded)
  }

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {topic.domain && (
            <span className="inline-block rounded px-1.5 py-0.5 text-[10px] font-medium bg-slate-700/40 text-slate-500 mb-1">
              {topic.domain}
            </span>
          )}
          <h3 className="text-sm font-medium text-slate-200 truncate">{topic.topic}</h3>
          <div className="mt-1 flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${scoreColor}`} />
            <span className="text-xs tabular-nums text-slate-400">{topic.composite_score.toFixed(1)}/10</span>
            <span className="text-[10px] text-slate-600">•</span>
            <span className="text-[10px] text-slate-500">{topic.snippet_count} sources</span>
          </div>
        </div>
        <button
          onClick={() => onDismiss(topic.id)}
          className="text-slate-600 hover:text-slate-400 transition-colors p-0.5"
          title="Dismiss"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex flex-col gap-1">
        <ScoreBar score={topic.trending_score} label="Trending" color="bg-violet-500" />
        <ScoreBar score={topic.engagement_score} label="Engage" color="bg-emerald-500" />
        <ScoreBar score={topic.content_gap_score} label="Gap" color="bg-amber-500" />
        <ScoreBar score={topic.relevance_score} label="Relevant" color="bg-sky-500" />
      </div>

      {topic.suggested_angle && (
        <p className="text-xs text-slate-400 italic leading-relaxed line-clamp-2">
          <Lightbulb className="inline h-3 w-3 mr-1 text-amber-500/70" />
          {topic.suggested_angle}
        </p>
      )}

      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={() => onGenerate(topic)}
          className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-violet-700/20 border border-violet-600/30 px-3 py-1.5 text-xs text-violet-300 hover:bg-violet-700/30 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
        >
          <Sparkles className="h-3 w-3" />
          Generate Post
        </button>
        <button
          onClick={handleExpand}
          className="flex items-center gap-1 rounded-lg border border-slate-700/40 px-2.5 py-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
        >
          {loadingDetail ? <Loader2 className="h-3 w-3 animate-spin" /> :
            expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          Sources
        </button>
      </div>

      {expanded && snippets && (
        <div className="mt-1 flex flex-col gap-1.5 max-h-48 overflow-y-auto pr-1">
          {snippets.length === 0 ? (
            <p className="text-xs text-slate-600 text-center py-2">No source snippets</p>
          ) : snippets.map((s, i) => (
            <div key={i} className="rounded-lg bg-slate-900/50 border border-slate-700/30 p-2">
              <div className="flex items-center gap-1.5 mb-1">
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${SOURCE_STYLES[s.source] || 'text-slate-400'}`}>
                  {s.source}
                </span>
                <span className="text-[10px] text-slate-500 tabular-nums">{s.engagement_signal} eng</span>
              </div>
              <p className="text-xs text-slate-400 line-clamp-2">{s.title}</p>
              {s.source_url && (
                <a href={s.source_url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-0.5 text-[10px] text-slate-600 hover:text-slate-400 mt-1">
                  <ExternalLink className="h-2.5 w-2.5" /> Link
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ContentStudio() {
  const [topics, setTopics] = useState(DEFAULT_TOPICS)
  const [topic, setTopic] = useState(DEFAULT_TOPICS[0])
  const [style, setStyle] = useState(STYLES[0])
  const [tone, setTone] = useState(TONES[0])
  const [wordCount, setWordCount] = useState(150)
  const [generating, setGenerating] = useState(false)
  const [generated, setGenerated] = useState('')
  const [qualityInfo, setQualityInfo] = useState(null)
  const [copied, setCopied] = useState(false)

  const [showScheduler, setShowScheduler] = useState(false)
  const [scheduledAt, setScheduledAt] = useState('')
  const [scheduling, setScheduling] = useState(false)
  const [publishing, setPublishing] = useState(false)

  const [queue, setQueue] = useState([])
  const [queueLoading, setQueueLoading] = useState(true)

  // Research state
  const [researchTopics, setResearchTopics] = useState([])
  const [researchLoading, setResearchLoading] = useState(false)
  const [researching, setResearching] = useState(false)
  const [researchStatus, setResearchStatus] = useState(null)
  const [researchOpen, setResearchOpen] = useState(true)
  const [enrichedContext, setEnrichedContext] = useState(null)
  const [generatingFromResearch, setGeneratingFromResearch] = useState(false)

  // Duplicate warning
  const [duplicateWarning, setDuplicateWarning] = useState(null)

  useEffect(() => {
    configApi.getTopics().then((res) => {
      const t = res.data
      if (Array.isArray(t) && t.length > 0) {
        setTopics(t)
        setTopic(t[0])
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    fetchQueue()
    const id = setInterval(fetchQueue, 30_000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    loadResearchTopics()
    loadResearchStatus()
  }, [])

  const loadResearchTopics = async () => {
    setResearchLoading(true)
    try {
      const res = await researchApi.topics()
      setResearchTopics(res.data || [])
    } catch { /* keep existing */ }
    finally { setResearchLoading(false) }
  }

  const loadResearchStatus = async () => {
    try {
      const res = await researchApi.status()
      setResearchStatus(res.data)
    } catch { /* ignore */ }
  }

  const triggerResearch = async () => {
    setResearching(true)
    try {
      await researchApi.trigger()
      await loadResearchTopics()
      await loadResearchStatus()
    } catch (e) {
      alert('Research failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setResearching(false)
    }
  }

  const dismissResearchTopic = async (id) => {
    try {
      await researchApi.dismiss(id)
      setResearchTopics(prev => prev.filter(t => t.id !== id))
    } catch { /* ignore */ }
  }

  const clearAllResearchTopics = async () => {
    if (!confirm('Clear all researched topics? This cannot be undone.')) return
    try {
      await researchApi.clearAll()
      setResearchTopics([])
    } catch (e) {
      alert('Failed to clear: ' + (e.response?.data?.detail || e.message))
    }
  }

  const generateFromResearchTopic = async (researchTopic) => {
    setGeneratingFromResearch(true)
    setEnrichedContext({ topicId: researchTopic.id, topicName: researchTopic.topic, angle: researchTopic.suggested_angle })
    setDuplicateWarning(null)
    try {
      const res = await researchApi.generateFromTopic(researchTopic.id, {
        style, tone, word_count: wordCount,
      })
      const data = res.data
      setGenerated(data.post || '')
      setTopic(researchTopic.topic)

      if (data.is_duplicate) {
        setDuplicateWarning({
          similarity: data.duplicate_similarity,
          preview: data.duplicate_preview,
        })
      }
    } catch (e) {
      setGenerated(`[Error: ${e.response?.data?.detail || e.message}]`)
    } finally {
      setGeneratingFromResearch(false)
    }
  }

  const fetchQueue = async () => {
    try {
      const res = await contentApi.getQueue()
      setQueue(res.data || [])
    } catch { }
    finally { setQueueLoading(false) }
  }

  const generate = async () => {
    setGenerating(true)
    setEnrichedContext(null)
    setDuplicateWarning(null)
    setQualityInfo(null)
    try {
      const res = await configApi.testPrompt('post', { topic, style, tone, word_count: wordCount })
      setGenerated(res.data.output || '')
      const qi = {}
      if (res.data.quality_score != null) qi.score = res.data.quality_score
      if (res.data.rejected) qi.rejected = true
      if (res.data.rejection_reason) qi.reason = res.data.rejection_reason
      if (res.data.improvement_suggestion) qi.suggestion = res.data.improvement_suggestion
      if (Object.keys(qi).length) setQualityInfo(qi)
    } catch (e) {
      setGenerated(`[Error generating post: ${e.response?.data?.output || e.message}]`)
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
        text: generated, topic, style, tone,
        scheduled_at: new Date(scheduledAt).toISOString(),
      })
      setShowScheduler(false)
      setScheduledAt('')
      setDuplicateWarning(null)
      fetchQueue()
    } catch (e) {
      const detail = e.response?.data?.detail
      if (typeof detail === 'object' && detail?.message?.includes('duplicate')) {
        setDuplicateWarning({ similarity: detail.similarity, preview: detail.matching_preview })
      } else {
        alert('Failed to schedule: ' + (typeof detail === 'string' ? detail : e.message))
      }
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
      setDuplicateWarning(null)
      fetchQueue()
    } catch (e) {
      const detail = e.response?.data?.detail
      if (typeof detail === 'object' && detail?.message?.includes('duplicate')) {
        setDuplicateWarning({ similarity: detail.similarity, preview: detail.matching_preview })
      } else {
        alert('Failed: ' + (typeof detail === 'string' ? detail : e.message))
      }
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
        <p className="mt-0.5 text-sm text-slate-500">Research trending topics, generate context-enriched LinkedIn posts.</p>
      </div>

      {/* ── Research Panel ───────────────────────────────────────────── */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 overflow-hidden">
        <button
          onClick={() => setResearchOpen(!researchOpen)}
          className="w-full flex items-center justify-between p-4 hover:bg-slate-800/60 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-violet-400" />
            <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">Topic Research</h2>
            {researchTopics.length > 0 && (
              <span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-[10px] tabular-nums text-violet-300">
                {researchTopics.length}
              </span>
            )}
          </div>
          {researchOpen ? <ChevronUp className="h-4 w-4 text-slate-500" /> : <ChevronDown className="h-4 w-4 text-slate-500" />}
        </button>

        {researchOpen && (
          <div className="px-4 pb-4 flex flex-col gap-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <button
                  onClick={triggerResearch}
                  disabled={researching}
                  className="flex items-center gap-2 rounded-lg bg-violet-700 px-4 py-2 text-xs font-medium text-white shadow-[0_0_12px_rgba(124,58,237,0.15)] hover:bg-violet-600 hover:shadow-[0_0_20px_rgba(124,58,237,0.25)] disabled:opacity-50 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 active:scale-[0.98]"
                >
                  {researching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
                  {researching ? 'Researching…' : 'Run Research'}
                </button>
                {researchTopics.length > 0 && (
                  <button
                    onClick={clearAllResearchTopics}
                    className="flex items-center gap-1.5 rounded-lg border border-red-700/30 px-3 py-2 text-xs text-red-400/70 hover:text-red-400 hover:border-red-600/40 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                  >
                    <Trash2 className="h-3 w-3" />
                    Clear All
                  </button>
                )}
              </div>
              <div className="text-xs text-slate-600">
                {researchStatus?.last_run
                  ? `Last: ${formatDate(researchStatus.last_run)}`
                  : 'Never run'}
                {researchStatus?.scan_interval_hours && (
                  <span className="ml-2">• every {researchStatus.scan_interval_hours}h</span>
                )}
              </div>
            </div>

            {researchLoading ? (
              <div className="py-8 text-center text-sm text-slate-500 flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading research…
              </div>
            ) : researchTopics.length === 0 ? (
              <div className="py-8 text-center text-sm text-slate-600">
                No research data yet. Click "Run Research" to discover trending topics from Reddit, RSS feeds, and your LinkedIn feed.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {researchTopics.map(rt => (
                  <ResearchTopicCard
                    key={rt.id}
                    topic={rt}
                    onGenerate={generateFromResearchTopic}
                    onDismiss={dismissResearchTopic}
                  />
                ))}
              </div>
            )}

            {generatingFromResearch && (
              <div className="flex items-center justify-center gap-2 py-3 text-sm text-violet-300">
                <Loader2 className="h-4 w-4 animate-spin" /> Generating context-enriched post…
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Generator + Output ───────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left — Generator controls */}
        <div className="flex flex-col gap-5 rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Generate Post</h2>
            {enrichedContext && (
              <span className="flex items-center gap-1 rounded-full bg-violet-500/15 px-2.5 py-0.5 text-[10px] text-violet-300">
                <Sparkles className="h-3 w-3" /> Context-enriched
              </span>
            )}
          </div>

          {enrichedContext && (
            <div className="rounded-lg border border-violet-600/20 bg-violet-900/10 p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] uppercase tracking-wider text-violet-400/70">Research Context</span>
                <button onClick={() => setEnrichedContext(null)} className="text-slate-600 hover:text-slate-400">
                  <X className="h-3 w-3" />
                </button>
              </div>
              <p className="text-xs text-slate-400">
                Topic: <span className="text-slate-300">{enrichedContext.topicName}</span>
              </p>
              {enrichedContext.angle && (
                <p className="text-xs text-slate-500 mt-0.5 italic">{enrichedContext.angle}</p>
              )}
            </div>
          )}

          <div>
            <label className="mb-1.5 block text-xs text-slate-400">Topic</label>
            <select
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
            >
              {topics.map((t) => <option key={t} value={t}>{t}</option>)}
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

          {duplicateWarning && (
            <div className="rounded-lg border border-amber-600/30 bg-amber-900/15 p-3 flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-medium text-amber-300">
                  Duplicate detected ({(duplicateWarning.similarity * 100).toFixed(0)}% match)
                </p>
                {duplicateWarning.preview && (
                  <p className="text-[11px] text-amber-400/60 mt-1 line-clamp-2">{duplicateWarning.preview}</p>
                )}
                <p className="text-[10px] text-slate-500 mt-1">You can still publish — click "Post Now" to proceed anyway.</p>
              </div>
            </div>
          )}

          <textarea
            value={generated}
            onChange={(e) => setGenerated(e.target.value)}
            placeholder="Generated post will appear here…"
            maxLength={3000}
            className="flex-1 min-h-[220px] resize-none rounded-lg border border-slate-700/60 bg-slate-900/60 p-3 text-sm leading-relaxed text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
          />

          {qualityInfo && (
            <div className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs ${
              qualityInfo.rejected ? 'bg-red-500/10 border border-red-500/30 text-red-400' :
              qualityInfo.score >= 7 ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400' :
              'bg-amber-500/10 border border-amber-500/30 text-amber-400'
            }`}>
              <span className="font-semibold">Quality: {qualityInfo.score?.toFixed(1) || '—'}/10</span>
              {qualityInfo.rejected && <span>— Rejected: {qualityInfo.reason}</span>}
              {qualityInfo.suggestion && !qualityInfo.rejected && <span>— {qualityInfo.suggestion}</span>}
            </div>
          )}

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

      {/* ── Post Queue ───────────────────────────────────────────────── */}
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
