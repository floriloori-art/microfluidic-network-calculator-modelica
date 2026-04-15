import { create } from 'zustand'
import {
  type Node, type Edge,
  addEdge, applyNodeChanges, applyEdgeChanges,
  type NodeChange, type EdgeChange, type Connection,
} from '@xyflow/react'
import { type FluidNodeData, type SimulateResponse, type PaletteItem } from './types'
import { fetchCustomPalette, registerCustomMeta } from './palette'

export type FluidNode = Node<FluidNodeData>

let nodeCounter = 0
export const genId = (kind: string) => `${kind}_${++nodeCounter}`

interface AppState {
  nodes: FluidNode[]
  edges: Edge[]
  selectedNodeId: string | null
  simulationResult: SimulateResponse | null
  isSimulating: boolean
  errorMessage: string | null
  customPaletteItems: PaletteItem[]

  onNodesChange: (changes: NodeChange<FluidNode>[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void

  addNode: (node: FluidNode) => void
  addEdges: (edges: Edge[]) => void
  selectNode: (id: string | null) => void
  updateNodeParams: (id: string, params: Partial<FluidNodeData['params']>) => void
  deleteNode: (id: string) => void
  clearAll: () => void
  setSimulationResult: (result: SimulateResponse | null) => void
  setSimulating: (v: boolean) => void
  setError: (msg: string | null) => void
  loadCustomPalette: () => Promise<void>
}

export const useStore = create<AppState>((set) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  simulationResult: null,
  isSimulating: false,
  errorMessage: null,
  customPaletteItems: [],

  onNodesChange: (changes) =>
    set((s) => ({ nodes: applyNodeChanges(changes, s.nodes) as FluidNode[] })),

  onEdgesChange: (changes) =>
    set((s) => ({ edges: applyEdgeChanges(changes, s.edges) })),

  onConnect: (connection) =>
    set((s) => ({ edges: addEdge({ ...connection, animated: true }, s.edges) })),

  addNode: (node) =>
    set((s) => ({ nodes: [...s.nodes, node] })),

  // Used by presets to bulk-add edges with known IDs and styles
  addEdges: (edges) =>
    set((s) => ({ edges: [...s.edges, ...edges] })),

  selectNode: (id) =>
    set({ selectedNodeId: id }),

  updateNodeParams: (id, params) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id
          ? { ...n, data: { ...n.data, params: { ...n.data.params, ...params } } }
          : n
      ),
    })),

  deleteNode: (id) =>
    set((s) => ({
      nodes: s.nodes.filter((n) => n.id !== id),
      edges: s.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: s.selectedNodeId === id ? null : s.selectedNodeId,
    })),

  clearAll: () =>
    set({ nodes: [], edges: [], selectedNodeId: null, simulationResult: null, errorMessage: null }),

  setSimulationResult: (result) => set({ simulationResult: result }),
  setSimulating: (v) => set({ isSimulating: v }),
  setError: (msg) => set({ errorMessage: msg }),

  loadCustomPalette: async () => {
    const items = await fetchCustomPalette()
    registerCustomMeta(items)
    set({ customPaletteItems: items })
  },
}))
