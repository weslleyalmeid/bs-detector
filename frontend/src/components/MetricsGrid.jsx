// Short labels to keep tiles single-line and aligned in the sidebar.
const LABELS = {
  total_citations: 'Citations',
  total_checks: 'Checks',
  rejected_count: 'Rejected',
  accepted_count: 'Accepted',
  unable_to_determine_count: 'Unable',
}

function formatLabel(key) {
  if (LABELS[key]) return LABELS[key]
  return key
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export default function MetricsGrid({ metrics }) {
  if (!metrics) return null
  const entries = Object.entries(metrics)
  return (
    <section className="section">
      <h2 className="section-title">Metrics</h2>
      <div className="metrics-grid">
        {entries.map(([k, v]) => (
          <div key={k} className="metric-tile">
            <div className="metric-label">{formatLabel(k)}</div>
            <div className="metric-value">{v}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
