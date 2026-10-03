import type { Provider } from './api'

const TYPE_LABELS = { carer: 'Carer', driver: 'Driver' } as const

interface Props {
  provider: Provider
  highlighted: Set<string>
}

export default function ProviderCard({ provider, highlighted }: Props) {
  return (
    <article className="card">
      <header className="card-header">
        <h3>{provider.name}</h3>
        <span className={`type-badge type-${provider.provider_type}`}>
          {TYPE_LABELS[provider.provider_type]}
        </span>
      </header>

      {provider.location && <p className="card-location">{provider.location}</p>}
      {provider.bio && <p className="card-bio">{provider.bio}</p>}

      {provider.competencies.length > 0 ? (
        <ul className="tags" aria-label="Competencies">
          {provider.competencies.map((c) => (
            <li key={c.code} className={highlighted.has(c.code) ? 'tag tag-match' : 'tag'}>
              {c.label}
              {highlighted.has(c.code) && <span className="visually-hidden"> (matches your search)</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="card-muted">No competencies listed yet.</p>
      )}
    </article>
  )
}
