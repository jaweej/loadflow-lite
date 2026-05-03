# MATPOWER Fixture Provenance

Static fixtures in this directory are generated from MATPOWER 8.1 using GNU Octave and:

```matlab
mpopt = mpoption( ...
    'pf.alg', 'NR', ...
    'pf.enforce_q_lims', 0, ...
    'pf.tol', 1e-10, ...
    'verbose', 0, ...
    'out.all', 0 ...
);
```

The source checkout should live outside the Python package at `.external/matpower/` and must not be committed. Record the exact MATPOWER commit and Octave version in each generated JSON fixture's `metadata` object.

Expected generated files:

- `case9.json`
- `case9_solution.json`
- `case14.json`
- `case14_solution.json`
- `case30.json`
- `case30_solution.json`
- `t_case9_pf.json` if available in the pinned MATPOWER release
- `soln9_pf.json` if available in the pinned MATPOWER release

The case fixtures convert MATPOWER MW/MVAr quantities to p.u. on `baseMVA`. Solution fixtures store voltage angles in degrees to match MATPOWER output and branch/generator powers in p.u.
