import { type Edge } from '@xyflow/react'
import { type FluidNode } from './store'
import { type FluidNodeData } from './types'

function node(id: string, kind: FluidNodeData['kind'], label: string, params: FluidNodeData['params'], x: number, y: number): FluidNode {
  return { id, type: 'fluid', position: { x, y }, data: { kind, label, params } }
}

function edge(id: string, source: string, target: string): Edge {
  return { id, source, target, animated: true, style: { stroke: '#475569', strokeWidth: 2 } }
}

// ── Simple Channel: Pump → CircularChannel → Chamber(outlet) ─────────────────
export const PRESET_SIMPLE_CHANNEL: { nodes: FluidNode[]; edges: Edge[] } = {
  nodes: [
    node('pump_1',    'pump',             'Pump 1',     { pressure_generated: 1000, flow_max: 1e-6 }, 80,  180),
    node('ch_1',      'circular_channel', 'Channel 1',  { radius: 100e-6, length: 0.01, viscosity: 1e-3 }, 280, 180),
    node('outlet_1',  'chamber',          'Outlet 1',   { height: 0, density: 998.2 },                480, 180),
  ],
  edges: [
    edge('e1', 'pump_1', 'ch_1'),
    edge('e2', 'ch_1',   'outlet_1'),
  ],
}

// ── Pump + Valve: Pump → Valve → Channel → Chamber ───────────────────────────
export const PRESET_PUMP_VALVE: { nodes: FluidNode[]; edges: Edge[] } = {
  nodes: [
    node('pump_1',   'pump',             'Pump 1',    { pressure_generated: 2000, flow_max: 2e-6 }, 60,  180),
    node('valve_1',  'valve',            'Valve 1',   { opening: 0.75, kv: 0.031623 },              260, 180),
    node('ch_1',     'circular_channel', 'Channel 1', { radius: 80e-6, length: 0.02, viscosity: 1e-3 }, 460, 180),
    node('outlet_1', 'chamber',          'Outlet 1',  { height: 0, density: 998.2 },                660, 180),
  ],
  edges: [
    edge('e1', 'pump_1',  'valve_1'),
    edge('e2', 'valve_1', 'ch_1'),
    edge('e3', 'ch_1',    'outlet_1'),
  ],
}

// ── T-Junction: Pump → 2 parallel channels → Chamber ────────────────────────
export const PRESET_T_JUNCTION: { nodes: FluidNode[]; edges: Edge[] } = {
  nodes: [
    node('pump_1',   'pump',             'Pump 1',    { pressure_generated: 1000, flow_max: 1e-6 }, 80,  200),
    node('ch_top',   'circular_channel', 'Channel A', { radius: 100e-6, length: 0.01, viscosity: 1e-3 }, 280, 120),
    node('ch_bot',   'circular_channel', 'Channel B', { radius: 100e-6, length: 0.02, viscosity: 1e-3 }, 280, 280),
    node('outlet_1', 'chamber',          'Outlet 1',  { height: 0, density: 998.2 },                480, 200),
  ],
  edges: [
    edge('e1', 'pump_1',  'ch_top'),
    edge('e2', 'pump_1',  'ch_bot'),
    edge('e3', 'ch_top',  'outlet_1'),
    edge('e4', 'ch_bot',  'outlet_1'),
  ],
}
