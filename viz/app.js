(() => {
  "use strict";

  const CASES = [
    { id: "case9", label: "IEEE 9-bus" },
    { id: "case14", label: "IEEE 14-bus" },
    { id: "case30", label: "IEEE 30-bus" }
  ];

  const VIEWBOX_SIZE = 1000;
  const BUS_RADIUS = 19;
  const FLOW_MARGIN = 31;
  const EPSILON = 1e-9;

  const state = {
    caseId: "case9",
    caseData: null,
    solutionData: null,
    layoutData: null,
    busCoords: new Map(),
    solutionBusById: new Map(),
    generatorByBusId: new Map(),
    solutionBranchByPair: new Map(),
    solutionBranchByIndex: new Map(),
    selected: null,
    flowEnabled: false,
    heatmapEnabled: false
  };

  const els = {};
  const layers = {};
  let zoomBehavior;
  let voltageColor;

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    Object.assign(els, {
      caseSelect: document.querySelector("#case-select"),
      solveStatus: document.querySelector("#solve-status"),
      resetView: document.querySelector("#reset-view"),
      flowToggle: document.querySelector("#flow-toggle"),
      heatmapToggle: document.querySelector("#heatmap-toggle"),
      inspector: document.querySelector("#inspector-content"),
      svg: d3.select("#network")
    });

    voltageColor = d3.scaleDiverging([0.94, 1.0, 1.06], d3.interpolateBrBG).clamp(true);

    setupCaseSelector();
    setupSvg();
    setupControls();
    loadCase(state.caseId);
  }

  function setupCaseSelector() {
    for (const item of CASES) {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.label;
      els.caseSelect.append(option);
    }
    els.caseSelect.value = state.caseId;
  }

  function setupSvg() {
    const svg = els.svg;

    svg.selectAll("*").remove();

    const defs = svg.append("defs");
    defs.append("marker")
      .attr("id", "flow-arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 9)
      .attr("refY", 0)
      .attr("markerWidth", 5)
      .attr("markerHeight", 5)
      .attr("orient", "auto")
      .attr("markerUnits", "strokeWidth")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5Z")
      .attr("fill", "#0f6b70");

    layers.root = svg.append("g").attr("class", "zoom-root");
    layers.root.append("rect")
      .attr("class", "pan-surface")
      .attr("x", 0)
      .attr("y", 0)
      .attr("width", VIEWBOX_SIZE)
      .attr("height", VIEWBOX_SIZE)
      .on("click", () => selectNone());

    layers.branches = layers.root.append("g").attr("class", "branches-layer");
    layers.flows = layers.root.append("g").attr("class", "flows-layer");
    layers.buses = layers.root.append("g").attr("class", "buses-layer");
    layers.message = svg.append("g").attr("class", "message-layer");

    zoomBehavior = d3.zoom()
      .scaleExtent([0.45, 4])
      .filter((event) => {
        if (event.type === "wheel") return true;
        if (event.type === "mousedown") {
          return event.target === svg.node() || event.target.classList.contains("pan-surface");
        }
        return true;
      })
      .on("zoom", (event) => {
        layers.root.attr("transform", event.transform);
      });

    svg.call(zoomBehavior);
    svg.on("dblclick.zoom", null);
    svg.on("click", (event) => {
      if (event.target === svg.node()) {
        selectNone();
      }
    });
  }

  function setupControls() {
    els.caseSelect.addEventListener("change", () => loadCase(els.caseSelect.value));

    els.resetView.addEventListener("click", () => {
      els.svg.transition()
        .duration(180)
        .call(zoomBehavior.transform, d3.zoomIdentity);
    });

    els.flowToggle.addEventListener("change", () => {
      state.flowEnabled = els.flowToggle.checked;
      renderNetwork();
    });

    els.heatmapToggle.addEventListener("change", () => {
      state.heatmapEnabled = els.heatmapToggle.checked;
      renderNetwork();
    });
  }

  async function loadCase(caseId) {
    state.caseId = caseId;
    state.selected = null;
    setStatus("Loading", "");
    setMessage("Loading case...");
    els.inspector.innerHTML = `<p class="muted">Loading ${escapeHtml(labelForCase(caseId))}...</p>`;
    setOverlayControls(false);

    try {
      const [caseData, layoutData, solutionData] = await Promise.all([
        fetchJson(`../data/${caseId}.json`),
        fetchJson(`layouts/${caseId}.layout.json`),
        fetchJson(`../data/${caseId}_solution.json`, true)
      ]);

      state.caseData = caseData;
      state.layoutData = layoutData;
      state.solutionData = solutionData;
      state.busCoords = buildBusCoords(caseData, layoutData);
      buildSolutionIndexes(solutionData);

      state.flowEnabled = Boolean(solutionData);
      state.heatmapEnabled = Boolean(solutionData);
      setOverlayControls(Boolean(solutionData));
      els.flowToggle.checked = state.flowEnabled;
      els.heatmapToggle.checked = state.heatmapEnabled;

      if (solutionData) {
        setStatus("Solution loaded", "loaded");
      } else {
        setStatus("Topology only", "partial");
      }

      renderNetwork();
      updateInspector();
    } catch (error) {
      state.caseData = null;
      state.solutionData = null;
      state.layoutData = null;
      state.busCoords = new Map();
      setOverlayControls(false);
      setStatus("Load failed", "error");
      setMessage(error.message || String(error), true);
      els.inspector.innerHTML = `<p class="error-message">${escapeHtml(error.message || String(error))}</p>`;
    }
  }

  async function fetchJson(url, optional = false) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`${url} returned HTTP ${response.status}`);
      }
      return response.json();
    } catch (error) {
      if (optional) return null;
      throw error;
    }
  }

  function buildBusCoords(caseData, layoutData) {
    if (!layoutData || !layoutData.buses) {
      throw new Error("Layout file is missing a buses object");
    }

    const coords = new Map();
    const missing = [];

    for (const bus of caseData.buses) {
      const coord = layoutData.buses[String(bus.id)];
      if (!coord || !Number.isFinite(coord.x) || !Number.isFinite(coord.y)) {
        missing.push(bus.id);
      } else {
        coords.set(bus.id, { x: Number(coord.x), y: Number(coord.y) });
      }
    }

    if (missing.length > 0) {
      throw new Error(`Layout is missing coordinates for bus ${missing.join(", ")}`);
    }

    return coords;
  }

  function buildSolutionIndexes(solutionData) {
    state.solutionBusById = new Map();
    state.generatorByBusId = new Map();
    state.solutionBranchByPair = new Map();
    state.solutionBranchByIndex = new Map();

    if (!solutionData) return;

    for (const bus of solutionData.buses || []) {
      state.solutionBusById.set(bus.id, bus);
    }

    for (const generator of solutionData.generators || []) {
      state.generatorByBusId.set(generator.bus_id, generator);
    }

    (solutionData.branches || []).forEach((branch, index) => {
      state.solutionBranchByPair.set(pairKey(branch), branch);
      state.solutionBranchByIndex.set(index, branch);
    });
  }

  function renderNetwork() {
    layers.message.selectAll("*").remove();

    if (!state.caseData || !state.layoutData) {
      return;
    }

    renderBranches();
    renderFlows();
    renderBuses();
  }

  function renderBranches() {
    const branchGroups = layers.branches
      .selectAll("g.branch")
      .data(state.caseData.branches, branchDataKey);

    const entered = branchGroups.enter()
      .append("g")
      .attr("class", "branch")
      .on("click", (event, branch) => {
        event.stopPropagation();
        const index = state.caseData.branches.indexOf(branch);
        state.selected = { type: "branch", index };
        renderNetwork();
        updateInspector();
      });

    entered.append("line").attr("class", "branch-hit");
    entered.append("line").attr("class", "branch-line");

    const marker = entered.append("g").attr("class", "transformer-marker");
    marker.append("circle").attr("cx", -5).attr("cy", 0).attr("r", 7);
    marker.append("circle").attr("cx", 5).attr("cy", 0).attr("r", 7);

    branchGroups.exit().remove();

    const merged = entered.merge(branchGroups);
    merged
      .classed("selected", (branch) => isSelectedBranch(branch))
      .each((branch, index, nodes) => {
        const group = d3.select(nodes[index]);
        const from = coordFor(branch.from_bus);
        const to = coordFor(branch.to_bus);
        const angle = Math.atan2(to.y - from.y, to.x - from.x) * 180 / Math.PI;
        const mid = midpoint(from, to);

        group.select(".branch-hit")
          .attr("x1", from.x)
          .attr("y1", from.y)
          .attr("x2", to.x)
          .attr("y2", to.y);

        group.select(".branch-line")
          .attr("x1", from.x)
          .attr("y1", from.y)
          .attr("x2", to.x)
          .attr("y2", to.y);

        group.select(".transformer-marker")
          .attr("transform", `translate(${mid.x},${mid.y}) rotate(${angle})`)
          .style("display", isTransformer(branch) ? null : "none");
      });
  }

  function renderFlows() {
    const rows = state.solutionData && state.flowEnabled
      ? state.caseData.branches
        .map((branch, index) => ({ branch, index, solution: solutionForBranch(branch, index) }))
        .filter((row) => row.solution)
      : [];

    const maxFlow = d3.max(rows, (row) => Math.abs(row.solution.p_from)) || 1;
    const widthScale = d3.scaleSqrt().domain([0, maxFlow]).range([2.2, 9]);

    const flowLines = layers.flows
      .selectAll("line.flow-line")
      .data(rows, (row) => branchDataKey(row.branch, row.index));

    flowLines.enter()
      .append("line")
      .attr("class", "flow-line")
      .attr("marker-end", "url(#flow-arrow)")
      .merge(flowLines)
      .each((row, index, nodes) => {
        const endpoints = flowEndpoints(row.branch, row.solution);
        d3.select(nodes[index])
          .attr("x1", endpoints.start.x)
          .attr("y1", endpoints.start.y)
          .attr("x2", endpoints.end.x)
          .attr("y2", endpoints.end.y)
          .attr("stroke-width", widthScale(Math.abs(row.solution.p_from)));
      });

    flowLines.exit().remove();
  }

  function renderBuses() {
    const busGroups = layers.buses
      .selectAll("g.bus")
      .data(state.caseData.buses, (bus) => bus.id);

    const entered = busGroups.enter()
      .append("g")
      .attr("class", "bus")
      .on("click", (event, bus) => {
        event.stopPropagation();
        state.selected = { type: "bus", id: bus.id };
        renderNetwork();
        updateInspector();
      });

    entered.append("circle").attr("class", "bus-core").attr("r", BUS_RADIUS);
    entered.append("circle").attr("class", "slack-inner").attr("r", BUS_RADIUS - 6);

    const generator = entered.append("g").attr("class", "generator-glyph");
    generator.append("circle").attr("cx", 28).attr("cy", -18).attr("r", 11);
    generator.append("text").attr("x", 28).attr("y", -18).text("G");

    const load = entered.append("g").attr("class", "load-glyph");
    load.append("line").attr("x1", -30).attr("y1", 15).attr("x2", -30).attr("y2", 35);
    load.append("path").attr("d", "M-39,27 L-30,36 L-21,27");

    const shunt = entered.append("g").attr("class", "shunt-glyph");
    shunt.append("line").attr("x1", 27).attr("y1", 14).attr("x2", 27).attr("y2", 27);
    shunt.append("rect").attr("x", 20).attr("y", 27).attr("width", 14).attr("height", 9);

    entered.append("text").attr("class", "bus-label").attr("y", 1);
    entered.append("text").attr("class", "voltage-label").attr("y", 36);

    busGroups.exit().remove();

    const merged = entered.merge(busGroups);
    merged
      .attr("transform", (bus) => {
        const coord = coordFor(bus.id);
        return `translate(${coord.x},${coord.y})`;
      })
      .classed("selected", (bus) => state.selected?.type === "bus" && state.selected.id === bus.id)
      .each((bus, index, nodes) => {
        const group = d3.select(nodes[index]);
        const solutionBus = state.solutionBusById.get(bus.id);
        const fill = state.solutionData && state.heatmapEnabled && solutionBus
          ? voltageColor(solutionBus.v_magnitude)
          : "#fffdf8";

        group.select(".bus-core").attr("fill", fill);
        group.select(".slack-inner").style("display", bus.type === "slack" ? null : "none");
        group.select(".generator-glyph").style("display", hasGeneratorSymbol(bus) ? null : "none");
        group.select(".load-glyph").style("display", hasLoad(bus) ? null : "none");
        group.select(".shunt-glyph").style("display", hasShunt(bus) ? null : "none");
        group.select(".bus-label").text(bus.id);
        group.select(".voltage-label").text(solutionBus ? `${formatNumber(solutionBus.v_magnitude, 3)} p.u.` : "");
      });
  }

  function updateInspector() {
    if (!state.caseData) return;

    if (!state.selected) {
      renderSummaryInspector();
      return;
    }

    if (state.selected.type === "bus") {
      renderBusInspector(state.selected.id);
      return;
    }

    if (state.selected.type === "branch") {
      renderBranchInspector(state.selected.index);
    }
  }

  function renderSummaryInspector() {
    const buses = state.caseData.buses;
    const branches = state.caseData.branches;
    const counts = countBusTypes(buses);
    const rows = [
      ["Case", labelForCase(state.caseId)],
      ["Base MVA", formatNumber(baseMva(), 0)],
      ["Buses", String(buses.length)],
      ["Branches", String(branches.length)],
      ["Slack / PV / PQ", `${counts.slack} / ${counts.pv} / ${counts.pq}`],
      ["Total load P", formatPower(d3.sum(buses, (bus) => bus.p_load), "MW")],
      ["Total load Q", formatPower(d3.sum(buses, (bus) => bus.q_load), "MVAr")]
    ];

    if (state.solutionData) {
      rows.push(
        ["Solved generation P", formatPower(d3.sum(state.solutionData.generators || [], (gen) => gen.p_generation), "MW")],
        ["Solved generation Q", formatPower(d3.sum(state.solutionData.generators || [], (gen) => gen.q_generation), "MVAr")],
        ["Total real losses", formatPower(totalBranchLoss("p"), "MW")],
        ["Total reactive losses", formatPower(totalBranchLoss("q"), "MVAr")]
      );
    } else {
      rows.push(
        ["Scheduled generation P", formatPower(d3.sum(buses, (bus) => bus.p_gen), "MW")],
        ["Scheduled generation Q", formatPower(d3.sum(buses, (bus) => bus.q_gen), "MVAr")]
      );
    }

    els.inspector.innerHTML = `
      <h2>${escapeHtml(labelForCase(state.caseId))}</h2>
      ${kvHtml(rows)}
    `;
  }

  function renderBusInspector(busId) {
    const bus = state.caseData.buses.find((item) => item.id === busId);
    if (!bus) return renderSummaryInspector();

    const rows = [
      ["Bus ID", String(bus.id)],
      ["Type", bus.type.toUpperCase()],
      ["Case load P", formatPower(bus.p_load, "MW")],
      ["Case load Q", formatPower(bus.q_load, "MVAr")],
      ["Case generation P", formatPower(bus.p_gen, "MW")],
      ["Case generation Q", formatPower(bus.q_gen, "MVAr")]
    ];

    if (bus.type === "slack" || bus.type === "pv") {
      rows.push(["Voltage setpoint", formatPu(bus.v_magnitude, 3)]);
    }

    if (hasShunt(bus)) {
      rows.push(["g shunt", formatPu(bus.g_shunt, 5)]);
      rows.push(["b shunt", formatPu(bus.b_shunt, 5)]);
    }

    const solutionBus = state.solutionBusById.get(bus.id);
    const generator = state.generatorByBusId.get(bus.id);
    if (solutionBus) {
      rows.push(["Solved voltage", formatPu(solutionBus.v_magnitude, 3)]);
      rows.push(["Solved angle", `${formatNumber(solutionBus.v_angle_degrees, 3)} deg`]);
    }
    if (generator) {
      rows.push(["Solved generation P", formatPower(generator.p_generation, "MW")]);
      rows.push(["Solved generation Q", formatPower(generator.q_generation, "MVAr")]);
    }

    els.inspector.innerHTML = `
      <h2>Bus ${escapeHtml(bus.id)}</h2>
      ${kvHtml(rows)}
      <h3>Incident Branches</h3>
      ${incidentBranchesHtml(bus.id)}
    `;
  }

  function renderBranchInspector(index) {
    const branch = state.caseData.branches[index];
    if (!branch) return renderSummaryInspector();

    const solution = solutionForBranch(branch, index);
    const rows = [
      ["From bus", String(branch.from_bus)],
      ["To bus", String(branch.to_bus)],
      ["r", formatPu(branch.r, 5)],
      ["x", formatPu(branch.x, 5)],
      ["b", formatPu(branch.b, 5)],
      ["Tap ratio", formatNumber(branch.tap_ratio, 5)],
      ["Phase shift", `${formatNumber(branch.phase_shift, 5)} rad`]
    ];

    if (solution) {
      rows.push(
        ["P from", formatPower(solution.p_from, "MW")],
        ["Q from", formatPower(solution.q_from, "MVAr")],
        ["P to", formatPower(solution.p_to, "MW")],
        ["Q to", formatPower(solution.q_to, "MVAr")],
        ["P loss", formatPower(solution.p_from + solution.p_to, "MW")],
        ["Q loss", formatPower(solution.q_from + solution.q_to, "MVAr")]
      );
    }

    els.inspector.innerHTML = `
      <h2>Branch ${escapeHtml(branch.from_bus)}-${escapeHtml(branch.to_bus)}</h2>
      ${kvHtml(rows)}
    `;
  }

  function incidentBranchesHtml(busId) {
    const rows = state.caseData.branches
      .map((branch, index) => ({ branch, index, solution: solutionForBranch(branch, index) }))
      .filter((row) => row.branch.from_bus === busId || row.branch.to_bus === busId);

    if (rows.length === 0) {
      return `<p class="muted">No incident branches.</p>`;
    }

    const items = rows.map((row) => {
      const neighbor = row.branch.from_bus === busId ? row.branch.to_bus : row.branch.from_bus;
      const endName = row.branch.from_bus === busId ? "from end" : "to end";

      let values = "Topology only";
      if (row.solution) {
        const flow = row.branch.from_bus === busId
          ? { p: row.solution.p_from, q: row.solution.q_from }
          : { p: row.solution.p_to, q: row.solution.q_to };
        values = `P ${formatPower(flow.p, "MW")}, Q ${formatPower(flow.q, "MVAr")}`;
      }

      return `
        <li>
          <div class="incident-title">
            <span>${escapeHtml(row.branch.from_bus)}-${escapeHtml(row.branch.to_bus)}</span>
            <span>to bus ${escapeHtml(neighbor)}</span>
          </div>
          <div class="incident-values">${escapeHtml(endName)}: ${escapeHtml(values)}</div>
        </li>
      `;
    }).join("");

    return `<ul class="incident-list">${items}</ul>`;
  }

  function kvHtml(rows) {
    const items = rows
      .filter(([, value]) => value !== null && value !== undefined && value !== "")
      .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`)
      .join("");

    return `<dl class="kv">${items}</dl>`;
  }

  function selectNone() {
    state.selected = null;
    renderNetwork();
    updateInspector();
  }

  function setOverlayControls(enabled) {
    els.flowToggle.disabled = !enabled;
    els.heatmapToggle.disabled = !enabled;
    if (!enabled) {
      els.flowToggle.checked = false;
      els.heatmapToggle.checked = false;
      state.flowEnabled = false;
      state.heatmapEnabled = false;
    }
  }

  function setStatus(text, className) {
    els.solveStatus.textContent = text;
    els.solveStatus.className = `status-pill ${className}`.trim();
  }

  function setMessage(text, isError = false) {
    layers.branches?.selectAll("*").remove();
    layers.flows?.selectAll("*").remove();
    layers.buses?.selectAll("*").remove();
    layers.message?.selectAll("*").remove();
    layers.message?.append("text")
      .attr("class", isError ? "diagram-error" : "loading-text")
      .attr("x", VIEWBOX_SIZE / 2)
      .attr("y", VIEWBOX_SIZE / 2)
      .text(text);
  }

  function countBusTypes(buses) {
    return buses.reduce((acc, bus) => {
      acc[bus.type] = (acc[bus.type] || 0) + 1;
      return acc;
    }, { slack: 0, pv: 0, pq: 0 });
  }

  function totalBranchLoss(kind) {
    if (!state.solutionData) return 0;
    const fromKey = kind === "p" ? "p_from" : "q_from";
    const toKey = kind === "p" ? "p_to" : "q_to";
    return d3.sum(state.solutionData.branches || [], (branch) => branch[fromKey] + branch[toKey]);
  }

  function solutionForBranch(branch, index) {
    return state.solutionBranchByPair.get(pairKey(branch)) || state.solutionBranchByIndex.get(index) || null;
  }

  function pairKey(branch) {
    return `${branch.from_bus}->${branch.to_bus}`;
  }

  function branchDataKey(branch, index) {
    return `${branch.from_bus}->${branch.to_bus}#${index}`;
  }

  function isSelectedBranch(branch) {
    if (state.selected?.type !== "branch") return false;
    const selectedBranch = state.caseData.branches[state.selected.index];
    return selectedBranch === branch;
  }

  function isTransformer(branch) {
    return Math.abs(branch.tap_ratio - 1) > EPSILON || Math.abs(branch.phase_shift) > EPSILON;
  }

  function flowEndpoints(branch, solution) {
    const from = coordFor(branch.from_bus);
    const to = coordFor(branch.to_bus);
    const start = solution.p_from >= 0 ? from : to;
    const end = solution.p_from >= 0 ? to : from;
    return shortenSegment(start, end, FLOW_MARGIN);
  }

  function shortenSegment(start, end, margin) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.hypot(dx, dy);
    if (length <= margin * 2) {
      return { start, end };
    }

    const ux = dx / length;
    const uy = dy / length;
    return {
      start: { x: start.x + ux * margin, y: start.y + uy * margin },
      end: { x: end.x - ux * margin, y: end.y - uy * margin }
    };
  }

  function midpoint(a, b) {
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  }

  function coordFor(busId) {
    return state.busCoords.get(busId);
  }

  function hasLoad(bus) {
    return Math.abs(bus.p_load) > EPSILON || Math.abs(bus.q_load) > EPSILON;
  }

  function hasShunt(bus) {
    return Math.abs(bus.g_shunt) > EPSILON || Math.abs(bus.b_shunt) > EPSILON;
  }

  function hasGeneratorSymbol(bus) {
    return bus.type === "slack" || bus.type === "pv" || Math.abs(bus.p_gen) > EPSILON;
  }

  function baseMva() {
    return state.caseData?.base_mva || state.solutionData?.metadata?.base_mva || 1;
  }

  function labelForCase(caseId) {
    return CASES.find((item) => item.id === caseId)?.label || caseId;
  }

  function formatPower(valuePu, unit) {
    return `${formatNumber(valuePu * baseMva(), 2)} ${unit}`;
  }

  function formatPu(value, digits) {
    return `${formatNumber(value, digits)} p.u.`;
  }

  function formatNumber(value, digits) {
    if (!Number.isFinite(value)) return "n/a";
    const rounded = Math.abs(value) < 0.0000005 ? 0 : value;
    return rounded.toFixed(digits);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
})();
