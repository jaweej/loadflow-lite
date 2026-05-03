# Power Flow Solver Study Plan

This plan is for understanding how this repository actually solves the AC power
flow problem, not just how it loads cases or reports results. The core path is:

1. Build the network admittance matrix.
2. Convert the current voltage guess into calculated power injections.
3. Compare calculated injections with specified injections.
4. Assemble the Newton-Raphson Jacobian.
5. Solve for a correction step.
6. Update voltage angles and magnitudes until the mismatch is small.
7. Compute branch flows from the solved voltages.

## 1. Start With the Main Solve Loop

Read [`src/powerflow/solver.py`](../src/powerflow/solver.py), starting with:

- `solve_power_flow`
- `_mismatch`
- `_jacobian`
- `power_injections`
- `specified_injections`

Focus first on `solve_power_flow`. It is the best high-level map of the solver:

- It validates the case.
- It builds `Ybus`.
- It identifies slack, PV, and PQ buses.
- It initializes voltage magnitudes and angles.
- It repeatedly computes mismatch, assembles the Jacobian, solves a linear
  system, and updates the state.

Checkpoint questions:

- Which buses have voltage angles solved?
- Which buses have voltage magnitudes solved?
- Why is the slack bus excluded from the Newton state?
- Why is reactive-power mismatch only included for PQ buses?

## 2. Understand the State Variables

Study these helper functions:

- `_bus_type_indices`
- `_initial_voltage`

The Newton state is not all bus voltages. It is:

- Voltage angles for PV and PQ buses.
- Voltage magnitudes for PQ buses only.

The slack bus angle and magnitude stay fixed. PV bus voltage magnitudes also
stay fixed, while their reactive generation is solved as an output.

Checkpoint questions:

- What would go wrong if the slack angle were also included as an unknown?
- Why does a PV bus solve for angle but not voltage magnitude?
- Where does the initial guess come from for each bus type?

## 3. Study the Power Injection Formula

Read:

- `power_injections` in [`src/powerflow/solver.py`](../src/powerflow/solver.py)
- `complex_voltages` in [`src/powerflow/flows.py`](../src/powerflow/flows.py)

The key formula is:

```text
S = V * conj(Ybus @ V)
```

This converts the current voltage guess into calculated complex power
injections at every bus.

Checkpoint questions:

- What are the shapes of `V`, `Ybus @ V`, and `S`?
- Why is the current conjugated before multiplying by voltage?
- What do positive and negative `P` and `Q` injections mean in this codebase?

Useful test:

- `test_power_injection_matches_hand_computed_two_bus_value` in
  [`tests/test_solver.py`](../tests/test_solver.py)

## 4. Study the Mismatch Definition

Read:

- `specified_injections`
- `_mismatch`

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
- How does the ordering of the mismatch vector match the ordering of the
  Newton update vector?

Useful tests:

- `test_two_bus_power_flow_converges_and_balances_power`
- `test_pv_bus_keeps_voltage_magnitude_fixed`

## 5. Spend the Most Time on the Jacobian

Read:

- `_jacobian` in [`src/powerflow/solver.py`](../src/powerflow/solver.py)

This is the densest and most important numerical function in the repo. It
assembles the analytic polar AC power-flow Jacobian:

```text
[ dP/dtheta   dP/dV ]
[ dQ/dtheta   dQ/dV ]
```

The rows match the mismatch equations:

- `P` rows for PV and PQ buses.
- `Q` rows for PQ buses.

The columns match the unknowns:

- Angle columns for PV and PQ buses.
- Voltage magnitude columns for PQ buses.

Checkpoint questions:

- Which block is being filled in each nested loop?
- Why do the diagonal and off-diagonal formulas differ?
- How do `g = ybus.real` and `b = ybus.imag` enter the formulas?
- Why does the code solve `J * step = mismatch` and then add `step`?

Suggested exercise:

- Trace one Newton iteration by hand for the two-bus case in
  `test_two_bus_power_flow_converges_and_balances_power`.

## 6. Understand `Ybus` Assembly

Read [`src/powerflow/ybus.py`](../src/powerflow/ybus.py), especially:

- `build_ybus`

This function stamps every branch into the bus admittance matrix. It includes:

- Series impedance.
- Line charging susceptance.
- Off-nominal transformer tap ratios.
- Phase shifts.
- Bus shunts.

Checkpoint questions:

- Why do simple lines add positive admittance to diagonals and negative
  admittance to off-diagonals?
- Why is line charging split in half between the two branch ends?
- How do tap ratios and phase shifts make the branch model asymmetric?

Useful tests:

- [`tests/test_ybus.py`](../tests/test_ybus.py)

## 7. Study Branch Flows After the Solve

Read [`src/powerflow/flows.py`](../src/powerflow/flows.py), especially:

- `_branch_admittance_terms`
- `compute_branch_flows`

This is not part of Newton-Raphson convergence, but it explains how solved bus
voltages become branch real and reactive power flows.

Checkpoint questions:

- How are from-end and to-end branch currents computed?
- Why are branch losses the sum of the two terminal powers?
- How does the branch model here match the `Ybus` stamping model?

Useful tests:

- [`tests/test_flows.py`](../tests/test_flows.py)

## 8. Validate Against Tests and Fixtures

After reading the core functions, run or inspect these tests:

- [`tests/test_solver.py`](../tests/test_solver.py)
- [`tests/test_ybus.py`](../tests/test_ybus.py)
- [`tests/test_flows.py`](../tests/test_flows.py)
- [`tests/test_ieee_cases.py`](../tests/test_ieee_cases.py)

The small tests are best for understanding individual equations. The IEEE
fixture tests are best for confirming that the complete implementation matches
known MATPOWER results.

## 9. Ignore These Until Later

These files are useful, but not the best starting point for understanding the
actual power-flow solve:

- [`src/powerflow/io.py`](../src/powerflow/io.py): case loading.
- [`src/powerflow/case.py`](../src/powerflow/case.py): data structures and
  validation.
- [`src/powerflow/contingency.py`](../src/powerflow/contingency.py): repeated
  solves for outage analysis.
- [`scripts/run_case9_n1.py`](../scripts/run_case9_n1.py): command-line report
  wrapper.

Read these after the Newton-Raphson path is clear.

## Recommended Reading Order

1. `solve_power_flow`
2. `_bus_type_indices`
3. `_initial_voltage`
4. `specified_injections`
5. `power_injections`
6. `_mismatch`
7. `_jacobian`
8. `build_ybus`
9. `compute_branch_flows`
10. The focused tests in `tests/test_solver.py`, `tests/test_ybus.py`, and
    `tests/test_flows.py`

By the end, you should be able to explain how a case turns into `Ybus`, how a
voltage guess turns into calculated injections, how the mismatch vector is
formed, how the Jacobian maps state updates to mismatch reduction, and how the
final voltage solution becomes branch flows.
