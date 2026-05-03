# Power Flow Visualization Tool — IEEE Benchmark Cases

## Objective

A single-page HTML viewer for the three IEEE benchmark power-flow cases (9, 14, 30 bus) and their solved results. The fixtures already exist in this repo at `data/case{9,14,30}.json` and `data/case{9,14,30}_solution.json`; the viz reads them directly and renders an interactive network diagram with click-to-inspect buses and branches.

This is a viewer, not an editor. Topology is fixed at load time.

## Where this lives

This is **not** a standalone repository. Everything goes under `loadflow-lite/viz/`:

```
loadflow-lite/
├── data/                          # MATPOWER-derived fixtures — do not modify
└── viz/
    ├── index.html
    ├── styles.css                 # optional; inline into index.html if you prefer
    ├── app.js                     # optional; inline into index.html if you prefer
    └── layouts/
        ├── case9.layout.json
        ├── case14.layout.json
        └── case30.layout.json
```

### Running it

Serve from the **repo root** so `fetch()` can reach both `viz/` and `data/`:

```
cd loadflow-lite
python3 -m http.server 8000
# open http://localhost:8000/viz/
```

The viz then fetches `../data/case9.json` and `layouts/case9.layout.json` (relative to `viz/`). Don't try to serve from inside `viz/` — `python3 -m http.server` won't follow `..` outside its root.

## Stack

- **D3.js v7** via CDN — SVG, scales, zoom.
- Plain HTML/CSS/JS, no build step, no framework, no CSS framework, no bundler.

If you want anything else, ask first.

## Look and feel

Restrained, engineering-tool aesthetic — closer to a SCADA HMI than a startup landing page. Off-white background, dark text, a small accent palette. System sans-serif stack for prose; monospace for numbers in the inspector. No gradients, no decorative shadows.

Bus symbols use conventional engineering iconography (circle with G for generator, downward arrow for load, double circle for slack, two interlocking circles mid-line for transformer, small block for shunt). Inline SVG only — no icon fonts or bitmaps.

## Data contract — what the fixtures actually contain

The MATPOWER-derived fixtures are the source of truth. Don't modify them. Shapes below are what's on disk today.

### Case file (e.g. `data/case9.json`)

```json
{
  "metadata": { "source_case": "case9", "matpower_version": "8.1", ... },
  "base_mva": 100,
  "buses": [
    {
      "id": 1, "type": "slack",
      "p_load": 0, "q_load": 0,
      "p_gen": 0.723, "q_gen": 0.2703,
      "v_magnitude": 1.04, "v_angle": 0,
      "g_shunt": 0, "b_shunt": 0
    }
  ],
  "branches": [
    {
      "from_bus": 1, "to_bus": 4,
      "r": 0, "x": 0.0576, "b": 0,
      "tap_ratio": 1, "phase_shift": 0,
      "status": 1
    }
  ]
}
```

`type` is `"slack" | "pv" | "pq"`. `phase_shift` is in radians.

Fields you might expect that **are not** in the fixtures — don't try to read them, don't fabricate them, don't display them:

- No `name` at the top level (use `metadata.source_case`).
- No `x_coord`/`y_coord` — coordinates live in the sidecar layout files (you author these).
- No `base_kv` — show voltages in p.u. only; no kV display anywhere.
- No `rate_a` — no loading-percentage display anywhere.

Note on `v_angle`: present in case files in radians, but it's just initial state. The viz should display angles from the solution (`v_angle_degrees`) when a solution is loaded; the case-file `v_angle` is not surfaced to the user.

### Solution file (e.g. `data/case9_solution.json`)

```json
{
  "metadata": { "source_case": "case9", "base_mva": 100, ... },
  "buses": [
    { "id": 1, "v_magnitude": 1.04, "v_angle_degrees": 0 }
  ],
  "generators": [
    { "bus_id": 1, "p_generation": 0.7164, "q_generation": 0.2705 }
  ],
  "branches": [
    { "from_bus": 1, "to_bus": 4, "p_from": 0.7164, "q_from": 0.2705, "p_to": -0.7164, "q_to": -0.2393 }
  ]
}
```

Things to derive in the viz (the fixtures don't store them):

- **Per-branch losses**: `p_loss = p_from + p_to`, `q_loss = q_from + q_to`.
- **Total losses**: sum the above across branches.

There's no `converged` / `iterations` / `max_mismatch` — don't display convergence metadata.

In all three IEEE cases each generator is on a unique bus; you can index `generators` by `bus_id` directly without summing.

### Sidecar layout files (you author these)

```json
{
  "case": "case9",
  "buses": { "1": { "x": 100, "y": 200 }, "2": { "x": 300, "y": 200 } }
}
```

Hand-curate from the conventional published one-line diagrams (Anderson layout for 9-bus; standard textbook layouts for 14 and 30). Coordinates in a 0–1000 range; the SVG `viewBox` is fixed at `0 0 1000 1000`. Approximations are fine. Provide a coordinate for every bus in the case — no fallback rendering.

## Functional scope

### Layout

```
┌──────────────────────────────────────────────────────┐
│  Header: case selector | solve status                │
├──────────────────────────────────────────────────────┤
│                                       │              │
│        Network diagram (SVG)          │  Inspector   │
│                                       │              │
├──────────────────────────────────────────────────────┤
│  Footer: legend | flow / heatmap toggles             │
└──────────────────────────────────────────────────────┘
```

Diagram ~70% width, inspector ~30%. Designed for ≥1280px wide; no responsive breakpoint required.

### Header

- **Case selector**: dropdown with "IEEE 9-bus" (default), "IEEE 14-bus", "IEEE 30-bus".
- **Solve status**: small subtitle next to the selector — "Solution loaded" or "Topology only" — based on whether the solution fetch succeeded.

### Network diagram

- **Pan and zoom** via `d3.zoom()` (wheel zooms, drag-on-empty pans). D3's default double-click behavior resets the view; that's enough — no separate reset button needed.
- **Static layout** from the sidecar file. No drag-to-reposition, no force simulation.
- **Bus rendering**:
  - Slack: double-circle.
  - PV (has `p_gen > 0` or type `pv`): circle with attached generator glyph.
  - PQ with non-zero load: circle with attached load arrow.
  - Both gen and load: both glyphs.
  - Non-zero `g_shunt` or `b_shunt`: small shunt marker.
  - Label: bus ID; add `v_magnitude` (p.u., 3 decimals) when solution loaded.
- **Branch rendering**: straight lines. Transformers (`tap_ratio ≠ 1.0` or `phase_shift ≠ 0`) get a small mid-line marker.
- **Flow overlay** (when solution loaded, toggleable): arrowhead on each branch in the direction of real-power flow, with line thickness scaled to `|p_from|`. Pick any reasonable scaling that keeps the lightest flows visible and the heaviest from dominating.
- **Voltage heatmap** (when solution loaded, toggleable): bus fill color from a colorblind-safe diverging scale (e.g. D3's `interpolatePuOr` or `interpolateBrBG`) clamped at 0.94/1.06 p.u., centered at 1.0. The IEEE cases stay close to 1.0 in normal operation, so expect subtle coloring — not a bug.

### Inspector panel

Two-column key/value layout, monospace numbers, units labeled. All powers in MW / MVAr (multiply p.u. by `base_mva`).

- **Empty selection** (default, or click background): case-level summary — total `p_gen`, total `p_load`, total real losses (when solved), bus counts by type, branch count.
- **Bus selected**: bus ID, type; case-side `p_load`, `q_load`, `p_gen`, `q_gen`, `v_magnitude` (PV/slack), `g_shunt`/`b_shunt` (when non-zero); when solution is loaded: solved `v_magnitude`, `v_angle_degrees`, generator output from the `generators` array, and a list of incident branches with their `p_from` / `q_from`.
- **Branch selected**: endpoints, `r`, `x`, `b`, `tap_ratio`, `phase_shift`; when solution is loaded: `p_from`, `q_from`, `p_to`, `q_to`, derived `p_loss`, `q_loss`.

### Footer

- **Legend**: small inline panel showing what each symbol means (slack, PV, PQ, generator, load, transformer, shunt). Always visible.
- **Toggles**: two checkboxes — "Flow arrows" and "Voltage heatmap". Both default on when a solution is loaded.

## Suggested build order

Vertical slices, each one demoable. Don't build all the layout machinery before anything renders.

1. **Topology, all three cases.** Load the case + its layout file, render buses as plain circles and branches as straight lines. Case selector switches between them. No icons, no inspector, no overlays. Verify everything reads cleanly off disk.
2. **Symbols + zoom + inspector.** Replace plain circles with the proper engineering symbols, add the legend, wire up `d3.zoom()`, build the click-to-inspect panel for empty / bus / branch — topology fields only.
3. **Solution overlay.** Load the solution, fill solved fields in the inspector, add flow arrows and the voltage heatmap, add the two toggles.
4. **Polish.** Typography, spacing, hover/focus states, basic loading and error states.

## Working style

- **Show me each slice working** before moving on — a one-line note is fine.
- **Pick the simplest thing that works.** If you find yourself reaching for a sophisticated SVG technique, ask whether something plainer would be just as readable.
- **Don't invent data.** If a field isn't in the fixtures, leave the row out. The data-contract section above lists exactly what is and isn't there.
- **Don't modify `data/`.** All viz authoring (layouts, display labels) goes under `viz/`.
- **Test in the browser.** Open it and look at it — layout bugs are obvious visually and invisible in code.
- **No unrequested features.** No dark mode, no export-to-PNG, no tour overlay, no settings panel, no animations.

## Definition of done

- All three cases render correctly; 9-bus loads by default.
- Solution overlay works on all three; absence of a solution file is handled gracefully (toggles disabled, inspector shows topology fields only).
- Inspector shows correct case-side and solved values, with derived losses computed in-viz.
- Pan and zoom work smoothly on the 30-bus case.
- External dependencies: D3 only.
- `data/` is unchanged.

When done, briefly summarize: which slices went smoothly, which fought you, and any visual or interaction tradeoffs worth knowing about.
