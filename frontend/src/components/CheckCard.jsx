import DecisionBadge from './DecisionBadge.jsx'

export default function CheckCard({ check }) {
  const {
    decision,
    statement,
    reason,
    source_document,
    evidence_quote,
    confidence,
    confidence_reason,
  } = check

  return (
    <div className="card check-card">
      <div className="card-header">
        <DecisionBadge decision={decision} size="md" />
        {typeof confidence === 'number' && (
          <div className="confidence">
            <div className="confidence-value">{confidence.toFixed(2)}</div>
            <div className="confidence-label">confidence</div>
          </div>
        )}
      </div>
      <div className="check-statement">{statement}</div>
      {reason && <p className="muted">{reason}</p>}
      {evidence_quote && (
        <blockquote className="quote">
          "{evidence_quote}"
          {source_document && <footer className="quote-footer">— {source_document}</footer>}
        </blockquote>
      )}
      {confidence_reason && <div className="footnote">{confidence_reason}</div>}
    </div>
  )
}
