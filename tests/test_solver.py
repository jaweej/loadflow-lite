import numpy as np
import pytest

from powerflow import Branch, Bus, Case
from powerflow.solver import (
    PowerFlowDidNotConverge,
    bus_power_balance_residuals,
    power_injections,
    solve_power_flow,
)
from powerflow.ybus import build_ybus


def test_power_injection_matches_hand_computed_two_bus_value():
    """Power injection follows S = V * conj(YV) for a known 2-bus state."""
    case = Case(
        base_mva=100.0,
        buses=[
            Bus(1, "slack", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            Bus(2, "pq", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        ],
        branches=[Branch(1, 2, r=0.0, x=0.2, b=0.0)],
    )
    ybus = build_ybus(case)

    p_calc, q_calc = power_injections(
        ybus,
        np.array([1.0, 0.98]),
        np.array([0.0, -0.1]),
    )

    theta = 0.0 - -0.1
    expected_p1 = 1.0 * 0.98 * (5.0 * np.sin(theta))
    expected_q1 = 1.0 * (5.0 * 1.0 - 0.98 * 5.0 * np.cos(theta))
    np.testing.assert_allclose([p_calc[0], q_calc[0]], [expected_p1, expected_q1])


def test_two_bus_power_flow_converges_and_balances_power():
    """A 2-bus slack/PQ case converges and satisfies network power balance."""
    case = Case(
        base_mva=100.0,
        buses=[
            Bus(1, "slack", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            Bus(2, "pq", 0.4, 0.2, 0.0, 0.0, 1.0, 0.0),
        ],
        branches=[Branch(1, 2, r=0.02, x=0.04, b=0.0)],
    )

    result = solve_power_flow(case, tolerance=1e-10)

    assert result.converged
    assert result.iterations < 10
    np.testing.assert_allclose(result.p_injection[1], -0.4, atol=1e-10)
    np.testing.assert_allclose(result.q_injection[1], -0.2, atol=1e-10)
    p_residual, q_residual = bus_power_balance_residuals(result)
    assert abs(p_residual) < 1e-10
    assert abs(q_residual) < 1e-10


def test_pv_bus_keeps_voltage_magnitude_fixed():
    """PV buses solve angle only while preserving their specified voltage."""
    case = Case(
        base_mva=100.0,
        buses=[
            Bus(1, "slack", 0.0, 0.0, 0.0, 0.0, 1.04, 0.0),
            Bus(2, "pv", 0.1, 0.0, 0.5, 0.0, 1.01, 0.0),
            Bus(3, "pq", 0.6, 0.25, 0.0, 0.0, 1.0, 0.0),
        ],
        branches=[
            Branch(1, 2, r=0.02, x=0.06, b=0.03),
            Branch(1, 3, r=0.08, x=0.24, b=0.025),
            Branch(2, 3, r=0.06, x=0.18, b=0.02),
        ],
    )

    result = solve_power_flow(case, tolerance=1e-10)

    assert result.converged
    np.testing.assert_allclose(result.v_magnitude[1], 1.01)
    np.testing.assert_allclose(result.p_injection[1], 0.4, atol=1e-10)
    np.testing.assert_allclose(result.p_injection[2], -0.6, atol=1e-10)
    np.testing.assert_allclose(result.q_injection[2], -0.25, atol=1e-10)


def test_non_convergence_raises_clear_error():
    """A valid case with max_iterations too low raises instead of returning."""
    case = Case(
        base_mva=100.0,
        buses=[
            Bus(1, "slack", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            Bus(2, "pq", 0.4, 0.2, 0.0, 0.0, 1.0, 0.0),
        ],
        branches=[Branch(1, 2, r=0.02, x=0.04, b=0.0)],
    )

    with pytest.raises(PowerFlowDidNotConverge, match="did not converge"):
        solve_power_flow(case, max_iterations=1)


def test_invalid_branch_reference_raises_before_solving():
    """Branch endpoint validation catches nonexistent buses before Newton."""
    case = Case(
        base_mva=100.0,
        buses=[Bus(1, "slack", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)],
        branches=[Branch(1, 2, r=0.02, x=0.04, b=0.0)],
    )

    with pytest.raises(ValueError, match="nonexistent to_bus"):
        solve_power_flow(case)


def test_disconnected_network_raises_before_solving():
    """Disconnected topology is rejected before Newton iteration starts."""
    case = Case(
        base_mva=100.0,
        buses=[
            Bus(1, "slack", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            Bus(2, "pq", 0.1, 0.0, 0.0, 0.0, 1.0, 0.0),
            Bus(3, "pq", 0.1, 0.0, 0.0, 0.0, 1.0, 0.0),
        ],
        branches=[Branch(1, 2, r=0.02, x=0.04, b=0.0)],
    )

    with pytest.raises(ValueError, match="disconnected"):
        solve_power_flow(case)


def test_out_of_service_branch_raises_before_solving():
    """v0 rejects disabled branches instead of silently handling them."""
    case = Case(
        base_mva=100.0,
        buses=[
            Bus(1, "slack", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            Bus(2, "pq", 0.1, 0.0, 0.0, 0.0, 1.0, 0.0),
        ],
        branches=[Branch(1, 2, r=0.02, x=0.04, b=0.0, status=0)],
    )

    with pytest.raises(ValueError, match="in-service"):
        solve_power_flow(case)
