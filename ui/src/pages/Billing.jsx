import { useState, useEffect } from 'react'
import { billing } from '../api/platform'
import { useAuth } from '../contexts/AuthContext'
import { CreditCard, ExternalLink, Loader2, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'

const STATUS_DISPLAY = {
  active: { label: 'Active', color: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/20', icon: CheckCircle2 },
  pending: { label: 'Pending', color: 'text-amber-400 bg-amber-500/15 border-amber-500/20', icon: AlertTriangle },
  cancelled: { label: 'Cancelled', color: 'text-red-400 bg-red-500/15 border-red-500/20', icon: XCircle },
  past_due: { label: 'Past Due', color: 'text-red-400 bg-red-500/15 border-red-500/20', icon: AlertTriangle },
  suspended: { label: 'Suspended', color: 'text-red-400 bg-red-500/15 border-red-500/20', icon: XCircle },
}

export default function Billing() {
  const { user } = useAuth()
  const [sub, setSub] = useState(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    billing.subscription()
      .then(res => setSub(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleCheckout = async () => {
    setActionLoading(true)
    try {
      const res = await billing.createCheckout()
      window.location.href = res.data.checkout_url
    } catch (e) {
      setMessage(e.response?.data?.detail || 'Checkout failed')
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!confirm('Cancel your subscription? You will retain access until the end of the current billing period.')) return
    setActionLoading(true)
    try {
      await billing.cancel()
      setMessage('Subscription will cancel at end of billing period.')
      const res = await billing.subscription()
      setSub(res.data)
    } catch (e) {
      setMessage(e.response?.data?.detail || 'Cancellation failed')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-violet-400" />
      </div>
    )
  }

  const status = sub?.status || 'pending'
  const display = STATUS_DISPLAY[status] || STATUS_DISPLAY.pending
  const StatusIcon = display.icon

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Billing & Subscription</h1>
        <p className="mt-0.5 text-sm text-slate-500">Manage your plan and payment</p>
      </div>

      {message && (
        <div className="rounded-lg border border-violet-500/30 bg-violet-500/10 px-4 py-2 text-sm text-violet-300">
          {message}
        </div>
      )}

      {/* Current plan */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-300">Current Plan</h2>
            <div className="mt-3 flex items-center gap-2">
              <StatusIcon className={`h-4 w-4 ${display.color.split(' ')[0]}`} />
              <span className={`rounded-md border px-2.5 py-1 text-xs font-medium ${display.color}`}>
                {display.label}
              </span>
            </div>
            {sub?.current_period_end && (
              <p className="mt-2 text-xs text-slate-500">
                {sub.cancel_at_period_end ? 'Access until' : 'Renews'}: {new Date(sub.current_period_end * 1000).toLocaleDateString()}
              </p>
            )}
          </div>
          <CreditCard className="h-8 w-8 text-slate-700" />
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        {(status === 'pending' || status === 'cancelled') && (
          <button
            onClick={handleCheckout}
            disabled={actionLoading}
            className="flex items-center gap-2 rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-violet-500 transition disabled:opacity-50"
          >
            {actionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ExternalLink className="h-4 w-4" />}
            {status === 'pending' ? 'Subscribe Now' : 'Resubscribe'}
          </button>
        )}

        {status === 'active' && !sub?.cancel_at_period_end && (
          <button
            onClick={handleCancel}
            disabled={actionLoading}
            className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-5 py-2.5 text-sm font-medium text-red-300 hover:bg-red-500/20 transition disabled:opacity-50"
          >
            Cancel Subscription
          </button>
        )}
      </div>

      {/* Account info */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-300">Account</h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-500">Email</span>
            <span className="text-slate-300">{user?.email}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Plan</span>
            <span className="text-slate-300">BlogPilot Pro</span>
          </div>
        </div>
      </div>
    </div>
  )
}
