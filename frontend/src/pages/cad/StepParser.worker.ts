/**
 * Web Worker for parsing STEP/IGES files using opencascade.js (WASM).
 *
 * Communication protocol:
 *   Main → Worker:  { type: 'parse', fileName: string, data: ArrayBuffer }
 *   Worker → Main:  { type: 'progress', percent: number }
 *   Worker → Main:  { type: 'result', topology: ParsedTopology }
 *   Worker → Main:  { type: 'error', message: string }
 */

// ── Types ──────────────────────────────────────────────────────────────────

export interface ParsedFace {
  id: number
  type: 'plane' | 'cylinder' | 'cone' | 'sphere' | 'torus' | 'bspline' | 'other'
  normal?: [number, number, number]
  center?: [number, number, number]
  radius?: number
  bounds: { minX: number; minY: number; minZ: number; maxX: number; maxY: number; maxZ: number }
  area: number
}

export interface ParsedEdge {
  id: number
  start: [number, number, number]
  end: [number, number, number]
  length: number
  curveType: 'line' | 'circle' | 'ellipse' | 'bspline' | 'other'
  /** For circular edges */
  radius?: number
  center?: [number, number, number]
}

export interface ParsedSolid {
  id: number
  faces: ParsedFace[]
  edges: ParsedEdge[]
  bounds: { minX: number; minY: number; minZ: number; maxX: number; maxY: number; maxZ: number }
  volume: number
}

export interface ParsedTopology {
  solids: ParsedSolid[]
  unit: string
  bounds: { minX: number; minY: number; minZ: number; maxX: number; maxY: number; maxZ: number }
}

// ── OCC type helpers (untyped, opencascade.js has no TS defs) ──────────────

/* eslint-disable @typescript-eslint/no-explicit-any */
type OCC = any

function postProgress(percent: number) {
  self.postMessage({ type: 'progress', percent })
}

// ── Initialize OpenCascade ─────────────────────────────────────────────────

let occPromise: Promise<OCC> | null = null

async function getOcc(): Promise<OCC> {
  if (occPromise) return occPromise

  occPromise = (async () => {
    // Dynamic import of the opencascade.js factory
    const mod = await import('/node_modules/opencascade.js/dist/opencascade.wasm.js' as string)
    const factory = mod.default || mod
    const occ = await factory({
      locateFile(path: string) {
        if (path.endsWith('.wasm')) {
          return '/opencascade.wasm.wasm'
        }
        return path
      },
    })
    return occ
  })()

  return occPromise
}

// ── Parse STEP/IGES ────────────────────────────────────────────────────────

async function parseFile(fileName: string, data: ArrayBuffer): Promise<ParsedTopology> {
  postProgress(5)

  const occ = await getOcc()
  postProgress(20)

  // Write file to WASM virtual filesystem
  const uint8 = new Uint8Array(data)
  const vfsPath = `/input/${fileName}`

  // Ensure directory exists
  try { occ.FS.mkdir('/input') } catch { /* exists */ }
  occ.FS.writeFile(vfsPath, uint8)
  postProgress(25)

  // Determine file type and read
  const ext = fileName.toLowerCase().split('.').pop() ?? ''
  let shape: any

  if (ext === 'step' || ext === 'stp') {
    const reader = new occ.STEPControl_Reader_1()
    const status = reader.ReadFile(vfsPath)
    if (status !== occ.IFSelect_ReturnStatus.IFSelect_RetDone) {
      throw new Error(`Failed to read STEP file (status: ${status})`)
    }
    reader.TransferRoots(new occ.Message_ProgressRange_1())
    shape = reader.OneShape()
    reader.delete()
  } else if (ext === 'iges' || ext === 'igs') {
    const reader = new occ.IGESControl_Reader_1()
    const status = reader.ReadFile(vfsPath)
    if (status !== occ.IFSelect_ReturnStatus.IFSelect_RetDone) {
      throw new Error(`Failed to read IGES file (status: ${status})`)
    }
    reader.TransferRoots(new occ.Message_ProgressRange_1())
    shape = reader.OneShape()
    reader.delete()
  } else {
    throw new Error(`Unsupported file format: .${ext} (use .step/.stp or .iges/.igs)`)
  }

  postProgress(50)

  // Clean up VFS
  try { occ.FS.unlink(vfsPath) } catch { /* ok */ }

  // Extract topology
  const topology = extractTopology(occ, shape)
  postProgress(90)

  shape.delete()
  postProgress(100)

  return topology
}

// ── Topology extraction ────────────────────────────────────────────────────

function extractTopology(occ: OCC, shape: any): ParsedTopology {
  const solids: ParsedSolid[] = []

  // Get bounding box of entire shape
  const globalBbox = getBoundingBox(occ, shape)

  // Iterate solids
  const solidExplorer = new occ.TopExp_Explorer_2(shape, occ.TopAbs_ShapeEnum.TopAbs_SOLID, occ.TopAbs_ShapeEnum.TopAbs_SHAPE)
  let solidId = 0

  while (solidExplorer.More()) {
    const solid = occ.TopoDS.Solid_1(solidExplorer.Current())
    const parsedSolid = extractSolid(occ, solid, solidId++)
    solids.push(parsedSolid)
    solidExplorer.Next()
  }
  solidExplorer.delete()

  // If no solids found, treat the whole shape as a shell/compound
  if (solids.length === 0) {
    const fallbackSolid = extractShapeAsSolid(occ, shape, 0)
    if (fallbackSolid.faces.length > 0) {
      solids.push(fallbackSolid)
    }
  }

  // Determine unit from shape metadata (default: mm → convert to µm later)
  const unit = 'mm'

  return { solids, unit, bounds: globalBbox }
}

function extractSolid(occ: OCC, solid: any, id: number): ParsedSolid {
  const faces = extractFaces(occ, solid)
  const edges = extractEdges(occ, solid)
  const bbox = getBoundingBox(occ, solid)

  // Compute volume
  let volume = 0
  try {
    const props = new occ.GProp_GProps_1()
    occ.BRepGProp.VolumeProperties_1(solid, props, false, false, false)
    volume = props.Mass()
    props.delete()
  } catch { /* ok */ }

  return { id, faces, edges, bounds: bbox, volume }
}

function extractShapeAsSolid(occ: OCC, shape: any, id: number): ParsedSolid {
  const faces = extractFaces(occ, shape)
  const edges = extractEdges(occ, shape)
  const bbox = getBoundingBox(occ, shape)
  return { id, faces, edges, bounds: bbox, volume: 0 }
}

function extractFaces(occ: OCC, shape: any): ParsedFace[] {
  const faces: ParsedFace[] = []
  const explorer = new occ.TopExp_Explorer_2(shape, occ.TopAbs_ShapeEnum.TopAbs_FACE, occ.TopAbs_ShapeEnum.TopAbs_SHAPE)
  let faceId = 0

  while (explorer.More()) {
    const face = occ.TopoDS.Face_1(explorer.Current())
    try {
      const parsed = parseFace(occ, face, faceId++)
      if (parsed) faces.push(parsed)
    } catch { /* skip problematic faces */ }
    explorer.Next()
  }
  explorer.delete()
  return faces
}

function parseFace(occ: OCC, face: any, id: number): ParsedFace | null {
  const surface = occ.BRep_Tool.Surface_2(face)
  if (!surface) return null

  const bbox = getBoundingBox(occ, face)

  // Compute area
  let area = 0
  try {
    const props = new occ.GProp_GProps_1()
    occ.BRepGProp.SurfaceProperties_1(face, props, false, false)
    area = props.Mass()
    props.delete()
  } catch { /* ok */ }

  // Determine surface type
  const adaptor = new occ.BRepAdaptor_Surface_2(face, true)
  const surfType = adaptor.GetType()

  let type: ParsedFace['type'] = 'other'
  let normal: [number, number, number] | undefined
  let center: [number, number, number] | undefined
  let radius: number | undefined

  if (surfType === occ.GeomAbs_SurfaceType.GeomAbs_Plane) {
    type = 'plane'
    const pln = adaptor.Plane()
    const axis = pln.Axis()
    const dir = axis.Direction()
    normal = [dir.X(), dir.Y(), dir.Z()]
  } else if (surfType === occ.GeomAbs_SurfaceType.GeomAbs_Cylinder) {
    type = 'cylinder'
    const cyl = adaptor.Cylinder()
    radius = cyl.Radius()
    const loc = cyl.Location()
    center = [loc.X(), loc.Y(), loc.Z()]
    const axis = cyl.Axis()
    const dir = axis.Direction()
    normal = [dir.X(), dir.Y(), dir.Z()]
  } else if (surfType === occ.GeomAbs_SurfaceType.GeomAbs_Cone) {
    type = 'cone'
  } else if (surfType === occ.GeomAbs_SurfaceType.GeomAbs_Sphere) {
    type = 'sphere'
  } else if (surfType === occ.GeomAbs_SurfaceType.GeomAbs_Torus) {
    type = 'torus'
  } else if (surfType === occ.GeomAbs_SurfaceType.GeomAbs_BSplineSurface) {
    type = 'bspline'
  }

  adaptor.delete()

  return { id, type, normal, center, radius, bounds: bbox, area }
}

function extractEdges(occ: OCC, shape: any): ParsedEdge[] {
  const edges: ParsedEdge[] = []
  const explorer = new occ.TopExp_Explorer_2(shape, occ.TopAbs_ShapeEnum.TopAbs_EDGE, occ.TopAbs_ShapeEnum.TopAbs_SHAPE)
  let edgeId = 0

  while (explorer.More()) {
    const edge = occ.TopoDS.Edge_1(explorer.Current())
    try {
      const parsed = parseEdge(occ, edge, edgeId++)
      if (parsed) edges.push(parsed)
    } catch { /* skip */ }
    explorer.Next()
  }
  explorer.delete()
  return edges
}

function parseEdge(occ: OCC, edge: any, id: number): ParsedEdge | null {
  // Get curve and parameters
  const adaptor = new occ.BRepAdaptor_Curve_2(edge)
  const first = adaptor.FirstParameter()
  const last = adaptor.LastParameter()

  // Start and end points
  const startPnt = adaptor.Value(first)
  const endPnt = adaptor.Value(last)
  const start: [number, number, number] = [startPnt.X(), startPnt.Y(), startPnt.Z()]
  const end: [number, number, number] = [endPnt.X(), endPnt.Y(), endPnt.Z()]

  // Compute length
  let length = 0
  try {
    const props = new occ.GProp_GProps_1()
    occ.BRepGProp.LinearProperties(edge, props, false, false)
    length = props.Mass()
    props.delete()
  } catch { /* ok */ }

  // Curve type
  const curveType_enum = adaptor.GetType()
  let curveType: ParsedEdge['curveType'] = 'other'
  let radius: number | undefined
  let center: [number, number, number] | undefined

  if (curveType_enum === occ.GeomAbs_CurveType.GeomAbs_Line) {
    curveType = 'line'
  } else if (curveType_enum === occ.GeomAbs_CurveType.GeomAbs_Circle) {
    curveType = 'circle'
    const circ = adaptor.Circle()
    radius = circ.Radius()
    const loc = circ.Location()
    center = [loc.X(), loc.Y(), loc.Z()]
  } else if (curveType_enum === occ.GeomAbs_CurveType.GeomAbs_Ellipse) {
    curveType = 'ellipse'
  } else if (curveType_enum === occ.GeomAbs_CurveType.GeomAbs_BSplineCurve) {
    curveType = 'bspline'
  }

  adaptor.delete()

  return { id, start, end, length, curveType, radius, center }
}

function getBoundingBox(occ: OCC, shape: any): { minX: number; minY: number; minZ: number; maxX: number; maxY: number; maxZ: number } {
  const bbox = new occ.Bnd_Box_1()
  occ.BRepBndLib.Add(shape, bbox, false)
  const min = bbox.CornerMin()
  const max = bbox.CornerMax()
  const result = {
    minX: min.X(), minY: min.Y(), minZ: min.Z(),
    maxX: max.X(), maxY: max.Y(), maxZ: max.Z(),
  }
  bbox.delete()
  return result
}

// ── Worker message handler ─────────────────────────────────────────────────

self.onmessage = async (event: MessageEvent) => {
  const { type, fileName, data } = event.data

  if (type === 'parse') {
    try {
      const topology = await parseFile(fileName, data)
      self.postMessage({ type: 'result', topology })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown parsing error'
      self.postMessage({ type: 'error', message })
    }
  }
}
