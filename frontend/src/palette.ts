import axios from 'axios'
import { type PaletteItem, type CompositeParams, type ExposedParam } from './types'

export const BUILTIN_PALETTE_ITEMS: PaletteItem[] = [
  {
    kind: 'circular_channel',
    label: 'Circular Channel',
    icon: '⬤',
    color: '#3b82f6',
    defaultParams: { radius: 100e-6, length: 0.01, viscosity: 1e-3 },
  },
  {
    kind: 'rectangular_channel',
    label: 'Rect. Channel',
    icon: '▬',
    color: '#6366f1',
    defaultParams: { width: 200e-6, height: 100e-6, length: 0.01, viscosity: 1e-3 },
  },
  {
    kind: 'chamber',
    label: 'Chamber',
    icon: '⬡',
    color: '#0ea5e9',
    defaultParams: { height: 500e-6, density: 998.2 },
  },
  {
    kind: 'pump',
    label: 'Pump',
    icon: '⟳',
    color: '#10b981',
    defaultParams: { pressure_generated: 1000, flow_max: 1e-6 },
  },
  {
    kind: 'valve',
    label: 'Valve',
    icon: '⧖',
    color: '#f59e0b',
    defaultParams: { opening: 1.0, kv: 0.031623 },
  },
  // ── Primitive building blocks ──────────────────────────────────────────────
  {
    kind: 'linear_resistance',
    label: 'Resistance',
    icon: '⊟',
    color: '#8b5cf6',
    defaultParams: { resistance: 1e9 },
  },
  {
    kind: 'pressure_source',
    label: 'Pressure Source',
    icon: '⊕',
    color: '#ec4899',
    defaultParams: { pressure: 1000 },
  },
  {
    kind: 'pressure_ground',
    label: 'P-Ground',
    icon: '⏚',
    color: '#64748b',
    defaultParams: { p_ref: 0 },
  },
  {
    kind: 'open_end',
    label: 'Open End',
    icon: '○',
    color: '#94a3b8',
    defaultParams: {},
  },
  {
    kind: 'flow_source',
    label: 'Flow Source',
    icon: '⇒',
    color: '#14b8a6',
    defaultParams: { flow_rate: 1e-9 },
  },
  {
    kind: 'check_valve',
    label: 'Check Valve',
    icon: '⊳',
    color: '#f97316',
    defaultParams: { r_fwd: 1e6, r_rev: 1e14 },
  },
]

export const KIND_META: Record<string, { color: string; icon: string; label: string }> =
  Object.fromEntries(BUILTIN_PALETTE_ITEMS.map(p => [p.kind, { color: p.color, icon: p.icon, label: p.label }]))

/** Merge custom palette items into KIND_META at runtime */
export function registerCustomMeta(items: PaletteItem[]) {
  for (const p of items) {
    KIND_META[p.kind] = { color: p.color, icon: p.icon, label: p.label }
  }
}

const client = axios.create({ baseURL: '/api' })

/** Fetch custom composite palette items from backend */
export async function fetchCustomPalette(): Promise<PaletteItem[]> {
  try {
    const resp = await client.get('/components/palette/items')
    const items: PaletteItem[] = (resp.data as Array<{
      kind: string; label: string; icon: string; color: string
      ports: string[]; default_params: Record<string, number>
      exposed_params?: ExposedParam[]
    }>).map(raw => {
      const compName = raw.kind.replace('composite:', '')
      const defaultParams: CompositeParams = { component_name: compName }
      // Pre-fill defaults from exposed params
      if (raw.exposed_params) {
        for (const ep of raw.exposed_params) {
          defaultParams[`${ep.element_id}.${ep.param}`] = ep.default
        }
      }
      return {
        kind: raw.kind as `composite:${string}`,
        label: raw.label,
        icon: raw.icon,
        color: raw.color,
        defaultParams,
        exposedParams: raw.exposed_params,
      }
    })
    return items
  } catch {
    console.warn('Failed to fetch custom palette – backend may be offline')
    return []
  }
}
