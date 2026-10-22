# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Area-Weighted Mean Removes the Cold Bias
  - **CRITICAL**: This test MUST FAIL on the unfixed code - failure confirms the cold bias exists
  - **DO NOT attempt to fix the test or the code when it fails** - the failure is the expected, correct outcome at this step
  - **NOTE**: This test encodes the expected behavior (area-weighted mean); it will validate the fix once it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the unweighted mean is biased cold relative to the true area-weighted mean
  - **Scoped PBT Approach**: the bug is deterministic for a given dataset, so scope the property to concrete inputs with known weighting rather than random generation here
  - Add `tests/test_global_mean.py` and run all tests with `uv run pytest tests/test_global_mean.py` (never `python`/`python3`/`.venv/bin/python` directly)
  - Bug Condition (from design): `isBugCondition(X)` is true when the true unit-sphere cell areas from `lat_bnds`/`lon_bnds` are NOT all equal AND `tas` varies across latitude
  - Expected Behavior the test asserts (from design Property 1): the reported value equals `sum(area * tas_tmean) / sum(area)`, where `area[i,j] = (sin(lat_hi_rad) - sin(lat_lo_rad)) * (lon_hi_rad - lon_lo_rad)` and `tas_tmean` is `tas` averaged over `time`
  - Case A - cold-bias direction on `data/sample.nc`: compute an independent area-weighted mean from `lat_bnds`/`lon_bnds`, then assert `global_mean("data/sample.nc")` is strictly less than that area-weighted mean. The expected sign is analytic: the field is coldest at the poles where cells are smallest, so down-weighting the cold cells raises the mean. On UNFIXED code this inequality does not hold -> test FAILS
  - Case B - synthetic latitude gradient: build an in-test NetCDF with a field rising monotonically with latitude on a coarse grid with strongly unequal cell areas and known bounds; assert `global_mean(path)` equals the closed-form area-weighted mean (tolerance `rtol = 1e-12`, justified as a short exact-arithmetic chain in double precision). On UNFIXED code the unweighted mean differs -> test FAILS
  - Pin reproducibility: synthetic datasets built deterministically with explicit values; `data/sample.nc` is the committed file from `make_sample.py` (`SEED = 20261020`)
  - Run on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the cold bias exists)
  - Document counterexamples found (e.g. "global_mean(sample) returns the colder unweighted mean, not the warmer area-weighted mean")
  - Mark this task complete when the test is written, run, and the failure is documented
  - _Requirements: 1.1, 1.2, 2.1, 2.2_

- [x] 2. Write preservation property tests (BEFORE implementing the fix)
  - **Property 2: Preservation** - Uniform Fields and Equal-Area Grids Unchanged
  - **IMPORTANT**: Follow the observation-first methodology - run the UNFIXED code on non-bug-condition inputs and confirm the tests pass before any fix
  - These tests cover inputs where `isBugCondition` is false: spatially uniform fields and equal-area (single-latitude-row) grids
  - Assert against analytic targets (the known constant / the arithmetic mean of known values), never a second run of our own code, so the test and the code cannot share the same mistake
  - Case 1 - uniform field (3.1): build a synthetic dataset whose `tas` equals a constant `T0` at every cell and time with known bounds; assert `global_mean(path) == T0` within `atol = 1e-12`. Justification: the only arithmetic is `sum(area*T0)/sum(area) = T0`, a handful of rounding steps; near machine epsilon scaled by `T0 ~ 300` is `eps*300 ~ 6.7e-14`, so `1e-12` sits above worst-case rounding and far below any real deviation. This holds on UNFIXED code (unweighted mean of a constant is also `T0`)
  - Case 2 - equal-area grid / single latitude row (3.2): build a synthetic one-row grid (all cells share one area) with known values; assert `global_mean(path)` equals the plain arithmetic mean of those values within `rtol = 1e-12`. Justification: short-chain double-precision rounding; equal weights make the weighted and arithmetic means identical analytically. This holds on UNFIXED code
  - Case 3 - contract and format (3.3, 3.4): assert `global_mean(path)` returns a Python `float`; assert the time axis is averaged (result unchanged under time reordering of a constructed time-symmetric field); assert `uv run python global_mean.py data/sample.nc` prints one line matching `Global-mean temperature: {value:.3f} K`. These are structural assertions and hold on UNFIXED code
  - Optional property-based form (recommended): generate constant fields with random `T0` and random valid increasing bounds and assert the result equals `T0` (`atol = 1e-12`); generate single-row grids with random values and assert the result equals the analytic arithmetic mean (`rtol = 1e-12`). The asserted target stays analytic
  - Run all tests with `uv run pytest tests/test_global_mean.py`
  - Run on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms the baseline behavior to preserve)
  - Mark this task complete when the tests are written, run, and passing on the unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix the cold bias in `global_mean()` by applying a true-spherical-cell-area weighted mean

  - [x] 3.1 Implement the area-weighted mean in `global_mean.py`
    - Read cell edges after opening the dataset: `lat_bnds` (shape `(lat, 2)`) and `lon_bnds` (shape `(lon, 2)`)
    - Compute true unit-sphere cell areas: convert edges to radians; per-latitude band weight `d_sin = sin(lat_hi_rad) - sin(lat_lo_rad)`; per-longitude width `d_lon = lon_hi_rad - lon_lo_rad`; cell area `area[i, j] = d_sin[i] * d_lon[j]` as an outer product, shape `(lat, lon)`
    - Average over time first (unweighted): `tas_tmean = tas.mean over time` -> shape `(lat, lon)`
    - Apply the area-weighted spatial mean: `result = sum(area * tas_tmean) / sum(area)`, returned as a Python `float`
    - Keep the contract and script format unchanged: still read `tas` from the file at `path`, still return a single `float`, and leave the `__main__` print line `Global-mean temperature: {value:.3f} K` unchanged
    - Keep the change minimal per workspace scope rules: edit `global_mean()` only - no new frameworks, configuration systems, or abstractions
    - _Bug_Condition: isBugCondition(X) = (true unit-sphere cell areas from lat_bnds/lon_bnds are NOT all equal) AND (tas varies across latitude)_
    - _Expected_Behavior: result = sum(area * tas_tmean) / sum(area), area[i,j] = (sin(lat_hi_rad) - sin(lat_lo_rad)) * (lon_hi_rad - lon_lo_rad), tas_tmean = tas averaged over time (design Property 1 / Fix Implementation)_
    - _Preservation: uniform field returns the constant (3.1); equal-area grid returns the arithmetic mean (3.2); read/time-average/return-float contract (3.3); script print format (3.4)_
    - _Requirements: 2.1, 2.2_

  - [x] 3.2 Add a cell-area helper unit test: area sum equals 4*pi
    - Compute cell areas from a full non-overlapping sphere tiling (the 90 lat x 180 lon grid implied by `data/sample.nc` bounds, or an equivalent full-grid synthetic) and assert `sum(area)` equals `4*pi`
    - **Tolerance**: `abs(sum(area) - 4*pi) <= 1e-9`. Justification: the sum accumulates ~16200 cell areas, each a difference of `sin` values and of longitudes; worst-case accumulated rounding is on the order of `eps * 4*pi * sqrt(N) ~ 2.2e-16 * 12.57 * 127 ~ 3.6e-13`. `1e-9` sits well above that yet far below any structurally meaningful error, so the check is exact-or-wrong, not approximately right
    - This anchors the area weighting against an exact analytic total (`4*pi` is the unit-sphere surface area)
    - Run with `uv run pytest tests/test_global_mean.py`
    - _Requirements: 2.1_

  - [x] 3.3 Verify the bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Area-Weighted Mean Removes the Cold Bias
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test. The test from task 1 encodes the expected behavior; when it passes it confirms the fix is correct
    - Run with `uv run pytest tests/test_global_mean.py`
    - **EXPECTED OUTCOME**: Test PASSES - Case A now satisfies `global_mean(sample) < area_weighted_mean` is false (fixed function equals the area-weighted mean, strictly warmer than the old unweighted mean), and Case B matches the closed-form area-weighted value within `rtol = 1e-12`
    - As an integration check, confirm the fixed result lies within the min/max of the field (a necessary bound for any positive-weight weighted mean)
    - _Requirements: 2.1, 2.2_

  - [x] 3.4 Verify the preservation tests still pass
    - **Property 2: Preservation** - Uniform Fields and Equal-Area Grids Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run with `uv run pytest tests/test_global_mean.py`
    - **EXPECTED OUTCOME**: Tests PASS (no regressions) - uniform field still returns `T0` (`atol = 1e-12`), single-row equal-area grid still returns the arithmetic mean (`rtol = 1e-12`), return type is still `float`, time is still averaged, and the script still prints `Global-mean temperature: {value:.3f} K`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4. Checkpoint - Ensure all tests pass
  - Run the full suite with `uv run pytest` and confirm every test passes (exploration test from task 1 now green, preservation tests from task 2 still green, unit test from 3.2 green)
  - Confirm no numerical assertion was weakened: tolerances remain `1e-9` (area sum), `1e-12` (constant field), and `rtol 1e-12` (known-area / equal-area means), each justified in the design
  - If any question or ambiguity arises, ask the user before proceeding
  - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 3.4_
