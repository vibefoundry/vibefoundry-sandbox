import { useState, useEffect, useRef, useCallback } from 'react'
import LocalTerminal from './LocalTerminal'
import './ScriptRunner.css'

let terminalIdCounter = 1

function ScriptRunner({ folderName, height }) {
  const [activeTab, setActiveTab] = useState('scripts') // 'scripts' or 'terminal'
  const [terminals, setTerminals] = useState([{ id: terminalIdCounter }])
  const [activeTerminalId, setActiveTerminalId] = useState(terminalIdCounter)
  const [scripts, setScripts] = useState([])
  const [selectedScripts, setSelectedScripts] = useState(new Set())
  const [isRunning, setIsRunning] = useState(false)
  const [output, setOutput] = useState([])
  const [autoRun, setAutoRun] = useState(true)
  const [collapsed, setCollapsed] = useState(false)
  const [scriptsWidth, setScriptsWidth] = useState(200)
  const [isResizingScripts, setIsResizingScripts] = useState(false)
  const outputRef = useRef(null)
  const wsRef = useRef(null)
  const scriptsResizeRef = useRef(null)

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

  const addTerminal = () => {
    terminalIdCounter++
    const newTerminal = { id: terminalIdCounter }
    setTerminals(prev => [...prev, newTerminal])
    setActiveTerminalId(terminalIdCounter)
  }

  const closeTerminal = (id) => {
    setTerminals(prev => {
      const newTerminals = prev.filter(t => t.id !== id)
      if (newTerminals.length === 0) {
        // Always keep at least one terminal
        terminalIdCounter++
        return [{ id: terminalIdCounter }]
      }
      // If we closed the active terminal, switch to another
      if (activeTerminalId === id) {
        setActiveTerminalId(newTerminals[newTerminals.length - 1].id)
      }
      return newTerminals
    })
  }

  const clearTerminals = () => {
    terminalIdCounter++
    setTerminals([{ id: terminalIdCounter }])
    setActiveTerminalId(terminalIdCounter)
  }

  const handleScriptsResizeStart = (e) => {
    e.preventDefault()
    scriptsResizeRef.current = true
    setIsResizingScripts(true)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const startX = e.clientX
    const startWidth = scriptsWidth

    const handleResizeMove = (e) => {
      if (!scriptsResizeRef.current) return
      const delta = e.clientX - startX
      const newWidth = Math.max(100, Math.min(400, startWidth + delta))
      setScriptsWidth(newWidth)
    }

    const handleResizeEnd = () => {
      scriptsResizeRef.current = false
      setIsResizingScripts(false)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', handleResizeMove)
      document.removeEventListener('mouseup', handleResizeEnd)
    }

    document.addEventListener('mousemove', handleResizeMove)
    document.addEventListener('mouseup', handleResizeEnd)
  }

  if (!folderName) return null

  return (
    <div className={`script-runner ${collapsed ? 'collapsed' : ''}`} style={height ? { height } : undefined}>
      <div className="script-runner-header">
        <div className="script-runner-header-left">
          <span className="collapse-icon" onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? '▶' : '▼'}
          </span>
          <div className="script-runner-tabs">
            <button
              className={`script-runner-tab ${activeTab === 'scripts' ? 'active' : ''}`}
              onClick={() => setActiveTab('scripts')}
            >
              Script Runner
            </button>
            <button
              className={`script-runner-tab ${activeTab === 'terminal' ? 'active' : ''}`}
              onClick={() => setActiveTab('terminal')}
            >
              Local Terminal
            </button>
          </div>
        </div>
        {activeTab === 'scripts' && (
          <div className="script-runner-header-actions" onClick={(e) => e.stopPropagation()}>
            <label className="auto-run-label">
              <input
                type="checkbox"
                checked={autoRun}
                onChange={(e) => setAutoRun(e.target.checked)}
              />
              Auto
            </label>
            <button
              className="btn-header"
              onClick={handleRun}
              disabled={isRunning || selectedScripts.size === 0}
            >
              {isRunning ? 'Running...' : 'Run'}
            </button>
            <button className="btn-header" onClick={fetchScripts}>
              Refresh
            </button>
            <button className="btn-header" onClick={handleRefreshMetadata}>
              Farm Metadata
            </button>
            <button className="btn-header" onClick={clearOutput}>
              Clear
            </button>
          </div>
        )}
      </div>

      {!collapsed && activeTab === 'scripts' && (
        <div className={`script-runner-body ${isResizingScripts ? 'resizing' : ''}`}>

          <div className="script-list" style={{ width: scriptsWidth }}>
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

          <div className="scripts-resize-handle" onMouseDown={handleScriptsResizeStart} />

          <div className="script-output-section">
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

      {!collapsed && activeTab === 'terminal' && (
        <div className="local-terminal-body">
          <div className="terminal-tabs-bar">
            {terminals.map(term => (
              <div
                key={term.id}
                className={`terminal-tab ${activeTerminalId === term.id ? 'active' : ''}`}
                onClick={() => setActiveTerminalId(term.id)}
              >
                <span>Terminal {term.id}</span>
                <button
                  className="terminal-tab-close"
                  onClick={(e) => {
                    e.stopPropagation()
                    closeTerminal(term.id)
                  }}
                >
                  ×
                </button>
              </div>
            ))}
            <button className="terminal-tab-new" onClick={addTerminal}>+</button>
            <button className="terminal-tab-clear" onClick={clearTerminals}>Clear All</button>
          </div>
          <div className="terminal-instances">
            {terminals.map(term => (
              <div
                key={term.id}
                className="terminal-instance-wrapper"
                style={{ display: activeTerminalId === term.id ? 'flex' : 'none' }}
              >
                <LocalTerminal id={term.id} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default ScriptRunner
