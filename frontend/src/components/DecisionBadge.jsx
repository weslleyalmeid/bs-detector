function formatDecision(decision) {
  if (!decision) return 'Unknown'
  return decision
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

// Plain-language meaning for the *overall* report decision.
// Per-check badges keep the short label; this is only used at the top
// where one word ("Rejected") risks reading as "the whole motion is false".
const OVERALL_MEANINGS = {
  rejected: 'Motion not supported as written — material claims contradicted by the record.',
  accepted: 'Motion supported by the record.',
  unable_to_determine: 'Insufficient evidence in the record to verify the motion.',
}

export function overallMeaning(decision) {
  return OVERALL_MEANINGS[decision] ?? null
}

export default function DecisionBadge({ decision, size = 'md' }) {
  const cls = `badge badge-${size} badge-${decision || 'unknown'}`
  return <span className={cls}>{formatDecision(decision)}</span>
}
