/**
 * BlockList: Right panel showing all derived building blocks.
 * - Channels (with type, dimensions, resistance)
 * - Chambers
 * - Ports
 * - Junctions
 * - Manual components (pumps, valves)
 * - Editable parameters
 */

import { useCadImportStore } from '../CadImportStore'
import type {
  ExtractedChannel, ExtractedChamber,
  ExtractedPort, ExtractedJunction, ManualComponent,
} from '../CadImportStore'

// ── Formatting ─────────────────────────────────────────────────────────────

function fmtUm(v: number): string {
  if (v >= 1000) return `${(v / 1000).toFixed(1)} mm`
  return `${v.toFixed(0)} µm`
}

function fmtResistance(r: number): string {
  if (!isFinite(r) || r === 0) return '—'
  if (r >= 1e15) return `${(r / 1e15).toFixed(1)}e15`
  if (r >= 1e12) return `${(r / 1e12).toFixed(1)}e12`
  if (r >= 1e9) return `${(r / 1e9).toFixed(1)}e9`
  if (r >= 1e6) return `${(r / 1e6).toFixed(1)}e6`
  return r.toExponential(2)
}

// ── Component ──────────────────────────────────────────────────────────────

export function BlockList() {
  const analysis = useCadImportStore(s => s.analysis)
  const manualComponents = useCadImportStore(s => s.manualComponents)
  const selectedId = useCadImportStore(s => s.selectedId)
  const setSelected = useCadImportStore(s => s.setSelected)
  const setHovered = useCadImportStore(s => s.setHovered)
  const updateChannel = useCadImportStore(s => s.updateChannel)
  const updateChamber = useCadImportStore(s => s.updateChamber)
  const updateManualComponent = useCadImportStore(s => s.updateManualComponent)
  const removeManualComponent = useCadImportStore(s => s.removeManualComponent)

  if (!analysis) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400 text-sm">
        Load a STEP/IGES file to see building blocks
      </div>
    )
  }

  const { channels, chambers, ports, junctions } = analysis

  return (
    <div className="h-full overflow-y-auto p-3 space-y-4">
      {/* Summary */}
      <div className="text-xs text-slate-500 bg-slate-50 rounded-lg p-2.5 border border-slate-200">
        <span className="font-medium text-slate-700">Detected:</span>{' '}
        {channels.length} channels · {chambers.length} chambers · {ports.length} ports · {junctions.length} junctions
        {manualComponents.length > 0 && ` · ${manualComponents.length} manual`}
      </div>

      {/* Channels */}
      {channels.length > 0 && (
        <Section title="Channels" icon="━" count={channels.length}>
          {channels.map(ch => (
            <ChannelCard
              key={ch.id}
              channel={ch}
              isSelected={selectedId === ch.id}
              onSelect={() => setSelected(ch.id)}
              onHover={(h) => setHovered(h ? ch.id : null)}
              onUpdate={(updates) => updateChannel(ch.id, updates)}
            />
          ))}
        </Section>
      )}

      {/* Chambers */}
      {chambers.length > 0 && (
        <Section title="Chambers" icon="▭" count={chambers.length}>
          {chambers.map(ch => (
            <ChamberCard
              key={ch.id}
              chamber={ch}
              isSelected={selectedId === ch.id}
              onSelect={() => setSelected(ch.id)}
              onHover={(h) => setHovered(h ? ch.id : null)}
              onUpdate={(updates) => updateChamber(ch.id, updates)}
            />
          ))}
        </Section>
      )}

      {/* Ports */}
      {ports.length > 0 && (
        <Section title="Ports" icon="○" count={ports.length}>
          {ports.map(p => (
            <PortCard
              key={p.id}
              port={p}
              isSelected={selectedId === p.id}
              onSelect={() => setSelected(p.id)}
              onHover={(h) => setHovered(h ? p.id : null)}
            />
          ))}
        </Section>
      )}

      {/* Junctions */}
      {junctions.length > 0 && (
        <Section title="Junctions" icon="●" count={junctions.length}>
          {junctions.map(j => (
            <JunctionCard
              key={j.id}
              junction={j}
              isSelected={selectedId === j.id}
              onSelect={() => setSelected(j.id)}
              onHover={(h) => setHovered(h ? j.id : null)}
            />
          ))}
        </Section>
      )}

      {/* Manual Components */}
      {manualComponents.length > 0 && (
        <Section title="Manual Components" icon="◆" count={manualComponents.length}>
          {manualComponents.map(c => (
            <ManualComponentCard
              key={c.id}
              component={c}
              isSelected={selectedId === c.id}
              onSelect={() => setSelected(c.id)}
              onHover={(h) => setHovered(h ? c.id : null)}
              onUpdate={(updates) => updateManualComponent(c.id, updates)}
              onRemove={() => removeManualComponent(c.id)}
            />
          ))}
        </Section>
      )}
    </div>
  )
}

// ── Section ────────────────────────────────────────────────────────────────

function Section({ title, icon, count, children }: {
  title: string
  icon: string
  count: number
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-slate-400 text-sm">{icon}</span>
        <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">{title}</h3>
        <span className="text-xs text-slate-400 ml-auto">{count}</span>
      </div>
      <div className="space-y-1.5">{children}</div>
    </div>
  )
}

// ── Channel card ───────────────────────────────────────────────────────────

function ChannelCard({ channel, isSelected, onSelect, onHover, onUpdate }: {
  channel: ExtractedChannel
  isSelected: boolean
  onSelect: () => void
  onHover: (h: boolean) => void
  onUpdate: (updates: Partial<ExtractedChannel>) => void
}) {
  return (
    <div
      className={`p-2.5 rounded-lg border cursor-pointer transition-all ${
        isSelected
          ? 'border-violet-300 bg-violet-50 shadow-sm'
          : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm'
      }`}
      onClick={onSelect}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-slate-700">
          {channel.type === 'circular' ? '⊙ Circular' : '▬ Rectangular'} Channel
        </span>
        <span className="text-[10px] text-slate-400 font-mono">{channel.id}</span>
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
        {channel.type === 'circular' ? (
          <ParamRow label="Diameter" value={fmtUm((channel.radius ?? 50) * 2)} />
        ) : (
          <ParamRow label="Width" value={fmtUm(channel.width ?? 100)} />
        )}
        <ParamRow label="Height" value={fmtUm(channel.height)} />
        <ParamRow label="Length" value={fmtUm(channel.length)} />
        <ParamRow label="R" value={`${fmtResistance(channel.resistance)} Pa·s/m³`} />
      </div>

      {/* Editable fields when selected */}
      {isSelected && (
        <div className="mt-2 pt-2 border-t border-slate-200 space-y-1.5">
          {channel.type === 'circular' ? (
            <EditableParam
              label="Radius (µm)"
              value={channel.radius ?? 50}
              onChange={(v) => onUpdate({ radius: v })}
            />
          ) : (
            <EditableParam
              label="Width (µm)"
              value={channel.width ?? 100}
              onChange={(v) => onUpdate({ width: v })}
            />
          )}
          <EditableParam
            label="Height (µm)"
            value={channel.height}
            onChange={(v) => onUpdate({ height: v })}
          />
          <EditableParam
            label="Length (µm)"
            value={channel.length}
            onChange={(v) => onUpdate({ length: v })}
          />
        </div>
      )}
    </div>
  )
}

// ── Chamber card ───────────────────────────────────────────────────────────

function ChamberCard({ chamber, isSelected, onSelect, onHover, onUpdate }: {
  chamber: ExtractedChamber
  isSelected: boolean
  onSelect: () => void
  onHover: (h: boolean) => void
  onUpdate: (updates: Partial<ExtractedChamber>) => void
}) {
  return (
    <div
      className={`p-2.5 rounded-lg border cursor-pointer transition-all ${
        isSelected
          ? 'border-violet-300 bg-violet-50 shadow-sm'
          : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm'
      }`}
      onClick={onSelect}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-slate-700">▭ Chamber</span>
        <span className="text-[10px] text-slate-400 font-mono">{chamber.id}</span>
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
        <ParamRow label="Size" value={`${fmtUm(chamber.widthX)} × ${fmtUm(chamber.widthY)}`} />
        <ParamRow label="Height" value={fmtUm(chamber.height)} />
        <ParamRow label="Volume" value={`${(chamber.volume / 1e9).toFixed(2)} nL`} />
      </div>

      {isSelected && (
        <div className="mt-2 pt-2 border-t border-slate-200 space-y-1.5">
          <EditableParam label="Width X (µm)" value={chamber.widthX} onChange={(v) => onUpdate({ widthX: v })} />
          <EditableParam label="Width Y (µm)" value={chamber.widthY} onChange={(v) => onUpdate({ widthY: v })} />
          <EditableParam label="Height (µm)" value={chamber.height} onChange={(v) => onUpdate({ height: v })} />
        </div>
      )}
    </div>
  )
}

// ── Port card ──────────────────────────────────────────────────────────────

function PortCard({ port, isSelected, onSelect, onHover }: {
  port: ExtractedPort
  isSelected: boolean
  onSelect: () => void
  onHover: (h: boolean) => void
}) {
  return (
    <div
      className={`p-2 rounded-lg border cursor-pointer transition-all ${
        isSelected
          ? 'border-emerald-300 bg-emerald-50'
          : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
      onClick={onSelect}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
    >
      <div className="flex items-center gap-2">
        <span className="w-4 h-4 rounded-full border-2 border-emerald-500 flex items-center justify-center">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        </span>
        <span className="text-xs font-medium text-slate-700">{port.label}</span>
        <span className="text-[10px] text-slate-400 ml-auto">→ {port.connectedTo}</span>
      </div>
    </div>
  )
}

// ── Junction card ──────────────────────────────────────────────────────────

function JunctionCard({ junction, isSelected, onSelect, onHover }: {
  junction: ExtractedJunction
  isSelected: boolean
  onSelect: () => void
  onHover: (h: boolean) => void
}) {
  return (
    <div
      className={`p-2 rounded-lg border cursor-pointer transition-all ${
        isSelected
          ? 'border-violet-300 bg-violet-50'
          : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
      onClick={onSelect}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
    >
      <div className="flex items-center gap-2">
        <span className="w-3 h-3 rounded-full bg-slate-500" />
        <span className="text-xs text-slate-600">
          {junction.channelIds.length}-way junction
        </span>
        <span className="text-[10px] text-slate-400 ml-auto font-mono">{junction.id}</span>
      </div>
    </div>
  )
}

// ── Manual component card ──────────────────────────────────────────────────

function ManualComponentCard({ component, isSelected, onSelect, onHover, onUpdate, onRemove }: {
  component: ManualComponent
  isSelected: boolean
  onSelect: () => void
  onHover: (h: boolean) => void
  onUpdate: (updates: Partial<ManualComponent>) => void
  onRemove: () => void
}) {
  return (
    <div
      className={`p-2.5 rounded-lg border cursor-pointer transition-all ${
        isSelected
          ? 'border-amber-300 bg-amber-50 shadow-sm'
          : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm'
      }`}
      onClick={onSelect}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-amber-800">
          ◆ {component.label}
        </span>
        <button
          className="text-[10px] text-red-400 hover:text-red-600 px-1"
          onClick={(e) => { e.stopPropagation(); onRemove() }}
        >
          ✕
        </button>
      </div>

      <div className="text-[11px] text-slate-500">
        Type: {component.kind} · Attached to: {component.attachedTo || '—'}
      </div>

      {isSelected && (
        <div className="mt-2 pt-2 border-t border-slate-200 space-y-1.5">
          {Object.entries(component.params).map(([key, val]) => (
            <EditableParam
              key={key}
              label={key}
              value={val}
              onChange={(v) => onUpdate({ params: { ...component.params, [key]: v } })}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Reusable components ────────────────────────────────────────────────────

function ParamRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-400">{label}</span>
      <span className="text-slate-600 font-mono">{value}</span>
    </div>
  )
}

function EditableParam({ label, value, onChange }: {
  label: string
  value: number
  onChange: (v: number) => void
}) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-[11px] text-slate-500 min-w-[80px]">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => {
          const v = parseFloat(e.target.value)
          if (!isNaN(v)) onChange(v)
        }}
        onClick={(e) => e.stopPropagation()}
        className="flex-1 text-[11px] px-1.5 py-0.5 rounded border border-slate-200 bg-white
                   focus:outline-none focus:ring-1 focus:ring-violet-400 focus:border-violet-400
                   text-slate-700 font-mono"
      />
    </div>
  )
}
