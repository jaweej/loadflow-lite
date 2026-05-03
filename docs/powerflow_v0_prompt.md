# Power Flow v0 — From-Scratch Python Newton-Raphson Implementation

## Objective

Build a minimal, correct AC Newton-Raphson power flow solver in Python, validated against the standard IEEE benchmark cases. The purpose is pedagogical: I want to feel the numerical machinery underneath PyPSA/pandapower in my hands. Correctness is the only success criterion — speed, generality beyond what's specified, and elegance are explicitly secondary.

## Hard constraints

### Dependencies — keep minimal

You may use **only**:

- `numpy` (linear algebra, sparse not required at this scale)
- `pytest` (testing)
- Python standard library (`dataclasses`, `pathlib`, `json`, `math`)

You may **not** use:

- `pandapower`, `PYPOWER`, `pypsa`, `scipy.sparse.linalg.spsolve`, or any other power-system library
- `pandas` (overkill for this scope; use plain dicts/dataclasses)
- `scipy` for solving the linear system — use `numpy.linalg.solve`

The point is to write the Newton-Raphson and Y-bus assembly by hand. If you find yourself wanting another package, stop and ask.

### Methodology — strict red/green TDD

Every piece of functionality must be developed in the red/green/refactor cycle:

1. **Red**: Write a failing test that pins down the expected behavior. Run it, confirm it fails for the right reason (not an import error or typo).
2. **Green**: Write the *minimum* code that makes the test pass. Resist the urge to generalize ahead of need.
3. **Refactor**: Clean up only with the test as a safety net.

After each green, briefly state what passed and what changed. Commit at natural milestones. Do not write a function before its test exists. Do not write code "you'll need later" — wait for the test that requires it.

When a test fails, **read the failure message carefully before changing code**. If you don't understand why it failed, write a smaller test that isolates the question, don't guess.

### Validation — rigorous, against published references

The implementation must reproduce solved MATPOWER reference outputs for the IEEE benchmark cases to high precision. Specifically:

- **Bus voltage magnitudes**: agree to within `1e-4` p.u.
- **Bus voltage angles**: agree to within `1e-3` degrees
- **Line flows (P and Q at both branch ends)**: agree to within `1e-3` p.u. (i.e. 0.1 MW at 100 MVA base), with the same branch orientation and sign convention as MATPOWER
- **Slack bus generation**: agree to within `1e-3` p.u.

Input case data must be transcribed from MATPOWER's published case files (`case9.m`, `case14.m`, `case30.m`) into your own Python or JSON format, with a citation to the MATPOWER source file and version. Use those exact cases. MATPOWER also provides `case_ieee30.m`; do not substitute it for `case30.m` unless this prompt is explicitly changed. `case30` is based on the IEEE 30-bus case but is not identical to `case_ieee30`. Do not depend on a MATPOWER parser library, and do not read `.m` case files at test time.

Do not assume official static JSON solution fixtures already exist online. Reference solution fixtures must be generated once by running MATPOWER `runpf` with a named MATPOWER version under GNU Octave and committed as static JSON.

For this repo's default environment, assume Linux/WSL with `apt-get`. If GNU Octave is not already available, install it as a system tool so `octave` is available on `PATH`, normally at `/usr/bin/octave`:

```bash
sudo apt-get update
sudo apt-get install -y octave
```

Install/download MATPOWER outside the Python package in a repo-local ignored tooling directory:

```bash
mkdir -p .external
# Add ".external/" to .gitignore before downloading MATPOWER.
# Then download or clone a named MATPOWER release into .external/matpower/.
```

Prefer a tagged MATPOWER release over an unpinned moving branch. Record the exact MATPOWER version or commit, the source URL, and the Octave version in `data/README.md`. It is part of this task to solve any Octave/MATPOWER setup issues that arise. The Python project itself must not gain a runtime or test dependency on Octave, MATPOWER, PYPOWER, pandapower, or any other power-system package.

Each solution fixture must include bus voltage magnitudes and angles, generator real and reactive outputs, and branch `PF`, `QF`, `PT`, and `QT` values. Each fixture must also include a `metadata` object recording the MATPOWER version, Octave version, command/options used, base MVA, date generated, and any unit/sign conversions applied. JSON has no comments, so do not rely on comment syntax for provenance. The fixtures must not be computed during tests.

### Execution model — minimize permission interruptions

Separate the work into two phases.

**Phase 1: permission/setup phase.** Before starting the solver implementation, do all approval-gated setup and verification:

1. Check whether `octave`, `git`, Python, and the project `.venv` are available.
2. Install GNU Octave via `apt-get` if needed.
3. Add `.external/` to `.gitignore`, create `.external/`, and download/clone a pinned MATPOWER release into `.external/matpower/`.
4. Use the project `.venv` for Python dependencies; install only `numpy` and `pytest` there if they are missing.
5. Verify `octave --version`, MATPOWER version/commit, and a smoke `runpf('case9')` before beginning the Python implementation.

Batch the expected permission requests in this phase as much as the environment allows. Network access, `sudo`, `apt-get`, package installation, and external downloads belong here, not in the implementation phase.

**Phase 2: autonomous build phase.** After setup succeeds, continue without asking for permissions unless something genuinely impossible appears. This phase should use only local repo writes, the already-installed `.venv`, the already-installed Octave/MATPOWER tooling, and normal test commands. Do not introduce new system packages, Python packages, external services, Docker images, or network downloads during this phase. Prefer Python standard-library scripts over new command-line utilities such as `jq`. If optional tooling is missing, work around it with existing Python/Octave capabilities instead of asking to install more software. If an unexpected permission need arises, pause and explain exactly why it is necessary.

## Scope — what to build

### Core solver

A Newton-Raphson AC power flow with:

1. **Y-bus assembly** from a line/transformer list. Lines have `(from_bus, to_bus, r, x, b, tap_ratio, phase_shift)`. Phase shifters can be 0 for v0 but the data structure must accommodate them. Shunt admittances at buses are a separate input.
2. **Bus type handling**: slack (V, θ fixed), PV (P, V fixed), PQ (P, Q fixed). Exactly one slack bus.
3. **Power mismatch** computation: `ΔP_i = P_i,specified − P_i,calculated`, similarly for Q at PQ buses only. Use positive loads and positive generations in the input data, and compute net specified injection as `P_spec = p_gen - p_load` and `Q_spec = q_gen - q_load` where a fixed-Q injection is required.
4. **Jacobian** assembled analytically from the four submatrices of calculated power injections: `∂P_calc/∂θ`, `∂P_calc/∂V`, `∂Q_calc/∂θ`, `∂Q_calc/∂V`. Do **not** use numerical differentiation. Add concise comments near the implementation that name the formula and textbook reference; do not paste long derivations into the code.
5. **Newton-Raphson iteration**: with the mismatch convention above and `J` defined as derivatives of calculated injections, solve `J Δx = Δf`, then update `x = x + Δx`. If you instead define a residual as `calculated - specified`, document that convention and solve the equivalent signed system consistently. Convergence on max mismatch < tolerance (default `1e-8` p.u.). Maximum iterations parameter (default 20). Raise a clear exception on non-convergence — do not return silently.
6. **Post-solution**: compute line flows (P, Q at both ends), line losses, total system losses, slack bus injection. Provide a focused post-solution Kirchhoff balance helper or assertion with a clear tolerance.

### Data layer

A minimal case representation:

```python
@dataclass
class Bus:
    id: int
    type: str  # "slack" | "pv" | "pq"
    p_load: float  # positive demand, p.u.
    q_load: float  # positive demand, p.u.
    p_gen: float   # positive generation, p.u.; slack value ignored until solved
    q_gen: float   # positive fixed-Q generation component, p.u.; PV/slack Q is solved
    v_magnitude: float  # specified for PV/slack
    v_angle: float      # specified for slack only (usually 0)
    g_shunt: float = 0.0
    b_shunt: float = 0.0

@dataclass
class Branch:
    from_bus: int
    to_bus: int
    r: float
    x: float
    b: float           # total line charging
    tap_ratio: float = 1.0
    phase_shift: float = 0.0  # radians internally; MATPOWER degrees must be converted
    status: int = 1     # v0 expects 1; raise on out-of-service branches

@dataclass
class Case:
    base_mva: float
    buses: list[Bus]
    branches: list[Branch]
```

All internal solver quantities should be in per unit except voltage angles and branch phase shifts, which may be stored in radians internally. JSON reference fixtures should report voltage angles in degrees to match MATPOWER output. When transcribing MATPOWER data, convert bus loads/generators/shunts from MW/MVAr to p.u. on `baseMVA`; branch `r`, `x`, and `b` are already p.u. on the system base; branch phase shifts are in degrees in MATPOWER and must be converted to radians internally.

Slack bus active and reactive generation and PV bus reactive generation are solved outputs, not fixed mismatch inputs. PQ buses use fixed net active and reactive injections.

For v0, all transcribed branch data is expected to be in service. If a branch has `status != 1`, raise a clear validation error rather than implementing out-of-service branch handling.

### Cases to support

- **IEEE 9-bus** (primary target — must work end-to-end)
- **IEEE 14-bus** (secondary — must also pass)
- **IEEE 30-bus** (third — must also pass)

The same solver must handle all three without case-specific code paths. If 9-bus passes but 14-bus fails, the solver is wrong, not the case.

### Out of scope for v0 — do not build

- Optimization / OPF
- Contingency analysis (that's v1)
- DC power flow (that's v1)
- Reactive limits / PV-to-PQ conversion (note as a known limitation)
- Sparse matrices (cases are too small to need them)
- Plotting, visualization, GUI
- Parsing MATPOWER `.m` files programmatically — transcribe the three required cases to JSON or Python literals
- Any case beyond the three IEEE cases above

## Suggested test progression (red/green order)

This is a sketch, not a script. Follow the spirit (smallest meaningful test first), adapt as you learn what's tricky.

1. **Y-bus on a 2-bus toy system** (one line, no shunts, no taps). Hand-compute the 2x2 Y matrix, assert equality.
2. **Y-bus with line charging susceptance**. Hand-compute, assert.
3. **Y-bus with off-nominal tap ratio**. Use the standard π-equivalent transformer model. Hand-compute, assert.
4. **Y-bus with bus shunts**. Assert added to diagonal.
5. **Optional Y-bus on IEEE 9-bus**. If the hand-computed toy tests are not enough to diagnose Y-bus issues, compare to MATPOWER's Y-bus dumped once as a fixture.
6. **Power injection calculation** at a bus given V, θ, Y. Hand-compute on 2-bus, assert.
7. **Single Newton-Raphson step on a 2-bus PQ-slack system** with hand-computed Jacobian.
8. **Full solve on 2-bus system** — converges, gives correct answer.
9. **Full solve on IEEE 9-bus** — voltage magnitudes and angles match MATPOWER reference within tolerance.
10. **Line flows on IEEE 9-bus** match MATPOWER reference within tolerance.
11. **Full solve on IEEE 14-bus** — passes.
12. **Full solve on IEEE 30-bus** — passes.
13. **Invalid topology test**: build a disconnected case or a branch that references a nonexistent bus and assert validation raises a clear error before Newton-Raphson starts.
14. **Non-convergence test**: force non-convergence with a valid case and an unrealistically low maximum iteration count, then assert the solver raises a clear error rather than returning garbage.
15. **Slack bus power balance**: total generation minus total load minus losses equals zero to machine precision.

Each test should have a one-line docstring explaining what physical or numerical property it pins down.

## Repository layout

```
powerflow/
├── README.md            # how to run tests, what's implemented, known limitations
├── pyproject.toml       # numpy, pytest only
├── src/
│   └── powerflow/
│       ├── __init__.py
│       ├── case.py      # Bus, Branch, Case dataclasses
│       ├── ybus.py      # Y-bus assembly
│       ├── solver.py    # Newton-Raphson, Jacobian, mismatch
│       └── flows.py     # post-solution line flows and losses
├── tests/
│   ├── test_ybus.py
│   ├── test_solver.py
│   ├── test_flows.py
│   └── test_ieee_cases.py
└── data/
    ├── README.md        # fixture provenance and conversion notes
    ├── case9.json       # transcribed from MATPOWER case9.m
    ├── case9_solution.json   # reference voltages, angles, flows
    ├── case14.json
    ├── case14_solution.json
    ├── case30.json
    └── case30_solution.json
```

## Working style — what I want from you

- **Work in small steps and show your work.** After each red/green cycle, briefly state what you tested, what you wrote, and what's next. Don't dump 500 lines of code at once.
- **When you implement a Jacobian expression, add a concise formula/reference comment** (e.g. Bergen & Vittal, Glover, or Grainger & Stevenson). I want to be able to read the code and recognize the equations without wading through textbook prose.
- **If a test fails in a way you don't immediately understand, stop and diagnose**, don't try random fixes. Print intermediate values, write a smaller test, reason about the physics. This is the most important rule.
- **Be honest about what's not working.** If 9-bus passes but 14-bus is off by `2e-3` on one voltage angle, say so explicitly. Don't quietly loosen the tolerance.
- **No silent fallbacks.** If Newton-Raphson doesn't converge, raise. If the case has no slack bus, raise. If a branch references a nonexistent bus, raise. Fail loudly with informative messages.
- **Don't add features I didn't ask for.** No CLI, no logging framework, no config files, no plotting. The test suite is the interface.

## Definition of done

- All tests pass.
- IEEE 9-bus, 14-bus, and 30-bus solutions match MATPOWER reference within the tolerances stated above.
- README documents how to run the tests, what the solver does, and what its known limitations are (no Q limits, no DC PF, etc.).
- Total dependency list is exactly: numpy, pytest.
- Code is readable enough that I can sit down and trace the Newton-Raphson update by eye.

When you reach this state, summarize: what passes, what the residual errors are on each case (max voltage error, max angle error, max flow error), and what surprised you during implementation. That summary is more valuable to me than a clean final commit message.
