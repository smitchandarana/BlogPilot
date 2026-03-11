import { useState, useEffect } from 'react'
import { Save, Loader2, CheckCircle2 } from 'lucide-react'
import { config as configApi } from '../api/client'

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
const DAY_LABELS = { monday: 'Mon', tuesday: 'Tue', wednesday: 'Wed', thursday: 'Thu', friday: 'Fri', saturday: 'Sat', sunday: 'Sun' }

const MODULE_LABELS = {
  feed_engagement: 'Feed Engagement',
  campaigns: 'Campaigns',
  content_studio: 'Content Studio',
  email_enrichment: 'Email Enrichment',
}

const DEFAULT_SETTINGS = {
  modules: { feed_engagement: true, campaigns: true, content_studio: true, email_enrichment: true },
  schedule: { active_days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'], start_hour: 9, end_hour: 18, feed_scan_interval_minutes: 20 },
  circuit_breaker: { enabled: true, error_threshold: 3, pause_duration_minutes: 30 },
}

function Toggle({ checked, onChange }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${checked ? 'bg-violet-600' : 'bg-slate-700'}`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform duration-200 ${checked ? 'translate-x-4' : 'translate-x-1'}`}
      />
    </button>
  )
}

function SectionCard({ title, children }) {
  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
      <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">{title}</h2>
      {children}
    </div>
  )
}

export default function EngineControl() {
  const [form, setForm] = useState(DEFAULT_SETTINGS)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    configApi.getSettings().then((res) => {
      const d = res.data
      setForm({
        modules: d.modules || DEFAULT_SETTINGS.modules,
        schedule: d.schedule || DEFAULT_SETTINGS.schedule,
        circuit_breaker: d.circuit_breaker || DEFAULT_SETTINGS.circuit_breaker,
      })
    }).catch(() => {})
  }, [])

  const setModule = (key, val) =>
    setForm((f) => ({ ...f, modules: { ...f.modules, [key]: val } }))

  const setSchedule = (key, val) =>
    setForm((f) => ({ ...f, schedule: { ...f.schedule, [key]: val } }))

  const setCB = (key, val) =>
    setForm((f) => ({ ...f, circuit_breaker: { ...f.circuit_breaker, [key]: val } }))

  const toggleDay = (day) => {
    const days = form.schedule.active_days || []
    const next = days.includes(day) ? days.filter((d) => d !== day) : [...days, day]
    setSchedule('active_days', next)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await configApi.updateSettings(form)
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
          <h1 className="text-xl font-semibold tracking-tight text-slate-100">Engine Control</h1>
          <p className="mt-0.5 text-sm text-slate-500">Configure modules, activity window, and safety limits.</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-[background,box-shadow] duration-200 hover:bg-violet-600 hover:shadow-[0_0_24px_rgba(124,58,237,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-60 active:scale-[0.98]"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : saved ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          {saved ? 'Saved' : 'Save Changes'}
        </button>
      </div>

      {/* Module toggles */}
      <SectionCard title="Modules">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {Object.entries(MODULE_LABELS).map(([key, label]) => (
            <div key={key} className="flex items-center justify-between rounded-lg border border-slate-700/40 bg-slate-900/30 px-4 py-3">
              <span className="text-sm text-slate-300">{label}</span>
              <Toggle
                checked={!!form.modules[key]}
                onChange={(v) => setModule(key, v)}
              />
            </div>
          ))}
        </div>
      </SectionCard>

      {/* Activity window */}
      <SectionCard title="Activity Window">
        <div className="flex flex-col gap-4">
          <div>
            <label className="mb-2 block text-xs text-slate-400">Active Days</label>
            <div className="flex gap-2 flex-wrap">
              {DAYS.map((day) => {
                const active = (form.schedule.active_days || []).includes(day)
                return (
                  <button
                    key={day}
                    onClick={() => toggleDay(day)}
                    className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                      active
                        ? 'border-violet-600/50 bg-violet-700/20 text-violet-300'
                        : 'border-slate-700/60 bg-slate-800/40 text-slate-400 hover:text-slate-300'
                    }`}
                  >
                    {DAY_LABELS[day]}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1.5 block text-xs text-slate-400">Start Hour (24h)</label>
              <input
                type="number"
                min={0}
                max={23}
                value={form.schedule.start_hour}
                onChange={(e) => setSchedule('start_hour', parseInt(e.target.value) || 0)}
                className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs text-slate-400">End Hour (24h)</label>
              <input
                type="number"
                min={0}
                max={23}
                value={form.schedule.end_hour}
                onChange={(e) => setSchedule('end_hour', parseInt(e.target.value) || 0)}
                className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs text-slate-400">Scan Interval (min)</label>
              <input
                type="number"
                min={5}
                max={120}
                value={form.schedule.feed_scan_interval_minutes}
                onChange={(e) => setSchedule('feed_scan_interval_minutes', parseInt(e.target.value) || 20)}
                className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              />
            </div>
          </div>
        </div>
      </SectionCard>

      {/* Circuit breaker */}
      <SectionCard title="Circuit Breaker">
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-300">Enable Circuit Breaker</p>
              <p className="text-xs text-slate-500 mt-0.5">Auto-pause on consecutive errors</p>
            </div>
            <Toggle
              checked={!!form.circuit_breaker.enabled}
              onChange={(v) => setCB('enabled', v)}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-xs text-slate-400">Error Threshold</label>
              <input
                type="number"
                min={1}
                max={20}
                value={form.circuit_breaker.error_threshold}
                onChange={(e) => setCB('error_threshold', parseInt(e.target.value) || 3)}
                className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs text-slate-400">Pause Duration (min)</label>
              <input
                type="number"
                min={5}
                max={240}
                value={form.circuit_breaker.pause_duration_minutes}
                onChange={(e) => setCB('pause_duration_minutes', parseInt(e.target.value) || 30)}
                className="w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              />
            </div>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
