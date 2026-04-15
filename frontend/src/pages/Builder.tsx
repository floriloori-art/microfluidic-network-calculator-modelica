import { useCallback, useState, type DragEvent } from 'react'
import {
  ReactFlow, Background, Controls,
  type NodeChange, type EdgeChange, type Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { nodeTypes } from '../nodes'
import { BUILTIN_PALETTE_ITEMS, KIND_META } from '../palette'
import { type FluidNodeData, type ElementKind, type PaletteItem } from '../types'
import { useBuilderStore, genBuilderId, type FluidNode } from './BuilderStore'
import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

const PRIMITIVE_KINDS = new Set([
  'linear_resistance', 'pressure_source', 'pressure_ground',
  'open_end', 'flow_source', 'check_valve',
])

const BUILDER_PALETTE: PaletteItem[] = [
  {
    kind: 'open_end' as ElementKind,
    label: 'Port (Inlet)',
    icon: '◉',
    color: '#22c55e',
    defaultParams: {},
  },
  {
    kind: 'open_end' as ElementKind,
    label: 'Port (Outlet)',
    icon: '◎',
    color: '#ef4444',
    defaultParams: {},
  },
  ...BUILTIN_PALETTE_ITEMS.filter(p => PRIMITIVE_KINDS.has(p.kind)),
]

// ── Sidebar ─────────────────────────────────────────────────────────────────

function BuilderSidebar() {
  function PaletteCard({ item, dragKind }: { item: PaletteItem; dragKind?: string }) {
    const onDragStart = (e: DragEvent) => {
      e.dataTransfer.setData('application/fluid-kind', dragKind ?? item.kind)
      e.dataTransfer.setData('application/label', item.label)
      e.dataTransfer.effectAllowed = 'move'
    }

    return (
      <div
        draggable
        onDragStart={onDragStart}
        style={{ borderColor: item.color }}
        className="flex items-center gap-3 px-3 py-2.5 rounded-lg border bg-white hover:bg-slate-50 cursor-grab active:cursor-grabbing transition-all select-none shadow-sm hover:shadow"
      >
        <span style={{ color: item.color }} className="text-xl leading-none w-6 text-center">{item.icon}</span>
        <span className="text-sm text-slate-700">{item.label}</span>
      </div>
    )
  }

  return (
    <aside className="w-52 bg-white border-r border-slate-200 flex flex-col">
      <div className="px-4 pt-4 pb-2">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">Primitives</h2>
        <p className="text-[10px] text-slate-400 mt-1">Drag onto canvas</p>
      </div>
      <div className="flex flex-col gap-1.5 px-3 pb-4 flex-1 overflow-y-auto">
        {BUILDER_PALETTE.map((item, i) => (
          <PaletteCard key={`${item.kind}-${i}`} item={item} />
        ))}
      </div>
    </aside>
  )
}

// ── Meta Panel (right side) ─────────────────────────────────────────────────

function MetaPanel() {
  const {
    componentName, componentLabel, componentIcon, componentColor,
    componentDescription, nodes, edges, setMeta,
  } = useBuilderStore()
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  const canSave = componentName.trim() && componentLabel.trim() && nodes.length >= 2 && edges.length >= 1

  const handleSave = async () => {
    setSaving(true)
    setMessage('')

    try {
      const elements = nodes.map(n => ({
        id: n.id,
        type: n.data.kind,
        params: { ...n.data.params },
      }))

      const connections = edges.map(e => [e.source, e.target])

      const portMapping: Record<string, string> = {}
      const openEndNodes = nodes.filter(n => n.data.kind === 'open_end')
      if (openEndNodes.length >= 2) {
        portMapping['inlet'] = openEndNodes[0].id
        portMapping['outlet'] = openEndNodes[1].id
      } else if (openEndNodes.length === 1) {
        portMapping['inlet'] = openEndNodes[0].id
        const nonPort = nodes.find(n => n.id !== openEndNodes[0].id)
        if (nonPort) portMapping['outlet'] = nonPort.id
      } else {
        if (nodes.length >= 1) portMapping['inlet'] = nodes[0].id
        if (nodes.length >= 2) portMapping['outlet'] = nodes[nodes.length - 1].id
      }

      await client.post('/components/define', {
        name: componentName.trim().replace(/\s+/g, '_').toLowerCase(),
        label: componentLabel.trim(),
        description: componentDescription,
        icon: componentIcon || '★',
        color: componentColor || '#e11d48',
        ports: ['inlet', 'outlet'],
        elements,
        connections,
        port_mapping: portMapping,
        exposed_params: [],
      })

      setMessage('Saved!')
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? err.response?.data?.detail ?? err.message
        : String(err)
      setMessage(`Error: ${msg}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <aside className="w-56 bg-white border-l border-slate-200 flex flex-col">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">
          Component Info
        </h2>
      </div>

      <div className="flex flex-col gap-3 p-4 flex-1 overflow-y-auto">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-500">Name (ID)</label>
          <input
            type="text"
            value={componentName}
            onChange={e => setMeta({ componentName: e.target.value })}
            placeholder="my_mixer"
            className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs text-slate-700 font-mono focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-500">Label</label>
          <input
            type="text"
            value={componentLabel}
            onChange={e => setMeta({ componentLabel: e.target.value })}
            placeholder="My Mixer"
            className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs text-slate-700 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
          />
        </div>

        <div className="flex gap-2">
          <div className="flex flex-col gap-1 flex-1">
            <label className="text-xs text-slate-500">Icon</label>
            <input
              type="text"
              value={componentIcon}
              onChange={e => setMeta({ componentIcon: e.target.value })}
              maxLength={2}
              className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs text-slate-700 text-center focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
            />
          </div>
          <div className="flex flex-col gap-1 flex-1">
            <label className="text-xs text-slate-500">Color</label>
            <input
              type="color"
              value={componentColor}
              onChange={e => setMeta({ componentColor: e.target.value })}
              className="w-full h-7 bg-white border border-slate-200 rounded cursor-pointer"
            />
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-500">Description</label>
          <textarea
            value={componentDescription}
            onChange={e => setMeta({ componentDescription: e.target.value })}
            rows={2}
            className="w-full bg-white border border-slate-200 rounded px-2 py-1 text-xs text-slate-700 resize-none focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
          />
        </div>

        <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5">
          {nodes.length} elements, {edges.length} connections
        </div>

        {message && (
          <div className={`text-[10px] rounded px-2 py-1.5 ${message.startsWith('Error') ? 'bg-red-50 border border-red-200 text-red-600' : 'bg-green-50 border border-green-200 text-green-600'}`}>
            {message}
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 p-3 flex flex-col gap-2">
        <button
          onClick={handleSave}
          disabled={!canSave || saving}
          className="w-full text-xs font-medium bg-blue-500 hover:bg-blue-600 disabled:bg-slate-100 disabled:text-slate-400 text-white rounded px-3 py-2 transition-colors shadow-sm"
        >
          {saving ? 'Saving...' : 'Save as Element'}
        </button>
      </div>
    </aside>
  )
}

// ── Canvas ──────────────────────────────────────────────────────────────────

function BuilderCanvas() {
  const {
    nodes, edges,
    onNodesChange, onEdgesChange, onConnect,
    addNode, selectNode,
  } = useBuilderStore()

  const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const kind = e.dataTransfer.getData('application/fluid-kind') as ElementKind
    if (!kind) return

    const paletteItem = BUILDER_PALETTE.find(p => p.kind === kind)
      ?? BUILTIN_PALETTE_ITEMS.find(p => p.kind === kind)
    if (!paletteItem) return

    const label = e.dataTransfer.getData('application/label') || paletteItem.label

    const bounds = e.currentTarget.getBoundingClientRect()
    const position = {
      x: e.clientX - bounds.left - 70,
      y: e.clientY - bounds.top - 30,
    }

    const id = genBuilderId(kind)
    const newNode: FluidNode = {
      id,
      type: 'fluid',
      position,
      data: {
        kind,
        label: `${label} ${id.split('_').pop()}`,
        params: { ...paletteItem.defaultParams },
      } as FluidNodeData,
    }
    addNode(newNode)
    selectNode(id)
  }, [addNode, selectNode])

  const onDragOver = useCallback((e: DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  return (
    <div className="flex-1 relative" onDrop={onDrop} onDragOver={onDragOver}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={(c) => onNodesChange(c as NodeChange<FluidNode>[])}
        onEdgesChange={(c) => onEdgesChange(c as EdgeChange[])}
        onConnect={(c) => onConnect(c as Connection)}
        onNodeClick={(_, node) => selectNode(node.id)}
        onPaneClick={() => selectNode(null)}
        fitView
        proOptions={{ hideAttribution: true }}
        style={{ background: '#f1f5f9' }}
        defaultEdgeOptions={{
          animated: true,
          style: { stroke: '#94a3b8', strokeWidth: 2 },
        }}
      >
        <Background color="#cbd5e1" gap={20} size={1} />
        <Controls
          style={{ background: '#ffffff', border: '1px solid #e2e8f0' }}
          showInteractive={false}
        />
      </ReactFlow>

      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center text-slate-400">
            <div className="text-5xl mb-4">★</div>
            <div className="text-sm font-medium">Drag primitives to build your element</div>
            <div className="text-xs mt-1">then connect them and save</div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Builder Toolbar (within the builder tab) ───────────────────────────────

function BuilderToolbar() {
  const { clearAll, nodes, edges } = useBuilderStore()

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-white border-b border-slate-200">
      <span className="text-violet-500 text-lg">★</span>
      <h2 className="font-semibold text-slate-700 text-sm">Component Builder</h2>
      <span className="text-[10px] px-2 py-0.5 rounded-full bg-violet-50 text-violet-600 font-medium border border-violet-200">
        Builder
      </span>

      <button
        onClick={clearAll}
        className="text-xs text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded px-3 py-1.5 transition-colors"
      >
        Clear
      </button>

      <div className="flex-1" />

      <span className="text-xs text-slate-400">
        {nodes.length} elements · {edges.length} connections
      </span>
    </div>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────

export function BuilderPage() {
  return (
    <>
      <BuilderToolbar />
      <div className="flex flex-1 overflow-hidden">
        <BuilderSidebar />
        <BuilderCanvas />
        <MetaPanel />
      </div>
    </>
  )
}
