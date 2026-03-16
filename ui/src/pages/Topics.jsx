import { useState, useEffect, useCallback } from 'react'
import { X, Plus, Save, Loader2, CheckCircle2, Play, Pause, RotateCcw, ChevronUp, ChevronDown, Clock } from 'lucide-react'
import { config as configApi } from '../api/client'

const INDUSTRIES = [
  'Manufacturing', 'Retail & E-Commerce', 'Financial Services & Banking',
  'Healthcare & Pharmaceuticals', 'Logistics & Supply Chain', 'Real Estate',
  'Information Technology', 'Consulting', 'Education', 'Hospitality',
  'Automotive', 'FMCG / Consumer Goods', 'Professional Services',
]

const DEFAULT_TOPICS = ['Business Intelligence', 'Data Analytics', 'Reporting Solutions', 'Dashboard Design', 'Data Visualization']
const DEFAULT_HASHTAGS = ['#businessintelligence', '#dataanalytics', '#powerbi', '#tableau', '#dataviz']
const DEFAULT_BLACKLIST = ['looking for a job', 'open to work', 'hiring', 'crypto', 'NFT']

function TagInput({ tags, onAdd, onRemove, placeholder, colorClass = 'bg-violet-700/20 text-violet-300 border-violet-600/30' }) {
  const [value, setValue] = useState('')

  const add = () => {
    const trimmed = value.trim()
    if (trimmed && !tags.includes(trimmed)) {
      onAdd(trimmed)
      setValue('')
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1.5">
        {tags.map((tag) => (
          <span
            key={tag}
            className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-medium ${colorClass}`}
          >
            {tag}
            <button
              onClick={() => onRemove(tag)}
              className="ml-0.5 rounded opacity-60 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-current"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
          placeholder={placeholder}
          className="flex-1 rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
        />
        <button
          onClick={add}
          className="flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-slate-700/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 active:scale-[0.98]"
        >
          <Plus className="h-3.5 w-3.5" />
          Add
        </button>
      </div>
    </div>
  )
}

function SectionCard({ title, description, children }) {
  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-slate-200">{title}</h2>
        {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
      </div>
      {children}
    </div>
  )
}

/* ── Rate badge helper ──────────────────────────────────────────────── */
function RateBadge({ value, suffix = '%' }) {
  const pct = (value * 100).toFixed(0)
  let cls = 'bg-red-700/20 text-red-300 border-red-600/30'
  if (value > 0.3) cls = 'bg-emerald-700/20 text-emerald-300 border-emerald-600/30'
  else if (value >= 0.15) cls = 'bg-amber-700/20 text-amber-300 border-amber-600/30'
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-semibold tabular-nums ${cls}`}>
      {pct}{suffix}
    </span>
  )
}

function ScoreBadge({ value }) {
  return (
    <span className="inline-block rounded border border-blue-600/30 bg-blue-700/20 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-blue-300">
      {Number(value).toFixed(1)}
    </span>
  )
}

/* ── Toast component ────────────────────────────────────────────────── */
function Toast({ message, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 3000)
    return () => clearTimeout(t)
  }, [onClose])
  return (
    <div className="fixed bottom-6 right-6 z-50 rounded-lg border border-emerald-600/40 bg-emerald-900/80 px-4 py-2.5 text-sm text-emerald-200 shadow-lg">
      {message}
    </div>
  )
}

export default function Topics() {
  const [topics, setTopics] = useState(DEFAULT_TOPICS)
  const [hashtags, setHashtags] = useState(DEFAULT_HASHTAGS)
  const [blacklist, setBlacklist] = useState(DEFAULT_BLACKLIST)
  const [industries, setIndustries] = useState(['Manufacturing', 'Information Technology', 'Financial Services & Banking'])
  const [minScore, setMinScore] = useState(6)
  const [influencers, setInfluencers] = useState([])
  const [competitors, setCompetitors] = useState([])
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Sprint 9 — topic rotation state
  const [topicData, setTopicData] = useState({ active: [], paused: [], available: [] })
  const [performance, setPerformance] = useState([])
  const [cycleReport, setCycleReport] = useState(null)
  const [cycleLoading, setCycleLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const [expandedAvailable, setExpandedAvailable] = useState(null) // topic being activated
  const [suggestedHashtags, setSuggestedHashtags] = useState([])
  const [checkedHashtags, setCheckedHashtags] = useState({})
  const [sortCol, setSortCol] = useState('engagement_rate')
  const [sortDir, setSortDir] = useState('desc')

  // ── Data fetching ──────────────────────────────────────────────────
  const fetchTopicData = useCallback(() => {
    configApi.getAllTopics().then((res) => setTopicData(res.data)).catch(() => {})
  }, [])

  const fetchPerformance = useCallback(() => {
    configApi.topicPerformance().then((res) => setPerformance(res.data)).catch(() => {})
  }, [])

  useEffect(() => {
    configApi.getTopics().then((res) => {
      if (Array.isArray(res.data) && res.data.length) setTopics(res.data)
    }).catch(() => {})
    configApi.getSettings().then((res) => {
      const d = res.data
      if (d?.feed_engagement?.min_relevance_score != null) setMinScore(d.feed_engagement.min_relevance_score)
      if (Array.isArray(d?.hashtags) && d.hashtags.length) setHashtags(d.hashtags)
      if (Array.isArray(d?.keyword_blacklist) && d.keyword_blacklist.length) setBlacklist(d.keyword_blacklist)
      if (Array.isArray(d?.target_industries) && d.target_industries.length) setIndustries(d.target_industries)
      if (Array.isArray(d?.influencer_watchlist)) setInfluencers(d.influencer_watchlist)
      if (Array.isArray(d?.competitor_watchlist)) setCompetitors(d.competitor_watchlist)
    }).catch(() => {})
    fetchTopicData()
    fetchPerformance()
  }, [fetchTopicData, fetchPerformance])

  // Auto-refresh performance table every 60s
  useEffect(() => {
    const iv = setInterval(fetchPerformance, 60000)
    return () => clearInterval(iv)
  }, [fetchPerformance])

  const toggleIndustry = (ind) =>
    setIndustries((prev) => prev.includes(ind) ? prev.filter((i) => i !== ind) : [...prev, ind])

  const handleSave = async () => {
    setSaving(true)
    try {
      await configApi.updateTopics(topics)
      await configApi.updateSettings({
        feed_engagement: { min_relevance_score: minScore },
        hashtags,
        keyword_blacklist: blacklist,
        target_industries: industries,
        influencer_watchlist: influencers,
        competitor_watchlist: competitors,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch {
      /* TODO: show error */
    } finally {
      setSaving(false)
    }
  }

  // ── Topic rotation actions ─────────────────────────────────────────
  const handleActivate = async (topic) => {
    try {
      await configApi.activateTopic(topic)
      setExpandedAvailable(null)
      setSuggestedHashtags([])
      fetchTopicData()
      fetchPerformance()
      setToast(`Topic "${topic}" activated`)
    } catch {
      setToast('Activation failed')
    }
  }

  const handleDeactivate = async (topic) => {
    try {
      await configApi.deactivateTopic(topic)
      fetchTopicData()
      fetchPerformance()
      setToast(`Topic "${topic}" paused`)
    } catch {
      setToast('Pause failed')
    }
  }

  const handleShowHashtags = async (topic) => {
    if (expandedAvailable === topic) {
      setExpandedAvailable(null)
      return
    }
    setExpandedAvailable(topic)
    try {
      const res = await configApi.hashtagSuggestions(topic)
      const tags = res.data.hashtags || []
      setSuggestedHashtags(tags)
      const checks = {}
      tags.forEach((h) => { checks[h] = true })
      setCheckedHashtags(checks)
    } catch {
      setSuggestedHashtags([])
    }
  }

  const handleRunIteration = async () => {
    setCycleLoading(true)
    try {
      const res = await configApi.runIteration()
      setCycleReport(res.data)
      fetchTopicData()
      fetchPerformance()
      const a = res.data.topics_activated?.length || 0
      const p = res.data.topics_paused?.length || 0
      setToast(`Cycle complete — ${a} activated, ${p} paused`)
    } catch {
      setToast('Cycle failed — check logs')
    } finally {
      setCycleLoading(false)
    }
  }

  // ── Sorting helper ─────────────────────────────────────────────────
  const toggleSort = (col) => {
    if (sortCol === col) setSortDir((d) => d === 'desc' ? 'asc' : 'desc')
    else { setSortCol(col); setSortDir('desc') }
  }

  const sortedPerformance = [...performance].sort((a, b) => {
    const av = a[sortCol] ?? 0
    const bv = b[sortCol] ?? 0
    return sortDir === 'desc' ? bv - av : av - bv
  })

  const SortIcon = ({ col }) => {
    if (sortCol !== col) return null
    return sortDir === 'desc'
      ? <ChevronDown className="ml-0.5 inline h-3 w-3" />
      : <ChevronUp className="ml-0.5 inline h-3 w-3" />
  }

  // ── Countdown timer ────────────────────────────────────────────────
  const [countdown, setCountdown] = useState('')
  useEffect(() => {
    if (!cycleReport?.cycle_timestamp) { setCountdown(''); return }
    const update = () => {
      const last = new Date(cycleReport.cycle_timestamp).getTime()
      const next = last + 24 * 60 * 60 * 1000
      const diff = next - Date.now()
      if (diff <= 0) { setCountdown('Due now'); return }
      const h = Math.floor(diff / 3600000)
      const m = Math.floor((diff % 3600000) / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      setCountdown(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`)
    }
    update()
    const iv = setInterval(update, 1000)
    return () => clearInterval(iv)
  }, [cycleReport])

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* ── Header + Save ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-100">Topics</h1>
          <p className="mt-0.5 text-sm text-slate-500">Configure what content to engage with.</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-[background,box-shadow] duration-200 hover:bg-violet-600 hover:shadow-[0_0_24px_rgba(124,58,237,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-60 active:scale-[0.98]"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : saved ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <Save className="h-4 w-4" />}
          {saved ? 'Saved' : 'Save Changes'}
        </button>
      </div>

      {/* ── Existing sections (unchanged) ──────────────────────────── */}
      <SectionCard title="Target Topics" description="Posts matching these topics will be scored and engaged with.">
        <TagInput tags={topics} onAdd={(t) => setTopics((p) => [...p, t])} onRemove={(t) => setTopics((p) => p.filter((x) => x !== t))} placeholder="Add a topic…" />
      </SectionCard>

      <SectionCard title="Hashtags to Monitor" description="Feed scanner will prioritise posts with these hashtags.">
        <TagInput
          tags={hashtags}
          onAdd={(t) => setHashtags((p) => [...p, t])}
          onRemove={(t) => setHashtags((p) => p.filter((x) => x !== t))}
          placeholder="#hashtag…"
          colorClass="bg-blue-700/20 text-blue-300 border-blue-600/30"
        />
      </SectionCard>

      <SectionCard title="Keyword Blacklist" description="Posts containing these phrases are automatically skipped.">
        <TagInput
          tags={blacklist}
          onAdd={(t) => setBlacklist((p) => [...p, t])}
          onRemove={(t) => setBlacklist((p) => p.filter((x) => x !== t))}
          placeholder="Add phrase to block…"
          colorClass="bg-red-700/20 text-red-300 border-red-600/30"
        />
      </SectionCard>

      <SectionCard title="Target Industries" description="Posts from people in these industries get a relevance boost.">
        <div className="flex flex-wrap gap-2">
          {INDUSTRIES.map((ind) => {
            const active = industries.includes(ind)
            return (
              <button
                key={ind}
                onClick={() => toggleIndustry(ind)}
                className={`rounded-lg border px-3 py-1.5 text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                  active
                    ? 'border-violet-600/50 bg-violet-700/20 text-violet-300'
                    : 'border-slate-700/60 bg-slate-800/40 text-slate-400 hover:text-slate-300'
                }`}
              >
                {ind}
              </button>
            )
          })}
        </div>
      </SectionCard>

      <SectionCard title="Minimum Relevance Score" description="Posts scoring below this threshold will be skipped entirely.">
        <div className="flex items-center gap-4">
          <input
            type="range"
            min={0}
            max={10}
            step={1}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="flex-1 accent-violet-500"
          />
          <span className="w-8 text-center text-lg font-semibold tabular-nums text-violet-300">{minScore}</span>
        </div>
        <div className="mt-2 flex justify-between text-xs text-slate-500">
          <span>0 — Engage everything</span>
          <span>10 — Only perfect matches</span>
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <SectionCard title="Influencer Watchlist" description="Posts from these profiles are always scanned first.">
          <TagInput
            tags={influencers}
            onAdd={(t) => setInfluencers((p) => [...p, t])}
            onRemove={(t) => setInfluencers((p) => p.filter((x) => x !== t))}
            placeholder="https://linkedin.com/in/…"
            colorClass="bg-emerald-700/20 text-emerald-300 border-emerald-600/30"
          />
        </SectionCard>
        <SectionCard title="Competitor Watchlist" description="Monitored but never engaged with.">
          <TagInput
            tags={competitors}
            onAdd={(t) => setCompetitors((p) => [...p, t])}
            onRemove={(t) => setCompetitors((p) => p.filter((x) => x !== t))}
            placeholder="https://linkedin.com/in/…"
            colorClass="bg-amber-700/20 text-amber-300 border-amber-600/30"
          />
        </SectionCard>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          SECTION A — Topic Selector Panel (Sprint 9)
          ═══════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Column 1 — Active Topics */}
        <div className="rounded-xl border border-emerald-600/40 bg-slate-800/40 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-emerald-300">Active Topics</h3>
            <span className="rounded-full bg-emerald-700/30 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
              {topicData.active.length}
            </span>
          </div>
          <div className="flex flex-col gap-2 max-h-80 overflow-y-auto">
            {topicData.active.length === 0 && (
              <p className="text-xs text-slate-500 italic">No active topics. Activate from the available pool.</p>
            )}
            {topicData.active.map((t) => (
              <div key={t.topic} className="flex items-center justify-between rounded-lg border border-slate-700/40 bg-slate-900/40 px-3 py-2">
                <div className="flex flex-col gap-1">
                  <span className="text-sm font-medium text-slate-200">{t.topic}</span>
                  <div className="flex gap-1.5">
                    <RateBadge value={t.engagement_rate} />
                    <ScoreBadge value={t.avg_score} />
                    <span className="text-[10px] text-slate-500">{t.posts_engaged}/{t.posts_seen} posts</span>
                  </div>
                </div>
                <button
                  onClick={() => handleDeactivate(t.topic)}
                  className="rounded-md border border-amber-600/30 bg-amber-700/20 px-2 py-1 text-[10px] font-medium text-amber-300 transition-colors hover:bg-amber-700/40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-500 active:scale-[0.97]"
                >
                  <Pause className="inline h-3 w-3 mr-0.5" />Pause
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Column 2 — Available Topics */}
        <div className="rounded-xl border border-slate-600/40 bg-slate-800/40 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-300">Available Topics</h3>
            <span className="rounded-full bg-slate-700/50 px-2 py-0.5 text-[10px] font-bold text-slate-400">
              {topicData.available.length}
            </span>
          </div>
          <div className="flex flex-col gap-2 max-h-80 overflow-y-auto">
            {topicData.available.length === 0 && (
              <p className="text-xs text-slate-500 italic">All topics have been activated or paused.</p>
            )}
            {topicData.available.map((t) => (
              <div key={t} className="rounded-lg border border-slate-700/40 bg-slate-900/40 px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-300">{t}</span>
                  <button
                    onClick={() => handleShowHashtags(t)}
                    className="rounded-md border border-emerald-600/30 bg-emerald-700/20 px-2 py-1 text-[10px] font-medium text-emerald-300 transition-colors hover:bg-emerald-700/40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500 active:scale-[0.97]"
                  >
                    <Play className="inline h-3 w-3 mr-0.5" />Activate
                  </button>
                </div>
                {expandedAvailable === t && (
                  <div className="mt-2 rounded-lg border border-slate-700/40 bg-slate-800/60 p-2">
                    <p className="mb-1.5 text-[10px] font-medium text-slate-400">Suggested hashtags:</p>
                    <div className="flex flex-col gap-1">
                      {suggestedHashtags.map((h) => (
                        <label key={h} className="flex items-center gap-1.5 text-xs text-slate-300">
                          <input
                            type="checkbox"
                            checked={!!checkedHashtags[h]}
                            onChange={(e) => setCheckedHashtags((p) => ({ ...p, [h]: e.target.checked }))}
                            className="h-3 w-3 rounded border-slate-600 accent-emerald-500"
                          />
                          {h}
                        </label>
                      ))}
                    </div>
                    <button
                      onClick={() => handleActivate(t)}
                      className="mt-2 w-full rounded-md bg-emerald-700 px-2 py-1 text-[11px] font-medium text-white transition-colors hover:bg-emerald-600 active:scale-[0.98]"
                    >
                      Confirm Activate
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Column 3 — Paused Topics */}
        <div className="rounded-xl border border-amber-600/30 bg-slate-800/40 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-amber-300">Paused Topics</h3>
            <span className="rounded-full bg-amber-700/30 px-2 py-0.5 text-[10px] font-bold text-amber-300">
              {topicData.paused.length}
            </span>
          </div>
          <div className="flex flex-col gap-2 max-h-80 overflow-y-auto">
            {topicData.paused.length === 0 && (
              <p className="text-xs text-slate-500 italic">No paused topics.</p>
            )}
            {topicData.paused.map((t) => (
              <div key={t.topic} className="flex items-center justify-between rounded-lg border border-slate-700/40 bg-slate-900/40 px-3 py-2">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-slate-200">{t.topic}</span>
                  <span className="text-[10px] italic text-slate-500">{t.pause_reason || 'paused'}</span>
                </div>
                <button
                  onClick={() => handleActivate(t.topic)}
                  className="rounded-md border border-emerald-600/30 bg-emerald-700/20 px-2 py-1 text-[10px] font-medium text-emerald-300 transition-colors hover:bg-emerald-700/40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500 active:scale-[0.97]"
                >
                  <RotateCcw className="inline h-3 w-3 mr-0.5" />Reactivate
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          SECTION B — Performance Table (Sprint 9)
          ═══════════════════════════════════════════════════════════════ */}
      <SectionCard title="Topic Performance" description="Engagement stats per topic. Auto-refreshes every 60 seconds.">
        {sortedPerformance.length === 0 ? (
          <p className="text-xs text-slate-500 italic">No performance data yet. Activate topics and run the engine.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-700/60 text-slate-400">
                  {[
                    ['topic', 'Topic'],
                    ['posts_seen', 'Seen'],
                    ['posts_engaged', 'Engaged'],
                    ['engagement_rate', 'Eng. Rate'],
                    ['avg_score', 'Avg Score'],
                  ].map(([key, label]) => (
                    <th
                      key={key}
                      onClick={() => toggleSort(key)}
                      className="cursor-pointer px-2 py-2 font-medium select-none hover:text-slate-200"
                    >
                      {label}<SortIcon col={key} />
                    </th>
                  ))}
                  <th className="px-2 py-2 font-medium">Status</th>
                  <th className="px-2 py-2 font-medium">Last Used</th>
                </tr>
              </thead>
              <tbody>
                {sortedPerformance.map((r) => {
                  let rowBg = ''
                  if (r.engagement_rate > 0.3) rowBg = 'bg-emerald-900/10'
                  else if (r.engagement_rate >= 0.1) rowBg = 'bg-amber-900/10'
                  else if (r.posts_seen > 0) rowBg = 'bg-red-900/10'

                  let statusChip
                  if (r.is_paused && r.pause_reason === 'manual') {
                    statusChip = <span className="rounded border border-amber-600/30 bg-amber-700/20 px-1.5 py-0.5 text-amber-300">Paused (manual)</span>
                  } else if (r.is_paused) {
                    statusChip = <span className="rounded border border-red-600/30 bg-red-700/20 px-1.5 py-0.5 text-red-300">Paused</span>
                  } else if (r.is_active) {
                    statusChip = <span className="rounded border border-emerald-600/30 bg-emerald-700/20 px-1.5 py-0.5 text-emerald-300">Active</span>
                  } else {
                    statusChip = <span className="rounded border border-slate-600/30 bg-slate-700/20 px-1.5 py-0.5 text-slate-400">Inactive</span>
                  }

                  return (
                    <tr key={r.topic} className={`border-b border-slate-800/40 ${rowBg}`}>
                      <td className="px-2 py-2 font-medium text-slate-200">{r.topic}</td>
                      <td className="px-2 py-2 tabular-nums text-slate-300">{r.posts_seen}</td>
                      <td className="px-2 py-2 tabular-nums text-slate-300">{r.posts_engaged}</td>
                      <td className="px-2 py-2"><RateBadge value={r.engagement_rate} /></td>
                      <td className="px-2 py-2"><ScoreBadge value={r.avg_score} /></td>
                      <td className="px-2 py-2">{statusChip}</td>
                      <td className="px-2 py-2 text-slate-500">
                        {r.last_used ? new Date(r.last_used).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      {/* ═══════════════════════════════════════════════════════════════
          SECTION C — Iteration Cycle Panel (Sprint 9)
          ═══════════════════════════════════════════════════════════════ */}
      <div className="rounded-xl border border-violet-600/30 bg-slate-800/40 p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-violet-300">Auto-Rotation Engine</h2>
          <button
            onClick={handleRunIteration}
            disabled={cycleLoading}
            className="flex items-center gap-2 rounded-full bg-violet-700 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-violet-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-60 active:scale-[0.98]"
          >
            {cycleLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            Run Iteration Cycle Now
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {/* Left — cycle stats */}
          <div className="flex flex-col gap-2 text-xs">
            <div className="text-slate-400">
              <span className="font-medium text-slate-300">Last cycle: </span>
              {cycleReport?.cycle_timestamp
                ? new Date(cycleReport.cycle_timestamp).toLocaleString()
                : 'No cycle run yet'}
            </div>
            <div className="text-slate-400">
              <span className="font-medium text-slate-300">Active topics: </span>
              {cycleReport ? `${cycleReport.active_count} / 8` : `${topicData.active.length} / 8`}
            </div>

            {cycleReport?.topics_activated?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                <span className="text-slate-400 mr-1">Activated:</span>
                {cycleReport.topics_activated.map((t) => (
                  <span key={t} className="rounded border border-emerald-600/30 bg-emerald-700/20 px-1.5 py-0.5 text-emerald-300">{t}</span>
                ))}
              </div>
            )}

            {cycleReport?.topics_paused?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                <span className="text-slate-400 mr-1">Paused:</span>
                {cycleReport.topics_paused.map((t) => (
                  <span key={t} className="rounded border border-amber-600/30 bg-amber-700/20 px-1.5 py-0.5 text-amber-300">{t}</span>
                ))}
              </div>
            )}

            {cycleReport?.top_performer && (
              <div className="text-emerald-400">
                Top: {cycleReport.top_performer.topic} — {(cycleReport.top_performer.engagement_rate * 100).toFixed(0)}%
              </div>
            )}
            {cycleReport?.low_performer && (
              <div className="text-red-400">
                Low: {cycleReport.low_performer.topic} — {(cycleReport.low_performer.engagement_rate * 100).toFixed(0)}%
              </div>
            )}
          </div>

          {/* Right — countdown */}
          <div className="flex flex-col items-end justify-center gap-1 text-xs">
            <div className="flex items-center gap-1.5 text-slate-400">
              <Clock className="h-3.5 w-3.5" />
              <span>Next scheduled cycle in:</span>
            </div>
            <span className="text-lg font-mono font-semibold tabular-nums text-violet-300">
              {countdown || (cycleReport ? '—' : 'Run manually to start')}
            </span>
          </div>
        </div>
      </div>

      {/* ── Toast notification ─────────────────────────────────────── */}
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  )
}
