# Area-Weighted Global Mean Bugfix Design

## Overview

`global_mean.py` reports the global-mean near-surface temperature (`tas`) from a NetCDF file on a regular latitude-longitude grid. The current implementation, `float(np.mean(temp))`, averages every grid cell with equal weight. On a regular lat-lon grid, polar cells span the same number of degrees as equatorial cells but cover far less physical surface area, so equal weighting over-represents the small, cold polar cells and biases the reported mean cold.

The fix replaces the uniform mean (`F`) with an area-weighted mean (`F'`) in which each cell is weighted by the cosine of its latitude. On a regular lat-lon grid, a cell's true surface area is proportional to the cosine of its latitude (to the degree the requirements call for), so cosine weighting makes each cell contribute in proportion to its area. The weight depends only on latitude, so it broadcasts across longitude and time.

The change is deliberately minimal: it alters only the aggregation inside `global_mean`, leaving the function signature, path resolution, return type, and print format untouched. Correctness is pinned to two analytic identities from the requirements — a constant field averages to that constant, and per-cell areas derived from the CF bounds sum to `4*pi` steradians on the unit sphere — never by comparing the new output to the old uniform output.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — the global mean is computed over a grid whose cell latitudes are not all identical, so uniform averaging misweights cells relative to their surface area.
- **Property (P)**: The desired behaviour — each cell contributes in proportion to its true surface area, realised by weighting each cell by the cosine of its latitude.
- **Preservation**: The function's interface and the single-latitude-band result that must remain unchanged by the fix — the `tas` variable read, CLI path resolution, the Python `float` return, the print format, and the reduction to a plain mean when all latitudes are identical.
- **global_mean**: The function in `global_mean.py` that opens the dataset, reads `ds["tas"].values` with dims `(time, lat, lon)`, and currently returns `float(np.mean(temp))`.
- **cos(lat) weight**: The per-cell weight `cos(deg2rad(lat))`, a function of latitude only, broadcast across longitude and time.
- **lat_bnds / lon_bnds**: CF-convention cell-edge arrays written by `make_sample.py`, each `(lat, nv)` / `(lon, nv)` with the lower and upper edge of every cell in degrees. Used by the area-closure identity, not by the weighting in the mean.
- **F**: The original (unfixed) function, `float(np.mean(temp))`.
- **F'**: The fixed function, an area-weighted mean using cos(lat) weights.

## Bug Details

### Bug Condition

The bug manifests when the global mean is computed over a lat-lon grid whose cell latitudes are not all identical. `global_mean` collapses the `(time, lat, lon)` array with `np.mean`, which assigns every cell the same weight `1/N`. Because the physical area of a cell on a regular lat-lon grid falls off with the cosine of its latitude, equal weighting over-represents high-latitude cells relative to their area, and the returned mean is biased cold.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type Dataset with variable tas over dims (time, lat, lon)
  OUTPUT: boolean

  RETURN NOT allEqual(input.lat)          // more than one distinct latitude
         AND cellsWeightedUniformly(input) // aggregation ignores cos(lat)
END FUNCTION
```

When `isBugCondition` holds, `F` returns a value that is cold-biased relative to the true area-weighted mean; the magnitude of the bias grows with the latitudinal temperature contrast and the span of latitudes.

### Examples

- **Sample grid (`data/sample.nc`)**: latitudes run from -89 to 89 in 2-degree steps with a warm-tropics/cold-poles field. `F` = `np.mean` over-weights the cold polar bands and returns a mean below the true area-weighted mean. Expected: `F'` weights each cell by `cos(lat)`, pulling the result toward the warmer, larger-area tropical cells.
- **Constant field C over the whole grid**: Expected `F'` returns `C` exactly (within 1e-9 K), because a weighted mean of identical values is a convex combination of `C`. `F` also returns `C` here — this input is *not* in the bug condition and must be preserved.
- **Single latitude band (all cells share one latitude)**: `cos(lat)` is one common constant, so the weighted mean reduces to the plain mean. Expected `F'` equals `F`. Not in the bug condition; preserved per 3.1.
- **Area closure (edge case, derived from bounds)**: per-cell areas computed from `lat_bnds`/`lon_bnds` over the full sphere sum to `4*pi` steradians (within relative tolerance 1e-12). This is an analytic anchor on the area derivation, independent of any temperature field.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- The function continues to read the `tas` variable from the dataset and operate on that same field (3.2).
- The CLI path argument is resolved exactly as before — first positional argument, defaulting to `data/sample.nc` when omitted (3.3).
- The function continues to return a Python `float`, and the `__main__` block continues to print `"Global-mean temperature: {value:.3f} K"` (3.4).
- When every cell shares the same latitude (a single latitude band), the result continues to equal the plain unweighted mean, because cosine weighting applies one common weight that cancels in normalisation (3.1).

**Scope:**
All inputs that do NOT fall under the bug condition should be unaffected by this fix. This includes:
- A constant temperature field (the mean stays equal to the constant, within 1e-9 K).
- A single-latitude-band grid (the result stays equal to the plain mean).
- The script's external interface: variable read, path resolution, return type, and print format.

**Note:** The expected correct behaviour for buggy inputs is defined in the Correctness Properties section (Property 1). This section records what must NOT change.

## Hypothesized Root Cause

Based on the bug description and a reading of `global_mean.py`, the cause is singular and well understood:

1. **Uniform weighting in the aggregation**: `global_mean` returns `float(np.mean(temp))`. `np.mean` assigns every element weight `1/N` regardless of latitude, so cells are averaged by count rather than by surface area.
   - On a regular lat-lon grid, cell area is proportional to `cos(lat)`, which `np.mean` ignores entirely.
   - With a warm-tropics/cold-poles field, over-weighting the numerous small polar cells pulls the mean below the true area-weighted value — the observed cold bias.

2. **No use of latitude geometry**: the function reads only `ds["tas"].values` and never consults the `lat` coordinate (or the `lat_bnds`/`lon_bnds`), so it has no notion of per-cell area.

The fix therefore needs to introduce a latitude-dependent weight into the aggregation and nothing more; no evidence points to a secondary cause.

## Correctness Properties

Property 1: Bug Condition - Area-Weighted Mean Uses Cosine-of-Latitude Weights

_For any_ input where the bug condition holds (isBugCondition returns true — a grid with more than one distinct latitude), the fixed `global_mean` function SHALL weight each grid cell by the cosine of its latitude, so that each cell contributes in proportion to its true surface area. As analytic anchors on this weighting: for a constant temperature field C the weighted mean SHALL equal C within 1e-9 K (regardless of the latitude weighting), and per-cell areas derived from `lat_bnds`/`lon_bnds` over the full sphere SHALL sum to `4*pi` steradians within relative tolerance 1e-12.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation - Interface and Single-Band Reduction

_For any_ input where the bug condition does NOT hold (isBugCondition returns false — a constant field, a single-latitude-band grid, or any invocation viewed through the script's interface), the fixed function SHALL produce the same result as the original function, preserving: the plain unweighted mean when all latitudes are identical, the `tas` field read, CLI path resolution (positional argument defaulting to `data/sample.nc`), the Python `float` return type, and the `"Global-mean temperature: {value:.3f} K"` print format.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

Assuming the root-cause analysis is correct, the fix is confined to the aggregation step of `global_mean`.

**File**: `global_mean.py`

**Function**: `global_mean`

**Weighting approach — decision and justification:**

Two candidate per-cell weights were considered:

1. **Cosine of latitude centre** — `w(lat) = cos(deg2rad(lat))`.
2. **Exact band area from bounds** — for a cell spanning `[lat_lo, lat_hi]` in latitude and `[lon_lo, lon_hi]` in longitude, the exact area element on the unit sphere integrates to `(sin(lat_hi) - sin(lat_lo)) * (lon_hi - lon_lo)`.

The implementation uses **cosine of latitude centre** for the weighting in the mean. This is the minimal change that satisfies the approved requirements: requirement 2.1 explicitly mandates weighting each cell "by the cosine of its latitude," and requirement 3.1 is stated in terms of cosine weighting reducing to the plain mean on a single band. Cosine weighting needs only the `lat` coordinate already available on the dataset, is a function of latitude alone, and broadcasts cleanly across longitude and time. The exact band-area formula would require reading `lat_bnds`/`lon_bnds` and a sin-difference computation that the requirements do not ask the *mean* to use, so adopting it for the weighting would exceed the approved scope.

The exact band-area formula (`sin(lat_hi) - sin(lat_lo)` per latitude band times the longitude span) is still used — but only inside the test suite, as the independent analytic anchor for the area-closure identity (requirement 2.4). Keeping it out of the production aggregation avoids coupling the fix to the bounds variables while preserving a from-first-principles check that the closed-form areas sum to `4*pi`.

**Specific Changes:**

1. **Read the latitude coordinate**: obtain `ds["lat"].values` alongside `ds["tas"].values`.

2. **Build cosine weights**: compute `w = cos(deg2rad(lat))`, a 1-D array over the `lat` dimension.

3. **Broadcast and apply**: reshape `w` to align with the `lat` axis of the `(time, lon)` field and compute the weighted mean `sum(temp * w) / sum(w_broadcast)`, normalising by the summed weights over the same elements so the normalisation is a true convex combination.
   - Implementation may use `xarray`'s `weighted(...).mean()` over `lat` (and plain mean over `time`/`lon`), or an explicit NumPy `np.average`/`np.sum` with the broadcast weight. Either keeps the change local to the aggregation.

4. **Preserve the return contract**: wrap the aggregate in `float(...)` so the function still returns a Python `float`.

5. **Leave everything else untouched**: the signature `global_mean(path)`, the `xr.open_dataset(path)` read, the `__main__` path resolution, and the print statement remain exactly as they are.

## Testing Strategy

### Validation Approach

The strategy follows the two-phase pattern: first surface a counterexample that demonstrates the bug on the UNFIXED code, then verify the fix satisfies the analytic identities and preserves the interface and single-band behaviour. Per the lab's research rules, every assertion checks a value known exactly or analytically; no test compares the area-weighted output to the old uniform output, since both could share the same mistake.

### Exploratory Bug Condition Checking

**Goal**: Surface a counterexample that demonstrates the bug BEFORE implementing the fix, and confirm the root-cause hypothesis (uniform weighting ignores cos(lat)). If the hypothesis is refuted, re-hypothesise.

**Test Plan**: Construct a grid with a strong latitude contrast and a known analytic area-weighted answer, then run the UNFIXED `global_mean` and observe that it deviates from that analytic answer. The counterexample is defined against a *known* target, not against the fixed code.

**Test Cases**:
1. **Constant-field anchor on unfixed code**: a constant field C returns C for both `F` and `F'`; running this first confirms the harness and shows this input is not where the bug lives (diagnostic, passes on unfixed code).
2. **Analytic area-weighted target**: build a small field whose true cos(lat)-weighted mean is computable by hand, then show the UNFIXED `np.mean` result differs from it (will fail on unfixed code — the counterexample).
3. **Cold-bias direction**: on the warm-tropics/cold-poles sample grid, show the UNFIXED mean lies below the independently computed analytic area-weighted mean (demonstrates the cold-bias direction).

**Expected Counterexamples**:
- The unfixed `np.mean` result departs from the analytically computed cos(lat)-weighted mean on a multi-latitude grid.
- Cause: uniform `1/N` weighting ignores the `cos(lat)` area factor.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behaviour.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := global_mean_fixed(input)
  ASSERT expectedBehavior(result)
END FOR
```

Here `expectedBehavior` is pinned to the two analytic anchors from the requirements:
- Constant-field identity (2.3): for a constant field C, `result == C` within 1e-9 K.
- Area-closure identity (2.4): per-cell areas from `lat_bnds`/`lon_bnds` sum to `4*pi` within relative tolerance 1e-12.

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT global_mean_original(input) = global_mean_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is well suited to preservation checking here because:
- It generates many single-latitude-band grids and constant fields automatically across the input domain.
- It catches edge cases (extreme latitudes, degenerate grids) that fixed unit tests might miss.
- It gives a strong guarantee that the single-band reduction and the interface are unchanged for all non-buggy inputs.

**Test Plan**: For the single-latitude-band case, the preserved result is itself a known value — the plain mean of the field — so the test asserts against that analytic value rather than against the old code's output. Interface preservation (variable, path, type, format) is checked structurally.

**Test Cases**:
1. **Single-latitude-band reduction (3.1)**: build a grid where every cell shares one latitude; assert the fixed result equals the plain `mean` of the values (the analytically known answer for one common weight), within double-precision tolerance.
2. **`tas` read and path resolution (3.2, 3.3)**: assert the fixed function reads `tas` and resolves the positional path argument, defaulting to `data/sample.nc` when omitted.
3. **Return type and print format (3.4)**: assert the return value is a Python `float` and that the printed line matches `"Global-mean temperature: {value:.3f} K"`.

### Unit Tests

- Constant-field identity: a constant field C returns C within 1e-9 K (2.3).
- Area-closure identity: per-cell areas from `lat_bnds`/`lon_bnds`, using the closed-form `(sin(lat_hi) - sin(lat_lo)) * (lon_hi - lon_lo)` element, sum to `4*pi` within relative tolerance 1e-12 (2.4).
- Single-latitude-band reduction: a one-latitude grid returns the plain mean (3.1).
- Interface checks: `tas` read, path default to `data/sample.nc`, `float` return, and the exact print format (3.2-3.4).

### Property-Based Tests

- Generate random constant fields C over varied multi-latitude grids and assert the fixed mean equals C within 1e-9 K (constant-field identity across the domain).
- Generate random single-latitude-band grids and assert the fixed mean equals the plain mean of the field (single-band preservation across the domain).
- Generate random grids from the sample's bounds construction and assert the per-cell areas sum to `4*pi` within relative tolerance 1e-12 (area-closure identity across the domain).

### Integration Tests

- Run `global_mean("data/sample.nc")` end to end and assert the return is a finite Python `float`.
- Run the script's `__main__` path with and without a positional argument and assert it resolves the path as before and prints the `"Global-mean temperature: {value:.3f} K"` line.
- Verify the constant-field and area-closure anchors against a freshly built sample dataset so the identities hold on the actual on-disk grid, not only on in-memory fixtures.
