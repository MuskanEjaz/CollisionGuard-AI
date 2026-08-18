/**
 * App — root component.
 *
 * Composes HealthStatus and ScenarioPanel.
 * Contains no business logic and no hardcoded computed results.
 */
import HealthStatus from './components/HealthStatus'
import ScenarioPanel from './components/ScenarioPanel'

const containerStyle = {
  fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif',
  maxWidth: '760px',
  margin: '0 auto',
  padding: '2rem 1.5rem',
  color: '#1f2328',
  lineHeight: 1.6,
}

const headerStyle = {
  borderBottom: '1px solid #e5e7eb',
  marginBottom: '2rem',
  paddingBottom: '1rem',
}

const disclaimerStyle = {
  fontSize: '0.75rem',
  color: '#6b7280',
  marginTop: '0.25rem',
}

export default function App() {
  return (
    <div style={containerStyle}>
      <header style={headerStyle}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700 }}>
          CollisionGuard AI
        </h1>
        <p style={disclaimerStyle}>
          Human-supervised decision-support prototype with simulated auto-execution.
          Not autonomous. Not flight-ready.
        </p>
      </header>

      <HealthStatus />
      <ScenarioPanel />
    </div>
  )
}
