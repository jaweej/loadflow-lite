import math

import numpy as np

from powerflow import Branch, Bus, Case, build_ybus


def two_bus_case(branch: Branch, bus_shunt: complex = 0j) -> Case:
    return Case(
        base_mva=100.0,
        buses=[
            Bus(1, "slack", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
            Bus(2, "pq", 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, bus_shunt.real, bus_shunt.imag),
        ],
        branches=[branch],
    )


def test_ybus_single_line_matches_hand_computed_admittance():
    """A simple 2-bus line stamps +y on diagonals and -y off diagonal."""
    branch = Branch(1, 2, r=0.0, x=0.2, b=0.0)

    ybus = build_ybus(two_bus_case(branch))

    expected = np.array([[-5j, 5j], [5j, -5j]])
    np.testing.assert_allclose(ybus, expected)


def test_ybus_line_charging_adds_half_to_each_diagonal():
    """Total line charging susceptance is split equally across both ends."""
    branch = Branch(1, 2, r=0.0, x=0.2, b=0.04)

    ybus = build_ybus(two_bus_case(branch))

    expected = np.array([[-4.98j, 5j], [5j, -4.98j]])
    np.testing.assert_allclose(ybus, expected)


def test_ybus_off_nominal_tap_uses_pi_transformer_model():
    """Off-nominal taps scale the from-side diagonal and mutual terms."""
    branch = Branch(1, 2, r=0.0, x=0.2, b=0.0, tap_ratio=2.0)

    ybus = build_ybus(two_bus_case(branch))

    expected = np.array([[-1.25j, 2.5j], [2.5j, -5j]])
    np.testing.assert_allclose(ybus, expected)


def test_ybus_phase_shift_creates_asymmetric_mutual_terms():
    """Phase shifters rotate the mutual admittances in opposite directions."""
    branch = Branch(1, 2, r=0.0, x=0.2, b=0.0, phase_shift=math.pi / 2)

    ybus = build_ybus(two_bus_case(branch))

    expected = np.array([[-5j, -5 + 0j], [5 + 0j, -5j]])
    np.testing.assert_allclose(ybus, expected, atol=1e-12)


def test_ybus_bus_shunt_adds_to_bus_diagonal():
    """Bus shunts are direct diagonal admittances."""
    branch = Branch(1, 2, r=0.0, x=0.2, b=0.0)

    ybus = build_ybus(two_bus_case(branch, bus_shunt=0.1 + 0.2j))

    expected = np.array([[-5j, 5j], [5j, 0.1 - 4.8j]])
    np.testing.assert_allclose(ybus, expected)
