# Global-Mean Area Weighting Bugfix Design

## Overview

`global_mean.py` reports the global-mean near-surface temperature by taking an unweighted arithmetic mean (`np.mean(temp)`) over every `(time, lat, lon)` grid point. On a regular latitude-longitude grid cells do not cover equal area: a cell's surface area is proportional to `cos(latitude)`, so the many small, cold polar cells are over-counted and the result is biased cold relative to the true global mean.

The fix computes an area-weighted mean, weighting each cell by `cos(latitude)` and applying that weight along the latitude dimension. The change is confined to the reduction inside `global_mean()`; the CLI, the variable read (`tas`), and the `Global-mean temperature: {value:.3f} K` output format are preserved.

The validation approach deliberately avoids comparing the fixed code to a re-derivation of itself or comparing the original function `F` against the fixed function `F'`. Instead it pins the fix to two values known analytically: a constant field must return that exact constant, and the cell areas used as weights must sum to the surface area of the unit sphere, `4*pi`.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — the field varies with latitude across cells carrying different `cos(latitude)` weight, so the unweighted and area-weighted means differ.
- **Property (P)**: The desired behaviour — the reduction weights each cell by its surface area (`cos(latitude)`), yielding the area-weighted global mean.
- **Preservation**: Behaviour that must remain unchanged — the CLI contract, the `tas` read, the output format, and the fact that a latitude-constant field returns its common value.
- **global_mean**: The function in `global_mean.py` that opens the dataset, reads `tas`, and reduces it to a single global-mean temperature.
- **lat / lat_bnds**: The latitude coordinate (degrees north) and its CF cell bounds in `data/sample.nc`; `lat_bnds[i] = [lat[i]-1, lat[i]+1]` for the 2-degree grid.
- **F / F'**: The original (unweighted) and fixed (area-weighted) `global_mean`.

## Bug Details

### Bug Condition

The bug manifests when the temperature field varies with latitude over a grid whose cells carry different `cos(latitude)` area weight. In that case `np.mean(temp)` assigns every cell equal weight, over-representing the smaller polar cells and producing a mean biased cold relative to the area-weighted global mean.

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT:  X with field tas(time, lat, lon) and latitude coordinate lat (degrees)
  OUTPUT: boolean

  // The unweighted and area-weighted means differ only when the field varies
  // with latitude AND the grid spans latitudes of differing cos(latitude) weight.
  RETURN cov_over_lat( cos(deg2rad(lat)), zonalMean(tas, lat) ) <> 0
END FUNCTION
```

### Examples

- Sample field `data/sample.nc` (`T ≈ 300 - 50 sin^2(lat) + ...`): expected the area-weighted global mean; actually a lower value because cold polar cells are over-counted.
- Two-band field: constant `A` over a warm equatorial band and constant `B < A` over a wider cold polar band — expected a value pulled toward `A` by area weighting; actually a value pulled toward `B` by cell count.
- A field that is uniform across latitude (constant `C`): expected `C`; the unweighted mean already returns `C`, so this input does NOT trigger the bug.
- Edge case: a single-latitude grid — expected unchanged (no latitude variation to re-weight); does NOT trigger the bug.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Invocation from the command line with a path argument, or the default `data/sample.nc`, continues to read the `tas` variable and print `Global-mean temperature: {value:.3f} K`.
- A field that is constant across latitude (including a field constant everywhere) continues to return that common value — any area weighting of equal values is that value.
- Averaging across longitude and time continues to use equal weight, since cells at a fixed latitude share equal area and the weighting applies only across latitude.

**Scope:**
All inputs that do NOT satisfy the bug condition should be completely unaffected in observable value by this fix. This includes:
- Latitude-constant temperature fields (result stays at the common value).
- The CLI contract (argument handling, default path, output string).
- The longitude and time reductions (still equal-weighted).

## Hypothesized Root Cause

Based on the bug description, the cause is:

1. **Missing area weighting in the reduction**: `global_mean()` reduces with `np.mean(temp)`, which assigns every `(lat, lon)` cell the same weight.
   - No `cos(latitude)` factor is applied along the latitude dimension.
   - Polar cells (smaller physical area) therefore carry the same weight as equatorial cells.

2. **Grid geometry ignored**: The latitude coordinate (and the CF `lat_bnds` describing each cell's extent) is available in the dataset but is never used to derive weights.

3. **No contribution normalisation by weight total**: Even if per-cell values were scaled, the result must be divided by the sum of weights (not the cell count) to remain a mean.

## Correctness Properties

Property 1: Bug Condition - Constant field returns the constant exactly

_For any_ `tas` field that is a single constant `C` at every `(time, lat, lon)` (an input on the boundary of the bug condition, where any valid weighting must agree), the fixed `global_mean` SHALL return exactly `C` to floating-point rounding, because an area-weighted mean of identical values is a convex combination equal to that value. This is checked against the known constant `C`, not against a re-implementation of the weighting.

**Validates: Requirements 2.1, 3.1**

Property 2: Preservation - Cell areas sum to the unit sphere

_For any_ full global grid defined by `lat_bnds`/`lon_bnds`, the area weights the fix relies on SHALL satisfy `sum_over_cells( A ) == 4*pi` to floating-point rounding, where `A = deg2rad(lon2-lon1) * (sin(deg2rad(lat2)) - sin(deg2rad(lat1)))`. The sum telescopes in latitude to `2*pi * (sin(90deg) - sin(-90deg)) = 4*pi`, the analytic surface area of the unit sphere. This validates the weights independent of the temperature field and does not compare the code to itself.

**Validates: Requirements 2.1, 2.2**

## Fix Implementation

### Changes Required

Assuming the root cause analysis is correct:

**File**: `global_mean.py`

**Function**: `global_mean`

**Specific Changes**:
1. **Read the latitude coordinate**: After opening the dataset, obtain the `lat` values (degrees) alongside `tas`.
2. **Compute latitude weights**: `w = cos(deg2rad(lat))`, a 1-D array over the latitude dimension. (`cos(latitude)` is proportional to cell area on a regular lat-lon grid, so it is sufficient along latitude; longitude and time cells share equal area.)
3. **Apply the weights along latitude**: Reduce `tas` so each cell contributes in proportion to `w(lat)` — e.g. weight each latitude row, sum over all cells, and divide by `size(time) * size(lon) * sum(w)`. Using `xarray`'s `weighted(...).mean(...)` over `("time", "lat", "lon")` with a `lat`-broadcast weight achieves this with a minimal change and avoids a hand-rolled normalisation.
4. **Keep the return contract**: Return a Python `float`, as before.
5. **Preserve the CLI and output**: Leave `__main__` and the `Global-mean temperature: {value:.3f} K` format untouched.

The change is the smallest that satisfies the requirements: it adds `cos(latitude)` weighting to the existing reduction and changes nothing else. No new configuration, framework, or abstraction is introduced.

## Testing Strategy

### Validation Approach

Every assertion compares the fixed code to a value known exactly or analytically — never to a second implementation of the same calculation and never `F` against `F'`. The strategy first surfaces the bug on the unfixed code, then pins the fix to two analytic truths: the constant-field value and the `4*pi` area identity. All tests run against `data/sample.nc`, produced deterministically by `make_sample.py` (pinned `SEED = 20261020`), with package versions pinned in `requirements.txt`.

### Exploratory Bug Condition Checking

**Goal**: Surface a counterexample that demonstrates the cold bias BEFORE implementing the fix, and confirm the root cause (missing `cos(latitude)` weighting). If refuted, re-hypothesise.

**Test Plan**: On the UNFIXED code, construct a field whose area-weighted mean is known by hand and show the reported value differs from it in the cold direction. The two-band field gives an exactly computable target: with constant `A` over an equatorial band and `B < A` over a wider polar band, the area-weighted mean is `(A * sum(w_warm) + B * sum(w_cold)) / (sum(w_warm) + sum(w_cold))` using `w = cos(deg2rad(lat))` — a value derived purely from chosen band temperatures and the known latitudes, not from the production reduction.

**Test Cases**:
1. **Two-band field**: Unweighted mean is pulled toward `B` by cell count; it will differ from the hand-computed area-weighted target (fails on unfixed code).
2. **Sample field cold bias**: The unfixed value sits below the area-weighted result (observable bias on unfixed code).
3. **Edge — latitude-constant field**: Unweighted mean already equals the constant, so no counterexample here (confirms this input is outside the bug condition).

**Expected Counterexamples**:
- The unfixed reported value does not match the analytically known two-band area-weighted mean, and is biased cold.
- Cause: the reduction applies no `cos(latitude)` weight along latitude.

### Fix Checking

**Goal**: Verify that where the bug condition holds, the fixed function produces the expected behaviour, asserted against values known exactly or analytically — not against a re-derivation of the weighted mean.

**Pseudocode:**
```
// Constant field: known target C, exact to rounding
FOR a tas field that is the constant C at every (time, lat, lon) DO
  result := global_mean_fixed(field)
  ASSERT result == C          // tol ~1e-12 relative
END FOR

// Weight identity: known target 4*pi, exact to rounding
FOR the full global grid from lat_bnds, lon_bnds DO
  A(cell) := deg2rad(lon2 - lon1) * (sin(deg2rad(lat2)) - sin(deg2rad(lat1)))
  ASSERT sum_over_cells(A) == 4*pi   // tol ~1e-12 absolute/relative
END FOR
```

**Tolerances and justification**:
- Constant field: `~1e-12` relative. The result is a weighted sum of equal values divided by the total weight; the only error is a few ULP of accumulated rounding, so the value is exact to floating-point rounding.
- Area identity: `~1e-12` absolute/relative. The sum telescopes to exact `sin` differences `2*pi*(sin(90deg) - sin(-90deg)) = 4*pi`; error is only accumulated rounding over the grid.

### Preservation Checking

**Goal**: Verify that behaviour outside the bug condition is unchanged, using known truths rather than a direct `F` vs `F'` comparison.

**Pseudocode:**
```
// Latitude-constant field preserves the common value (known target C)
FOR a tas field constant across latitude with common value C DO
  ASSERT global_mean_fixed(field) == C   // tol ~1e-12 relative
END FOR

// CLI contract preserved
RUN: python global_mean.py data/sample.nc
ASSERT stdout matches "Global-mean temperature: <float formatted %.3f> K"
```

**Testing Approach**: The constant-field check is the strongest preservation guarantee that can be stated against a known value: a latitude-constant field must return its common value under any correct weighting, so asserting `== C` both confirms the fix and preserves prior behaviour without comparing two implementations. Property-based generation over the constant `C` and over grid sizes broadens coverage of the constant-field invariant.

**Test Cases**:
1. **Constant-field preservation**: A field constant everywhere returns exactly that constant (known `C`, tol `~1e-12`).
2. **Latitude-constant preservation**: A field constant across latitude but varying in longitude/time still returns the common latitude value.
3. **CLI/format preservation**: Running the script prints the result in the `Global-mean temperature: {value:.3f} K` format.

### Unit Tests

- Constant field returns the constant `C` exactly (tol `~1e-12` relative).
- Cell areas from `lat_bnds`/`lon_bnds` sum to `4*pi` (tol `~1e-12`).
- Two-band field matches the hand-computed area-weighted target (tol stated with the test; dominated by rounding of a short sum).
- CLI prints the expected output format for `data/sample.nc`.

### Property-Based Tests

- For a randomly chosen constant `C` and random grid size, the fixed mean equals `C` to `~1e-12` relative.
- For random full global 2-degree-style grids, the cell-area sum equals `4*pi` to `~1e-12`.
- Seeds pinned; generators bounded to valid latitudes in `[-90, 90]`.

### Integration Tests

- End-to-end run on `data/sample.nc` produces a single `Global-mean temperature: ... K` line, and the printed value is consistent with the constant-field and area identities (not asserted against a second reduction).
- Default-path invocation (no argument) behaves identically to passing `data/sample.nc`.
