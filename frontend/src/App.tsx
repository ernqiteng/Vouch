import { useEffect, useRef, useState } from 'react'
import type { SyntheticEvent } from 'react'
import { AuthError, getMe, getToken, listCompetencies, logOut, searchProviders } from './api'
import type { Booking, Competency, Me, Provider, SearchFilter, SearchResponse } from './api'
import AuthForm from './AuthForm'
import BookingConfirmation from './BookingConfirmation'
import BookingForm from './BookingForm'
import MyBookings from './MyBookings'
import ProfileForm from './ProfileForm'
import ProviderCard from './ProviderCard'
import './App.css'

const EXAMPLES = [
  'I need a carer confident with hoist transfers who can communicate in BSL',
  'A driver in Leeds who can take me while I stay in my wheelchair',
  'Someone to help my dad, who has dementia, in Edinburgh',
]

type Status =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; data: SearchResponse }

type View = 'search' | 'login' | 'signup' | 'profile' | 'book' | 'booking' | 'bookings'

interface SearchSettings {
  useProfile: boolean
  skipped: string[]
}

function isEmptyFilter(f: SearchFilter) {
  return !f.provider_type && f.required_competencies.length === 0 && !f.location
}

export default function App() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const [competencies, setCompetencies] = useState<Competency[]>([])
  const [me, setMe] = useState<Me | null>(null)
  const [view, setView] = useState<View>('search')
  const [settings, setSettings] = useState<SearchSettings>({ useProfile: true, skipped: [] })
  const [notice, setNotice] = useState<string | null>(null)
  const [bookingProvider, setBookingProvider] = useState<Provider | null>(null)
  const [booking, setBooking] = useState<{ data: Booking; justBooked: boolean } | null>(null)
  const [afterLogin, setAfterLogin] = useState<View | null>(null)
  const inFlight = useRef<AbortController | null>(null)
  const labels = Object.fromEntries(competencies.map((c) => [c.code, c.label]))

  useEffect(() => {
    listCompetencies()
      .then(setCompetencies)
      .catch(() => {}) // Labels are a nicety; fall back to raw codes.
    if (getToken()) {
      getMe()
        .then(setMe)
        .catch(() => logOut()) // Expired or invalid token: start logged out.
    }
  }, [])

  async function refreshMe() {
    try {
      setMe(await getMe())
    } catch {
      logOut()
      setMe(null)
    }
  }

  function signOut(message: string | null = null) {
    logOut()
    setMe(null)
    setNotice(message)
    setView('search')
  }

  /** Session expired while doing something that needs login: log in, then carry on. */
  function sessionExpired(returnTo: View) {
    logOut()
    setMe(null)
    setNotice('Your session expired. Please log in again to carry on.')
    setAfterLogin(returnTo)
    setView('login')
  }

  function startBooking(provider: Provider) {
    setBookingProvider(provider)
    if (me) {
      setView('book')
    } else {
      setNotice(`Log in or create an account to book ${provider.name}.`)
      setAfterLogin('book')
      setView('login')
    }
  }

  async function runSearch(text: string, next: SearchSettings = settings) {
    const trimmed = text.trim()
    if (!trimmed) return

    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setSettings(next)
    setStatus({ kind: 'loading' })
    try {
      const data = await searchProviders(trimmed, {
        useProfile: next.useProfile,
        skipProfileCompetencies: next.skipped,
        signal: controller.signal,
      })
      setStatus({ kind: 'done', data })
    } catch (error) {
      if (controller.signal.aborted) return
      if (error instanceof AuthError) {
        // Session expired mid-search: log out and search again without the profile.
        signOut('Your session expired, so this search ran without your saved needs. Log in again to use them.')
        return runSearch(trimmed, { useProfile: true, skipped: [] })
      }
      setStatus({ kind: 'error', message: (error as Error).message })
    }
  }

  function handleSubmit(event: SyntheticEvent) {
    event.preventDefault()
    runSearch(query, { ...settings, skipped: [] }) // a new search starts with the full profile
  }

  function runExample(example: string) {
    setQuery(example)
    runSearch(example, { ...settings, skipped: [] })
  }

  const lastQuery = status.kind === 'done' ? status.data.query : null
  function rerun(next: SearchSettings) {
    if (lastQuery) runSearch(lastQuery, next)
    else setSettings(next)
  }

  return (
    <div className="page">
      <header className="site-header">
        <div className="topbar">
          <p className="logo">Vouch</p>
          <nav className="account" aria-label="Account">
            {me ? (
              <>
                <span className="signed-in">{me.user.email}</span>
                <button type="button" className="secondary small" onClick={() => setView('bookings')}>
                  Your bookings
                </button>
                <button type="button" className="secondary small" onClick={() => setView('profile')}>
                  Your needs
                </button>
                <button type="button" className="link" onClick={() => signOut()}>
                  Log out
                </button>
              </>
            ) : (
              <>
                <button type="button" className="secondary small" onClick={() => setView('login')}>
                  Log in
                </button>
                <button type="button" className="small" onClick={() => setView('signup')}>
                  Sign up
                </button>
              </>
            )}
          </nav>
        </div>
        {view === 'search' && (
          <>
            <h1>Find a carer or driver who knows how to help</h1>
            <p className="lede">Describe what you need in your own words.</p>
          </>
        )}
      </header>

      {notice && (
        <div className="notice notice-dismiss" role="status">
          <span>{notice}</span>
          <button type="button" className="link" onClick={() => setNotice(null)}>
            Dismiss
          </button>
        </div>
      )}

      <main>
        {(view === 'login' || view === 'signup') && (
          <AuthForm
            mode={view}
            onSwitch={setView}
            onCancel={() => {
              setAfterLogin(null)
              setView('search')
            }}
            onDone={async () => {
              await refreshMe()
              setNotice(null)
              setView(afterLogin ?? 'search')
              setAfterLogin(null)
            }}
          />
        )}

        {view === 'book' && me && bookingProvider && (
          <BookingForm
            provider={bookingProvider}
            onBooked={(data) => {
              setBooking({ data, justBooked: true })
              setView('booking')
            }}
            onCancel={() => setView('search')}
            onAuthError={() => sessionExpired('book')}
          />
        )}

        {view === 'booking' && booking && (
          <BookingConfirmation
            booking={booking.data}
            justBooked={booking.justBooked}
            onBack={() => setView('search')}
            onAllBookings={() => setView('bookings')}
          />
        )}

        {view === 'bookings' && me && (
          <MyBookings
            onOpen={(data) => {
              setBooking({ data, justBooked: false })
              setView('booking')
            }}
            onBack={() => setView('search')}
            onAuthError={() => sessionExpired('bookings')}
          />
        )}

        {view === 'profile' && me && (
          <ProfileForm
            me={me}
            competencies={competencies}
            onSaved={(profile) => setMe((m) => m && { ...m, profile })}
            onClose={() => {
              setView('search')
              rerun({ useProfile: true, skipped: [] })
            }}
          />
        )}

        {view === 'search' && (
          <>
            <form className="search" onSubmit={handleSubmit} role="search">
              <label htmlFor="query" className="search-label">
                What do you need?
              </label>
              <div className="search-row">
                <textarea
                  id="query"
                  rows={2}
                  value={query}
                  maxLength={500}
                  placeholder="e.g. I need a carer who can use a hoist and speaks BSL"
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) handleSubmit(e)
                  }}
                />
                <button type="submit" disabled={status.kind === 'loading' || !query.trim()}>
                  {status.kind === 'loading' ? 'Searching…' : 'Search'}
                </button>
              </div>

              {me?.profile && (
                <label className="check profile-toggle">
                  <input
                    type="checkbox"
                    checked={settings.useProfile}
                    onChange={(e) => rerun({ useProfile: e.target.checked, skipped: [] })}
                  />
                  Use my saved accessibility needs
                </label>
              )}
              {me && !me.profile && (
                <p className="hint">
                  <button type="button" className="link" onClick={() => setView('profile')}>
                    Save your accessibility needs
                  </button>{' '}
                  so every search uses them automatically.
                </p>
              )}
            </form>

            <section className="results" aria-live="polite" aria-busy={status.kind === 'loading'}>
              {status.kind === 'idle' && (
                <div className="examples">
                  <p>Try an example:</p>
                  <ul>
                    {EXAMPLES.map((example) => (
                      <li key={example}>
                        <button type="button" className="example" onClick={() => runExample(example)}>
                          {example}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {status.kind === 'loading' && (
                <div className="state state-loading">
                  <span className="spinner" aria-hidden="true" />
                  <p>Finding providers who match…</p>
                </div>
              )}

              {status.kind === 'error' && (
                <div className="state state-error" role="alert">
                  <p className="state-title">Search didn't work</p>
                  <p>{status.message}</p>
                  <button type="button" onClick={() => runSearch(query)}>
                    Try again
                  </button>
                </div>
              )}

              {status.kind === 'done' && (
                <Results
                  data={status.data}
                  labels={labels}
                  skipped={settings.skipped}
                  onSkip={(code) => rerun({ ...settings, skipped: [...settings.skipped, code] })}
                  onRestore={(code) =>
                    rerun({ ...settings, skipped: settings.skipped.filter((c) => c !== code) })
                  }
                  onBook={startBooking}
                />
              )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}

interface ResultsProps {
  data: SearchResponse
  labels: Record<string, string>
  skipped: string[]
  onSkip: (code: string) => void
  onRestore: (code: string) => void
  onBook: (provider: Provider) => void
}

function Results({ data, labels, skipped, onSkip, onRestore, onBook }: ResultsProps) {
  const { query_filter, filter, filter_parsed, profile_applied, added_from_profile, ranked_from, results } =
    data
  const highlighted = new Set(filter.required_competencies)
  const label = (code: string) => labels[code] ?? code

  return (
    <>
      {isEmptyFilter(query_filter) && (
        <div className="notice">
          {filter_parsed
            ? "We couldn't pick out specific needs from your words. Try mentioning a skill, like hoist transfers or BSL, or a city."
            : "Our search assistant isn't available right now, so your words weren't used for this search."}
        </div>
      )}

      {!isEmptyFilter(query_filter) && (
        <div className="understood">
          <p>From your search:</p>
          <ul className="tags">
            {query_filter.provider_type && (
              <li className="tag tag-filter">{query_filter.provider_type === 'carer' ? 'Carer' : 'Driver'}</li>
            )}
            {query_filter.required_competencies.map((code) => (
              <li key={code} className="tag tag-filter">
                {label(code)}
              </li>
            ))}
            {query_filter.location && <li className="tag tag-filter">In {query_filter.location}</li>}
          </ul>
        </div>
      )}

      {profile_applied && (added_from_profile.length > 0 || skipped.length > 0) && (
        <div className="understood">
          <p>Ranked by your saved needs:</p>
          <ul className="tags">
            {added_from_profile.map((code) => (
              <li key={code} className="tag tag-profile">
                {label(code)}
                <button
                  type="button"
                  className="tag-remove"
                  aria-label={`Don't rank by ${label(code)} for this search`}
                  onClick={() => onSkip(code)}
                >
                  ×
                </button>
              </li>
            ))}
            {skipped.map((code) => (
              <li key={code} className="tag tag-skipped">
                <s>{label(code)}</s>
                <button type="button" className="link" onClick={() => onRestore(code)}>
                  Put back
                  <span className="visually-hidden"> {label(code)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {results.length === 0 ? (
        <div className="state state-empty">
          <p className="state-title">No one matches all of that yet</p>
          <p>Try leaving out one requirement or the location.</p>
        </div>
      ) : (
        <>
          <p className="count">
            {results.length} {results.length === 1 ? 'provider' : 'providers'} found, best matches first
            {ranked_from && ` (distance measured from ${ranked_from})`}
          </p>
          <div className="legend">
            <span>
              <span className="tag tag-verified">Skill</span>backed by a document
            </span>
            <span>
              <span className="tag">Skill</span>self-reported
            </span>
            {highlighted.size > 0 && (
              <span>
                <span className="tag tag-match">Skill</span>matches your search
              </span>
            )}
          </div>
          <div className="cards">
            {results.map((provider) => (
              <ProviderCard
                key={provider.id}
                provider={provider}
                highlighted={highlighted}
                rankedFrom={ranked_from}
                onBook={() => onBook(provider)}
              />
            ))}
          </div>
        </>
      )}
    </>
  )
}
