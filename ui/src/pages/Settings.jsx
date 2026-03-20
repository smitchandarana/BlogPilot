import { useState, useEffect, useCallback } from 'react'
import { Eye, EyeOff, Save, Loader2, CheckCircle2, AlertTriangle, X, RotateCcw, Power } from 'lucide-react'
import { config as configApi, server as serverApi } from '../api/client'

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

function InputRow({ label, children }) {
  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <label className="shrink-0 text-sm text-slate-300 sm:w-48">{label}</label>
      <div className="flex-1">{children}</div>
    </div>
  )
}

const inputCls = 'w-full rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40'

const ACTION_TYPES = ['likes', 'comments', 'connections', 'profile_visits', 'inmails', 'posts_published']
const DELAY_KEYS = [
  ['before_like', 'Before Like'],
  ['before_comment', 'Before Comment'],
  ['before_connect', 'Before Connect'],
  ['between_posts', 'Between Posts'],
]

const DEFAULT_SETTINGS = {
  ai: { model: 'llama3-70b-8192', temperature: 0.7, max_tokens: 500 },
  daily_budget: { likes: 30, comments: 12, connections: 15, profile_visits: 50, inmails: 5, posts_published: 5 },
  delays: { before_like_min: 3, before_like_max: 12, before_comment_min: 8, before_comment_max: 45, before_connect_min: 5, before_connect_max: 20, between_posts_min: 4, between_posts_max: 15 },
  browser: { headless: false, stealth: true, profile_path: './browser_profile' },
  storage: { database_path: './data/engine.db', log_retention_days: 90 },
}

export default function Settings() {
  const [form, setForm] = useState(DEFAULT_SETTINGS)
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [groqStatus, setGroqStatus] = useState(null) // { configured, masked_key }
  const [savingKey, setSavingKey] = useState(false)
  const [keySaved, setKeySaved] = useState(false)
  const [groqKeyError, setGroqKeyError] = useState('')
  const [orKey, setOrKey] = useState('')
  const [showOrKey, setShowOrKey] = useState(false)
  const [orStatus, setOrStatus] = useState(null)
  const [savingOrKey, setSavingOrKey] = useState(false)
  const [orKeySaved, setOrKeySaved] = useState(false)
  const [orKeyError, setOrKeyError] = useState('')
  const [liPassword, setLiPassword] = useState('')
  const [liEmail, setLiEmail] = useState('')
  const [liStatus, setLiStatus] = useState(null)
  const [savingLi, setSavingLi] = useState(false)
  const [liSaved, setLiSaved] = useState(false)
  const [liError, setLiError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [showConfirmClear, setShowConfirmClear] = useState(false)
  const [showConfirmRestart, setShowConfirmRestart] = useState(false)
  const [showConfirmShutdown, setShowConfirmShutdown] = useState(false)
  const [serverAction, setServerAction] = useState(null) // 'restarting' | 'shutdown' | null

  useEffect(() => {
    configApi.getSettings().then((res) => {
      const d = res.data
      setForm({
        ai: d.ai || DEFAULT_SETTINGS.ai,
        daily_budget: d.daily_budget || DEFAULT_SETTINGS.daily_budget,
        delays: d.delays || DEFAULT_SETTINGS.delays,
        browser: d.browser || DEFAULT_SETTINGS.browser,
        storage: d.storage || DEFAULT_SETTINGS.storage,
      })
    }).catch(() => {})
    configApi.getGroqKeyStatus().then((res) => setGroqStatus(res.data)).catch(() => {})
    configApi.getOpenRouterKeyStatus().then((res) => setOrStatus(res.data)).catch(() => {})
    configApi.getLinkedInStatus().then((res) => setLiStatus(res.data)).catch(() => {})
  }, [])

  const handleSaveGroqKey = async () => {
    if (!apiKey.trim()) return
    setSavingKey(true)
    setGroqKeyError('')
    try {
      const res = await configApi.saveGroqKey(apiKey.trim())
      setGroqStatus(res.data)
      setApiKey('')
      setKeySaved(true)
      setTimeout(() => setKeySaved(false), 3000)
    } catch (e) {
      setGroqKeyError(e?.response?.data?.detail || 'Failed to save key')
    } finally { setSavingKey(false) }
  }

  const handleSaveOrKey = async () => {
    if (!orKey.trim()) return
    setSavingOrKey(true)
    setOrKeyError('')
    try {
      const res = await configApi.saveOpenRouterKey(orKey.trim())
      setOrStatus(res.data)
      setOrKey('')
      setOrKeySaved(true)
      setTimeout(() => setOrKeySaved(false), 3000)
    } catch (e) {
      setOrKeyError(e?.response?.data?.detail || 'Failed to save key')
    } finally { setSavingOrKey(false) }
  }

  const set = (section, key, val) =>
    setForm((f) => ({ ...f, [section]: { ...f[section], [key]: val } }))

  const pollUntilReady = useCallback(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch('http://localhost:8000/health')
        if (res.ok) {
          clearInterval(interval)
          setServerAction(null)
          window.location.reload()
        }
      } catch { /* server still down */ }
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  const handleRestart = async () => {
    setShowConfirmRestart(false)
    setServerAction('restarting')
    try {
      await serverApi.restart()
    } catch { /* expected — server is restarting */ }
    setTimeout(pollUntilReady, 1500)
  }

  const handleShutdown = async () => {
    setShowConfirmShutdown(false)
    setServerAction('shutdown')
    try {
      await serverApi.shutdown()
    } catch { /* expected — server is shutting down */ }
  }

  const [saveError, setSaveError] = useState('')

  const handleSave = async () => {
    setSaving(true)
    setSaveError('')
    try {
      await configApi.updateSettings(form)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      setSaveError(e?.response?.data?.detail || 'Failed to save settings — is the server running?')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-100">Settings</h1>
          <p className="mt-0.5 text-sm text-slate-500">Configure API keys, rate limits, delays, and browser behaviour.</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-[background,box-shadow] duration-200 hover:bg-violet-600 hover:shadow-[0_0_24px_rgba(124,58,237,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-60 active:scale-[0.98]"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : saved ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <Save className="h-4 w-4" />}
            {saved ? 'Saved' : 'Save Changes'}
          </button>
          {saveError && <p className="text-xs text-red-400">{saveError}</p>}
        </div>
      </div>

      <SectionCard title="AI Configuration" description="Groq API settings for comment generation and scoring.">
        <div className="flex flex-col gap-4">
          <InputRow label="Groq API Key">
            <div className="flex flex-col gap-2">
              {groqStatus?.configured && (
                <div className="flex items-center gap-2 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  <span className="text-emerald-400">Configured</span>
                  <span className="text-slate-500">({groqStatus.masked_key})</span>
                </div>
              )}
              {groqStatus && !groqStatus.configured && (
                <div className="flex items-center gap-2 text-sm">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <span className="text-amber-400">Not configured — AI features disabled</span>
                </div>
              )}
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={groqStatus?.configured ? 'Enter new key to replace...' : 'gsk_your_api_key_here'}
                    className={`${inputCls} pr-10`}
                  />
                  <button
                    onClick={() => setShowKey(!showKey)}
                    aria-label={showKey ? 'Hide API key' : 'Show API key'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none"
                  >
                    {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <button
                  onClick={handleSaveGroqKey}
                  disabled={!apiKey.trim() || savingKey}
                  className="flex shrink-0 items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:opacity-40"
                >
                  {savingKey ? <Loader2 className="h-4 w-4 animate-spin" /> : keySaved ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
                  {keySaved ? 'Saved' : 'Save Key'}
                </button>
              </div>
              {groqKeyError && <p className="text-xs text-red-400 mt-1">{groqKeyError}</p>}
            </div>
          </InputRow>
          <InputRow label="OpenRouter API Key">
            <div className="flex flex-col gap-2">
              <p className="text-xs text-slate-500">
                Free — used for background processing (extraction, relevance scoring, topic research).
                Get your key at{' '}
                <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer"
                  className="text-violet-400 hover:text-violet-300 underline underline-offset-2">
                  openrouter.ai
                </a>
              </p>
              {orStatus?.configured && (
                <div className="flex items-center gap-2 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  <span className="text-emerald-400">Configured</span>
                  <span className="text-slate-500">({orStatus.masked_key})</span>
                </div>
              )}
              {orStatus && !orStatus.configured && (
                <div className="flex items-center gap-2 text-sm">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <span className="text-amber-400">Not configured — background AI uses Groq (burns daily quota)</span>
                </div>
              )}
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type={showOrKey ? 'text' : 'password'}
                    value={orKey}
                    onChange={(e) => setOrKey(e.target.value)}
                    placeholder={orStatus?.configured ? 'Enter new key to replace...' : 'sk-or-v1_your_key_here'}
                    className={`${inputCls} pr-10`}
                  />
                  <button
                    onClick={() => setShowOrKey(!showOrKey)}
                    aria-label={showOrKey ? 'Hide API key' : 'Show API key'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none"
                  >
                    {showOrKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <button
                  onClick={handleSaveOrKey}
                  disabled={savingOrKey || !orKey.trim()}
                  className="flex items-center gap-1.5 rounded-lg bg-violet-700 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                >
                  {savingOrKey ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : orKeySaved ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" /> : <Save className="h-3.5 w-3.5" />}
                  {orKeySaved ? 'Saved!' : 'Save'}
                </button>
              </div>
              {orKeyError && <p className="text-xs text-red-400 mt-1">{orKeyError}</p>}
            </div>
          </InputRow>
          <InputRow label="Model">
            <select value={form.ai.model} onChange={(e) => set('ai', 'model', e.target.value)} className={inputCls}>
              <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile (recommended)</option>
              <option value="llama3-70b-8192">llama3-70b-8192</option>
              <option value="llama3-8b-8192">llama3-8b-8192</option>
              <option value="mixtral-8x7b-32768">mixtral-8x7b-32768</option>
            </select>
          </InputRow>
          <InputRow label={`Temperature (${form.ai.temperature})`}>
            <input
              type="range" min={0} max={1} step={0.05}
              value={form.ai.temperature}
              onChange={(e) => set('ai', 'temperature', parseFloat(e.target.value))}
              className="w-full accent-violet-500"
            />
          </InputRow>
        </div>
      </SectionCard>

      <SectionCard title="LinkedIn Credentials" description="Stored encrypted using Fernet. Never shown in plaintext after saving.">
        <div className="flex flex-col gap-4">
          <div className="flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            Credentials are encrypted on disk using Fernet. Never stored or logged in plaintext.
          </div>
          {liStatus?.configured && (
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span className="text-emerald-400">Credentials saved</span>
              <span className="text-slate-500">— enter new values below to replace</span>
            </div>
          )}
          {liError && (
            <div className="flex items-center gap-2 text-sm text-red-400">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {liError}
            </div>
          )}
          <InputRow label="LinkedIn Email">
            <input type="email" value={liEmail} onChange={(e) => setLiEmail(e.target.value)} placeholder="your@email.com" className={inputCls} />
          </InputRow>
          <InputRow label="LinkedIn Password">
            <input type="password" value={liPassword} onChange={(e) => setLiPassword(e.target.value)} placeholder="••••••••" className={inputCls} />
          </InputRow>
          <div className="flex justify-end">
            <button
              onClick={async () => {
                if (!liEmail.trim() || !liPassword.trim()) {
                  setLiError('Both email and password are required')
                  return
                }
                setLiError('')
                setSavingLi(true)
                try {
                  const res = await configApi.saveLinkedInCredentials(liEmail.trim(), liPassword.trim())
                  setLiStatus({ configured: true })
                  setLiEmail('')
                  setLiPassword('')
                  setLiSaved(true)
                  setTimeout(() => setLiSaved(false), 3000)
                } catch (e) {
                  setLiError(e?.response?.data?.detail || 'Failed to save credentials')
                } finally {
                  setSavingLi(false)
                }
              }}
              disabled={savingLi || !liEmail.trim() || !liPassword.trim()}
              className="flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:opacity-40"
            >
              {savingLi ? <Loader2 className="h-4 w-4 animate-spin" /> : liSaved ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
              {liSaved ? 'Saved & Encrypted' : 'Save Credentials'}
            </button>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Daily Budget Limits" description="Max actions per day. Resets at midnight.">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {ACTION_TYPES.map((action) => (
            <div key={action}>
              <label className="mb-1.5 block text-xs text-slate-400 capitalize">{action.replace(/_/g, ' ')}</label>
              <input
                type="number" min={0} max={200}
                value={form.daily_budget[action] || 0}
                onChange={(e) => set('daily_budget', action, parseInt(e.target.value) || 0)}
                className={inputCls}
              />
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Human Behaviour Delays" description="Random delay range (seconds) before each action type.">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {DELAY_KEYS.map(([key, label]) => (
            <div key={key} className="flex flex-col gap-1.5">
              <label className="text-xs text-slate-400">{label} (s)</label>
              <div className="flex items-center gap-2">
                <input
                  type="number" min={0}
                  value={form.delays[`${key}_min`] || 0}
                  onChange={(e) => set('delays', `${key}_min`, Number(e.target.value))}
                  className={`${inputCls} w-20`}
                />
                <span className="text-slate-500 text-sm">–</span>
                <input
                  type="number" min={0}
                  value={form.delays[`${key}_max`] || 0}
                  onChange={(e) => set('delays', `${key}_max`, Number(e.target.value))}
                  className={`${inputCls} w-20`}
                />
              </div>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Browser" description="Playwright browser settings for LinkedIn automation.">
        <div className="flex flex-col gap-4">
          <InputRow label="Profile Path">
            <input type="text" value={form.browser.profile_path} onChange={(e) => set('browser', 'profile_path', e.target.value)} className={inputCls} />
          </InputRow>
          <div className="flex gap-6">
            {[['headless', 'Run Headless'], ['stealth', 'Stealth Mode']].map(([key, label]) => (
              <label key={key} className="flex cursor-pointer items-center gap-2.5">
                <input
                  type="checkbox"
                  checked={!!form.browser[key]}
                  onChange={(e) => set('browser', key, e.target.checked)}
                  className="h-4 w-4 rounded accent-violet-500"
                />
                <span className="text-sm text-slate-300">{label}</span>
              </label>
            ))}
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Storage">
        <div className="flex flex-col gap-4">
          <InputRow label="Database Path">
            <input type="text" value={form.storage.database_path} readOnly className={`${inputCls} cursor-default opacity-60`} />
          </InputRow>
          <InputRow label="Log Retention (days)">
            <input
              type="number" min={7} max={365}
              value={form.storage.log_retention_days}
              onChange={(e) => set('storage', 'log_retention_days', parseInt(e.target.value) || 90)}
              className={inputCls}
            />
          </InputRow>
        </div>
      </SectionCard>

      <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-5">
        <h2 className="mb-1 text-sm font-semibold text-red-400">Danger Zone</h2>
        <p className="mb-4 text-xs text-slate-500">These actions are irreversible. Proceed with caution.</p>

        <div className="mb-4 flex flex-col gap-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-4">
          <h3 className="text-sm font-medium text-amber-300">Server Control</h3>
          <p className="text-xs text-slate-500">Restart or shut down the entire backend process. The engine will be stopped gracefully before the action.</p>
          <div className="flex gap-3">
            <button
              onClick={() => setShowConfirmRestart(true)}
              className="flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-sm font-medium text-amber-300 transition-colors hover:bg-amber-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
            >
              <RotateCcw className="h-4 w-4" />
              Restart Server
            </button>
            <button
              onClick={() => setShowConfirmShutdown(true)}
              className="flex items-center gap-2 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
            >
              <Power className="h-4 w-4" />
              Shutdown Server
            </button>
          </div>
        </div>

        <button
          onClick={() => setShowConfirmClear(true)}
          className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
        >
          Clear All Data
        </button>
      </div>

      {/* Server action overlay */}
      {serverAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-4 rounded-2xl border border-slate-700/60 bg-[#161b27] p-8 shadow-[0_24px_64px_rgba(0,0,0,0.5)]">
            {serverAction === 'restarting' ? (
              <>
                <Loader2 className="h-8 w-8 animate-spin text-amber-400" />
                <p className="text-base font-medium text-slate-200">Restarting server...</p>
                <p className="text-sm text-slate-500">Reconnecting automatically when ready.</p>
              </>
            ) : (
              <>
                <Power className="h-8 w-8 text-red-400" />
                <p className="text-base font-medium text-slate-200">Server has been shut down</p>
                <p className="text-sm text-slate-500">Start the backend manually to continue.</p>
              </>
            )}
          </div>
        </div>
      )}

      {/* Confirm restart modal */}
      {showConfirmRestart && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-slate-700/60 bg-[#161b27] p-6 shadow-[0_24px_64px_rgba(0,0,0,0.5)]">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-100">Restart Server?</h3>
              <button onClick={() => setShowConfirmRestart(false)} className="rounded-lg p-1 text-slate-400 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="mb-5 text-sm text-slate-400">
              The engine will be stopped gracefully and the entire backend process will restart. The UI will automatically reconnect when the server is back.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setShowConfirmRestart(false)} className="rounded-lg border border-slate-700/60 px-4 py-2 text-sm text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500">
                Cancel
              </button>
              <button
                onClick={handleRestart}
                className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
              >
                Yes, Restart
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm shutdown modal */}
      {showConfirmShutdown && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-slate-700/60 bg-[#161b27] p-6 shadow-[0_24px_64px_rgba(0,0,0,0.5)]">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-100">Shutdown Server?</h3>
              <button onClick={() => setShowConfirmShutdown(false)} className="rounded-lg p-1 text-slate-400 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="mb-5 text-sm text-slate-400">
              The engine will be stopped and the backend process will be terminated. You will need to manually restart the server to use the application again.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setShowConfirmShutdown(false)} className="rounded-lg border border-slate-700/60 px-4 py-2 text-sm text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500">
                Cancel
              </button>
              <button
                onClick={handleShutdown}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
              >
                Yes, Shutdown
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm clear data modal */}
      {showConfirmClear && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-slate-700/60 bg-[#161b27] p-6 shadow-[0_24px_64px_rgba(0,0,0,0.5)]">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-100">Clear All Data?</h3>
              <button onClick={() => setShowConfirmClear(false)} className="rounded-lg p-1 text-slate-400 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="mb-5 text-sm text-slate-400">
              This will delete all posts, leads, action logs, campaigns, and analytics data. This cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setShowConfirmClear(false)} className="rounded-lg border border-slate-700/60 px-4 py-2 text-sm text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500">
                Cancel
              </button>
              <button
                onClick={async () => {
                  setShowConfirmClear(false)
                  try {
                    await serverApi.clearData()
                    window.location.reload()
                  } catch (e) {
                    setSaveError(e?.response?.data?.detail || 'Failed to clear data')
                  }
                }}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
              >
                Yes, Delete Everything
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
