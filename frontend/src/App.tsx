import { useEffect, useRef, useState } from 'react'
import type { SyntheticEvent } from 'react'
import { listCompetencies, searchProviders } from './api'
import type { SearchFilter, SearchResponse } from './api'
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

function isEmptyFilter(f: SearchFilter) {
  return !f.provider_type && f.required_competencies.length === 0 && !f.location
}

export default function App() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const [labels, setLabels] = useState<Record<string, string>>({})
  const inFlight = useRef<AbortController | null>(null)

  useEffect(() => {
    listCompetencies()
      .then((list) => setLabels(Object.fromEntries(list.map((c) => [c.code, c.label]))))
      .catch(() => {}) // Labels are a nicety; fall back to raw codes.
  }, [])

  async function runSearch(text: string) {
    const trimmed = text.trim()
    if (!trimmed) return

    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller

    setStatus({ kind: 'loading' })
    try {
      const data = await searchProviders(trimmed, controller.signal)
      setStatus({ kind: 'done', data })
    } catch (error) {
      if (controller.signal.aborted) return
      setStatus({ kind: 'error', message: (error as Error).message })
    }
  }

  function handleSubmit(event: SyntheticEvent) {
    event.preventDefault()
    runSearch(query)
  }

  function runExample(example: string) {
    setQuery(example)
    runSearch(example)
  }

  return (
    <div className="page">
      <header className="site-header">
        <p className="logo">Vouch</p>
        <h1>Find a carer or driver who knows how to help</h1>
        <p className="lede">Describe what you need in your own words.</p>
      </header>

      <main>
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

          {status.kind === 'done' && <Results data={status.data} labels={labels} />}
        </section>
      </main>
    </div>
  )
}

function Results({ data, labels }: { data: SearchResponse; labels: Record<string, string> }) {
  const { filter, filter_parsed, results } = data
  const highlighted = new Set(filter.required_competencies)
  const understood = !isEmptyFilter(filter)

  return (
    <>
      {understood ? (
        <div className="understood">
          <p>Looking for:</p>
          <ul className="tags">
            {filter.provider_type && <li className="tag tag-filter">{filter.provider_type === 'carer' ? 'Carer' : 'Driver'}</li>}
            {filter.required_competencies.map((code) => (
              <li key={code} className="tag tag-filter">
                {labels[code] ?? code}
              </li>
            ))}
            {filter.location && <li className="tag tag-filter">In {filter.location}</li>}
          </ul>
        </div>
      ) : (
        <div className="notice">
          {filter_parsed
            ? "We couldn't pick out specific needs from that, so here's everyone. Try mentioning a skill, like hoist transfers or BSL, or a city."
            : "Our search assistant isn't available right now, so here's everyone. You can still browse the list."}
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
            {results.length} {results.length === 1 ? 'provider' : 'providers'} found
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
              <ProviderCard key={provider.id} provider={provider} highlighted={highlighted} />
            ))}
          </div>
        </>
      )}
    </>
  )
}
