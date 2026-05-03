from __future__ import annotations

import cmath

import numpy as np

from powerflow.case import Case, bus_index


def build_ybus(case: Case) -> np.ndarray:
    index = bus_index(case)
    ybus = np.zeros((len(case.buses), len(case.buses)), dtype=complex)

    for branch in case.branches:
        from_idx = index[branch.from_bus]
        to_idx = index[branch.to_bus]
        y_series = 1 / complex(branch.r, branch.x)
        y_charge = 1j * branch.b / 2
        tap = branch.tap_ratio * cmath.exp(1j * branch.phase_shift)

        y_ff = (y_series + y_charge) / (tap * tap.conjugate())
        y_ft = -y_series / tap.conjugate()
        y_tf = -y_series / tap
        y_tt = y_series + y_charge

        ybus[from_idx, from_idx] += y_ff
        ybus[from_idx, to_idx] += y_ft
        ybus[to_idx, from_idx] += y_tf
        ybus[to_idx, to_idx] += y_tt

    for idx, bus in enumerate(case.buses):
        ybus[idx, idx] += complex(bus.g_shunt, bus.b_shunt)

    return ybus
