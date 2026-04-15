import { create } from 'zustand'
import type { Node, Edge } from '@xyflow/react'
import type { ElementKind, FluidNodeData } from '../types'

// ── Geometry types (output of STEP parsing + analysis) ─────────────────────

export interface Vec2 { x: number; y: number }
export interface Vec3 { x: number; y: number; z: number }

/** A channel segment extracted from 3D geometry */
export interface ExtractedChannel {
  id: string
  type: 'circular' | 'rectangular'
  /** Centerline start/end in 2D (µm) */
  start: Vec2
  end: Vec2
  /** Channel dimensions (µm) */
  radius?: number       // circular
  width?: number        // rectangular
  height: number        // channel depth (z-extent)
  length: number        // centerline length
  /** Computed resistance (Pa·s/m³) */
  resistance: number
}

/** A chamber extracted from 3D geometry */
export interface ExtractedChamber {
  id: string
  center: Vec2
  /** Bounding dimensions (µm) */
  widthX: number
  widthY: number
  height: number
  /** Approximate volume (µm³) */
  volume: number
}

/** A port (open end at chip boundary) */
export interface ExtractedPort {
  id: string
  position: Vec2
  label: string
  /** Connected channel ID */
  connectedTo: string
}

/** A junction where multiple channels meet */
export interface ExtractedJunction {
  id: string
  position: Vec2
  /** IDs of connected channels */
  channelIds: string[]
}

/** Manually placed active component */
export interface ManualComponent {
  id: string
  kind: ElementKind
  label: string
  position: Vec2
  /** On which channel or at which junction */
  attachedTo: string
  params: Record<string, number>
}

/** Complete 2D analysis result */
export interface AnalysisResult {
  channels: ExtractedChannel[]
  chambers: ExtractedChamber[]
  ports: ExtractedPort[]
  junctions: ExtractedJunction[]
  /** Bounding box of the 2D projection (µm) */
  bounds: { minX: number; minY: number; maxX: number; maxY: number }
  /** Height layers found in the geometry */
  heightLayers: { zMin: number; zMax: number; height: number; count: number }[]
  /** Unit from STEP file */
  unit: string
}

/** Validation issue */
export interface ValidationIssue {
  severity: 'error' | 'warning'
  message: string
}

// ── Processing stages ──────────────────────────────────────────────────────

export type ProcessingStage =
  | 'idle'
  | 'loading'        // reading file
  | 'parsing'        // opencascade.js parsing STEP/IGES
  | 'analyzing'      // 2.5D → 2D extraction
  | 'deriving'       // 2D → 1D network
  | 'review'         // user reviews in split view
  | 'error'

// ── Store ──────────────────────────────────────────────────────────────────

export interface CadImportState {
  // File
  fileName: string | null
  fileData: ArrayBuffer | null

  // Processing
  stage: ProcessingStage
  progress: number        // 0..100
  errorMessage: string | null

  // Analysis result
  analysis: AnalysisResult | null

  // Manual components (pumps, valves)
  manualComponents: ManualComponent[]

  // UI state
  selectedId: string | null           // selected channel/chamber/port/junction/manual
  hoveredId: string | null
  showDimensions: boolean
  showHeightColors: boolean
  placingComponentKind: ElementKind | null

  // Fluid properties (for resistance calculation)
  viscosity: number     // Pa·s (default water)
  density: number       // kg/m³

  // Actions
  loadFile: (name: string, data: ArrayBuffer) => void
  setStage: (stage: ProcessingStage, progress?: number) => void
  setProgress: (progress: number) => void
  setError: (message: string) => void
  setAnalysis: (result: AnalysisResult) => void
  clearAll: () => void

  setSelected: (id: string | null) => void
  setHovered: (id: string | null) => void
  toggleDimensions: () => void
  toggleHeightColors: () => void

  startPlacingComponent: (kind: ElementKind) => void
  cancelPlacing: () => void
  addManualComponent: (comp: ManualComponent) => void
  updateManualComponent: (id: string, updates: Partial<ManualComponent>) => void
  removeManualComponent: (id: string) => void

  setViscosity: (v: number) => void
  setDensity: (d: number) => void

  /** Update a channel's parameters (user correction) */
  updateChannel: (id: string, updates: Partial<ExtractedChannel>) => void
  /** Update a chamber's parameters */
  updateChamber: (id: string, updates: Partial<ExtractedChamber>) => void

  /** Build simulator-compatible nodes & edges */
  toSimulatorData: () => { nodes: Node<FluidNodeData>[]; edges: Edge[] }

  /** Run validation checks */
  validate: () => ValidationIssue[]
}

export const useCadImportStore = create<CadImportState>((set, get) => ({
  fileName: null,
  fileData: null,

  stage: 'idle',
  progress: 0,
  errorMessage: null,

  analysis: null,
  manualComponents: [],

  selectedId: null,
  hoveredId: null,
  showDimensions: true,
  showHeightColors: true,
  placingComponentKind: null,

  viscosity: 0.001,    // water at ~20°C
  density: 998.2,

  loadFile: (name, data) => set({
    fileName: name,
    fileData: data,
    stage: 'loading',
    progress: 0,
    errorMessage: null,
    analysis: null,
    manualComponents: [],
    selectedId: null,
  }),

  setStage: (stage, progress) => set({ stage, progress: progress ?? 0 }),
  setProgress: (progress) => set({ progress }),
  setError: (message) => set({ stage: 'error', errorMessage: message }),
  setAnalysis: (result) => set({ analysis: result, stage: 'review' }),
  clearAll: () => set({
    fileName: null, fileData: null, stage: 'idle', progress: 0,
    errorMessage: null, analysis: null, manualComponents: [],
    selectedId: null, hoveredId: null, placingComponentKind: null,
  }),

  setSelected: (id) => set({ selectedId: id }),
  setHovered: (id) => set({ hoveredId: id }),
  toggleDimensions: () => set(s => ({ showDimensions: !s.showDimensions })),
  toggleHeightColors: () => set(s => ({ showHeightColors: !s.showHeightColors })),

  startPlacingComponent: (kind) => set({ placingComponentKind: kind }),
  cancelPlacing: () => set({ placingComponentKind: null }),

  addManualComponent: (comp) => set(s => ({
    manualComponents: [...s.manualComponents, comp],
    placingComponentKind: null,
  })),
  updateManualComponent: (id, updates) => set(s => ({
    manualComponents: s.manualComponents.map(c => c.id === id ? { ...c, ...updates } : c),
  })),
  removeManualComponent: (id) => set(s => ({
    manualComponents: s.manualComponents.filter(c => c.id !== id),
    selectedId: s.selectedId === id ? null : s.selectedId,
  })),

  setViscosity: (v) => set({ viscosity: v }),
  setDensity: (d) => set({ density: d }),

  updateChannel: (id, updates) => set(s => {
    if (!s.analysis) return {}
    return {
      analysis: {
        ...s.analysis,
        channels: s.analysis.channels.map(ch => ch.id === id ? { ...ch, ...updates } : ch),
      },
    }
  }),

  updateChamber: (id, updates) => set(s => {
    if (!s.analysis) return {}
    return {
      analysis: {
        ...s.analysis,
        chambers: s.analysis.chambers.map(ch => ch.id === id ? { ...ch, ...updates } : ch),
      },
    }
  }),

  toSimulatorData: () => {
    const { analysis, manualComponents, viscosity, density } = get()
    if (!analysis) return { nodes: [], edges: [] }

    const nodes: Node<FluidNodeData>[] = []
    const edges: Edge[] = []
    let edgeId = 1

    // Scale factor: analysis is in µm, simulator expects m
    const um2m = 1e-6

    // 1) Junctions become implicit nodes
    for (const junc of analysis.junctions) {
      nodes.push({
        id: junc.id,
        type: 'fluid',
        position: { x: junc.position.x / 10, y: junc.position.y / 10 }, // scale for canvas
        data: {
          kind: 'linear_resistance' as ElementKind,
          label: `Junction`,
          params: { resistance: 0 },
        },
      })
    }

    // 2) Channels become nodes
    for (const ch of analysis.channels) {
      const midX = (ch.start.x + ch.end.x) / 2
      const midY = (ch.start.y + ch.end.y) / 2
      const kind: ElementKind = ch.type === 'circular' ? 'circular_channel' : 'rectangular_channel'
      const params = ch.type === 'circular'
        ? { radius: (ch.radius ?? 50) * um2m, length: ch.length * um2m, viscosity }
        : { width: (ch.width ?? 100) * um2m, height: ch.height * um2m, length: ch.length * um2m, viscosity }

      nodes.push({
        id: ch.id,
        type: 'fluid',
        position: { x: midX / 10, y: midY / 10 },
        data: { kind, label: `Channel ${ch.id.split('_').pop()}`, params },
      })
    }

    // 3) Chambers
    for (const chamber of analysis.chambers) {
      nodes.push({
        id: chamber.id,
        type: 'fluid',
        position: { x: chamber.center.x / 10, y: chamber.center.y / 10 },
        data: {
          kind: 'chamber' as ElementKind,
          label: `Chamber`,
          params: { height: chamber.height * um2m, density },
        },
      })
    }

    // 4) Ports → open_end or pressure_source
    for (const port of analysis.ports) {
      nodes.push({
        id: port.id,
        type: 'fluid',
        position: { x: port.position.x / 10, y: port.position.y / 10 },
        data: {
          kind: 'open_end' as ElementKind,
          label: port.label,
          params: {},
        },
      })
      // Connect port to its channel
      edges.push({
        id: `e_${edgeId++}`,
        source: port.id,
        target: port.connectedTo,
      })
    }

    // 5) Manual components (pumps, valves)
    for (const comp of manualComponents) {
      nodes.push({
        id: comp.id,
        type: 'fluid',
        position: { x: comp.position.x / 10, y: comp.position.y / 10 },
        data: {
          kind: comp.kind,
          label: comp.label,
          params: { ...comp.params },
        },
      })
      // Connect to attached element
      edges.push({
        id: `e_${edgeId++}`,
        source: comp.id,
        target: comp.attachedTo,
      })
    }

    // 6) Channel-to-junction/chamber edges (from topology)
    for (const junc of analysis.junctions) {
      for (const chId of junc.channelIds) {
        edges.push({
          id: `e_${edgeId++}`,
          source: junc.id,
          target: chId,
        })
      }
    }

    return { nodes, edges }
  },

  validate: () => {
    const { analysis, manualComponents } = get()
    const issues: ValidationIssue[] = []

    if (!analysis) {
      issues.push({ severity: 'error', message: 'No geometry loaded' })
      return issues
    }

    if (analysis.channels.length === 0) {
      issues.push({ severity: 'warning', message: 'No channels detected — check geometry' })
    }

    if (analysis.ports.length === 0) {
      issues.push({ severity: 'warning', message: 'No ports (open ends) detected' })
    }

    // Check for at least one pressure boundary
    const hasPressureBC = manualComponents.some(c =>
      c.kind === 'pressure_source' || c.kind === 'pressure_ground' || c.kind === 'pump'
    )
    if (!hasPressureBC && analysis.ports.length === 0) {
      issues.push({ severity: 'error', message: 'No pressure boundary — add a pump or pressure source' })
    }

    if (!hasPressureBC && analysis.ports.length > 0) {
      issues.push({ severity: 'warning', message: 'No pump/pressure source — open ends default to P=0' })
    }

    // Check disconnected channels
    const connectedChannelIds = new Set<string>()
    for (const junc of analysis.junctions) {
      for (const chId of junc.channelIds) connectedChannelIds.add(chId)
    }
    for (const port of analysis.ports) connectedChannelIds.add(port.connectedTo)
    for (const ch of analysis.channels) {
      if (!connectedChannelIds.has(ch.id)) {
        issues.push({ severity: 'warning', message: `Channel ${ch.id} appears disconnected` })
      }
    }

    return issues
  },
}))
