import { useEffect, useRef, useState } from 'react'
import { AuthError, listBookings } from './api'
import type { Booking } from './api'
import { formatDayWithYear, formatTimeRange } from './format'

interface Props {
  onOpen: (booking: Booking) => void
  onBack: () => void
  onAuthError: (error: AuthError) => void
}

type State = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; bookings: Booking[] }

export default function MyBookings({ onOpen, onBack, onAuthError }: Props) {
  const [state, setState] = useState<State>({ kind: 'loading' })
  const heading = useRef<HTMLHeadingElement>(null)
  // Kept in a ref so a new callback from the parent doesn't re-run the fetch.
  const authErrorHandler = useRef(onAuthError)
  useEffect(() => {
    authErrorHandler.current = onAuthError
  })

  useEffect(() => heading.current?.focus(), [])

  useEffect(() => {
    let current = true
    listBookings()
      .then((bookings) => current && setState({ kind: 'ready', bookings }))
      .catch((e) => {
        if (!current) return
        if (e instanceof AuthError) authErrorHandler.current(e)
        else setState({ kind: 'error', message: (e as Error).message })
      })
    return () => {
      current = false
    }
  }, [])

  return (
    <section aria-labelledby="bookings-heading">
      <h2 id="bookings-heading" ref={heading} tabIndex={-1}>
        Your bookings
      </h2>

      {state.kind === 'loading' && <p className="hint">Loading your bookings…</p>}
      {state.kind === 'error' && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
      {state.kind === 'ready' && state.bookings.length === 0 && (
        <p className="notice">You haven’t booked anyone yet. Search for a carer or driver and choose “Book”.</p>
      )}
      {state.kind === 'ready' && state.bookings.length > 0 && (
        <ul className="booking-list">
          {state.bookings.map((b) => {
            const snapshot = b.verification_snapshot
            return (
              <li key={b.id} className="card booking-card">
                <h3>{snapshot.provider.name}</h3>
                <p>
                  {formatDayWithYear(b.starts_at)}, {formatTimeRange(b.starts_at, b.ends_at)}
                </p>
                <p className="card-location">
                  {b.pickup}
                  {b.dropoff && ` → ${b.dropoff}`}
                </p>
                <p className="card-evidence">
                  {snapshot.verification?.verified ? '✓ Verified when booked' : 'Not verified when booked'}
                </p>
                <button type="button" className="secondary small" onClick={() => onOpen(b)}>
                  View booking #{b.id}
                </button>
              </li>
            )
          })}
        </ul>
      )}

      <div className="actions">
        <button type="button" className="secondary" onClick={onBack}>
          Back to search
        </button>
      </div>
    </section>
  )
}
