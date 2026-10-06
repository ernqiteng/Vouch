import { useEffect, useRef, useState } from 'react'
import type { SyntheticEvent } from 'react'
import { AuthError, createBooking, listAvailability } from './api'
import type { Booking, Provider, Slot } from './api'
import { formatDay, formatTimeRange } from './format'

interface Props {
  provider: Provider
  onBooked: (booking: Booking) => void
  onCancel: () => void
  onAuthError: (error: AuthError) => void
}

type SlotsState = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; slots: Slot[] }

function groupByDay(slots: Slot[]): [string, Slot[]][] {
  const groups = new Map<string, Slot[]>()
  for (const slot of slots) {
    const day = formatDay(slot.starts_at)
    groups.set(day, [...(groups.get(day) ?? []), slot])
  }
  return [...groups]
}

export default function BookingForm({ provider, onBooked, onCancel, onAuthError }: Props) {
  const isDriver = provider.provider_type === 'driver'
  const [slots, setSlots] = useState<SlotsState>({ kind: 'loading' })
  const [slotId, setSlotId] = useState<number | null>(null)
  const [pickup, setPickup] = useState('')
  const [dropoff, setDropoff] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  const heading = useRef<HTMLHeadingElement>(null)

  useEffect(() => heading.current?.focus(), [])

  useEffect(() => {
    let current = true
    listAvailability(provider.id)
      .then((list) => current && setSlots({ kind: 'ready', slots: list }))
      .catch((e: Error) => current && setSlots({ kind: 'error', message: e.message }))
    return () => {
      current = false
    }
  }, [provider.id, reload])

  async function handleSubmit(event: SyntheticEvent) {
    event.preventDefault()
    if (slots.kind !== 'ready') return
    const slot = slots.slots.find((s) => s.id === slotId)
    if (!slot) {
      setError('Please choose a time.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const booking = await createBooking({
        provider_id: provider.id,
        requested_time: slot.starts_at,
        pickup,
        dropoff: dropoff.trim() || null,
        notes: notes.trim() || null,
      })
      onBooked(booking)
    } catch (e) {
      if (e instanceof AuthError) return onAuthError(e)
      setError((e as Error).message)
      if ((e as Error).message.includes('already booked')) {
        setSlotId(null)
        setSlots({ kind: 'loading' })
        setReload((n) => n + 1)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel panel-wide" aria-labelledby="book-heading">
      <h2 id="book-heading" ref={heading} tabIndex={-1}>
        Book {provider.name}
      </h2>
      <p className="panel-lede">
        {provider.provider_type === 'carer' ? 'Carer' : 'Driver'}
        {provider.location && ` in ${provider.location}`}. Choose a time, then tell them where to meet you.
      </p>

      <form onSubmit={handleSubmit} className="stack">
        <fieldset>
          <legend>When</legend>
          {slots.kind === 'loading' && <p className="hint">Loading available times…</p>}
          {slots.kind === 'error' && (
            <p className="form-error" role="alert">
              {slots.message}
            </p>
          )}
          {slots.kind === 'ready' && slots.slots.length === 0 && (
            <p className="hint">{provider.name} has no free times in the next two weeks.</p>
          )}
          {slots.kind === 'ready' &&
            groupByDay(slots.slots).map(([day, daySlots]) => (
              <div key={day} className="slot-day">
                <p className="slot-day-name">{day}</p>
                <div className="slot-options">
                  {daySlots.map((slot) => (
                    <label key={slot.id} className={slot.id === slotId ? 'slot slot-selected' : 'slot'}>
                      <input
                        type="radio"
                        name="slot"
                        value={slot.id}
                        checked={slot.id === slotId}
                        onChange={() => setSlotId(slot.id)}
                      />
                      {formatTimeRange(slot.starts_at, slot.ends_at)}
                      <span className="visually-hidden"> on {day}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
        </fieldset>

        <div className="field">
          <label htmlFor="pickup">{isDriver ? 'Pickup address' : 'Address for the visit'}</label>
          <input
            id="pickup"
            required
            maxLength={255}
            autoComplete="street-address"
            value={pickup}
            onChange={(e) => setPickup(e.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="dropoff">
            {isDriver ? 'Drop-off address' : 'Destination, if you’re going somewhere together (optional)'}
          </label>
          <input
            id="dropoff"
            required={isDriver}
            maxLength={255}
            value={dropoff}
            onChange={(e) => setDropoff(e.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="notes">Anything they should know (optional)</label>
          <textarea id="notes" rows={3} maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <div className="actions">
          <button type="submit" disabled={busy || slots.kind !== 'ready' || slotId === null}>
            {busy ? 'Booking…' : 'Confirm booking'}
          </button>
          <button type="button" className="secondary" onClick={onCancel}>
            Back to results
          </button>
        </div>
      </form>
    </section>
  )
}
