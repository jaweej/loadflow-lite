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

Classify the branches into two groups:

- **Transmission-loop branches**:
  - `4-5`
  - `5-6`
  - `6-7`
  - `7-8`
  - `8-9`
  - `9-4`
- **Generator step-up / generator-connection branches**:
  - `1-4`
  - `3-6`
  - `8-2`

The transmission-loop outages should be the main N-1 AC power-flow
cases. The generator-connection outages should not be silently treated
as ordinary line outages: removing one isolates the corresponding
generator bus in this simplified network. Include them in the reported
contingency table, but classify them explicitly as disconnected/islanded
or out of scope for connected transmission-line N-1 analysis.

Do not implement generator redispatch or OPF unless a test and this
prompt are explicitly extended. The post-contingency power-flow cases
should keep:

- loads unchanged;
- bus types unchanged for connected branch outages;
- PV real-power setpoints unchanged;
- PV voltage setpoints unchanged;
- the original slack bus as slack, unless the contingency islands it.

### Violation Checks

Implement configurable limits with conservative defaults:

- bus voltage lower limit: `0.95 p.u.`;
- bus voltage upper limit: `1.05 p.u.`;
- solver convergence required;
- connectivity required for connected AC power-flow contingencies;
- branch thermal loading only if ratings exist.

The current fixtures do not include thermal ratings (`rate_a`) or
generator reactive limits (`Qmin`, `Qmax`). Do not fabricate them. The
analysis may report branch flows in MW/MVAr, but it must state that
thermal overload and Q-limit checks are unavailable from the current
fixture data.

### Outputs

Add a small, reviewable output artifact, preferably JSON, for the
computed N-1 results. A suggested path is:

```text
data/case9_n1_results.json
```

The JSON should include:

- metadata:
  - source case path;
  - base MVA;
  - solver tolerance;
  - voltage limits;
  - generation date or a deterministic omitted-date policy;
  - note that branch ratings and generator reactive limits are absent;
- base-case summary:
  - convergence;
  - min and max bus voltage;
  - total real loss;
  - total reactive endpoint sum;
- one row per contingency:
  - contingency id;
  - branch from/to;
  - branch group (`transmission_loop` or `generator_connection`);
  - status (`solved`, `islanded`, `non_converged`, or similar);
  - min voltage and bus id, if solved;
  - max voltage and bus id, if solved;
  - total real loss, if solved;
  - total reactive endpoint sum, if solved;
  - largest absolute branch-end MW flow, if solved;
  - voltage violations, if any;
  - explanatory notes.

Keep the JSON deterministic and pretty-printed so diffs are reviewable.
If dates make reproducibility annoying, omit them or provide a command
line flag for deterministic output.

## Suggested Implementation Shape

Prefer a small module under `src/powerflow/`, for example:

```text
src/powerflow/contingency.py
```

Likely functions/classes:

- `remove_branch(case, branch_index_or_id) -> Case`
- `classify_case9_branch(branch) -> str`
- `run_branch_outage(case, branch_index, limits) -> ContingencyResult`
- `run_case9_n1(case, limits) -> N1Report`
- serialization helpers that convert dataclasses to plain dicts

Prefer dataclasses for result records. Keep CLI/file-writing code thin,
for example:

```text
scripts/run_case9_n1.py
```

The script should read `data/case9.json`, run the analysis, and write the
deterministic JSON result.

## Test Plan — Red/Green Order

Use focused pytest tests. Suggested sequence:

1. **Branch removal preserves the base case except for the removed
   branch.**
   - Red: assert that removing branch `4-5` returns a new `Case` with
     one fewer branch and leaves the original case unchanged.
   - Green: implement `remove_branch`.

2. **Branch removal triggers connectivity detection for a generator
   connection outage.**
   - Red: remove branch `1-4` and assert validation/connectivity reports
     an islanded network.
   - Green: implement or route through existing connectivity checks.

3. **Transmission-loop branch classification is correct.**
   - Red: assert `4-5` is `transmission_loop` and `1-4` is
     `generator_connection`.
   - Green: implement classification.

4. **A connected transmission-loop outage solves.**
   - Red: run one outage such as `4-5`; assert status is `solved`,
     voltages are present, and branch count is one less.
   - Green: implement one-contingency solve.

5. **Generator-connection outage is reported, not solved as an ordinary
   case.**
   - Red: run outage `1-4`; assert status is `islanded` and no solved
     voltage table is claimed.
   - Green: add structured error handling.

6. **Full case9 report has nine branch contingencies.**
   - Red: assert six `transmission_loop` rows and three
     `generator_connection` rows.
   - Green: implement report iteration.

7. **Voltage violation detection is deterministic.**
   - Red: feed a tiny synthetic solved-voltage record with one low and
     one high voltage; assert both violations are detected with bus ids.
   - Green: implement limit checks.

8. **Base-case consistency remains anchored to existing MATPOWER
   fixture.**
   - Red: assert the base solve still reproduces
     `data/case9_solution.json` within existing tolerances.
   - Green: reuse existing solver tests or add a narrow regression test
     if coverage is missing.

9. **JSON output is deterministic.**
   - Red: serialize the same report twice and assert identical strings
     or identical parsed dicts.
   - Green: implement stable serialization with sorted keys and fixed
     numeric formatting where appropriate.

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
- each solved contingency satisfies AC power balance:
  - total solved net active injection equals total branch real losses;
  - total solved net reactive injection equals total branch reactive
    endpoint sum;
- all solved contingency results use the same branch endpoint sign
  convention as `compute_branch_flows`;
- islanded contingencies are classified before attempting to interpret
  voltage or flow results;
- the report never claims thermal overload or Q-limit compliance when
  ratings/limits are absent;
- rerunning the analysis produces the same JSON output, aside from any
  deliberately documented timestamp field.

If MATPOWER/Octave is already available locally, optionally add an
independent spot-check by running equivalent branch-removal power flows
for the six connected transmission-loop outages. Do not introduce a new
runtime test dependency on MATPOWER. Any MATPOWER comparison should be a
separate reproducibility check or static fixture generation step, not a
normal unit-test dependency.

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

