/**
 * SketchView: 2D dimensioned sketch of the extracted microfluidic network.
 * Uses HTML5 Canvas for rendering (lighter than Three.js for 2D).
 *
 * Features:
 * - Channels drawn as lines with width proportional to cross-section
 * - Chambers as filled rectangles
 * - Ports as circles with labels
 * - Junctions as dots
 * - Dimension annotations (length in µm)
 * - Height color-coding
 * - Pan & zoom
 * - Click to select elements
 * - Manual component placement mode
 */

import { useRef, useEffect, useCallback, useState } from 'react'
import { useCadImportStore } from '../CadImportStore'
import type {
  AnalysisResult, ExtractedChannel, ExtractedChamber,
  ExtractedPort, ExtractedJunction, ManualComponent, Vec2,
} from '../CadImportStore'

// ── Height → color mapping ─────────────────────────────────────────────────

function heightToColor(height: number, minH: number, maxH: number): string {
  if (maxH <= minH) return '#3b82f6' // blue default
  const t = Math.max(0, Math.min(1, (height - minH) / (maxH - minH)))
  // blue → cyan → green → yellow → red
  const r = Math.round(t < 0.5 ? 0 : (t - 0.5) * 2 * 255)
  const g = Math.round(t < 0.5 ? t * 2 * 255 : (1 - t) * 2 * 255)
  const b = Math.round(t < 0.5 ? (1 - t * 2) * 255 : 0)
  return `rgb(${r},${g},${b})`
}

// ── Format µm nicely ───────────────────────────────────────────────────────

function formatUm(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)} mm`
  return `${value.toFixed(0)} µm`
}

// ── Component ──────────────────────────────────────────────────────────────

export function SketchView() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // View transform
  const [offset, setOffset] = useState<Vec2>({ x: 0, y: 0 })
  const [scale, setScale] = useState(1)
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState<Vec2>({ x: 0, y: 0 })

  const analysis = useCadImportStore(s => s.analysis)
  const manualComponents = useCadImportStore(s => s.manualComponents)
  const selectedId = useCadImportStore(s => s.selectedId)
  const hoveredId = useCadImportStore(s => s.hoveredId)
  const showDimensions = useCadImportStore(s => s.showDimensions)
  const showHeightColors = useCadImportStore(s => s.showHeightColors)
  const placingKind = useCadImportStore(s => s.placingComponentKind)

  const setSelected = useCadImportStore(s => s.setSelected)
  const setHovered = useCadImportStore(s => s.setHovered)
  const addManualComponent = useCadImportStore(s => s.addManualComponent)

  // Fit view to analysis bounds on first load
  useEffect(() => {
    if (!analysis || !containerRef.current) return

    const { bounds } = analysis
    const cw = containerRef.current.clientWidth
    const ch = containerRef.current.clientHeight
    const bw = bounds.maxX - bounds.minX
    const bh = bounds.maxY - bounds.minY

    if (bw <= 0 || bh <= 0) return

    const padding = 60
    const sx = (cw - padding * 2) / bw
    const sy = (ch - padding * 2) / bh
    const s = Math.min(sx, sy)

    setScale(s)
    setOffset({
      x: (cw - bw * s) / 2 - bounds.minX * s,
      y: (ch - bh * s) / 2 - bounds.minY * s,
    })
  }, [analysis])

  // World ↔ screen transforms
  const screenToWorld = useCallback((p: Vec2): Vec2 => ({
    x: (p.x - offset.x) / scale,
    y: (p.y - offset.y) / scale,
  }), [scale, offset])

  // ── Draw ─────────────────────────────────────────────────────────────────

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !analysis) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const cw = canvas.clientWidth
    const ch = canvas.clientHeight
    canvas.width = cw * dpr
    canvas.height = ch * dpr
    ctx.scale(dpr, dpr)

    // Clear
    ctx.fillStyle = '#f8fafc'
    ctx.fillRect(0, 0, cw, ch)

    // Grid
    drawGrid(ctx, cw, ch, scale, offset)

    // Height range for color mapping
    const heights = analysis.channels.map(c => c.height)
    const minH = heights.length > 0 ? Math.min(...heights) : 0
    const maxH = heights.length > 0 ? Math.max(...heights) : 100

    // Draw chambers
    for (const chamber of analysis.chambers) {
      drawChamber(ctx, chamber, analysis, scale, offset, selectedId, hoveredId, showHeightColors, minH, maxH)
    }

    // Draw channels
    for (const channel of analysis.channels) {
      drawChannel(ctx, channel, scale, offset, selectedId, hoveredId, showDimensions, showHeightColors, minH, maxH)
    }

    // Draw junctions
    for (const junc of analysis.junctions) {
      drawJunction(ctx, junc, scale, offset, selectedId, hoveredId)
    }

    // Draw ports
    for (const port of analysis.ports) {
      drawPort(ctx, port, scale, offset, selectedId, hoveredId)
    }

    // Draw manual components
    for (const comp of manualComponents) {
      drawManualComponent(ctx, comp, scale, offset, selectedId, hoveredId)
    }

    // Placement cursor
    if (placingKind) {
      ctx.strokeStyle = '#8b5cf6'
      ctx.setLineDash([4, 4])
      ctx.lineWidth = 1
      // Draw crosshair at mouse position (handled by mousemove)
      ctx.setLineDash([])
    }

  }, [analysis, manualComponents, selectedId, hoveredId, showDimensions, showHeightColors, scale, offset, placingKind])

  // ── Mouse handlers ───────────────────────────────────────────────────────

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const rect = canvasRef.current!.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top

    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
    const newScale = Math.max(0.01, Math.min(100, scale * factor))

    // Zoom toward cursor
    setOffset({
      x: mx - (mx - offset.x) * (newScale / scale),
      y: my - (my - offset.y) * (newScale / scale),
    })
    setScale(newScale)
  }, [scale, offset])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      // Middle click or Alt+click → pan
      setIsPanning(true)
      setPanStart({ x: e.clientX - offset.x, y: e.clientY - offset.y })
      return
    }

    if (e.button === 0 && analysis) {
      const rect = canvasRef.current!.getBoundingClientRect()
      const screenPt = { x: e.clientX - rect.left, y: e.clientY - rect.top }
      const worldPt = screenToWorld(screenPt)

      // Placement mode
      if (placingKind) {
        const id = `manual_${Date.now()}`
        addManualComponent({
          id,
          kind: placingKind,
          label: placingKind === 'pump' ? 'Pump' : placingKind === 'check_valve' ? 'Check Valve' : placingKind === 'pressure_source' ? 'Pressure Source' : placingKind === 'flow_source' ? 'Flow Source' : String(placingKind),
          position: worldPt,
          attachedTo: findNearestElement(worldPt, analysis)?.id ?? '',
          params: getDefaultParams(placingKind),
        })
        return
      }

      // Selection mode
      const hit = hitTest(worldPt, analysis, manualComponents)
      setSelected(hit)
    }
  }, [analysis, manualComponents, placingKind, screenToWorld, offset, addManualComponent, setSelected])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isPanning) {
      setOffset({ x: e.clientX - panStart.x, y: e.clientY - panStart.y })
      return
    }

    if (!analysis) return
    const rect = canvasRef.current!.getBoundingClientRect()
    const screenPt = { x: e.clientX - rect.left, y: e.clientY - rect.top }
    const worldPt = screenToWorld(screenPt)
    const hit = hitTest(worldPt, analysis, manualComponents)
    setHovered(hit)
  }, [isPanning, panStart, analysis, manualComponents, screenToWorld, setHovered])

  const handleMouseUp = useCallback(() => {
    setIsPanning(false)
  }, [])

  return (
    <div ref={containerRef} className="relative flex-1 bg-slate-50 overflow-hidden">
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ cursor: placingKind ? 'crosshair' : isPanning ? 'grabbing' : 'default' }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      />

      {/* Scale indicator */}
      {analysis && (
        <div className="absolute bottom-3 left-3 bg-white/90 border border-slate-200 rounded px-2 py-1 text-xs text-slate-500">
          Scale: {(scale * 1000).toFixed(1)} px/mm
        </div>
      )}

      {/* Legend for height colors */}
      {analysis && showHeightColors && analysis.heightLayers.length > 1 && (
        <div className="absolute top-3 right-3 bg-white/90 border border-slate-200 rounded p-2 text-xs">
          <div className="text-slate-600 font-medium mb-1">Channel Depth</div>
          {analysis.heightLayers.map((layer, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <div
                className="w-3 h-3 rounded-sm"
                style={{
                  backgroundColor: heightToColor(
                    layer.height,
                    Math.min(...analysis.heightLayers.map(l => l.height)),
                    Math.max(...analysis.heightLayers.map(l => l.height)),
                  ),
                }}
              />
              <span className="text-slate-500">{formatUm(layer.height)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Drawing helpers ────────────────────────────────────────────────────────

function drawGrid(
  ctx: CanvasRenderingContext2D,
  cw: number, ch: number,
  scale: number, offset: Vec2,
) {
  // Adaptive grid spacing
  let gridSpacing = 100 // µm
  while (gridSpacing * scale < 30) gridSpacing *= 5
  while (gridSpacing * scale > 150) gridSpacing /= 5

  ctx.strokeStyle = '#e2e8f0'
  ctx.lineWidth = 0.5

  const startX = Math.floor(-offset.x / scale / gridSpacing) * gridSpacing
  const startY = Math.floor(-offset.y / scale / gridSpacing) * gridSpacing
  const endX = Math.ceil((cw - offset.x) / scale / gridSpacing) * gridSpacing
  const endY = Math.ceil((ch - offset.y) / scale / gridSpacing) * gridSpacing

  for (let x = startX; x <= endX; x += gridSpacing) {
    const sx = x * scale + offset.x
    ctx.beginPath()
    ctx.moveTo(sx, 0)
    ctx.lineTo(sx, ch)
    ctx.stroke()
  }

  for (let y = startY; y <= endY; y += gridSpacing) {
    const sy = y * scale + offset.y
    ctx.beginPath()
    ctx.moveTo(0, sy)
    ctx.lineTo(cw, sy)
    ctx.stroke()
  }
}

function drawChannel(
  ctx: CanvasRenderingContext2D,
  ch: ExtractedChannel,
  scale: number, offset: Vec2,
  selectedId: string | null,
  hoveredId: string | null,
  showDimensions: boolean,
  showHeightColors: boolean,
  minH: number, maxH: number,
) {
  const s1 = { x: ch.start.x * scale + offset.x, y: ch.start.y * scale + offset.y }
  const s2 = { x: ch.end.x * scale + offset.x, y: ch.end.y * scale + offset.y }

  const isSelected = selectedId === ch.id
  const isHovered = hoveredId === ch.id

  // Channel width visualization (clamped for visibility)
  const visualWidth = ch.type === 'circular'
    ? Math.max(3, (ch.radius ?? 50) * 2 * scale)
    : Math.max(3, (ch.width ?? 100) * scale)
  const drawWidth = Math.min(visualWidth, 30)

  // Color
  let color = '#3b82f6' // blue default
  if (showHeightColors) {
    color = heightToColor(ch.height, minH, maxH)
  }
  if (isSelected) color = '#8b5cf6' // purple
  if (isHovered && !isSelected) color = '#60a5fa' // lighter blue

  // Draw channel body
  ctx.strokeStyle = color
  ctx.lineWidth = drawWidth
  ctx.lineCap = 'round'
  ctx.globalAlpha = 0.6
  ctx.beginPath()
  ctx.moveTo(s1.x, s1.y)
  ctx.lineTo(s2.x, s2.y)
  ctx.stroke()
  ctx.globalAlpha = 1

  // Center line
  ctx.strokeStyle = color
  ctx.lineWidth = 1.5
  ctx.setLineDash([4, 3])
  ctx.beginPath()
  ctx.moveTo(s1.x, s1.y)
  ctx.lineTo(s2.x, s2.y)
  ctx.stroke()
  ctx.setLineDash([])

  // Dimensions
  if (showDimensions) {
    const mx = (s1.x + s2.x) / 2
    const my = (s1.y + s2.y) / 2

    ctx.font = '10px sans-serif'
    ctx.fillStyle = '#475569'
    ctx.textAlign = 'center'

    const label = ch.type === 'circular'
      ? `⌀${formatUm((ch.radius ?? 50) * 2)}`
      : `${formatUm(ch.width ?? 100)} × ${formatUm(ch.height)}`
    const lengthLabel = `L: ${formatUm(ch.length)}`

    ctx.fillText(label, mx, my - 8)
    ctx.fillText(lengthLabel, mx, my + 14)

    // Dimension arrows at endpoints
    drawDimensionArrow(ctx, s1, s2)
  }

  // Selection ring
  if (isSelected) {
    ctx.strokeStyle = '#8b5cf6'
    ctx.lineWidth = 2
    ctx.setLineDash([3, 3])
    ctx.beginPath()
    ctx.moveTo(s1.x, s1.y)
    ctx.lineTo(s2.x, s2.y)
    ctx.stroke()
    ctx.setLineDash([])
  }
}

function drawDimensionArrow(ctx: CanvasRenderingContext2D, p1: Vec2, p2: Vec2) {
  const len = Math.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2)
  if (len < 30) return

  const dx = (p2.x - p1.x) / len
  const dy = (p2.y - p1.y) / len
  const arrLen = 6

  ctx.strokeStyle = '#94a3b8'
  ctx.lineWidth = 1
  ctx.beginPath()

  // Start arrow
  ctx.moveTo(p1.x + arrLen * (dx - dy * 0.5), p1.y + arrLen * (dy + dx * 0.5))
  ctx.lineTo(p1.x, p1.y)
  ctx.lineTo(p1.x + arrLen * (dx + dy * 0.5), p1.y + arrLen * (dy - dx * 0.5))

  // End arrow
  ctx.moveTo(p2.x - arrLen * (dx + dy * 0.5), p2.y - arrLen * (dy - dx * 0.5))
  ctx.lineTo(p2.x, p2.y)
  ctx.lineTo(p2.x - arrLen * (dx - dy * 0.5), p2.y - arrLen * (dy + dx * 0.5))

  ctx.stroke()
}

function drawChamber(
  ctx: CanvasRenderingContext2D,
  chamber: ExtractedChamber,
  _analysis: AnalysisResult,
  scale: number, offset: Vec2,
  selectedId: string | null,
  hoveredId: string | null,
  showHeightColors: boolean,
  minH: number, maxH: number,
) {
  const cx = chamber.center.x * scale + offset.x
  const cy = chamber.center.y * scale + offset.y
  const hw = Math.max(15, chamber.widthX * scale / 2)
  const hh = Math.max(15, chamber.widthY * scale / 2)

  const isSelected = selectedId === chamber.id
  const isHovered = hoveredId === chamber.id

  let fillColor = '#dbeafe' // light blue
  if (showHeightColors) {
    fillColor = heightToColor(chamber.height, minH, maxH) + '40' // with alpha
  }
  if (isSelected) fillColor = '#c4b5fd'
  if (isHovered && !isSelected) fillColor = '#bfdbfe'

  ctx.fillStyle = fillColor
  ctx.strokeStyle = isSelected ? '#8b5cf6' : '#3b82f6'
  ctx.lineWidth = isSelected ? 2 : 1

  // Rounded rectangle
  const r = 4
  ctx.beginPath()
  ctx.moveTo(cx - hw + r, cy - hh)
  ctx.lineTo(cx + hw - r, cy - hh)
  ctx.quadraticCurveTo(cx + hw, cy - hh, cx + hw, cy - hh + r)
  ctx.lineTo(cx + hw, cy + hh - r)
  ctx.quadraticCurveTo(cx + hw, cy + hh, cx + hw - r, cy + hh)
  ctx.lineTo(cx - hw + r, cy + hh)
  ctx.quadraticCurveTo(cx - hw, cy + hh, cx - hw, cy + hh - r)
  ctx.lineTo(cx - hw, cy - hh + r)
  ctx.quadraticCurveTo(cx - hw, cy - hh, cx - hw + r, cy - hh)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()

  // Label
  ctx.font = '10px sans-serif'
  ctx.fillStyle = '#334155'
  ctx.textAlign = 'center'
  ctx.fillText(`Chamber`, cx, cy - 2)
  ctx.fillText(`${formatUm(chamber.widthX)} × ${formatUm(chamber.widthY)}`, cx, cy + 10)
}

function drawJunction(
  ctx: CanvasRenderingContext2D,
  junc: ExtractedJunction,
  scale: number, offset: Vec2,
  selectedId: string | null,
  hoveredId: string | null,
) {
  const sx = junc.position.x * scale + offset.x
  const sy = junc.position.y * scale + offset.y
  const r = selectedId === junc.id ? 7 : hoveredId === junc.id ? 6 : 5

  ctx.fillStyle = selectedId === junc.id ? '#8b5cf6' : '#475569'
  ctx.beginPath()
  ctx.arc(sx, sy, r, 0, Math.PI * 2)
  ctx.fill()

  if (selectedId === junc.id) {
    ctx.strokeStyle = '#8b5cf6'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(sx, sy, r + 3, 0, Math.PI * 2)
    ctx.stroke()
  }
}

function drawPort(
  ctx: CanvasRenderingContext2D,
  port: ExtractedPort,
  scale: number, offset: Vec2,
  selectedId: string | null,
  hoveredId: string | null,
) {
  const sx = port.position.x * scale + offset.x
  const sy = port.position.y * scale + offset.y
  const isSelected = selectedId === port.id
  const isHovered = hoveredId === port.id

  const r = isSelected ? 9 : isHovered ? 8 : 7

  // Outer ring
  ctx.fillStyle = '#ffffff'
  ctx.strokeStyle = isSelected ? '#8b5cf6' : '#10b981'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.arc(sx, sy, r, 0, Math.PI * 2)
  ctx.fill()
  ctx.stroke()

  // Inner dot
  ctx.fillStyle = isSelected ? '#8b5cf6' : '#10b981'
  ctx.beginPath()
  ctx.arc(sx, sy, 3, 0, Math.PI * 2)
  ctx.fill()

  // Label
  ctx.font = 'bold 10px sans-serif'
  ctx.fillStyle = '#10b981'
  ctx.textAlign = 'center'
  ctx.fillText(port.label, sx, sy - r - 4)
}

function drawManualComponent(
  ctx: CanvasRenderingContext2D,
  comp: ManualComponent,
  scale: number, offset: Vec2,
  selectedId: string | null,
  hoveredId: string | null,
) {
  const sx = comp.position.x * scale + offset.x
  const sy = comp.position.y * scale + offset.y
  const isSelected = selectedId === comp.id
  const isHovered = hoveredId === comp.id

  const size = 14
  const half = size / 2

  // Background
  ctx.fillStyle = isSelected ? '#fef3c7' : isHovered ? '#fef9c3' : '#fefce8'
  ctx.strokeStyle = isSelected ? '#d97706' : '#f59e0b'
  ctx.lineWidth = isSelected ? 2 : 1.5

  // Diamond shape for active components
  ctx.beginPath()
  ctx.moveTo(sx, sy - half - 2)
  ctx.lineTo(sx + half + 2, sy)
  ctx.lineTo(sx, sy + half + 2)
  ctx.lineTo(sx - half - 2, sy)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()

  // Icon
  ctx.font = '11px sans-serif'
  ctx.fillStyle = '#92400e'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  const icon = comp.kind === 'pump' ? 'P' : comp.kind === 'check_valve' ? 'V' : comp.kind === 'pressure_source' ? '⊕' : comp.kind === 'flow_source' ? 'F' : '?'
  ctx.fillText(icon, sx, sy)
  ctx.textBaseline = 'alphabetic'

  // Label
  ctx.font = '9px sans-serif'
  ctx.fillStyle = '#92400e'
  ctx.fillText(comp.label, sx, sy + half + 12)
}

// ── Hit testing ────────────────────────────────────────────────────────────

function hitTest(
  world: Vec2,
  analysis: AnalysisResult,
  manualComponents: ManualComponent[],
): string | null {
  // Check manual components first (on top)
  for (const comp of manualComponents) {
    const d = Math.sqrt((world.x - comp.position.x) ** 2 + (world.y - comp.position.y) ** 2)
    if (d < 200) return comp.id
  }

  // Ports
  for (const port of analysis.ports) {
    const d = Math.sqrt((world.x - port.position.x) ** 2 + (world.y - port.position.y) ** 2)
    if (d < 150) return port.id
  }

  // Junctions
  for (const junc of analysis.junctions) {
    const d = Math.sqrt((world.x - junc.position.x) ** 2 + (world.y - junc.position.y) ** 2)
    if (d < 100) return junc.id
  }

  // Channels (distance to line segment)
  for (const ch of analysis.channels) {
    const d = distToSegment(world, ch.start, ch.end)
    const width = ch.type === 'circular' ? (ch.radius ?? 50) * 2 : (ch.width ?? 100)
    if (d < Math.max(width, 100)) return ch.id
  }

  // Chambers
  for (const chamber of analysis.chambers) {
    const hw = chamber.widthX / 2
    const hh = chamber.widthY / 2
    if (world.x >= chamber.center.x - hw && world.x <= chamber.center.x + hw &&
        world.y >= chamber.center.y - hh && world.y <= chamber.center.y + hh) {
      return chamber.id
    }
  }

  return null
}

function distToSegment(p: Vec2, a: Vec2, b: Vec2): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const lenSq = dx * dx + dy * dy
  if (lenSq === 0) return Math.sqrt((p.x - a.x) ** 2 + (p.y - a.y) ** 2)

  let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq
  t = Math.max(0, Math.min(1, t))

  const projX = a.x + t * dx
  const projY = a.y + t * dy
  return Math.sqrt((p.x - projX) ** 2 + (p.y - projY) ** 2)
}

function findNearestElement(
  world: Vec2,
  analysis: AnalysisResult,
): { id: string } | null {
  let bestDist = Infinity
  let bestId: string | null = null

  // Check channels
  for (const ch of analysis.channels) {
    const d = distToSegment(world, ch.start, ch.end)
    if (d < bestDist) { bestDist = d; bestId = ch.id }
  }

  // Check junctions
  for (const junc of analysis.junctions) {
    const d = Math.sqrt((world.x - junc.position.x) ** 2 + (world.y - junc.position.y) ** 2)
    if (d < bestDist) { bestDist = d; bestId = junc.id }
  }

  return bestId ? { id: bestId } : null
}

function getDefaultParams(kind: string): Record<string, number> {
  switch (kind) {
    case 'pump': return { pressure_generated: 10000, flow_max: 1e-9 }
    case 'pressure_source': return { pressure: 10000 }
    case 'flow_source': return { flow_rate: 1e-9 }
    case 'check_valve': return { r_fwd: 1e6, r_rev: 1e14 }
    default: return {}
  }
}
