import DecisionBadge from './DecisionBadge.jsx'

export default function CitationReview({ review }) {
  if (!review) return null
  const { decision, total_citations, reason, citations = [] } = review

  return (
    <section className="section">
      <h2 className="section-title">Citation Review ({total_citations})</h2>
      <div className="card">
        <div className="card-header">
          <DecisionBadge decision={decision} size="md" />
        </div>
        {reason && <p className="muted">{reason}</p>}

        {citations.length > 0 && (
          <details className="details">
            <summary>View {citations.length} citation{citations.length === 1 ? '' : 's'}</summary>
            <div className="citation-list">
              {citations.map((c) => (
                <div key={c.citation_id} className="citation-item">
                  <div className="citation-raw">{c.raw_citation}</div>
                  {c.proposition && <div className="muted small">{c.proposition}</div>}
                  <div className="row">
                    <span className="label">Support:</span>
                    <DecisionBadge decision={c.support_decision} size="sm" />
                    {c.support_reason && <span className="muted small">{c.support_reason}</span>}
                  </div>
                  {c.direct_quote && (
                    <>
                      <blockquote className="quote">"{c.direct_quote}"</blockquote>
                      <div className="row">
                        <span className="label">Quote:</span>
                        <DecisionBadge decision={c.quote_decision} size="sm" />
                        {c.quote_reason && <span className="muted small">{c.quote_reason}</span>}
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </section>
  )
}
