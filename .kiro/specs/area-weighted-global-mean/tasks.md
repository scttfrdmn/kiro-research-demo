# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Area-Weighted Mean Uses Cosine-of-Latitude Weights
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior (the analytic anchors) - it will validate the fix when it passes after implementation
  - **GOAL**: Surface a counterexample that demonstrates the cold-biased uniform mean departs from a value known analytically
  - **Scoped PBT Approach**: Scope the property to grids where the bug condition holds (more than one distinct latitude) with analytically known area-weighted targets; do NOT compare area-weighted output against the old uniform output
  - Create `tests/test_bug_condition.py` using pytest (pytest.ini sets `pythonpath = .`, `testpaths = tests`)
  - Build an in-memory `xarray.Dataset` with `tas` over dims `(time, lat, lon)` and multiple distinct latitudes, written to a temp NetCDF file (use `tmp_path`) so `global_mean(path)` can open it
  - Constant-field anchor (2.3): a constant field C over a multi-latitude grid must average to C within 1e-9 K; on UNFIXED code `np.mean` also returns C here, so assert the fixed-behavior target C directly (analytic anchor, not an F-vs-F' comparison)
  - Analytic area-weighted target (2.1, 2.2): build a small multi-latitude field whose true `cos(deg2rad(lat))`-weighted mean is computable by hand, assert `global_mean` equals that analytic target within 1e-9 K
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS - the unfixed `np.mean` departs from the analytic cos(lat)-weighted target (this is correct; it proves the bug exists)
  - Document the counterexample found (the unfixed uniform mean lies below the analytic area-weighted mean on the warm-tropics/cold-poles grid, confirming the cold-bias direction and the uniform-weighting root cause)
  - Mark task complete when the test is written, run, and the failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Interface and Single-Band Reduction
  - **IMPORTANT**: Follow observation-first methodology - observe behavior on UNFIXED code for non-bug-condition inputs, then assert against the analytically known value (the plain mean), not against the old code's output
  - Create `tests/test_preservation.py` using pytest
  - Single-latitude-band reduction (3.1): build a grid where every cell shares one latitude; observe the unfixed result equals `np.mean` of the field; write a property-based test asserting the fixed `global_mean` equals the plain mean of the values within double-precision tolerance (one common cos(lat) weight cancels in normalisation)
  - Constant-field preservation (part of ¬C domain): generate random constant fields over single-band grids and assert the result equals the constant
  - `tas` read and path resolution (3.2, 3.3): assert `global_mean` reads the `tas` variable and resolves the positional path argument, defaulting to `data/sample.nc` when omitted
  - Return type and print format (3.4): assert the return value is a Python `float`; assert the `__main__` output line matches `"Global-mean temperature: {value:.3f} K"` exactly
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS on unfixed code (these inputs are outside the bug condition and confirm the baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix cold-biased uniform mean with cosine-of-latitude area weighting

  - [x] 3.1 Implement the area-weighted mean in `global_mean`
    - Edit `global_mean.py`, function `global_mean(path)`, changing only the aggregation step
    - Read the latitude coordinate: obtain `ds["lat"].values` alongside `ds["tas"].values`
    - Build cosine weights: `w = np.cos(np.deg2rad(lat))`, a 1-D array over the `lat` dimension
    - Broadcast and apply: align `w` with the `lat` axis of the `(time, lat, lon)` field and compute a convex-combination weighted mean `sum(temp * w_broadcast) / sum(w_broadcast)` over the same elements (equivalently `xarray`'s `weighted(...).mean()` over `lat` with plain mean over `time`/`lon`, or `np.average` with broadcast weights)
    - Wrap the aggregate in `float(...)` to preserve the Python `float` return
    - Leave the signature `global_mean(path)`, the `xr.open_dataset(path)` read, the `__main__` path resolution, and the print statement unchanged
    - _Bug_Condition: isBugCondition(input) where NOT allEqual(input.lat) AND cellsWeightedUniformly(input)_
    - _Expected_Behavior: expectedBehavior(result) - each cell weighted by cos(deg2rad(lat)); constant field returns C within 1e-9 K; areas from lat_bnds/lon_bnds sum to 4*pi within 1e-12 relative_
    - _Preservation: Preservation Requirements from design - tas read, CLI path resolution, float return, print format, single-band reduction to plain mean_
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.2 Add the area-closure identity test
    - **Property 1: Expected Behavior** - Area-Weighted Mean Uses Cosine-of-Latitude Weights
    - Add a test (in `tests/test_bug_condition.py` or a dedicated `tests/test_area_closure.py`) that derives per-cell areas from `lat_bnds`/`lon_bnds` using the exact closed-form element `(sin(deg2rad(lat_hi)) - sin(deg2rad(lat_lo))) * deg2rad(lon_hi - lon_lo)`
    - **IMPORTANT**: This exact-area formula lives in the test only - it is NOT used by the production aggregation (which uses cos(lat) centre weighting)
    - Assert the sum of all cell areas over the full sphere equals `4*pi` steradians within relative tolerance 1e-12, both for an in-memory grid built like `make_sample.py` and for the on-disk `data/sample.nc`
    - **EXPECTED OUTCOME**: Test PASSES (confirms the area derivation that backs the cos(lat) weighting)
    - _Requirements: 2.4_

  - [x] 3.3 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Area-Weighted Mean Uses Cosine-of-Latitude Weights
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior (constant-field anchor and analytic cos(lat)-weighted target)
    - Run the bug condition exploration test from task 1 on the fixed code
    - **EXPECTED OUTCOME**: Test PASSES (confirms the bug is fixed - the mean now matches the analytic area-weighted target within 1e-9 K)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Interface and Single-Band Reduction
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run the preservation property tests from task 2 on the fixed code
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions - single-band reduction to the plain mean, `tas` read, path resolution, `float` return, and print format all unchanged)
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4. Checkpoint - Ensure all tests pass
  - Run the full suite with `pytest` (single execution, not watch mode)
  - Confirm the exploration test (task 1), area-closure test (task 3.2), and preservation tests (task 2) all pass on the fixed code
  - Ensure all tests pass; ask the user if questions arise
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4_
