import type { Provider, ProviderCompetency, RankingBreakdown } from './api'

const TYPE_LABELS = { carer: 'Carer', driver: 'Driver' } as const

interface Props {
  provider: Provider & { ranking?: RankingBreakdown }
  highlighted: Set<string>
  rankedFrom?: string | null
}

const percent = (value: number) => `${Math.round(value * 100)}%`

export default function ProviderCard({ provider, highlighted, rankedFrom }: Props) {
  const { verification, ranking } = provider
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
          {ranking && <span className="match-badge">{percent(ranking.score)} match</span>}
        </div>
      </header>

      <p className="card-evidence">
        {verification
          ? `${percent(verification.confidence)} of claimed skills backed by documents`
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

      {ranking && <WhyThisPosition ranking={ranking} rankedFrom={rankedFrom ?? null} />}
    </article>
  )
}

function WhyThisPosition({ ranking, rankedFrom }: { ranking: RankingBreakdown; rankedFrom: string | null }) {
  const distance =
    ranking.distance_km !== null
      ? `${ranking.distance_km} km from ${rankedFrom}`
      : rankedFrom
        ? 'Location not known'
        : 'Your location isn’t known, so this doesn’t change the order'
  const rows: [string, string, number, string][] = [
    ['Has the skills you need', '40%', ranking.competency_match, percent(ranking.competency_match) + ' of them'],
    ['Skills backed by documents', '25%', ranking.verification_confidence, percent(ranking.verification_confidence)],
    ['Available', '20%', ranking.availability, 'Not checked yet, counted as available'],
    ['Distance', '15%', ranking.distance, distance],
  ]
  return (
    <details className="why">
      <summary>Why this position?</summary>
      <table>
        <caption className="visually-hidden">How this provider's {percent(ranking.score)} match score is made up</caption>
        <thead>
          <tr>
            <th scope="col">Factor</th>
            <th scope="col">Weight</th>
            <th scope="col">Score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, weight, value, detail]) => (
            <tr key={label}>
              <th scope="row">
                {label}
                <span className="why-detail">{detail}</span>
              </th>
              <td>{weight}</td>
              <td>{percent(value)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Match score</th>
            <td />
            <td>{percent(ranking.score)}</td>
          </tr>
        </tfoot>
      </table>
    </details>
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
