import { useState, type FormEvent } from 'react'
import { Eye, EyeOff, LockKeyhole } from 'lucide-react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

export default function AdminLogin() {
  const { isAuthenticated, isLoading, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  if (isLoading) {
    return <main className="flex min-h-screen items-center justify-center bg-[#faf8f3] text-sm text-[#766f67]">Checking your session…</main>
  }
  if (isAuthenticated) return <Navigate to="/admin" replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      await login(email.trim(), password)
      const destination = (location.state as { from?: string } | null)?.from ?? '/admin'
      navigate(destination, { replace: true })
    } catch {
      setError('We couldn’t sign you in with those details. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#faf8f3] px-5 py-12 sm:px-8">
      <div aria-hidden="true" className="pointer-events-none absolute -left-28 -top-36 h-96 w-96 rounded-full bg-[#eadfc8]/35 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-48 -right-32 h-[32rem] w-[32rem] rounded-full bg-[#e7d7c4]/30 blur-3xl" />
      <section className="relative w-full max-w-md rounded-[2rem] border border-[#e9e1d4] bg-white/80 p-7 shadow-[0_24px_80px_-48px_rgba(70,55,35,0.35)] backdrop-blur sm:p-10">
        <header className="mb-9 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full border border-[#d5bd91] text-[#9b7b49]">
            <span className="font-serif text-2xl">W</span>
          </div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[#9b7b49]">Wedding Memories</p>
          <h1 className="mt-3 font-serif text-3xl font-normal text-[#332e29]">Administrator sign in</h1>
          <p className="mt-2 text-sm leading-6 text-[#82796f]">A private space for the people behind the celebration.</p>
        </header>

        <form className="space-y-5" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="admin-email" className="mb-2 block text-sm font-medium text-[#4d463e]">Email address</label>
            <input
              id="admin-email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-xl border border-[#e5ddd1] bg-[#fffdfa] px-4 py-3 text-sm text-[#332e29] outline-none transition placeholder:text-[#aaa198] focus:border-[#b89b69] focus:ring-4 focus:ring-[#b89b69]/10"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label htmlFor="admin-password" className="mb-2 block text-sm font-medium text-[#4d463e]">Password</label>
            <div className="relative">
              <input
                id="admin-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-xl border border-[#e5ddd1] bg-[#fffdfa] px-4 py-3 pr-12 text-sm text-[#332e29] outline-none transition placeholder:text-[#aaa198] focus:border-[#b89b69] focus:ring-4 focus:ring-[#b89b69]/10"
                placeholder="Enter your password"
              />
              <button
                type="button"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                onClick={() => setShowPassword((visible) => !visible)}
                className="absolute inset-y-0 right-0 flex items-center px-4 text-[#8c8378] transition hover:text-[#6e5939]"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>
          {error && <p role="alert" className="rounded-xl border border-[#e8c9bd] bg-[#fff7f4] px-4 py-3 text-sm text-[#914e3a]">{error}</p>}
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#9b7b49] px-4 py-3.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#85683c] focus:outline-none focus:ring-4 focus:ring-[#b89b69]/25 disabled:cursor-wait disabled:opacity-70"
          >
            <LockKeyhole size={16} />
            {isSubmitting ? 'Signing in…' : 'Sign in securely'}
          </button>
        </form>

        <p className="mt-7 text-center text-xs leading-5 text-[#a29a90]">Administrator access is private and invitation-free.</p>
      </section>
    </main>
  )
}
