/**
 * ManualPlacement: Toolbar/dialog for manually adding pumps, valves,
 * pressure sources, and flow sources to the network.
 * These active components cannot be detected from STEP geometry.
 */

import { useCadImportStore } from '../CadImportStore'
import type { ElementKind } from '../../types'

interface PlaceableComponent {
  kind: ElementKind
  label: string
  icon: string
  description: string
  color: string
}

const PLACEABLE_COMPONENTS: PlaceableComponent[] = [
  {
    kind: 'pump',
    label: 'Pump',
    icon: 'P',
    description: 'Pressure-generating pump',
    color: 'bg-blue-50 border-blue-200 text-blue-700 hover:bg-blue-100',
  },
  {
    kind: 'pressure_source',
    label: 'Pressure Source',
    icon: '⊕',
    description: 'Fixed pressure boundary',
    color: 'bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100',
  },
  {
    kind: 'flow_source',
    label: 'Flow Source',
    icon: 'F',
    description: 'Fixed flow rate injection',
    color: 'bg-cyan-50 border-cyan-200 text-cyan-700 hover:bg-cyan-100',
  },
  {
    kind: 'check_valve',
    label: 'Check Valve',
    icon: 'V',
    description: 'One-way flow valve',
    color: 'bg-amber-50 border-amber-200 text-amber-700 hover:bg-amber-100',
  },
  {
    kind: 'pressure_ground',
    label: 'Pressure Ground',
    icon: '⏚',
    description: 'Reference pressure (P=0)',
    color: 'bg-slate-50 border-slate-300 text-slate-700 hover:bg-slate-100',
  },
]

export function ManualPlacement() {
  const placingKind = useCadImportStore(s => s.placingComponentKind)
  const startPlacing = useCadImportStore(s => s.startPlacingComponent)
  const cancelPlacing = useCadImportStore(s => s.cancelPlacing)
  const analysis = useCadImportStore(s => s.analysis)

  if (!analysis) return null

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
          Add Active Components
        </span>
      </div>

      <p className="text-[11px] text-slate-400 leading-tight">
        Pumps, valves and pressure sources cannot be detected from geometry.
        Click a button below, then click on the sketch to place it.
      </p>

      <div className="grid grid-cols-1 gap-1.5">
        {PLACEABLE_COMPONENTS.map(comp => {
          const isActive = placingKind === comp.kind
          return (
            <button
              key={comp.kind}
              onClick={() => isActive ? cancelPlacing() : startPlacing(comp.kind)}
              className={`
                flex items-center gap-2.5 px-2.5 py-2 rounded-lg border text-left transition-all text-xs
                ${isActive
                  ? 'border-violet-400 bg-violet-50 text-violet-700 ring-1 ring-violet-400'
                  : comp.color
                }
              `}
            >
              <span className={`
                w-6 h-6 rounded flex items-center justify-center text-sm font-bold shrink-0
                ${isActive ? 'bg-violet-200' : 'bg-white/80'}
              `}>
                {comp.icon}
              </span>
              <div className="min-w-0">
                <div className="font-medium">{comp.label}</div>
                <div className="text-[10px] opacity-60">{comp.description}</div>
              </div>
              {isActive && (
                <span className="ml-auto text-[10px] text-violet-500 shrink-0">
                  Click sketch…
                </span>
              )}
            </button>
          )
        })}
      </div>

      {placingKind && (
        <button
          onClick={cancelPlacing}
          className="w-full text-xs text-slate-400 hover:text-slate-600 py-1"
        >
          Cancel placement (Esc)
        </button>
      )}
    </div>
  )
}
