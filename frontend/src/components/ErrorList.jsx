export default function ErrorList({ errors }) {
  if (!errors || errors.length === 0) return null
  return (
    <section className="section">
      <div className="card error-card">
        <h2 className="section-title error-title">Pipeline Errors</h2>
        <ul className="error-list">
          {errors.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      </div>
    </section>
  )
}
