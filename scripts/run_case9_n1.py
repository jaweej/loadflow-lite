from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from powerflow.contingency import Limits, report_to_dict, run_case9_n1, stable_json_dumps
from powerflow.io import load_case


def main() -> int:
    parser = argparse.ArgumentParser(description="Run IEEE 9-bus AC N-1 branch outage analysis.")
    parser.add_argument(
        "--case",
        type=Path,
        default=REPO_ROOT / "data" / "case9.json",
        help="Input case JSON path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data" / "case9_n1_results.json",
        help="Output JSON path.",
    )
    parser.add_argument("--solver-tolerance", type=float, default=1e-8)
    parser.add_argument("--v-min", type=float, default=0.95)
    parser.add_argument("--v-max", type=float, default=1.05)
    parser.add_argument("--q-gen-sanity-limit-pu", type=float, default=2.0)
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Include the current UTC timestamp in metadata. Omitted by default for stable diffs.",
    )
    args = parser.parse_args()

    case = load_case(args.case)
    limits = Limits(
        v_min=args.v_min,
        v_max=args.v_max,
        q_gen_sanity_limit_pu=args.q_gen_sanity_limit_pu,
    )
    report = run_case9_n1(
        case,
        limits,
        solver_tolerance=args.solver_tolerance,
        source_case=args.case.stem,
    )
    payload = report_to_dict(report)
    if args.timestamp:
        payload["metadata"]["generated_at"] = datetime.now(UTC).isoformat()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(stable_json_dumps(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
