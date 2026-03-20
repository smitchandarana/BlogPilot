import { useState, useEffect } from 'react'
import { Plus, X, ChevronDown, ChevronUp, Play, Pause, Trash2, Users, Loader2 } from 'lucide-react'
import CampaignBuilder from '../components/CampaignBuilder'
import { campaigns as campaignsApi } from '../api/client'

const STATUS_STYLES = {
  ACTIVE: 'bg-emerald-500/15 text-emerald-400',
  PAUSED: 'bg-amber-500/15 text-amber-400',
  COMPLETED: 'bg-slate-700/60 text-slate-400',
  ARCHIVED: 'bg-slate-700/60 text-slate-400',
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-slate-700/60 bg-[#161b27] p-6 shadow-[0_24px_64px_rgba(0,0,0,0.5)]">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500">
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)
  const [expandedStats, setExpandedStats] = useState({})
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState('')
  const [newSteps, setNewSteps] = useState([])
  const [showEnroll, setShowEnroll] = useState(null)
  const [enrollUrls, setEnrollUrls] = useState('')
  const [enrollResult, setEnrollResult] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const fetchCampaigns = async () => {
    try {
      const res = await campaignsApi.list()
      setCampaigns(res.data || [])
    } catch {
      // keep existing data
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCampaigns()
  }, [])

  const toggleExpand = async (id) => {
    if (expanded === id) {
      setExpanded(null)
      return
    }
    setExpanded(id)
    // Fetch real stats for this campaign
    try {
      const res = await campaignsApi.stats(id)
      setExpandedStats((prev) => ({ ...prev, [id]: res.data }))
    } catch {}
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      await campaignsApi.create({ name: newName, steps: newSteps })
      fetchCampaigns()
    } catch {}
    setShowNew(false)
    setNewName('')
    setNewSteps([])
  }

  const handleDelete = async (id) => {
    setDeleteTarget(id)
  }

  const confirmDelete = async (id) => {
    setDeleteTarget(null)
    try {
      await campaignsApi.delete(id)
      setCampaigns((prev) => prev.filter((c) => c.id !== id))
    } catch {}
  }

  const handleToggleStatus = async (c) => {
    const newStatus = c.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE'
    try {
      await campaignsApi.update(c.id, { status: newStatus })
      fetchCampaigns()
    } catch {}
  }

  const handleEnroll = async () => {
    const ids = enrollUrls.split('\n').map((s) => s.trim()).filter(Boolean)
    if (!ids.length) return
    try {
      await campaignsApi.enroll(showEnroll, ids)
      fetchCampaigns()
      setEnrollResult({ success: true, message: `${ids.length} lead${ids.length !== 1 ? 's' : ''} enrolled` })
    } catch {
      setEnrollResult({ success: false, message: 'Enrollment failed' })
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-100">Campaigns</h1>
          <p className="mt-0.5 text-sm text-slate-500">Build multi-step outreach sequences for your leads.</p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-2 rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-[background,box-shadow] duration-200 hover:bg-violet-600 hover:shadow-[0_0_24px_rgba(124,58,237,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 active:scale-[0.98]"
        >
          <Plus className="h-4 w-4" />
          New Campaign
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12 gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading campaigns…
        </div>
      ) : campaigns.length === 0 ? (
        <div className="py-12 text-center text-sm text-slate-500">No campaigns yet. Create one to get started.</div>
      ) : (
        <div className="flex flex-col gap-3">
          {campaigns.map((c) => {
            const stepCount = Array.isArray(c.steps) ? c.steps.length : 0
            const stats = expandedStats[c.id]
            return (
              <div key={c.id} className="rounded-xl border border-slate-700/60 bg-slate-800/40 overflow-hidden">
                {/* Row */}
                <div className="flex items-center gap-4 px-5 py-4">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-slate-200 truncate">{c.name}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{stepCount} steps · created {c.created_at ? c.created_at.slice(0, 10) : '—'}</p>
                  </div>
                  <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[c.status] || ''}`}>{c.status}</span>
                  <div className="flex items-center gap-1.5 text-sm text-slate-400">
                    <Users className="h-3.5 w-3.5" />
                    {c.enrolled_count ?? 0}
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setShowEnroll(c.id)}
                      className="rounded-lg border border-slate-700/40 px-2.5 py-1 text-xs text-slate-400 transition-colors hover:text-violet-300 hover:border-violet-600/40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500"
                    >
                      Enroll
                    </button>
                    <button
                      onClick={() => handleToggleStatus(c)}
                      className={`rounded-lg border border-slate-700/40 p-1.5 text-slate-500 transition-colors focus-visible:outline-none focus-visible:ring-1 ${
                        c.status === 'ACTIVE' ? 'hover:text-amber-400 focus-visible:ring-amber-500' : 'hover:text-emerald-400 focus-visible:ring-emerald-500'
                      }`}
                    >
                      {c.status === 'ACTIVE' ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                    </button>
                    {deleteTarget === c.id ? (
                      <div className="flex items-center gap-1.5 rounded-lg border border-red-700/40 bg-red-900/20 px-2 py-1">
                        <span className="text-xs text-red-300">Delete?</span>
                        <button
                          onClick={() => confirmDelete(c.id)}
                          className="rounded px-1.5 py-0.5 text-xs font-medium text-red-300 hover:bg-red-700/30 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500"
                        >
                          Delete
                        </button>
                        <button
                          onClick={() => setDeleteTarget(null)}
                          className="rounded px-1.5 py-0.5 text-xs text-slate-400 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleDelete(c.id)}
                        className="rounded-lg border border-slate-700/40 p-1.5 text-slate-500 transition-colors hover:text-red-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                    <button onClick={() => toggleExpand(c.id)} className="rounded-lg border border-slate-700/40 p-1.5 text-slate-500 transition-colors hover:text-slate-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500">
                      {expanded === c.id ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                </div>

                {/* Expanded stats */}
                {expanded === c.id && (
                  <div className="border-t border-slate-700/40 bg-slate-900/30 px-5 py-4">
                    {stats ? (
                      <div className="grid grid-cols-4 gap-4">
                        {[
                          { label: 'Enrolled', value: stats.enrolled, color: 'text-slate-200' },
                          { label: 'In Progress', value: stats.in_progress, color: 'text-violet-300' },
                          { label: 'Completed', value: stats.completed, color: 'text-emerald-400' },
                          { label: 'Reply Rate', value: `${Math.round((stats.reply_rate || 0) * 100)}%`, color: 'text-amber-400' },
                        ].map(({ label, value, color }) => (
                          <div key={label} className="text-center">
                            <p className={`text-xl font-semibold tabular-nums ${color}`}>{value}</p>
                            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center text-sm text-slate-500">Loading stats…</div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* New campaign modal */}
      {showNew && (
        <Modal title="New Campaign" onClose={() => setShowNew(false)}>
          <div className="flex flex-col gap-5">
            <div>
              <label className="mb-1.5 block text-xs text-slate-400">Campaign Name</label>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. BI Leaders Q2 Outreach"
                className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              />
            </div>
            <div>
              <label className="mb-2 block text-xs text-slate-400">Sequence Steps</label>
              <CampaignBuilder steps={newSteps} onChange={setNewSteps} />
            </div>
            <div className="flex justify-end gap-3">
              <button onClick={() => setShowNew(false)} className="rounded-lg border border-slate-700/60 px-4 py-2 text-sm text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500">
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!newName.trim()}
                className="rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              >
                Create Campaign
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Enroll modal */}
      {showEnroll && (
        <Modal title="Enroll Leads" onClose={() => { setShowEnroll(null); setEnrollUrls(''); setEnrollResult(null) }}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-slate-400">Paste LinkedIn profile URLs, one per line.</p>
            <textarea
              value={enrollUrls}
              onChange={(e) => setEnrollUrls(e.target.value)}
              rows={6}
              placeholder={"https://linkedin.com/in/profile-1\nhttps://linkedin.com/in/profile-2"}
              className="w-full resize-none rounded-lg border border-slate-700/60 bg-slate-900/60 p-3 text-sm text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
            />
            {enrollResult && (
              <p className={`text-xs ${enrollResult.success ? 'text-emerald-400' : 'text-red-400'}`}>
                {enrollResult.message}
              </p>
            )}
            <div className="flex justify-end gap-3">
              <button onClick={() => { setShowEnroll(null); setEnrollUrls(''); setEnrollResult(null) }} className="rounded-lg border border-slate-700/60 px-4 py-2 text-sm text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500">
                Cancel
              </button>
              <button
                onClick={handleEnroll}
                className="rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              >
                Enroll
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
