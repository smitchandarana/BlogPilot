import { useState, useEffect, useRef } from 'react'
import { Wand2, RotateCcw, Send, CalendarDays, Loader2, Copy, Check, X, Search, ChevronDown, ChevronUp, AlertTriangle, Sparkles, Lightbulb, ExternalLink, Trash2, Zap, Brain, Users, TrendingUp, Target } from 'lucide-react'
import { config as configApi, content as contentApi, research as researchApi, intelligence as intelligenceApi } from '../api/client'
import IdeasLab from './IdeasLab'

const DEFAULT_TOPICS = ['Business Intelligence', 'Data Analytics', 'Reporting Solutions', 'Dashboard Design', 'Power BI', 'Tableau']
const STYLES = ['Thought Leadership', 'Story', 'Tips List', 'Question', 'Data Insight', 'Contrarian Take']
const TONES = ['Professional', 'Conversational', 'Bold', 'Educational']
const HOOK_INTENTS = ['CONTRARIAN', 'QUESTION', 'STAT', 'STORY', 'TREND', 'MISTAKE']
const PROOF_TYPES = ['STAT', 'STORY', 'EXAMPLE', 'ANALOGY', 'FRAMEWORK']

const HOOK_LABELS = {
  CONTRARIAN: 'Contrarian', QUESTION: 'Question', STAT: 'Statistic',
  STORY: 'Story', TREND: 'Trend', MISTAKE: 'Mistake',
}
const HOOK_DESCRIPTIONS = {
  CONTRARIAN: 'Challenge a common belief',
  QUESTION: 'A question they\'re already asking',
  STAT: 'A surprising number or data point',
  STORY: 'Start in a specific moment',
  TREND: 'Something changing right now',
  MISTAKE: 'A common error you\'ve seen',
}

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

function InsightDrilldownModal({ patternId, patternValue, onClose, onUseInsight }) {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)

  useEffect(() => {
    intelligenceApi.patternDetail(patternId)
      .then(res => setData(res.data))
      .catch(() => setData({ insights: [] }))
      .finally(() => setLoading(false))
  }, [patternId])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-xl border border-slate-700/60 bg-slate-900 shadow-2xl flex flex-col max-h-[80vh]"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between p-4 border-b border-slate-700/40">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">Pattern Evidence</p>
            <p className="text-sm font-medium text-slate-200 leading-snug">{patternValue}</p>
          </div>
          <button onClick={onClose} className="text-slate-600 hover:text-slate-300 p-0.5 ml-3 shrink-0">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="overflow-y-auto flex-1 p-4 flex flex-col gap-3">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-8 text-xs text-slate-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading evidence…
            </div>
          )}
          {!loading && (!data?.insights || data.insights.length === 0) && (
            <p className="text-center text-xs text-slate-600 py-8">
              No supporting insights linked to this pattern yet.
            </p>
          )}
          {!loading && data?.insights?.map((ins, i) => (
            <div key={i} className="rounded-lg border border-slate-700/40 bg-slate-800/60 p-3 flex flex-col gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                {ins.hook_type && (
                  <span className="rounded px-1.5 py-0.5 text-[10px] bg-amber-500/15 text-amber-400">
                    {HOOK_LABELS[ins.hook_type] || ins.hook_type}
                  </span>
                )}
                {ins.source_type && (
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${SOURCE_STYLES[ins.source_type] || 'text-slate-400'}`}>
                    {ins.source_type}
                  </span>
                )}
                <span className="text-[10px] text-slate-600 ml-auto tabular-nums">
                  {ins.specificity_score?.toFixed(1)}/10 · {ins.source_engagement} eng
                </span>
              </div>
              {ins.key_insight && (
                <p className="text-xs text-slate-300 leading-relaxed">{ins.key_insight}</p>
              )}
              {ins.pain_point && (
                <p className="text-[11px] text-slate-500 italic">Pain: {ins.pain_point}</p>
              )}
              {ins.audience_segment && (
                <p className="text-[11px] text-slate-500">Audience: {ins.audience_segment}</p>
              )}
              <button
                onClick={() => { onUseInsight(ins); onClose(); }}
                className="self-start text-[11px] text-violet-400 hover:text-violet-300 transition-colors focus-visible:outline-none"
              >
                → Use this insight
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function IntelligencePanel({ topic, onFillPainPoint, onFillAudience, onFillHook, onUseInsight }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(true)
  const [drilldown, setDrilldown] = useState(null)

  useEffect(() => {
    if (!topic) return
    setLoading(true)
    intelligenceApi.patternsForGeneration(topic)
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [topic])

  if (loading) return (
    <div className="flex items-center justify-center gap-2 py-4 text-xs text-slate-500">
      <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading intelligence…
    </div>
  )

  const hasData = data && (
    (data.pain_points?.length > 0) ||
    (data.hooks?.length > 0) ||
    (data.audiences?.length > 0)
  )

  if (!hasData) return (
    <div className="rounded-lg border border-slate-700/40 bg-slate-900/30 p-3 text-center text-xs text-slate-600">
      No intelligence data yet for this topic.
      <br />Run Research to build your content intelligence library.
    </div>
  )

  return (
    <div className="rounded-xl border border-violet-700/30 bg-violet-950/20 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-3 hover:bg-violet-900/20 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Brain className="h-3.5 w-3.5 text-violet-400" />
          <span className="text-xs font-semibold text-violet-300">Intelligence Panel</span>
          <span className="text-[10px] text-violet-500">click to fill fields</span>
        </div>
        {open ? <ChevronUp className="h-3.5 w-3.5 text-slate-500" /> : <ChevronDown className="h-3.5 w-3.5 text-slate-500" />}
      </button>

      {open && (
        <div className="px-3 pb-3 flex flex-col gap-3">
          {data.pain_points?.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-1.5">
                <Target className="h-3 w-3 text-red-400" />
                <span className="text-[10px] uppercase tracking-wider text-slate-500">Top Pain Points</span>
              </div>
              <div className="flex flex-col gap-1">
                {data.pain_points.slice(0, 4).map((p, i) => (
                  <div key={i} className="flex items-center gap-1">
                    <button
                      onClick={() => onFillPainPoint(p.pattern_value)}
                      className="flex-1 text-left rounded-lg border border-slate-700/30 bg-slate-900/40 px-2.5 py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:border-violet-600/30 hover:bg-violet-900/20 transition-colors"
                    >
                      <span className="text-[10px] tabular-nums text-slate-600 mr-1.5">×{p.frequency}</span>
                      {p.pattern_value}
                    </button>
                    <button
                      onClick={() => setDrilldown({ id: p.id, value: p.pattern_value })}
                      className="shrink-0 rounded p-1.5 text-slate-700 hover:text-violet-400 transition-colors"
                      title="See supporting insights"
                    >
                      <Sparkles className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.hooks?.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-1.5">
                <Zap className="h-3 w-3 text-amber-400" />
                <span className="text-[10px] uppercase tracking-wider text-slate-500">Effective Hooks (by engagement)</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {data.hooks.map((h, i) => (
                  <div key={i} className="flex items-center gap-0.5">
                    <button
                      onClick={() => onFillHook(h.pattern_value)}
                      className="rounded-lg border border-slate-700/30 bg-slate-900/40 px-2.5 py-1 text-xs text-slate-400 hover:text-amber-300 hover:border-amber-600/30 hover:bg-amber-900/20 transition-colors"
                    >
                      {HOOK_LABELS[h.pattern_value] || h.pattern_value}
                      {h.avg_engagement > 0 && (
                        <span className="ml-1 text-[10px] text-slate-600">{Math.round(h.avg_engagement)} eng</span>
                      )}
                    </button>
                    <button
                      onClick={() => setDrilldown({ id: h.id, value: h.pattern_value })}
                      className="rounded p-1 text-slate-700 hover:text-amber-400 transition-colors"
                      title="See supporting insights"
                    >
                      <Sparkles className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.audiences?.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-1.5">
                <Users className="h-3 w-3 text-sky-400" />
                <span className="text-[10px] uppercase tracking-wider text-slate-500">Audience Segments</span>
              </div>
              <div className="flex flex-col gap-1">
                {data.audiences.slice(0, 3).map((a, i) => (
                  <div key={i} className="flex items-center gap-1">
                    <button
                      onClick={() => onFillAudience(a.pattern_value)}
                      className="flex-1 text-left rounded-lg border border-slate-700/30 bg-slate-900/40 px-2.5 py-1.5 text-xs text-slate-400 hover:text-sky-300 hover:border-sky-600/30 hover:bg-sky-900/20 transition-colors"
                    >
                      {a.pattern_value}
                    </button>
                    <button
                      onClick={() => setDrilldown({ id: a.id, value: a.pattern_value })}
                      className="shrink-0 rounded p-1.5 text-slate-700 hover:text-sky-400 transition-colors"
                      title="See supporting insights"
                    >
                      <Sparkles className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {drilldown && (
        <InsightDrilldownModal
          patternId={drilldown.id}
          patternValue={drilldown.value}
          onClose={() => setDrilldown(null)}
          onUseInsight={onUseInsight}
        />
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
  const [criticScores, setCriticScores] = useState(null)
  const [rewriteAttempted, setRewriteAttempted] = useState(false)
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
  const [pipelineTrace, setPipelineTrace] = useState(null)
  const [generatingFromResearch, setGeneratingFromResearch] = useState(false)

  // Structured mode state
  const [generationMode, setGenerationMode] = useState('structured') // 'quick' | 'structured'
  const [structuredInputs, setStructuredInputs] = useState({
    subtopic: '',
    pain_point: '',
    real_scenario: '',
    audience: '',
    hook_intent: 'STORY',
    belief_to_challenge: '',
    core_insight: '',
    proof_type: 'EXAMPLE',
  })

  // Duplicate warning
  const [duplicateWarning, setDuplicateWarning] = useState(null)

  // Preferences auto-fill
  const [prefsFilled, setPrefsFilled] = useState(false)
  const prefsLoadedRef = useRef(false)
  const [topPosts, setTopPosts] = useState([])

  // Manual paste / learn panel
  const [pasteOpen, setPasteOpen] = useState(false)
  const [pasteText, setPasteText] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [extractResult, setExtractResult] = useState(null)

  // Session tracking for preference learning
  const [currentSession, setCurrentSession] = useState(null)

  // Style matching — holds top posts to inject into next generate() call
  const [pendingStyleExamples, setPendingStyleExamples] = useState(null)
  const [loadingStyleMatch, setLoadingStyleMatch] = useState(false)

  // Tab state
  const [activeTab, setActiveTab] = useState('generate') // 'generate' | 'ideas-lab'
  const [briefFromIdeasLab, setBriefFromIdeasLab] = useState(null)

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

  // Auto-fill structured form from learned preferences (once per mount)
  useEffect(() => {
    if (prefsLoadedRef.current) return
    intelligenceApi.preferences().then(res => {
      const prefs = res.data
      if (!prefs.has_data) return
      prefsLoadedRef.current = true
      setStructuredInputs(prev => ({
        ...prev,
        hook_intent: prefs.default_hook || prev.hook_intent,
        audience: prefs.default_audience || prev.audience,
      }))
      if (prefs.default_style) {
        const matched = STYLES.find(s => s.toLowerCase() === prefs.default_style.toLowerCase())
        if (matched) setStyle(matched)
      }
      if (prefs.top_posts?.length > 0) setTopPosts(prefs.top_posts)
      setPrefsFilled(true)
    }).catch(() => {})
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

  const pollResearchStatus = () => {
    const interval = setInterval(async () => {
      try {
        const s = await researchApi.status()
        setResearchStatus(s.data)
        if (!s.data?.is_running) {
          clearInterval(interval)
          setResearching(false)
          await loadResearchTopics()
          await loadResearchStatus()
        }
      } catch {
        clearInterval(interval)
        setResearching(false)
      }
    }, 5000)
  }

  const triggerResearch = async () => {
    setResearching(true)
    try {
      const res = await researchApi.trigger()
      if (res.data?.status === 'started') {
        // Research is running in background — poll until complete
        pollResearchStatus()
      } else if (res.data?.status === 'already_running') {
        // Already in progress — just poll
        pollResearchStatus()
      } else {
        await loadResearchTopics()
        await loadResearchStatus()
        setResearching(false)
      }
    } catch (e) {
      alert('Research failed: ' + (e.response?.data?.detail || e.message))
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
    setPipelineTrace(null)
    setQualityInfo(null)
    setCriticScores(null)
    setRewriteAttempted(false)
    try {
      const res = await contentApi.generateV2({
        topic: researchTopic.topic,
        style,
        tone,
        word_count: wordCount,
      })
      const data = res.data
      setGenerated(data.post || '')
      setTopic(researchTopic.topic)

      // Capture pipeline trace
      if (data.insight_used || data.angle_used || data.hook_used) {
        setPipelineTrace({
          insight: data.insight_used,
          angle_used: data.angle_used,
          hook_used: data.hook_used,
          quality_score: data.quality_score,
          improvement_suggestion: data.improvement_suggestion,
        })
      }

      const qi = {}
      if (data.quality_score != null) qi.score = data.quality_score
      if (data.approved === false) qi.rejected = true
      if (data.rejection_reason) qi.reason = data.rejection_reason
      if (data.improvement_suggestion) qi.suggestion = data.improvement_suggestion
      if (Object.keys(qi).length) setQualityInfo(qi)

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

  const setStructuredField = (key, value) => {
    setStructuredInputs(prev => ({ ...prev, [key]: value }))
  }

  const handleExtractText = async () => {
    if (pasteText.trim().length < 50) {
      alert('Paste at least 50 characters of content to extract from.')
      return
    }
    setExtracting(true)
    setExtractResult(null)
    try {
      const res = await intelligenceApi.extractText(pasteText, 'MANUAL')
      setExtractResult(res.data)
      setPasteText('')
    } catch (e) {
      alert('Extraction failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setExtracting(false)
    }
  }

  const generate = async () => {
    setGenerating(true)
    setEnrichedContext(null)
    setDuplicateWarning(null)
    setQualityInfo(null)
    setCriticScores(null)
    setRewriteAttempted(false)
    setPipelineTrace(null)
    try {
      let data
      if (generationMode === 'structured') {
        const payload = {
          topic, style, tone, word_count: wordCount,
          ...structuredInputs,
          ...(pendingStyleExamples ? { style_examples: pendingStyleExamples } : {}),
        }
        const res = await contentApi.generateStructured(payload)
        setPendingStyleExamples(null)
        data = res.data
        setGenerated(data.post || '')
        // Store session inputs for later publish/schedule logging
        const session = {
          topic, style, tone,
          ...structuredInputs,
          generated_text: data.post || '',
          quality_score: data.quality_score || 0,
        }
        setCurrentSession(session)
        // Log pending session — fire and forget
        intelligenceApi.logSession({ ...session, action: 'pending' }).catch(() => {})
      } else {
        const res = await configApi.testPrompt('post', { topic, style, tone, word_count: wordCount })
        data = res.data
        setGenerated(data.output || data.post || '')
      }
      const qi = {}
      if (data.quality_score != null) qi.score = data.quality_score
      if (data.approved === false) qi.rejected = true
      if (data.rejection_reason) qi.reason = data.rejection_reason
      if (data.improvement_suggestion) qi.suggestion = data.improvement_suggestion
      if (Object.keys(qi).length) setQualityInfo(qi)
      if (data.critic_scores) setCriticScores(data.critic_scores)
      if (data.rewrite_attempted) setRewriteAttempted(data.rewrite_attempted)
    } catch (e) {
      setGenerated(`[Error generating post: ${e.response?.data?.detail || e.message}]`)
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
      // Log scheduled session for preference learning
      if (currentSession) {
        intelligenceApi.logSession({
          ...currentSession,
          final_text: generated,
          action: 'scheduled',
        }).catch(() => {})
      }
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
      // Log published session for preference learning
      if (currentSession) {
        intelligenceApi.logSession({
          ...currentSession,
          final_text: generated,
          action: 'published',
        }).catch(() => {})
      }
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

  const onSendToGenerator = (brief) => {
    setActiveTab('generate')
    setBriefFromIdeasLab(brief)
    setGenerationMode('structured')
    setStructuredInputs(prev => ({ ...prev, core_insight: brief }))
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-100">Content Studio</h1>
        <p className="mt-0.5 text-sm text-slate-500">Research trending topics, generate context-enriched LinkedIn posts.</p>
      </div>

      {/* ── Tab Bar ───────────────────────────────────────────────────── */}
      <div className="flex gap-1 rounded-lg border border-slate-700/60 bg-slate-800/40 p-1 w-fit">
        <button
          onClick={() => setActiveTab('generate')}
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
            activeTab === 'generate'
              ? 'bg-slate-700 text-slate-100 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Wand2 className="h-3.5 w-3.5" />
          Generate
        </button>
        <button
          onClick={() => setActiveTab('ideas-lab')}
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
            activeTab === 'ideas-lab'
              ? 'bg-slate-700 text-slate-100 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Lightbulb className="h-3.5 w-3.5" />
          Ideas Lab
        </button>
      </div>

      {activeTab === 'ideas-lab' ? (
        <IdeasLab onSendToGenerator={onSendToGenerator} />
      ) : (
        <>
          {briefFromIdeasLab && (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-violet-500/30 bg-violet-500/10 px-4 py-2.5">
              <div className="flex items-center gap-2 text-xs text-violet-300">
                <Lightbulb className="h-3.5 w-3.5 shrink-0" />
                Brief loaded from Ideas Lab
              </div>
              <button
                onClick={() => setBriefFromIdeasLab(null)}
                className="text-violet-400/60 hover:text-violet-300 transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

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

      {/* ── Learn from Content ───────────────────────────────────────── */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 overflow-hidden">
        <button
          onClick={() => setPasteOpen(!pasteOpen)}
          className="w-full flex items-center justify-between p-4 hover:bg-slate-800/60 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4 text-emerald-400" />
            <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">Learn from Content</h2>
            <span className="text-[10px] text-slate-600">paste a post or article to extract insights</span>
          </div>
          {pasteOpen ? <ChevronUp className="h-4 w-4 text-slate-500" /> : <ChevronDown className="h-4 w-4 text-slate-500" />}
        </button>

        {pasteOpen && (
          <div className="px-4 pb-4 flex flex-col gap-3">
            <textarea
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder="Paste a LinkedIn post, article excerpt, or any content you want to extract insights from…"
              rows={5}
              className="w-full resize-none rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-emerald-500/40 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
            />
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-slate-600">
                {pasteText.length > 0 ? `${pasteText.length} chars` : 'Min. 50 characters'}
              </span>
              <button
                onClick={handleExtractText}
                disabled={extracting || pasteText.trim().length < 50}
                className="flex items-center gap-2 rounded-lg bg-emerald-700/30 border border-emerald-600/30 px-4 py-2 text-xs font-medium text-emerald-300 hover:bg-emerald-700/40 disabled:opacity-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
              >
                {extracting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Brain className="h-3.5 w-3.5" />}
                {extracting ? 'Extracting…' : 'Extract & Learn'}
              </button>
            </div>

            {extractResult && (
              <div className="rounded-lg border border-emerald-600/20 bg-emerald-900/10 p-3 flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase tracking-wider text-emerald-500">Extracted Insight</span>
                  <button onClick={() => setExtractResult(null)} className="text-slate-600 hover:text-slate-400">
                    <X className="h-3 w-3" />
                  </button>
                </div>
                {extractResult.subtopic && (
                  <p className="text-xs text-slate-300">
                    <span className="text-slate-500">Subtopic:</span> {extractResult.subtopic}
                  </p>
                )}
                {extractResult.pain_point && (
                  <p className="text-xs text-slate-400">
                    <span className="text-slate-500">Pain point:</span> {extractResult.pain_point}
                  </p>
                )}
                {extractResult.hook_type && (
                  <p className="text-xs text-slate-400">
                    <span className="text-slate-500">Hook:</span> {HOOK_LABELS[extractResult.hook_type] || extractResult.hook_type}
                  </p>
                )}
                <div className="flex items-center gap-4 mt-1">
                  <span className="text-[10px] text-slate-600">
                    Specificity: <span className="text-slate-400">{extractResult.specificity_score?.toFixed(1)}/10</span>
                  </span>
                  <button
                    onClick={() => {
                      if (extractResult.topic) setTopic(extractResult.topic)
                      setStructuredField('subtopic', extractResult.subtopic || '')
                      setStructuredField('pain_point', extractResult.pain_point || '')
                      if (extractResult.hook_type) setStructuredField('hook_intent', extractResult.hook_type)
                      if (extractResult.audience_segment) setStructuredField('audience', extractResult.audience_segment)
                      if (extractResult.key_insight) setStructuredField('core_insight', extractResult.key_insight)
                      setGenerationMode('structured')
                      setPasteOpen(false)
                      setExtractResult(null)
                    }}
                    className="text-[10px] text-emerald-400 hover:text-emerald-300 transition-colors"
                  >
                    → Fill structured form
                  </button>
                </div>
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
            {/* Mode toggle */}
            <div className="flex rounded-lg border border-slate-700/60 overflow-hidden text-xs">
              <button
                onClick={() => setGenerationMode('quick')}
                className={`px-3 py-1.5 transition-colors ${
                  generationMode === 'quick'
                    ? 'bg-slate-700/60 text-slate-200'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                Quick
              </button>
              <button
                onClick={() => setGenerationMode('structured')}
                className={`flex items-center gap-1 px-3 py-1.5 transition-colors ${
                  generationMode === 'structured'
                    ? 'bg-violet-700/30 text-violet-300'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <Brain className="h-3 w-3" /> Structured
              </button>
            </div>
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

          {/* Topic — shared by both modes */}
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

          {/* ── STRUCTURED MODE FIELDS ── */}
          {generationMode === 'structured' && (
            <>
              {prefsFilled && (
                <div className="flex items-center justify-between rounded-lg border border-slate-700/30 bg-slate-900/40 px-3 py-2">
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
                    <TrendingUp className="h-3 w-3 text-violet-500" />
                    Defaults pre-filled from your generation history
                  </div>
                  <button
                    onClick={() => setPrefsFilled(false)}
                    className="text-slate-700 hover:text-slate-500 transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              )}

              {/* Intelligence Panel */}
              <IntelligencePanel
                topic={topic}
                onFillPainPoint={(v) => setStructuredField('pain_point', v)}
                onFillAudience={(v) => setStructuredField('audience', v)}
                onFillHook={(v) => setStructuredField('hook_intent', v)}
                onUseInsight={(ins) => {
                  if (ins.subtopic) setStructuredField('subtopic', ins.subtopic)
                  if (ins.pain_point) setStructuredField('pain_point', ins.pain_point)
                  if (ins.scenario) setStructuredField('real_scenario', ins.scenario)
                  if (ins.hook_type) setStructuredField('hook_intent', ins.hook_type)
                  if (ins.audience_segment) setStructuredField('audience', ins.audience_segment)
                  if (ins.key_insight) setStructuredField('core_insight', ins.key_insight)
                }}
              />

              {topPosts.length > 0 && (
                <button
                  onClick={async () => {
                    setLoadingStyleMatch(true)
                    try {
                      const res = await intelligenceApi.preferences()
                      const fresh = res.data?.top_posts?.length > 0 ? res.data.top_posts : topPosts
                      setPendingStyleExamples(fresh)
                      setTopPosts(fresh)
                      await generate()
                    } catch (e) {
                      setGenerated(`[Error: ${e.response?.data?.detail || e.message}]`)
                    } finally {
                      setLoadingStyleMatch(false)
                    }
                  }}
                  disabled={generating || loadingStyleMatch}
                  className="flex items-center gap-2 rounded-lg border border-emerald-700/30 bg-emerald-900/10 px-3 py-2 text-xs text-emerald-400 hover:bg-emerald-900/20 hover:border-emerald-600/40 disabled:opacity-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
                  title={`Match the style of your top ${topPosts.length} published posts`}
                >
                  {loadingStyleMatch ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                  Write like my best posts
                  <span className="ml-1 text-[10px] text-emerald-600">({topPosts.length})</span>
                </button>
              )}

              <div>
                <label className="mb-1.5 block text-xs text-slate-400">Subtopic <span className="text-slate-600">(optional — be specific)</span></label>
                <input
                  type="text"
                  value={structuredInputs.subtopic}
                  onChange={(e) => setStructuredField('subtopic', e.target.value)}
                  placeholder="e.g. KPI design for executive dashboards"
                  className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs text-slate-400">Target Audience</label>
                <input
                  type="text"
                  value={structuredInputs.audience}
                  onChange={(e) => setStructuredField('audience', e.target.value)}
                  placeholder="e.g. Finance directors at mid-market companies"
                  className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs text-slate-400">Pain Point</label>
                <textarea
                  value={structuredInputs.pain_point}
                  onChange={(e) => setStructuredField('pain_point', e.target.value)}
                  placeholder="What frustration or challenge does your audience face? Use their language."
                  rows={2}
                  className="w-full resize-none rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs text-slate-400">
                  Real Scenario <span className="text-slate-600">(optional — name a role + what happened)</span>
                </label>
                <textarea
                  value={structuredInputs.real_scenario}
                  onChange={(e) => setStructuredField('real_scenario', e.target.value)}
                  placeholder={`e.g. "A CFO found month-end numbers were wrong because sales and finance tracked revenue differently"`}
                  rows={2}
                  className="w-full resize-none rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs text-slate-400">Hook Intent</label>
                <div className="grid grid-cols-3 gap-1.5">
                  {HOOK_INTENTS.map((h) => (
                    <button
                      key={h}
                      onClick={() => setStructuredField('hook_intent', h)}
                      title={HOOK_DESCRIPTIONS[h]}
                      className={`rounded-lg border px-2 py-2 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                        structuredInputs.hook_intent === h
                          ? 'border-amber-600/50 bg-amber-700/20 text-amber-300'
                          : 'border-slate-700/40 bg-slate-900/30 text-slate-400 hover:text-slate-300'
                      }`}
                    >
                      {HOOK_LABELS[h]}
                    </button>
                  ))}
                </div>
                {structuredInputs.hook_intent && (
                  <p className="mt-1.5 text-[11px] text-slate-600 italic">{HOOK_DESCRIPTIONS[structuredInputs.hook_intent]}</p>
                )}
              </div>

              <div>
                <label className="mb-1.5 block text-xs text-slate-400">Belief to Challenge <span className="text-slate-600">(optional)</span></label>
                <input
                  type="text"
                  value={structuredInputs.belief_to_challenge}
                  onChange={(e) => setStructuredField('belief_to_challenge', e.target.value)}
                  placeholder="e.g. 'More data always leads to better decisions'"
                  className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs text-slate-400">Core Insight <span className="text-slate-600">(optional — your grounding point)</span></label>
                <textarea
                  value={structuredInputs.core_insight}
                  onChange={(e) => setStructuredField('core_insight', e.target.value)}
                  placeholder="The one thing you want readers to walk away knowing."
                  rows={2}
                  className="w-full resize-none rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs text-slate-400">Proof Type</label>
                <div className="flex flex-wrap gap-1.5">
                  {PROOF_TYPES.map((p) => (
                    <button
                      key={p}
                      onClick={() => setStructuredField('proof_type', p)}
                      className={`rounded-lg border px-3 py-1.5 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                        structuredInputs.proof_type === p
                          ? 'border-sky-600/50 bg-sky-700/20 text-sky-300'
                          : 'border-slate-700/40 bg-slate-900/30 text-slate-400 hover:text-slate-300'
                      }`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Style + Tone + Word Count — shared by both modes */}
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
            className={`flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-[background,box-shadow] duration-200 hover:shadow-[0_0_24px_rgba(124,58,237,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-60 active:scale-[0.98] ${
              generationMode === 'structured'
                ? 'bg-violet-800 hover:bg-violet-700'
                : 'bg-violet-700 hover:bg-violet-600'
            }`}
          >
            {generating ? <Loader2 className="h-4 w-4 animate-spin" /> :
              generationMode === 'structured' ? <Brain className="h-4 w-4" /> : <Wand2 className="h-4 w-4" />}
            {generating ? 'Generating…' :
              generationMode === 'structured' ? 'Generate (Structured)' : 'Generate Post'}
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

          {criticScores && (
            <div className="flex flex-wrap items-center gap-1.5">
              {rewriteAttempted && (
                <span className="flex items-center gap-1 rounded-full bg-emerald-500/15 border border-emerald-500/25 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
                  <Sparkles className="h-2.5 w-2.5" /> Auto-improved
                </span>
              )}
              {[
                { label: 'Specific', val: criticScores.specificity_score, invert: false },
                { label: 'Sharp', val: criticScores.insight_sharpness, invert: false },
                { label: 'Hook', val: criticScores.hook_strength, invert: false },
                { label: 'Generic', val: criticScores.generic_score, invert: true },
              ].map(({ label, val, invert }) => {
                const good = invert ? val <= 3 : val >= 7
                const mid = invert ? val <= 5 : val >= 5
                const cls = good
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                  : mid
                  ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                  : 'bg-red-500/10 border-red-500/20 text-red-400'
                return (
                  <span key={label} className={`rounded-full px-2 py-0.5 text-[10px] font-medium border ${cls}`}>
                    {label}: {val}
                  </span>
                )
              })}
            </div>
          )}

          {pipelineTrace && (
            <div className="rounded-lg border border-violet-500/20 bg-violet-950/20 p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-violet-400 text-sm">✦</span>
                <h3 className="text-xs font-semibold uppercase tracking-widest text-violet-400">Pipeline Trace</h3>
              </div>
              <div className="flex flex-col gap-2.5">
                {pipelineTrace.insight && (
                  <div className="flex gap-3">
                    <span className="text-[10px] uppercase tracking-wider text-slate-500 w-14 shrink-0 pt-0.5">Insight</span>
                    <p className="text-xs text-slate-300 leading-relaxed line-clamp-2">
                      {pipelineTrace.insight.key_insight || pipelineTrace.insight.subtopic || '—'}
                    </p>
                  </div>
                )}
                {pipelineTrace.angle_used && (
                  <div className="flex gap-3 items-start">
                    <span className="text-[10px] uppercase tracking-wider text-slate-500 w-14 shrink-0 pt-0.5">Angle</span>
                    <span className="inline-flex items-center rounded-md bg-violet-500/15 px-2 py-0.5 text-[11px] font-medium text-violet-300 border border-violet-500/20">
                      {pipelineTrace.angle_used}
                    </span>
                  </div>
                )}
                <div className="flex gap-3 items-center">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 w-14 shrink-0">Hook</span>
                  <div className="flex items-center gap-2">
                    {pipelineTrace.hook_used && (
                      <span className="inline-flex items-center rounded-md bg-slate-700/60 px-2 py-0.5 text-[11px] font-medium text-slate-300">
                        {pipelineTrace.hook_used}
                      </span>
                    )}
                    {pipelineTrace.quality_score != null && (
                      <span className={`text-xs font-semibold ${
                        pipelineTrace.quality_score >= 7 ? 'text-emerald-400' :
                        pipelineTrace.quality_score >= 5 ? 'text-amber-400' : 'text-red-400'
                      }`}>
                        {pipelineTrace.quality_score.toFixed(1)}/10
                        {pipelineTrace.quality_score >= 7 ? ' ✓' : ''}
                      </span>
                    )}
                  </div>
                </div>
                {pipelineTrace.improvement_suggestion && (
                  <div className="flex gap-3">
                    <span className="text-[10px] uppercase tracking-wider text-slate-500 w-14 shrink-0 pt-0.5">Tip</span>
                    <p className="text-xs text-slate-400 italic leading-relaxed">
                      → {pipelineTrace.improvement_suggestion}
                    </p>
                  </div>
                )}
              </div>
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
        </>
      )}
    </div>
  )
}
