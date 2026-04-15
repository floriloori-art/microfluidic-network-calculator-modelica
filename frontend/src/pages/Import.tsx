import { useCallback, useEffect, useRef, useState, type DragEvent, type ChangeEvent } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import { BUILTIN_PALETTE_ITEMS, KIND_META } from '../palette'
import { type ElementKind, type PaletteItem } from '../types'
import {
  useImportStore, genImportId,
  type PlacedElement, type ScaleState,
} from './ImportStore'
import { useStore } from '../store'

// pdf.js worker — served from public/ directory
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'


// ── PDF Canvas ──────────────────────────────────────────────────────────────

function PdfCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const {
    pdfFile, currentPage, scale, umPerPx,
    elements, connections, selectedElementId,
    placingKind, showPdf, showGrid, showOverlay,
    setScalePoint, addElement, selectElement,
  } = useImportStore()

  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null)
  const [canvasSize, setCanvasSize] = useState({ w: 0, h: 0 })
  // Force overlay redraws when store changes
  const [overlayTick, setOverlayTick] = useState(0)
  useEffect(() => {
    const unsub = useImportStore.subscribe(() => setOverlayTick(t => t + 1))
    return unsub
  }, [])

  // Load PDF document
  useEffect(() => {
    if (!pdfFile) { setPdfDoc(null); return }
    const url = URL.createObjectURL(pdfFile)
    pdfjsLib.getDocument(url).promise.then(doc => {
      setPdfDoc(doc)
    }).catch(err => console.error('PDF load error:', err))
    return () => URL.revokeObjectURL(url)
  }, [pdfFile])

  // Render PDF page
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return
    pdfDoc.getPage(currentPage).then(page => {
      const viewport = page.getViewport({ scale: 1.5 })
      const canvas = canvasRef.current!
      canvas.width = viewport.width
      canvas.height = viewport.height
      setCanvasSize({ w: viewport.width, h: viewport.height })

      const ctx = canvas.getContext('2d')!
      if (!showPdf) {
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        ctx.fillStyle = '#f8fafc'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
        return
      }
      page.render({ canvasContext: ctx, viewport }).promise
    })
  }, [pdfDoc, currentPage, showPdf])

  // Draw overlay (elements, connections, scale line, grid)
  useEffect(() => {
    const ov = overlayRef.current
    if (!ov || canvasSize.w === 0) return
    ov.width = canvasSize.w
    ov.height = canvasSize.h
    const ctx = ov.getContext('2d')!
    ctx.clearRect(0, 0, ov.width, ov.height)

    // Grid
    if (showGrid) {
      ctx.strokeStyle = 'rgba(148,163,184,0.2)'
      ctx.lineWidth = 0.5
      for (let x = 0; x < ov.width; x += 40) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, ov.height); ctx.stroke()
      }
      for (let y = 0; y < ov.height; y += 40) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(ov.width, y); ctx.stroke()
      }
    }

    if (!showOverlay) return

    // Scale calibration line
    if (scale.mode === 'picking_p2' || scale.mode === 'done') {
      const p1 = scale.p1
      const p2 = scale.mode === 'done' ? scale.p2 : null
      ctx.strokeStyle = '#ef4444'
      ctx.lineWidth = 2
      ctx.setLineDash([6, 4])
      ctx.beginPath()
      ctx.arc(p1.x, p1.y, 5, 0, Math.PI * 2)
      ctx.stroke()
      if (p2) {
        ctx.beginPath()
        ctx.moveTo(p1.x, p1.y)
        ctx.lineTo(p2.x, p2.y)
        ctx.stroke()
        ctx.beginPath()
        ctx.arc(p2.x, p2.y, 5, 0, Math.PI * 2)
        ctx.stroke()
      }
      ctx.setLineDash([])
    }

    // Connections
    for (const conn of connections) {
      const src = elements.find(e => e.id === conn.sourceId)
      const tgt = elements.find(e => e.id === conn.targetId)
      if (!src || !tgt) continue
      ctx.strokeStyle = '#94a3b8'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(src.x, src.y)
      ctx.lineTo(tgt.x, tgt.y)
      ctx.stroke()
      // Arrow
      const angle = Math.atan2(tgt.y - src.y, tgt.x - src.x)
      const ax = tgt.x - 15 * Math.cos(angle)
      const ay = tgt.y - 15 * Math.sin(angle)
      ctx.beginPath()
      ctx.moveTo(tgt.x, tgt.y)
      ctx.lineTo(ax - 6 * Math.cos(angle - 0.5), ay - 6 * Math.sin(angle - 0.5))
      ctx.lineTo(ax - 6 * Math.cos(angle + 0.5), ay - 6 * Math.sin(angle + 0.5))
      ctx.closePath()
      ctx.fillStyle = '#94a3b8'
      ctx.fill()
    }

    // Elements
    for (const el of elements) {
      const meta = KIND_META[el.kind] ?? { color: '#94a3b8', icon: '?', label: el.kind }
      const isSelected = el.id === selectedElementId

      // Node circle
      ctx.beginPath()
      ctx.arc(el.x, el.y, 18, 0, Math.PI * 2)
      ctx.fillStyle = '#ffffff'
      ctx.fill()
      ctx.strokeStyle = isSelected ? '#3b82f6' : meta.color
      ctx.lineWidth = isSelected ? 3 : 2
      ctx.stroke()

      // Icon
      ctx.fillStyle = meta.color
      ctx.font = '16px system-ui'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(meta.icon, el.x, el.y)

      // Label below
      ctx.fillStyle = '#334155'
      ctx.font = '11px system-ui'
      ctx.fillText(el.label, el.x, el.y + 30)
    }
  }, [canvasSize, elements, connections, selectedElementId, scale, showGrid, showOverlay, overlayTick])

  // Click handler
  const handleCanvasClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = overlayRef.current?.getBoundingClientRect()
    if (!rect) return
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    // Scale calibration mode
    if (scale.mode === 'picking_p1' || scale.mode === 'picking_p2') {
      setScalePoint(x, y)
      return
    }

    // Placing an element
    if (placingKind) {
      const meta = KIND_META[placingKind] ?? { label: placingKind }
      const id = genImportId(placingKind)
      const newEl: PlacedElement = {
        id,
        kind: placingKind,
        label: `${meta.label} ${id.split('_').pop()}`,
        x, y,
        params: { ...(BUILTIN_PALETTE_ITEMS.find(p => p.kind === placingKind)?.defaultParams ?? {}) } as Record<string, number>,
      }
      addElement(newEl)
      return
    }

    // Select existing element
    const clicked = elements.find(el => {
      const dx = el.x - x
      const dy = el.y - y
      return dx * dx + dy * dy < 22 * 22
    })
    selectElement(clicked?.id ?? null)
  }, [scale, placingKind, elements, setScalePoint, addElement, selectElement])

  if (!pdfFile) return null

  return (
    <div ref={containerRef} className="flex-1 relative overflow-auto bg-slate-100">
      <div className="relative inline-block">
        <canvas
          ref={canvasRef}
          className="block"
          style={{ imageRendering: 'auto' }}
        />
        <canvas
          ref={overlayRef}
          onClick={handleCanvasClick}
          className="absolute top-0 left-0 cursor-crosshair"
          style={{ imageRendering: 'auto' }}
        />
      </div>
    </div>
  )
}

// ── Upload Area ─────────────────────────────────────────────────────────────

function UploadArea() {
  const { setPdf } = useImportStore()
  const [dragging, setDragging] = useState(false)

  const handleFile = useCallback(async (file: File) => {
    if (file.type !== 'application/pdf') return
    const url = URL.createObjectURL(file)
    try {
      const doc = await pdfjsLib.getDocument(url).promise
      setPdf(file, doc.numPages)
      doc.destroy()
    } catch (err) {
      console.error('PDF load error:', err)
    }
    URL.revokeObjectURL(url)
  }, [setPdf])

  const onDrop = useCallback((e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const onFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  return (
    <div className="flex-1 flex items-center justify-center bg-slate-50">
      <div
        onDrop={onDrop}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        className={`
          w-96 h-64 border-2 border-dashed rounded-2xl flex flex-col items-center justify-center gap-4
          transition-colors cursor-pointer
          ${dragging ? 'border-blue-400 bg-blue-50' : 'border-slate-300 hover:border-blue-300 hover:bg-slate-50'}
        `}
        onClick={() => document.getElementById('pdf-file-input')?.click()}
      >
        <div className="text-5xl text-slate-300">📄</div>
        <div className="text-slate-500 text-sm font-medium">
          Drop a PDF here or click to browse
        </div>
        <div className="text-slate-400 text-xs">
          Technical drawings, CAD exports, chip layouts
        </div>
        <input
          id="pdf-file-input"
          type="file"
          accept="application/pdf"
          onChange={onFileInput}
          className="hidden"
        />
      </div>
    </div>
  )
}

// ── Left Panel: Layers + Palette ────────────────────────────────────────────

function ImportSidebar() {
  const {
    pdfFile, pdfPageCount, currentPage, setPage,
    scale, umPerPx, placingKind,
    showPdf, showGrid, showOverlay,
    startScaleCalibration, clearScale, toggleLayer, setPlacingKind,
  } = useImportStore()

  if (!pdfFile) return null

  const IMPORT_PALETTE: PaletteItem[] = BUILTIN_PALETTE_ITEMS.filter(p =>
    ['circular_channel', 'rectangular_channel', 'chamber', 'pump', 'valve',
     'pressure_source', 'pressure_ground', 'open_end', 'flow_source', 'check_valve',
    ].includes(p.kind)
  )

  return (
    <aside className="w-52 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
      {/* Pages */}
      {pdfPageCount > 1 && (
        <div className="px-4 pt-3 pb-2 border-b border-slate-200">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">Page</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, currentPage - 1))}
              disabled={currentPage <= 1}
              className="px-2 py-0.5 text-xs rounded border border-slate-200 hover:bg-slate-50 disabled:opacity-40"
            >
              ←
            </button>
            <span className="text-xs text-slate-600">{currentPage} / {pdfPageCount}</span>
            <button
              onClick={() => setPage(Math.min(pdfPageCount, currentPage + 1))}
              disabled={currentPage >= pdfPageCount}
              className="px-2 py-0.5 text-xs rounded border border-slate-200 hover:bg-slate-50 disabled:opacity-40"
            >
              →
            </button>
          </div>
        </div>
      )}

      {/* Layers */}
      <div className="px-4 pt-3 pb-2 border-b border-slate-200">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">Layers</h2>
        {(['showPdf', 'showGrid', 'showOverlay'] as const).map(layer => (
          <label key={layer} className="flex items-center gap-2 text-xs text-slate-600 py-0.5 cursor-pointer">
            <input
              type="checkbox"
              checked={useImportStore.getState()[layer]}
              onChange={() => toggleLayer(layer)}
              className="accent-blue-500"
            />
            {layer === 'showPdf' ? 'PDF Drawing' : layer === 'showGrid' ? 'Grid' : 'Overlay'}
          </label>
        ))}
      </div>

      {/* Scale */}
      <div className="px-4 pt-3 pb-2 border-b border-slate-200">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">Scale</h2>
        {scale.mode === 'none' && (
          <button
            onClick={startScaleCalibration}
            className="w-full text-xs text-blue-600 hover:bg-blue-50 border border-blue-200 rounded px-2 py-1.5 transition-colors"
          >
            📏 Set Scale
          </button>
        )}
        {scale.mode === 'picking_p1' && (
          <div className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
            Click first point on a known dimension
          </div>
        )}
        {scale.mode === 'picking_p2' && (
          <div className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
            Click second point
          </div>
        )}
        {scale.mode === 'done' && <ScaleInput />}
        {umPerPx && (
          <div className="text-[10px] text-emerald-600 bg-emerald-50 border border-emerald-200 rounded px-2 py-1.5 mt-2">
            Scale: 1 px = {umPerPx.toFixed(2)} µm
          </div>
        )}
        {scale.mode !== 'none' && (
          <button
            onClick={clearScale}
            className="w-full text-[10px] text-slate-400 hover:text-slate-600 mt-1"
          >
            Reset scale
          </button>
        )}
      </div>

      {/* Element palette */}
      <div className="px-4 pt-3 pb-2">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">Place Element</h2>
        <p className="text-[10px] text-slate-400 mb-2">Click to select, then click on PDF</p>
        <div className="flex flex-col gap-1">
          {IMPORT_PALETTE.map(item => (
            <button
              key={item.kind}
              onClick={() => setPlacingKind(placingKind === item.kind ? null : item.kind)}
              style={{ borderColor: placingKind === item.kind ? item.color : undefined }}
              className={`
                flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-left transition-all
                ${placingKind === item.kind
                  ? 'bg-blue-50 border-2 font-medium text-slate-700'
                  : 'border border-slate-200 text-slate-600 hover:bg-slate-50'}
              `}
            >
              <span style={{ color: item.color }} className="text-base leading-none">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </aside>
  )
}

// ── Scale distance input ────────────────────────────────────────────────────

function ScaleInput() {
  const { scale, confirmScale } = useImportStore()
  const [value, setValue] = useState('')

  if (scale.mode !== 'done') return null

  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-xs text-slate-500">
        Line: {scale.pxDistance.toFixed(1)} px
      </div>
      <div className="flex gap-1">
        <input
          type="number"
          value={value}
          onChange={e => setValue(e.target.value)}
          placeholder="Distance"
          className="flex-1 bg-white border border-slate-200 rounded px-2 py-1 text-xs font-mono focus:outline-none focus:border-blue-400"
        />
        <span className="text-xs text-slate-400 self-center">µm</span>
      </div>
      <button
        onClick={() => {
          const v = parseFloat(value)
          if (v > 0) confirmScale(v)
        }}
        disabled={!value || parseFloat(value) <= 0}
        className="text-xs bg-blue-500 hover:bg-blue-600 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded px-2 py-1 transition-colors"
      >
        Confirm
      </button>
    </div>
  )
}

// ── Right Panel: Element Details + Connections ──────────────────────────────

function ImportDetailsPanel() {
  const {
    elements, connections, selectedElementId,
    updateElement, removeElement, addConnection, removeConnection,
  } = useImportStore()

  const selectedEl = elements.find(e => e.id === selectedElementId)

  // Connection mode state
  const [connectingFrom, setConnectingFrom] = useState<string | null>(null)

  if (!useImportStore.getState().pdfFile) return null

  return (
    <aside className="w-56 bg-white border-l border-slate-200 flex flex-col">
      {/* Element details */}
      {selectedEl ? (
        <>
          <div className="border-b border-slate-200 px-4 py-3">
            <div className="text-xs font-semibold text-slate-700">{selectedEl.label}</div>
            <div className="text-[10px] text-slate-400">{selectedEl.id}</div>
          </div>

          <div className="flex flex-col gap-2 p-4 flex-1 overflow-y-auto">
            {/* Label */}
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-500">Label</label>
              <input
                type="text"
                value={selectedEl.label}
                onChange={e => updateElement(selectedEl.id, { label: e.target.value })}
                className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-400"
              />
            </div>

            {/* Parameters */}
            {Object.entries(selectedEl.params).map(([key, val]) => (
              <div key={key} className="flex flex-col gap-1">
                <label className="text-xs text-slate-500">{key}</label>
                <input
                  type="number"
                  value={val}
                  step="any"
                  onChange={e => updateElement(selectedEl.id, {
                    params: { ...selectedEl.params, [key]: parseFloat(e.target.value) || 0 },
                  })}
                  className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs font-mono focus:outline-none focus:border-blue-400"
                />
              </div>
            ))}

            {/* Connect button */}
            <div className="mt-2">
              {connectingFrom === null ? (
                <button
                  onClick={() => setConnectingFrom(selectedEl.id)}
                  className="w-full text-xs text-blue-600 hover:bg-blue-50 border border-blue-200 rounded px-2 py-1.5 transition-colors"
                >
                  🔗 Connect to...
                </button>
              ) : connectingFrom === selectedEl.id ? (
                <div className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
                  Now select target element
                  <button onClick={() => setConnectingFrom(null)} className="ml-2 text-slate-400 hover:text-slate-600">✕</button>
                </div>
              ) : (
                <button
                  onClick={() => {
                    addConnection(connectingFrom, selectedEl.id)
                    setConnectingFrom(null)
                  }}
                  className="w-full text-xs text-emerald-600 hover:bg-emerald-50 border border-emerald-200 rounded px-2 py-1.5 transition-colors"
                >
                  ✓ Connect from {elements.find(e => e.id === connectingFrom)?.label}
                </button>
              )}
            </div>

            {/* Delete */}
            <button
              onClick={() => removeElement(selectedEl.id)}
              className="w-full text-xs text-red-500 hover:bg-red-50 border border-red-200 rounded px-2 py-1.5 mt-2 transition-colors"
            >
              Delete element
            </button>
          </div>
        </>
      ) : (
        <div className="p-4 text-center text-sm text-slate-400">
          <div className="text-3xl mb-2">↖</div>
          Select an element<br />to edit
        </div>
      )}

      {/* Connections list */}
      {connections.length > 0 && (
        <div className="border-t border-slate-200 p-3">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">Connections</h3>
          {connections.map(c => {
            const src = elements.find(e => e.id === c.sourceId)
            const tgt = elements.find(e => e.id === c.targetId)
            return (
              <div key={c.id} className="flex items-center justify-between text-[10px] text-slate-500 py-0.5">
                <span>{src?.label ?? '?'} → {tgt?.label ?? '?'}</span>
                <button
                  onClick={() => removeConnection(c.id)}
                  className="text-red-400 hover:text-red-600"
                >✕</button>
              </div>
            )
          })}
        </div>
      )}
    </aside>
  )
}

// ── Import Toolbar ──────────────────────────────────────────────────────────

function ImportToolbar() {
  const { pdfFile, clearPdf, elements, connections } = useImportStore()
  const { clearAll: clearSim, addNode, addEdges } = useStore()

  const canSend = elements.length >= 2 && connections.length >= 1

  const handleSendToSimulator = () => {
    const { nodes, edges } = useImportStore.getState().toSimulatorData()
    clearSim()
    nodes.forEach(n => addNode(n))
    addEdges(edges)
  }

  if (!pdfFile) return null

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-white border-b border-slate-200">
      <span className="text-blue-500 text-lg">📄</span>
      <span className="text-sm font-semibold text-slate-700 truncate max-w-48">
        {pdfFile.name}
      </span>

      <button
        onClick={clearPdf}
        className="text-xs text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded px-3 py-1.5 transition-colors"
      >
        Close PDF
      </button>

      <div className="flex-1" />

      <span className="text-xs text-slate-400">
        {elements.length} elements · {connections.length} connections
      </span>

      <button
        onClick={handleSendToSimulator}
        disabled={!canSend}
        className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-200 disabled:text-slate-400 text-white transition-colors shadow-sm"
      >
        → Send to Simulator
      </button>
    </div>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────

export function ImportPage() {
  const { pdfFile } = useImportStore()

  return (
    <>
      <ImportToolbar />
      <div className="flex flex-1 overflow-hidden">
        {pdfFile ? (
          <>
            <ImportSidebar />
            <PdfCanvas />
            <ImportDetailsPanel />
          </>
        ) : (
          <UploadArea />
        )}
      </div>
    </>
  )
}
