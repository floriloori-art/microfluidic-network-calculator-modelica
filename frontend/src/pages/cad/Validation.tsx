/**
 * Validation: Status bar showing validation issues and the "Send to Simulator" button.
 */

import { useCadImportStore } from '../CadImportStore'

export function ValidationBar() {
  const validate = useCadImportStore(s => s.validate)
  const analysis = useCadImportStore(s => s.analysis)

  if (!analysis) return null

  const issues = validate()
  const errors = issues.filter(i => i.severity === 'error')
  const warnings = issues.filter(i => i.severity === 'warning')

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-white border-t border-slate-200 text-xs">
      {/* Summary */}
      <div className="flex items-center gap-3">
        <span className="text-slate-500">
          {analysis.channels.length} channels · {analysis.chambers.length} chambers · {analysis.ports.length} ports
        </span>
      </div>

      {/* Issues */}
      <div className="flex items-center gap-2 ml-auto">
        {errors.map((e, i) => (
          <span key={`e${i}`} className="text-red-600 bg-red-50 border border-red-200 rounded px-2 py-0.5">
            {e.message}
          </span>
        ))}
        {warnings.map((w, i) => (
          <span key={`w${i}`} className="text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-0.5">
            {w.message}
          </span>
        ))}
        {issues.length === 0 && (
          <span className="text-emerald-600 bg-emerald-50 border border-emerald-200 rounded px-2 py-0.5">
            Network valid
          </span>
        )}
      </div>
    </div>
  )
}
