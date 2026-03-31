import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { auth as authApi } from '../api/platform'
import { LogIn, Loader2, ArrowLeft } from 'lucide-react'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const [showForgot, setShowForgot] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleForgotPassword = async (e) => {
    e.preventDefault()
    if (!email) { setError('Enter your email first'); return }
    setLoading(true); setError('')
    try {
      await authApi.forgotPassword(email)
      setSuccess('If that email exists, a reset link has been sent.')
      setShowForgot(false)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send reset email')
    } finally { setLoading(false) }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-slate-100">BlogPilot</h1>
          <p className="mt-1 text-sm text-slate-500">Sign in to your account</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-400">
              {error}
            </div>
          )}
          {success && (
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-400">
              {success}
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
              placeholder="••••••••"
            />
          </div>

          {showForgot ? (
            <>
              <button
                type="button"
                onClick={handleForgotPassword}
                disabled={loading}
                className="flex items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-violet-500 disabled:opacity-50"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Send Reset Link
              </button>
              <button type="button" onClick={() => setShowForgot(false)} className="flex items-center justify-center gap-1 text-sm text-slate-500 hover:text-slate-300">
                <ArrowLeft className="h-3.5 w-3.5" /> Back to login
              </button>
            </>
          ) : (
            <>
              <button
                type="submit"
                disabled={loading}
                className="flex items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-violet-500 disabled:opacity-50"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
                Sign In
              </button>
              <button type="button" onClick={() => { setShowForgot(true); setError('') }} className="text-sm text-slate-500 hover:text-violet-400 transition">
                Forgot password?
              </button>
            </>
          )}
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Don't have an account?{' '}
          <Link to="/signup" className="text-violet-400 hover:text-violet-300">Sign up</Link>
        </p>
      </div>
    </div>
  )
}
