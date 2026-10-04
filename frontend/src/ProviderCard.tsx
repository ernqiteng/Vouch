import type { Provider, ProviderCompetency } from './api'

const TYPE_LABELS = { carer: 'Carer', driver: 'Driver' } as const

interface Props {
  provider: Provider
  highlighted: Set<string>
}

export default function ProviderCard({ provider, highlighted }: Props) {
  const { verification } = provider
  const verified = verification?.verified ?? false

  return (
    <article className="card">
      <header className="card-header">
        <h3>{provider.name}</h3>
        <div className="badges">
          <span className={`type-badge type-${provider.provider_type}`}>
            {TYPE_LABELS[provider.provider_type]}
          </span>
          <span className={verified ? 'status-badge status-verified' : 'status-badge status-self'}>
            {verified ? '✓ Verified' : 'Self-reported'}
          </span>
        </div>
      </header>

      <p className="card-evidence">
        {verification
          ? `${Math.round(verification.confidence * 100)}% of claimed skills backed by documents`
          : 'No documents checked yet'}
      </p>

      {provider.location && <p className="card-location">{provider.location}</p>}
      {provider.bio && <p className="card-bio">{provider.bio}</p>}

      {provider.competencies.length > 0 ? (
        <ul className="tags" aria-label="Competencies">
          {provider.competencies.map((c) => (
            <CompetencyTag key={c.code} competency={c} matches={highlighted.has(c.code)} />
          ))}
        </ul>
      ) : (
        <p className="card-muted">No competencies listed yet.</p>
      )}
    </article>
  )
}

function CompetencyTag({ competency, matches }: { competency: ProviderCompetency; matches: boolean }) {
  const classes = ['tag', competency.verified && 'tag-verified', matches && 'tag-match']
  return (
    <li className={classes.filter(Boolean).join(' ')}>
      {competency.label}
      <span className="visually-hidden">
        {competency.verified ? ' (backed by a document)' : ' (self-reported)'}
        {matches && ', matches your search'}
      </span>
    </li>
  )
}
