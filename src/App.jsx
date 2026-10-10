import { useState } from 'react'
import './App.css'

function App() {
  const [waterLevel, setWaterLevel] = useState(1.8) // Level in meters
  const [reports, setReports] = useState([
    { id: 1, location: 'Marikina River', level: 'Critical', time: '10 mins ago' },
    { id: 2, location: 'España Blvd', level: 'Moderate', time: '25 mins ago' },
  ])

  return (
    <div className="container">
      {/* Header */}
      <header className="header">
        <h1>🌊 Bantay Baha</h1>
        <p>Real-Time Flood Monitoring & Emergency Alert System</p>
      </header>

      {/* Main Alert Status */}
      <div className={`alert-card ${waterLevel > 1.5 ? 'warning' : 'safe'}`}>
        <h2>Current Alert Status</h2>
        <div className="status-badge">
          {waterLevel > 1.5 ? '⚠️ HIGH RISK / WARNING' : '✅ NORMAL LEVEL'}
        </div>
        <p className="water-depth">Current Water Level: <strong>{waterLevel}m</strong></p>
        
        {/* Quick actions to simulate level changes */}
        <div className="button-group">
          <button onClick={() => setWaterLevel((prev) => +(prev + 0.2).toFixed(1))}>
            + Increase Level
          </button>
          <button onClick={() => setWaterLevel((prev) => +(Math.max(0, prev - 0.2)).toFixed(1))}>
            - Lower Level
          </button>
        </div>
      </div>

      {/* Community Reports List */}
      <section className="reports-section">
        <h3>Recent Flood Reports</h3>
        <ul className="report-list">
          {reports.map((report) => (
            <li key={report.id} className="report-item">
              <div>
                <strong>{report.location}</strong>
                <span className="timestamp"> ({report.time})</span>
              </div>
              <span className={`badge ${report.level.toLowerCase()}`}>
                {report.level}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

export default App