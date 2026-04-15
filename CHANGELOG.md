# Changelog

All notable changes to this project are documented here.

## [0.3.1] — 2026-04-15

### Added — Nonlinear turbulent channels (Modelica two-port port)

Back-port of the nonlinear channel models from the node-based backend (v0.2.0 in the legacy repo) onto the Modelica two-port architecture.

#### Files

- `backend/physics/flow_calculations.py` — Added `calculate_turbulent_resistance_circular` and `calculate_turbulent_resistance_rectangular`. Both use the Blasius friction factor `f = 0.316 · Re^(-0.25)` and the Darcy-Weisbach formulation `R_turb = f · L · ρ · |Q| / (2 · D · A²)`. Falls back to Hagen-Poiseuille laminar resistance for `Re < 1` to avoid unphysical values.
- `backend/models/channel.py` — Added `NonlinearCircularChannel` and `NonlinearRectangularChannel`. Both inherit from their laminar counterparts and expose `is_nonlinear = True` (duck-typed flag the solver's Picard loop reads). Density is taken from the shared `FluidMedium` (legacy `density=` kwarg still accepted for backward compatibility). `update_resistance(flow)` re-linearises by blending laminar and turbulent resistance with a linear weight in the transition zone (Re 2300–4000).
- `backend/solver/network_solver.py` — Generalised the solver to Picard iteration:
  - Detects nonlinear elements via `getattr(elem, "is_nonlinear", False)`.
  - For linear networks runs exactly one iteration (no behaviour change).
  - For networks with nonlinear elements, wraps the linear solve in a Picard loop. After each linear solve the new flow estimate is averaged per nonlinear element and fed back via `update_resistance`.
  - Adds **under-relaxation** `Q_eff = α · Q_new + (1-α) · Q_prev` (default α = 0.5) to damp the R(|Q|) oscillations inherent to Blasius-type turbulent models.
  - Convergence check on relative resistance change (default tol = 1e-6, max 30 iterations).
  - `element_results` now includes `reynolds` for nonlinear elements.
- `backend/tests/test_nonlinear_channels.py` — **New**: 25 tests covering laminar/turbulent/transition regimes, Blasius correlation analytically verified, Picard convergence, Reynolds reporting, legacy `(viscosity, density)` constructor API and serialisation round-trip.

### Design decisions

- **Two-port refactor for nonlinear channels** — the nonlinear classes live in the Modelica TwoPortElement hierarchy (not the legacy node base) and use the shared `FluidMedium` for both viscosity and density. The legacy `(viscosity=, density=)` kwargs are preserved as a backward-compat wrapper so existing callers keep working.
- **Under-relaxation in the Picard loop** — without relaxation, `R(|Q|) ∝ |Q|^0.75` causes oscillations at high Reynolds (R swings between 10⁴ and 10¹⁰). α = 0.5 converges reliably within ~10 iterations for the tested cases.
- **Linear networks unaffected** — the Picard loop reduces to a single pass when no element carries the `is_nonlinear` flag, so all 133 existing tests pass unchanged.

### Test coverage

158/158 unit tests passing (133 existing + 25 new nonlinear-channel tests).

---

## [0.3.0] — 2026-04-15

### Added — 3D CAD Import (STEP/IGES)

New tool for importing 3D CAD files and deriving a simplified microfluidic network.

**Pipeline:** STEP/IGES file → OpenCascade WASM parsing → 2.5D→2D projection → 2D→1D network → interactive review → simulator handoff.

#### Files (frontend)

- `src/pages/CadImportStore.ts` — Zustand store for the CAD import pipeline (stages: idle → loading → parsing → analyzing → review). Holds extracted channels/chambers/ports/junctions, manually placed active components, and the fluid properties used for resistance calculation. Includes `toSimulatorData()` to convert the analysis result into simulator-compatible `Node[]` / `Edge[]` and `validate()` for pre-handoff checks.
- `src/pages/cad/StepParser.worker.ts` — Web Worker that loads `opencascade.js` (WASM) and parses STEP/IGES files. Extracts topology: solids, faces (plane/cylinder/cone/sphere/torus/bspline), edges (line/circle/ellipse/bspline), and bounding boxes. Runs off the main thread so the UI stays responsive.
- `src/pages/cad/GeometryAnalyzer.ts` — 2.5D → 2D projection:
  - Height-layer clustering (faces grouped by Z-extent)
  - Channel detection (cylindrical faces → circular; elongated rectangular voids → rectangular)
  - Chamber detection (low aspect-ratio horizontal regions)
  - Junction detection (clustered channel endpoints)
  - Port detection (endpoints at chip boundary or open)
  - Unit normalization (mm / µm / cm / m / inch → µm)
- `src/pages/cad/NetworkDeriver.ts` — Computes hydraulic resistances from extracted geometry using the same formulas as the backend:
  - Circular: `R = 8ηL / (π r⁴)`
  - Rectangular: series expansion with tanh correction
- `src/pages/cad/SketchView.tsx` — 2D dimensioned sketch (HTML5 Canvas):
  - Channels rendered as lines with width proportional to cross-section
  - Chambers as filled rounded rectangles
  - Ports as ringed circles, junctions as dots, manual components as diamonds
  - Height-based color coding (blue → cyan → green → yellow → red)
  - Dimension annotations (length, width/diameter, height)
  - Pan, zoom, click-to-select, hover highlighting
  - Placement mode: click on sketch to drop a manual component at the nearest feature
- `src/pages/cad/BlockList.tsx` — Right-panel list of all derived building blocks with:
  - Type, ID, key dimensions, computed resistance
  - Inline parameter editing when selected (radius/width/height/length)
  - Separate sections for Channels, Chambers, Ports, Junctions, Manual Components
  - Bidirectional highlighting with SketchView
- `src/pages/cad/ManualPlacement.tsx` — Menu for adding active components that cannot be detected from STEP geometry: Pump, Pressure Source, Flow Source, Check Valve, Pressure Ground.
- `src/pages/cad/Validation.tsx` — Footer status bar with validation checks (missing pressure boundary, disconnected channels, empty geometry) shown as error/warning badges.
- `src/pages/CadImport.tsx` — Main page orchestrating the upload area, processing progress view, error view, and review split-layout with toolbar (dimensions toggle, height-color toggle, viscosity input, "Send to Simulator" button).

#### Files (infrastructure)

- `frontend/vite.config.ts` — Added `worker: { format: 'es' }` for ES-module Web Worker support in production builds.
- `frontend/public/opencascade.wasm.wasm` — OpenCascade WASM binary copied to public for runtime loading.
- `frontend/package.json` — New dependencies: `opencascade.js`, `three`, `@types/three`.
- `frontend/src/App.tsx` — Tab type extended to include `'cad'`; CadImportPage mounted as a fourth tab that stays mounted to preserve state.
- `frontend/src/components/Toolbar.tsx` — New "3D CAD" pill-tab button (orange accent).

### Design decisions

- **STEP/IGES only, no STL** — preserves semantic B-Rep topology (faces, edges, exact dimensions) which is required to reliably identify cylindrical channels and rectangular chambers. STL would lose this information.
- **2.5D → 2D → 1D (not direct 3D → 1D)** — microfluidic chips are essentially planar with varying depths. Projecting to 2D first makes channel/chamber detection tractable; the height is preserved as a per-element parameter and flows into the rectangular-channel resistance formula.
- **Intermediate review interface** — automated extraction is heuristic and cannot be perfect on unusual geometries. The split-view lets users verify and correct dimensions before simulation.
- **Manual pump/valve placement** — active components are not visible in STEP geometry. Users place them via menu + click, attaching them to the nearest detected channel or junction.
- **WASM in Web Worker** — OpenCascade's WASM build is ~30 MB. Running it in a Web Worker prevents UI freezes during parsing of large assemblies.

### Known limitations

- Heuristic detection can miss unusual geometries — the manual correction UI is the fallback.
- Curved/3D channels get projected to a 2D straight-line approximation; lengths may be slightly off for strongly curved paths.
- Large STEP files (> 50 MB) can take several seconds to parse.
- OpenCascade WASM is lazy-loaded only when the CAD tab is active.

---

## [0.2.0] — 2026-04-14

### Added — Frontend redesign & new tabs

- **Tab navigation:** Simulator, Builder, Import, (3D CAD added in 0.3.0) as parallel tabs in the toolbar. All tabs stay mounted to preserve state; single shared `ReactFlowProvider`.
- **Light theme** — slate-50 background, white panels, slate-200 borders, blue/violet/emerald/orange accents per tab.
- **PDF Import tab** — upload technical drawings, calibrate scale via two-point click, trace channels/chambers/ports as an overlay, then push the traced network into the Simulator.

### Added — Backend S3: Nonlinear turbulent channels

- `NonlinearCircularChannel` and `NonlinearRectangularChannel` with Reynolds-dependent laminar/turbulent switching.
- Blasius friction factor `f = 0.316 · Re^(-0.25)` + Darcy-Weisbach for the turbulent branch.
- Smooth blending in the transition zone (Re 2300–4000) to avoid discontinuities.
- Generalized Picard iteration in the solver handles both check valves and nonlinear channels uniformly.

### Fixed — Solver bugs from earlier audit

- Solver conductance formula: `1/(r_src+r_tgt)` (was `2/(r_src+r_tgt)`).
- Flow calculation: `r_total = r1+r2` (was `r_avg = (r1+r2)/2`).
- BC validator: `model_validator(mode="after")` (was a no-op `field_validator`).
- Pump model: Dirichlet BC at pump node (was incorrect Norton source).
- Disconnected network detection via `nx.is_connected()`.
- Graceful error wrapping in `/api/network/elements` (KeyError → ValueError).
- Warning log when channel width/height are silently swapped.

### Test coverage

323/323 tests passing.

---

## [0.1.0] — Initial release

Kirchhoff-nodal microfluidic network solver with FastAPI backend and React + Xyflow frontend.
