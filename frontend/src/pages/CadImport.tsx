/**
 * CadImport: Main page for importing 3D CAD files (STEP/IGES).
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────┐
 *   │  Upload area / Processing progress                   │
 *   ├──────────────────────┬───────────────────────────────┤
 *   │                      │                               │
 *   │  2D Sketch View      │  Building Blocks + Controls   │
 *   │  (left, ~60%)        │  (right, ~40%)                │
 *   │                      │                               │
 *   ├──────────────────────┴───────────────────────────────┤
 *   │  Validation bar + "Send to Simulator"                │
 *   └──────────────────────────────────────────────────────┘
 */

import { useCallback, useRef, useEffect } from 'react'
import { useCadImportStore } from './CadImportStore'
import { SketchView } from './cad/SketchView'
import { BlockList } from './cad/BlockList'
import { ManualPlacement } from './cad/ManualPlacement'
import { ValidationBar } from './cad/Validation'
import { analyzeTopology } from './cad/GeometryAnalyzer'
import { computeResistances } from './cad/NetworkDeriver'
import type { ParsedTopology } from './cad/StepParser.worker'
import { useStore } from '../store'

// ── File processing pipeline ───────────────────────────────────────────────

function useProcessFile() {
  const workerRef = useRef<Worker | null>(null)
  const {
    setStage, setProgress, setError, setAnalysis, viscosity,
  } = useCadImportStore()

  // Initialize worker lazily
  const getWorker = useCallback(() => {
    if (!workerRef.current) {
      workerRef.current = new Worker(
        new URL('./cad/StepParser.worker.ts', import.meta.url),
        { type: 'module' },
      )
    }
    return workerRef.current
  }, [])

  // Cleanup worker on unmount
  useEffect(() => {
    return () => {
      workerRef.current?.terminate()
      workerRef.current = null
    }
  }, [])

  const processFile = useCallback((fileName: string, data: ArrayBuffer) => {
    setStage('parsing', 0)

    const worker = getWorker()

    worker.onmessage = (event: MessageEvent) => {
      const msg = event.data

      if (msg.type === 'progress') {
        setProgress(msg.percent)
      } else if (msg.type === 'result') {
        setStage('analyzing', 60)
        try {
          const topology = msg.topology as ParsedTopology
          // 2.5D → 2D analysis
          let analysis = analyzeTopology(topology)
          // Compute resistances
          analysis = computeResistances(analysis, viscosity)
          setAnalysis(analysis)
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Analysis failed')
        }
      } else if (msg.type === 'error') {
        setError(msg.message)
      }
    }

    worker.onerror = (err) => {
      setError(`Worker error: ${err.message}`)
    }

    worker.postMessage({ type: 'parse', fileName, data })
  }, [getWorker, setStage, setProgress, setError, setAnalysis, viscosity])

  return processFile
}

// ── Upload area ────────────────────────────────────────────────────────────

function UploadArea() {
  const loadFile = useCadImportStore(s => s.loadFile)
  const processFile = useProcessFile()

  const handleFile = useCallback((file: File) => {
    const ext = file.name.toLowerCase().split('.').pop() ?? ''
    if (!['step', 'stp', 'iges', 'igs'].includes(ext)) {
      useCadImportStore.getState().setError(`Unsupported format: .${ext} — use .step/.stp or .iges/.igs`)
      return
    }

    const reader = new FileReader()
    reader.onload = () => {
      const data = reader.result as ArrayBuffer
      loadFile(file.name, data)
      processFile(file.name, data)
    }
    reader.onerror = () => {
      useCadImportStore.getState().setError('Failed to read file')
    }
    reader.readAsArrayBuffer(file)
  }, [loadFile, processFile])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      className="flex-1 flex flex-col items-center justify-center gap-4 p-8"
    >
      <div className="w-20 h-20 rounded-2xl bg-slate-100 border-2 border-dashed border-slate-300 flex items-center justify-center text-3xl text-slate-400">
        ⬡
      </div>

      <div className="text-center">
        <h2 className="text-lg font-semibold text-slate-700 mb-1">Import 3D CAD File</h2>
        <p className="text-sm text-slate-400 mb-4">
          Drag & drop a STEP (.step, .stp) or IGES (.iges, .igs) file
        </p>
        <label className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium cursor-pointer shadow-sm transition-colors">
          <span>Choose File</span>
          <input
            type="file"
            accept=".step,.stp,.iges,.igs"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleFile(file)
              e.target.value = ''
            }}
          />
        </label>
      </div>

      <div className="text-xs text-slate-300 mt-4">
        Supported: STEP (AP203/AP214), IGES · Parsed locally via OpenCascade WASM
      </div>
    </div>
  )
}

// ── Processing indicator ───────────────────────────────────────────────────

function ProcessingView() {
  const stage = useCadImportStore(s => s.stage)
  const progress = useCadImportStore(s => s.progress)
  const fileName = useCadImportStore(s => s.fileName)

  const stageLabels: Record<string, string> = {
    loading: 'Reading file…',
    parsing: 'Parsing STEP/IGES geometry (OpenCascade WASM)…',
    analyzing: 'Extracting 2D features from 3D geometry…',
    deriving: 'Building 1D network model…',
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 p-8">
      <div className="w-16 h-16 rounded-full bg-blue-50 border-2 border-blue-200 flex items-center justify-center">
        <span className="text-2xl animate-spin">⟳</span>
      </div>

      <div className="text-center">
        <div className="text-sm font-medium text-slate-700 mb-1">
          {stageLabels[stage] ?? 'Processing…'}
        </div>
        <div className="text-xs text-slate-400">{fileName}</div>
      </div>

      {/* Progress bar */}
      <div className="w-64 h-2 bg-slate-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="text-xs text-slate-400">{progress}%</div>
    </div>
  )
}

// ── Error view ─────────────────────────────────────────────────────────────

function ErrorView() {
  const errorMessage = useCadImportStore(s => s.errorMessage)
  const clearAll = useCadImportStore(s => s.clearAll)

  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 p-8">
      <div className="w-16 h-16 rounded-full bg-red-50 border-2 border-red-200 flex items-center justify-center text-2xl">
        ✕
      </div>

      <div className="text-center max-w-md">
        <div className="text-sm font-medium text-red-700 mb-1">Import Failed</div>
        <div className="text-xs text-red-500 bg-red-50 border border-red-200 rounded-lg p-3 mt-2">
          {errorMessage}
        </div>
      </div>

      <button
        onClick={clearAll}
        className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-sm text-slate-600 transition-colors"
      >
        Try Again
      </button>
    </div>
  )
}

// ── Review view (split layout) ─────────────────────────────────────────────

function ReviewView() {
  const clearAll = useCadImportStore(s => s.clearAll)
  const fileName = useCadImportStore(s => s.fileName)
  const toSimulatorData = useCadImportStore(s => s.toSimulatorData)
  const showDimensions = useCadImportStore(s => s.showDimensions)
  const showHeightColors = useCadImportStore(s => s.showHeightColors)
  const toggleDimensions = useCadImportStore(s => s.toggleDimensions)
  const toggleHeightColors = useCadImportStore(s => s.toggleHeightColors)
  const viscosity = useCadImportStore(s => s.viscosity)
  const setViscosity = useCadImportStore(s => s.setViscosity)

  const handleSendToSimulator = useCallback(() => {
    const { nodes, edges } = toSimulatorData()

    // Push into simulator store
    useStore.setState(s => ({
      nodes: [...s.nodes, ...nodes],
      edges: [...s.edges, ...edges],
    }))

    // Clear CAD import
    clearAll()
  }, [toSimulatorData, clearAll])

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-white border-b border-slate-200 shrink-0">
        <span className="text-xs text-slate-500 truncate max-w-[200px]" title={fileName ?? ''}>
          {fileName}
        </span>

        <div className="flex items-center gap-1.5 ml-2">
          <ToggleButton
            active={showDimensions}
            onClick={toggleDimensions}
            label="Dimensions"
          />
          <ToggleButton
            active={showHeightColors}
            onClick={toggleHeightColors}
            label="Height Colors"
          />
        </div>

        {/* Viscosity */}
        <div className="flex items-center gap-1.5 ml-3 text-xs text-slate-500">
          <label>η:</label>
          <input
            type="number"
            value={viscosity * 1000} // display in mPa·s
            onChange={(e) => {
              const v = parseFloat(e.target.value)
              if (!isNaN(v) && v > 0) setViscosity(v / 1000)
            }}
            className="w-16 px-1.5 py-0.5 rounded border border-slate-200 text-xs font-mono
                       focus:outline-none focus:ring-1 focus:ring-blue-400"
            step={0.1}
          />
          <span className="text-slate-400">mPa·s</span>
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <button
            onClick={clearAll}
            className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            Close
          </button>
          <button
            onClick={handleSendToSimulator}
            className="px-4 py-1.5 rounded-lg text-xs font-medium bg-blue-500 hover:bg-blue-600 text-white shadow-sm transition-colors"
          >
            Send to Simulator →
          </button>
        </div>
      </div>

      {/* Split view */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Sketch */}
        <div className="flex-[3] border-r border-slate-200 flex flex-col">
          <SketchView />
        </div>

        {/* Right: Blocks + Controls */}
        <div className="flex-[2] flex flex-col bg-white overflow-hidden min-w-[280px] max-w-[400px]">
          <div className="flex-1 overflow-y-auto">
            <BlockList />
          </div>

          {/* Manual placement section */}
          <div className="border-t border-slate-200 p-3 shrink-0">
            <ManualPlacement />
          </div>
        </div>
      </div>

      {/* Validation */}
      <ValidationBar />
    </div>
  )
}

// ── Toggle button ──────────────────────────────────────────────────────────

function ToggleButton({ active, onClick, label }: {
  active: boolean
  onClick: () => void
  label: string
}) {
  return (
    <button
      onClick={onClick}
      className={`
        px-2.5 py-1 rounded text-xs font-medium transition-all
        ${active
          ? 'bg-blue-50 text-blue-600 border border-blue-200'
          : 'bg-slate-50 text-slate-400 border border-slate-200 hover:text-slate-600'
        }
      `}
    >
      {label}
    </button>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────

export function CadImportPage() {
  const stage = useCadImportStore(s => s.stage)

  if (stage === 'idle') {
    return <UploadArea />
  }

  if (stage === 'error') {
    return <ErrorView />
  }

  if (stage === 'review') {
    return <ReviewView />
  }

  // loading / parsing / analyzing / deriving
  return <ProcessingView />
}
