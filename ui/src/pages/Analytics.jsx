import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell
} from 'recharts'
import { Loader2 } from 'lucide-react'
import { analytics } from '../api/client'

const BAR_COLORS = {
  likes: '#7c3aed',
  comments: '#0ea5e9',
  connections: '#10b981',
  profile_visits: '#f59e0b',
}

const TOOLTIP_STYLE = {
  backgroundColor: '#1e2433',
  border: '1px solid rgba(148,163,184,0.12)',
  borderRadius: '8px',
  color: '#e2e8f0',
  fontSize: '12px',
}

function StatCard({ label, value, sub, color = 'text-violet-300' }) {
  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 px-5 py-4">
      <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-2 text-3xl font-semibold tabular-nums ${color}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  )
}

function formatDayLabel(isoDate) {
  try {
    const d = new Date(isoDate + 'T00:00:00')
    return d.toLocaleDateString(undefined, { weekday: 'short' })
  } catch {
    return isoDate
  }
}

export default function Analytics() {
  const [range, setRange] = useState('7d')
  const [weeklyData, setWeeklyData] = useState([])
  const [topTopics, setTopTopics] = useState([])
  const [funnelData, setFunnelData] = useState([])
  const [summary, setSummary] = useState('')
  const [dailyStats, setDailyStats] = useState(null)
  const [commentQuality, setCommentQuality] = useState(null)
  const [postQuality, setPostQuality] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [weeklyRes, topicsRes, funnelRes, summaryRes, dailyRes, cqRes, pqRes] = await Promise.all([
          analytics.weekly(),
          analytics.topTopics(),
          analytics.campaignFunnel(),
          analytics.summary(),
          analytics.daily(),
          analytics.commentQuality().catch(() => ({ data: null })),
          analytics.postQuality().catch(() => ({ data: null })),
        ])

        // Transform weekly data for chart
        const weekly = (weeklyRes.data || []).map((d) => ({
          date: formatDayLabel(d.date),
          fullDate: d.date,
          likes: d.actions?.likes || 0,
          comments: d.actions?.comments || 0,
          connections: d.actions?.connections || 0,
          profile_visits: d.actions?.profile_visits || 0,
        }))
        setWeeklyData(weekly)
        setTopTopics(topicsRes.data || [])

        const funnel = funnelRes.data || {}
        setFunnelData([
          { stage: 'Enrolled', value: funnel.enrolled || 0, color: '#7c3aed' },
          { stage: 'Connected', value: funnel.connected || 0, color: '#4f46e5' },
          { stage: 'Replied', value: funnel.replied || 0, color: '#0ea5e9' },
          { stage: 'Completed', value: funnel.completed || 0, color: '#10b981' },
        ])

        setSummary(summaryRes.data?.summary || 'No summary available yet.')
        setDailyStats(dailyRes.data || {})
        setCommentQuality(cqRes.data || null)
        setPostQuality(pqRes.data || null)
      } catch {
        // keep defaults
      } finally {
        setLoading(false)
      }
    }
    load()
    const id = setInterval(load, 60000)
    return () => clearInterval(id)
  }, [])

  // Compute stat card values from real data
  const totalEngagements = weeklyData.reduce((sum, d) => sum + d.likes + d.comments + d.connections + d.profile_visits, 0)
  const leadsTotal = dailyStats?.leads_total || 0
  const emailsFound = dailyStats?.emails_found || 0
  const emailRate = leadsTotal > 0 ? Math.round((emailsFound / leadsTotal) * 100) : 0

  const chartData = range === '7d' ? weeklyData : weeklyData // only 7d data from API for now

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 gap-2 text-sm text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading analytics…
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-100">Analytics</h1>
        <p className="mt-0.5 text-sm text-slate-500">Engagement performance and growth metrics.</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Engagements" value={totalEngagements} sub="This week" color="text-violet-300" />
        <StatCard label="Email Find Rate" value={`${emailRate}%`} sub="Of leads in DB" color="text-blue-400" />
        <StatCard label="Emails Found" value={emailsFound} sub="Found or verified" color="text-emerald-400" />
        <StatCard label="Total Leads" value={leadsTotal} sub="In database" color="text-amber-400" />
      </div>

      {/* Daily actions chart */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Daily Actions</h2>
          <div className="flex rounded-lg border border-slate-700/60 overflow-hidden">
            {['7d'].map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1 text-xs font-medium transition-colors ${range === r ? 'bg-violet-700/30 text-violet-300' : 'text-slate-400 hover:text-slate-300'}`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        {chartData.length === 0 ? (
          <div className="py-12 text-center text-sm text-slate-500">No activity data yet.</div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} barCategoryGap="30%" barGap={2}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Legend wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }} />
              {Object.entries(BAR_COLORS).map(([key, color]) => (
                <Bar key={key} dataKey={key} fill={color} radius={[3, 3, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Top topics */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Top Topics</h2>
          {topTopics.length === 0 ? (
            <div className="py-8 text-center text-sm text-slate-500">No topic data yet. Topics are tagged when the engine processes posts.</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={topTopics} layout="vertical" barCategoryGap="25%">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" horizontal={false} />
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="topic" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} width={130} />
                <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                <Bar dataKey="count" radius={[0, 3, 3, 0]}>
                  {topTopics.map((_, i) => (
                    <Cell key={i} fill={`rgba(124,58,237,${0.9 - i * 0.08})`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Campaign funnel */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Campaign Funnel</h2>
          {funnelData.every((d) => d.value === 0) ? (
            <div className="py-8 text-center text-sm text-slate-500">No campaign data yet. Enroll leads in a campaign to see the funnel.</div>
          ) : (
            <div className="flex flex-col gap-3 mt-2">
              {funnelData.map((item) => {
                const maxVal = funnelData[0].value || 1
                const pct = Math.round((item.value / maxVal) * 100)
                return (
                  <div key={item.stage} className="flex items-center gap-3">
                    <span className="w-20 text-right text-xs text-slate-400">{item.stage}</span>
                    <div className="flex-1 h-6 bg-slate-800 rounded-md overflow-hidden">
                      <div
                        className="h-full rounded-md flex items-center px-2 transition-[width] duration-700"
                        style={{ width: `${Math.max(pct, 2)}%`, backgroundColor: item.color }}
                      >
                        <span className="text-xs font-semibold text-white">{item.value}</span>
                      </div>
                    </div>
                    <span className="w-10 text-xs text-slate-500 tabular-nums">{pct}%</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Weekly summary */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Weekly Summary</h2>
        <p className="text-sm leading-relaxed text-slate-400">{summary}</p>
      </div>

      {/* Content Quality Metrics (Sprint 10) */}
      {(commentQuality || postQuality) && (
        <div>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Content Quality Metrics</h2>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Comment Quality */}
            <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
              <h3 className="mb-4 text-sm font-medium text-slate-300">Comment Quality</h3>
              {commentQuality && commentQuality.total_comments > 0 ? (
                <div className="flex flex-col gap-3">
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs text-slate-500">Avg Quality Score</span>
                    <span className={`text-2xl font-semibold tabular-nums ${commentQuality.avg_quality_score >= 8 ? 'text-green-500' : commentQuality.avg_quality_score >= 6 ? 'text-yellow-500' : 'text-red-500'}`}>
                      {commentQuality.avg_quality_score}/10
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs text-slate-500">Reply Rate</span>
                    <span className="text-lg font-semibold text-violet-300 tabular-nums">{Math.round(commentQuality.reply_rate * 100)}%</span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs text-slate-500">High Quality</span>
                    <span className="text-sm text-slate-400">{commentQuality.high_quality_count} / {commentQuality.total_comments}</span>
                  </div>
                  {commentQuality.top_angles && (
                    <div className="mt-2">
                      <span className="text-xs text-slate-500 block mb-2">Angle Breakdown</span>
                      <div className="flex gap-2">
                        {Object.entries(commentQuality.top_angles).map(([angle, count]) => (
                          <div key={angle} className="flex-1 rounded-lg border border-slate-700/40 bg-slate-900/40 px-3 py-2 text-center">
                            <p className="text-xs text-slate-500 capitalize">{angle}</p>
                            <p className="text-sm font-semibold text-slate-300 tabular-nums">{count}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="py-4 text-center text-sm text-slate-500">No comment quality data yet.</p>
              )}
            </div>

            {/* Post Quality */}
            <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
              <h3 className="mb-4 text-sm font-medium text-slate-300">Post Quality</h3>
              {postQuality && postQuality.total_generated > 0 ? (
                <div className="flex flex-col gap-3">
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs text-slate-500">Approval Rate</span>
                    <span className={`text-2xl font-semibold tabular-nums ${postQuality.approval_rate >= 0.8 ? 'text-green-500' : postQuality.approval_rate >= 0.6 ? 'text-yellow-500' : 'text-red-500'}`}>
                      {Math.round(postQuality.approval_rate * 100)}%
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs text-slate-500">Avg Score</span>
                    <span className={`text-lg font-semibold tabular-nums ${postQuality.avg_quality_score >= 8 ? 'text-green-500' : postQuality.avg_quality_score >= 6 ? 'text-yellow-500' : 'text-red-500'}`}>
                      {postQuality.avg_quality_score}/10
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs text-slate-500">Approved / Rejected</span>
                    <span className="text-sm text-slate-400">{postQuality.approved_count} / {postQuality.rejected_count}</span>
                  </div>
                  {postQuality.top_rejection_reasons && postQuality.top_rejection_reasons.length > 0 && (
                    <div className="mt-2">
                      <span className="text-xs text-slate-500 block mb-1">Top Rejection Reason</span>
                      <p className="text-xs text-red-400/80 italic">{postQuality.top_rejection_reasons[0]}</p>
                    </div>
                  )}
                </div>
              ) : (
                <p className="py-4 text-center text-sm text-slate-500">No post quality data yet.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
