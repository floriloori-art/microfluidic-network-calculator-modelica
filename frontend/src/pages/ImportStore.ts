import { create } from 'zustand'
import { type ElementKind, type FluidNodeData } from '../types'
import { type Node, type Edge } from '@xyflow/react'

// ── Types ───────────────────────────────────────────────────────────────────

export interface PlacedElement {
  id: string
  kind: ElementKind
  label: string
  /** Position on the PDF canvas (px) */
  x: number
  y: number
  /** User-entered physical parameters */
  params: Record<string, number>
}

export interface PlacedConnection {
  id: string
  sourceId: string
  targetId: string
}

export type ScaleState =
  | { mode: 'none' }
  | { mode: 'picking_p1' }
  | { mode: 'picking_p2'; p1: { x: number; y: number } }
  | { mode: 'done'; p1: { x: number; y: number }; p2: { x: number; y: number }; pxDistance: number; realDistance: number }

export interface ImportState {
  // PDF
  pdfFile: File | null
  pdfPageCount: number
  currentPage: number

  // Scale calibration
  scale: ScaleState
  /** Micrometers per pixel (derived from scale calibration) */
  umPerPx: number | null

  // Placed elements (overlay)
  elements: PlacedElement[]
  connections: PlacedConnection[]
  selectedElementId: string | null

  // Placement mode
  placingKind: ElementKind | null

  // Layer visibility
  showPdf: boolean
  showGrid: boolean
  showOverlay: boolean

  // Actions
  setPdf: (file: File, pageCount: number) => void
  setPage: (page: number) => void
  clearPdf: () => void

  startScaleCalibration: () => void
  setScalePoint: (x: number, y: number) => void
  confirmScale: (realDistanceUm: number) => void
  clearScale: () => void

  setPlacingKind: (kind: ElementKind | null) => void
  addElement: (el: PlacedElement) => void
  updateElement: (id: string, updates: Partial<PlacedElement>) => void
  removeElement: (id: string) => void
  selectElement: (id: string | null) => void

  addConnection: (sourceId: string, targetId: string) => void
  removeConnection: (id: string) => void

  toggleLayer: (layer: 'showPdf' | 'showGrid' | 'showOverlay') => void

  /** Build simulator-compatible nodes & edges */
  toSimulatorData: () => { nodes: Node<FluidNodeData>[]; edges: Edge[] }
}

let _nextId = 1
function genImportId(kind: string): string {
  return `imp_${kind}_${_nextId++}`
}

export const useImportStore = create<ImportState>((set, get) => ({
  pdfFile: null,
  pdfPageCount: 0,
  currentPage: 1,

  scale: { mode: 'none' },
  umPerPx: null,

  elements: [],
  connections: [],
  selectedElementId: null,

  placingKind: null,

  showPdf: true,
  showGrid: true,
  showOverlay: true,

  setPdf: (file, pageCount) => set({ pdfFile: file, pdfPageCount: pageCount, currentPage: 1 }),
  setPage: (page) => set({ currentPage: page }),
  clearPdf: () => set({
    pdfFile: null, pdfPageCount: 0, currentPage: 1,
    elements: [], connections: [], selectedElementId: null,
    scale: { mode: 'none' }, umPerPx: null,
  }),

  startScaleCalibration: () => set({ scale: { mode: 'picking_p1' } }),
  setScalePoint: (x, y) => set(s => {
    if (s.scale.mode === 'picking_p1') {
      return { scale: { mode: 'picking_p2', p1: { x, y } } }
    }
    if (s.scale.mode === 'picking_p2') {
      const dx = x - s.scale.p1.x
      const dy = y - s.scale.p1.y
      const pxDist = Math.sqrt(dx * dx + dy * dy)
      return {
        scale: {
          mode: 'done',
          p1: s.scale.p1,
          p2: { x, y },
          pxDistance: pxDist,
          realDistance: 0,
        },
      }
    }
    return {}
  }),
  confirmScale: (realDistanceUm) => set(s => {
    if (s.scale.mode === 'done') {
      return {
        umPerPx: realDistanceUm / s.scale.pxDistance,
        scale: { ...s.scale, realDistance: realDistanceUm },
      }
    }
    return {}
  }),
  clearScale: () => set({ scale: { mode: 'none' }, umPerPx: null }),

  setPlacingKind: (kind) => set({ placingKind: kind }),

  addElement: (el) => set(s => ({ elements: [...s.elements, el], placingKind: null })),
  updateElement: (id, updates) => set(s => ({
    elements: s.elements.map(el => el.id === id ? { ...el, ...updates } : el),
  })),
  removeElement: (id) => set(s => ({
    elements: s.elements.filter(el => el.id !== id),
    connections: s.connections.filter(c => c.sourceId !== id && c.targetId !== id),
    selectedElementId: s.selectedElementId === id ? null : s.selectedElementId,
  })),
  selectElement: (id) => set({ selectedElementId: id }),

  addConnection: (sourceId, targetId) => set(s => ({
    connections: [...s.connections, {
      id: `conn_${_nextId++}`,
      sourceId,
      targetId,
    }],
  })),
  removeConnection: (id) => set(s => ({
    connections: s.connections.filter(c => c.id !== id),
  })),

  toggleLayer: (layer) => set(s => ({ [layer]: !s[layer] })),

  toSimulatorData: () => {
    const { elements, connections } = get()
    const nodes: Node<FluidNodeData>[] = elements.map((el, i) => ({
      id: el.id,
      type: 'fluid' as const,
      position: { x: el.x, y: el.y },
      data: {
        kind: el.kind,
        label: el.label,
        params: { ...el.params },
      } as FluidNodeData,
    }))

    const edges: Edge[] = connections.map(c => ({
      id: c.id,
      source: c.sourceId,
      target: c.targetId,
    }))

    return { nodes, edges }
  },
}))

export { genImportId }
