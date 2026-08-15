import { useEffect, useState } from 'react'
import { startBackend, getBackendStatus, onTauriReady } from './lib/tauri'

function App() {
  const [backendStatus, setBackendStatus] = useState<{ running: boolean; message: string }>({
    running: false,
    message: 'Checking...',
  })
  const [logs, setLogs] = useState<string[]>([])

  useEffect(() => {
    // Listen for tauri-ready event
    onTauriReady(() => {
      addLog('Tauri is ready')
      checkBackendStatus()
    })

    // Start backend automatically
    startBackend().then((msg) => {
      addLog(msg)
      setTimeout(checkBackendStatus, 2000)
    }).catch((err) => {
      addLog(`Failed to start backend: ${err}`)
    })
  }, [])

  const addLog = (msg: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [...prev, `[${timestamp}] ${msg}`])
  }

  const checkBackendStatus = async () => {
    try {
      const status = await getBackendStatus()
      setBackendStatus(status)
      addLog(`Backend status: ${status.running ? 'Running' : 'Stopped'} - ${status.message}`)
    } catch (err) {
      addLog(`Status check failed: ${err}`)
    }
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>Vortex Agent</h1>
        <div style={styles.statusBadge}>
          <span style={{
            ...styles.statusDot,
            backgroundColor: backendStatus.running ? '#10b981' : '#ef4444'
          }} />
          <span>{backendStatus.running ? 'Backend Running' : 'Backend Stopped'}</span>
        </div>
      </header>

      <main style={styles.main}>
        <section style={styles.panel}>
          <h2 style={styles.panelTitle}>System Status</h2>
          <p style={styles.statusMessage}>{backendStatus.message}</p>
          
          <div style={styles.buttonGroup}>
            <button 
              onClick={checkBackendStatus}
              style={styles.button}
            >
              Refresh Status
            </button>
          </div>
        </section>

        <section style={styles.panel}>
          <h2 style={styles.panelTitle}>Activity Log</h2>
          <div style={styles.logContainer}>
            {logs.map((log, idx) => (
              <div key={idx} style={styles.logEntry}>{log}</div>
            ))}
            {logs.length === 0 && <div style={styles.emptyLog}>No activity yet...</div>}
          </div>
        </section>

        <section style={styles.panel}>
          <h2 style={styles.panelTitle}>Quick Actions</h2>
          <div style={styles.buttonGroup}>
            <button style={styles.button} disabled={!backendStatus.running}>
              Start Chat
            </button>
            <button style={styles.button} disabled={!backendStatus.running}>
              Create Task
            </button>
            <button style={styles.button} disabled={!backendStatus.running}>
              Open Council
            </button>
            <button style={styles.button} disabled={!backendStatus.running}>
              View Memory
            </button>
            <button style={styles.button} disabled={!backendStatus.running}>
              Knowledge Graph
            </button>
            <button style={styles.button} disabled={!backendStatus.running}>
              Governance
            </button>
            <button style={styles.button} disabled={!backendStatus.running}>
              Evolution
            </button>
          </div>
        </section>
      </main>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    minHeight: '100vh',
    backgroundColor: '#f8f9fa',
    color: '#1d1d1f',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '24px 32px',
    borderBottom: '1px solid #e5e5e5',
    backgroundColor: '#ffffff',
    boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
  },
  title: {
    margin: 0,
    fontSize: '28px',
    fontWeight: 600,
    letterSpacing: '-0.02em',
    background: 'linear-gradient(135deg, #0071e3, #00c6ff)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  statusBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 16px',
    borderRadius: '9999px',
    backgroundColor: '#f0f4f8',
    fontSize: '14px',
    fontWeight: 500,
  },
  statusDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
  },
  main: {
    padding: '32px',
    maxWidth: '1200px',
    margin: '0 auto',
  },
  panel: {
    backgroundColor: '#ffffff',
    borderRadius: '16px',
    padding: '24px',
    marginBottom: '24px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.04), 0 1px 4px rgba(0,0,0,0.02)',
    border: '1px solid #eef2f7',
  },
  panelTitle: {
    margin: '0 0 16px 0',
    fontSize: '18px',
    fontWeight: 600,
    color: '#1d1d1f',
  },
  statusMessage: {
    margin: '0 0 16px 0',
    color: '#6e6e73',
    fontSize: '15px',
    lineHeight: 1.5,
  },
  buttonGroup: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '12px',
  },
  button: {
    padding: '10px 20px',
    borderRadius: '10px',
    border: 'none',
    backgroundColor: '#0071e3',
    color: '#ffffff',
    fontSize: '14px',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    boxShadow: '0 2px 8px rgba(0,113,227,0.25)',
  },
  logContainer: {
    maxHeight: '300px',
    overflowY: 'auto',
    backgroundColor: '#1d1d1f',
    borderRadius: '10px',
    padding: '16px',
    fontFamily: 'SF Mono, Monaco, "Courier New", monospace',
    fontSize: '12px',
    lineHeight: 1.6,
  },
  logEntry: {
    color: '#d4d4d4',
    borderBottom: '1px solid #2d2d2d',
    padding: '4px 0',
  },
  emptyLog: {
    color: '#6e6e73',
    fontStyle: 'italic',
    textAlign: 'center',
    padding: '32px',
  },
}

export default App