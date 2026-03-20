import { useState } from 'react'
import { ChevronUp, ChevronDown, Trash2, Plus, Wand2, Eye, Link2, MessageSquare, Mail, ThumbsUp, Timer } from 'lucide-react'
import { config as configApi } from '../api/client'

const STEP_TYPES = ['VISIT_PROFILE', 'FOLLOW', 'CONNECT', 'MESSAGE', 'INMAIL', 'ENDORSE', 'WAIT']
const STEP_LABELS = {
  VISIT_PROFILE: 'Visit Profile', FOLLOW: 'Follow', CONNECT: 'Connect',
  MESSAGE: 'Message', INMAIL: 'InMail', ENDORSE: 'Endorse', WAIT: 'Wait',
}
const STEP_ICONS = {
  VISIT_PROFILE: <Eye size={16} />,
  FOLLOW: <Plus size={16} />,
  CONNECT: <Link2 size={16} />,
  MESSAGE: <MessageSquare size={16} />,
  INMAIL: <Mail size={16} />,
  ENDORSE: <ThumbsUp size={16} />,
  WAIT: <Timer size={16} />,
}
const VARIABLES = ['{first_name}', '{company}', '{title}']
const HAS_MESSAGE = ['MESSAGE', 'INMAIL']
const HAS_DAYS = ['WAIT']

function VariableChips({ onInsert }) {
  return (
    <div className="flex gap-1.5 flex-wrap">
      {VARIABLES.map((v) => (
        <button
          key={v}
          onClick={() => onInsert(v)}
          className="rounded-md border border-blue-600/30 bg-blue-700/15 px-2 py-0.5 text-xs text-blue-300 transition-colors hover:bg-blue-700/25 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500"
        >
          {v}
        </button>
      ))}
    </div>
  )
}

export default function CampaignBuilder({ steps: externalSteps, onChange }) {
  const [steps, setSteps] = useState(externalSteps || [])
  const [addType, setAddType] = useState(STEP_TYPES[0])
  const [generatingIdx, setGeneratingIdx] = useState(null)

  const update = (newSteps) => {
    setSteps(newSteps)
    onChange?.(newSteps)
  }

  const addStep = () => {
    update([...steps, { id: Date.now(), type: addType, message: '', days: 1 }])
  }

  const removeStep = (idx) => update(steps.filter((_, i) => i !== idx))

  const moveUp = (idx) => {
    if (idx === 0) return
    const s = [...steps]
    ;[s[idx - 1], s[idx]] = [s[idx], s[idx - 1]]
    update(s)
  }

  const moveDown = (idx) => {
    if (idx === steps.length - 1) return
    const s = [...steps]
    ;[s[idx], s[idx + 1]] = [s[idx + 1], s[idx]]
    update(s)
  }

  const setField = (idx, field, val) => {
    update(steps.map((s, i) => (i === idx ? { ...s, [field]: val } : s)))
  }

  const insertVar = (idx, variable) => {
    const cur = steps[idx].message || ''
    setField(idx, 'message', cur + variable)
  }

  const aiWrite = async (idx) => {
    setGeneratingIdx(idx)
    try {
      const res = await configApi.testPrompt('note', {
        first_name: '{first_name}', title: '{title}',
        company: '{company}', shared_context: 'post engagement', topics: 'Business Intelligence',
      })
      setField(idx, 'message', res.data.output || '')
    } catch {
      setField(idx, 'message', 'Hi {first_name}, I came across your work at {company} and thought your perspective on analytics would be valuable to discuss.')
    } finally {
      setGeneratingIdx(null)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {steps.length === 0 && (
        <p className="rounded-lg border border-dashed border-slate-700/60 py-6 text-center text-sm text-slate-500">
          No steps yet. Add a step below to build your sequence.
        </p>
      )}

      {steps.map((step, idx) => (
        <div key={step.id} className="rounded-xl border border-slate-700/60 bg-slate-900/50 p-4">
          <div className="flex items-center gap-3">
            <span className="flex items-center text-slate-400">{STEP_ICONS[step.type] || '•'}</span>
            <div className="flex-1">
              <span className="text-sm font-medium text-slate-200">
                Step {idx + 1} — {STEP_LABELS[step.type] || step.type}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => moveUp(idx)}
                disabled={idx === 0}
                className="rounded p-1 text-slate-500 transition-colors hover:text-slate-300 disabled:opacity-30 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500"
              >
                <ChevronUp className="h-4 w-4" />
              </button>
              <button
                onClick={() => moveDown(idx)}
                disabled={idx === steps.length - 1}
                className="rounded p-1 text-slate-500 transition-colors hover:text-slate-300 disabled:opacity-30 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500"
              >
                <ChevronDown className="h-4 w-4" />
              </button>
              <button
                onClick={() => removeStep(idx)}
                className="rounded p-1 text-slate-500 transition-colors hover:text-red-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>

          {HAS_MESSAGE.includes(step.type) && (
            <div className="mt-3 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <label className="text-xs text-slate-400">Message</label>
                <button
                  onClick={() => aiWrite(idx)}
                  disabled={generatingIdx === idx}
                  className="flex items-center gap-1 text-xs text-violet-400 transition-colors hover:text-violet-300 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500"
                >
                  <Wand2 className="h-3 w-3" />
                  {generatingIdx === idx ? 'Writing…' : 'AI Write'}
                </button>
              </div>
              <textarea
                value={step.message}
                onChange={(e) => setField(idx, 'message', e.target.value)}
                rows={3}
                maxLength={300}
                placeholder="Write your message… use variables to personalize."
                className="w-full resize-none rounded-lg border border-slate-700/60 bg-slate-800/60 p-2.5 text-sm text-slate-200 placeholder-slate-600 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              />
              <div className="flex items-center justify-between">
                <VariableChips onInsert={(v) => insertVar(idx, v)} />
                <span className="text-xs tabular-nums text-slate-500">{(step.message || '').length}/300</span>
              </div>
            </div>
          )}

          {HAS_DAYS.includes(step.type) && (
            <div className="mt-3">
              <label className="mb-1.5 block text-xs text-slate-400">Wait (days)</label>
              <input
                type="number"
                min={1}
                max={30}
                value={step.days}
                onChange={(e) => setField(idx, 'days', parseInt(e.target.value) || 1)}
                className="w-24 rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-1.5 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
              />
            </div>
          )}
        </div>
      ))}

      <div className="flex gap-2">
        <select
          value={addType}
          onChange={(e) => setAddType(e.target.value)}
          className="flex-1 rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 focus:border-violet-500/60 focus:outline-none focus:ring-1 focus:ring-violet-500/40"
        >
          {STEP_TYPES.map((t) => <option key={t} value={t}>{STEP_LABELS[t]}</option>)}
        </select>
        <button
          onClick={addStep}
          className="flex items-center gap-1.5 rounded-lg border border-violet-600/40 bg-violet-700/20 px-4 py-2 text-sm text-violet-300 transition-colors hover:bg-violet-700/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 active:scale-[0.98]"
        >
          <Plus className="h-4 w-4" />
          Add Step
        </button>
      </div>
    </div>
  )
}
