/**
 * GeometryAnalyzer: Converts parsed B-Rep topology (3D) into a 2D feature map.
 *
 * Pipeline:  ParsedTopology → height-layer clustering → channel detection
 *            → chamber detection → port detection → junction detection
 *            → AnalysisResult
 *
 * All output coordinates are in µm (micrometers).
 */

import type { ParsedTopology, ParsedSolid, ParsedFace, ParsedEdge } from './StepParser.worker'
import type {
  AnalysisResult, ExtractedChannel, ExtractedChamber,
  ExtractedPort, ExtractedJunction, Vec2,
} from '../CadImportStore'

// ── Unit conversion ────────────────────────────────────────────────────────

const UNIT_TO_UM: Record<string, number> = {
  'um': 1,
  'µm': 1,
  'mm': 1000,
  'cm': 10000,
  'm': 1e6,
  'inch': 25400,
  'in': 25400,
}

function toMicrons(value: number, unit: string): number {
  return value * (UNIT_TO_UM[unit.toLowerCase()] ?? 1000) // default mm
}

// ── Height-layer analysis ──────────────────────────────────────────────────

interface HeightLayer {
  zMin: number   // µm
  zMax: number   // µm
  height: number // µm (zMax - zMin)
  faceIds: number[]
}

/**
 * Cluster faces by their Z-extent to find distinct height layers.
 * Microfluidic chips typically have 2-5 height layers.
 */
function findHeightLayers(faces: ParsedFace[], unit: string, tolerance: number = 5): HeightLayer[] {
  // Collect unique Z-extents
  const zExtents: { zMin: number; zMax: number; faceId: number }[] = []

  for (const face of faces) {
    const zMin = toMicrons(face.bounds.minZ, unit)
    const zMax = toMicrons(face.bounds.maxZ, unit)
    const height = zMax - zMin
    if (height > tolerance) { // skip flat faces (top/bottom surfaces)
      zExtents.push({ zMin, zMax, faceId: face.id })
    }
  }

  // Cluster by similar height
  const layers: HeightLayer[] = []
  for (const ext of zExtents) {
    const height = ext.zMax - ext.zMin
    const existing = layers.find(l => Math.abs(l.height - height) < tolerance)
    if (existing) {
      existing.faceIds.push(ext.faceId)
      existing.zMin = Math.min(existing.zMin, ext.zMin)
      existing.zMax = Math.max(existing.zMax, ext.zMax)
    } else {
      layers.push({ zMin: ext.zMin, zMax: ext.zMax, height, faceIds: [ext.faceId] })
    }
  }

  return layers.sort((a, b) => a.height - b.height)
}

// ── Channel detection ──────────────────────────────────────────────────────

/**
 * Detect channels: elongated features with aspect ratio > 3
 * and small cross-section relative to length.
 */
function detectChannels(
  solid: ParsedSolid,
  unit: string,
): ExtractedChannel[] {
  const channels: ExtractedChannel[] = []

  // Strategy 1: Find cylindrical faces → circular channels
  const cylFaces = solid.faces.filter(f => f.type === 'cylinder' && f.radius != null)
  const usedCylFaceIds = new Set<number>()

  for (const face of cylFaces) {
    if (usedCylFaceIds.has(face.id)) continue

    const r = toMicrons(face.radius!, unit)
    // Microfluidic channel radii: typically 10-500 µm
    if (r < 1 || r > 5000) continue

    const length = toMicrons(
      Math.max(
        face.bounds.maxX - face.bounds.minX,
        face.bounds.maxY - face.bounds.minY,
      ),
      unit,
    )
    const height = toMicrons(face.bounds.maxZ - face.bounds.minZ, unit)

    if (length < r * 2) continue // too short to be a channel

    // Project centerline to 2D
    const cx = toMicrons((face.bounds.minX + face.bounds.maxX) / 2, unit)
    const cy = toMicrons((face.bounds.minY + face.bounds.maxY) / 2, unit)

    // Determine orientation
    const dx = toMicrons(face.bounds.maxX - face.bounds.minX, unit)
    const dy = toMicrons(face.bounds.maxY - face.bounds.minY, unit)

    let start: Vec2, end: Vec2
    if (dx >= dy) {
      start = { x: toMicrons(face.bounds.minX, unit), y: cy }
      end = { x: toMicrons(face.bounds.maxX, unit), y: cy }
    } else {
      start = { x: cx, y: toMicrons(face.bounds.minY, unit) }
      end = { x: cx, y: toMicrons(face.bounds.maxY, unit) }
    }

    channels.push({
      id: `ch_cir_${channels.length}`,
      type: 'circular',
      start, end,
      radius: r,
      height,
      length: Math.max(dx, dy),
      resistance: 0, // computed later by NetworkDeriver
    })
    usedCylFaceIds.add(face.id)
  }

  // Strategy 2: Find elongated rectangular voids → rectangular channels
  // Group plane faces that form rectangular cross-sections
  const planeFaces = solid.faces.filter(f => f.type === 'plane' && f.normal)

  // Find pairs of opposing horizontal planes (top/bottom of channel)
  const horizontalFaces = planeFaces.filter(f => {
    const n = f.normal!
    return Math.abs(n[2]) > 0.9 // Z-normal → horizontal
  })

  // Group by similar X/Y extent
  const groups = groupFacesByOverlap(horizontalFaces, unit)

  for (const group of groups) {
    if (group.length < 2) continue

    const zValues = group.map(f => toMicrons(f.bounds.minZ, unit))
      .concat(group.map(f => toMicrons(f.bounds.maxZ, unit)))
    const zMin = Math.min(...zValues)
    const zMax = Math.max(...zValues)
    const height = zMax - zMin
    if (height < 1) continue // too thin

    const minX = Math.min(...group.map(f => toMicrons(f.bounds.minX, unit)))
    const maxX = Math.max(...group.map(f => toMicrons(f.bounds.maxX, unit)))
    const minY = Math.min(...group.map(f => toMicrons(f.bounds.minY, unit)))
    const maxY = Math.max(...group.map(f => toMicrons(f.bounds.maxY, unit)))

    const dx = maxX - minX
    const dy = maxY - minY
    const width = Math.min(dx, dy)
    const length = Math.max(dx, dy)

    // Channel: elongated (length/width > 3) and small width (< 2000 µm)
    if (length / width < 3 || width > 2000) continue

    const cx = (minX + maxX) / 2
    const cy = (minY + maxY) / 2

    let start: Vec2, end: Vec2
    if (dx >= dy) {
      start = { x: minX, y: cy }
      end = { x: maxX, y: cy }
    } else {
      start = { x: cx, y: minY }
      end = { x: cx, y: maxY }
    }

    // Avoid duplicates with circular channels
    const isDuplicate = channels.some(ch => {
      const d = Math.sqrt((ch.start.x - start.x) ** 2 + (ch.start.y - start.y) ** 2)
      return d < width
    })
    if (isDuplicate) continue

    channels.push({
      id: `ch_rect_${channels.length}`,
      type: 'rectangular',
      start, end,
      width,
      height,
      length,
      resistance: 0,
    })
  }

  return channels
}

/**
 * Group horizontal plane faces by overlapping X/Y extents.
 */
function groupFacesByOverlap(faces: ParsedFace[], unit: string, tolerance: number = 50): ParsedFace[][] {
  const groups: ParsedFace[][] = []
  const used = new Set<number>()

  for (const face of faces) {
    if (used.has(face.id)) continue

    const group = [face]
    used.add(face.id)

    for (const other of faces) {
      if (used.has(other.id)) continue

      // Check X/Y overlap
      const overlap = rangesOverlap(
        toMicrons(face.bounds.minX, unit), toMicrons(face.bounds.maxX, unit),
        toMicrons(other.bounds.minX, unit), toMicrons(other.bounds.maxX, unit),
        tolerance,
      ) && rangesOverlap(
        toMicrons(face.bounds.minY, unit), toMicrons(face.bounds.maxY, unit),
        toMicrons(other.bounds.minY, unit), toMicrons(other.bounds.maxY, unit),
        tolerance,
      )

      if (overlap) {
        group.push(other)
        used.add(other.id)
      }
    }
    groups.push(group)
  }

  return groups
}

function rangesOverlap(a1: number, a2: number, b1: number, b2: number, tol: number): boolean {
  return a1 - tol <= b2 && b1 - tol <= a2
}

// ── Chamber detection ──────────────────────────────────────────────────────

function detectChambers(
  solid: ParsedSolid,
  channels: ExtractedChannel[],
  unit: string,
): ExtractedChamber[] {
  const chambers: ExtractedChamber[] = []

  // Chambers: regions with low aspect ratio (width ~ height in XY) and significant volume
  const horizontalFaces = solid.faces.filter(f =>
    f.type === 'plane' && f.normal && Math.abs(f.normal[2]) > 0.9
  )

  const groups = groupFacesByOverlap(horizontalFaces, unit)

  for (const group of groups) {
    if (group.length < 2) continue

    const minX = Math.min(...group.map(f => toMicrons(f.bounds.minX, unit)))
    const maxX = Math.max(...group.map(f => toMicrons(f.bounds.maxX, unit)))
    const minY = Math.min(...group.map(f => toMicrons(f.bounds.minY, unit)))
    const maxY = Math.max(...group.map(f => toMicrons(f.bounds.maxY, unit)))
    const zValues = group.map(f => toMicrons(f.bounds.minZ, unit))
      .concat(group.map(f => toMicrons(f.bounds.maxZ, unit)))
    const zMin = Math.min(...zValues)
    const zMax = Math.max(...zValues)

    const dx = maxX - minX
    const dy = maxY - minY
    const height = zMax - zMin
    const aspectRatio = Math.max(dx, dy) / (Math.min(dx, dy) || 1)

    // Chamber: non-elongated (aspect < 3) and minimum size
    if (aspectRatio >= 3 || Math.min(dx, dy) < 100 || height < 1) continue

    // Not already a channel
    const center: Vec2 = { x: (minX + maxX) / 2, y: (minY + maxY) / 2 }
    const isChannel = channels.some(ch => {
      const mid = { x: (ch.start.x + ch.end.x) / 2, y: (ch.start.y + ch.end.y) / 2 }
      return Math.sqrt((mid.x - center.x) ** 2 + (mid.y - center.y) ** 2) < Math.max(dx, dy) * 0.5
    })
    if (isChannel) continue

    chambers.push({
      id: `chamber_${chambers.length}`,
      center,
      widthX: dx,
      widthY: dy,
      height,
      volume: dx * dy * height, // approximate
    })
  }

  return chambers
}

// ── Port detection ─────────────────────────────────────────────────────────

function detectPorts(
  channels: ExtractedChannel[],
  junctions: ExtractedJunction[],
  bounds: AnalysisResult['bounds'],
  tolerance: number = 100,
): ExtractedPort[] {
  const ports: ExtractedPort[] = []
  const connectedEndpoints = new Set<string>()

  // Mark junction endpoints
  for (const junc of junctions) {
    connectedEndpoints.add(`${Math.round(junc.position.x)},${Math.round(junc.position.y)}`)
  }

  // Channel endpoints near chip boundary → ports
  let portIdx = 0
  for (const ch of channels) {
    for (const pt of [ch.start, ch.end]) {
      const key = `${Math.round(pt.x)},${Math.round(pt.y)}`
      if (connectedEndpoints.has(key)) continue

      const nearBoundary =
        Math.abs(pt.x - bounds.minX) < tolerance ||
        Math.abs(pt.x - bounds.maxX) < tolerance ||
        Math.abs(pt.y - bounds.minY) < tolerance ||
        Math.abs(pt.y - bounds.maxY) < tolerance

      if (nearBoundary) {
        const label = `Port ${String.fromCharCode(65 + portIdx)}` // A, B, C, ...
        ports.push({
          id: `port_${portIdx}`,
          position: { x: pt.x, y: pt.y },
          label,
          connectedTo: ch.id,
        })
        connectedEndpoints.add(key)
        portIdx++
      }
    }
  }

  // Also: channel endpoints that are NOT connected to anything → open ends
  for (const ch of channels) {
    for (const pt of [ch.start, ch.end]) {
      const key = `${Math.round(pt.x)},${Math.round(pt.y)}`
      if (connectedEndpoints.has(key)) continue

      const label = `Port ${String.fromCharCode(65 + portIdx)}`
      ports.push({
        id: `port_${portIdx}`,
        position: { x: pt.x, y: pt.y },
        label,
        connectedTo: ch.id,
      })
      connectedEndpoints.add(key)
      portIdx++
    }
  }

  return ports
}

// ── Junction detection ─────────────────────────────────────────────────────

function detectJunctions(
  channels: ExtractedChannel[],
  chambers: ExtractedChamber[],
  tolerance: number = 50,
): ExtractedJunction[] {
  const junctions: ExtractedJunction[] = []

  // Collect all channel endpoints
  const endpoints: { point: Vec2; channelId: string }[] = []
  for (const ch of channels) {
    endpoints.push({ point: ch.start, channelId: ch.id })
    endpoints.push({ point: ch.end, channelId: ch.id })
  }

  // Cluster nearby endpoints
  const used = new Set<number>()
  for (let i = 0; i < endpoints.length; i++) {
    if (used.has(i)) continue

    const cluster = [i]
    used.add(i)

    for (let j = i + 1; j < endpoints.length; j++) {
      if (used.has(j)) continue
      const d = Math.sqrt(
        (endpoints[i].point.x - endpoints[j].point.x) ** 2 +
        (endpoints[i].point.y - endpoints[j].point.y) ** 2,
      )
      if (d < tolerance) {
        cluster.push(j)
        used.add(j)
      }
    }

    // A junction needs ≥2 channel endpoints meeting
    if (cluster.length >= 2) {
      const channelIds = [...new Set(cluster.map(idx => endpoints[idx].channelId))]
      if (channelIds.length >= 2) {
        const avgX = cluster.reduce((s, idx) => s + endpoints[idx].point.x, 0) / cluster.length
        const avgY = cluster.reduce((s, idx) => s + endpoints[idx].point.y, 0) / cluster.length

        junctions.push({
          id: `junc_${junctions.length}`,
          position: { x: avgX, y: avgY },
          channelIds,
        })
      }
    }
  }

  // Also check channel endpoints near chamber centers
  for (const chamber of chambers) {
    const nearbyChannels: string[] = []
    for (const ep of endpoints) {
      const d = Math.sqrt(
        (ep.point.x - chamber.center.x) ** 2 +
        (ep.point.y - chamber.center.y) ** 2,
      )
      if (d < Math.max(chamber.widthX, chamber.widthY)) {
        nearbyChannels.push(ep.channelId)
      }
    }
    if (nearbyChannels.length >= 2) {
      // Check if junction already exists near chamber
      const existing = junctions.find(j => {
        const d = Math.sqrt((j.position.x - chamber.center.x) ** 2 + (j.position.y - chamber.center.y) ** 2)
        return d < tolerance
      })
      if (!existing) {
        junctions.push({
          id: `junc_${junctions.length}`,
          position: chamber.center,
          channelIds: [...new Set(nearbyChannels)],
        })
      }
    }
  }

  return junctions
}

// ── Main analysis function ─────────────────────────────────────────────────

export function analyzeTopology(topology: ParsedTopology): AnalysisResult {
  const unit = topology.unit

  // Combine all faces and edges from all solids
  const allFaces: ParsedFace[] = []
  const allEdges: ParsedEdge[] = []
  for (const solid of topology.solids) {
    allFaces.push(...solid.faces)
    allEdges.push(...solid.edges)
  }

  // Height layers
  const heightLayers = findHeightLayers(allFaces, unit).map(l => ({
    zMin: l.zMin,
    zMax: l.zMax,
    height: l.height,
    count: l.faceIds.length,
  }))

  // Detect features per solid
  let channels: ExtractedChannel[] = []
  let chambers: ExtractedChamber[] = []

  for (const solid of topology.solids) {
    channels.push(...detectChannels(solid, unit))
  }

  for (const solid of topology.solids) {
    chambers.push(...detectChambers(solid, channels, unit))
  }

  // Junctions and ports
  const junctions = detectJunctions(channels, chambers)

  const globalBounds = {
    minX: toMicrons(topology.bounds.minX, unit),
    minY: toMicrons(topology.bounds.minY, unit),
    maxX: toMicrons(topology.bounds.maxX, unit),
    maxY: toMicrons(topology.bounds.maxY, unit),
  }

  const ports = detectPorts(channels, junctions, globalBounds)

  return {
    channels,
    chambers,
    ports,
    junctions,
    bounds: globalBounds,
    heightLayers,
    unit: 'µm',
  }
}
