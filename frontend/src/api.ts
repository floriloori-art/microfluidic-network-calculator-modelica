import axios from 'axios'
import {
  type SimulateRequest, type SimulateResponse, type ElementKind, type ElementParams,
  type LinearResistanceParams, type PressureSourceParams, type PressureGroundParams,
  type FlowSourceParams, type CheckValveParams, type CompositeParams,
} from './types'

const client = axios.create({ baseURL: '/api' })

// ─── Map frontend params → backend parameters dict ───────────────────────────
// Backend expects: { element_id, name, element_type, parameters: { ...flat } }

function buildParameters(kind: ElementKind, params: ElementParams): Record<string, number | boolean> {
  switch (kind) {
    case 'circular_channel': {
      const p = params as { radius: number; length: number; viscosity: number }
      return { radius: p.radius, length: p.length, viscosity: p.viscosity }
    }
    case 'rectangular_channel': {
      const p = params as { width: number; height: number; length: number; viscosity: number }
      return { width: p.width, height: p.height, length: p.length, viscosity: p.viscosity }
    }
    case 'chamber': {
      const p = params as { height: number; density: number }
      return { height: p.height, density: p.density }
    }
    case 'pump': {
      const p = params as { pressure_generated: number; flow_max: number }
      return { pressure_generated: p.pressure_generated, flow_max: p.flow_max }
    }
    case 'valve': {
      const p = params as { opening: number; kv: number }
      return { opening: p.opening, kv: p.kv }
    }
    case 'linear_resistance': {
      const p = params as LinearResistanceParams
      return { resistance: p.resistance }
    }
    case 'pressure_source': {
      const p = params as PressureSourceParams
      return { pressure: p.pressure }
    }
    case 'pressure_ground': {
      const p = params as PressureGroundParams
      return { p_ref: p.p_ref }
    }
    case 'open_end': {
      return {}
    }
    case 'flow_source': {
      const p = params as FlowSourceParams
      return { flow_rate: p.flow_rate }
    }
    case 'check_valve': {
      const p = params as CheckValveParams
      return { r_fwd: p.r_fwd, r_rev: p.r_rev }
    }
    default: {
      // Composite elements: kind is "composite:<name>"
      if (kind.startsWith('composite:')) {
        const p = params as CompositeParams
        // Pass all params through — backend handles component_name + overrides
        const result: Record<string, number | string | boolean> = {}
        for (const [k, v] of Object.entries(p)) {
          result[k] = v
        }
        return result
      }
      return {}
    }
  }
}

// ─── Simulate ─────────────────────────────────────────────────────────────────
// Real backend routes (all under /network prefix):
//   POST /network/create
//   POST /network/{id}/element     body: { element_id, name, element_type, parameters }
//   POST /network/{id}/connect     body: { element_id_1, element_id_2 }
//   POST /network/{id}/simulate    body: { boundary_conditions: [{element_id, pressure?, flow?}] }

export async function runSimulation(req: SimulateRequest): Promise<SimulateResponse> {
  try {
    // 1. Create network
    const createResp = await client.post('/network/create', { name: 'frontend_network' })
    const networkId: string = createResp.data.network_id

    // 2. Add all elements
    for (const node of req.nodes) {
      // Map "composite:xxx" kinds → "composite" element_type for backend
      const elementType = node.kind.startsWith('composite:') ? 'composite' : node.kind
      await client.post(`/network/${networkId}/element`, {
        element_id: node.id,
        name: node.id,
        element_type: elementType,
        parameters: buildParameters(node.kind, node.params),
      })
    }

    // 3. Connect edges
    for (const edge of req.edges) {
      await client.post(`/network/${networkId}/connect`, {
        element_id_1: edge.source,
        element_id_2: edge.target,
      })
    }

    // 4. Run simulation (BCs go directly into the simulate call)
    const bcList = Object.entries(req.boundary_conditions).map(([element_id, bc]) => ({
      element_id,
      ...(bc.pressure !== undefined ? { pressure: bc.pressure } : {}),
      ...(bc.flow !== undefined ? { flow: bc.flow } : {}),
    }))

    const simResp = await client.post(`/network/${networkId}/simulate`, {
      boundary_conditions: bcList,
    })

    const data = simResp.data

    // 5. Clean up network (fire and forget)
    client.delete(`/network/${networkId}`).catch(() => {})

    return {
      success: true,
      pressures: data.pressures ?? {},
      flows: data.flows ?? {},
    }
  } catch (err: unknown) {
    const msg =
      axios.isAxiosError(err)
        ? err.response?.data?.detail ?? err.message
        : String(err)
    return { success: false, pressures: {}, flows: {}, error: msg }
  }
}

export async function checkBackend(): Promise<boolean> {
  try {
    await client.get('/health')
    return true
  } catch {
    return false
  }
}
