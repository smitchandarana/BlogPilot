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
  const [loading, setLoading] = useState(true)

  useEffect(() => {
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
    </div>
  )
}
