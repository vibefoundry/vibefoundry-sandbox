import { useEffect, useRef, useState } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'

// Fixed terminal size - wider and taller for better Claude Code experience
const FIXED_COLS = 80
const FIXED_ROWS = 48

function Terminal({ syncUrl, isConnected, alwaysExpanded = false }) {
  const terminalRef = useRef(null)
  const xtermRef = useRef(null)
  const wsRef = useRef(null)
  const [isTerminalConnected, setIsTerminalConnected] = useState(false)
  const [isExpanded, setIsExpanded] = useState(alwaysExpanded)

  // Auto-expand when alwaysExpanded changes
  useEffect(() => {
    if (alwaysExpanded) {
      setIsExpanded(true)
    }
  }, [alwaysExpanded])

  useEffect(() => {
    if (!terminalRef.current || !isExpanded) return

    // Create terminal with fixed size
    const xterm = new XTerm({
      cursorBlink: true,
      cursorStyle: 'block',
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      scrollback: 5000,
      cols: FIXED_COLS,
      rows: FIXED_ROWS,
      theme: {
        background: '#ffffff',
        foreground: '#1e1e1e',
        cursor: '#1e1e1e',
        selectionBackground: '#b5d5ff',
        black: '#1e1e1e',
        red: '#c91b00',
        green: '#00a600',
        yellow: '#c7c400',
        blue: '#0451a5',
        magenta: '#bc05bc',
        cyan: '#0598bc',
        white: '#e5e5e5',
        brightBlack: '#666666',
        brightRed: '#e74856',
        brightGreen: '#16c60c',
        brightYellow: '#f9f1a5',
        brightBlue: '#3b78ff',
        brightMagenta: '#b4009e',
        brightCyan: '#61d6d6',
        brightWhite: '#ffffff',
      }
    })

    xterm.open(terminalRef.current)
    xtermRef.current = xterm

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      xterm.dispose()
    }
  }, [isExpanded])

  // Connect WebSocket when expanded and syncUrl available
  useEffect(() => {
    if (!isExpanded || !syncUrl || !xtermRef.current) return

    const wsUrl = syncUrl.replace('https://', 'wss://').replace('http://', 'ws://') + '/terminal'

    xtermRef.current.writeln('Connecting to terminal...')

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    // Ping interval to keep connection alive
    let pingInterval = null

    ws.onopen = () => {
      setIsTerminalConnected(true)
      xtermRef.current.clear()

      // Send fixed terminal size to backend
      ws.send(JSON.stringify({ type: 'resize', cols: FIXED_COLS, rows: FIXED_ROWS }))

      // Auto-run claude after shell prompt loads
      setTimeout(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('claude\n')
        }
      }, 2000)

      // Start ping interval to keep connection alive (every 30 seconds)
      pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30000)

    }

    ws.onmessage = (event) => {
      // Filter out pong messages
      const filtered = event.data.replace(/\{"type":\s*"pong"\}/g, '')
      if (filtered) {
        xtermRef.current.write(filtered)
      }
    }

    ws.onclose = () => {
      setIsTerminalConnected(false)
      if (pingInterval) clearInterval(pingInterval)
      if (xtermRef.current) {
        xtermRef.current.writeln('\r\n\x1b[31mConnection closed\x1b[0m')
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      if (xtermRef.current) {
        xtermRef.current.writeln('\r\n\x1b[31mConnection error\x1b[0m')
      }
    }

    // Handle direct keyboard input in terminal
    const inputDisposable = xtermRef.current.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data)
      }
    })

    return () => {
      if (pingInterval) clearInterval(pingInterval)
      inputDisposable.dispose()
      ws.close()
    }
  }, [isExpanded, syncUrl])

  if (!isConnected) {
    return null
  }

  // When alwaysExpanded, render terminal directly (type directly in terminal)
  if (alwaysExpanded) {
    return (
      <div className="terminal-container expanded">
        <div className="terminal-body" ref={terminalRef}></div>
        <div className="terminal-end-line"></div>
      </div>
    )
  }

  return (
    <div className={`terminal-container ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <div className="terminal-header" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="terminal-title">
          <span className={`terminal-dot ${isTerminalConnected ? 'connected' : ''}`}></span>
          Terminal
        </span>
        <span className="terminal-toggle">{isExpanded ? '−' : '+'}</span>
      </div>
      {isExpanded && (
        <>
          <div className="terminal-body" ref={terminalRef}></div>
          <div className="terminal-end-line"></div>
        </>
      )}
    </div>
  )
}

export default Terminal
