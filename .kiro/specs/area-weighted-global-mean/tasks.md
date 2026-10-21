# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Area-weighted mean of a latitude-varying field is cold-biased under equal weighting
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails** at this step
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface a counterexample that demonstrates the unweighted `np.mean` bias (equal weighting of unequal-area cells)
  - **Scoped PBT Approach**: For this deterministic bug, scope the property to concrete in-memory grids constructed so the area-weighted mean has a known closed form
  - Create `tests/test_global_mean.py`. Build a small in-memory dataset (xarray) with `tas(time, lat, lon)` and matching `lat_bnds`/`lon_bnds` (centre ± half-step) on a grid that tiles the sphere (lat spanning -90..90, lon spanning 0..360). Construct `tas` so the exact area-weighted, time-averaged mean equals a chosen known constant `c` — e.g. set every grid point to `c` is uniform (not a bug input); instead use a latitude-varying field whose bounds-based area-weighted mean is analytically `c`. The simplest analytic construction: choose `tas(lat) = a + b * s(lat)` where `s(lat) = sin(lat_upper)+sin(lat_lower)` is proportional to the weighted centroid contribution, OR more directly assert the known value using the area-weighting identity. If a closed form is awkward, assert the weaker-but-exact fact that the area-weighted mean of the constructed field equals its analytic value `V` while `np.mean` does not — the test asserts only the analytic `V`, never an output of our own weighting code.
  - **Assertion rule (lab correctness)**: assert against an analytically known value only (the chosen `V`/`c`), with `rtol ~1e-12`. Do NOT compare `global_mean` output to a re-implementation of the weighting, and do NOT compare F against F'.
  - Run on UNFIXED code: `uv run pytest tests/test_global_mean.py -k bug_condition -q`
  - **EXPECTED OUTCOME**: Test FAILS (unweighted `np.mean` returns a value departing from the analytic `V`, confirming the cold-bias bug)
  - Document the counterexample found (record the analytic `V`, the value F returns, and the gap) as a comment in the test
  - **Acceptance check**: `uv run pytest tests/test_global_mean.py -k bug_condition -q` runs and FAILS with the documented counterexample
  - _Requirements: 1.1, 1.2, 2.1, 2.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Cell areas from `lat_bnds`/`lon_bnds` sum to 4π
  - **IMPORTANT**: Follow observation-first methodology — these tests assert analytic truths that hold on UNFIXED code because they test grid geometry (a helper/computation in the test), plus the I/O contract of the unchanged `global_mean`
  - Add to `tests/test_global_mean.py` a property-based test (use `hypothesis` if available in the pinned env; otherwise a loop over several generated grids) that builds `lat_bnds`/`lon_bnds` tiling the sphere (latitude edges strictly increasing from -90 to 90, longitude edges from 0 to 360) and computes cell areas `(sin(lat_upper) - sin(lat_lower)) * (lon_upper_rad - lon_lower_rad)` via the outer product. Assert `sum(areas) == 4*pi`.
  - **Assertion rule (lab correctness)**: `4π` is known from geometry, independent of `global_mean`; assert with `atol`/`rtol ~1e-12`. Justification: latitude terms telescope to `sin(90°)-sin(-90°)=2` and longitude spans cover `2π`, so a correct area array sums to `4π` up to bounded float rounding.
  - Also assert the preserved I/O contract on the real sample file: `global_mean("data/sample.nc")` returns a Python `float` (type check only at this stage; value correctness comes from Property 1 after the fix). **Record/verify the sample checksum** at the top of the file as a comment: `data/sample.nc` SHA-256 = `766614bd7cd884d131aec35a7eab0b930690789823e9f6f80232ad52a14c5ad6`. Verify with `shasum -a 256 data/sample.nc` and re-run if it differs.
  - Run on UNFIXED code: `uv run pytest tests/test_global_mean.py -k preservation -q`
  - **EXPECTED OUTCOME**: Tests PASS (geometry and return-type contract hold before the fix)
  - **Acceptance check**: `uv run pytest tests/test_global_mean.py -k preservation -q` runs and PASSES
  - _Requirements: 2.1, 3.2, 3.3_

- [x] 3. Fix global_mean to return the area-weighted, time-averaged mean

  - [x] 3.1 Implement the fix in the body of `global_mean`
    - Read `lat_bnds` and `lon_bnds` (shape `(lat, 2)`, `(lon, 2)`) alongside `tas` after `xr.open_dataset(path)`
    - Convert bounds to radians; compute `dsin_lat = sin(lat_upper) - sin(lat_lower)` `(lat,)` and `dlon = lon_upper - lon_lower` `(lon,)`; form cell areas `area = dsin_lat[:, None] * dlon[None, :]` `(lat, lon)`
    - Broadcast `area` over `time` and return `float(sum(temp * w) / sum(w))` — area-weighted spatial mean, averaged over time, as a single Python `float`
    - Keep `xr.open_dataset`, the `tas` read, and the `__main__` CLI untouched. Change confined to the body of `global_mean`; no new modules, frameworks, or abstractions
    - _Bug_Condition: isBugCondition(X) = (NOT spatially_uniform(X.tas)) AND (cellArea(X.lat_bnds, X.lon_bnds) not constant) — from design_
    - _Expected_Behavior: expectedBehavior = area-weighted, time-averaged mean using bounds-based cell areas; `return float(sum(temp*w)/sum(w))` — from design Fix Implementation_
    - _Preservation: reads `tas` via xarray, averages over time, returns one Python `float`, returns `c` exactly for a uniform field — from design Preservation Requirements_
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Area-weighted mean returns the analytic value
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior (assertion against the analytic `V`/`c`, `rtol ~1e-12`)
    - **Acceptance check**: `uv run pytest tests/test_global_mean.py -k bug_condition -q` PASSES (confirms the bug is fixed)
    - _Requirements: 2.1, 2.2, 3.1_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Cell areas sum to 4π; I/O contract unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - **Acceptance check**: `uv run pytest tests/test_global_mean.py -k preservation -q` PASSES (no regressions)
    - _Requirements: 2.1, 3.2, 3.3_

- [x] 4. Checkpoint - Ensure all tests pass
  - Re-verify the sample checksum: `shasum -a 256 data/sample.nc` equals `766614bd7cd884d131aec35a7eab0b930690789823e9f6f80232ad52a14c5ad6`
  - Run the full suite and confirm Property 1 and Property 2 both pass and the integration smoke check returns a finite Python `float`
  - **Acceptance check**: `uv run pytest -q` passes; ask the user if any questions arise
  - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3_
