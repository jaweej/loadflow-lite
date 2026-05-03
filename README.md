# Load Flow Lite

Minimal AC Newton-Raphson power flow solver in Python. The implementation is intentionally small and dense: `numpy` for numerics, `pytest` for tests, and static MATPOWER fixtures for benchmark validation.

## Current Status

- Y-bus assembly is implemented for lines, line charging, off-nominal taps, phase shifts, and bus shunts.
- Slack, PV, and PQ bus handling is implemented.
- Newton-Raphson solves polar AC power flow with an analytic Jacobian.
- Branch flows, losses, solved bus injections, and solved generation are computed.
- IEEE 9-bus AC N-1 branch-outage analysis is implemented with deterministic JSON output.
- Toy/system tests pass.
- IEEE MATPOWER fixture tests validate `case9`, `case14`, `case30`, and the supplemental `soln9_pf` 9-bus fixture.

## Setup

Use the project virtualenv:

```bash
python3 -m venv .venv
./.venv/bin/pip install numpy pytest
```

For MATPOWER fixture generation, GNU Octave must be installed as a system tool and MATPOWER must be checked out under the ignored `.external/` directory:

```bash
sudo apt-get update
sudo apt-get install -y octave
mkdir -p .external
git clone --depth 1 --branch 8.1 https://github.com/MATPOWER/matpower.git .external/matpower
```

Then generate fixtures:

```bash
octave --quiet scripts/generate_matpower_fixtures.m
octave --quiet scripts/generate_case9_n1_matpower_fixture.m
```

## IEEE 9-Bus N-1 Analysis

```bash
./.venv/bin/python scripts/run_case9_n1.py
```

The script writes `data/case9_n1_results.json` by default. The accompanying
note is in `docs/ieee9_n1_analysis_note.tex` and
`docs/ieee9_n1_analysis_note.pdf`.

## Tests

```bash
./.venv/bin/python -m pytest
```

Without generated MATPOWER fixtures, the IEEE tests are skipped. With fixtures present, the test suite validates case9, case14, and case30 voltages, generator outputs, and branch flows against static MATPOWER `runpf` output.

## Known Limitations

- No reactive power limits or PV-to-PQ conversion.
- No DC power flow.
- No OPF or economic redispatch.
- No sparse matrix path.
- Out-of-service branches are rejected instead of handled.
- The only CLI is the case9 N-1 analysis script; there is no general case-runner CLI.
