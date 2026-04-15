/**
 * NetworkDeriver: Computes hydraulic resistances from extracted geometry
 * and builds the final 1D network representation.
 *
 * Uses the same physics formulas as the backend:
 *   Circular:     R = 8ηL / (π r⁴)
 *   Rectangular:  R = 12ηL / (w h³) · 1/[1 - (192h)/(π⁵w) · Σ tanh(nπw/2h)/n⁵]
 */

import type {
  AnalysisResult, ExtractedChannel,
} from '../CadImportStore'

const PI = Math.PI

// ── Resistance formulas ────────────────────────────────────────────────────

/**
 * Hagen-Poiseuille resistance for circular channel.
 * R = 8 η L / (π r⁴)
 *
 * @param radius   m
 * @param length   m
 * @param viscosity Pa·s
 */
export function circularResistance(radius: number, length: number, viscosity: number): number {
  if (radius <= 0 || length <= 0) return Infinity
  return (8 * viscosity * length) / (PI * radius ** 4)
}

/**
 * Rectangular channel resistance using series expansion.
 * R = 12 η L / (w h³) · 1 / [1 - (192h)/(π⁵w) · Σ_{n=1,3,5,...}^N tanh(nπw/(2h))/n⁵]
 *
 * @param width    m  (larger dimension)
 * @param height   m  (smaller dimension)
 * @param length   m
 * @param viscosity Pa·s
 */
export function rectangularResistance(
  width: number, height: number, length: number, viscosity: number,
): number {
  if (width <= 0 || height <= 0 || length <= 0) return Infinity

  // Ensure width >= height for the formula
  let w = width, h = height
  if (h > w) { [w, h] = [h, w] }

  const baseR = (12 * viscosity * length) / (w * h ** 3)

  // Series correction
  let seriesSum = 0
  for (let n = 1; n <= 99; n += 2) {
    const term = Math.tanh(n * PI * w / (2 * h)) / (n ** 5)
    seriesSum += term
    if (term < 1e-12) break
  }

  const correction = 1 - (192 * h) / (PI ** 5 * w) * seriesSum
  if (correction <= 0) return baseR

  return baseR / correction
}

// ── Compute all resistances ────────────────────────────────────────────────

/**
 * Update all channel resistances in the analysis result.
 * Coordinates in analysis are in µm — convert to m for physics.
 */
export function computeResistances(
  analysis: AnalysisResult,
  viscosity: number = 0.001, // Pa·s (water)
): AnalysisResult {
  const um2m = 1e-6

  const channels: ExtractedChannel[] = analysis.channels.map(ch => {
    let resistance: number

    if (ch.type === 'circular') {
      const r = (ch.radius ?? 50) * um2m
      const L = ch.length * um2m
      resistance = circularResistance(r, L, viscosity)
    } else {
      const w = (ch.width ?? 100) * um2m
      const h = ch.height * um2m
      const L = ch.length * um2m
      resistance = rectangularResistance(w, h, L, viscosity)
    }

    return { ...ch, resistance }
  })

  return { ...analysis, channels }
}

// ── Network summary ────────────────────────────────────────────────────────

export interface NetworkSummary {
  totalChannels: number
  totalChambers: number
  totalPorts: number
  totalJunctions: number
  totalResistance: number  // rough estimate: series sum
  heightLayers: number
  minChannelWidth: number  // µm
  maxChannelWidth: number  // µm
}

export function summarizeNetwork(analysis: AnalysisResult): NetworkSummary {
  const widths = analysis.channels.map(ch =>
    ch.type === 'circular' ? (ch.radius ?? 50) * 2 : (ch.width ?? 100)
  )

  return {
    totalChannels: analysis.channels.length,
    totalChambers: analysis.chambers.length,
    totalPorts: analysis.ports.length,
    totalJunctions: analysis.junctions.length,
    totalResistance: analysis.channels.reduce((s, ch) => s + ch.resistance, 0),
    heightLayers: analysis.heightLayers.length,
    minChannelWidth: widths.length > 0 ? Math.min(...widths) : 0,
    maxChannelWidth: widths.length > 0 ? Math.max(...widths) : 0,
  }
}
