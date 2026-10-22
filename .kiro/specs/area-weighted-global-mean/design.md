# Area-Weighted Global Mean Bugfix Design

## Overview

`global_mean.py` reports a global-mean near-surface temperature (`tas`, dims `(time, lat, lon)`) that is biased cold. `global_mean()` computes `float(np.mean(temp))`, weighting every grid cell equally. On a regular latitude-longitude grid, grid-cell surface area shrinks toward the poles, so equal weighting over-counts the cold polar cells and under-counts the warm tropical cells — a systematic cold bias.

The fix replaces the unweighted mean with an area-weighted mean. Rather than the point proxy `cos(latitude)`, the fix uses **true spherical cell areas** computed from the dataset's `lat_bnds` / `lon_bnds`. On the unit sphere a cell spanning `[lat_lo, lat_hi] x [lon_lo, lon_hi]` has area

```
area = (sin(lat_hi_rad) - sin(lat_lo_rad)) * (lon_hi_rad - lon_lo_rad)
```

The reported value is `tas` averaged over `time`, then collapsed over space with these area weights: `sum(area * tas) / sum(area)`.

This realizes the intent of the requirements (an area-weighted mean that removes the cold bias, clauses 2.1-2.2) more accurately than the `cos(latitude)` point proxy named in requirement 2.1. The exact-integral cell area is the correct surface-area weight; the point `cos(lat)` value is the first-order approximation to it. Because the verified dataset carries `lat_bnds` and `lon_bnds`, the fix uses the exact areas. In the limit of fine latitude spacing the two agree, and both satisfy every preservation requirement (3.1-3.4), which depend only on the weights being positive and — for 3.2 — equal when the grid makes them equal.

## Glossary

- **Bug_Condition (C)**: The input condition under which the reported mean is wrong — the per-cell area weights are not all equal AND `tas` varies across latitude, so the unweighted mean is biased relative to the area-weighted mean.
- **Property (P)**: The desired behavior — the reported value equals the area-weighted mean of the time-averaged field, `sum(area * tas_tmean) / sum(area)`.
- **Preservation**: Behaviors that must not change — results for spatially uniform fields, for equal-area/equal-weight grids, the read/time-average/return-`float` contract, and the script print format.
- **Cell area (unit sphere)**: For a cell bounded by latitudes `lat_lo < lat_hi` and longitudes `lon_lo < lon_hi` (all in radians), `area = (sin(lat_hi) - sin(lat_lo)) * (lon_hi - lon_lo)`. Summed over a full, non-overlapping tiling of the sphere, these areas total `4*pi`.
- **`global_mean`**: The function in `global_mean.py` that opens the NetCDF file at `path`, reads `tas`, and returns a single global-mean temperature as a Python `float`.
- **`lat_bnds` / `lon_bnds`**: CF-convention cell-edge arrays carried by the dataset, shapes `(lat, 2)` and `(lon, 2)`, giving the lower and upper edge of each cell. Verified present in `data/sample.nc` (`lat` has attr `bounds="lat_bnds"`).
- **F / F'**: The original (unweighted) and fixed (area-weighted) `global_mean`.

## Bug Details

### Bug Condition

The bug manifests whenever the grid's per-cell areas are not all equal and the temperature field varies with latitude. In that case `float(np.mean(temp))` weights each cell equally, over-weighting the small, cold polar cells and under-weighting the large, warm tropical cells, so the reported mean is biased cold relative to the true area-weighted mean.

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT:  X with tas(time, lat, lon), and cell edges lat_bnds, lon_bnds
  OUTPUT: boolean

  areas := cellAreas(X.lat_bnds, X.lon_bnds)   // true unit-sphere areas per (lat, lon)
  RETURN (areas are NOT all equal)
         AND (X.tas varies across latitude)
END FUNCTION
```

### Examples

- **Realistic gradient (buggy)**: `data/sample.nc` has `tas ~ 300 - 50 sin^2(lat) + ...` on a 2-degree grid (`lat` centres -89..89, `lon` centres 1..359). Cell areas fall off toward the poles, and `tas` is coldest there. Expected: the area-weighted mean is warmer than `float(np.mean(temp))`. Actual (F): returns the colder unweighted mean.
- **Single mid-latitude band, varying field (buggy)**: a field that increases with latitude across cells of differing area. Expected: area-weighted mean. Actual (F): equal-weight mean, biased toward the larger-count latitudes.
- **Spatially uniform field (not buggy)**: every cell equals `T0` at each time. Expected and actual both return `T0` — no bug, must be preserved.
- **Equal-area grid / single latitude row (not buggy, edge case)**: all cells share one area, so weighted mean reduces to the arithmetic mean. Expected and actual agree — must be preserved.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- A spatially uniform field (all cells equal at a given time) still returns that value — the weighted mean of a constant equals the constant for any positive weights (requirement 3.1).
- A grid whose cells all have equal area (e.g. a single latitude row) still returns the arithmetic mean — equal weights reduce the weighted mean to the unweighted mean (requirement 3.2).
- The function still reads `tas` from the NetCDF file at `path`, averages over `time` as well as space, and returns a single Python `float` (requirement 3.3).
- Run as a script with a path argument, the module still prints `Global-mean temperature: {value:.3f} K` (requirement 3.4).

**Scope:**
Any input where `isBugCondition` is false — uniform fields and equal-area grids — must produce exactly the same result as the original code (to floating-point rounding). The read/time-average/return contract and the script output format are unchanged for all inputs.

## Hypothesized Root Cause

The defect is not a subtle logic error; it is a missing weighting step. The most likely contributing factors:

1. **Equal weighting of unequal-area cells**: `float(np.mean(temp))` treats the `(time, lat, lon)` array as a flat set of equally weighted samples. On a lat-lon grid, cell area varies with latitude, so this is wrong whenever `tas` varies with latitude.
2. **Surface-area information ignored**: the dataset carries exact cell edges (`lat_bnds`, `lon_bnds`) that make true cell areas computable, but the function never reads them.
3. **No separation of time vs. space collapse**: collapsing all axes at once with one `np.mean` leaves no place to apply spatial weights; time and space need distinct treatment (unweighted over time, area-weighted over space).

## Correctness Properties

Property 1: Bug Condition - Area-Weighted Mean Removes the Cold Bias

_For any_ input where the bug condition holds (`isBugCondition` returns true), the fixed `global_mean` SHALL return the area-weighted mean of the time-averaged field, `sum(area * tas_tmean) / sum(area)`, where `area` is the true unit-sphere cell area from `lat_bnds`/`lon_bnds` and `tas_tmean` is `tas` averaged over `time`. For a field with a cold-pole/warm-tropic gradient this value SHALL be warmer than the original unweighted mean.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - Uniform Fields and Equal-Area Grids Unchanged

_For any_ input where the bug condition does NOT hold (`isBugCondition` returns false) — a spatially uniform field, or a grid whose cells all have equal area — the fixed `global_mean` SHALL produce the same result as the original function (to floating-point rounding), preserving the uniform-field value (3.1) and the equal-area arithmetic mean (3.2), as well as the read/time-average/return-`float` contract (3.3) and the script print format (3.4).

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

Assuming the root-cause analysis is correct:

**File**: `global_mean.py`

**Function**: `global_mean`

**Specific Changes**:
1. **Read cell edges**: after opening the dataset, read `lat_bnds` and `lon_bnds` (shapes `(lat, 2)` and `(lon, 2)`).
2. **Compute true cell areas**: convert edges to radians; per-latitude band weight `d_sin = sin(lat_hi) - sin(lat_lo)`; per-longitude width `d_lon = lon_hi - lon_lo`; cell area `area[i, j] = d_sin[i] * d_lon[j]` as an outer product, shape `(lat, lon)`.
3. **Average over time first**: `tas_tmean = tas.mean(axis=time)` → shape `(lat, lon)`, matching the preservation contract (time is averaged unweighted, 3.3).
4. **Apply the area-weighted spatial mean**: `result = sum(area * tas_tmean) / sum(area)`, returned as a Python `float`.
5. **Keep the contract and script format**: still read `tas` from `path`, return a single `float`, and leave the `__main__` print line `Global-mean temperature: {value:.3f} K` unchanged.

Keep the change minimal (workspace scope rules): edit `global_mean()` and add tests only — no new frameworks, no configuration system, no new abstractions.

## Testing Strategy

### Validation Approach

Two phases: first surface counterexamples that demonstrate the bug on the unfixed code, then verify the fix is correct and preserves existing behavior. Honoring the workspace research rules, every numerical assertion targets a value known **analytically or exactly** (not a second run of our own code), states its tolerance, and justifies it. All Python runs through `uv run` (`uv run pytest ...`), never `python`/`python3`/`.venv/bin/python` directly. Synthetic datasets with known bounds are constructed in the tests so expected values are known exactly; `data/sample.nc` is used only for the directional (bias-sign) check, whose expected sign is known analytically from the field definition.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the cold bias BEFORE the fix, and confirm the root cause (missing area weighting). If refuted, re-hypothesize.

**Test Plan**: On the UNFIXED code, compare `global_mean("data/sample.nc")` against an independently computed area-weighted mean. Because the sample field is coldest at the poles (where cells are smallest), the area-weighted mean is analytically known to be **warmer**; the unweighted result must come out lower. Observe the failure direction to confirm the bug.

**Test Cases**:
1. **Cold-bias direction on sample.nc**: assert the unfixed `global_mean` is strictly less than the area-weighted mean (will fail on unfixed code — i.e. the inequality the fix must satisfy does not yet hold). Expected sign is analytic: smaller weights on the coldest cells raise the mean.
2. **Synthetic latitude gradient**: a field rising monotonically with latitude on a coarse grid with strongly unequal cell areas; the unfixed mean differs from the known area-weighted mean (will fail on unfixed code).
3. **Edge — single latitude row**: on a one-row grid (equal areas) the unfixed mean already equals the area-weighted mean (will NOT fail; documents the preservation boundary).

**Expected Counterexamples**:
- The unweighted mean is colder than the area-weighted mean on any cold-pole/warm-tropic field.
- Cause: equal weighting of unequal-area cells; the exact cell areas from `lat_bnds`/`lon_bnds` are ignored.

### Fix Checking

**Goal**: For all inputs where the bug condition holds, the fixed function produces the area-weighted mean.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := global_mean_fixed(input)
  ASSERT result == weightedMean(timeMean(input.tas), weights = cellAreas(input))
END FOR
```

Grounded in exactly known values:

- **Area sum equals 4*pi**: cell areas computed from `lat_bnds`/`lon_bnds` over a full non-overlapping sphere tiling SUM TO `4*pi` (unit-sphere surface area). Assert `sum(area)` equals `4*pi`.
  - **Tolerance**: `abs(sum(area) - 4*pi) <= atol` with `atol = 1e-9` (equivalently `rtol ~ 1e-10` against `4*pi ~ 12.566`). Justification: the sum accumulates ~16200 cell areas (90 lat x 180 lon) each formed from differences of `sin` and of longitudes; rounding is on the order of `eps * 4*pi * sqrt(N) ~ 2.2e-16 * 12.57 * 127 ~ 3.6e-13`. The `1e-9` bound sits well above worst-case accumulated rounding yet far below any structurally meaningful error, so it is exact-or-wrong, not approximately right.
- **Constant field returns the constant exactly**: on a synthetic dataset whose `tas` is a single constant `T0` everywhere (any grid with known bounds), the weighted mean equals `T0` for any positive weights.
  - **Tolerance**: `abs(result - T0) <= 1e-12` (near machine epsilon scaled by `T0 ~ 300`: `eps * 300 ~ 6.7e-14`). Justification: the only arithmetic is `sum(area*T0)/sum(area) = T0`, a handful of rounding steps; `1e-12` is comfortably above that and far below any real deviation.
- **Known-area weighted mean**: on a small synthetic grid whose cell areas and `tas` values are chosen so the weighted mean has a closed-form value, assert the fixed function returns that value.
  - **Tolerance**: `rtol = 1e-12`. Justification: a short exact arithmetic expression; `1e-12` tracks accumulated double-precision rounding over a few operations.

### Preservation Checking

**Goal**: For all inputs where the bug condition does NOT hold, the fixed function returns the same result as the original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT global_mean_original(input) == global_mean_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing fits preservation because it samples many inputs across the domain and catches edge cases manual cases miss. Here the preservation classes are narrow and have exactly known targets, so they are expressed as constructed cases with analytic expected values (not a second run of our own code sharing a possible mistake). Where a property-style generator is used, the asserted target is still the analytic arithmetic mean, not another code path.

**Test Cases**:
1. **Uniform field (3.1)**: synthetic dataset, `tas = T0` everywhere across all times; assert `result == T0` exactly (tolerance `1e-12`, justified as above). The arithmetic mean is also `T0`, so original and fixed agree by construction.
2. **Equal-area grid / single latitude row (3.2)**: synthetic one-row grid (all cells equal area); assert `result` equals the plain arithmetic mean of the (known) values. Tolerance `rtol = 1e-12`, justified as short-chain double-precision rounding. Equal weights make the weighted and arithmetic means identical analytically.
3. **Contract and format (3.3, 3.4)**: assert `global_mean(path)` returns a Python `float` and that the time axis is averaged (result independent of time ordering for a time-symmetric constructed field); assert the script prints `Global-mean temperature: {value:.3f} K`. These are structural, not numerical, assertions.

### Unit Tests

- Cell-area helper: area sum equals `4*pi` on the full grid (tolerance `1e-9`, justified above).
- Constant-field dataset returns the constant exactly (tolerance `1e-12`).
- Small known-area grid returns the closed-form weighted mean (tolerance `rtol 1e-12`).
- Return type is `float`; script output matches the required format string.

### Property-Based Tests

- Generate constant fields with random `T0` and random (valid, increasing) bounds; assert the result equals `T0` (tolerance `1e-12`) — exercises Property 2 preservation across many grids with an exactly known target.
- Generate single-latitude-row grids with random values; assert the result equals the analytic arithmetic mean of those values (tolerance `rtol 1e-12`) — Property 2 equal-area case.
- Generate full-sphere grids with random (monotonic) latitude edges; assert the computed cell-area sum equals `4*pi` (tolerance `1e-9`) — anchors Property 1's weighting against an exact total.

### Integration Tests

- End-to-end on `data/sample.nc`: assert the fixed `global_mean` is strictly greater than the original unweighted mean (analytic cold-bias direction), and that it lies within the min/max of the field (a necessary bound for any weighted mean with positive weights).
- Script invocation via `uv run python global_mean.py data/sample.nc` produces one line matching `Global-mean temperature: {value:.3f} K`.
- Reproducibility: tests that read `data/sample.nc` pin to the committed file produced by `make_sample.py` (fixed `SEED = 20261020`); synthetic in-test datasets are built deterministically so expected values stay exact across runs.
