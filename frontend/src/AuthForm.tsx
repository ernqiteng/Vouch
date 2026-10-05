import { useEffect, useRef, useState } from 'react'
import type { SyntheticEvent } from 'react'
import { logIn, signUp } from './api'

interface Props {
  mode: 'login' | 'signup'
  onDone: () => void
  onSwitch: (mode: 'login' | 'signup') => void
  onCancel: () => void
}

export default function AuthForm({ mode, onDone, onSwitch, onCancel }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const signup = mode === 'signup'

  useEffect(() => heading.current?.focus(), [mode])

  function switchMode() {
    setError(null)
    onSwitch(signup ? 'login' : 'signup')
  }

  async function handleSubmit(event: SyntheticEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await (signup ? signUp(email, password) : logIn(email, password))
      onDone()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel" aria-labelledby="auth-heading">
      <h2 id="auth-heading" ref={heading} tabIndex={-1}>
        {signup ? 'Create an account' : 'Log in'}
      </h2>
      <p className="panel-lede">
        {signup
          ? 'Save your accessibility needs once and every search uses them.'
          : 'Welcome back. Your saved needs will apply to your searches.'}
      </p>

      <form onSubmit={handleSubmit} className="stack">
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete={signup ? 'new-password' : 'current-password'}
            required
            minLength={signup ? 8 : undefined}
            aria-describedby={signup ? 'password-hint' : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {signup && (
            <p id="password-hint" className="hint">
              At least 8 characters.
            </p>
          )}
        </div>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <div className="actions">
          <button type="submit" disabled={busy}>
            {busy ? 'Please wait…' : signup ? 'Create account' : 'Log in'}
          </button>
          <button type="button" className="secondary" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>

      <p className="switch">
        {signup ? 'Already have an account? ' : 'New here? '}
        <button type="button" className="link" onClick={switchMode}>
          {signup ? 'Log in' : 'Create an account'}
        </button>
      </p>
    </section>
  )
}
