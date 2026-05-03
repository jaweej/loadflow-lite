from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from powerflow.case import Bus, Case, validate_case
from powerflow.flows import BranchFlow
from powerflow.solver import PowerFlowDidNotConverge, PowerFlowResult, solve_power_flow


TRANSMISSION_LOOP_BRANCHES = {
    (4, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (8, 9),
    (9, 4),
}
GENERATOR_CONNECTION_BRANCHES = {
    (1, 4),
    (3, 6),
    (8, 2),
}


@dataclass(frozen=True)
class Limits:
    v_min: float = 0.95
    v_max: float = 1.05
    q_gen_sanity_limit_pu: float = 2.0


@dataclass(frozen=True)
class OutageTopology:
    slack_islanded: bool
    islanded_buses: list[int]
    surviving_buses: list[int]
    surviving_case: Case | None


@dataclass(frozen=True)
class VoltageViolation:
    bus_id: int
    kind: str
    v_post_pu: float
    limit_pu: float


@dataclass(frozen=True)
class VoltageDelta:
    bus_id: int
    v_base_pu: float
    v_post_pu: float
    delta_from_base_pu: float


@dataclass(frozen=True)
class BranchFlowRecord:
    from_bus: int
    to_bus: int
    p_from_pu: float
    q_from_pu: float
    p_to_pu: float
    q_to_pu: float
    p_loss_pu: float
    branch_reactive_endpoint_sum_pu: float
    p_from_mw: float
    q_from_mvar: float
    p_to_mw: float
    q_to_mvar: float
    p_loss_mw: float
    branch_reactive_endpoint_sum_mvar: float


@dataclass(frozen=True)
class GeneratorOutput:
    bus_id: int
    bus_type: str
    p_gen_pu: float
    q_gen_pu: float
    p_gen_mw: float
    q_gen_mvar: float


@dataclass(frozen=True)
class BaseCaseSummary:
    converged: bool
    iterations: int
    max_mismatch_pu: float
    min_voltage_pu: float
    min_voltage_bus_id: int
    max_voltage_pu: float
    max_voltage_bus_id: int
    total_real_loss_pu: float
    total_real_loss_mw: float
    branch_reactive_endpoint_sum_pu: float
    branch_reactive_endpoint_sum_mvar: float
    generator_outputs: list[GeneratorOutput]


@dataclass(frozen=True)
class ContingencyResult:
    contingency_id: str
    from_bus: int
    to_bus: int
    group: str
    status: str
    islanded_buses: list[int]
    surviving_buses: list[int]
    branch_count: int
    converged: bool
    iterations: int | None
    max_mismatch_pu: float | None
    voltages: list[VoltageDelta]
    min_voltage_pu: float | None
    min_voltage_bus_id: int | None
    max_voltage_pu: float | None
    max_voltage_bus_id: int | None
    largest_abs_voltage_delta_pu: float | None
    largest_abs_voltage_delta_bus_id: int | None
    total_real_loss_pu: float | None
    total_real_loss_mw: float | None
    branch_reactive_endpoint_sum_pu: float | None
    branch_reactive_endpoint_sum_mvar: float | None
    largest_abs_branch_end_mw: float | None
    branch_flows: list[BranchFlowRecord]
    generator_outputs: list[GeneratorOutput]
    voltage_violations: list[VoltageViolation]
    notes: list[str]


@dataclass(frozen=True)
class N1Report:
    metadata: dict[str, Any]
    base_case: BaseCaseSummary
    rows: list[ContingencyResult]


def remove_branch(case: Case, branch_index: int) -> Case:
    if not 0 <= branch_index < len(case.branches):
        raise IndexError(f"branch_index {branch_index} out of range")
    return Case(
        base_mva=case.base_mva,
        buses=list(case.buses),
        branches=case.branches[:branch_index] + case.branches[branch_index + 1 :],
    )


def connected_components(case: Case) -> list[set[int]]:
    adjacency = {bus.id: set() for bus in case.buses}
    for branch in case.branches:
        if branch.from_bus not in adjacency:
            raise ValueError(f"branch references nonexistent from_bus {branch.from_bus}")
        if branch.to_bus not in adjacency:
            raise ValueError(f"branch references nonexistent to_bus {branch.to_bus}")
        adjacency[branch.from_bus].add(branch.to_bus)
        adjacency[branch.to_bus].add(branch.from_bus)

    remaining = set(adjacency)
    components: list[set[int]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        component = {start}
        remaining.remove(start)
        while stack:
            current = stack.pop()
            for neighbor in sorted(adjacency[current]):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)

    return sorted(components, key=lambda item: min(item))


def classify_outage(case: Case, branch_index: int) -> OutageTopology:
    outaged = remove_branch(case, branch_index)
    components = connected_components(outaged)
    slack_bus_id = _single_slack_bus_id(case)

    if len(components) == 1:
        surviving_buses = sorted(components[0])
        return OutageTopology(
            slack_islanded=False,
            islanded_buses=[],
            surviving_buses=surviving_buses,
            surviving_case=outaged,
        )

    slack_component = next(component for component in components if slack_bus_id in component)
    non_slack_components = [component for component in components if slack_bus_id not in component]
    non_slack_buses: list[int] = []
    for component in non_slack_components:
        non_slack_buses.extend(sorted(component))

    if not _component_has_load(case, slack_component):
        load_components = [component for component in non_slack_components if _component_has_load(case, component)]
        surviving_buses: list[int] = []
        for component in load_components:
            surviving_buses.extend(sorted(component))
        return OutageTopology(
            slack_islanded=True,
            islanded_buses=sorted(slack_component),
            surviving_buses=surviving_buses,
            surviving_case=None,
        )

    surviving_case = _subcase_for_buses(outaged, slack_component)
    validate_case(surviving_case)
    return OutageTopology(
        slack_islanded=False,
        islanded_buses=non_slack_buses,
        surviving_buses=sorted(slack_component),
        surviving_case=surviving_case,
    )


def classify_case9_branch(from_to: tuple[int, int]) -> str:
    if from_to in TRANSMISSION_LOOP_BRANCHES:
        return "transmission_loop"
    if from_to in GENERATOR_CONNECTION_BRANCHES:
        return "generator_connection"

    reversed_tuple = (from_to[1], from_to[0])
    if reversed_tuple in TRANSMISSION_LOOP_BRANCHES or reversed_tuple in GENERATOR_CONNECTION_BRANCHES:
        raise ValueError(
            f"branch tuple {from_to} uses the reverse orientation; use {reversed_tuple}"
        )
    raise ValueError(f"branch tuple {from_to} is not a case9 branch")


def find_voltage_violations(
    voltages_by_bus: dict[int, float],
    limits: Limits,
) -> list[VoltageViolation]:
    violations: list[VoltageViolation] = []
    for bus_id in sorted(voltages_by_bus):
        voltage = voltages_by_bus[bus_id]
        if voltage < limits.v_min:
            violations.append(VoltageViolation(bus_id, "low", voltage, limits.v_min))
        if voltage > limits.v_max:
            violations.append(VoltageViolation(bus_id, "high", voltage, limits.v_max))
    return violations


def largest_voltage_delta(
    base_voltages_by_bus: dict[int, float],
    post_voltages_by_bus: dict[int, float],
) -> VoltageDelta:
    deltas = _voltage_deltas(base_voltages_by_bus, post_voltages_by_bus)
    if not deltas:
        raise ValueError("no surviving buses available for voltage delta calculation")
    return max(deltas, key=lambda item: (abs(item.delta_from_base_pu), -item.bus_id))


def run_branch_outage(
    case: Case,
    branch_index: int,
    limits: Limits,
    solver_tolerance: float = 1e-8,
) -> ContingencyResult:
    base_result = solve_power_flow(case, tolerance=solver_tolerance, max_iterations=50)
    return _run_branch_outage_with_base(case, branch_index, limits, solver_tolerance, base_result)


def run_case9_n1(
    case: Case,
    limits: Limits,
    solver_tolerance: float = 1e-8,
    source_case: str = "case9",
) -> N1Report:
    base_result = solve_power_flow(case, tolerance=solver_tolerance, max_iterations=50)
    base_case = _base_case_summary(case, base_result)
    rows = [
        _run_branch_outage_with_base(case, branch_index, limits, solver_tolerance, base_result)
        for branch_index in range(len(case.branches))
    ]
    metadata = {
        "source_case": source_case,
        "base_mva": case.base_mva,
        "solver_tolerance": solver_tolerance,
        "voltage_limits": {
            "v_min": limits.v_min,
            "v_max": limits.v_max,
        },
        "q_gen_sanity_limit_pu": limits.q_gen_sanity_limit_pu,
        "power_units": "p.u. values are on base_mva; MW and MVAr values are converted using base_mva.",
        "branch_reactive_endpoint_sum": (
            "Sum over branches of q_from + q_to; includes line charging as a "
            "negative contribution and is not colloquial reactive losses."
        ),
        "caveats": [
            "Branch thermal ratings are absent from the fixture; overload checks are unavailable.",
            "Generator reactive limits are absent from the fixture; Q-limit enforcement is not performed.",
        ],
    }
    return N1Report(metadata=metadata, base_case=base_case, rows=rows)


def report_to_dict(report: N1Report) -> dict[str, Any]:
    return {
        "metadata": _clean_value(report.metadata),
        "base_case": _clean_value(asdict(report.base_case)),
        "contingencies": [_clean_value(asdict(row)) for row in report.rows],
    }


def stable_json_dumps(report_or_dict: N1Report | dict[str, Any]) -> str:
    payload = report_to_dict(report_or_dict) if isinstance(report_or_dict, N1Report) else report_or_dict
    return json.dumps(_clean_value(payload), indent=2, sort_keys=True) + "\n"


def _run_branch_outage_with_base(
    case: Case,
    branch_index: int,
    limits: Limits,
    solver_tolerance: float,
    base_result: PowerFlowResult,
) -> ContingencyResult:
    branch = case.branches[branch_index]
    from_to = (branch.from_bus, branch.to_bus)
    group = classify_case9_branch(from_to)
    topology = classify_outage(case, branch_index)
    contingency_id = _contingency_id(branch.from_bus, branch.to_bus)
    base_voltages = _voltage_map(case, base_result)

    if topology.slack_islanded:
        return ContingencyResult(
            contingency_id=contingency_id,
            from_bus=branch.from_bus,
            to_bus=branch.to_bus,
            group=group,
            status="slack_islanded",
            islanded_buses=topology.islanded_buses,
            surviving_buses=topology.surviving_buses,
            branch_count=len(case.branches) - 1,
            converged=False,
            iterations=None,
            max_mismatch_pu=None,
            voltages=[],
            min_voltage_pu=None,
            min_voltage_bus_id=None,
            max_voltage_pu=None,
            max_voltage_bus_id=None,
            largest_abs_voltage_delta_pu=None,
            largest_abs_voltage_delta_bus_id=None,
            total_real_loss_pu=None,
            total_real_loss_mw=None,
            branch_reactive_endpoint_sum_pu=None,
            branch_reactive_endpoint_sum_mvar=None,
            largest_abs_branch_end_mw=None,
            branch_flows=[],
            generator_outputs=[],
            voltage_violations=[],
            notes=[
                (
                    f"slack bus {topology.islanded_buses[0]} islanded; surviving load "
                    "component has no slack reference; AC power flow not solved"
                )
            ],
        )

    assert topology.surviving_case is not None
    try:
        post_result = solve_power_flow(
            topology.surviving_case,
            tolerance=solver_tolerance,
            max_iterations=50,
        )
    except PowerFlowDidNotConverge as exc:
        return _non_converged_result(
            case,
            branch_index,
            group,
            topology,
            str(exc),
        )

    post_voltages = _voltage_map(topology.surviving_case, post_result)
    voltages = _voltage_deltas(base_voltages, post_voltages)
    largest_delta = largest_voltage_delta(base_voltages, post_voltages)
    min_bus_id, min_voltage = min(post_voltages.items(), key=lambda item: (item[1], item[0]))
    max_bus_id, max_voltage = max(post_voltages.items(), key=lambda item: (item[1], -item[0]))
    branch_flows = _branch_flow_records(topology.surviving_case, post_result.branch_flows)
    total_real_loss_pu = sum(flow.p_loss for flow in post_result.branch_flows)
    reactive_endpoint_sum_pu = sum(flow.q_from + flow.q_to for flow in post_result.branch_flows)
    generator_outputs = _generator_outputs(topology.surviving_case, post_result)
    notes = _solved_notes(case, topology, generator_outputs, limits)

    return ContingencyResult(
        contingency_id=contingency_id,
        from_bus=branch.from_bus,
        to_bus=branch.to_bus,
        group=group,
        status="partial_island" if topology.islanded_buses else "solved",
        islanded_buses=topology.islanded_buses,
        surviving_buses=topology.surviving_buses,
        branch_count=len(topology.surviving_case.branches),
        converged=post_result.converged,
        iterations=post_result.iterations,
        max_mismatch_pu=post_result.max_mismatch,
        voltages=voltages,
        min_voltage_pu=min_voltage,
        min_voltage_bus_id=min_bus_id,
        max_voltage_pu=max_voltage,
        max_voltage_bus_id=max_bus_id,
        largest_abs_voltage_delta_pu=abs(largest_delta.delta_from_base_pu),
        largest_abs_voltage_delta_bus_id=largest_delta.bus_id,
        total_real_loss_pu=total_real_loss_pu,
        total_real_loss_mw=total_real_loss_pu * topology.surviving_case.base_mva,
        branch_reactive_endpoint_sum_pu=reactive_endpoint_sum_pu,
        branch_reactive_endpoint_sum_mvar=reactive_endpoint_sum_pu
        * topology.surviving_case.base_mva,
        largest_abs_branch_end_mw=_largest_abs_branch_end_mw(post_result.branch_flows, case.base_mva),
        branch_flows=branch_flows,
        generator_outputs=generator_outputs,
        voltage_violations=find_voltage_violations(post_voltages, limits),
        notes=notes,
    )


def _base_case_summary(case: Case, result: PowerFlowResult) -> BaseCaseSummary:
    voltages = _voltage_map(case, result)
    min_bus_id, min_voltage = min(voltages.items(), key=lambda item: (item[1], item[0]))
    max_bus_id, max_voltage = max(voltages.items(), key=lambda item: (item[1], -item[0]))
    total_real_loss_pu = sum(flow.p_loss for flow in result.branch_flows)
    reactive_endpoint_sum_pu = sum(flow.q_from + flow.q_to for flow in result.branch_flows)
    return BaseCaseSummary(
        converged=result.converged,
        iterations=result.iterations,
        max_mismatch_pu=result.max_mismatch,
        min_voltage_pu=min_voltage,
        min_voltage_bus_id=min_bus_id,
        max_voltage_pu=max_voltage,
        max_voltage_bus_id=max_bus_id,
        total_real_loss_pu=total_real_loss_pu,
        total_real_loss_mw=total_real_loss_pu * case.base_mva,
        branch_reactive_endpoint_sum_pu=reactive_endpoint_sum_pu,
        branch_reactive_endpoint_sum_mvar=reactive_endpoint_sum_pu * case.base_mva,
        generator_outputs=_generator_outputs(case, result),
    )


def _non_converged_result(
    case: Case,
    branch_index: int,
    group: str,
    topology: OutageTopology,
    reason: str,
) -> ContingencyResult:
    branch = case.branches[branch_index]
    return ContingencyResult(
        contingency_id=_contingency_id(branch.from_bus, branch.to_bus),
        from_bus=branch.from_bus,
        to_bus=branch.to_bus,
        group=group,
        status="non_converged",
        islanded_buses=topology.islanded_buses,
        surviving_buses=topology.surviving_buses,
        branch_count=len(topology.surviving_case.branches) if topology.surviving_case else 0,
        converged=False,
        iterations=None,
        max_mismatch_pu=None,
        voltages=[],
        min_voltage_pu=None,
        min_voltage_bus_id=None,
        max_voltage_pu=None,
        max_voltage_bus_id=None,
        largest_abs_voltage_delta_pu=None,
        largest_abs_voltage_delta_bus_id=None,
        total_real_loss_pu=None,
        total_real_loss_mw=None,
        branch_reactive_endpoint_sum_pu=None,
        branch_reactive_endpoint_sum_mvar=None,
        largest_abs_branch_end_mw=None,
        branch_flows=[],
        generator_outputs=[],
        voltage_violations=[],
        notes=[reason],
    )


def _voltage_map(case: Case, result: PowerFlowResult) -> dict[int, float]:
    return {bus.id: float(result.v_magnitude[idx]) for idx, bus in enumerate(case.buses)}


def _voltage_deltas(
    base_voltages_by_bus: dict[int, float],
    post_voltages_by_bus: dict[int, float],
) -> list[VoltageDelta]:
    deltas: list[VoltageDelta] = []
    for bus_id in sorted(post_voltages_by_bus):
        v_base = base_voltages_by_bus[bus_id]
        v_post = post_voltages_by_bus[bus_id]
        deltas.append(VoltageDelta(bus_id, v_base, v_post, v_post - v_base))
    return deltas


def _branch_flow_records(case: Case, flows: list[BranchFlow]) -> list[BranchFlowRecord]:
    records: list[BranchFlowRecord] = []
    for flow in flows:
        reactive_endpoint_sum_pu = flow.q_from + flow.q_to
        records.append(
            BranchFlowRecord(
                from_bus=flow.from_bus,
                to_bus=flow.to_bus,
                p_from_pu=flow.p_from,
                q_from_pu=flow.q_from,
                p_to_pu=flow.p_to,
                q_to_pu=flow.q_to,
                p_loss_pu=flow.p_loss,
                branch_reactive_endpoint_sum_pu=reactive_endpoint_sum_pu,
                p_from_mw=flow.p_from * case.base_mva,
                q_from_mvar=flow.q_from * case.base_mva,
                p_to_mw=flow.p_to * case.base_mva,
                q_to_mvar=flow.q_to * case.base_mva,
                p_loss_mw=flow.p_loss * case.base_mva,
                branch_reactive_endpoint_sum_mvar=reactive_endpoint_sum_pu * case.base_mva,
            )
        )
    return records


def _generator_outputs(case: Case, result: PowerFlowResult) -> list[GeneratorOutput]:
    outputs: list[GeneratorOutput] = []
    for idx, bus in enumerate(case.buses):
        if bus.type not in {"slack", "pv"}:
            continue
        outputs.append(
            GeneratorOutput(
                bus_id=bus.id,
                bus_type=bus.type,
                p_gen_pu=float(result.p_generation[idx]),
                q_gen_pu=float(result.q_generation[idx]),
                p_gen_mw=float(result.p_generation[idx] * case.base_mva),
                q_gen_mvar=float(result.q_generation[idx] * case.base_mva),
            )
        )
    return outputs


def _solved_notes(
    case: Case,
    topology: OutageTopology,
    generator_outputs: list[GeneratorOutput],
    limits: Limits,
) -> list[str]:
    notes: list[str] = []
    if topology.islanded_buses:
        lost_generation_pu = sum(
            bus.p_gen for bus in case.buses if bus.id in set(topology.islanded_buses)
        )
        notes.append(
            (
                f"bus {','.join(str(bus_id) for bus_id in topology.islanded_buses)} "
                f"islanded; {lost_generation_pu:.6g} p.u. / "
                f"{lost_generation_pu * case.base_mva:.6g} MW of generation absorbed by slack"
            )
        )
    for output in generator_outputs:
        if abs(output.q_gen_pu) > limits.q_gen_sanity_limit_pu:
            notes.append(
                (
                    f"generator bus {output.bus_id} solved q_gen_pu="
                    f"{output.q_gen_pu:.6g}, exceeding sanity threshold "
                    f"{limits.q_gen_sanity_limit_pu:.6g}"
                )
            )
    return notes


def _single_slack_bus_id(case: Case) -> int:
    slack_buses = [bus.id for bus in case.buses if bus.type == "slack"]
    if len(slack_buses) != 1:
        raise ValueError(f"case must contain exactly one slack bus, found {len(slack_buses)}")
    return slack_buses[0]


def _component_has_load(case: Case, component: set[int]) -> bool:
    return any((bus.p_load != 0.0 or bus.q_load != 0.0) and bus.id in component for bus in case.buses)


def _subcase_for_buses(case: Case, bus_ids: set[int]) -> Case:
    return Case(
        base_mva=case.base_mva,
        buses=[bus for bus in case.buses if bus.id in bus_ids],
        branches=[
            branch
            for branch in case.branches
            if branch.from_bus in bus_ids and branch.to_bus in bus_ids
        ],
    )


def _largest_abs_branch_end_mw(flows: list[BranchFlow], base_mva: float) -> float:
    if not flows:
        return 0.0
    largest_pu = max(
        max(abs(flow.p_from), abs(flow.p_to))
        for flow in flows
    )
    return largest_pu * base_mva


def _contingency_id(from_bus: int, to_bus: int) -> str:
    return f"{from_bus}-{to_bus}"


def _clean_value(value: Any) -> Any:
    if isinstance(value, float):
        if not np.isfinite(value):
            raise ValueError(f"cannot serialize non-finite float {value}")
        rounded = round(value, 10)
        return 0.0 if rounded == 0.0 else rounded
    if isinstance(value, dict):
        return {key: _clean_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean_value(item) for item in value]
    return value
