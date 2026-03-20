import { useState, useEffect, useRef } from 'react'
import { Key, Linkedin, Tags, Rocket, CheckCircle2, AlertTriangle, Loader2, Eye, EyeOff, Plus, X } from 'lucide-react'
import { config as configApi } from '../api/client'

const inputCls =
  'w-full rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40 transition-colors'

const DEFAULT_TOPICS = [
  'Business Intelligence',
  'Data Analytics',
  'Reporting Solutions',
  'Dashboard Design',
  'Data Visualization',
  'Business Reporting',
  'KPI Tracking',
  'Financial Reporting',
  'Sales Analytics',
  'Operations Analytics',
  'Data-Driven Decision Making',
  'Power BI',
  'Tableau',
  'Excel Automation',
  'Data Strategy',
  'Business Performance',
  'Revenue Analytics',
  'Customer Analytics',
  'Supply Chain Analytics',
  'HR Analytics',
]

// ─── Step 1: Groq API Key ─────────────────────────────────────────────────────

function StepGroq({ onComplete }) {
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null) // null | { valid: bool, model: str, error: str }

  const handleTest = async () => {
    if (!apiKey.trim()) return
    setTesting(true)
    setTestResult(null)
    try {
      // Save key — a successful save is proof of configuration
      await configApi.saveGroqKey(apiKey.trim())
      setTestResult({ valid: true, model: 'llama-3.3-70b-versatile' })
    } catch (e) {
      setTestResult({ valid: false, error: e?.response?.data?.detail || 'Connection failed — check your key.' })
    } finally {
      setTesting(false)
    }
  }

  const handleContinue = () => {
    if (!testResult?.valid) return
    onComplete({ groqConnected: true })
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-slate-300">Groq API Key</label>
        <p className="text-xs text-slate-500">
          Required for AI comment generation and relevance scoring. Free tier available at{' '}
          <a
            href="https://console.groq.com/keys"
            target="_blank"
            rel="noopener noreferrer"
            className="text-violet-400 underline underline-offset-2 hover:text-violet-300 transition-colors"
          >
            console.groq.com
          </a>
        </p>
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type={showKey ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => { setApiKey(e.target.value); setTestResult(null) }}
            onKeyDown={(e) => e.key === 'Enter' && handleTest()}
            placeholder="gsk_your_api_key_here"
            className={`${inputCls} pr-10`}
            autoFocus
          />
          <button
            onClick={() => setShowKey(!showKey)}
            aria-label={showKey ? 'Hide key' : 'Show key'}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none"
          >
            {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        <button
          onClick={handleTest}
          disabled={!apiKey.trim() || testing}
          className="flex shrink-0 items-center gap-2 rounded-lg border border-slate-600/60 bg-slate-700/50 px-4 py-2 text-sm font-medium text-slate-200 transition-colors hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-40"
        >
          {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Test'}
        </button>
      </div>

      {testResult && (
        <div
          className={`flex items-start gap-3 rounded-lg border px-3.5 py-3 text-sm transition-opacity ${
            testResult.valid
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
              : 'border-red-500/30 bg-red-500/10 text-red-300'
          }`}
        >
          {testResult.valid ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          ) : (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          )}
          <span>
            {testResult.valid
              ? `Connected — model: ${testResult.model}`
              : testResult.error}
          </span>
        </div>
      )}

      <div className="flex justify-end pt-1">
        <button
          onClick={handleContinue}
          disabled={!testResult?.valid}
          className="flex items-center gap-2 rounded-lg bg-violet-700 px-5 py-2.5 text-sm font-semibold text-white shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-[background,box-shadow,opacity] hover:bg-violet-600 hover:shadow-[0_0_24px_rgba(124,58,237,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-40 active:scale-[0.98]"
        >
          Save &amp; Continue
        </button>
      </div>
    </div>
  )
}

// ─── Step 2: LinkedIn Credentials ─────────────────────────────────────────────

function StepLinkedIn({ onComplete, onSkip }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null) // null | { success: bool, error: str }

  const handleTest = async () => {
    if (!email.trim() || !password.trim()) return
    setTesting(true)
    setTestResult(null)
    try {
      // Save credentials — a successful save is proof of configuration
      await configApi.saveLinkedInCredentials(email.trim(), password.trim())
      setTestResult({ success: true })
    } catch (e) {
      setTestResult({ success: false, error: e?.response?.data?.detail || 'Failed to save credentials.' })
    } finally {
      setTesting(false)
    }
  }

  const handleContinue = () => {
    onComplete({ linkedInConnected: true })
  }

  const canContinue = testResult?.success

  return (
    <div className="flex flex-col gap-5">
      {/* Risk warning */}
      <div className="flex items-start gap-3 rounded-lg border border-amber-500/25 bg-amber-500/8 px-3.5 py-3 text-sm text-amber-300">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          BlogPilot automates LinkedIn interactions. Use at your own risk. Your account may be
          reviewed by LinkedIn for unusual activity.
        </span>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-slate-300">LinkedIn Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => { setEmail(e.target.value); setTestResult(null) }}
            placeholder="your@email.com"
            className={inputCls}
            autoFocus
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-slate-300">LinkedIn Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setTestResult(null) }}
            placeholder="••••••••"
            className={inputCls}
          />
        </div>
      </div>

      <p className="text-xs text-slate-500">
        Credentials are encrypted on disk using Fernet symmetric encryption and never stored in plaintext.
      </p>

      {testResult && (
        <div
          className={`flex items-start gap-3 rounded-lg border px-3.5 py-3 text-sm ${
            testResult.success
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
              : 'border-red-500/30 bg-red-500/10 text-red-300'
          }`}
        >
          {testResult.success ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          ) : (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          )}
          <span>
            {testResult.success ? 'Credentials saved and encrypted.' : testResult.error}
          </span>
        </div>
      )}

      <div className="flex items-center justify-between pt-1">
        <button
          onClick={onSkip}
          className="rounded-lg border border-slate-700/60 px-4 py-2 text-sm text-slate-400 transition-colors hover:text-slate-200 hover:border-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500"
        >
          Skip for now
        </button>
        <div className="flex items-center gap-2">
          <button
            onClick={handleTest}
            disabled={!email.trim() || !password.trim() || testing}
            className="flex items-center gap-2 rounded-lg border border-slate-600/60 bg-slate-700/50 px-4 py-2 text-sm font-medium text-slate-200 transition-colors hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-40"
          >
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {testing ? 'Saving…' : 'Test Login'}
          </button>
          <button
            onClick={handleContinue}
            disabled={!canContinue}
            className="flex items-center gap-2 rounded-lg bg-violet-700 px-5 py-2.5 text-sm font-semibold text-white shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-[background,box-shadow,opacity] hover:bg-violet-600 hover:shadow-[0_0_24px_rgba(124,58,237,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-40 active:scale-[0.98]"
          >
            Save &amp; Continue
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Step 3: Select Topics ─────────────────────────────────────────────────────

function StepTopics({ onComplete }) {
  const [topics, setTopics] = useState(DEFAULT_TOPICS)
  const [selected, setSelected] = useState(new Set(DEFAULT_TOPICS))
  const [customInput, setCustomInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Try to load topics from backend on mount
  useEffect(() => {
    configApi.getTopics().then((res) => {
      const loaded = Array.isArray(res.data)
        ? res.data
        : Array.isArray(res.data?.topics)
        ? res.data.topics
        : null
      if (loaded && loaded.length > 0) {
        const deduped = [...new Set([...DEFAULT_TOPICS, ...loaded])]
        setTopics(deduped)
        setSelected(new Set(deduped))
      }
    }).catch(() => {})
  }, [])

  const toggleTopic = (topic) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(topic) ? next.delete(topic) : next.add(topic)
      return next
    })
  }

  const addCustom = () => {
    const val = customInput.trim()
    if (!val) return
    if (topics.includes(val)) {
      setSelected((prev) => new Set([...prev, val]))
    } else {
      setTopics((prev) => [...prev, val])
      setSelected((prev) => new Set([...prev, val]))
    }
    setCustomInput('')
  }

  const handleContinue = async () => {
    if (selected.size === 0) {
      setError('Select at least one topic to continue.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const topicList = [...selected]
      await configApi.updateTopics(topicList)
      onComplete({ topics: topicList })
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to save topics.')
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <p className="text-sm text-slate-400">
          Select the topics relevant to your LinkedIn audience. The AI uses these to score and filter posts.
        </p>
        <p className="text-xs text-slate-500">{selected.size} topic{selected.size !== 1 ? 's' : ''} selected</p>
      </div>

      <div className="max-h-52 overflow-y-auto rounded-lg border border-slate-700/60 bg-slate-800/30 p-3">
        <div className="grid grid-cols-2 gap-1.5">
          {topics.map((topic) => {
            const isSelected = selected.has(topic)
            return (
              <button
                key={topic}
                onClick={() => toggleTopic(topic)}
                className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500 ${
                  isSelected
                    ? 'bg-violet-700/30 text-violet-200 border border-violet-600/40'
                    : 'bg-slate-700/30 text-slate-400 border border-transparent hover:border-slate-600 hover:text-slate-300'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 shrink-0 rounded-full transition-colors ${
                    isSelected ? 'bg-violet-400' : 'bg-slate-600'
                  }`}
                />
                <span className="leading-tight">{topic}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Custom topic input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addCustom()}
          placeholder="Add a custom topic…"
          className={inputCls}
        />
        <button
          onClick={addCustom}
          disabled={!customInput.trim()}
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-600/60 bg-slate-700/50 px-3 py-2 text-sm font-medium text-slate-200 transition-colors hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-40"
        >
          <Plus className="h-4 w-4" />
          Add
        </button>
      </div>

      {error && (
        <p className="flex items-center gap-2 text-sm text-red-400">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
        </p>
      )}

      <div className="flex justify-end pt-1">
        <button
          onClick={handleContinue}
          disabled={selected.size === 0 || saving}
          className="flex items-center gap-2 rounded-lg bg-violet-700 px-5 py-2.5 text-sm font-semibold text-white shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-[background,box-shadow,opacity] hover:bg-violet-600 hover:shadow-[0_0_24px_rgba(124,58,237,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-40 active:scale-[0.98]"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Continue
        </button>
      </div>
    </div>
  )
}

// ─── Step 4: Ready ─────────────────────────────────────────────────────────────

function StepReady({ summary, onLaunch }) {
  const [animating, setAnimating] = useState(false)

  useEffect(() => {
    // Small delay before checkmark animation
    const t = setTimeout(() => setAnimating(true), 100)
    return () => clearTimeout(t)
  }, [])

  return (
    <div className="flex flex-col items-center gap-6 py-2">
      {/* Animated checkmark */}
      <div
        className={`flex h-16 w-16 items-center justify-center rounded-full border-2 border-emerald-500/60 bg-emerald-500/10 transition-[opacity,transform] duration-500 ${
          animating ? 'opacity-100 scale-100' : 'opacity-0 scale-75'
        }`}
      >
        <CheckCircle2 className="h-8 w-8 text-emerald-400" />
      </div>

      <div className="text-center">
        <h3 className="text-base font-semibold text-slate-100">You're all set!</h3>
        <p className="mt-1 text-sm text-slate-500">BlogPilot is configured and ready to run.</p>
      </div>

      {/* Summary list */}
      <div className="w-full rounded-xl border border-slate-700/60 bg-slate-800/40 p-4">
        <ul className="flex flex-col gap-2.5">
          <SummaryRow
            label="Groq AI"
            value={summary.groqConnected ? 'Connected' : 'Not configured'}
            ok={summary.groqConnected}
          />
          <SummaryRow
            label="LinkedIn"
            value={
              summary.linkedInConnected
                ? 'Connected'
                : summary.linkedInSkipped
                ? 'Skipped'
                : 'Not configured'
            }
            ok={summary.linkedInConnected}
            neutral={summary.linkedInSkipped}
          />
          <SummaryRow
            label="Topics"
            value={`${summary.topicCount} selected`}
            ok={summary.topicCount > 0}
          />
        </ul>
      </div>

      <button
        onClick={onLaunch}
        className="flex w-full items-center justify-center gap-2.5 rounded-xl bg-emerald-700 px-6 py-3.5 text-base font-semibold text-white shadow-[0_0_24px_rgba(16,185,129,0.2)] transition-[background,box-shadow] hover:bg-emerald-600 hover:shadow-[0_0_32px_rgba(16,185,129,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 active:scale-[0.99]"
      >
        <Rocket className="h-5 w-5" />
        Launch Dashboard
      </button>
    </div>
  )
}

function SummaryRow({ label, value, ok, neutral }) {
  return (
    <li className="flex items-center justify-between gap-4">
      <span className="text-sm text-slate-400">{label}</span>
      <div className="flex items-center gap-1.5">
        {ok ? (
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
        ) : neutral ? (
          <span className="h-3.5 w-3.5 flex items-center justify-center">
            <span className="h-2 w-2 rounded-full bg-slate-500" />
          </span>
        ) : (
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
        )}
        <span
          className={`text-sm font-medium ${
            ok ? 'text-emerald-300' : neutral ? 'text-slate-400' : 'text-amber-300'
          }`}
        >
          {value}
        </span>
      </div>
    </li>
  )
}

// ─── Step Indicator ────────────────────────────────────────────────────────────

function StepDots({ current, total }) {
  return (
    <div className="flex items-center justify-center gap-2">
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className={`block rounded-full transition-all duration-300 ${
            i === current
              ? 'h-2 w-6 bg-violet-500'
              : i < current
              ? 'h-2 w-2 bg-violet-700'
              : 'h-2 w-2 bg-slate-700'
          }`}
        />
      ))}
    </div>
  )
}

// ─── Step Header Meta ──────────────────────────────────────────────────────────

const STEPS = [
  { icon: Key, title: 'Groq API Key', subtitle: 'Connect your AI provider' },
  { icon: Linkedin, title: 'LinkedIn Account', subtitle: 'Authenticate your LinkedIn session' },
  { icon: Tags, title: 'Target Topics', subtitle: 'Tell the AI what content to engage with' },
  { icon: Rocket, title: 'Ready to Launch', subtitle: 'Your setup is complete' },
]

// ─── Main Wizard ───────────────────────────────────────────────────────────────

export default function FirstRunWizard({ onComplete }) {
  const [step, setStep] = useState(0)
  const [summary, setSummary] = useState({
    groqConnected: false,
    linkedInConnected: false,
    linkedInSkipped: false,
    topicCount: 0,
  })

  // Fade state for step transitions
  const [visible, setVisible] = useState(true)
  const transitionTimerRef = useRef(null)

  useEffect(() => {
    return () => clearTimeout(transitionTimerRef.current)
  }, [])

  const transition = (nextStep, summaryUpdate = {}) => {
    setVisible(false)
    clearTimeout(transitionTimerRef.current)
    transitionTimerRef.current = setTimeout(() => {
      setSummary((s) => ({ ...s, ...summaryUpdate }))
      setStep(nextStep)
      setVisible(true)
    }, 180)
  }

  const { icon: StepIcon, title, subtitle } = STEPS[step]

  return (
    // Full-screen overlay
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/90 p-4 backdrop-blur-sm">
      {/* Wizard card */}
      <div className="w-full max-w-lg rounded-2xl border border-slate-700/60 bg-[#161b27] shadow-[0_24px_64px_rgba(0,0,0,0.6)]">
        {/* Header */}
        <div className="border-b border-slate-700/60 px-6 pt-6 pb-5">
          <div className="mb-4">
            <StepDots current={step} total={STEPS.length} />
          </div>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-700/60 bg-slate-800/60">
              <StepIcon className="h-4.5 w-4.5 text-violet-400" style={{ width: 18, height: 18 }} />
            </div>
            <div>
              <h2 className="text-base font-semibold leading-tight text-slate-100">{title}</h2>
              <p className="text-xs text-slate-500">{subtitle}</p>
            </div>
          </div>
        </div>

        {/* Body */}
        <div
          className="px-6 py-5 transition-opacity duration-180"
          style={{ opacity: visible ? 1 : 0 }}
        >
          {step === 0 && (
            <StepGroq
              onComplete={(data) => transition(1, { groqConnected: data.groqConnected })}
            />
          )}
          {step === 1 && (
            <StepLinkedIn
              onComplete={(data) => transition(2, { linkedInConnected: data.linkedInConnected })}
              onSkip={() => transition(2, { linkedInSkipped: true })}
            />
          )}
          {step === 2 && (
            <StepTopics
              onComplete={(data) => transition(3, { topicCount: data.topics.length })}
            />
          )}
          {step === 3 && (
            <StepReady
              summary={summary}
              onLaunch={() => {
                localStorage.setItem('firstRunComplete', 'true')
                onComplete()
              }}
            />
          )}
        </div>

        {/* Footer note */}
        {step < 3 && (
          <div className="border-t border-slate-700/40 px-6 py-3">
            <p className="text-center text-xs text-slate-600">
              Step {step + 1} of {STEPS.length} — you can change these settings later in Settings
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
