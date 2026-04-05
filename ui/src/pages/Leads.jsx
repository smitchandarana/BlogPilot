import { useState, useEffect } from 'react'
import { Download, RefreshCw, ExternalLink, Search, Loader2 } from 'lucide-react'
import { leads as leadsApi } from '../api/client'

const EMAIL_STATUS_STYLES = {
  NOT_FOUND: 'bg-slate-700/60 text-slate-400',
  FOUND: 'bg-blue-500/15 text-blue-400',
  VERIFIED: 'bg-emerald-500/15 text-emerald-400',
  BOUNCED: 'bg-red-500/15 text-red-400',
}

export default function Leads() {
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [companyFilter, setCompanyFilter] = useState('')
  const [enriching, setEnriching] = useState(new Set())
  const [exportError, setExportError] = useState('')

  const fetchLeads = async () => {
    try {
      const params = {}
      if (statusFilter) params.status = statusFilter
      if (companyFilter) params.company = companyFilter
      if (search) params.search = search
      const res = await leadsApi.list(params)
      setLeads(res.data || [])
    } catch {
      // keep existing data
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLeads()
  }, [statusFilter, companyFilter])

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(fetchLeads, 400)
    return () => clearTimeout(timer)
  }, [search])

  const filtered = leads

  const handleEnrich = async (id) => {
    setEnriching((prev) => new Set([...prev, id]))
    const clearSpinner = () =>
      setEnriching((prev) => { const s = new Set(prev); s.delete(id); return s })
    try {
      await leadsApi.enrich(id)
      // Refresh after a short delay; always clear spinner regardless of refresh outcome
      setTimeout(() => fetchLeads().finally(clearSpinner), 2000)
    } catch {
      clearSpinner()
    }
  }

  const handleEnrichAll = async () => {
    try {
      await leadsApi.enrichAll()
      setTimeout(fetchLeads, 3000)
    } catch {}
  }

  const handleExport = async () => {
    setExportError('')
    try {
      const res = await leadsApi.export()
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'leads.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setExportError('Export failed — please try again')
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-100">Leads</h1>
          <p className="mt-0.5 text-sm text-slate-500">{leads.length} total · {leads.filter((l) => l.email_status === 'VERIFIED').length} verified emails</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleEnrichAll}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-slate-700/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Enrich All
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-slate-700/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>
        </div>
      </div>

      {exportError && (
        <p className="text-xs text-red-400">{exportError}</p>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, title…"
            className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 pl-9 pr-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
        >
          <option value="">All statuses</option>
          <option value="VERIFIED">Verified</option>
          <option value="FOUND">Found</option>
          <option value="NOT_FOUND">Not Found</option>
          <option value="BOUNCED">Bounced</option>
        </select>
        <input
          value={companyFilter}
          onChange={(e) => setCompanyFilter(e.target.value)}
          placeholder="Company…"
          className="rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
        />
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12 gap-2 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading leads…
          </div>
        ) : (
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="border-b border-slate-700/60">
                {['Name', 'Title', 'Company', 'LinkedIn', 'Email', 'Status', 'Source', 'Actions'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/30">
              {filtered.map((lead) => (
                <tr key={lead.id} className="group hover:bg-slate-800/60 transition-colors duration-150">
                  <td className="px-4 py-3 font-medium text-slate-200 whitespace-nowrap">
                    {lead.first_name} {lead.last_name}
                  </td>
                  <td className="px-4 py-3 text-slate-400 max-w-[150px] truncate">{lead.title}</td>
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap">{lead.company}</td>
                  <td className="px-4 py-3">
                    {lead.linkedin_url && lead.linkedin_url !== '#' ? (
                      <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-violet-400 hover:text-violet-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500">
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-400 max-w-[180px] truncate">
                    {lead.email || <span className="text-slate-600">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${EMAIL_STATUS_STYLES[lead.email_status] || ''}`}>
                      {(lead.email_status || 'NOT_FOUND').replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500 capitalize">{(lead.source || '').replace('_', ' ')}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleEnrich(lead.id)}
                      disabled={enriching.has(lead.id) || lead.email_status === 'VERIFIED'}
                      className="rounded-md border border-slate-700/40 px-2.5 py-1 text-xs text-slate-400 transition-colors hover:text-violet-300 hover:border-violet-600/40 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500"
                    >
                      {enriching.has(lead.id) ? 'Enriching…' : 'Enrich'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && filtered.length === 0 && (
          <div className="py-12 text-center text-sm text-slate-500">No leads found.</div>
        )}
      </div>
    </div>
  )
}
