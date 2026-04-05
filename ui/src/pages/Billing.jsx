import { CheckCircle2, Zap, Shield, Infinity } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

const FEATURES = [
  'Unlimited LinkedIn post scanning',
  'AI-powered comment generation',
  'Lead capture & email enrichment',
  'Campaign automation engine',
  'Analytics & learning insights',
  'Content Studio with structured generation',
  'Full API access',
]

export default function Billing() {
  const { user } = useAuth()

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Billing & Plan</h1>
        <p className="mt-0.5 text-sm text-slate-500">Your current access and plan details.</p>
      </div>

      {/* Beta banner */}
      <div className="rounded-xl border border-violet-500/30 bg-violet-500/10 p-5">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-violet-500/20">
            <Zap className="h-5 w-5 text-violet-400" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-violet-200">Free Beta Access</h2>
            <p className="mt-1 text-sm text-violet-300/80">
              BlogPilot is currently in free beta. You have full access to all features at no cost.
              No credit card required, no limits, no expiry during this phase.
            </p>
          </div>
        </div>
      </div>

      {/* Plan card */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Current Plan</p>
            <div className="mt-2 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <span className="rounded-md border border-emerald-500/20 bg-emerald-500/15 px-2.5 py-1 text-xs font-medium text-emerald-400">
                Beta — Free
              </span>
            </div>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-slate-100">$0</p>
            <p className="text-xs text-slate-500">/ month</p>
          </div>
        </div>

        <div className="mt-5 border-t border-slate-700/50 pt-5">
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">Included</p>
          <ul className="space-y-2">
            {FEATURES.map((f) => (
              <li key={f} className="flex items-center gap-2 text-sm text-slate-400">
                <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-emerald-500" />
                {f}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Account details */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-300">Account</h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-500">Email</span>
            <span className="text-slate-300">{user?.email}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Role</span>
            <span className="capitalize text-slate-300">{user?.role || 'user'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Status</span>
            <span className="flex items-center gap-1.5 text-emerald-400">
              <Infinity className="h-3.5 w-3.5" />
              Unlimited access
            </span>
          </div>
        </div>
      </div>

      {/* Info note */}
      <div className="flex items-start gap-3 rounded-lg border border-slate-700/40 bg-slate-800/30 px-4 py-3">
        <Shield className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-500" />
        <p className="text-xs text-slate-500">
          Paid plans will be introduced after the beta period. Existing beta users will receive advance notice
          and a preferential rate before any charges are applied.
        </p>
      </div>
    </div>
  )
}
