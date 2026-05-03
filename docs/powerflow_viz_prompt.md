# Power Flow Visualization Tool — IEEE Benchmark Cases

## Objective

Build a professional, single-page HTML visualization tool for inspecting IEEE benchmark power-flow cases (9-bus, 14-bus, 30-bus) and their solved results. The tool sits on top of the existing `powerflow` solver from the v0 project — it consumes case JSON files and solution JSON files produced by that project, and renders them as an interactive network diagram with inspectable elements.

This is a viewer/inspector, not an editor. Users explore cases and results; they do not modify network topology in the browser.

## Hard constraints

### Single self-contained HTML file

The deliverable is **one `index.html` file** that opens in a browser by double-clicking, with no build step, no server required, no `npm install`. CSS and JavaScript live inline in the file or in sibling files loaded by relative path. Case data files (JSON) live in a `data/` subdirectory next to `index.html` and are loaded via `fetch()`.

The user must be able to run it by:

```
cd powerflow-viz/
python -m http.server 8000   # any static server, only because fetch() of local files needs one
```

…and opening `http://localhost:8000`. That's the entire setup story. If `fetch()` is awkward, embedding the JSON inline as `<script type="application/json">` blocks is acceptable as a fallback — explain the choice.

### Dependencies — minimal and CDN-loaded

Allowed:

- **D3.js v7** (via CDN, for SVG rendering, scales, drag, zoom)
- Plain HTML/CSS/JavaScript

Not allowed:

- React, Vue, Svelte, or any framework requiring a build step
- Tailwind, Bootstrap, or any CSS framework — write the CSS yourself
- jQuery
- Chart libraries (D3 is enough; we're not building dashboards)
- Any package manager, bundler, or transpiler

The point is a clean, professional-feeling tool that a reviewer can open and read end-to-end without tooling. If you find yourself wanting a framework, stop and ask.

### Look and feel — professional, not flashy

Aesthetic target: a TSO/utility engineering tool, not a consumer app. Specifically:

- **Restrained color palette.** Suggest a neutral background (off-white `#fafafa` or very light grey), dark text (`#1a1a1a`), and a small set of accent colors used meaningfully (e.g. one color for active selection, one for warnings/violations, one for power flow direction). No gradients, no shadows-as-decoration, no glassmorphism.
- **Clear typography.** A single sans-serif (system font stack is fine: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`) at 2–3 sizes. A monospace font for numerical values in the inspector panel.
- **Functional iconography.** Generators, loads, slack bus, transformers, and shunts each have a distinct visual representation in SVG. Use the conventional power-engineering symbols where sensible (circle with G inside for generator, downward arrow for load, double-circle for slack, two interlocking circles for transformer). Render them as inline SVG, not bitmap icons or icon fonts.
- **Whitespace and alignment matter.** A 12-column grid mental model is fine; the panels should feel deliberate, not crowded.

If you're tempted to make it "pop" with bright colors or large shadows, don't. The reference aesthetic is closer to a Bloomberg terminal or a SCADA HMI than a startup landing page.

## Functional scope

### Layout

A three-region layout:

```
┌───────────────────────────────────────────────────────────────────┐
│  Header: case selector | solve status | tolerance summary         │
├───────────────────────────────────────────────────────────────────┤
│                                            │                      │
│                                            │   Inspector panel    │
│        Network diagram (SVG)               │   (selected item     │
│        — pan/zoom enabled                  │    details)          │
│                                            │                      │
│                                            │                      │
├───────────────────────────────────────────────────────────────────┤
│  Footer: legend | view-mode toggles                               │
└───────────────────────────────────────────────────────────────────┘
```

The diagram region takes ~70% of the width on desktop, the inspector ~30%. On narrow viewports (<900px), the inspector collapses below the diagram.

### Header

- **Case selector**: dropdown with "IEEE 9-bus", "IEEE 14-bus", "IEEE 30-bus". Default selection is **IEEE 9-bus**, loaded automatically on page open.
- **Solve status**: a compact indicator showing whether a solved-results file is available for the selected case (e.g. green dot "Solution loaded" or grey dot "Topology only — no solution data"). The visualization works with topology alone; results overlays are conditional on having solution data.
- **Iteration / convergence summary**: when results are available, show "Converged in N iterations, max mismatch X p.u." in small text.

### Network diagram

The central SVG. It must support:

- **Pan and zoom** (D3 `d3.zoom()`). Mouse wheel zooms, drag-on-empty-space pans. Reset-view button somewhere unobtrusive.
- **Drag-to-reposition** individual buses. The user can rearrange the layout by dragging buses; lines follow. Position changes persist for the session (no need to save to disk).
- **Initial layout**: use a force-directed layout (D3 `d3.forceSimulation`) seeded from the bus list, *with manual override coordinates baked into the case JSON files where available* (the IEEE cases have conventional published layouts — include those coordinates in the JSON, fall back to force layout if absent). After a few seconds the simulation should settle and stop (`alphaDecay` tuned so it doesn't jitter forever).
- **Node rendering** (buses): each bus is rendered with attached symbols indicating what's at it:
  - Slack bus: distinct symbol (e.g. double circle or different fill)
  - PV bus (has generator): generator symbol attached
  - PQ bus with load: load arrow attached
  - Buses can have both generator and load — show both symbols
  - Shunt elements (G_shunt, B_shunt non-zero): small shunt symbol
  - Bus label: bus number, plus voltage magnitude (when results loaded)
- **Edge rendering** (branches): lines between buses. Transformers (tap_ratio ≠ 1.0) are visually distinguished — e.g. with a small circle marker mid-line, or a different stroke pattern. Out-of-service branches (status = 0) shown dashed and greyed.
- **Power flow overlay** (when results loaded): arrowheads on each branch indicating direction of real power flow, with arrow size or line thickness proportional to flow magnitude (use a sqrt scale to keep extremes readable). A toggle in the footer enables/disables this overlay.
- **Voltage heatmap overlay** (when results loaded): bus fill color encodes voltage magnitude using a diverging color scale centered at 1.0 p.u. (e.g. blue for low voltage, white at 1.0, red for high voltage; clamp at 0.94 / 1.06). Toggle in the footer.

### Inspector panel

When the user clicks a bus, branch, or empty space:

- **Empty selection** (default / click background): show case-level summary — total generation (P, Q), total load, total losses, number of buses by type, number of branches.
- **Bus selected**: show bus ID, type, specified vs. solved values:
  - Specified: P_load, Q_load, P_gen, Q_gen (where applicable), V_specified (PV/slack)
  - Solved (if results loaded): V_magnitude, V_angle, P_injection, Q_injection
  - Shunts if non-zero
  - List of incident branches with their flows
- **Branch selected**: show endpoints, R, X, B, tap ratio, phase shift, status. When results loaded: P and Q at both ends, real and reactive losses, loading percentage if a rating is present (IEEE cases include `rate_a` — use it).

All numerical values displayed in monospace, right-aligned in a two-column key/value table, with units. Voltage in p.u. and kV (compute kV from base; the case base is typically 100 MVA but per-bus base kV is in the case data). Power in MW / MVAr (converted from p.u. using `base_mva`).

### Footer

- **Legend**: small panel showing what each symbol means (slack, PV, PQ, generator, load, transformer, shunt). Visible at all times.
- **View toggles**: checkboxes for "Show flow arrows", "Show voltage heatmap", "Show branch labels". Each independently togglable.

## Data contract

Case JSON files use the format produced by the v0 solver project. Concretely:

```json
{
  "name": "IEEE 9-bus",
  "base_mva": 100.0,
  "buses": [
    {
      "id": 1,
      "type": "slack",
      "p_load": 0.0,
      "q_load": 0.0,
      "p_gen": 0.0,
      "q_gen": 0.0,
      "v_magnitude": 1.04,
      "v_angle": 0.0,
      "g_shunt": 0.0,
      "b_shunt": 0.0,
      "base_kv": 16.5,
      "x_coord": 100,
      "y_coord": 200
    }
  ],
  "branches": [
    {
      "from_bus": 1,
      "to_bus": 4,
      "r": 0.0,
      "x": 0.0576,
      "b": 0.0,
      "tap_ratio": 1.0,
      "phase_shift": 0.0,
      "status": 1,
      "rate_a": 250.0
    }
  ]
}
```

Solution files (separately loaded, optional):

```json
{
  "case": "IEEE 9-bus",
  "converged": true,
  "iterations": 4,
  "max_mismatch": 1.2e-9,
  "buses": [
    { "id": 1, "v_magnitude": 1.04, "v_angle": 0.0, "p_injection": 0.7164, "q_injection": 0.2705 }
  ],
  "branches": [
    { "from_bus": 1, "to_bus": 4, "p_from": 0.7164, "q_from": 0.2705, "p_to": -0.7164, "q_to": -0.2393, "p_loss": 0.0, "q_loss": 0.0312 }
  ]
}
```

The visualization must handle the absence of solution files gracefully — topology-only display is a valid mode, not an error state.

If the v0 solver project doesn't yet emit JSON in exactly this shape, write a small adapter or document the shape clearly enough that adding an exporter to v0 is trivial. Don't fabricate solution numbers — if no solution file is present, show "no solution loaded" and don't render flow/voltage overlays.

### Coordinates for IEEE cases

Include hand-curated coordinates for the three IEEE cases in their JSON files, based on the conventional published one-line diagrams. These are well-known layouts:

- **9-bus**: the three-generator, three-load Anderson layout (gens at buses 1/2/3, loads at 5/6/8)
- **14-bus**: standard textbook layout with the two areas
- **30-bus**: standard 6-area textbook layout

Place coordinates in a viewBox-friendly range (e.g. 0–1000 in each axis). Approximations are fine; users can drag to refine.

## Suggested build order

Work in vertical slices, each one a working visualization. Don't build all the layout machinery before anything renders.

1. **Slice 1 — topology only, 9-bus, no interactivity.** Load `case9.json`, render buses as plain circles at their JSON coordinates, render branches as straight lines. No icons, no inspector, no zoom. Just verify the data flows end to end.
2. **Slice 2 — proper symbols.** Replace plain circles with the generator/load/slack/transformer symbols. Add the legend in the footer.
3. **Slice 3 — pan, zoom, drag.** D3 zoom on the SVG, drag handlers on bus groups, branches follow.
4. **Slice 4 — inspector panel.** Click handling, empty-state summary, bus details, branch details. Topology-only fields first.
5. **Slice 5 — case selector.** Dropdown, load 14-bus and 30-bus on demand. Verify all three render.
6. **Slice 6 — solution overlay.** Load solution JSON when available, add flow arrows and voltage heatmap, add the toggles, fill in solved values in the inspector.
7. **Slice 7 — polish.** Typography pass, spacing pass, hover states, keyboard shortcut for "reset view" (e.g. `r`), sensible loading/error states.

Each slice should be visually demoable. Don't move to the next slice until the current one works on all three cases (or, for slice 1, at least on 9-bus).

## Repository layout

```
powerflow-viz/
├── README.md            # how to run, what's implemented, screenshots if you take any
├── index.html           # the application
├── styles.css           # extracted styles (or inline in index.html — your call)
├── app.js               # extracted JS (or inline)
└── data/
    ├── case9.json
    ├── case9_solution.json
    ├── case14.json
    ├── case14_solution.json
    ├── case30.json
    └── case30_solution.json
```

Inline-vs-separated is a judgment call. Inline keeps it as a true single file; separated is more readable. Either is fine; if separated, keep file count small.

## Working style — what I want from you

- **Show me each slice working before moving on.** A short note like "Slice 3 done: zoom and drag work on 9-bus, screenshots verified" is enough. Don't disappear for an hour and return with everything done.
- **Pick the simplest thing that works.** If you're considering a sophisticated SVG technique, ask whether a plainer one would be just as readable. The visual quality target is "clean and considered", not "ambitious".
- **Don't invent data.** If the IEEE case is missing a field you'd like to display, leave it blank or omit it — don't make up a plausible-looking number. Same for solution data: missing means missing.
- **Test in the browser, not just in your head.** When you change a layout, open it and look at it. Layout bugs (overlapping labels, clipped icons, panels overflowing) are obvious visually and invisible in code.
- **If accessibility is easy, do it.** Semantic HTML, focus states, sufficient contrast. Don't go overboard — this is a desktop tool — but don't actively make it inaccessible.
- **No unrequested features.** No dark mode toggle, no export-to-PNG, no animation library, no tour overlay, no settings panel. The functional scope above is the entire scope.

## Definition of done

- All three IEEE cases (9, 14, 30) render correctly on page load (after case selection).
- 9-bus loads by default.
- Topology mode and solution-overlay mode both work; solution mode degrades gracefully when no solution file is present.
- Inspector panel shows correct details for buses, branches, and the empty-selection summary.
- Pan, zoom, and drag-to-reposition all work smoothly on a 30-bus case without lag.
- The page is usable on a 1280-wide laptop screen and degrades reasonably to ~900px wide.
- The README documents how to run it, the data format expected, and the known limitations.
- Total external dependencies: D3 (one CDN link). Nothing else.
- Visual feel: when I open it, my reaction is "this looks like a tool, not a toy."

When you reach this state, briefly summarize: which slices went smoothly, which fought you, and any visual or interaction tradeoffs you made that I should know about.
