import { useEffect, useRef, useState } from 'react'
import type { SyntheticEvent } from 'react'
import { saveProfile } from './api'
import type { CommunicationNeed, Competency, Me, MobilityDevice, Profile } from './api'

const MOBILITY_OPTIONS: [MobilityDevice, string][] = [
  ['none', "I don't use a mobility aid"],
  ['manual_wheelchair', 'Manual wheelchair'],
  ['powered_wheelchair', 'Powered wheelchair'],
  ['mobility_scooter', 'Mobility scooter'],
  ['walking_aid', 'Walking aid (stick, frame, crutches)'],
  ['other', 'Something else'],
]

const COMMUNICATION_OPTIONS: [CommunicationNeed, string][] = [
  ['bsl', 'British Sign Language (BSL)'],
  ['lip_reading', 'I lip-read'],
  ['written', 'I prefer written messages to calls'],
  ['easy_read', 'Easy read information'],
  ['extra_time', 'Extra time to process or respond'],
]

interface Props {
  me: Me
  competencies: Competency[]
  onSaved: (profile: Me['profile']) => void
  onClose: () => void
}

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

export default function ProfileForm({ me, competencies, onSaved, onClose }: Props) {
  const saved = me.profile
  const [profile, setProfile] = useState<Profile>({
    mobility_device: saved?.mobility_device ?? null,
    communication_needs: saved?.communication_needs ?? [],
    required_competencies: saved?.required_competencies ?? [],
    location: saved?.location ?? '',
  })
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [error, setError] = useState<string | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)

  useEffect(() => heading.current?.focus(), [])

  function update(changes: Partial<Profile>) {
    setProfile((p) => ({ ...p, ...changes }))
    setStatus('idle')
  }

  async function handleSubmit(event: SyntheticEvent) {
    event.preventDefault()
    setStatus('saving')
    setError(null)
    try {
      const result = await saveProfile({ ...profile, location: profile.location?.trim() || null })
      onSaved(result)
      setStatus('saved')
    } catch (e) {
      setError((e as Error).message)
      setStatus('idle')
    }
  }

  return (
    <section className="panel" aria-labelledby="profile-heading">
      <h2 id="profile-heading" ref={heading} tabIndex={-1}>
        Your accessibility needs
      </h2>
      <p className="panel-lede">
        These apply to every search you make while logged in. You can switch them off for a single search.
      </p>

      <form onSubmit={handleSubmit} className="stack">
        <div className="field">
          <label htmlFor="mobility">Mobility aid</label>
          <select
            id="mobility"
            value={profile.mobility_device ?? ''}
            onChange={(e) => update({ mobility_device: (e.target.value || null) as MobilityDevice | null })}
          >
            <option value="">Prefer not to say</option>
            {MOBILITY_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <p className="hint">For driver searches, wheelchairs and scooters add the right vehicle skills.</p>
        </div>

        <fieldset>
          <legend>Communication</legend>
          {COMMUNICATION_OPTIONS.map(([value, label]) => (
            <label key={value} className="check">
              <input
                type="checkbox"
                checked={profile.communication_needs.includes(value)}
                onChange={() => update({ communication_needs: toggle(profile.communication_needs, value) })}
              />
              {label}
            </label>
          ))}
        </fieldset>

        <fieldset>
          <legend>Skills I always need</legend>
          <div className="check-grid">
            {competencies.map((c) => (
              <label key={c.code} className="check">
                <input
                  type="checkbox"
                  checked={profile.required_competencies.includes(c.code)}
                  onChange={() =>
                    update({ required_competencies: toggle(profile.required_competencies, c.code) })
                  }
                />
                {c.label}
              </label>
            ))}
          </div>
          <p className="hint">Skills only carers have are left out of driver searches, and the other way round.</p>
        </fieldset>

        <div className="field">
          <label htmlFor="location">Home town or postcode</label>
          <input
            id="location"
            autoComplete="address-level2"
            value={profile.location ?? ''}
            maxLength={255}
            onChange={(e) => update({ location: e.target.value })}
          />
        </div>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <p className="form-success" role="status">
          {status === 'saved' ? 'Saved. Your searches will now use these needs.' : ''}
        </p>

        <div className="actions">
          <button type="submit" disabled={status === 'saving'}>
            {status === 'saving' ? 'Saving…' : 'Save my needs'}
          </button>
          <button type="button" className="secondary" onClick={onClose}>
            Back to search
          </button>
        </div>
      </form>
    </section>
  )
}
