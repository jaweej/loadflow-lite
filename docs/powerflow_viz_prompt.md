# Power Flow Visualization Tool — IEEE Benchmark Cases

## Objective

Build a single-page HTML visualization tool for inspecting the IEEE benchmark power-flow cases (9-bus, 14-bus, 30-bus) and their solved results that already live in this repo (`data/case{9,14,30}.json` and `data/case{9,14,30}_solution.json`). The tool renders a case as an interactive network diagram with inspectable buses and branches, optionally overlaid with solved results.

This is a viewer/inspector, not an editor. Users explore cases and results; they do not modify network topology in the browser.

## Where this lives

This is **not** a standalone repository. The visualization lives inside `loadflow-lite` at:

```
loadflow-lite/
├── data/                    # existing MATPOWER-derived fixtures (do not modify)
├── docs/
├── scripts/
├── src/
├── tests/
└── viz/                     # the new visualization tool — all viz code goes here
    ├── README.md
    ├── index.html
    ├── styles.css           # optional; may be inlined
    ├── app.js               # optional; may be inlined
    └── layouts/             # hand-curated bus coordinates (sidecar files)
        ├── case9.layout.json
        ├── case14.layout.json
        └── case30.layout.json
```

The viz reads the fixtures in `../data/` directly via `fetch()` (relative path). Do not duplicate the fixture JSON into `viz/`.

## Hard constraints

### No build step, no framework

The user must be able to run it by:

```
cd loadflow-lite/viz
python3 -m http.server 8000   # any static server; needed because fetch() of local files needs one
```

…and opening `http://localhost:8000`. That's the entire setup story.

Allowed dependencies:

- **D3.js v7** via CDN (SVG rendering, scales, drag, zoom)
- Plain HTML/CSS/JavaScript

Not allowed:

- React, Vue, Svelte, or any framework requiring a build step
- Tailwind, Bootstrap, or any CSS framework — write the CSS yourself
- jQuery
- Chart libraries
- Any package manager, bundler, or transpiler

If you find yourself wanting a framework, stop and ask.

### File structure: prefer separated, but few files

Use `index.html` + `styles.css` + `app.js`. Inlining everything into `index.html` is also acceptable if the file stays readable; pick one and stick with it. Don't split `app.js` into many modules — a single file is fine for this scope.

### Look and feel — professional, not flashy

Aesthetic target: a TSO/utility engineering tool, not a consumer app. Specifically:

- **Restrained color palette.** Neutral background (off-white `#fafafa` or very light grey), dark text (`#1a1a1a`), and a small set of accent colors used meaningfully. No gradients, no decorative shadows, no glassmorphism.
- **Clear typography.** A single sans-serif (system stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`) at 2–3 sizes. A monospace font for numerical values in the inspector panel.
- **Functional iconography.** Generators, loads, slack bus, transformers, and shunts each have a distinct inline-SVG representation. Conventional power-engineering symbols where sensible (circle with G inside for generator, downward arrow for load, double-circle for slack, two interlocking circles for transformer).
- **Whitespace and alignment matter.** Panels should feel deliberate, not crowded.

If you're tempted to make it "pop" with bright colors or large shadows, don't. The reference is closer to a Bloomberg terminal or a SCADA HMI than a startup landing page.

## Data contract — what the fixtures actually contain

**Read this carefully.** The repo's MATPOWER-derived fixtures are the source of truth and must not be modified. The shapes below are what's actually on disk today.

### Case file (e.g. `data/case9.json`)

```json
{
  "metadata": { "source_case": "case9", "matpower_version": "8.1", ... },
  "base_mva": 100,
  "buses": [
    {
      "id": 1,
      "type": "slack",          // "slack" | "pv" | "pq"
      "p_load": 0,
      "q_load": 0,
      "p_gen": 0.723,
      "q_gen": 0.2703,
      "v_magnitude": 1.04,      // specified (slack/PV) or initial (PQ)
      "v_angle": 0,             // RADIANS in case files
      "g_shunt": 0,
      "b_shunt": 0
    }
  ],
  "branches": [
    {
      "from_bus": 1,
      "to_bus": 4,
      "r": 0,
      "x": 0.0576,
      "b": 0,
      "tap_ratio": 1,
      "phase_shift": 0,         // radians
      "status": 1
    }
  ]
}
```

Fields **not** present in the case fixtures (don't try to read them):

- No `name` at top level — use `metadata.source_case` for display, or hardcode display labels in the case selector.
- No `x_coord`/`y_coord` on buses — coordinates live in sidecar `viz/layouts/case*.layout.json` (you author these).
- No `base_kv` per bus — therefore the inspector cannot show kV values; show p.u. only, and a separate "system base: 100 MVA" indicator in the header.
- No `rate_a` per branch — therefore no branch loading-percentage display. Skip that field in the inspector rather than fabricating a rating.

### Solution file (e.g. `data/case9_solution.json`)

```json
{
  "metadata": { "source_case": "case9", "base_mva": 100, "unit_conversions": "..." },
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

Important quirks to handle correctly:

- **Angle units differ.** Case files use `v_angle` in **radians**; solution files use `v_angle_degrees` in **degrees**. The inspector must show degrees consistently — convert from the case file when needed and label the unit.
- **No `converged` / `iterations` / `max_mismatch`** in the solution file. The header indicator should say "Solution loaded" / "No solution loaded" only; do not fabricate convergence metadata.
- **No `p_injection` / `q_injection` per bus.** Compute net bus injection in the viz from `generators` minus `p_load`/`q_load` if needed. State this derivation in the README.
- **No per-branch `p_loss` / `q_loss`.** Derive in the viz: `p_loss = p_from + p_to`, `q_loss = q_from + q_to`. State this in the README too.
- **Generators are a separate array** keyed by `bus_id`; a bus can have multiple generators (rare in IEEE 9/14/30 but possible). Sum per bus.

### Sidecar layout files (you author these)

Coordinates do not belong in the MATPOWER fixtures. Put them in `viz/layouts/case{9,14,30}.layout.json`:

```json
{
  "case": "case9",
  "viewbox": [0, 0, 1000, 1000],
  "buses": { "1": { "x": 100, "y": 200 }, "2": { "x": 300, "y": 200 } }
}
```

Hand-curate based on the conventional published one-line diagrams (Anderson layout for 9-bus; standard textbook layouts for 14 and 30). Approximations are fine; users can drag to refine for the session. If a bus is missing a coordinate, render it at the centroid and let drag handle the rest — no force simulation needed.

## Functional scope

### Layout

```
┌───────────────────────────────────────────────────────────────────┐
│  Header: case selector | solve status | system base               │
├───────────────────────────────────────────────────────────────────┤
│                                            │                      │
│        Network diagram (SVG)               │   Inspector panel    │
│        — pan/zoom enabled                  │   (selected item)    │
│                                            │                      │
├───────────────────────────────────────────────────────────────────┤
│  Footer: legend | view-mode toggles                               │
└───────────────────────────────────────────────────────────────────┘
```

Diagram ~70% width on desktop, inspector ~30%. Below ~900px, the inspector collapses below the diagram.

### Header

- **Case selector**: dropdown with "IEEE 9-bus", "IEEE 14-bus", "IEEE 30-bus". Default selection **IEEE 9-bus**, loaded automatically.
- **Solve status**: a compact indicator — green dot "Solution loaded" or grey dot "Topology only". The viz works with topology alone; results overlays are conditional.
- **System base**: small text "System base: 100 MVA" (read from `base_mva`).

### Network diagram

- **Pan and zoom** via `d3.zoom()`. Wheel zooms, drag-on-empty pans. Reset-view button somewhere unobtrusive; bind `r` to the same.
- **Drag-to-reposition** individual buses; lines follow. Position changes persist for the session only.
- **Initial layout**: read from the sidecar layout file. No force simulation — curated coordinates are sufficient. If a bus has no coordinate, place it at the case centroid and rely on the user to drag.
- **Node rendering** (buses):
  - Slack bus: distinct symbol (e.g. double circle).
  - PV bus: generator symbol attached.
  - PQ bus with non-zero load: load arrow attached.
  - Buses can have both generator and load — show both.
  - Non-zero `g_shunt`/`b_shunt`: small shunt symbol.
  - Label: bus ID, plus `v_magnitude` (p.u.) when results loaded.
- **Edge rendering** (branches): straight lines. Transformers (`tap_ratio ≠ 1.0` or `phase_shift ≠ 0`) get a small mid-line marker. Out-of-service branches (`status = 0`) shown dashed and greyed.
- **Power flow overlay** (when results loaded): arrowheads on each branch indicating direction of real power flow, with line thickness proportional to `|p_from|` (sqrt scale to keep extremes readable). Footer toggle.
- **Voltage heatmap overlay** (when results loaded): bus fill color encodes `v_magnitude` using a diverging scale clamped at 0.94/1.06 p.u., centered at 1.0. Use a colorblind-safe diverging palette (e.g. D3's `interpolatePuOr` or `interpolateBrBG`); avoid red/green pairings. Note: well-conditioned IEEE cases have voltages clustered near 1.0 — expect subtle coloring, that's correct, not a bug. Footer toggle.

### Inspector panel

When the user clicks a bus, branch, or empty space:

- **Empty selection**: case-level summary — total generation (sum of `p_gen`/`q_gen`), total load, total real losses (summed `p_from + p_to` across branches if solved), bus counts by type, branch count.
- **Bus selected**: bus ID, type, specified vs. solved values:
  - Specified: `p_load`, `q_load`, `p_gen`, `q_gen`, `v_magnitude` (PV/slack only).
  - Solved (if loaded): `v_magnitude`, `v_angle_degrees`, generator output from the `generators` array.
  - Shunts if non-zero.
  - List of incident branches with their `p_from`/`q_from` (when solved).
- **Branch selected**: endpoints, `r`, `x`, `b`, `tap_ratio`, `phase_shift`, `status`. When solved: `p_from`/`q_from`/`p_to`/`q_to`, derived `p_loss`/`q_loss`. **No loading percentage** — `rate_a` is not in the fixtures.

All numerical values monospace, right-aligned in a two-column key/value table, with units. Voltage in p.u. only (no kV — `base_kv` is not in the fixtures). Power in MW / MVAr (multiply p.u. by `base_mva`).

### Footer

- **Legend**: small panel showing what each symbol means (slack, PV, PQ, generator, load, transformer, shunt). Visible at all times.
- **View toggles**: checkboxes for "Show flow arrows", "Show voltage heatmap", "Show branch labels". Each independently togglable.

## Suggested build order

Work in vertical slices, each one a working visualization. Don't build all the layout machinery before anything renders.

1. **Slice 1 — topology only, 9-bus, no interactivity.** Load `../data/case9.json` and `viz/layouts/case9.layout.json`, render buses as plain circles at their layout coordinates, render branches as straight lines. No icons, no inspector, no zoom. Just verify the data flows end to end.
2. **Slice 2 — proper symbols.** Replace plain circles with the generator/load/slack/transformer symbols. Add the legend in the footer.
3. **Slice 3 — pan, zoom, drag.** D3 zoom on the SVG, drag handlers on bus groups, branches follow. Bind `r` for reset.
4. **Slice 4 — inspector panel.** Click handling, empty-state summary, bus details, branch details. Topology-only fields first.
5. **Slice 5 — case selector.** Dropdown, load 14-bus and 30-bus on demand. Verify all three render with their layout files.
6. **Slice 6 — solution overlay.** Load solution JSON when available, add flow arrows and voltage heatmap, add the toggles, fill in solved values in the inspector. Handle the radians-vs-degrees angle discrepancy explicitly.
7. **Slice 7 — polish.** Typography pass, spacing pass, hover/focus states, loading and error states, narrow-viewport check.

Each slice should be visually demoable. Don't move to the next slice until the current one works on all three cases (or, for slice 1, at least on 9-bus).

## Working style — what I want from you

- **Show me each slice working before moving on.** A short note like "Slice 3 done: zoom and drag work on 9-bus" is enough.
- **Pick the simplest thing that works.** If you're considering a sophisticated SVG technique, ask whether a plainer one would be just as readable.
- **Don't invent data.** If a fixture is missing a field you'd like to display, leave the row out — don't make up a plausible-looking number. The data-contract section above lists exactly what is and isn't present.
- **Don't modify `data/`.** The fixtures are MATPOWER-derived and reproducible from `scripts/`. All viz-side authoring (coordinates, display labels) goes under `viz/`.
- **Test in the browser, not just in your head.** Open it and look at it. Layout bugs (overlapping labels, clipped icons, panels overflowing) are obvious visually and invisible in code.
- **If accessibility is easy, do it.** Semantic HTML, focus states, sufficient contrast, colorblind-safe palette. Don't go overboard.
- **No unrequested features.** No dark mode toggle, no export-to-PNG, no animation library, no tour overlay, no settings panel.

## Definition of done

- All three IEEE cases (9, 14, 30) render correctly on case selection; 9-bus loads by default.
- Topology mode and solution-overlay mode both work; solution mode degrades gracefully when no solution file is present.
- Inspector panel shows correct details for buses, branches, and the empty-selection summary, with derived losses/injections labeled as derived in the README.
- Pan, zoom, and drag-to-reposition all work smoothly on the 30-bus case.
- The page is usable on a 1280-wide laptop and degrades reasonably to ~900px wide.
- `viz/README.md` documents how to run it, the data-contract assumptions (especially radians vs degrees, derived losses, missing fields), and known limitations.
- External dependencies: D3 only.
- Data fixtures under `data/` are unchanged.

When you reach this state, briefly summarize: which slices went smoothly, which fought you, and any visual or interaction tradeoffs you made that I should know about.
