function formatDecision(decision) {
  if (!decision) return 'Unknown'
  return decision
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export default function DecisionBadge({ decision, size = 'md' }) {
  const cls = `badge badge-${size} badge-${decision || 'unknown'}`
  return <span className={cls}>{formatDecision(decision)}</span>
}
