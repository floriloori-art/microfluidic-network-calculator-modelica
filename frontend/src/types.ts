// ─── Element types ────────────────────────────────────────────────────────────

export type BuiltinElementKind =
  | 'circular_channel' | 'rectangular_channel' | 'chamber' | 'pump' | 'valve'
  | 'linear_resistance' | 'pressure_source' | 'pressure_ground' | 'open_end'
  | 'flow_source' | 'check_valve'

// Composite kinds are dynamic: "composite:<name>" (e.g. "composite:two_resistor")
export type ElementKind = BuiltinElementKind | `composite:${string}`

export interface CircularChannelParams {
  radius: number      // m  (e.g. 100e-6)
  length: number      // m  (e.g. 0.01)
  viscosity: number   // Pa·s
}

export interface RectangularChannelParams {
  width: number       // m
  height: number      // m
  length: number      // m
  viscosity: number   // Pa·s
}

export interface ChamberParams {
  height: number      // m  (fluid column)
  density: number     // kg/m³
}

export interface PumpParams {
  pressure_generated: number  // Pa
  flow_max: number            // m³/s
}

export interface ValveParams {
  opening: number   // 0..1
  kv: number        // m³/(s·√Pa)
}

export interface LinearResistanceParams {
  resistance: number  // Pa·s/m³
}

export interface PressureSourceParams {
  pressure: number    // Pa (gauge)
}

export interface PressureGroundParams {
  p_ref: number       // Pa (default 0)
}

export interface OpenEndParams {
  // no parameters – P always 0 Pa
}

export interface FlowSourceParams {
  flow_rate: number   // m³/s (positive = inject)
}

export interface CheckValveParams {
  r_fwd: number       // Pa·s/m³ (default 1e6)
  r_rev: number       // Pa·s/m³ (default 1e14)
}

// Generic params for composite elements — keys are "elementId.param" overrides
export interface CompositeParams {
  component_name: string
  [key: string]: number | string
}

export type ElementParams =
  | CircularChannelParams
  | RectangularChannelParams
  | ChamberParams
  | PumpParams
  | ValveParams
  | LinearResistanceParams
  | PressureSourceParams
  | PressureGroundParams
  | OpenEndParams
  | FlowSourceParams
  | CheckValveParams
  | CompositeParams

// ─── Node data stored in React Flow ───────────────────────────────────────────
// Must extend Record<string, unknown> to satisfy @xyflow/react v12 constraints

export interface FluidNodeData extends Record<string, unknown> {
  kind: ElementKind
  label: string
  params: ElementParams
  // Results filled after simulation
  pressure?: number        // Pa at this node
  flow?: number            // m³/s through element
}

// ─── API types ────────────────────────────────────────────────────────────────

export interface BoundaryCondition {
  pressure?: number
  flow?: number
}

export interface SimulateRequest {
  nodes: Array<{ id: string; kind: ElementKind; params: ElementParams }>
  edges: Array<{ source: string; target: string }>
  boundary_conditions: Record<string, BoundaryCondition>
}

export interface SimulateResponse {
  success: boolean
  pressures: Record<string, number>
  flows: Record<string, number>
  error?: string
}

// ─── Palette entry ────────────────────────────────────────────────────────────

export interface ExposedParam {
  element_id: string
  param: string
  label: string
  default: number
}

export interface PaletteItem {
  kind: ElementKind
  label: string
  icon: string
  color: string
  defaultParams: ElementParams
  /** Only set on composite palette items */
  exposedParams?: ExposedParam[]
}
