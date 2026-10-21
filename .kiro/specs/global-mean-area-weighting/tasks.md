# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Latitude-Varying Field Is Biased Cold
  - **CRITICAL**: This test MUST FAIL on unfixed `global_mean.py` - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails** - the failure is the expected result for this task
  - **NOTE**: The assertion encodes the expected (area-weighted) behavior, so the same test will validate the fix once it passes in task 3.2
  - **GOAL**: Surface a counterexample demonstrating that the unweighted mean (`np.mean(temp)`) is biased cold relative to the hand-computed area-weighted target
  - **Scoped PBT Approach**: The bug here is deterministic for a fixed field, so scope the property to concrete, analytically-known cases rather than random fields; use a pinned numpy RNG seed only for any grid-size parameterization
  - Create `tests/test_global_mean.py`. Build a synthetic two-band `tas(time, lat, lon)` field directly in the test on the 2-degree grid (latitude centres `-89..89`, longitude centres `1..359`), matching the grid in `make_sample.py`: constant `A` over an equatorial latitude band and constant `B < A` over the wider polar bands
  - Compute the target BY HAND from chosen constants and known latitudes: `target = (A*sum(w_warm) + B*sum(w_cold)) / (sum(w_warm) + sum(w_cold))`, where `w = cos(deg2rad(lat))` broadcast across lon/time. This value comes only from the chosen `A`, `B`, and the fixed latitude list - NOT from any production reduction and NOT from a re-implementation of the weighted mean (Bug Condition: `isBugCondition(X)` where `cov_over_lat(cos(deg2rad(lat)), zonalMean(tas, lat)) != 0`)
  - Assert the UNFIXED `global_mean` value on this field differs from `target` and lies below it (cold bias): `assert unfixed < target - margin`, with the margin justified in a comment by the band temperature gap and area ratio (not a floating-point tolerance)
  - Run the test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS when run as a fix-validation assertion `== target` (equivalently, the explicit bias assertion PASSES, documenting the counterexample) - this proves the cold bias
  - Document the counterexample in a comment (e.g. the concrete `A`, `B`, band latitudes, the unfixed value, and the hand-computed `target`)
  - Pin the numpy seed for any parameterization; no random temperature noise in this constructed field so the target stays analytically exact
  - Mark task complete when the test is written, run, and the counterexample/failure is documented
  - _Requirements: 1.1, 1.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Weight Identity And Constant-Field Baseline
  - **IMPORTANT**: Follow observation-first methodology - these tests must PASS on the UNFIXED code to establish the baseline to preserve
  - **Weight identity (bounds-based area, geometric basis of the weighting)**: Read `lat_bnds`/`lon_bnds` from `data/sample.nc` (produced by `make_sample.py`, pinned `SEED = 20261020`). For each cell compute the exact unit-sphere area `A = deg2rad(lon2 - lon1) * (sin(deg2rad(lat2)) - sin(deg2rad(lat1)))` and assert `sum_over_cells(A) == 4*pi`. Target `4*pi` is the analytic surface area of the unit sphere, known exactly; the sum telescopes in latitude to `2*pi*(sin(90deg) - sin(-90deg)) = 4*pi`. Use `math.isclose(total, 4*math.pi, rel_tol=1e-12, abs_tol=1e-12)`; tolerance `~1e-12` is justified because the only error is accumulated floating-point rounding over the telescoping `sin`-difference sum
  - **CONSISTENCY NOTE (keep distinct from task 3)**: This identity validates the bounds-based per-cell area formula - the geometric basis of the weighting. The fix's chosen weight is `cos(latitude)` at cell centres (a renormalized proxy for that area), so this test does NOT assert the code's center-based weights directly; it validates the area geometry those weights approximate. The renormalization the code actually performs is validated separately by the constant-field test (task 3.2)
  - **Constant-field baseline**: Build a `tas` field equal to a single chosen constant `C` at every `(time, lat, lon)` and record that the UNFIXED `np.mean` already returns `C`, establishing the preserved value. Assert `math.isclose(result, C, rel_tol=1e-12)`; tolerance `~1e-12` relative is justified because any mean of identical values is that value to a few ULP of accumulated rounding
  - **Property-based coverage**: Parameterize the constant-field test over several chosen constants `C` and grid sizes using a pinned numpy RNG seed; bound generated latitudes to `[-90, 90]`. Record the numpy and xarray versions (pinned in `requirements.txt`) in a test comment for reproducibility
  - Run the tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (the `4*pi` identity holds independent of the code, and the unfixed constant-field mean equals `C`) - this is the baseline to preserve
  - Mark task complete when the tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 3. Fix missing cos(latitude) area weighting in global_mean

  - [x] 3.1 Implement the area-weighted reduction
    - In `global_mean.py`, after opening the dataset and reading `tas`, read the `lat` coordinate (degrees)
    - Compute latitude weights `w = cos(deg2rad(lat))`, a 1-D array over the latitude dimension (proportional to cell area on a regular lat-lon grid; longitude and time cells share equal area so need no relative weighting)
    - Apply `w` along the latitude dimension and normalize by the total weight, e.g. `ds["tas"].weighted(w_da).mean(("time", "lat", "lon"))` with `w_da` a `lat`-broadcast DataArray, so each cell contributes in proportion to `w(lat)` and the result divides by `size(time) * size(lon) * sum(w)`
    - Return a Python `float`, as before
    - Make the smallest change that satisfies the requirements: do not alter `__main__`, the `tas` read, or the `Global-mean temperature: {value:.3f} K` output format; add no new configuration, framework, or abstraction
    - _Bug_Condition: isBugCondition(X) where cov_over_lat(cos(deg2rad(lat)), zonalMean(tas, lat)) != 0_
    - _Expected_Behavior: expectedBehavior(result) = cos(latitude)-area-weighted mean applied along latitude, normalized by sum of weights_
    - _Preservation: CLI contract, `tas` read, output format, and latitude-constant fields returning their common value_
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Latitude-Varying Field Returns Area-Weighted Mean
    - **IMPORTANT**: Re-run the SAME two-band test from task 1 - do NOT write a new test
    - Switch the assertion to the fix-validation form: `assert math.isclose(global_mean(field), target, rel_tol=1e-12)` against the hand-computed two-band `target`. This also exercises the renormalization the code performs (center-based `cos` weights divided by their sum), validating it against an analytically-known value - distinct from the `4*pi` bounds-based identity in task 2
    - Tolerance `~1e-12` relative is justified: the target is a short weighted sum of two constants divided by the weight total; error is only accumulated rounding
    - Run the exploration test from task 1 on the FIXED code
    - **EXPECTED OUTCOME**: Test PASSES (confirms the cold bias is removed and the area-weighted value matches the known target)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Weight Identity And Constant-Field Baseline
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Confirm the constant-field test still returns `C` to `~1e-12` relative on the FIXED code (validates the code's renormalization preserves a constant field exactly)
    - Confirm the `4*pi` bounds-based area identity still holds (it is independent of the fix; re-running guards against accidental edits to the test or data)
    - Add/confirm a CLI check: running `python global_mean.py data/sample.nc` prints one line matching `Global-mean temperature: <%.3f> K`
    - **EXPECTED OUTCOME**: Tests PASS (no regressions in constant-field behavior, the area identity, or the CLI/output format)
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 4. Checkpoint - Ensure all tests pass
  - Run the full suite with a single execution (`pytest --run` equivalent: `pytest` in `tests/`, no watch mode)
  - Confirm Property 1 (two-band area-weighted mean == hand-computed target) and Property 2 (constant field == `C`; cell areas == `4*pi`) all pass, and the CLI prints the expected format
  - Confirm no number reported in comments or summaries was hand-edited: every asserted value is either a chosen constant (`A`, `B`, `C`), the analytic `4*pi`, or recomputed by re-running `make_sample.py` / the test
  - Ensure all tests pass; ask the user if questions arise
