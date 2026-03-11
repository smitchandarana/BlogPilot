import { useState } from 'react'
import { ExternalLink } from 'lucide-react'

const MODES = [
  { value: 'like_only', label: 'Like Only', desc: 'Like relevant posts, never comment' },
  { value: 'comment_only', label: 'Comment Only', desc: 'Comment on relevant posts, never like' },
  { value: 'like_and_comment', label: 'Like + Comment', desc: 'Always do both for relevant posts' },
  { value: 'smart', label: 'Smart', desc: 'Score 6-7: like. Score 8+: like + comment' },
]

const MOCK_RECENT = [
  { author: 'Rahul Sharma', snippet: 'How we cut reporting time by 60% using Po...', score: 9, action: 'COMMENT', result: 'SUCCESS', time: '2m ago' },
  { author: 'Priya Mehta', snippet: 'Data analytics is the backbone of every mo...', score: 7, action: 'LIKE', result: 'SUCCESS', time: '8m ago' },
  { author: 'James Liu', snippet: 'We launched our new BI dashboard to the te...', score: 8, action: 'COMMENT', result: 'SUCCESS', time: '15m ago' },
  { author: 'Sarah Chen', snippet: 'The future of business intelligence is here...', score: 6, action: 'LIKE', result: 'SUCCESS', time: '22m ago' },
  { author: 'Tom Nguyen', snippet: 'Power BI tips that saved us hours every we...', score: 10, action: 'COMMENT', result: 'FAILED', time: '31m ago' },
]

const MOCK_SKIPPED = [
  { author: 'Alex Kim', snippet: 'Looking for a job in data science, anyone h...', score: 0, action: 'SKIP', result: 'SKIPPED', time: '5m ago', reason: 'Blacklisted keyword' },
  { author: 'Maria Lopez', snippet: 'Hiring! Senior BI Developer, DM me if inter...', score: 0, action: 'SKIP', result: 'SKIPPED', time: '18m ago', reason: 'Blacklisted keyword' },
  { author: 'David Park', snippet: 'Check out my new crypto portfolio tracker...', score: 2, action: 'SKIP', result: 'SKIPPED', time: '35m ago', reason: 'Score too low (2 < 6)' },
]

const MOCK_COMMENTS = [
  { author: 'Rahul Sharma', comment: 'Really impressive results — what did you use for the data pipeline behind this?', link: '#', time: '2m ago' },
  { author: 'James Liu', comment: 'The rollout strategy you described here aligns with what I\'ve seen work at scale too.', link: '#', time: '15m ago' },
]

const RESULT_STYLES = {
  SUCCESS: 'bg-emerald-500/15 text-emerald-400',
  FAILED: 'bg-red-500/15 text-red-400',
  SKIPPED: 'bg-slate-700/60 text-slate-400',
}

function ScoreBadge({ score }) {
  const color = score >= 8 ? 'text-emerald-400' : score >= 6 ? 'text-amber-400' : 'text-slate-500'
  return <span className={`font-semibold tabular-nums ${color}`}>{score}</span>
}

function DataTable({ headers, rows, renderRow }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[600px] text-sm">
        <thead>
          <tr className="border-b border-slate-700/60">
            {headers.map((h) => (
              <th key={h} className="pb-2 text-left text-xs font-medium uppercase tracking-wider text-slate-500 pr-4 last:pr-0">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700/30">
          {rows.map((row, i) => renderRow(row, i))}
        </tbody>
      </table>
    </div>
  )
}

export default function FeedEngagement() {
  const [mode, setMode] = useState('smart')
  const [previewComments, setPreviewComments] = useState(true)
  const [viralThreshold, setViralThreshold] = useState(50)

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-100">Feed Engagement</h1>
        <p className="mt-0.5 text-sm text-slate-500">Configure how the engine interacts with LinkedIn feed posts.</p>
      </div>

      {/* Settings row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Engagement mode */}
        <div className="col-span-2 rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Engagement Mode</h2>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {MODES.map((m) => (
              <label
                key={m.value}
                className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors duration-150 ${
                  mode === m.value
                    ? 'border-violet-600/50 bg-violet-700/15'
                    : 'border-slate-700/40 bg-slate-900/30 hover:border-slate-600/60'
                }`}
              >
                <input
                  type="radio"
                  name="mode"
                  value={m.value}
                  checked={mode === m.value}
                  onChange={() => setMode(m.value)}
                  className="mt-0.5 accent-violet-500"
                />
                <div>
                  <p className={`text-sm font-medium ${mode === m.value ? 'text-violet-300' : 'text-slate-300'}`}>{m.label}</p>
                  <p className="mt-0.5 text-xs text-slate-500">{m.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Quick settings */}
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">Quick Settings</h2>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-300">Preview Comments</p>
                <p className="text-xs text-slate-500">Show before posting</p>
              </div>
              <button
                role="switch"
                aria-checked={previewComments}
                onClick={() => setPreviewComments(!previewComments)}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${previewComments ? 'bg-violet-600' : 'bg-slate-700'}`}
              >
                <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform duration-200 ${previewComments ? 'translate-x-4' : 'translate-x-1'}`} />
              </button>
            </div>
            <div>
              <label className="mb-1.5 block text-xs text-slate-400">Viral Threshold (likes/hr)</label>
              <input
                type="number"
                min={10}
                max={500}
                value={viralThreshold}
                onChange={(e) => setViralThreshold(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Recent posts table */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Recent Posts</h2>
        <DataTable
          headers={['Author', 'Post', 'Score', 'Action', 'Result', 'Time']}
          rows={MOCK_RECENT}
          renderRow={(row, i) => (
            <tr key={i} className="group">
              <td className="py-2.5 pr-4 text-slate-300">{row.author}</td>
              <td className="py-2.5 pr-4 max-w-[220px] truncate text-slate-400">{row.snippet}</td>
              <td className="py-2.5 pr-4"><ScoreBadge score={row.score} /></td>
              <td className="py-2.5 pr-4 text-xs text-slate-400">{row.action}</td>
              <td className="py-2.5 pr-4">
                <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${RESULT_STYLES[row.result]}`}>{row.result}</span>
              </td>
              <td className="py-2.5 text-xs text-slate-500 tabular-nums">{row.time}</td>
            </tr>
          )}
        />
      </div>

      {/* Skipped posts */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Skipped Posts</h2>
        <DataTable
          headers={['Author', 'Post', 'Score', 'Reason', 'Time']}
          rows={MOCK_SKIPPED}
          renderRow={(row, i) => (
            <tr key={i}>
              <td className="py-2.5 pr-4 text-slate-300">{row.author}</td>
              <td className="py-2.5 pr-4 max-w-[200px] truncate text-slate-400">{row.snippet}</td>
              <td className="py-2.5 pr-4"><ScoreBadge score={row.score} /></td>
              <td className="py-2.5 pr-4 text-xs text-slate-500">{row.reason}</td>
              <td className="py-2.5 text-xs text-slate-500 tabular-nums">{row.time}</td>
            </tr>
          )}
        />
      </div>

      {/* Comment history */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Comment History</h2>
        <DataTable
          headers={['Author', 'Comment', 'Post', 'Time']}
          rows={MOCK_COMMENTS}
          renderRow={(row, i) => (
            <tr key={i}>
              <td className="py-2.5 pr-4 text-slate-300 whitespace-nowrap">{row.author}</td>
              <td className="py-2.5 pr-4 max-w-[320px] text-slate-400 leading-relaxed">{row.comment}</td>
              <td className="py-2.5 pr-4">
                <a href={row.link} className="inline-flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500">
                  View <ExternalLink className="h-3 w-3" />
                </a>
              </td>
              <td className="py-2.5 text-xs text-slate-500 tabular-nums">{row.time}</td>
            </tr>
          )}
        />
      </div>
    </div>
  )
}
