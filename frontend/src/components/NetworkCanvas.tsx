import { useCallback, type DragEvent } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap,
  type NodeChange, type EdgeChange, type Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { useStore, genId, type FluidNode } from '../store'
import { nodeTypes } from '../nodes'
import { BUILTIN_PALETTE_ITEMS, KIND_META } from '../palette'
import { type FluidNodeData, type ElementKind } from '../types'

export function NetworkCanvas() {
  const {
    nodes, edges,
    onNodesChange, onEdgesChange, onConnect,
    addNode, selectNode,
    customPaletteItems,
  } = useStore()

  const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const kind = e.dataTransfer.getData('application/fluid-kind') as ElementKind
    if (!kind) return

    const allItems = [...BUILTIN_PALETTE_ITEMS, ...customPaletteItems]
    const paletteItem = allItems.find(p => p.kind === kind)
    if (!paletteItem) return

    const bounds = e.currentTarget.getBoundingClientRect()
    const position = {
      x: e.clientX - bounds.left - 70,
      y: e.clientY - bounds.top - 30,
    }

    const id = genId(kind)
    const newNode: FluidNode = {
      id,
      type: 'fluid',
      position,
      data: {
        kind,
        label: `${paletteItem.label} ${id.split('_').pop()}`,
        params: { ...paletteItem.defaultParams },
      } as FluidNodeData,
    }
    addNode(newNode)
    selectNode(id)
  }, [addNode, selectNode, customPaletteItems])

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
        <MiniMap
          nodeColor={(n) => KIND_META[(n.data as FluidNodeData).kind]?.color ?? '#94a3b8'}
          style={{ background: '#ffffff', border: '1px solid #e2e8f0' }}
          maskColor="rgba(241,245,249,0.7)"
        />
      </ReactFlow>

      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center text-slate-400">
            <div className="text-5xl mb-4">⬡</div>
            <div className="text-sm font-medium">Drag elements from the left panel</div>
            <div className="text-xs mt-1">then connect their ports</div>
          </div>
        </div>
      )}
    </div>
  )
}
