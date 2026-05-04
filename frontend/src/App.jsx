import { useState } from 'react'
import './App.css'
import DecisionBadge from './components/DecisionBadge.jsx'
import CitationReview from './components/CitationReview.jsx'
import CheckCard from './components/CheckCard.jsx'
import JudicialMemo from './components/JudicialMemo.jsx'
import MetricsGrid from './components/MetricsGrid.jsx'
import ErrorList from './components/ErrorList.jsx'

function App() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const runAnalysis = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('http://localhost:8002/analyze', { method: 'POST' })
      if (!response.ok) throw new Error(`Server responded with ${response.status}`)
      const data = await response.json()
      setReport(data.report)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const checks = report?.checks ?? []

  return (
    <div className="app">
      <header className="header">
        <div className="header-text">
          <h1 className="app-title">BS Detector</h1>
          {report?.case_name && <div className="case-name">{report.case_name}</div>}
          {!report && <div className="case-name">Legal brief verification pipeline</div>}
        </div>
        <button className="run-btn" onClick={runAnalysis} disabled={loading}>
          {loading ? 'Analyzing…' : 'Run analysis'}
        </button>
      </header>

      <main className="main">
        {error && (
          <div className="error-banner">
            <strong>Error:</strong> {error}
          </div>
        )}

        {!report && !loading && !error && (
          <div className="empty-state">Click "Run analysis" to verify the motion.</div>
        )}

        {loading && <div className="empty-state">Analyzing motion — this may take a moment…</div>}

        {report && (
          <>
            {/* Verdict at a glance — full width */}
            <section className="hero">
              <DecisionBadge decision={report.overall_decision} size="lg" />
              {report.summary && <p className="hero-summary">{report.summary}</p>}
            </section>

            {/* Two-column investigative layout:
                left = exploration (citations + checks, scrollable)
                right = synthesis (memo + metrics, sticky) */}
            <div className="report-grid">
              <div className="report-col report-col--explore">
                <CitationReview review={report.citation_review} />

                {checks.length > 0 && (
                  <section className="section">
                    <h2 className="section-title">Factual Checks ({checks.length})</h2>
                    <div className="checks-list">
                      {checks.map((c) => (
                        <CheckCard key={c.check_id} check={c} />
                      ))}
                    </div>
                  </section>
                )}
              </div>

              <aside className="report-col report-col--summary">
                <JudicialMemo memo={report.judicial_memo} />
                <MetricsGrid metrics={report.metrics} />
              </aside>
            </div>

            <ErrorList errors={report.errors} />
          </>
        )}
      </main>
    </div>
  )
}

export default App
