import { type DragEvent, useEffect } from 'react'
import { BUILTIN_PALETTE_ITEMS } from '../palette'
import { useStore } from '../store'
import { type PaletteItem } from '../types'
import { PRESET_SIMPLE_CHANNEL, PRESET_PUMP_VALVE, PRESET_T_JUNCTION } from '../presets'

function PaletteCard({ item }: { item: PaletteItem }) {
  const onDragStart = (e: DragEvent) => {
    e.dataTransfer.setData('application/fluid-kind', item.kind)
    e.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div
      draggable
      onDragStart={onDragStart}
      style={{ borderColor: item.color }}
      className="
        flex items-center gap-3 px-3 py-2.5 rounded-lg border
        bg-white hover:bg-slate-50 cursor-grab active:cursor-grabbing
        transition-all select-none shadow-sm hover:shadow
      "
    >
      <span style={{ color: item.color }} className="text-xl leading-none w-6 text-center">
        {item.icon}
      </span>
      <span className="text-sm text-slate-700">{item.label}</span>
    </div>
  )
}

const PRESETS = [
  { label: 'Simple Channel', data: PRESET_SIMPLE_CHANNEL },
  { label: 'Pump + Valve',   data: PRESET_PUMP_VALVE },
  { label: 'T-Junction',     data: PRESET_T_JUNCTION },
]

export function Sidebar() {
  const { clearAll, addNode, addEdges, customPaletteItems, loadCustomPalette } = useStore()

  useEffect(() => { loadCustomPalette() }, [loadCustomPalette])

  const allPaletteItems = [...BUILTIN_PALETTE_ITEMS, ...customPaletteItems]

  const loadPreset = (data: typeof PRESET_SIMPLE_CHANNEL) => {
    clearAll()
    data.nodes.forEach(n => addNode(n))
    addEdges(data.edges)
  }

  return (
    <aside className="w-52 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
      <div className="px-4 pt-4 pb-2">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">
          Elements
        </h2>
        <p className="text-[10px] text-slate-400 mt-1">Drag onto canvas</p>
      </div>

      <div className="flex flex-col gap-1.5 px-3 pb-4">
        {allPaletteItems.map((item) => (
          <PaletteCard key={item.kind} item={item} />
        ))}
      </div>

      <div className="mt-auto border-t border-slate-200 px-4 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">
          Presets
        </h2>
        {PRESETS.map(p => (
          <button
            key={p.label}
            onClick={() => loadPreset(p.data)}
            className="w-full text-left text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-50 rounded px-2 py-1.5 transition-colors"
          >
            {p.label}
          </button>
        ))}
      </div>
    </aside>
  )
}
