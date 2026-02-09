import { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { List } from 'react-window'

const ROW_HEIGHT = 36
const CHUNK_SIZE = 200

// Row component for react-window v2
const VirtualRow = ({ index, style, rows, columns, columnWidths, isCellSelected, handleCellMouseDown, handleCellMouseEnter }) => {
  const row = rows[index]
  if (!row) return null

  return (
    <div style={style} className="virtual-row">
      <table className="dataframe-table dataframe-body-table">
        <tbody>
          <tr>
            <td className="row-number">{index + 1}</td>
            {columns.map((col, colIdx) => {
              const width = columnWidths[col]
              return (
                <td
                  key={col}
                  className={isCellSelected(index, colIdx) ? 'selected' : ''}
                  onMouseDown={(e) => handleCellMouseDown(index, colIdx, e)}
                  onMouseEnter={() => handleCellMouseEnter(index, colIdx)}
                  title={String(row[col] ?? '')}
                  style={width ? { width: width, minWidth: width } : undefined}
                >
                  {String(row[col] ?? '')}
                </td>
              )
            })}
          </tr>
        </tbody>
      </table>
    </div>
  )
}

const DataFrameViewer = ({ content }) => {
  // Data state - rows loaded from backend
  const [rows, setRows] = useState(content.data || [])
  const [totalRows, setTotalRows] = useState(content.totalRows || content.data?.length || 0)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [loadedUpTo, setLoadedUpTo] = useState(content.data?.length || 0)

  // Filter/sort state
  const [filters, setFilters] = useState({})
  const [activeFilter, setActiveFilter] = useState(null)
  const [filterSearch, setFilterSearch] = useState('')
  const [tempFilter, setTempFilter] = useState({})
  const [dropdownPosition, setDropdownPosition] = useState({ x: 0, y: 0 })
  const [sortConfig, setSortConfig] = useState({ column: null, direction: 'asc' })

  // UI state
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [selection, setSelection] = useState(null)
  const [isSelecting, setIsSelecting] = useState(false)
  const [columnWidths, setColumnWidths] = useState({})
  const [resizingColumn, setResizingColumn] = useState(null)

  // Refs
  const dropdownRef = useRef(null)
  const filterButtonRefs = useRef({})
  const tableRef = useRef(null)
  const containerRef = useRef(null)
  const headerRef = useRef(null)
  const listRef = useRef(null)
  const [containerHeight, setContainerHeight] = useState(400)

  // Get columnInfo from props (computed by backend)
  const columnInfo = content.columnInfo || {}
  const filePath = content.filePath

  // Reset state when file changes
  useEffect(() => {
    setRows(content.data || [])
    setTotalRows(content.totalRows || content.data?.length || 0)
    setLoadedUpTo(content.data?.length || 0)
    setFilters({})
    setSortConfig({ column: null, direction: 'asc' })
    setSelection(null)
    setColumnWidths({})
  }, [content.filename])

  // Measure container height for virtual list
  useEffect(() => {
    const measureHeight = () => {
      if (containerRef.current) {
        const container = containerRef.current
        const toolbar = container.querySelector('.dataframe-toolbar')
        const statusbar = container.querySelector('.dataframe-statusbar')
        const header = container.querySelector('.dataframe-header-container')
        const toolbarH = toolbar?.offsetHeight || 0
        const statusH = statusbar?.offsetHeight || 0
        const headerH = header?.offsetHeight || 0
        const availableHeight = container.offsetHeight - toolbarH - statusH - headerH
        setContainerHeight(Math.max(100, availableHeight))
      }
    }
    measureHeight()
    window.addEventListener('resize', measureHeight)
    const timer = setTimeout(measureHeight, 100)
    return () => {
      window.removeEventListener('resize', measureHeight)
      clearTimeout(timer)
    }
  }, [isFullscreen])

  // Sync horizontal scroll between header and body
  const handleBodyScroll = useCallback((e) => {
    if (headerRef.current) {
      headerRef.current.scrollLeft = e.target.scrollLeft
    }
  }, [])

  // Load more rows when scrolling near bottom
  const handleItemsRendered = useCallback(async ({ visibleStopIndex }) => {
    // Check if we need to load more rows
    if (isLoadingMore || !filePath) return
    if (loadedUpTo >= totalRows) return
    if (visibleStopIndex < loadedUpTo - 50) return // Not near bottom yet

    setIsLoadingMore(true)
    try {
      const res = await fetch(
        `/api/dataframe/rows?filePath=${encodeURIComponent(filePath)}&offset=${loadedUpTo}&limit=${CHUNK_SIZE}`
      )
      if (res.ok) {
        const data = await res.json()
        setRows(prev => [...prev, ...data.data])
        setLoadedUpTo(prev => prev + data.data.length)
        setTotalRows(data.totalRows)
      }
    } catch (err) {
      console.error('Failed to load more rows:', err)
    } finally {
      setIsLoadingMore(false)
    }
  }, [isLoadingMore, filePath, loadedUpTo, totalRows])

  // Apply filter/sort via backend
  const applyFilterSort = useCallback(async (newFilters, newSort) => {
    if (!filePath) return

    try {
      const res = await fetch('/api/dataframe/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filePath,
          filters: newFilters,
          sort: newSort.column ? newSort : null
        })
      })

      if (res.ok) {
        const data = await res.json()
        setRows(data.data)
        setTotalRows(data.totalRows)
        setLoadedUpTo(data.data.length)
      }
    } catch (err) {
      console.error('Failed to apply filter/sort:', err)
    }
  }, [filePath])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setActiveFilter(null)
        setFilterSearch('')
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'c' && selection) {
        e.preventDefault()
        copySelection()
      }
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [selection, isFullscreen])

  // Calculate selection statistics
  const selectionStats = (() => {
    if (!selection) return null

    const { startRow, startCol, endRow, endCol } = selection
    const minRow = Math.min(startRow, endRow)
    const maxRow = Math.max(startRow, endRow)
    const minCol = Math.min(startCol, endCol)
    const maxCol = Math.max(startCol, endCol)

    const values = []
    for (let r = minRow; r <= maxRow; r++) {
      for (let c = minCol; c <= maxCol; c++) {
        if (r < rows.length && c < content.columns.length) {
          const val = rows[r][content.columns[c]]
          if (typeof val === 'number' && !isNaN(val)) {
            values.push(val)
          }
        }
      }
    }

    const cellCount = (maxRow - minRow + 1) * (maxCol - minCol + 1)

    if (values.length === 0) {
      return { count: cellCount, numericCount: 0 }
    }

    const sum = values.reduce((a, b) => a + b, 0)
    const avg = sum / values.length
    const min = Math.min(...values)
    const max = Math.max(...values)

    return {
      count: cellCount,
      numericCount: values.length,
      sum: sum,
      average: avg,
      min: min,
      max: max
    }
  })()

  // Copy selection to clipboard
  const copySelection = useCallback(() => {
    if (!selection) return

    const { startRow, startCol, endRow, endCol } = selection
    const minRow = Math.min(startRow, endRow)
    const maxRow = Math.max(startRow, endRow)
    const minCol = Math.min(startCol, endCol)
    const maxCol = Math.max(startCol, endCol)

    const lines = []
    for (let r = minRow; r <= maxRow; r++) {
      const cells = []
      for (let c = minCol; c <= maxCol; c++) {
        if (r < rows.length && c < content.columns.length) {
          cells.push(String(rows[r][content.columns[c]] ?? ''))
        }
      }
      lines.push(cells.join('\t'))
    }

    navigator.clipboard.writeText(lines.join('\n'))
  }, [selection, rows, content.columns])

  // Handle column header click for sorting
  const handleSort = async (col) => {
    const newSort = sortConfig.column === col
      ? { column: col, direction: sortConfig.direction === 'asc' ? 'desc' : 'asc' }
      : { column: col, direction: 'asc' }

    setSortConfig(newSort)
    await applyFilterSort(filters, newSort)
  }

  // Cell selection handlers
  const handleCellMouseDown = (rowIdx, colIdx, e) => {
    if (e.button !== 0) return
    setSelection({ startRow: rowIdx, startCol: colIdx, endRow: rowIdx, endCol: colIdx })
    setIsSelecting(true)
  }

  const handleCellMouseEnter = (rowIdx, colIdx) => {
    if (isSelecting && selection) {
      setSelection(prev => ({ ...prev, endRow: rowIdx, endCol: colIdx }))
    }
  }

  const handleMouseUp = () => {
    setIsSelecting(false)
  }

  useEffect(() => {
    document.addEventListener('mouseup', handleMouseUp)
    return () => document.removeEventListener('mouseup', handleMouseUp)
  }, [])

  // Check if cell is in selection
  const isCellSelected = (rowIdx, colIdx) => {
    if (!selection) return false
    const { startRow, startCol, endRow, endCol } = selection
    const minRow = Math.min(startRow, endRow)
    const maxRow = Math.max(startRow, endRow)
    const minCol = Math.min(startCol, endCol)
    const maxCol = Math.max(startCol, endCol)
    return rowIdx >= minRow && rowIdx <= maxRow && colIdx >= minCol && colIdx <= maxCol
  }

  // Column resizing handlers
  const handleResizeStart = (col, e) => {
    e.preventDefault()
    e.stopPropagation()
    setResizingColumn(col)

    const startX = e.clientX
    const startWidth = columnWidths[col] || 120

    const handleMouseMove = (e) => {
      const diff = e.clientX - startX
      setColumnWidths(prev => ({ ...prev, [col]: Math.max(50, startWidth + diff) }))
    }

    const handleMouseUp = () => {
      setResizingColumn(null)
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }

  // Filter functions
  const toggleFilter = (col, e) => {
    e.stopPropagation()
    if (activeFilter === col) {
      setActiveFilter(null)
      setFilterSearch('')
      return
    }

    const button = e?.currentTarget || filterButtonRefs.current[col]
    if (button) {
      const rect = button.getBoundingClientRect()
      setDropdownPosition({ x: rect.left, y: rect.bottom + 4 })
    }

    const info = columnInfo[col]
    if (info?.type === 'numeric') {
      setTempFilter(filters[col] || { min: '', max: '' })
    } else {
      setTempFilter(filters[col] || [])
    }
    setActiveFilter(col)
    setFilterSearch('')
  }

  // Collision detection for dropdown
  useEffect(() => {
    if (activeFilter && dropdownRef.current) {
      const dropdown = dropdownRef.current
      const rect = dropdown.getBoundingClientRect()
      const viewportWidth = window.innerWidth
      const viewportHeight = window.innerHeight

      let newX = dropdownPosition.x
      let newY = dropdownPosition.y

      if (dropdownPosition.x + rect.width > viewportWidth - 10) {
        newX = viewportWidth - rect.width - 10
      }

      if (dropdownPosition.y + rect.height > viewportHeight - 10) {
        const button = filterButtonRefs.current[activeFilter]
        if (button) {
          const buttonRect = button.getBoundingClientRect()
          newY = buttonRect.top - rect.height - 4
        }
      }

      newX = Math.max(10, newX)
      newY = Math.max(10, newY)

      if (newX !== dropdownPosition.x || newY !== dropdownPosition.y) {
        setDropdownPosition({ x: newX, y: newY })
      }
    }
  }, [activeFilter, dropdownPosition.x, dropdownPosition.y])

  const applyFilter = async (col) => {
    const newFilters = { ...filters }
    const info = columnInfo[col]

    if (info?.type === 'numeric') {
      if ((tempFilter.min === '' || tempFilter.min === null) &&
          (tempFilter.max === '' || tempFilter.max === null)) {
        delete newFilters[col]
      } else {
        newFilters[col] = tempFilter
      }
    } else {
      if (!tempFilter || tempFilter.length === 0) {
        delete newFilters[col]
      } else {
        newFilters[col] = tempFilter
      }
    }

    setFilters(newFilters)
    setActiveFilter(null)
    setFilterSearch('')
    await applyFilterSort(newFilters, sortConfig)
  }

  const clearFilter = async (col) => {
    const newFilters = { ...filters }
    delete newFilters[col]
    setFilters(newFilters)
    setActiveFilter(null)
    setFilterSearch('')
    await applyFilterSort(newFilters, sortConfig)
  }

  const toggleValue = (value) => {
    setTempFilter(prev => {
      if (Array.isArray(prev)) {
        if (prev.includes(value)) {
          return prev.filter(v => v !== value)
        } else {
          return [...prev, value]
        }
      }
      return [value]
    })
  }

  const selectAll = (col) => {
    const info = columnInfo[col]
    if (!info?.values) return
    const filtered = info.values.filter(v =>
      filterSearch === '' || String(v).toLowerCase().includes(filterSearch.toLowerCase())
    )
    setTempFilter(filtered)
  }

  const clearAll = () => {
    setTempFilter([])
  }

  const isFiltered = (col) => {
    const f = filters[col]
    if (!f) return false
    if (Array.isArray(f)) return f.length > 0
    return (f.min !== '' && f.min !== null) || (f.max !== '' && f.max !== null)
  }

  const activeFilterCount = Object.keys(filters).filter(isFiltered).length

  const formatNumber = (num) => {
    if (num === undefined || num === null) return '-'
    if (Math.abs(num) >= 1000000) return (num / 1000000).toFixed(2) + 'M'
    if (Math.abs(num) >= 1000) return (num / 1000).toFixed(2) + 'K'
    return Number.isInteger(num) ? num.toString() : num.toFixed(2)
  }

  const containerClass = `dataframe-container ${isFullscreen ? 'fullscreen' : ''}`

  return (
    <div className={containerClass} ref={containerRef}>
      {/* Toolbar */}
      <div className="dataframe-toolbar">
        <button
          className="toolbar-btn"
          onClick={() => setIsFullscreen(!isFullscreen)}
          title={isFullscreen ? 'Exit fullscreen (Esc)' : 'Fullscreen'}
        >
          {isFullscreen ? (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M5.5 0a.5.5 0 0 1 .5.5v4A1.5 1.5 0 0 1 4.5 6h-4a.5.5 0 0 1 0-1h4a.5.5 0 0 0 .5-.5v-4a.5.5 0 0 1 .5-.5zm5 0a.5.5 0 0 1 .5.5v4a.5.5 0 0 0 .5.5h4a.5.5 0 0 1 0 1h-4A1.5 1.5 0 0 1 10 4.5v-4a.5.5 0 0 1 .5-.5zM0 10.5a.5.5 0 0 1 .5-.5h4A1.5 1.5 0 0 1 6 11.5v4a.5.5 0 0 1-1 0v-4a.5.5 0 0 0-.5-.5h-4a.5.5 0 0 1-.5-.5zm10 0a.5.5 0 0 1 .5-.5h4a.5.5 0 0 1 0 1h-4a.5.5 0 0 0-.5.5v4a.5.5 0 0 1-1 0v-4z"/>
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M1.5 1a.5.5 0 0 0-.5.5v4a.5.5 0 0 1-1 0v-4A1.5 1.5 0 0 1 1.5 0h4a.5.5 0 0 1 0 1h-4zM10 .5a.5.5 0 0 1 .5-.5h4A1.5 1.5 0 0 1 16 1.5v4a.5.5 0 0 1-1 0v-4a.5.5 0 0 0-.5-.5h-4a.5.5 0 0 1-.5-.5zM.5 10a.5.5 0 0 1 .5.5v4a.5.5 0 0 0 .5.5h4a.5.5 0 0 1 0 1h-4A1.5 1.5 0 0 1 0 14.5v-4a.5.5 0 0 1 .5-.5zm15 0a.5.5 0 0 1 .5.5v4a1.5 1.5 0 0 1-1.5 1.5h-4a.5.5 0 0 1 0-1h4a.5.5 0 0 0 .5-.5v-4a.5.5 0 0 1 .5-.5z"/>
            </svg>
          )}
        </button>
        <button
          className="toolbar-btn"
          onClick={copySelection}
          disabled={!selection}
          title="Copy selection (Ctrl+C)"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"/>
            <path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"/>
          </svg>
        </button>
        <span className="toolbar-info">
          {rows.length}{totalRows > rows.length ? ` of ${totalRows}` : ''} rows × {content.columns.length} cols
          {activeFilterCount > 0 && ` • ${activeFilterCount} filter${activeFilterCount > 1 ? 's' : ''}`}
          {isLoadingMore && ' • Loading...'}
        </span>
      </div>

      {/* Table Header */}
      <div className="dataframe-header-container" ref={headerRef}>
        <table className="dataframe-table dataframe-header-table" ref={tableRef}>
          <thead>
            <tr>
              <th className="row-number-header">#</th>
              {content.columns.map((col, colIdx) => {
                const filtered = isFiltered(col)
                const isSorted = sortConfig.column === col
                const width = columnWidths[col]
                return (
                  <th
                    key={col}
                    className="filterable-header"
                    style={width ? { width: width, minWidth: width } : undefined}
                  >
                    <div className="header-content" onClick={() => handleSort(col)}>
                      <span className="header-text">{col}</span>
                      <span className="header-icons">
                        {isSorted && (
                          <span className="sort-indicator">
                            {sortConfig.direction === 'asc' ? '↑' : '↓'}
                          </span>
                        )}
                        <button
                          ref={el => filterButtonRefs.current[col] = el}
                          className={`filter-btn ${filtered ? 'active' : ''}`}
                          onClick={(e) => toggleFilter(col, e)}
                          title="Filter"
                        >
                          <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                            <path d="M1.5 1.5A.5.5 0 0 1 2 1h12a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-.128.334L10 8.692V13.5a.5.5 0 0 1-.342.474l-3 1A.5.5 0 0 1 6 14.5V8.692L1.628 3.834A.5.5 0 0 1 1.5 3.5v-2z"/>
                          </svg>
                        </button>
                      </span>
                    </div>
                    <div
                      className="resize-handle"
                      onMouseDown={(e) => handleResizeStart(col, e)}
                    />
                  </th>
                )
              })}
            </tr>
          </thead>
        </table>
      </div>

      {/* Virtual scrolling table body */}
      <div className="dataframe-body-container" onScroll={handleBodyScroll}>
        <List
          listRef={listRef}
          defaultHeight={containerHeight}
          rowCount={rows.length}
          rowHeight={ROW_HEIGHT}
          overscanCount={10}
          rowComponent={VirtualRow}
          rowProps={{
            rows,
            columns: content.columns,
            columnWidths,
            isCellSelected,
            handleCellMouseDown,
            handleCellMouseEnter
          }}
          onItemsRendered={handleItemsRendered}
          style={{ overflowX: 'auto', height: containerHeight }}
        />
      </div>

      {/* Status bar */}
      <div className="dataframe-statusbar">
        <span className="status-left">
          {selection ? (
            `Selected: ${Math.abs(selection.endRow - selection.startRow) + 1} × ${Math.abs(selection.endCol - selection.startCol) + 1} cells`
          ) : (
            `Click and drag to select cells`
          )}
        </span>
        {selectionStats && selectionStats.numericCount > 0 && (
          <span className="status-right">
            <span className="stat">Count: {selectionStats.numericCount}</span>
            <span className="stat">Sum: {formatNumber(selectionStats.sum)}</span>
            <span className="stat">Avg: {formatNumber(selectionStats.average)}</span>
            <span className="stat">Min: {formatNumber(selectionStats.min)}</span>
            <span className="stat">Max: {formatNumber(selectionStats.max)}</span>
          </span>
        )}
      </div>

      {/* Filter dropdown portal */}
      {activeFilter && createPortal(
        <div
          ref={dropdownRef}
          className="filter-dropdown"
          style={{ left: dropdownPosition.x, top: dropdownPosition.y }}
          onClick={e => e.stopPropagation()}
        >
          {columnInfo[activeFilter]?.type === 'numeric' ? (
            <div className="numeric-filter">
              <div className="filter-row">
                <label>Min:</label>
                <input
                  type="number"
                  value={tempFilter.min || ''}
                  onChange={e => setTempFilter(prev => ({ ...prev, min: e.target.value }))}
                  placeholder={String(columnInfo[activeFilter]?.min ?? '')}
                />
              </div>
              <div className="filter-row">
                <label>Max:</label>
                <input
                  type="number"
                  value={tempFilter.max || ''}
                  onChange={e => setTempFilter(prev => ({ ...prev, max: e.target.value }))}
                  placeholder={String(columnInfo[activeFilter]?.max ?? '')}
                />
              </div>
            </div>
          ) : (
            <div className="categorical-filter">
              <input
                type="text"
                className="filter-search"
                placeholder="Search..."
                value={filterSearch}
                onChange={e => setFilterSearch(e.target.value)}
              />
              <div className="select-actions">
                <button onClick={() => selectAll(activeFilter)}>Select All</button>
                <button onClick={clearAll}>Clear All</button>
              </div>
              <div className="filter-values">
                {columnInfo[activeFilter]?.values
                  ?.filter(v => filterSearch === '' || String(v).toLowerCase().includes(filterSearch.toLowerCase()))
                  .slice(0, 100)
                  .map((val, idx) => (
                    <label key={idx} className="filter-checkbox">
                      <input
                        type="checkbox"
                        checked={Array.isArray(tempFilter) && tempFilter.includes(val)}
                        onChange={() => toggleValue(val)}
                      />
                      <span>{String(val)}</span>
                    </label>
                  ))}
              </div>
            </div>
          )}
          <div className="filter-actions">
            <button className="clear-btn" onClick={() => clearFilter(activeFilter)}>Clear</button>
            <button className="apply-btn" onClick={() => applyFilter(activeFilter)}>Apply</button>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

export default DataFrameViewer
