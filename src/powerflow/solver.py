from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from powerflow.case import Case, validate_case
from powerflow.flows import BranchFlow, complex_voltages, compute_branch_flows
from powerflow.ybus import build_ybus


class PowerFlowDidNotConverge(RuntimeError):
    pass


@dataclass(frozen=True)
class PowerFlowResult:
    converged: bool
    iterations: int
    max_mismatch: float
    v_magnitude: np.ndarray
    v_angle: np.ndarray
    p_injection: np.ndarray
    q_injection: np.ndarray
    p_generation: np.ndarray
    q_generation: np.ndarray
    branch_flows: list[BranchFlow]


def specified_injections(case: Case) -> tuple[np.ndarray, np.ndarray]:
    p_spec = np.array([bus.p_gen - bus.p_load for bus in case.buses], dtype=float)
    q_spec = np.array([bus.q_gen - bus.q_load for bus in case.buses], dtype=float)
    return p_spec, q_spec


def power_injections(
    ybus: np.ndarray,
    v_magnitude: np.ndarray,
    v_angle: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    voltage = complex_voltages(v_magnitude, v_angle)
    s_injection = voltage * (ybus @ voltage).conjugate()
    return s_injection.real, s_injection.imag


def _bus_type_indices(case: Case) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    slack = np.array([idx for idx, bus in enumerate(case.buses) if bus.type == "slack"], dtype=int)
    pv = np.array([idx for idx, bus in enumerate(case.buses) if bus.type == "pv"], dtype=int)
    pq = np.array([idx for idx, bus in enumerate(case.buses) if bus.type == "pq"], dtype=int)
    return slack, pv, pq


def _initial_voltage(case: Case) -> tuple[np.ndarray, np.ndarray]:
    v_magnitude = np.array([bus.v_magnitude for bus in case.buses], dtype=float)
    v_angle = np.array([bus.v_angle for bus in case.buses], dtype=float)
    for idx, bus in enumerate(case.buses):
        if bus.type == "pq" and v_magnitude[idx] == 0.0:
            v_magnitude[idx] = 1.0
    return v_magnitude, v_angle


def _mismatch(
    case: Case,
    ybus: np.ndarray,
    v_magnitude: np.ndarray,
    v_angle: np.ndarray,
    angle_buses: np.ndarray,
    pq_buses: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p_calc, q_calc = power_injections(ybus, v_magnitude, v_angle)
    p_spec, q_spec = specified_injections(case)
    delta_p = p_spec[angle_buses] - p_calc[angle_buses]
    delta_q = q_spec[pq_buses] - q_calc[pq_buses]
    return np.concatenate([delta_p, delta_q]), p_calc, q_calc


def _jacobian(
    ybus: np.ndarray,
    v_magnitude: np.ndarray,
    v_angle: np.ndarray,
    p_calc: np.ndarray,
    q_calc: np.ndarray,
    angle_buses: np.ndarray,
    pq_buses: np.ndarray,
) -> np.ndarray:
    g = ybus.real
    b = ybus.imag
    n_angle = len(angle_buses)
    n_pq = len(pq_buses)
    jacobian = np.zeros((n_angle + n_pq, n_angle + n_pq), dtype=float)

    # Standard polar power-flow Jacobian for derivatives of calculated
    # injections P_calc, Q_calc; e.g. Grainger & Stevenson AC load-flow formulas.
    for row_pos, i in enumerate(angle_buses):
        for col_pos, k in enumerate(angle_buses):
            if i == k:
                value = -q_calc[i] - b[i, i] * v_magnitude[i] ** 2
            else:
                theta = v_angle[i] - v_angle[k]
                value = v_magnitude[i] * v_magnitude[k] * (
                    g[i, k] * np.sin(theta) - b[i, k] * np.cos(theta)
                )
            jacobian[row_pos, col_pos] = value

        for col_pos, k in enumerate(pq_buses):
            if i == k:
                value = p_calc[i] / v_magnitude[i] + g[i, i] * v_magnitude[i]
            else:
                theta = v_angle[i] - v_angle[k]
                value = v_magnitude[i] * (
                    g[i, k] * np.cos(theta) + b[i, k] * np.sin(theta)
                )
            jacobian[row_pos, n_angle + col_pos] = value

    for row_pos, i in enumerate(pq_buses):
        for col_pos, k in enumerate(angle_buses):
            if i == k:
                value = p_calc[i] - g[i, i] * v_magnitude[i] ** 2
            else:
                theta = v_angle[i] - v_angle[k]
                value = -v_magnitude[i] * v_magnitude[k] * (
                    g[i, k] * np.cos(theta) + b[i, k] * np.sin(theta)
                )
            jacobian[n_angle + row_pos, col_pos] = value

        for col_pos, k in enumerate(pq_buses):
            if i == k:
                value = q_calc[i] / v_magnitude[i] - b[i, i] * v_magnitude[i]
            else:
                theta = v_angle[i] - v_angle[k]
                value = v_magnitude[i] * (
                    g[i, k] * np.sin(theta) - b[i, k] * np.cos(theta)
                )
            jacobian[n_angle + row_pos, n_angle + col_pos] = value

    return jacobian


def solve_power_flow(
    case: Case,
    tolerance: float = 1e-8,
    max_iterations: int = 20,
) -> PowerFlowResult:
    validate_case(case)
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")

    ybus = build_ybus(case)
    _slack_buses, pv_buses, pq_buses = _bus_type_indices(case)
    angle_buses = np.concatenate([pv_buses, pq_buses])
    v_magnitude, v_angle = _initial_voltage(case)

    mismatch = np.array([], dtype=float)
    p_calc = np.zeros(len(case.buses), dtype=float)
    q_calc = np.zeros(len(case.buses), dtype=float)
    for iteration in range(max_iterations + 1):
        mismatch, p_calc, q_calc = _mismatch(
            case, ybus, v_magnitude, v_angle, angle_buses, pq_buses
        )
        max_mismatch = float(np.max(np.abs(mismatch))) if mismatch.size else 0.0
        if max_mismatch < tolerance:
            return _build_result(
                case,
                iteration,
                max_mismatch,
                v_magnitude,
                v_angle,
                p_calc,
                q_calc,
            )
        if iteration == max_iterations:
            break

        jacobian = _jacobian(
            ybus, v_magnitude, v_angle, p_calc, q_calc, angle_buses, pq_buses
        )
        try:
            step = np.linalg.solve(jacobian, mismatch)
        except np.linalg.LinAlgError as exc:
            raise PowerFlowDidNotConverge("Newton-Raphson Jacobian is singular") from exc

        angle_step = step[: len(angle_buses)]
        voltage_step = step[len(angle_buses) :]
        v_angle[angle_buses] += angle_step
        v_magnitude[pq_buses] += voltage_step

    raise PowerFlowDidNotConverge(
        f"Newton-Raphson did not converge after {max_iterations} iterations; "
        f"max mismatch {max_mismatch:.6g} p.u."
    )


def _build_result(
    case: Case,
    iterations: int,
    max_mismatch: float,
    v_magnitude: np.ndarray,
    v_angle: np.ndarray,
    p_calc: np.ndarray,
    q_calc: np.ndarray,
) -> PowerFlowResult:
    p_generation = p_calc + np.array([bus.p_load for bus in case.buses], dtype=float)
    q_generation = q_calc + np.array([bus.q_load for bus in case.buses], dtype=float)
    branch_flows = compute_branch_flows(case, v_magnitude, v_angle)
    return PowerFlowResult(
        converged=True,
        iterations=iterations,
        max_mismatch=max_mismatch,
        v_magnitude=v_magnitude.copy(),
        v_angle=v_angle.copy(),
        p_injection=p_calc.copy(),
        q_injection=q_calc.copy(),
        p_generation=p_generation,
        q_generation=q_generation,
        branch_flows=branch_flows,
    )


def bus_power_balance_residuals(result: PowerFlowResult) -> tuple[float, float]:
    total_branch_p_loss = sum(flow.p_loss for flow in result.branch_flows)
    total_branch_q_loss = sum(flow.q_loss for flow in result.branch_flows)
    return (
        float(np.sum(result.p_injection) - total_branch_p_loss),
        float(np.sum(result.q_injection) - total_branch_q_loss),
    )
