import { useStore } from '../store'
import { KIND_META } from '../palette'
import {
  type CircularChannelParams, type RectangularChannelParams,
  type ChamberParams, type PumpParams, type ValveParams,
  type LinearResistanceParams, type PressureSourceParams,
  type PressureGroundParams, type FlowSourceParams, type CheckValveParams,
  type CompositeParams, type ExposedParam,
} from '../types'

// ─── Generic number field ──────────────────────────────────────────────────────
function Field({
  label, value, unit, onChange, min, max, step,
}: {
  label: string; value: number; unit: string
  onChange: (v: number) => void
  min?: number; max?: number; step?: number
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-baseline">
        <label className="text-xs text-slate-500">{label}</label>
        <span className="text-[10px] text-slate-400">{unit}</span>
      </div>
      <input
        type="number"
        value={value}
        min={min} max={max} step={step ?? 'any'}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="
          w-full bg-white border border-slate-200 rounded px-2 py-1
          text-xs text-slate-700 font-mono
          focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100 transition-colors
        "
      />
    </div>
  )
}

// ─── Slider field for opening ─────────────────────────────────────────────────
function SliderField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-baseline">
        <label className="text-xs text-slate-500">{label}</label>
        <span className="text-xs font-mono text-amber-600">{(value * 100).toFixed(0)}%</span>
      </div>
      <input
        type="range" min={0} max={1} step={0.01} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-amber-500"
      />
    </div>
  )
}

// ─── Per-element forms ────────────────────────────────────────────────────────
function CircularChannelForm({ params, onChange }: { params: CircularChannelParams; onChange: (p: Partial<CircularChannelParams>) => void }) {
  return <>
    <Field label="Radius" value={params.radius * 1e6} unit="µm" onChange={v => onChange({ radius: v / 1e6 })} min={1} />
    <Field label="Length" value={params.length * 1e3} unit="mm" onChange={v => onChange({ length: v / 1e3 })} min={0.01} />
    <Field label="Viscosity" value={params.viscosity * 1e3} unit="mPa·s" onChange={v => onChange({ viscosity: v / 1e3 })} min={0.001} />
  </>
}

function RectangularChannelForm({ params, onChange }: { params: RectangularChannelParams; onChange: (p: Partial<RectangularChannelParams>) => void }) {
  return <>
    <Field label="Width" value={params.width * 1e6} unit="µm" onChange={v => onChange({ width: v / 1e6 })} min={1} />
    <Field label="Height" value={params.height * 1e6} unit="µm" onChange={v => onChange({ height: v / 1e6 })} min={1} />
    <Field label="Length" value={params.length * 1e3} unit="mm" onChange={v => onChange({ length: v / 1e3 })} min={0.01} />
    <Field label="Viscosity" value={params.viscosity * 1e3} unit="mPa·s" onChange={v => onChange({ viscosity: v / 1e3 })} min={0.001} />
  </>
}

function ChamberForm({ params, onChange }: { params: ChamberParams; onChange: (p: Partial<ChamberParams>) => void }) {
  return <>
    <Field label="Fluid height" value={params.height * 1e6} unit="µm" onChange={v => onChange({ height: v / 1e6 })} min={0} />
    <Field label="Density" value={params.density} unit="kg/m³" onChange={v => onChange({ density: v })} min={1} />
    <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5 mt-1">
      ΔP = ρ·g·h ≈ <span className="text-cyan-600 font-mono">
        {(params.density * 9.81 * params.height).toFixed(2)} Pa
      </span>
    </div>
  </>
}

function PumpForm({ params, onChange }: { params: PumpParams; onChange: (p: Partial<PumpParams>) => void }) {
  return <>
    <Field label="Max pressure" value={params.pressure_generated} unit="Pa" onChange={v => onChange({ pressure_generated: v })} min={0} />
    <Field label="Max flow" value={params.flow_max * 1e9} unit="nL/s" onChange={v => onChange({ flow_max: v / 1e9 })} min={0.001} />
    <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5 mt-1">
      Curve: dp = dp_max − b·Q²
    </div>
  </>
}

function ValveForm({ params, onChange }: { params: ValveParams; onChange: (p: Partial<ValveParams>) => void }) {
  const R = 1 / Math.pow(params.kv * Math.max(params.opening, 1e-10), 2)
  return <>
    <SliderField label="Opening" value={params.opening} onChange={v => onChange({ opening: v })} />
    <Field label="Kv coefficient" value={params.kv} unit="m³/(s·√Pa)" onChange={v => onChange({ kv: v })} min={1e-6} step={0.001} />
    <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5 mt-1">
      R = <span className="text-amber-600 font-mono">{R.toExponential(2)} Pa·s/m³</span>
    </div>
  </>
}

function LinearResistanceForm({ params, onChange }: { params: LinearResistanceParams; onChange: (p: Partial<LinearResistanceParams>) => void }) {
  return <>
    <Field label="Resistance" value={params.resistance} unit="Pa·s/m³" onChange={v => onChange({ resistance: v })} min={1} step={1e6} />
    <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5 mt-1">
      ΔP = R · Q
    </div>
  </>
}

function PressureSourceForm({ params, onChange }: { params: PressureSourceParams; onChange: (p: Partial<PressureSourceParams>) => void }) {
  return <>
    <Field label="Pressure" value={params.pressure} unit="Pa" onChange={v => onChange({ pressure: v })} step={100} />
    <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5 mt-1">
      Ideal pressure source — P = p₀
    </div>
  </>
}

function PressureGroundForm({ params, onChange }: { params: PressureGroundParams; onChange: (p: Partial<PressureGroundParams>) => void }) {
  return <>
    <Field label="Reference pressure" value={params.p_ref} unit="Pa" onChange={v => onChange({ p_ref: v })} step={100} />
    <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5 mt-1">
      Network pressure reference
    </div>
  </>
}

function OpenEndForm() {
  return (
    <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5">
      Atmospheric outlet — P = 0 Pa<br />No parameters required.
    </div>
  )
}

function FlowSourceForm({ params, onChange }: { params: FlowSourceParams; onChange: (p: Partial<FlowSourceParams>) => void }) {
  return <>
    <Field label="Flow rate" value={params.flow_rate * 1e9} unit="nL/s" onChange={v => onChange({ flow_rate: v / 1e9 })} step={0.1} />
    <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5 mt-1">
      Ideal flow source — Q = Q₀<br />Positive = inject into network
    </div>
  </>
}

function CheckValveForm({ params, onChange }: { params: CheckValveParams; onChange: (p: Partial<CheckValveParams>) => void }) {
  return <>
    <Field label="R forward" value={params.r_fwd} unit="Pa·s/m³" onChange={v => onChange({ r_fwd: v })} min={1} step={1e5} />
    <Field label="R reverse" value={params.r_rev} unit="Pa·s/m³" onChange={v => onChange({ r_rev: v })} min={1} step={1e12} />
    <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5 mt-1">
      One-way valve — blocks reverse flow
    </div>
  </>
}

function CompositeForm({ params, exposedParams, onChange }: {
  params: CompositeParams
  exposedParams?: ExposedParam[]
  onChange: (p: Partial<CompositeParams>) => void
}) {
  if (!exposedParams || exposedParams.length === 0) {
    return (
      <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5">
        Composite element — no exposed parameters
      </div>
    )
  }
  return <>
    {exposedParams.map(ep => {
      const key = `${ep.element_id}.${ep.param}`
      const value = typeof params[key] === 'number' ? params[key] as number : (ep.default ?? 0)
      return (
        <Field
          key={key}
          label={ep.label}
          value={value}
          unit=""
          onChange={v => onChange({ [key]: v })}
          step={1}
        />
      )
    })}
    <div className="text-[10px] text-slate-500 bg-slate-50 border border-slate-200 rounded px-2 py-1.5 mt-1">
      Composite: {params.component_name}
    </div>
  </>
}

// ─── Main panel ───────────────────────────────────────────────────────────────
export function PropertiesPanel() {
  const { nodes, selectedNodeId, updateNodeParams, deleteNode, customPaletteItems } = useStore()
  const node = nodes.find(n => n.id === selectedNodeId)

  if (!node) {
    return (
      <aside className="w-56 bg-white border-l border-slate-200 flex flex-col items-center justify-center p-6">
        <div className="text-slate-400 text-center text-sm">
          <div className="text-3xl mb-3">↖</div>
          Select an element<br />to edit its parameters
        </div>
      </aside>
    )
  }

  const meta = KIND_META[node.data.kind] ?? { color: '#94a3b8', icon: '?', label: node.data.kind }
  const update = (p: object) => updateNodeParams(node.id, p as never)

  return (
    <aside className="w-56 bg-white border-l border-slate-200 flex flex-col">
      {/* Header */}
      <div style={{ borderColor: meta.color }} className="border-b-2 px-4 py-3 flex items-center gap-2">
        <span style={{ color: meta.color }} className="text-xl">{meta.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-slate-700 truncate">{node.data.label}</div>
          <div className="text-[10px] text-slate-400">{node.id}</div>
        </div>
      </div>

      {/* Form */}
      <div className="flex flex-col gap-3 p-4 flex-1 overflow-y-auto">
        {node.data.kind === 'circular_channel' &&
          <CircularChannelForm params={node.data.params as CircularChannelParams} onChange={update} />}
        {node.data.kind === 'rectangular_channel' &&
          <RectangularChannelForm params={node.data.params as RectangularChannelParams} onChange={update} />}
        {node.data.kind === 'chamber' &&
          <ChamberForm params={node.data.params as ChamberParams} onChange={update} />}
        {node.data.kind === 'pump' &&
          <PumpForm params={node.data.params as PumpParams} onChange={update} />}
        {node.data.kind === 'valve' &&
          <ValveForm params={node.data.params as ValveParams} onChange={update} />}
        {node.data.kind === 'linear_resistance' &&
          <LinearResistanceForm params={node.data.params as LinearResistanceParams} onChange={update} />}
        {node.data.kind === 'pressure_source' &&
          <PressureSourceForm params={node.data.params as PressureSourceParams} onChange={update} />}
        {node.data.kind === 'pressure_ground' &&
          <PressureGroundForm params={node.data.params as PressureGroundParams} onChange={update} />}
        {node.data.kind === 'open_end' &&
          <OpenEndForm />}
        {node.data.kind === 'flow_source' &&
          <FlowSourceForm params={node.data.params as FlowSourceParams} onChange={update} />}
        {node.data.kind === 'check_valve' &&
          <CheckValveForm params={node.data.params as CheckValveParams} onChange={update} />}
        {node.data.kind.startsWith('composite:') &&
          <CompositeForm
            params={node.data.params as CompositeParams}
            exposedParams={customPaletteItems.find(p => p.kind === node.data.kind)?.exposedParams}
            onChange={update}
          />}
      </div>

      {/* Delete */}
      <div className="border-t border-slate-200 p-3">
        <button
          onClick={() => deleteNode(node.id)}
          className="w-full text-xs text-red-500 hover:text-red-600 hover:bg-red-50 rounded px-3 py-1.5 transition-colors border border-red-200"
        >
          Delete element
        </button>
      </div>
    </aside>
  )
}
