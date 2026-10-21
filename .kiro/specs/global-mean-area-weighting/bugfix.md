# Bugfix Requirements Document

## Introduction

`global_mean.py` computes the global-mean near-surface temperature (`tas`) from a NetCDF file by taking an unweighted arithmetic mean over every grid point in the `(time, lat, lon)` array (`np.mean(temp)`). On a regular latitude-longitude grid, cells do not cover equal surface area: a cell near a pole spans the same number of degrees in longitude as a cell at the equator but subtends a much smaller physical area, with area proportional to `cos(latitude)`. Treating every cell equally therefore over-counts the many small, cold polar cells and under-counts the fewer-per-degree but larger warm tropical cells, producing a global mean that is biased cold.

The fix is to compute an area-weighted mean in which each cell's weight is proportional to its surface area, i.e. proportional to `cos(latitude)` for a regular lat-lon grid. The weighting is applied along the latitude dimension; longitude cells at a given latitude share equal area and are unaffected by relative weighting.

**Reproduction:** Run `python global_mean.py data/sample.nc`. The sample field (built by `make_sample.py`) is warm in the tropics and cold at the poles (`T ≈ 300 - 50 sin^2(lat) + ...`). The reported value from the unweighted mean sits below the true area-weighted global mean because polar cells are over-represented.

**Root cause:** `global_mean()` reduces the temperature array with `np.mean(temp)`, which assigns every `(lat, lon)` cell the same weight regardless of latitude. No `cos(latitude)` area weighting is applied.

## Bug Analysis

### Current Behavior (Defect)

The function averages all grid points with equal weight, ignoring that polar cells cover less area than equatorial cells.

1.1 WHEN a dataset spanning a range of latitudes is averaged THEN the system weights every grid cell equally and returns an area-unweighted mean that is biased cold relative to the true global mean
1.2 WHEN latitude cells near the poles are present THEN the system over-represents their (cold) values because their smaller surface area is not accounted for

### Expected Behavior (Correct)

The function should weight each cell by its surface area, proportional to `cos(latitude)`, so the result approximates the true global-mean temperature.

2.1 WHEN a dataset spanning a range of latitudes is averaged THEN the system SHALL weight each cell by `cos(latitude)` and return the area-weighted global mean
2.2 WHEN latitude cells near the poles are present THEN the system SHALL assign them smaller weight than equatorial cells in proportion to `cos(latitude)` so that polar values no longer bias the mean cold

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the field is uniform in latitude (every cell has the same temperature) THEN the system SHALL CONTINUE TO return that common value, because any area weighting of a constant field equals the constant
3.2 WHEN averaging over the longitude and time dimensions THEN the system SHALL CONTINUE TO treat those cells with equal weight, since cells at a fixed latitude share equal area and the weighting applies only across latitude
3.3 WHEN invoked from the command line with a path argument (or the default `data/sample.nc`) THEN the system SHALL CONTINUE TO read the `tas` variable and print the result in the existing `Global-mean temperature: {value:.3f} K` format

## Bug Condition and Properties

**Definitions:**
- **F**: the original function, `global_mean(path)` returning `np.mean(temp)` over all grid points.
- **F'**: the fixed function, returning the `cos(latitude)`-area-weighted mean.
- **X**: an input dataset with a `tas(time, lat, lon)` field and a `lat` coordinate (degrees).

**Bug Condition** — inputs that trigger the bug (the mean actually changes under area weighting):

```pascal
FUNCTION isBugCondition(X)
  INPUT:  X with field tas(time, lat, lon) and latitude coordinate lat
  OUTPUT: boolean

  // The unweighted and area-weighted means differ only when the field
  // varies with latitude AND the grid spans latitudes of differing area.
  // Equivalently: the per-latitude mean temperature is not constant across
  // latitudes that carry different cos(latitude) weight.
  RETURN cov_over_lat( cos(lat), zonalMean(tas, lat) ) <> 0
END FUNCTION
```

**Checking against known values (not against our own code).** Per the lab's correctness rule, every assertion compares the fixed code to a value that is known exactly or analytically. We therefore do **not** assert `globalMean'(X)` against a second re-implementation of the weighted mean (both could share the same mistake), and we do **not** assert `globalMean(X) = globalMean'(X)` (that compares `F` against `F'` rather than against a known truth). The two properties below pin the fix to values derivable by hand.

**Property 1: Bug Condition — constant field returns the constant exactly.**

For a `tas` field equal to a single constant `C` at every `(time, lat, lon)`, any valid area weighting is a convex combination of identical values, so the area-weighted mean is exactly `C` regardless of the weights.

```pascal
// Property 1: known-value check, independent of the weighting details
FOR a tas field that is the constant C at every (time, lat, lon) DO
  result ← globalMean'(X)
  ASSERT result == C      // exact to floating-point rounding; tol ~1e-12 relative
END FOR
```

`C` is a chosen constant, known exactly — not a quantity recomputed from the input by weighting. Tolerance `~1e-12` relative is justified because the result is a weighted sum of equal values divided by the weight total; the only error is a handful of ULP of accumulated rounding.

**Property 2: Preservation / weight correctness — cell areas sum to the whole sphere.**

The area weights the fix applies must be correct independent of the temperature field. On a unit sphere a cell spanning `[lon1, lon2] x [lat1, lat2]` has area `(lon2 - lon1 in radians) * (sin(lat2) - sin(lat1))`. Summing over the full global grid telescopes in latitude to `2*pi * (sin(90deg) - sin(-90deg)) = 4*pi` exactly.

```pascal
// Property 2: known-value check for the weights themselves
FOR the full global grid defined by lat_bnds, lon_bnds DO
  A(cell) ← deg2rad(lon2 - lon1) * ( sin(deg2rad(lat2)) - sin(deg2rad(lat1)) )
  ASSERT sum_over_cells( A ) == 4*pi    // tol ~1e-12 absolute/relative
END FOR
```

`4*pi` is the analytic surface area of the unit sphere, known exactly. Tolerance `~1e-12` is justified because the sum is a telescoping series of exact `sin` differences; error is only accumulated floating-point rounding over the grid. This validates the weights are correct without ever comparing the code to itself.

**Reproducibility.** Both properties are exercised against `data/sample.nc`, which is produced deterministically by `make_sample.py` with a pinned seed `SEED = 20261020` on a 2-degree grid (latitude centres `-89..89`, longitude centres `1..359`, with CF `lat_bnds`/`lon_bnds`). Package versions are pinned in `requirements.txt`.
