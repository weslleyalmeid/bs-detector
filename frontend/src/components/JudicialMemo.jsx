export default function JudicialMemo({ memo }) {
  if (!memo) return null
  return (
    <section className="section">
      <h2 className="section-title">Judicial Memo</h2>
      <blockquote className="memo-card">{memo}</blockquote>
    </section>
  )
}
