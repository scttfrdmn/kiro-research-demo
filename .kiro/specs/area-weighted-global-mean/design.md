# Area-Weighted Global Mean Bugfix Design

## Overview

`global_mean(path)` in `global_mean.py` reads the `tas(time, lat, lon)` field and
returns `float(np.mean(temp))`. On a regular latitude-longitude grid this gives
every grid point equal weight, but grid cells do not cover equal surface area:
a cell's area shrinks toward the poles. The unweighted mean therefore
over-represents the small, cold polar cells and under-represents the large, warm
equatorial cells, biasing the reported mean cold.

The fix replaces the unweighted mean with an **area-weighted** mean. The weights
are the exact unit-sphere cell areas derived from the grid's `lat_bnds` /
`lon_bnds` (CF conventions, written by `make_sample.py`):

```
area(cell) = (sin(lat_upper) - sin(lat_lower)) * (lon_upper_rad - lon_lower_rad)
```

This is the analytically correct cell area (not the centre-`cos(lat)`
approximation) and is the form whose cells sum to exactly `4π` over the sphere.
The field is averaged over `time` as well as space; the function still reads the
`tas` variable via xarray and still returns a single Python `float`.

The change is confined to the body of `global_mean`. No new modules, frameworks,
configuration, or abstractions are introduced.

## Glossary

- **Bug_Condition (C)**: the field is not spatially uniform AND the grid's cell
  areas are not all equal (cell area varies with latitude). For such fields the
  unweighted mean differs from the area-weighted mean.
- **Property (P)**: the desired behavior of the fixed function — each grid cell
  contributes in proportion to its surface area, so the returned scalar is the
  area-weighted, time-averaged mean of `tas`.
- **Preservation**: behaviors that must not change — reading `tas` via xarray,
  averaging over time as well as space, returning one Python `float`, and
  returning `c` exactly for a spatially uniform field of value `c`.
- **global_mean**: the function in `global_mean.py` that opens the dataset at
  `path`, reads `tas`, and returns the global-mean temperature.
- **Cell area**: the exact unit-sphere surface area of a grid cell spanning
  `[lat_lower, lat_upper] × [lon_lower, lon_upper]`, equal to
  `(sin(lat_upper) - sin(lat_lower)) * (lon_upper_rad - lon_lower_rad)`.
- **lat_bnds / lon_bnds**: CF-convention cell-edge arrays of shape `(lat, 2)` and
  `(lon, 2)` present in `data/sample.nc`; the source of truth for cell areas.
- **F**: the original function, returning `float(np.mean(temp))`.
- **F'**: the fixed function, returning the area-weighted, time-averaged mean.

## Data Source (Reproducibility)

- **Input file**: `data/sample.nc`
- **SHA-256**: `766614bd7cd884d131aec35a7eab0b930690789823e9f6f80232ad52a14c5ad6`
- **Generator**: `make_sample.py`, deterministic via a fixed seed
  (`SEED = 20261020`), so a regenerated file reproduces the same values. It
  writes `tas(time, lat, lon)` on a 2-degree grid (lat centres -89..89, lon
  centres 1..359, 12 monthly steps) together with `lat_bnds` / `lon_bnds` giving
  each cell's edges (centre ± 1 degree).

Tests that construct their own in-memory grids do not depend on this file; the
checksum is recorded because the design and the integration test reference
`data/sample.nc`.

## Bug Details

### Bug Condition

The bug manifests whenever the temperature field varies across the grid AND the
grid's cell areas are not all equal (cell area varies with latitude). For such a
field, giving every grid point equal weight (`np.mean`) produces a different
answer from weighting each cell by its surface area, and the equal-weight answer
is biased toward the values in the small polar cells.

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT:  X = (tas field over (time, lat, lon), lat/lon coordinates with bounds)
  OUTPUT: boolean

  RETURN (NOT spatially_uniform(X.tas))
         AND (cellArea(X.lat_bnds, X.lon_bnds) is not constant across cells)
END FUNCTION
```

### Examples

- **Latitude-varying field (buggy input)**: `tas` warm at the equator and cold at
  the poles (as in `data/sample.nc`). Expected: area-weighted mean, dominated by
  the large equatorial cells. Actual (F): unweighted mean, biased cold because
  small polar cells carry equal weight.
- **Uniform field (not a buggy input)**: every grid point equals `c`. Expected
  and actual both equal `c`; area weighting leaves a constant unchanged.
- **Edge cell near the pole**: the cell spanning `[88°, 90°]` has a far smaller
  `sin(lat_upper) - sin(lat_lower)` than an equatorial cell spanning `[-1°, 1°]`,
  so it must contribute less. F ignores this difference.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- A spatially uniform field of value `c` continues to return `c` (Req 3.1).
- `global_mean(path)` continues to read the `tas` variable from the dataset at
  `path` via xarray and to return a single Python `float` (Req 3.2).
- A dataset with a `time` dimension continues to be averaged over time as well as
  space, yielding one scalar for the whole field (Req 3.3).

**Scope:**
All inputs where the bug condition does NOT hold must be unaffected by the fix.
This includes any spatially uniform field (same value everywhere), for which the
weighted and unweighted means both reduce to that value, and the function's I/O
contract (variable read, return type, time averaging).

## Hypothesized Root Cause

1. **Equal weighting of unequal-area cells**: `np.mean(temp)` averages every
   `(time, lat, lon)` grid point with weight `1/N`. On a regular lat-lon grid the
   cells are not equal area, so this is the wrong estimator of the spatial mean.

2. **No use of grid geometry**: the function never reads `lat_bnds` / `lon_bnds`
   (or even `lat`), so it has no notion of how much surface each cell represents.

3. **Latitude dominates the error**: cell area scales with
   `sin(lat_upper) - sin(lat_lower)`, which collapses toward the poles. The
   longitude spans are uniform on this grid, but the bounds are still used for
   longitude so the area formula is correct for any grid.

The fix addresses cause 1 and 2 directly by computing per-cell areas from the
bounds and using them as weights; cause 3 explains why latitude weighting carries
the correction.

## Correctness Properties

Property 1: Bug Condition - Area-weighted mean of a constant field is the constant

_For any_ spatially uniform field holding a chosen known constant `c` at every
grid point (a `¬isBugCondition` input that also pins the fix target), the fixed
`global_mean` SHALL return `c`. `c` is a value we choose, not an output of our
code, so the assertion is anchored to a known answer rather than to a second run
of our own mean.

**Validates: Requirements 2.1, 2.2, 3.1**

Property 2: Preservation - Cell areas from bounds sum to 4π

_For any_ grid described by `lat_bnds` / `lon_bnds`, the cell areas used as the
weights — `(sin(lat_upper) - sin(lat_lower)) * (lon_upper_rad - lon_lower_rad)` —
SHALL sum to the unit sphere's surface area `4π`. `4π` is known from geometry,
independent of `global_mean`, so this anchors the weighting scheme to an external
truth and confirms the weights are the correct cell areas.

**Validates: Requirements 2.1, 3.3**

## Fix Implementation

### Changes Required

**File**: `global_mean.py`

**Function**: `global_mean`

**Specific Changes**:
1. **Read grid bounds**: after opening the dataset, read `lat_bnds` and
   `lon_bnds` (shape `(lat, 2)` and `(lon, 2)`) alongside `tas`.

2. **Compute exact cell areas**: convert bounds to radians and compute
   `dsin_lat = sin(lat_upper_rad) - sin(lat_lower_rad)` per latitude and
   `dlon = lon_upper_rad - lon_lower_rad` per longitude; form the 2-D cell-area
   array as the outer product `dsin_lat[:, None] * dlon[None, :]` of shape
   `(lat, lon)`.

3. **Weighted spatial mean per time step, then mean over time**: compute the
   area-weighted spatial mean using the cell areas, then average over the `time`
   axis, reducing to a single scalar. Equivalently, broadcast the `(lat, lon)`
   weights over `time` and take `sum(temp * w) / sum(w)` over all axes, which is
   identical because the per-time-step weights are the same.

4. **Return a Python float**: wrap the scalar result in `float(...)` so the
   return type is unchanged.

5. **Keep everything else**: still open with `xr.open_dataset`, still read the
   `tas` variable, keep the `__main__` CLI untouched.

**Illustrative pseudocode:**
```
ds        = open_dataset(path)
temp      = ds["tas"].values                      # (time, lat, lon)
lat_bnds  = radians(ds["lat_bnds"].values)        # (lat, 2)
lon_bnds  = radians(ds["lon_bnds"].values)        # (lon, 2)

dsin_lat  = sin(lat_bnds[:, 1]) - sin(lat_bnds[:, 0])   # (lat,)
dlon      = lon_bnds[:, 1] - lon_bnds[:, 0]             # (lon,)
area      = dsin_lat[:, None] * dlon[None, :]           # (lat, lon)

w         = broadcast area over time                    # (time, lat, lon)
return float(sum(temp * w) / sum(w))
```

## Testing Strategy

### Validation Approach

Two-phase approach: first surface counterexamples that demonstrate the bug on the
unfixed code, then verify the fix returns known analytic values and preserves
existing behavior. Every assertion below compares an output (or a derived
quantity) against a value known analytically — a chosen constant `c` or the
geometric total `4π`. No test compares two outputs of our own code to each other,
and no test compares F against F'.

All Python is run through `uv run` (`uv run pytest ...`, `uv run python ...`);
`python`, `python3`, and `.venv/bin/python` are never invoked directly.

### Exploratory Bug Condition Checking

**Goal**: Surface a counterexample that demonstrates the bug on the UNFIXED code
and confirm the root cause (equal weighting of unequal-area cells). If it does
not fail as expected, re-hypothesize.

**Test Plan**: Construct a small in-memory field that varies with latitude on a
grid with known `lat_bnds` / `lon_bnds`, for which the area-weighted mean has a
known closed form. Run `global_mean` (F) and observe that it departs from that
known value, demonstrating the cold bias. This test is exploratory and is
expected to fail on F; it is not part of the preserved suite in its failing form.

**Test Cases**:
1. **Latitude-varying field**: a field whose area-weighted mean is analytically
   known (e.g. constructed so the weighted mean equals a chosen value) will show
   F returning a cold-biased number (will fail on unfixed code).

**Expected Counterexamples**:
- F returns a value biased toward the polar (cold) cells rather than the
  area-weighted value, because `np.mean` weights all cells equally.

### Fix Checking

**Goal**: Verify that for inputs where the bug would apply, the fixed function
produces behavior anchored to a known value.

**Pseudocode:**
```
FOR ALL c IN chosen_constants DO
  X := uniform_field(value = c over (time, lat, lon))   // NOT isBugCondition(X)
  result := global_mean'(X)
  ASSERT result == c          // rtol ~1e-12
END FOR
```

This is Property 1. A spatially uniform field is a `¬isBugCondition` input, but
it also pins the fixed function to a known answer: any correctly normalized set
of nonnegative weights averages a constant field back to that constant.

**Tolerance**: `rtol ~1e-12` (exact to a few ULPs). **Justification**: the
weighted mean of a constant `c` reduces algebraically to `c`; the only departure
is floating-point rounding in the weighted sum and the final division, bounded by
a few ULPs for grids of this size. A tolerance near `1e-12` is comfortably above
that rounding floor and far below any real difference, so the assertion is
exact-or-wrong, not approximately right.

### Preservation Checking

**Goal**: Verify that the weighting scheme matches the true cell geometry and
that unchanged behaviors remain unchanged, both anchored to known facts rather
than to a second run of our code.

**Pseudocode:**
```
areas := FOR each cell:
           (sin(lat_upper) - sin(lat_lower)) * (lon_upper_rad - lon_lower_rad)
ASSERT sum(areas) == 4 * pi      // atol/rtol ~1e-12
```

This is Property 2. The total is independent of `global_mean`: the latitude terms
telescope to `sin(90°) - sin(-90°) = 2` and the longitude spans cover `2π`
exactly, so a correct area array sums to `4π`.

**Tolerance**: `atol`/`rtol ~1e-12`. **Justification**: the sum is a finite
series of exact analytic terms; the only error is the rounding of a bounded
number of floating-point additions (a few thousand cells here), which stays well
within `1e-12`. Choosing `1e-12` keeps the check tight enough to catch a wrong
area formula (which would miss `4π` by far more than rounding) while tolerating
only genuine floating-point noise.

**Testing Approach**: Property-based testing is a natural fit for the area-sum
check because it can generate many valid `lat_bnds` / `lon_bnds` grids and assert
the `4π` total holds for all of them, catching edge cases (pole-adjacent cells,
uneven spacing) that a single hand-built grid might miss. The constant-field
check (Property 1) is likewise amenable to property-based generation over a range
of chosen constants `c` and grid shapes.

**Test Cases**:
1. **Area normalization (Property 2)**: cell areas from `lat_bnds` / `lon_bnds`
   sum to `4π` on a unit sphere (`atol`/`rtol ~1e-12`), for the sample grid and
   for generated grids that tile the sphere.
2. **Constant-field preservation (Property 1)**: a uniform field of value `c`
   returns `c` (`rtol ~1e-12`), for several chosen `c` and grid shapes.
3. **Return contract**: `global_mean` returns a Python `float` and averages over
   time (a uniform-in-space field with time variation still returns the uniform
   spatial value per the constant-field construction).

### Unit Tests

- Area-sum equals `4π` for the `data/sample.nc` grid (pinned by checksum).
- Constant field of chosen `c` returns `c`.
- Return type is `float`; function reads the `tas` variable.

### Property-Based Tests

- Generate grids with varied `lat_bnds` / `lon_bnds` that tile the sphere and
  assert cell areas sum to `4π` (Property 2).
- Generate uniform fields with varied constants `c` and grid shapes and assert
  the result equals `c` (Property 1).

### Integration Tests

- Run `global_mean("data/sample.nc")` end to end via `uv run` and confirm it
  returns a finite Python `float` averaged over time and space (behavioral
  smoke check; numeric correctness is pinned by the analytic Properties 1 and 2,
  not by comparing against a stored output of our own code).
