import { useState, useEffect } from 'react'
import { X, Plus, Save, Loader2, CheckCircle2 } from 'lucide-react'
import { config as configApi } from '../api/client'

const INDUSTRIES = [
  'Manufacturing', 'Retail & E-Commerce', 'Financial Services & Banking',
  'Healthcare & Pharmaceuticals', 'Logistics & Supply Chain', 'Real Estate',
  'Information Technology', 'Consulting', 'Education', 'Hospitality',
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
  }, [])

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

  return (
    <div className="flex flex-col gap-6 p-6">
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
    </div>
  )
}
