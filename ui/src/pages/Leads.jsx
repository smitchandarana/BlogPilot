import { useState } from 'react'
import { Download, RefreshCw, ExternalLink, Search } from 'lucide-react'
import { leads as leadsApi } from '../api/client'

const EMAIL_STATUS_STYLES = {
  NOT_FOUND: 'bg-slate-700/60 text-slate-400',
  FOUND: 'bg-blue-500/15 text-blue-400',
  VERIFIED: 'bg-emerald-500/15 text-emerald-400',
  BOUNCED: 'bg-red-500/15 text-red-400',
}

const MOCK_LEADS = [
  { id: '1', first_name: 'Rahul', last_name: 'Sharma', title: 'VP Analytics', company: 'TechCorp', linkedin_url: '#', email: 'rahul@techcorp.com', email_status: 'VERIFIED', source: 'feed_scan' },
  { id: '2', first_name: 'Priya', last_name: 'Mehta', title: 'Head of Data', company: 'DataFlow', linkedin_url: '#', email: 'priya@dataflow.io', email_status: 'FOUND', source: 'feed_scan' },
  { id: '3', first_name: 'James', last_name: 'Liu', title: 'CFO', company: 'FinanceEdge', linkedin_url: '#', email: null, email_status: 'NOT_FOUND', source: 'campaign' },
  { id: '4', first_name: 'Sarah', last_name: 'Chen', title: 'Director of BI', company: 'Insights Co', linkedin_url: '#', email: 'sarah@insights.co', email_status: 'VERIFIED', source: 'feed_scan' },
  { id: '5', first_name: 'Tom', last_name: 'Nguyen', title: 'Analytics Manager', company: 'DataDriven', linkedin_url: '#', email: 'tom@datadriven.com', email_status: 'BOUNCED', source: 'campaign' },
  { id: '6', first_name: 'Maria', last_name: 'Lopez', title: 'COO', company: 'OpsMax', linkedin_url: '#', email: null, email_status: 'NOT_FOUND', source: 'feed_scan' },
  { id: '7', first_name: 'David', last_name: 'Park', title: 'CEO', company: 'Metrix Labs', linkedin_url: '#', email: 'david@metrix.io', email_status: 'FOUND', source: 'feed_scan' },
  { id: '8', first_name: 'Alex', last_name: 'Kim', title: 'Chief Data Officer', company: 'DataFirst', linkedin_url: '#', email: 'alex@datafirst.com', email_status: 'VERIFIED', source: 'campaign' },
]

export default function Leads() {
  const [leads, setLeads] = useState(MOCK_LEADS)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [companyFilter, setCompanyFilter] = useState('')
  const [enriching, setEnriching] = useState(new Set())

  const filtered = leads.filter((l) => {
    const q = search.toLowerCase()
    const matchSearch = !q || `${l.first_name} ${l.last_name} ${l.title}`.toLowerCase().includes(q)
    const matchStatus = !statusFilter || l.email_status === statusFilter
    const matchCompany = !companyFilter || l.company.toLowerCase().includes(companyFilter.toLowerCase())
    return matchSearch && matchStatus && matchCompany
  })

  const handleEnrich = async (id) => {
    setEnriching((prev) => new Set([...prev, id]))
    try {
      await leadsApi.enrich(id)
    } catch {}
    setTimeout(() => {
      setEnriching((prev) => { const s = new Set(prev); s.delete(id); return s })
      setLeads((prev) => prev.map((l) => l.id === id && l.email_status === 'NOT_FOUND' ? { ...l, email_status: 'FOUND', email: `${l.first_name.toLowerCase()}@${l.company.toLowerCase().replace(/\s/g, '')}.com` } : l))
    }, 1500)
  }

  const handleEnrichAll = async () => {
    try {
      await leadsApi.enrichAll()
    } catch {}
  }

  const handleExport = async () => {
    try {
      const res = await leadsApi.export()
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'leads.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      const csv = 'first_name,last_name,title,company,email,email_status\n' +
        leads.map((l) => `${l.first_name},${l.last_name},${l.title},${l.company},${l.email || ''},${l.email_status}`).join('\n')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'leads.csv'
      a.click()
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
                  <a href={lead.linkedin_url} className="inline-flex items-center gap-1 text-violet-400 hover:text-violet-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500">
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </td>
                <td className="px-4 py-3 text-slate-400 max-w-[180px] truncate">
                  {lead.email || <span className="text-slate-600">—</span>}
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${EMAIL_STATUS_STYLES[lead.email_status]}`}>
                    {lead.email_status.replace('_', ' ')}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-slate-500 capitalize">{lead.source.replace('_', ' ')}</td>
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
        {filtered.length === 0 && (
          <div className="py-12 text-center text-sm text-slate-500">No leads match your filters.</div>
        )}
      </div>
    </div>
  )
}
