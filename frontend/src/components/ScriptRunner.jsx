import { useState, useEffect, useRef, useCallback } from 'react'
import './ScriptRunner.css'

function ScriptRunner({ folderName, height, onHeightChange, isResizing, onResizeStart }) {
  const [scripts, setScripts] = useState([])
  const [selectedScripts, setSelectedScripts] = useState(new Set())
  const [isRunning, setIsRunning] = useState(false)
  const [output, setOutput] = useState([])
  const [autoRun, setAutoRun] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [outputExpanded, setOutputExpanded] = useState(false)
  const outputRef = useRef(null)
  const wsRef = useRef(null)

  // Fetch scripts list
  const fetchScripts = useCallback(async () => {
    try {
      const res = await fetch('/api/scripts')
      if (res.ok) {
        const data = await res.json()
        setScripts(data.scripts || [])
      }
    } catch (err) {
      console.error('Failed to fetch scripts:', err)
    }
  }, [])

  // Load scripts when folder changes
  useEffect(() => {
    if (folderName) {
      fetchScripts()
    }
  }, [folderName, fetchScripts])

  // Connect to WebSocket for file change notifications
  useEffect(() => {
    if (!folderName) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/watch`

    const connect = () => {
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('Script watcher connected')
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'script_change' && autoRun) {
            // Auto-run the modified script
            const scriptPath = data.path
            addOutput(`Script modified: ${scriptPath.split('/').pop()}`, 'info')
            runScripts([scriptPath])
          } else if (data.type === 'data_change') {
            addOutput('Data files changed - metadata updated', 'info')
          }
        } catch (e) {
          // Ignore parse errors for keepalive messages
        }
      }

      ws.onclose = () => {
        // Reconnect after delay
        setTimeout(connect, 3000)
      }

      wsRef.current = ws
    }

    connect()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [folderName, autoRun])

  // Auto-scroll output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [output])

  const addOutput = (message, type = 'log') => {
    setOutput(prev => [...prev, { message, type, timestamp: new Date() }])
  }

  const toggleScript = (scriptPath) => {
    setSelectedScripts(prev => {
      const next = new Set(prev)
      if (next.has(scriptPath)) {
        next.delete(scriptPath)
      } else {
        next.add(scriptPath)
      }
      return next
    })
  }

  const selectAll = () => {
    setSelectedScripts(new Set(scripts.map(s => s.path)))
  }

  const selectNone = () => {
    setSelectedScripts(new Set())
  }

  const runScripts = async (scriptPaths) => {
    if (scriptPaths.length === 0) return

    setIsRunning(true)
    addOutput('─'.repeat(40), 'divider')

    for (const scriptPath of scriptPaths) {
      const scriptName = scriptPath.split('/').pop()
      addOutput(`▶ Running: ${scriptName}`, 'header')

      try {
        const res = await fetch('/api/scripts/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scripts: [scriptPath] })
        })

        if (res.ok) {
          const data = await res.json()
          const result = data.results[0]

          if (result.stdout) {
            addOutput(result.stdout.trim(), 'stdout')
          }
          if (result.stderr) {
            addOutput(result.stderr.trim(), 'stderr')
          }
          if (result.error) {
            addOutput(result.error, 'error')
          }

          if (result.success) {
            addOutput(`✓ ${scriptName} completed`, 'success')
          } else if (result.timed_out) {
            addOutput(`⏱ ${scriptName} timed out`, 'error')
          } else {
            addOutput(`✗ ${scriptName} failed (code ${result.return_code})`, 'error')
          }
        } else {
          addOutput(`Failed to run ${scriptName}`, 'error')
        }
      } catch (err) {
        addOutput(`Error: ${err.message}`, 'error')
      }
    }

    setIsRunning(false)
  }

  const handleRun = () => {
    const selected = Array.from(selectedScripts)
    if (selected.length === 0) {
      addOutput('No scripts selected', 'warning')
      return
    }
    runScripts(selected)
  }

  const handleRefreshMetadata = async () => {
    try {
      const res = await fetch('/api/metadata/generate', { method: 'POST' })
      if (res.ok) {
        addOutput('✓ Metadata regenerated', 'success')
      }
    } catch (err) {
      addOutput(`Metadata error: ${err.message}`, 'error')
    }
  }

  const clearOutput = () => {
    setOutput([])
  }

  if (!folderName) return null

  return (
    <div
      className={`script-runner ${collapsed ? 'collapsed' : ''} ${isResizing ? 'resizing' : ''}`}
      style={{ height: collapsed ? 48 : height }}
    >
      <div className="script-runner-resize-handle" onMouseDown={onResizeStart} />
      <div className="script-runner-header" onClick={() => setCollapsed(!collapsed)}>
        <span className="script-runner-title">Script Runner</span>
        <span className="script-count">{scripts.length} script{scripts.length !== 1 ? 's' : ''}</span>
        <span className="collapse-icon">{collapsed ? '▲' : '▼'}</span>
      </div>

      {!collapsed && (
        <div className="script-runner-body">
          <div className="script-runner-controls">
            <button
              className="btn-run"
              onClick={handleRun}
              disabled={isRunning || selectedScripts.size === 0}
            >
              {isRunning ? 'Running...' : '▶ Run'}
            </button>
            <button className="btn-flat" onClick={fetchScripts}>
              ↻ Refresh
            </button>
            <button className="btn-flat" onClick={handleRefreshMetadata}>
              📋 Metadata
            </button>
            <label className="auto-run-toggle">
              <input
                type="checkbox"
                checked={autoRun}
                onChange={(e) => setAutoRun(e.target.checked)}
              />
              Auto-run
            </label>
          </div>

          <div className="script-list">
            {scripts.length > 0 ? (
              <>
                <div className="script-list-actions">
                  <button className="btn-link" onClick={selectAll}>All</button>
                  <button className="btn-link" onClick={selectNone}>None</button>
                </div>
                {scripts.map((script) => (
                  <label key={script.path} className="script-item">
                    <input
                      type="checkbox"
                      checked={selectedScripts.has(script.path)}
                      onChange={() => toggleScript(script.path)}
                    />
                    <span className="script-name">{script.relative_path}</span>
                  </label>
                ))}
              </>
            ) : (
              <div className="no-scripts">No scripts in app_folder/scripts/</div>
            )}
          </div>

          <div className={`script-output-section ${outputExpanded ? 'expanded' : ''}`}>
            <div className="script-output-header">
              <span>Output</span>
              <div className="script-output-actions">
                <button className="btn-link" onClick={clearOutput}>Clear</button>
                <button className="btn-link" onClick={() => setOutputExpanded(!outputExpanded)}>
                  {outputExpanded ? 'Collapse' : 'Expand'}
                </button>
              </div>
            </div>
            <div className="script-output" ref={outputRef}>
              {output.map((entry, i) => (
                <div key={i} className={`output-line ${entry.type}`}>
                  {entry.message}
                </div>
              ))}
              {output.length === 0 && (
                <div className="output-placeholder">Script output will appear here...</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ScriptRunner
