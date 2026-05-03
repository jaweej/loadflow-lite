from __future__ import annotations

import cmath
from dataclasses import dataclass

import numpy as np

from powerflow.case import Branch, Case, bus_index


@dataclass(frozen=True)
class BranchFlow:
    from_bus: int
    to_bus: int
    p_from: float
    q_from: float
    p_to: float
    q_to: float
    p_loss: float
    q_loss: float


def _branch_admittance_terms(branch: Branch) -> tuple[complex, complex, complex, complex]:
    y_series = 1 / complex(branch.r, branch.x)
    y_charge = 1j * branch.b / 2
    tap = branch.tap_ratio * cmath.exp(1j * branch.phase_shift)

    y_ff = (y_series + y_charge) / (tap * tap.conjugate())
    y_ft = -y_series / tap.conjugate()
    y_tf = -y_series / tap
    y_tt = y_series + y_charge
    return y_ff, y_ft, y_tf, y_tt


def complex_voltages(v_magnitude: np.ndarray, v_angle: np.ndarray) -> np.ndarray:
    return v_magnitude * np.exp(1j * v_angle)


def compute_branch_flows(
    case: Case,
    v_magnitude: np.ndarray,
    v_angle: np.ndarray,
) -> list[BranchFlow]:
    index = bus_index(case)
    voltage = complex_voltages(v_magnitude, v_angle)
    flows: list[BranchFlow] = []

    for branch in case.branches:
        from_idx = index[branch.from_bus]
        to_idx = index[branch.to_bus]
        y_ff, y_ft, y_tf, y_tt = _branch_admittance_terms(branch)
        v_from = voltage[from_idx]
        v_to = voltage[to_idx]

        i_from = y_ff * v_from + y_ft * v_to
        i_to = y_tf * v_from + y_tt * v_to
        s_from = v_from * i_from.conjugate()
        s_to = v_to * i_to.conjugate()
        s_loss = s_from + s_to

        flows.append(
            BranchFlow(
                from_bus=branch.from_bus,
                to_bus=branch.to_bus,
                p_from=float(s_from.real),
                q_from=float(s_from.imag),
                p_to=float(s_to.real),
                q_to=float(s_to.imag),
                p_loss=float(s_loss.real),
                q_loss=float(s_loss.imag),
            )
        )

    return flows
