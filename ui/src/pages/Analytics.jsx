import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell
} from 'recharts'
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

export default function Analytics() {
  const [range, setRange] = useState('7d')
  const [weeklyData, setWeeklyData] = useState([])
  const [topTopics, setTopTopics] = useState([])
  const [funnelData, setFunnelData] = useState([])
  const [summaryText, setSummaryText] = useState('')
  const [dailyStats, setDailyStats] = useState({})
  const [loading, setLoading] = useState(true)
  const [commentQuality, setCommentQuality] = useState(null)
  const [calibration, setCalibration] = useState(null)
  const [timing, setTiming] = useState(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const [weeklyRes, topicsRes, funnelRes, summaryRes, dailyRes] = await Promise.all([
          analytics.weekly(),
          analytics.topTopics(),
          analytics.campaignFunnel(),
          analytics.summary(),
          analytics.daily(),
        ])
        if (cancelled) return

        // Transform weekly data for chart
        const weekly = (weeklyRes.data || []).map((d) => {
          const dayLabel = new Date(d.date + 'T00:00:00').toLocaleDateString('en', { weekday: 'short' })
          return {
            date: dayLabel,
            likes: d.actions?.likes || 0,
            comments: d.actions?.comments || 0,
            connections: d.actions?.connections || 0,
            profile_visits: d.actions?.profile_visits || 0,
          }
        })
        setWeeklyData(weekly)
        setTopTopics(topicsRes.data || [])

        const funnel = funnelRes.data || {}
        setFunnelData([
          { stage: 'Enrolled', value: funnel.enrolled || 0, color: '#7c3aed' },
          { stage: 'In Progress', value: funnel.in_progress || 0, color: '#4f46e5' },
          { stage: 'Completed', value: funnel.completed || 0, color: '#10b981' },
          { stage: 'Failed', value: funnel.failed || 0, color: '#ef4444' },
        ])

        setSummaryText(summaryRes.data?.summary || 'No data yet.')

        const daily = dailyRes.data || {}
        const actions = daily.actions || {}
        const totalEngagements = Object.values(actions).reduce((a, b) => a + b, 0)
        setDailyStats({
          totalEngagements,
          emailRate: daily.leads_total > 0 ? Math.round((daily.emails_found / daily.leads_total) * 100) + '%' : 'N/A',
          leadsTotal: daily.leads_total || 0,
          emailsFound: daily.emails_found || 0,
        })
        // Learning insights
        const [cqRes, calRes, timRes] = await Promise.all([
          analytics.learningCommentQuality().catch(() => ({ data: null })),
          analytics.learningCalibration().catch(() => ({ data: null })),
          analytics.learningTiming().catch(() => ({ data: null })),
        ])
        if (cancelled) return
        setCommentQuality(cqRes.data)
        setCalibration(calRes.data)
        setTiming(timRes.data)
      } catch {
        // keep empty state
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  const chartData = weeklyData

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-100">Analytics</h1>
        <p className="mt-0.5 text-sm text-slate-500">Engagement performance and growth metrics.</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Engagements" value={dailyStats.totalEngagements ?? 0} sub="Today" color="text-violet-300" />
        <StatCard label="Email Find Rate" value={dailyStats.emailRate ?? 'N/A'} sub="Of profiles visited" color="text-blue-400" />
        <StatCard label="Emails Found" value={dailyStats.emailsFound ?? 0} sub="Verified emails" color="text-emerald-400" />
        <StatCard label="Total Leads" value={dailyStats.leadsTotal ?? 0} sub="In database" color="text-amber-400" />
      </div>

      {/* Daily actions chart */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Daily Actions (Last 7 Days)</h2>
        </div>
        {loading ? (
          <div className="flex h-[220px] items-center justify-center text-sm text-slate-500">Loading...</div>
        ) : chartData.length === 0 ? (
          <div className="flex h-[220px] items-center justify-center text-sm text-slate-500">No engagement data yet. Start the engine to collect data.</div>
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
            <p className="py-6 text-center text-sm text-slate-500">No topic data yet.</p>
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
          {funnelData.length === 0 ? (
            <p className="py-4 text-center text-sm text-slate-500">No campaign data yet.</p>
          ) : (
          <div className="flex flex-col gap-3 mt-2">
            {funnelData.map((item) => {
              const maxVal = Math.max(...funnelData.map(d => d.value), 1)
              const pct = Math.round((item.value / maxVal) * 100)
              return (
                <div key={item.stage} className="flex items-center gap-3">
                  <span className="w-20 text-right text-xs text-slate-400">{item.stage}</span>
                  <div className="flex-1 h-6 bg-slate-800 rounded-md overflow-hidden">
                    <div
                      className="h-full rounded-md flex items-center px-2 transition-[width] duration-700"
                      style={{ width: `${Math.max(pct, 5)}%`, backgroundColor: item.color }}
                    >
                      <span className="text-xs font-semibold text-white">{item.value}</span>
                    </div>
                  </div>
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
        {summaryText
          ? <p className="text-sm leading-relaxed text-slate-400">{summaryText}</p>
          : <p className="text-sm text-slate-500">No summary yet. Run the engine to collect engagement data.</p>
        }
      </div>

      {/* ── Learning Insights ─────────────────────────────────────── */}
      <div className="mt-2">
        <h2 className="text-lg font-semibold tracking-tight text-slate-100">Learning Insights</h2>
        <p className="mt-0.5 text-sm text-slate-500">Self-learning feedback from engagement data.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Comments Logged"
          value={commentQuality?.total_comments ?? 0}
          sub="Quality tracked"
          color="text-blue-400"
        />
        <StatCard
          label="Avg Quality Score"
          value={commentQuality?.avg_quality_score?.toFixed(1) ?? '0.0'}
          sub="Out of 10"
          color="text-violet-300"
        />
        <StatCard
          label="Reply Rate"
          value={commentQuality?.total_comments > 0 && commentQuality.reply_rate != null ? `${(commentQuality.reply_rate * 100).toFixed(0)}%` : 'N/A'}
          sub={`${commentQuality?.got_reply_count ?? 0} replies`}
          color="text-emerald-400"
        />
        <StatCard
          label="Scored Posts"
          value={calibration?.total_posts ?? 0}
          sub="For calibration"
          color="text-amber-400"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Score calibration */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Score Calibration</h2>
          {calibration?.buckets?.length > 0 ? (
            <div className="space-y-3">
              {(calibration?.buckets ?? []).map((b) => {
                const pct = Math.round(b.rate * 100)
                return (
                  <div key={b.range} className="flex items-center gap-3">
                    <span className="w-12 text-right text-xs font-mono text-slate-400">{b.range}</span>
                    <div className="flex-1 h-5 bg-slate-800 rounded overflow-hidden">
                      <div
                        className="h-full rounded flex items-center px-2 transition-[width] duration-500"
                        style={{
                          width: `${Math.max(pct, 4)}%`,
                          backgroundColor: pct > 50 ? '#10b981' : pct > 20 ? '#f59e0b' : '#64748b',
                        }}
                      >
                        <span className="text-[10px] font-bold text-white">{pct}%</span>
                      </div>
                    </div>
                    <span className="w-16 text-right text-xs text-slate-500">{b.acted}/{b.total}</span>
                  </div>
                )
              })}
              {calibration.recommendation && (
                <p className="mt-3 text-xs text-slate-500 italic">{calibration.recommendation}</p>
              )}
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-slate-500">No calibration data yet.</p>
          )}
        </div>

        {/* Timing heatmap */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Activity by Hour</h2>
          {timing?.total_actions > 0 ? (
            <div>
              <div className="flex flex-wrap gap-1">
                {Array.from({ length: 24 }, (_, h) => {
                  const count = timing.hourly?.[h] ?? 0
                  const maxCount = Math.max(...Object.values(timing.hourly ?? {}), 1)
                  const intensity = count / maxCount
                  return (
                    <div
                      key={h}
                      className="flex flex-col items-center"
                      title={`${h}:00 — ${count} actions`}
                    >
                      <div
                        className="w-5 h-5 rounded-sm"
                        style={{
                          backgroundColor: count === 0
                            ? 'rgba(100,116,139,0.15)'
                            : `rgba(124,58,237,${0.2 + intensity * 0.8})`,
                        }}
                      />
                      <span className="text-[8px] text-slate-600 mt-0.5">{h}</span>
                    </div>
                  )
                })}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {timing.best_hours?.length > 0 && (
                  <span className="text-xs text-slate-400">
                    Best hours: <span className="text-emerald-400 font-medium">
                      {timing.best_hours.map(h => `${h}:00`).join(', ')}
                    </span>
                  </span>
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {timing.best_days?.length > 0 && (
                  <span className="text-xs text-slate-400">
                    Best days: <span className="text-violet-300 font-medium">
                      {timing.best_days.map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(', ')}
                    </span>
                  </span>
                )}
              </div>
              {timing.recommendation && (
                <p className="mt-2 text-xs text-slate-500 italic">{timing.recommendation}</p>
              )}
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-slate-500">No timing data yet.</p>
          )}
        </div>
      </div>

      {/* Comment angle performance */}
      {commentQuality?.top_angles && Object.values(commentQuality.top_angles).some(v => v > 0) && (
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Comment Angle Distribution</h2>
          <div className="flex flex-wrap gap-3">
            {Object.entries(commentQuality.top_angles).map(([angle, count]) => (
              <div key={angle} className="rounded-lg bg-slate-800 px-4 py-2 border border-slate-700/40">
                <span className="text-xs text-slate-400 capitalize">{angle}</span>
                <p className="text-lg font-semibold text-violet-300">{count}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
