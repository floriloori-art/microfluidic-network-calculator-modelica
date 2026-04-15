import { create } from 'zustand'
import {
  type Node, type Edge,
  addEdge, applyNodeChanges, applyEdgeChanges,
  type NodeChange, type EdgeChange, type Connection,
} from '@xyflow/react'
import { type FluidNodeData } from '../types'

export type FluidNode = Node<FluidNodeData>

let nodeCounter = 0
export const genBuilderId = (kind: string) => `${kind}_${++nodeCounter}`

interface BuilderState {
  nodes: FluidNode[]
  edges: Edge[]
  selectedNodeId: string | null

  // Component metadata
  componentName: string
  componentLabel: string
  componentIcon: string
  componentColor: string
  componentDescription: string

  // Actions
  onNodesChange: (changes: NodeChange<FluidNode>[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  addNode: (node: FluidNode) => void
  selectNode: (id: string | null) => void
  updateNodeParams: (id: string, params: Partial<FluidNodeData['params']>) => void
  deleteNode: (id: string) => void
  clearAll: () => void
  setMeta: (meta: Partial<Pick<BuilderState, 'componentName' | 'componentLabel' | 'componentIcon' | 'componentColor' | 'componentDescription'>>) => void
}

export const useBuilderStore = create<BuilderState>((set) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  componentName: '',
  componentLabel: '',
  componentIcon: '★',
  componentColor: '#e11d48',
  componentDescription: '',

  onNodesChange: (changes) =>
    set((s) => ({ nodes: applyNodeChanges(changes, s.nodes) as FluidNode[] })),

  onEdgesChange: (changes) =>
    set((s) => ({ edges: applyEdgeChanges(changes, s.edges) })),

  onConnect: (connection) =>
    set((s) => ({ edges: addEdge({ ...connection, animated: true }, s.edges) })),

  addNode: (node) =>
    set((s) => ({ nodes: [...s.nodes, node] })),

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
    set({
      nodes: [], edges: [], selectedNodeId: null,
      componentName: '', componentLabel: '', componentIcon: '★',
      componentColor: '#e11d48', componentDescription: '',
    }),

  setMeta: (meta) => set(meta),
}))
