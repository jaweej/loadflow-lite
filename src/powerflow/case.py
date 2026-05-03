from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VALID_BUS_TYPES = {"slack", "pv", "pq"}


@dataclass(frozen=True)
class Bus:
    id: int
    type: str
    p_load: float
    q_load: float
    p_gen: float
    q_gen: float
    v_magnitude: float
    v_angle: float
    g_shunt: float = 0.0
    b_shunt: float = 0.0


@dataclass(frozen=True)
class Branch:
    from_bus: int
    to_bus: int
    r: float
    x: float
    b: float
    tap_ratio: float = 1.0
    phase_shift: float = 0.0
    status: int = 1


@dataclass(frozen=True)
class Case:
    base_mva: float
    buses: list[Bus]
    branches: list[Branch]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Case":
        return cls(
            base_mva=float(payload["base_mva"]),
            buses=[Bus(**bus) for bus in payload["buses"]],
            branches=[Branch(**branch) for branch in payload["branches"]],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_mva": self.base_mva,
            "buses": [bus.__dict__.copy() for bus in self.buses],
            "branches": [branch.__dict__.copy() for branch in self.branches],
        }


def bus_index(case: Case) -> dict[int, int]:
    validate_case(case)
    return {bus.id: idx for idx, bus in enumerate(case.buses)}


def validate_case(case: Case) -> None:
    if case.base_mva <= 0:
        raise ValueError("case base_mva must be positive")
    if not case.buses:
        raise ValueError("case must contain at least one bus")

    seen: set[int] = set()
    slack_count = 0
    for bus in case.buses:
        if bus.id in seen:
            raise ValueError(f"duplicate bus id {bus.id}")
        seen.add(bus.id)
        if bus.type not in VALID_BUS_TYPES:
            raise ValueError(f"bus {bus.id} has invalid type {bus.type!r}")
        if bus.type == "slack":
            slack_count += 1
        if bus.v_magnitude <= 0:
            raise ValueError(f"bus {bus.id} voltage magnitude must be positive")

    if slack_count != 1:
        raise ValueError(f"case must contain exactly one slack bus, found {slack_count}")

    for branch in case.branches:
        if branch.status != 1:
            raise ValueError(
                f"branch {branch.from_bus}->{branch.to_bus} has status {branch.status}; "
                "v0 supports only in-service branches"
            )
        if branch.from_bus not in seen:
            raise ValueError(f"branch references nonexistent from_bus {branch.from_bus}")
        if branch.to_bus not in seen:
            raise ValueError(f"branch references nonexistent to_bus {branch.to_bus}")
        if branch.from_bus == branch.to_bus:
            raise ValueError(f"branch {branch.from_bus}->{branch.to_bus} connects a bus to itself")
        if branch.r == 0.0 and branch.x == 0.0:
            raise ValueError(f"branch {branch.from_bus}->{branch.to_bus} has zero impedance")
        if branch.tap_ratio == 0.0:
            raise ValueError(f"branch {branch.from_bus}->{branch.to_bus} has zero tap ratio")
