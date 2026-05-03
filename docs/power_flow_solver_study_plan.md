# Power Flow Solver Study Plan

This is a guided plan for understanding how this repository actually solves the
AC power flow problem. Treat it as a lab, not a checklist: read a small amount
of code, predict what it should do, run a focused test, then explain the result
back in your own words.

The shortest path through the solver is:

1. Build the network admittance matrix, `Ybus`.
2. Convert a voltage guess into calculated bus injections.
3. Compare calculated injections with specified injections.
4. Assemble the Newton-Raphson Jacobian.
5. Solve a linear correction system.
6. Update voltage angles and magnitudes.
7. Repeat until mismatch is below tolerance.
8. Compute branch flows from the solved voltages.

## Learning Outcomes

By the end, you should be able to:

- Explain which variables are solved for at slack, PV, and PQ buses.
- Trace how a `Case` becomes a `Ybus` matrix.
- Derive `S = V * conj(Ybus @ V)` from voltage and current.
- Build the mismatch vector in the same order as the code.
- Map every block of the Jacobian to its rows, columns, and bus types.
- Hand-compute one Newton step for a two-bus slack/PQ system.
- Explain how solved bus voltages become branch powers and losses.
- Identify which files are core numerical code and which are wrappers.

## How to Use This Plan

Make two passes.

Pass 1 is top-down. Start with `solve_power_flow` so you know the whole control
flow before studying formulas.

Pass 2 is bottom-up. Study `build_ybus`, `power_injections`, `_mismatch`, and
`_jacobian` in detail, then return to `solve_power_flow`.

For each session:

1. Read the listed functions.
2. Answer the checkpoint questions without looking ahead.
3. Run the focused test command.
4. Write down one sentence explaining what the code is doing mathematically.

The commands below assume the project virtualenv from the README:

```bash
python3 -m venv .venv
./.venv/bin/pip install numpy pytest
```

## Function Map

Use this as the map from concepts to code:

| Concept | Main code | Why it matters |
| --- | --- | --- |
| Case validation | [`validate_case`](../src/powerflow/case.py#L63) | Rejects invalid topology before Newton starts. |
| Bus indexing | [`bus_index`](../src/powerflow/case.py#L58) | Converts external bus IDs to array indices. |
| Network model | [`build_ybus`](../src/powerflow/ybus.py#L10) | Builds the admittance matrix used in every injection calculation. |
| Complex voltages | [`complex_voltages`](../src/powerflow/flows.py#L35) | Converts magnitudes and angles into complex phasors. |
| Calculated injections | [`power_injections`](../src/powerflow/solver.py#L36) | Computes `P_calc` and `Q_calc` from the current voltage guess. |
| Specified injections | [`specified_injections`](../src/powerflow/solver.py#L30) | Applies the repo sign convention: generation minus load. |
| Bus type handling | [`_bus_type_indices`](../src/powerflow/solver.py#L46) | Determines which equations and unknowns exist. |
| Initial guess | [`_initial_voltage`](../src/powerflow/solver.py#L53) | Creates the first Newton state. |
| Mismatch vector | [`_mismatch`](../src/powerflow/solver.py#L62) | Defines the residual that Newton drives to zero. |
| Jacobian | [`_jacobian`](../src/powerflow/solver.py#L77) | Linearizes the AC power-flow equations. |
| Newton loop | [`solve_power_flow`](../src/powerflow/solver.py#L139) | Orchestrates the full nonlinear solve. |
| Result assembly | [`_build_result`](../src/powerflow/solver.py#L195) | Converts the converged state into useful outputs. |
| Branch flows | [`compute_branch_flows`](../src/powerflow/flows.py#L39) | Computes line powers and losses after convergence. |

## Glossary

- `Ybus`: the bus admittance matrix. It maps complex bus voltages to complex
  injected currents: `I = Ybus @ V`.
- `V`: complex bus voltage phasor. In code it is built from `v_magnitude` and
  `v_angle`.
- `theta`: voltage angle in radians.
- `P`, `Q`: real and reactive power injection. Positive means net injection
  into the network; negative means net load.
- `S`: complex power, `S = P + jQ`.
- `G`, `B`: real and imaginary parts of `Ybus`, so `Ybus = G + jB`.
- `slack bus`: fixed voltage magnitude and fixed angle. Its real and reactive
  generation are solved outputs.
- `PV bus`: fixed real-power injection and voltage magnitude. Its angle is
  solved, and its reactive generation is a solved output.
- `PQ bus`: fixed real and reactive injection. Its voltage angle and magnitude
  are solved.
- `mismatch`: specified injection minus calculated injection.
- `Jacobian`: the matrix of partial derivatives used to turn a nonlinear
  mismatch into a linear correction step.
- `per unit`: normalized power-system units. The repo stores powers in p.u.;
  conversion to MW/MVAr uses `base_mva`.

## Session 1. Get the Whole Solver in Your Head

Read:

- [`solve_power_flow`](../src/powerflow/solver.py#L139)
- [`_build_result`](../src/powerflow/solver.py#L195)

Focus on the loop shape:

```text
build Ybus
choose unknowns
initialize voltage state
repeat:
    compute mismatch
    stop if mismatch is small
    build Jacobian
    solve J * step = mismatch
    update angles and magnitudes
```

Checkpoint questions:

- Where is `Ybus` built?
- Where does the code stop on convergence?
- What arrays are updated during each Newton step?
- Why does non-convergence raise instead of returning a partial result?

Run:

```bash
./.venv/bin/python -m pytest tests/test_solver.py::test_two_bus_power_flow_converges_and_balances_power -q
```

Done criteria:

- You can describe `solve_power_flow` without mentioning any wrapper code.
- You can point to the exact lines that call `_mismatch`, `_jacobian`, and
  `np.linalg.solve`.

## Session 2. Understand Bus Types and the State Vector

Read:

- [`_bus_type_indices`](../src/powerflow/solver.py#L46)
- [`_initial_voltage`](../src/powerflow/solver.py#L53)
- [`validate_case`](../src/powerflow/case.py#L63)

The Newton state is not all bus voltages. It is:

- Voltage angles for PV and PQ buses.
- Voltage magnitudes for PQ buses only.

The slack bus angle and magnitude stay fixed. PV bus voltage magnitudes also
stay fixed, while their reactive generation is solved after convergence.

Checkpoint questions:

- What would go wrong if the slack angle were included as an unknown?
- Why does a PV bus solve for angle but not voltage magnitude?
- Why does a PQ bus solve for both angle and magnitude?
- For a system with 1 slack, 2 PV buses, and 6 PQ buses, how many Newton
  unknowns are there?

Run:

```bash
./.venv/bin/python -m pytest tests/test_solver.py::test_pv_bus_keeps_voltage_magnitude_fixed -q
```

Done criteria:

- You can construct the state vector for any mix of slack, PV, and PQ buses.
- You can explain why PV-bus `q_gen` is not a fixed input to the mismatch.

## Session 3. Build `Ybus`

Read:

- [`build_ybus`](../src/powerflow/ybus.py#L10)
- [`_branch_admittance_terms`](../src/powerflow/flows.py#L23)

`Ybus` is the electrical network model. Each branch contributes self-admittance
terms to the diagonal and mutual admittance terms to the off-diagonal entries.
Line charging, transformer tap ratios, phase shifts, and bus shunts all enter
here.

Checkpoint questions:

- Why does a simple series line add `+y` to both diagonals and `-y` to both
  off-diagonals?
- Why is line charging split between the two ends?
- What changes when `tap_ratio != 1.0`?
- Why can a phase shifter make `Ybus[from, to]` differ from `Ybus[to, from]`?

Run:

```bash
./.venv/bin/python -m pytest tests/test_ybus.py -q
```

Done criteria:

- You can manually stamp a two-bus branch into a 2x2 `Ybus`.
- You can explain why `build_ybus` and `_branch_admittance_terms` must use the
  same branch model.

## Session 4. Convert Voltages Into Power Injections

Read:

- [`complex_voltages`](../src/powerflow/flows.py#L35)
- [`power_injections`](../src/powerflow/solver.py#L36)

The key formula is:

```text
I = Ybus @ V
S = V * conj(I)
P_calc = real(S)
Q_calc = imag(S)
```

This is where the current voltage guess becomes calculated real and reactive
power injection at each bus.

Checkpoint questions:

- What are the shapes of `V`, `Ybus @ V`, and `S`?
- Why is the current conjugated in the complex-power formula?
- What does a negative `P_calc` mean?
- What does a negative `Q_calc` mean?

Run:

```bash
./.venv/bin/python -m pytest tests/test_solver.py::test_power_injection_matches_hand_computed_two_bus_value -q
```

Done criteria:

- You can compute `S = V * conj(Ybus @ V)` for a two-bus example.
- You can explain why this function knows nothing about slack, PV, or PQ bus
  types.

## Session 5. Build the Mismatch Vector

Read:

- [`specified_injections`](../src/powerflow/solver.py#L30)
- [`_mismatch`](../src/powerflow/solver.py#L62)

The sign convention is:

```text
P_spec = p_gen - p_load
Q_spec = q_gen - q_load
mismatch = specified - calculated
```

The mismatch vector is ordered as:

1. Real-power mismatches for PV and PQ buses.
2. Reactive-power mismatches for PQ buses.

Checkpoint questions:

- Why is there no real-power mismatch equation for the slack bus?
- Why is there no reactive-power mismatch equation for PV buses?
- How does the mismatch ordering match the Newton update vector?
- What would change if mismatch were defined as calculated minus specified?

Run:

```bash
./.venv/bin/python -m pytest tests/test_solver.py::test_two_bus_power_flow_converges_and_balances_power -q
```

Done criteria:

- You can write the mismatch vector shape for a given set of bus types.
- You can explain the sign of the update in `solve_power_flow`.

## Session 6. Spend the Most Time on the Jacobian

Read:

- [`_jacobian`](../src/powerflow/solver.py#L77)

This is the densest numerical function in the repo. It assembles the analytic
polar AC power-flow Jacobian:

```text
[ dP_calc/dtheta   dP_calc/dV ]
[ dQ_calc/dtheta   dQ_calc/dV ]
```

Rows match equations:

- `P` rows for PV and PQ buses.
- `Q` rows for PQ buses.

Columns match unknowns:

- Angle columns for PV and PQ buses.
- Voltage-magnitude columns for PQ buses.

The implementation uses derivatives of calculated injections. Since mismatch is
specified minus calculated, the Newton correction is applied consistently by
solving:

```text
J * step = mismatch
x = x + step
```

Checkpoint questions:

- Which nested loop fills `dP/dtheta`?
- Which nested loop fills `dP/dV`?
- Which nested loop fills `dQ/dtheta`?
- Which nested loop fills `dQ/dV`?
- Why do diagonal and off-diagonal formulas differ?
- How do `g = ybus.real` and `b = ybus.imag` enter the formulas?

Run:

```bash
./.venv/bin/python -m pytest tests/test_solver.py -q
```

Done criteria:

- You can label each quadrant of the Jacobian in the code.
- For a 1 slack, 1 PV, 2 PQ system, you can state the Jacobian dimensions and
  row/column ordering.

## Session 7. Work One Newton Step by Hand

Use the two-bus case from
[`test_two_bus_power_flow_converges_and_balances_power`](../tests/test_solver.py#L38):

```text
bus 1: slack, V = 1.0, theta = 0
bus 2: PQ load, P_load = 0.4, Q_load = 0.2
branch: r = 0.02, x = 0.04, b = 0.0
flat start: V1 = 1.0 angle 0, V2 = 1.0 angle 0
```

First compute the series admittance:

```text
y = 1 / (0.02 + j0.04) = 10 - j20
```

So the flat-start `Ybus` is:

```text
[  10 - j20    -10 + j20 ]
[ -10 + j20     10 - j20 ]
```

At flat voltage, `Ybus @ V = 0`, so:

```text
P_calc2 = 0
Q_calc2 = 0
P_spec2 = 0 - 0.4 = -0.4
Q_spec2 = 0 - 0.2 = -0.2
mismatch = [-0.4, -0.2]
```

For bus 2 at the flat start:

```text
G22 = 10
B22 = -20
V2 = 1
P_calc2 = 0
Q_calc2 = 0
```

The 2x2 Jacobian is:

```text
dP/dtheta = -Q_calc2 - B22 * V2^2 = 20
dP/dV     =  P_calc2 / V2 + G22 * V2 = 10
dQ/dtheta =  P_calc2 - G22 * V2^2 = -10
dQ/dV     =  Q_calc2 / V2 - B22 * V2 = 20

J = [  20   10 ]
    [ -10   20 ]
```

Solve:

```text
J * step = [-0.4, -0.2]
step = [-0.012, -0.016]
```

So the first update is approximately:

```text
theta2 = 0.0 - 0.012 = -0.012 radians
V2     = 1.0 - 0.016 = 0.984 p.u.
```

Checkpoint questions:

- Why is the first angle update negative?
- Why does the first voltage-magnitude update reduce `V2`?
- Which two entries of the state vector exist in this two-bus case?
- Which entries would disappear if bus 2 were PV instead of PQ?

Done criteria:

- You can reproduce the first Newton step without reading the code.
- You can point from each hand-computed quantity to the line that computes it.

## Session 8. Interpret the Solved Result

Read:

- [`_build_result`](../src/powerflow/solver.py#L195)
- [`compute_branch_flows`](../src/powerflow/flows.py#L39)
- [`bus_power_balance_residuals`](../src/powerflow/solver.py#L221)

After convergence, the code computes solved generation and branch flows. This is
post-solution interpretation, not part of Newton convergence.

Checkpoint questions:

- Why is slack-bus generation computed after the solve?
- Why is PV-bus reactive generation computed after the solve?
- How are branch from-end and to-end currents computed?
- Why are branch losses the sum of the two terminal complex powers?

Run:

```bash
./.venv/bin/python -m pytest tests/test_flows.py -q
```

Done criteria:

- You can explain how solved bus voltages become branch `P/Q` flows.
- You can distinguish mismatch convergence from post-solve reporting.

## Session 9. Validate the Complete Implementation

Run the focused tests first:

```bash
./.venv/bin/python -m pytest tests/test_ybus.py tests/test_solver.py tests/test_flows.py -q
```

Then run the broader suite:

```bash
./.venv/bin/python -m pytest -q
```

The small tests are best for understanding individual equations. The IEEE tests
are best for confirming that the complete implementation matches static
MATPOWER fixtures when those fixtures are present.

Done criteria:

- You know which test protects each concept.
- You can explain why a solver can pass a two-bus test but still need IEEE case
  validation.

## Common Confusions

- Slack-bus `p_gen` and `q_gen` in the input are not fixed mismatch equations;
  the solved slack injection is computed from the final network state.
- PV-bus `q_gen` is solved, not fixed. This repo does not implement reactive
  power limits or PV-to-PQ conversion.
- PQ-bus voltage magnitude is unknown, even if the input provides an initial
  value.
- The mismatch excludes slack equations because the slack bus absorbs the
  active-power residual and fixes the angle reference.
- The mismatch excludes PV reactive equations because PV voltage magnitude is
  fixed and reactive output is allowed to move.
- `power_injections` computes injections for every bus, but `_mismatch` selects
  only the equations that belong in the Newton solve.
- `build_ybus` builds a global network model; `compute_branch_flows` uses the
  same branch model locally for each line after convergence.
- The code stores angles in radians. Some fixtures and reports may display
  degrees.
- The code solves `J * step = mismatch` because the implementation uses the
  Jacobian of calculated injections together with a specified-minus-calculated
  mismatch convention.

## Optional Theory Backup

If you want more context while reading the code, use:

- [`docs/ieee9_power_flow_lecture_note.tex`](ieee9_power_flow_lecture_note.tex),
  especially the Newton-Raphson appendix.
- [`docs/powerflow_v0_prompt.md`](powerflow_v0_prompt.md), which describes the
  original implementation goals and constraints.

Use these as references only after you have tried to trace the code path. The
fastest learning loop is still: code, tiny example, test, explanation.

## Files to Delay Until Later

These files are useful, but they are not the best starting point for
understanding the numerical solve:

- [`src/powerflow/io.py`](../src/powerflow/io.py): case loading.
- [`src/powerflow/case.py`](../src/powerflow/case.py): data structures and
  validation.
- [`src/powerflow/contingency.py`](../src/powerflow/contingency.py): repeated
  solves for outage analysis.
- [`scripts/run_case9_n1.py`](../scripts/run_case9_n1.py): command-line report
  wrapper.

Read these after the Newton-Raphson path is clear.

## Final Self-Test

You are done with the core study plan when you can answer these without looking
at the code:

- What is the Newton state vector for a network with 1 slack, 2 PV, and 6 PQ
  buses?
- Why is the slack bus excluded from both `P` and `Q` mismatch equations?
- Why is a PV bus included in `P` mismatch but excluded from `Q` mismatch?
- What does `S = V * conj(Ybus @ V)` compute?
- How is `P_spec` different from `P_calc`?
- What are the four Jacobian blocks?
- Why does the code update only `v_angle[angle_buses]` and
  `v_magnitude[pq_buses]`?
- How do branch flows differ from bus injections?
- Which function would you inspect first if voltages fail to converge?
- Which function would you inspect first if voltages converge but branch losses
  look wrong?
