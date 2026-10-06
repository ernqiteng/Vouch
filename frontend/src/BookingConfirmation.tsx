import { useEffect, useRef, useState } from 'react'
import { AuthError, cancelBooking } from './api'
import type { Booking, VerificationSnapshot } from './api'
import { formatDayWithYear, formatStamp, formatTimeRange, percent } from './format'

type SnapshotCompetency = VerificationSnapshot['competencies'][number]

interface Props {
  booking: Booking
  justBooked: boolean
  onBack: () => void
  onAllBookings: () => void
  onCancelled: (booking: Booking) => void
  onAuthError: (error: AuthError) => void
}

export default function BookingConfirmation({
  booking,
  justBooked,
  onBack,
  onAllBookings,
  onCancelled,
  onAuthError,
}: Props) {
  const snapshot = booking.verification_snapshot
  const { provider, verification } = snapshot
  const heading = useRef<HTMLHeadingElement>(null)
  const needed = snapshot.competencies.filter((c) => c.relevant)
  const others = snapshot.competencies.filter((c) => !c.relevant)
  const cancelled = booking.status === 'cancelled'
  // Read the clock once when the screen opens; the server enforces the rule anyway.
  const [openedAt] = useState(() => Date.now())
  const canCancel = !cancelled && new Date(booking.starts_at).getTime() > openedAt
  const [confirming, setConfirming] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [cancelError, setCancelError] = useState<string | null>(null)

  useEffect(() => heading.current?.focus(), [booking.id, cancelled])

  async function handleCancel() {
    setCancelling(true)
    setCancelError(null)
    try {
      onCancelled(await cancelBooking(booking.id))
      setConfirming(false)
    } catch (e) {
      if (e instanceof AuthError) return onAuthError(e)
      setCancelError((e as Error).message)
    } finally {
      setCancelling(false)
    }
  }

  return (
    <article className="confirmation" aria-labelledby="confirmation-heading">
      {cancelled ? (
        <p className="cancelled-banner" role="status">
          This booking was cancelled{booking.cancelled_at && ` on ${formatStamp(booking.cancelled_at)}`}.
        </p>
      ) : (
        justBooked && (
          <p className="confirmed-banner" role="status">
            ✓ Booking confirmed
          </p>
        )
      )}
      <h2 id="confirmation-heading" ref={heading} tabIndex={-1}>
        Your booking with {provider.name}
      </h2>

      <section className="panel panel-wide" aria-labelledby="trip-heading">
        <h3 id="trip-heading">Trip details</h3>
        <dl className="details">
          <dt>Status</dt>
          <dd>{cancelled ? 'Cancelled' : 'Confirmed'}</dd>
          <dt>When</dt>
          <dd>
            {formatDayWithYear(booking.starts_at)}, {formatTimeRange(booking.starts_at, booking.ends_at)}
          </dd>
          <dt>With</dt>
          <dd>
            {provider.name}, {provider.provider_type === 'carer' ? 'carer' : 'driver'}
            {provider.location && ` based in ${provider.location}`}
          </dd>
          <dt>{booking.dropoff || provider.provider_type === 'driver' ? 'Pickup' : 'Address'}</dt>
          <dd>{booking.pickup}</dd>
          {booking.dropoff && (
            <>
              <dt>Drop-off</dt>
              <dd>{booking.dropoff}</dd>
            </>
          )}
          {booking.notes && (
            <>
              <dt>Notes</dt>
              <dd>{booking.notes}</dd>
            </>
          )}
          <dt>Reference</dt>
          <dd>
            #{booking.id}, booked {formatStamp(booking.created_at)}
          </dd>
        </dl>
      </section>

      <section className="panel panel-wide" aria-labelledby="snapshot-heading">
        <h3 id="snapshot-heading">What was verified when you booked</h3>
        <p className="snapshot-note">
          A permanent record captured {formatStamp(snapshot.captured_at)}. It won’t change if {provider.name}’s
          verification changes later, so you can always see what was confirmed for this trip.
        </p>

        {verification ? (
          <div className="snapshot-overall">
            <span className={verification.verified ? 'status-badge status-verified' : 'status-badge status-self'}>
              {verification.verified ? '✓ Verified' : 'Not verified'}
            </span>
            <p>
              {percent(verification.confidence)} of the skills {provider.name} claimed were backed by documents
              (Verified needs {percent(verification.threshold)}). Checked {formatStamp(verification.verified_at)}.
            </p>
          </div>
        ) : (
          <p className="notice">
            {provider.name} hadn’t been verified when you booked, so none of their skills were backed by documents.
          </p>
        )}

        {needed.length > 0 && <CompetencyList title="Skills you need for this trip" items={needed} />}
        {others.length > 0 && (
          <CompetencyList title={needed.length ? 'Their other skills' : 'Their skills'} items={others} />
        )}
      </section>

      {confirming && (
        <section className="panel panel-wide cancel-confirm" aria-labelledby="cancel-heading">
          <h3 id="cancel-heading">Cancel this booking?</h3>
          <p>
            Your booking with {provider.name} on {formatDayWithYear(booking.starts_at)},{' '}
            {formatTimeRange(booking.starts_at, booking.ends_at)} will be cancelled and the time freed for someone
            else. The record of what was verified is kept.
          </p>
          {cancelError && (
            <p className="form-error" role="alert">
              {cancelError}
            </p>
          )}
          <div className="actions">
            <button type="button" className="danger" onClick={handleCancel} disabled={cancelling}>
              {cancelling ? 'Cancelling…' : 'Yes, cancel booking'}
            </button>
            <button type="button" className="secondary" onClick={() => setConfirming(false)} disabled={cancelling}>
              Keep booking
            </button>
          </div>
        </section>
      )}

      <div className="actions">
        <button type="button" onClick={onAllBookings}>
          All my bookings
        </button>
        <button type="button" className="secondary" onClick={onBack}>
          Back to search
        </button>
        {canCancel && !confirming && (
          <button type="button" className="secondary danger-outline" onClick={() => setConfirming(true)}>
            Cancel booking
          </button>
        )}
      </div>
    </article>
  )
}

function CompetencyList({ title, items }: { title: string; items: SnapshotCompetency[] }) {
  return (
    <div className="snapshot-group">
      <h4>{title}</h4>
      <ul className="snapshot-list">
        {items.map((c) => (
          <li key={c.code} className="snapshot-item">
            <div className="snapshot-row">
              <span className="snapshot-label">{c.label}</span>
              <StatusTag competency={c} />
            </div>
            {c.bio_evidence && (
              <p className="evidence">
                Their profile said: <q>{c.bio_evidence}</q>
              </p>
            )}
            {c.document_evidence && (
              <p className="evidence">
                Their document said: <q>{c.document_evidence}</q>
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

function StatusTag({ competency: c }: { competency: SnapshotCompetency }) {
  if (!c.held) return <span className="tag tag-missing">Not offered by this provider</span>
  if (c.verified) return <span className="tag tag-verified">Backed by a document</span>
  // Listed by the provider but not backed by a document, whether or not the
  // bio mentioned it: the same "self-reported" meaning as on search results.
  return <span className="tag">Self-reported</span>
}
