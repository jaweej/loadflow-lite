# IEEE 9-Bus N-1 Analysis — Red/Green TDD Implementation Prompt

## Objective

Implement and document an AC N-1 contingency analysis for the IEEE 9-bus
system in this repository.

The result should be both executable and pedagogical:

- executable Python code that applies one-at-a-time contingencies to
  `data/case9.json`, resolves the AC power flow, and summarizes
  violations;
- focused tests developed with strict red/green TDD;
- a LaTeX note in `docs/` that explains the method, assumptions,
  contingencies, results, and limitations.

Correctness, traceability, and reproducibility matter more than feature
count.

## Current Repo Context

The repository already contains:

- `src/powerflow/case.py` with `Bus`, `Branch`, `Case`, validation, and
  connectivity checks;
- `src/powerflow/solver.py` with Newton-Raphson AC power flow;
- `src/powerflow/flows.py` and `src/powerflow/ybus.py`;
- MATPOWER-derived fixtures:
  - `data/case9.json`
  - `data/case9_solution.json`
  - larger benchmark cases and solutions;
- an existing lecture note:
  - `docs/ieee9_power_flow_lecture_note.tex`
  - `docs/ieee9_power_flow_lecture_note.pdf`

Branch `status != 1` is currently rejected by validation, so model a
branch outage by constructing a new `Case` with that branch removed,
unless you deliberately extend the data model with tests first.

## Methodology — Strict Red/Green TDD

Use the red/green/refactor loop for every behavioral change.

1. **Red**: write the smallest failing test that captures the desired
   behavior. Run it and confirm it fails for the intended reason.
2. **Green**: write the minimum implementation that makes the test pass.
3. **Refactor**: clean up only with the passing tests as a safety net.

Do not write implementation code before a failing test exists. Do not
generalize beyond the next test. When a failure appears, inspect the
failure carefully before changing code.

Commit at natural milestones only after tests pass.

## Scope

### Contingencies

For the 9-bus branch outage study, use the branches in
`data/case9.json`.

#### Branch identifier convention

Branches in `data/case9.json` are an indexed list with `from_bus` and
`to_bus`; they have no string id. Within the implementation use the
ordered tuple `(from_bus, to_bus)` exactly as it appears in the JSON
(e.g. `(8, 2)`, not `(2, 8)`). The classification helper must accept
that tuple form. Human-readable display strings like `"8-2"` should be
derived from the tuple, not parsed from user input.

#### Branch classification

Classify the branches into two groups (tuples reflect the JSON
orientation):

- **Transmission-loop branches**:
  - `(4, 5)`
  - `(5, 6)`
  - `(6, 7)`
  - `(7, 8)`
  - `(8, 9)`
  - `(9, 4)`
- **Generator step-up / generator-connection branches**:
  - `(1, 4)`
  - `(3, 6)`
  - `(8, 2)`

Do not hardcode the count `9` anywhere. Tests should derive the total
from `len(case.branches)` and assert that the two groups partition that
total exactly.

#### Post-contingency status taxonomy

Removing a generator-connection branch partitions the graph but does
**not** uniformly make the case unsolvable. The three cases differ:

- `(1, 4)` islands bus 1, which is the **slack**. The remaining 8-bus
  component is connected but has no slack reference, so AC PF cannot be
  formulated without redesignating slack. Status: `slack_islanded`.
- `(3, 6)` islands bus 3 (a PV generator). The remaining 8-bus
  component contains the slack and all load and **is solvable**; the
  ~85 MW gap is absorbed by the slack.
- `(8, 2)` islands bus 2 (a PV generator). Same shape as `(3, 6)`;
  remaining island is solvable and ~163 MW lands on the slack.

Use a three-valued status for these cases:

- `slack_islanded` — the surviving connected component containing load
  has no slack reference; do not solve.
- `partial_island` — exactly one PV generator bus is islanded, and the
  surviving component containing the slack and all load is solved with
  the missing generation absorbed by the slack. Report the solved
  result on the surviving component, plus the list of islanded bus ids.
- `solved` — full network connected and solved.

Reserve `non_converged` for the case where the solver fails on a
connected, slack-bearing network.

Do not implement generator redispatch or OPF unless a test and this
prompt are explicitly extended. The `partial_island` policy of dumping
the lost generation onto the slack is the **modeling choice** here; it
is not a graph-theoretic necessity, and the LaTeX note must say so.

The post-contingency power-flow cases should keep:

- loads on the surviving connected component unchanged;
- bus types unchanged for surviving buses;
- PV real-power setpoints unchanged for surviving PV buses;
- PV voltage setpoints unchanged for surviving PV buses;
- the original slack bus as slack whenever it survives.

### Violation Checks

Implement a configurable limits dataclass with conservative defaults:

```python
@dataclass(frozen=True)
class Limits:
    v_min: float = 0.95
    v_max: float = 1.05
    q_gen_sanity_limit_pu: float = 2.0
```

- solver convergence required for `solved` and `partial_island`;
- connectivity of the slack-containing component required for any
  AC PF attempt;
- branch thermal loading checked only if ratings exist.

In addition to absolute violations, report **delta-from-base**: for
each surviving bus, `v_post - v_base`. The IEEE-9 base case already
operates near the upper band (`V_6 ≈ 1.032`, `V_slack = 1.04`), so a
small absolute violation is often less informative than the change
induced by the contingency.

The current fixtures do not include thermal ratings (`rate_a`) or
generator reactive limits (`Qmin`, `Qmax`). Do not fabricate them. The
analysis must:

- report branch endpoint flows with explicit unit suffixes, e.g.
  `p_from_mw`, `q_from_mvar`, `p_to_mw`, and `q_to_mvar`;
- state that thermal overload checks are unavailable from the current
  fixture data;
- state that Q-limit enforcement (PV→PQ conversion) is not performed;
- nevertheless, **report the computed reactive output at every
  surviving generator bus** (slack and PV) in each solved/partial-island
  result, so a reader can spot implausibly large Q demands even though
  no limit is enforced.

### Outputs

Add a small, reviewable output artifact, preferably JSON, for the
computed N-1 results. A suggested path is:

```text
data/case9_n1_results.json
```

The JSON should include:

- explicit unit suffixes for every power quantity. Use p.u. on
  `base_mva` for solver-native quantities with `_pu` suffixes; use
  `_mw` and `_mvar` suffixes for converted human-readable branch-flow
  and generator-output quantities. Avoid unsuffixed power keys such as
  `q_gen` or `total_real_loss`;
- metadata (mirror existing key names from `data/case9.json` where
  applicable):
  - `source_case` (string, matching the existing convention);
  - `base_mva`;
  - `solver_tolerance`;
  - `voltage_limits` (object with `v_min`, `v_max`);
  - `q_gen_sanity_limit_pu`;
  - **no timestamp by default**; the script may accept an optional
    `--timestamp` flag that injects an ISO-8601 string, but default
    output omits all date/time fields for byte-stable diffs;
  - `caveats`: array of short strings noting that branch thermal
    ratings and generator Q-limits are absent;
- base-case summary:
  - convergence;
  - min and max bus voltage;
  - `total_real_loss_pu` (`Σ_branches p_loss`) and
    `total_real_loss_mw`;
  - `branch_reactive_endpoint_sum_pu` and
    `branch_reactive_endpoint_sum_mvar`, defined explicitly as
    `Σ_branches (q_from + q_to)`. Note in the metadata that this
    quantity includes line charging as a negative contribution and is
    NOT the same as "reactive losses" in the colloquial sense.
- one row per contingency:
  - contingency id (the tuple display string, e.g. `"8-2"`);
  - `from_bus`, `to_bus` (integers);
  - `group` (`transmission_loop` or `generator_connection`);
  - `status` (`solved`, `partial_island`, `slack_islanded`, or
    `non_converged`);
  - `islanded_buses`: list of bus ids in the disconnected component
    (empty for `solved`);
  - for `solved` and `partial_island`:
    - min voltage and bus id;
    - max voltage and bus id;
    - largest `|v_post - v_base|` and bus id;
    - `total_real_loss_pu` and `total_real_loss_mw` on the surviving
      component;
    - `branch_reactive_endpoint_sum_pu` and
      `branch_reactive_endpoint_sum_mvar` on the surviving component;
    - largest absolute branch-end MW flow as `largest_abs_branch_end_mw`;
    - branch endpoint flow rows with explicit `_mw` and `_mvar`
      suffixes;
    - per-generator reactive output records for surviving slack and PV
      buses, including `bus_id`, `bus_type`, `q_gen_pu`, and
      `q_gen_mvar`;
    - voltage violations, if any (with bus id and `v_post_pu`).
  - explanatory notes (e.g. "bus 2 islanded; 1.63 p.u. / 163 MW of
    generation absorbed by slack").

Keep the JSON deterministic and pretty-printed (sorted keys, fixed
float repr) so diffs are reviewable.

## Suggested Implementation Shape

Prefer a small module under `src/powerflow/`, for example:

```text
src/powerflow/contingency.py
```

Required functions/classes (signatures pinned so the TDD steps have an
unambiguous contract):

- `remove_branch(case: Case, branch_index: int) -> Case`
  - Returns a new `Case` with `case.branches[branch_index]` removed.
  - Does **not** call `validate_case`; the result may be disconnected
    or otherwise invalid by design. The caller is responsible for
    connectivity inspection.
  - Must not mutate the input (use list slicing, not `.pop`).
- `connected_components(case: Case) -> list[set[int]]`
  - Pure graph helper, independent of `validate_case`. Returns the
    bus-id partition.
- `classify_outage(case: Case, branch_index: int) -> OutageTopology`
  - `OutageTopology` is a dataclass with: `slack_islanded: bool`,
    `islanded_buses: list[int]`, `surviving_buses: list[int]`,
    `surviving_case: Case | None` (None iff `slack_islanded`).
  - The surviving subcase has buses and branches restricted to the
    slack-containing component, and must independently pass
    `validate_case`.
- `classify_case9_branch(from_to: tuple[int, int]) -> str`
  - Accepts the directional tuple as it appears in `data/case9.json`
    (e.g. `(8, 2)`). Reject reversed orientations explicitly with a
    `ValueError` so a caller can't silently miss a classification.
- `run_branch_outage(case, branch_index, limits) -> ContingencyResult`
- `run_case9_n1(case, limits) -> N1Report`
- serialization helpers that convert dataclasses to plain dicts.

Prefer dataclasses for result records. Keep CLI/file-writing code thin,
for example:

```text
scripts/run_case9_n1.py
```

The script should read `data/case9.json`, run the analysis, and write the
deterministic JSON result.

## Test Plan — Red/Green Order

Use focused pytest tests. Base-case regression against
`data/case9_solution.json` is a precondition (already covered by
`tests/test_ieee_cases.py`); do not duplicate it as a TDD step.

Suggested sequence:

1. **`remove_branch` returns a new `Case` without revalidating.**
   - Red: assert that `remove_branch(case, idx_of_4_5)` returns a new
     `Case` with one fewer branch, leaves the input branch list
     untouched (identity-check the original list contents), and does
     **not** raise even when called for the `(1, 4)` slack-islanding
     branch.
   - Green: implement `remove_branch` via list slicing; do not call
     `validate_case`.

2. **`connected_components` partitions the bus set correctly.**
   - Red: on the base case, assert one component containing all bus
     ids. On `remove_branch(case, idx_of_1_4)`, assert two components,
     one being `{1}`. On `remove_branch(case, idx_of_3_6)`, assert
     `{3}` is islanded.
   - Green: implement BFS/DFS over the branch list.

3. **`classify_outage` distinguishes `slack_islanded` from
   `partial_island` from connected.**
   - Red: assert `(1, 4)` → `slack_islanded=True`,
     `surviving_case is None`. Assert `(3, 6)` →
     `slack_islanded=False`, `islanded_buses == [3]`,
     `validate_case(surviving_case)` does not raise. Assert `(4, 5)` →
     `slack_islanded=False`, `islanded_buses == []`,
     `surviving_case` equals `remove_branch(case, idx)`.
   - Green: implement classification.

4. **Branch classification is orientation-strict.**
   - Red: `classify_case9_branch((4, 5)) == "transmission_loop"`,
     `classify_case9_branch((1, 4)) == "generator_connection"`,
     `classify_case9_branch((8, 2)) == "generator_connection"`,
     `classify_case9_branch((2, 8))` raises `ValueError`.
   - Green: implement classification with strict tuple lookup.

5. **A connected transmission-loop outage solves.**
   - Red: run `(4, 5)`; assert `status == "solved"`, voltages present
     for every base-case bus id, branch count is one less than base.
   - Green: implement single-contingency solve.

6. **A `partial_island` outage solves on the surviving component.**
   - Red: run `(3, 6)`; assert `status == "partial_island"`,
     `islanded_buses == [3]`, voltages present for buses
     `{1, 2, 4, 5, 6, 7, 8, 9}` only, slack `p_gen` increased relative
     to base by the islanded generator's lost `p_gen` plus the change
     in total real losses within tolerance, and generator reactive
     output records are reported for surviving generator buses 1 and 2.
   - Green: implement surviving-component solve path.

7. **A `slack_islanded` outage is not solved.**
   - Red: run `(1, 4)`; assert `status == "slack_islanded"`,
     `islanded_buses == [1]`, no voltage table is produced, and an
     explanatory note is present.
   - Green: short-circuit before attempting a solve.

8. **Full case9 report uses derived counts.**
   - Red: assert
     `sum(1 for r in report.rows if r.group == "transmission_loop")
     + sum(1 for r in report.rows if r.group == "generator_connection")
     == len(case.branches)`. Then assert each group's count equals
     the number of branches in `data/case9.json` of that class
     (recomputed from the case, not hardcoded).
   - Green: implement report iteration.

9. **Voltage violation detection is deterministic.**
   - Red: feed a synthetic per-bus voltage map with one low and one
     high voltage; assert both violations are detected with bus ids.
     Add a second assertion that delta-from-base reporting flags the
     bus with the largest absolute change even when no absolute limit
     is breached.
   - Green: implement limit + delta checks.

10. **N-1 results match a MATPOWER reference fixture for the six
    connected outages.**
    - Red: assert each transmission-loop outage's per-bus voltages
      match `data/case9_n1_solutions.json` within the existing solver
      tolerance.
    - Green: regenerate the fixture via a sibling MATPOWER script
      following the pattern of `scripts/generate_matpower_fixtures.m`.
      The pytest test should consume the generated static fixture only;
      do not run MATPOWER/Octave from pytest.

11. **JSON output is byte-identical across runs.**
    - Red: serialize the same report twice and assert the byte strings
      are equal. Then run the script twice and `diff` the produced
      files; the diff must be empty.
    - Green: implement stable serialization with sorted keys and a
      fixed float repr; omit timestamps by default.

## Robust Verification Strategy

Verification must go beyond "the tests pass."

Run and record:

```bash
pytest
python scripts/run_case9_n1.py
pytest
pdflatex -interaction=nonstopmode -halt-on-error -output-directory /tmp docs/<n1-note>.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory /tmp docs/<n1-note>.tex
```

Then copy the generated PDF from `/tmp` into `docs/` if the note is meant
to be committed as a PDF.

For numerical verification, include these checks:

- base-case voltages and flows match `data/case9_solution.json` within
  the repo's existing tolerances;
- each `solved` or `partial_island` contingency satisfies AC power
  balance on the surviving component:
  - `Σ_buses (p_gen − p_load) == Σ_branches p_loss` (case9 has no
    shunts; if shunts are added later this check must add the shunt
    term explicitly);
  - `Σ_buses (q_gen − q_load) == Σ_branches (q_from + q_to)`. Note
    that the right-hand side is the **branch reactive endpoint sum**
    as defined in the Outputs section, NOT a "reactive losses"
    quantity — it includes line charging as a negative contribution.
- all solved contingency results use the same branch endpoint sign
  convention as `compute_branch_flows` in `src/powerflow/flows.py`;
- `slack_islanded` and `partial_island` cases are classified before
  any attempt to interpret voltages or flows;
- for `partial_island`, the slack `p_gen` increase must equal the
  islanded generator's lost `p_gen` plus the change in total losses
  (within tolerance);
- the report never claims thermal overload or Q-limit compliance when
  ratings/limits are absent;
- per-generator `q_gen_pu` is reported for surviving slack and PV
  generator buses, and a soft warning string is emitted in the row's
  notes when `abs(q_gen_pu)` exceeds `q_gen_sanity_limit_pu`;
- rerunning the analysis produces a byte-identical JSON file by
  default (timestamp omitted unless `--timestamp` is passed).

The MATPOWER/Octave cross-check on the six connected transmission-loop
outages is **required** as a fixture (`data/case9_n1_solutions.json`),
not optional. The fixture must be regenerated by a sibling MATPOWER
script following the existing
`scripts/generate_matpower_fixtures.m` pattern. The test that consumes
the fixture must `pytest.skip` only when the fixture file is missing,
with a clear message. Do not introduce a runtime dependency on
MATPOWER/Octave.

## LaTeX Note Requirement

Write up the results in a LaTeX note in `docs/`, for example:

```text
docs/ieee9_n1_analysis_note.tex
docs/ieee9_n1_analysis_note.pdf
```

The note should be concise but complete. Include:

- purpose and definition of N-1 analysis;
- what is included and excluded for this 9-bus study;
- base-case operating point summary;
- contingency list and branch classification;
- explanation of why generator-connection outages are islanding/out of
  scope for ordinary connected line-outage power flow;
- table of solved transmission-loop outage results;
- table or paragraph for islanded generator-connection outages;
- voltage-limit results;
- clear statement that branch thermal ratings and generator reactive
  limits are not present in the fixtures, so overload and Q-limit
  conclusions cannot be drawn;
- discussion of limitations:
  - no OPF or redispatch;
  - no dynamic or transient stability;
  - no protection modeling;
  - no load shedding;
  - no reactive limit enforcement / PV-to-PQ conversion.

Compile the LaTeX note twice and ensure the final log has no unresolved
references, overfull boxes, or warnings that indicate a broken document.

## Acceptance Criteria

The task is complete when:

- every new behavior was introduced through red/green TDD;
- `pytest` passes;
- the N-1 script produces deterministic results for all nine branch
  contingencies in the IEEE 9-bus fixture;
- the report distinguishes solved connected line outages from islanding
  generator-connection outages;
- no result claims unsupported thermal-rating or generator-Q-limit
  compliance;
- a LaTeX note and compiled PDF exist in `docs/`;
- the final LaTeX build log is clean;
- the final git diff is limited to the implementation, tests, result
  artifact, and docs needed for this task.
