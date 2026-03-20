import { useState, useEffect } from 'react'
import { Save, Loader2, CheckCircle2, RotateCcw } from 'lucide-react'
import { config as configApi } from '../api/client'
import PromptTestPanel from '../components/PromptTestPanel'

const PROMPT_NAMES = ['relevance', 'comment', 'post', 'note', 'reply']

const PROMPT_DEFAULTS = {
  relevance: `You are a LinkedIn relevance scoring assistant.\n\nScore how relevant a post is to: {topics}\n\nPost author: {author_name}\nPost content:\n{post_text}\n\nRespond with ONLY JSON: {"score": <0-10>, "reason": "<one sentence>"}`,
  comment: `You are a professional LinkedIn commenter.\n\nWrite ONE genuine comment for this post.\nNEVER start with "Great post!" or generic openers.\nTone: {tone}\nTopics: {topics}\n\nAuthor: {author_name}\nPost: {post_text}\n\nWrite ONLY the comment text.`,
  post: `You are a LinkedIn content strategist.\n\nWrite ONE original post on: {topic}\nStyle: {style}\nTone: {tone}\nLength: ~{word_count} words\n\nWrite ONLY the post text.`,
  note: `Write a personalised LinkedIn connection note.\n\nPerson: {first_name}, {title} at {company}\nContext: {shared_context}\nYour expertise: {topics}\n\nMax 300 characters. Write ONLY the note.`,
  reply: `Continue this LinkedIn comment thread.\n\nOriginal post: {original_post}\nYour comment: {your_comment}\n{replier_name} replied: {reply_to_comment}\n\nWrite ONE natural reply. 1-3 sentences.`,
}

function extractVars(text) {
  return [...new Set((text.match(/\{(\w+)\}/g) || []).map((m) => m.slice(1, -1)))]
}

export default function PromptEditor() {
  const [selected, setSelected] = useState('relevance')
  const [prompts, setPrompts] = useState(PROMPT_DEFAULTS)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [resetting, setResetting] = useState(false)

  useEffect(() => {
    configApi.getPrompts().then((res) => {
      if (res.data && typeof res.data === 'object') {
        setPrompts((prev) => ({ ...prev, ...res.data }))
      }
    }).catch(() => {})
  }, [])

  const currentText = prompts[selected] || ''
  const vars = extractVars(currentText)

  const handleSave = async () => {
    setSaving(true)
    setSaveError('')
    try {
      await configApi.updatePrompt(selected, currentText)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      setSaveError(e?.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    setResetting(true)
    try {
      const res = await configApi.resetPrompt(selected)
      if (res.data?.text) {
        setPrompts((prev) => ({ ...prev, [selected]: res.data.text }))
      }
    } catch {
      setPrompts((prev) => ({ ...prev, [selected]: PROMPT_DEFAULTS[selected] }))
    } finally {
      setResetting(false)
    }
  }

  return (
    <div className="flex h-full flex-col gap-0 p-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight text-slate-100">Prompt Editor</h1>
        <p className="mt-0.5 text-sm text-slate-500">Edit the AI prompts used for scoring, comments, posts, and outreach.</p>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Sidebar */}
        <div className="flex flex-row gap-1 lg:flex-col lg:w-44 lg:shrink-0">
          {PROMPT_NAMES.map((name) => (
            <button
              key={name}
              onClick={() => setSelected(name)}
              className={`rounded-lg px-3 py-2 text-left text-sm font-medium capitalize transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                selected === name
                  ? 'bg-violet-700/20 text-violet-300'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              {name}
            </button>
          ))}
        </div>

        {/* Editor */}
        <div className="flex flex-1 flex-col gap-4 min-w-0">
          <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold capitalize text-slate-200">{selected}</h2>
                {vars.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {vars.map((v) => (
                      <span
                        key={v}
                        className="rounded-md border border-blue-600/30 bg-blue-700/15 px-2 py-0.5 text-xs text-blue-300"
                      >
                        {'{' + v + '}'}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {saveError && <p className="text-xs text-red-400">{saveError}</p>}
                {saved && !saveError && <p className="text-xs text-emerald-400">Saved ✓</p>}
                <button
                  onClick={handleReset}
                  disabled={resetting}
                  className="flex items-center gap-1.5 rounded-lg border border-slate-700/60 px-2.5 py-1.5 text-xs text-slate-400 transition-colors hover:text-slate-200 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Reset
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-1.5 rounded-lg bg-violet-700 px-3 py-1.5 text-xs font-medium text-white transition-[background] hover:bg-violet-600 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                >
                  {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : saved ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" /> : <Save className="h-3.5 w-3.5" />}
                  {saved ? 'Saved' : 'Save'}
                </button>
              </div>
            </div>

            <textarea
              value={currentText}
              onChange={(e) => setPrompts((prev) => ({ ...prev, [selected]: e.target.value }))}
              rows={14}
              spellCheck={false}
              className="w-full resize-y rounded-lg border border-slate-700/60 bg-slate-900/60 p-3 font-mono text-sm leading-relaxed text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
            />
            <div className="mt-1.5 flex justify-end">
              <span className="text-xs tabular-nums text-slate-500">{currentText.length} chars</span>
            </div>
          </div>

          {/* Test panel */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-5">
            <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Test Prompt</h2>
            <PromptTestPanel promptName={selected} promptText={currentText} />
          </div>
        </div>
      </div>
    </div>
  )
}
