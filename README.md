# Load Flow Lite

Minimal AC Newton-Raphson power flow solver in Python. The implementation is intentionally small and dense: `numpy` for numerics, `pytest` for tests, and static MATPOWER fixtures for benchmark validation.

## Current Status

- Y-bus assembly is implemented for lines, line charging, off-nominal taps, phase shifts, and bus shunts.
- Slack, PV, and PQ bus handling is implemented.
- Newton-Raphson solves polar AC power flow with an analytic Jacobian.
- Branch flows, losses, solved bus injections, and solved generation are computed.
- Toy/system tests pass.
- IEEE MATPOWER fixture tests are present but skip until `data/*_solution.json` fixtures are generated.

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
```

## Tests

```bash
./.venv/bin/python -m pytest
```

Without generated MATPOWER fixtures, the IEEE tests are skipped. After fixture generation, the test suite validates case9, case14, and case30 voltages and branch flows against static MATPOWER `runpf` output.

## Known Limitations

- No reactive power limits or PV-to-PQ conversion.
- No DC power flow.
- No OPF or contingency analysis.
- No sparse matrix path.
- Out-of-service branches are rejected instead of handled.
- The test suite is the only interface; there is no CLI or plotting layer.
