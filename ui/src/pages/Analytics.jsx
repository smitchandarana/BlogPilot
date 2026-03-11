import { useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell
} from 'recharts'

const DAILY_7D = [
  { date: 'Mon', likes: 8, comments: 3, connections: 2, visits: 12 },
  { date: 'Tue', likes: 12, comments: 4, connections: 4, visits: 18 },
  { date: 'Wed', likes: 6, comments: 2, connections: 1, visits: 9 },
  { date: 'Thu', likes: 15, comments: 5, connections: 5, visits: 22 },
  { date: 'Fri', likes: 10, comments: 4, connections: 3, visits: 16 },
  { date: 'Sat', likes: 4, comments: 1, connections: 0, visits: 5 },
  { date: 'Sun', likes: 2, comments: 0, connections: 0, visits: 3 },
]

const DAILY_30D = Array.from({ length: 30 }, (_, i) => ({
  date: `D${i + 1}`,
  likes: Math.floor(Math.random() * 20 + 3),
  comments: Math.floor(Math.random() * 6 + 1),
  connections: Math.floor(Math.random() * 5),
  visits: Math.floor(Math.random() * 25 + 5),
}))

const TOP_TOPICS = [
  { topic: 'Data Analytics', count: 48 },
  { topic: 'Business Intelligence', count: 37 },
  { topic: 'Power BI', count: 29 },
  { topic: 'Dashboard Design', count: 21 },
  { topic: 'Reporting Solutions', count: 17 },
  { topic: 'Data Visualization', count: 13 },
]

const FUNNEL_DATA = [
  { stage: 'Enrolled', value: 72, color: '#7c3aed' },
  { stage: 'Connected', value: 48, color: '#4f46e5' },
  { stage: 'Replied', value: 22, color: '#0ea5e9' },
  { stage: 'Converted', value: 9, color: '#10b981' },
]

const BAR_COLORS = {
  likes: '#7c3aed',
  comments: '#0ea5e9',
  connections: '#10b981',
  visits: '#f59e0b',
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
  const data = range === '7d' ? DAILY_7D : DAILY_30D

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-100">Analytics</h1>
        <p className="mt-0.5 text-sm text-slate-500">Engagement performance and growth metrics.</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Engagements" value="187" sub="This week" color="text-violet-300" />
        <StatCard label="Email Find Rate" value="62%" sub="Of profiles visited" color="text-blue-400" />
        <StatCard label="Connection Rate" value="34%" sub="Accepted / sent" color="text-emerald-400" />
        <StatCard label="Leads This Week" value="7" sub="New leads added" color="text-amber-400" />
      </div>

      {/* Daily actions chart */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Daily Actions</h2>
          <div className="flex rounded-lg border border-slate-700/60 overflow-hidden">
            {['7d', '30d'].map((r) => (
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
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data} barCategoryGap="30%" barGap={2}>
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
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Top topics */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Top Topics</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={TOP_TOPICS} layout="vertical" barCategoryGap="25%">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" horizontal={false} />
              <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="topic" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} width={130} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Bar dataKey="count" radius={[0, 3, 3, 0]}>
                {TOP_TOPICS.map((_, i) => (
                  <Cell key={i} fill={`rgba(124,58,237,${0.9 - i * 0.12})`} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Campaign funnel */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Campaign Funnel</h2>
          <div className="flex flex-col gap-3 mt-2">
            {FUNNEL_DATA.map((item, i) => {
              const pct = Math.round((item.value / FUNNEL_DATA[0].value) * 100)
              return (
                <div key={item.stage} className="flex items-center gap-3">
                  <span className="w-20 text-right text-xs text-slate-400">{item.stage}</span>
                  <div className="flex-1 h-6 bg-slate-800 rounded-md overflow-hidden">
                    <div
                      className="h-full rounded-md flex items-center px-2 transition-[width] duration-700"
                      style={{ width: `${pct}%`, backgroundColor: item.color }}
                    >
                      <span className="text-xs font-semibold text-white">{item.value}</span>
                    </div>
                  </div>
                  <span className="w-10 text-xs text-slate-500 tabular-nums">{pct}%</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Weekly summary */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Weekly Summary</h2>
        <p className="text-sm leading-relaxed text-slate-400">
          This week the engine processed <strong className="text-slate-200">187 engagements</strong> across 5 active days, with a peak on Thursday.
          The <strong className="text-slate-200">Data Analytics</strong> topic drove the most interactions (48 posts engaged).
          Email enrichment found addresses for <strong className="text-slate-200">62% of visited profiles</strong>, adding 7 new verified leads.
          Campaign reply rate is holding at <strong className="text-slate-200">18%</strong> — above the benchmark of 12%.
        </p>
      </div>
    </div>
  )
}
