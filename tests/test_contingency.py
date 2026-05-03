from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from powerflow.case import validate_case
from powerflow.contingency import (
    Limits,
    classify_case9_branch,
    classify_outage,
    connected_components,
    find_voltage_violations,
    largest_voltage_delta,
    remove_branch,
    run_branch_outage,
    run_case9_n1,
    stable_json_dumps,
)
from powerflow.io import load_case, load_json


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REPO_ROOT = Path(__file__).resolve().parents[1]


def case9():
    return load_case(DATA_DIR / "case9.json")


def branch_index(case, from_bus: int, to_bus: int) -> int:
    return next(
        idx
        for idx, branch in enumerate(case.branches)
        if (branch.from_bus, branch.to_bus) == (from_bus, to_bus)
    )


def voltages_by_bus(row):
    return {voltage.bus_id: voltage.v_post_pu for voltage in row.voltages}


def generator_outputs_by_bus(row):
    return {output.bus_id: output for output in row.generator_outputs}


def test_remove_branch_returns_new_case_without_revalidating():
    case = case9()
    original_branches = list(case.branches)

    outaged = remove_branch(case, branch_index(case, 4, 5))

    assert outaged is not case
    assert outaged.branches == original_branches[:1] + original_branches[2:]
    assert case.branches == original_branches
    assert all(actual is expected for actual, expected in zip(case.branches, original_branches))
    remove_branch(case, branch_index(case, 1, 4))


def test_connected_components_partitions_bus_ids():
    case = case9()

    assert connected_components(case) == [{bus.id for bus in case.buses}]
    assert connected_components(remove_branch(case, branch_index(case, 1, 4))) == [
        {1},
        {2, 3, 4, 5, 6, 7, 8, 9},
    ]
    assert connected_components(remove_branch(case, branch_index(case, 3, 6))) == [
        {1, 2, 4, 5, 6, 7, 8, 9},
        {3},
    ]


def test_classify_outage_distinguishes_slack_island_partial_island_and_connected():
    case = case9()

    slack_islanded = classify_outage(case, branch_index(case, 1, 4))
    assert slack_islanded.slack_islanded
    assert slack_islanded.islanded_buses == [1]
    assert slack_islanded.surviving_case is None

    partial = classify_outage(case, branch_index(case, 3, 6))
    assert not partial.slack_islanded
    assert partial.islanded_buses == [3]
    assert partial.surviving_buses == [1, 2, 4, 5, 6, 7, 8, 9]
    validate_case(partial.surviving_case)

    connected = classify_outage(case, branch_index(case, 4, 5))
    assert not connected.slack_islanded
    assert connected.islanded_buses == []
    assert connected.surviving_case == remove_branch(case, branch_index(case, 4, 5))


def test_classify_case9_branch_is_orientation_strict():
    assert classify_case9_branch((4, 5)) == "transmission_loop"
    assert classify_case9_branch((1, 4)) == "generator_connection"
    assert classify_case9_branch((8, 2)) == "generator_connection"
    with pytest.raises(ValueError, match="orientation"):
        classify_case9_branch((2, 8))


def test_connected_transmission_loop_outage_solves():
    case = case9()

    row = run_branch_outage(case, branch_index(case, 4, 5), Limits())

    assert row.status == "solved"
    assert set(voltages_by_bus(row)) == {bus.id for bus in case.buses}
    assert row.branch_count == len(case.branches) - 1


def test_partial_island_outage_solves_on_surviving_component():
    case = case9()
    base = run_case9_n1(case, Limits()).base_case

    row = run_branch_outage(case, branch_index(case, 3, 6), Limits())

    assert row.status == "partial_island"
    assert row.islanded_buses == [3]
    assert set(voltages_by_bus(row)) == {1, 2, 4, 5, 6, 7, 8, 9}
    outputs = generator_outputs_by_bus(row)
    assert set(outputs) == {1, 2}

    base_outputs = {output.bus_id: output for output in base.generator_outputs}
    slack_increase = outputs[1].p_gen_pu - base_outputs[1].p_gen_pu
    expected_increase = (
        next(bus.p_gen for bus in case.buses if bus.id == 3)
        + row.total_real_loss_pu
        - base.total_real_loss_pu
    )
    np.testing.assert_allclose(slack_increase, expected_increase, atol=1e-8)


def test_slack_islanded_outage_is_not_solved():
    case = case9()

    row = run_branch_outage(case, branch_index(case, 1, 4), Limits())

    assert row.status == "slack_islanded"
    assert row.islanded_buses == [1]
    assert row.voltages == []
    assert row.notes


def test_full_case9_report_uses_derived_counts():
    case = case9()

    report = run_case9_n1(case, Limits())

    by_group = {
        "transmission_loop": sum(1 for row in report.rows if row.group == "transmission_loop"),
        "generator_connection": sum(
            1 for row in report.rows if row.group == "generator_connection"
        ),
    }
    assert sum(by_group.values()) == len(case.branches)
    expected = {"transmission_loop": 0, "generator_connection": 0}
    for branch in case.branches:
        expected[classify_case9_branch((branch.from_bus, branch.to_bus))] += 1
    assert by_group == expected


def test_solved_contingencies_balance_power_on_surviving_component():
    case = case9()

    report = run_case9_n1(case, Limits())

    load_by_bus = {bus.id: (bus.p_load, bus.q_load) for bus in case.buses}
    for row in report.rows:
        if row.status not in {"solved", "partial_island"}:
            continue
        p_load = sum(load_by_bus[bus_id][0] for bus_id in row.surviving_buses)
        q_load = sum(load_by_bus[bus_id][1] for bus_id in row.surviving_buses)
        p_gen = sum(output.p_gen_pu for output in row.generator_outputs)
        q_gen = sum(output.q_gen_pu for output in row.generator_outputs)

        np.testing.assert_allclose(p_gen - p_load, row.total_real_loss_pu, atol=1e-8)
        np.testing.assert_allclose(
            q_gen - q_load,
            row.branch_reactive_endpoint_sum_pu,
            atol=1e-8,
        )


def test_voltage_violation_and_delta_detection_are_deterministic():
    violations = find_voltage_violations({1: 0.949, 2: 1.0, 3: 1.051}, Limits())

    assert [(item.bus_id, item.kind, item.v_post_pu) for item in violations] == [
        (1, "low", 0.949),
        (3, "high", 1.051),
    ]
    largest = largest_voltage_delta({1: 1.0, 2: 1.01, 3: 0.99}, {1: 1.02, 2: 1.0, 3: 0.98})
    assert largest.bus_id == 1
    assert largest.delta_from_base_pu == pytest.approx(0.02)


def test_case9_n1_transmission_loop_voltages_match_matpower_fixture():
    fixture_path = DATA_DIR / "case9_n1_solutions.json"
    if not fixture_path.exists():
        pytest.skip("MATPOWER case9 N-1 fixture has not been generated")
    fixture = load_json(fixture_path)
    expected_by_id = {
        row["contingency_id"]: {bus["id"]: bus["v_magnitude"] for bus in row["buses"]}
        for row in fixture["contingencies"]
    }

    report = run_case9_n1(case9(), Limits())

    for row in report.rows:
        if row.group != "transmission_loop":
            continue
        actual = voltages_by_bus(row)
        expected = expected_by_id[row.contingency_id]
        assert set(actual) == set(expected)
        for bus_id, expected_vm in expected.items():
            np.testing.assert_allclose(actual[bus_id], expected_vm, atol=1e-4)


def test_json_serialization_is_byte_stable():
    report = run_case9_n1(case9(), Limits())

    assert stable_json_dumps(report) == stable_json_dumps(report)


def test_case9_n1_script_writes_deterministic_json(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    for output in (first, second):
        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "run_case9_n1.py"),
                "--output",
                str(output),
            ],
            cwd=REPO_ROOT,
            check=True,
        )

    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["metadata"]["source_case"] == "case9"
    assert len(payload["contingencies"]) == len(case9().branches)
