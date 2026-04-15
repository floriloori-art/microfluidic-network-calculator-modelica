import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import { type FluidNodeData } from '../types'
import { KIND_META } from '../palette'

export type FluidNodeType = Node<FluidNodeData, 'fluid'>

const FALLBACK_META = { color: '#94a3b8', icon: '?', label: 'unknown' }

function formatPressure(p: number) {
  if (Math.abs(p) >= 1000) return `${(p / 1000).toFixed(2)} kPa`
  return `${p.toFixed(1)} Pa`
}

function formatFlow(q: number) {
  if (Math.abs(q) >= 1e-3) return `${(q * 1e3).toFixed(3)} mL/s`
  if (Math.abs(q) >= 1e-6) return `${(q * 1e6).toFixed(2)} µL/s`
  return `${(q * 1e9).toFixed(1)} nL/s`
}

export const FluidNode = memo(({ data, selected }: NodeProps<FluidNodeType>) => {
  const meta = KIND_META[data.kind as string] ?? FALLBACK_META
  const pressure = typeof data.pressure === 'number' ? data.pressure : undefined
  const flow     = typeof data.flow     === 'number' ? data.flow     : undefined

  return (
    <div
      style={{ borderColor: meta.color }}
      className={`
        relative rounded-xl border-2 bg-white shadow-md min-w-[140px]
        transition-all duration-150
        ${selected ? 'ring-2 ring-blue-400 ring-offset-1 ring-offset-slate-50' : ''}
      `}
    >
      {/* Port A – left */}
      <Handle
        type="target"
        position={Position.Left}
        id="port_a"
        style={{ background: meta.color, width: 10, height: 10, border: '2px solid #ffffff' }}
      />

      {/* Header */}
      <div
        style={{ background: meta.color }}
        className="rounded-t-lg px-3 py-1.5 flex items-center gap-2"
      >
        <span className="text-lg leading-none">{meta.icon}</span>
        <span className="text-white text-xs font-semibold tracking-wide truncate">
          {data.label as string}
        </span>
      </div>

      {/* Body */}
      <div className="px-3 py-2 text-xs text-slate-600 space-y-0.5">
        <div className="text-slate-400 text-[10px] uppercase tracking-widest mb-1">{meta.label}</div>

        {pressure !== undefined && (
          <div className="flex justify-between gap-3">
            <span className="text-slate-400">p</span>
            <span className="font-mono text-cyan-600">{formatPressure(pressure)}</span>
          </div>
        )}
        {flow !== undefined && (
          <div className="flex justify-between gap-3">
            <span className="text-slate-400">Q</span>
            <span className="font-mono text-emerald-600">{formatFlow(flow)}</span>
          </div>
        )}
        {pressure === undefined && flow === undefined && (
          <div className="text-slate-400 italic text-[10px]">not simulated</div>
        )}
      </div>

      {/* Port B – right */}
      <Handle
        type="source"
        position={Position.Right}
        id="port_b"
        style={{ background: meta.color, width: 10, height: 10, border: '2px solid #ffffff' }}
      />
    </div>
  )
})

FluidNode.displayName = 'FluidNode'
