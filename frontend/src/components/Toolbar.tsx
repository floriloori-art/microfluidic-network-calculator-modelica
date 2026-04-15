import { useStore } from '../store'
import { runSimulation } from '../api'
import { type ElementKind } from '../types'
import { type Tab } from '../App'

export function Toolbar({
  activeTab,
  onTabChange,
}: {
  activeTab: Tab
  onTabChange: (tab: Tab) => void
}) {
  const {
    nodes, edges, isSimulating, simulationResult, errorMessage,
    setSimulating, setSimulationResult, setError, clearAll,
  } = useStore()

  const handleSimulate = async () => {
    if (nodes.length === 0) {
      setError('Add at least one element to the canvas first.')
      return
    }
    if (edges.length === 0) {
      setError('Connect elements before simulating.')
      return
    }

    setSimulating(true)
    setError(null)
    setSimulationResult(null)

    try {
      const bcs: Record<string, { pressure?: number; flow?: number }> = {}

      for (const node of nodes) {
        const kind = node.data.kind
        const params = node.data.params as Record<string, number>

        if (kind === 'chamber') {
          bcs[node.id] = { pressure: (params.density ?? 998.2) * 9.81 * (params.height ?? 0) }
        } else if (kind === 'pump') {
          bcs[node.id] = { pressure: params.pressure_generated }
        } else if (kind === 'pressure_source') {
          bcs[node.id] = { pressure: params.pressure }
        } else if (kind === 'pressure_ground') {
          bcs[node.id] = { pressure: params.p_ref ?? 0 }
        } else if (kind === 'open_end') {
          bcs[node.id] = { pressure: 0 }
        } else if (kind === 'flow_source') {
          bcs[node.id] = { flow: params.flow_rate }
        }
      }

      const hasOutgoing = new Set(edges.map(e => e.source))
      for (const node of nodes) {
        if (!hasOutgoing.has(node.id) && !bcs[node.id]) {
          bcs[node.id] = { pressure: 0 }
        }
      }

      const result = await runSimulation({
        nodes: nodes.map(n => ({ id: n.id, kind: n.data.kind as ElementKind, params: n.data.params })),
        edges: edges.map(e => ({ source: e.source, target: e.target })),
        boundary_conditions: bcs,
      })

      if (result.success) {
        setSimulationResult(result)
        useStore.setState(s => ({
          nodes: s.nodes.map(n => ({
            ...n,
            data: {
              ...n.data,
              pressure: result.pressures[n.id],
              flow: Object.entries(result.flows).find(
                ([key]) => key.startsWith(n.id + '->') || key.endsWith('->' + n.id)
              )?.[1],
            },
          })),
        }))
      } else {
        setError(result.error ?? 'Simulation failed')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error')
    } finally {
      setSimulating(false)
    }
  }

  return (
    <header className="h-13 bg-white border-b border-slate-200 flex items-center px-4 gap-4 shrink-0 shadow-sm">
      {/* Logo */}
      <div className="flex items-center gap-2 mr-2">
        <span className="text-blue-500 text-lg">🔬</span>
        <span className="text-sm font-semibold text-slate-700">MicroSim</span>
      </div>

      {/* Tab buttons */}
      <div className="flex items-center bg-slate-100 rounded-lg p-0.5 gap-0.5">
        <button
          onClick={() => onTabChange('simulator')}
          className={`
            px-4 py-1.5 rounded-md text-sm font-medium transition-all
            ${activeTab === 'simulator'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'}
          `}
        >
          Simulator
        </button>
        <button
          onClick={() => onTabChange('builder')}
          className={`
            px-4 py-1.5 rounded-md text-sm font-medium transition-all
            ${activeTab === 'builder'
              ? 'bg-white text-violet-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'}
          `}
        >
          Builder
        </button>
        <button
          onClick={() => onTabChange('import')}
          className={`
            px-4 py-1.5 rounded-md text-sm font-medium transition-all
            ${activeTab === 'import'
              ? 'bg-white text-emerald-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'}
          `}
        >
          Import
        </button>
        <button
          onClick={() => onTabChange('cad')}
          className={`
            px-4 py-1.5 rounded-md text-sm font-medium transition-all
            ${activeTab === 'cad'
              ? 'bg-white text-orange-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'}
          `}
        >
          3D CAD
        </button>
      </div>

      {/* Simulate (only in simulator tab) */}
      {activeTab === 'simulator' && (
        <>
          <button
            onClick={handleSimulate}
            disabled={isSimulating}
            className="
              flex items-center gap-2 px-5 py-1.5 rounded-lg text-sm font-medium
              bg-blue-500 hover:bg-blue-600 disabled:bg-slate-200 disabled:text-slate-400
              text-white transition-colors shadow-sm
            "
          >
            {isSimulating ? (
              <><span className="animate-spin inline-block">⟳</span> Simulating…</>
            ) : (
              <><span>▶</span> Simulate</>
            )}
          </button>

          <button
            onClick={clearAll}
            className="px-3 py-1.5 rounded-lg text-sm text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            Clear
          </button>
        </>
      )}

      {/* Status */}
      <div className="ml-auto flex items-center gap-3">
        {errorMessage && (
          <span className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1 max-w-xs truncate">
            ⚠ {errorMessage}
          </span>
        )}
        {simulationResult?.success && !errorMessage && (
          <span className="text-xs text-emerald-600 bg-emerald-50 border border-emerald-200 rounded px-2 py-1">
            ✓ Solved — {Object.keys(simulationResult.pressures).length} nodes
          </span>
        )}
        {activeTab === 'simulator' && (
          <span className="text-xs text-slate-400">
            {nodes.length} elements · {edges.length} connections
          </span>
        )}
      </div>
    </header>
  )
}
