from pathlib import Path

import numpy as np
import pytest

from powerflow.io import load_case, load_json
from powerflow.solver import solve_power_flow


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def fixture_pair(case_name: str) -> tuple[Path, Path]:
    return DATA_DIR / f"{case_name}.json", DATA_DIR / f"{case_name}_solution.json"


def require_fixtures(case_name: str) -> tuple[Path, Path]:
    case_path, solution_path = fixture_pair(case_name)
    if not case_path.exists() or not solution_path.exists():
        pytest.skip(f"MATPOWER fixtures for {case_name} have not been generated")
    return case_path, solution_path


@pytest.mark.parametrize("case_name", ["case9", "case14", "case30"])
def test_ieee_case_voltages_match_matpower_fixture(case_name):
    """IEEE benchmark bus voltages match static MATPOWER runpf fixtures."""
    case_path, solution_path = require_fixtures(case_name)
    case = load_case(case_path)
    solution = load_json(solution_path)

    result = solve_power_flow(case)

    expected_vm = np.array([bus["v_magnitude"] for bus in solution["buses"]])
    expected_va = np.deg2rad([bus["v_angle_degrees"] for bus in solution["buses"]])
    np.testing.assert_allclose(result.v_magnitude, expected_vm, atol=1e-4)
    np.testing.assert_allclose(result.v_angle, expected_va, atol=np.deg2rad(1e-3))


@pytest.mark.parametrize("case_name", ["case9", "case14", "case30"])
def test_ieee_case_branch_flows_match_matpower_fixture(case_name):
    """IEEE benchmark branch flows match MATPOWER orientation and signs."""
    case_path, solution_path = require_fixtures(case_name)
    case = load_case(case_path)
    solution = load_json(solution_path)

    result = solve_power_flow(case)

    expected = solution["branches"]
    assert len(result.branch_flows) == len(expected)
    for actual, wanted in zip(result.branch_flows, expected):
        assert actual.from_bus == wanted["from_bus"]
        assert actual.to_bus == wanted["to_bus"]
        np.testing.assert_allclose(actual.p_from, wanted["p_from"], atol=1e-3)
        np.testing.assert_allclose(actual.q_from, wanted["q_from"], atol=1e-3)
        np.testing.assert_allclose(actual.p_to, wanted["p_to"], atol=1e-3)
        np.testing.assert_allclose(actual.q_to, wanted["q_to"], atol=1e-3)


def test_optional_matpower_soln9_fixture_matches_when_available():
    """MATPOWER test-suite soln9_pf provides a supplemental 9-bus check."""
    case_path = DATA_DIR / "t_case9_pf.json"
    solution_path = DATA_DIR / "soln9_pf.json"
    if not case_path.exists() or not solution_path.exists():
        pytest.skip("MATPOWER soln9_pf fixture has not been generated")

    result = solve_power_flow(load_case(case_path))
    solution = load_json(solution_path)

    expected_vm = np.array([bus["v_magnitude"] for bus in solution["buses"]])
    expected_va = np.deg2rad([bus["v_angle_degrees"] for bus in solution["buses"]])
    np.testing.assert_allclose(result.v_magnitude, expected_vm, atol=1e-4)
    np.testing.assert_allclose(result.v_angle, expected_va, atol=np.deg2rad(1e-3))
