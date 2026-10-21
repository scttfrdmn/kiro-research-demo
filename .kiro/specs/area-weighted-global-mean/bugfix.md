# Bugfix Requirements Document

## Introduction

`global_mean.py` computes the global-mean near-surface temperature from a NetCDF
dataset. Its `global_mean(path)` function reads the `tas` variable into a
`(time, lat, lon)` array and returns `float(np.mean(temp))`.

On a regular latitude-longitude grid, grid cells do not represent equal surface
area: a cell's area is proportional to the cosine of its latitude, so cells near
the poles cover far less surface than cells near the equator. By taking an
unweighted `np.mean`, the current code gives every grid point equal weight. This
over-represents the small, cold polar cells and under-represents the large, warm
equatorial cells, so the reported global mean is biased cold.

The fix is to compute an area-weighted mean using `cos(latitude)` weights, so each
grid cell contributes in proportion to the surface area it represents.

## Bug Analysis

### Current Behavior (Defect)

The function averages every grid point with equal weight, ignoring that polar
cells cover less area than equatorial cells.

1.1 WHEN `global_mean(path)` averages a `(time, lat, lon)` temperature field THEN the system weights every grid point equally via `np.mean(temp)`, ignoring latitude-dependent cell area
1.2 WHEN the temperature field varies with latitude (warm equator, cold poles) THEN the system returns a global mean biased cold relative to the true area-weighted mean, because small cold polar cells are over-weighted

### Expected Behavior (Correct)

The function weights each grid cell by `cos(latitude)` so that each cell
contributes in proportion to its surface area.

2.1 WHEN `global_mean(path)` averages a `(time, lat, lon)` temperature field THEN the system SHALL weight each grid cell by `cos(latitude)` (in radians) so that each cell contributes in proportion to its surface area
2.2 WHEN the temperature field varies with latitude THEN the system SHALL return the area-weighted global mean, which removes the cold bias introduced by equal weighting

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the temperature field is spatially uniform (identical value at every grid point) THEN the system SHALL CONTINUE TO return that value, because area weighting leaves the mean of a constant field unchanged
3.2 WHEN `global_mean(path)` is called THEN the system SHALL CONTINUE TO read the `tas` variable from the NetCDF dataset at `path` via xarray and return a single Python `float`
3.3 WHEN the dataset has a `time` dimension THEN the system SHALL CONTINUE TO average over time as well as space, returning one scalar for the whole field

## Bug Condition and Properties

**Key definitions**
- **F**: the original function, returning `float(np.mean(temp))`.
- **F'**: the fixed function, returning the `cos(latitude)`-weighted mean.
- **X**: an input field `tas(time, lat, lon)` with its `lat` coordinate.

### Bug Condition

```pascal
FUNCTION isBugCondition(X)
  INPUT:  X = (tas field over (time, lat, lon), lat coordinates)
  OUTPUT: boolean

  // The bug manifests whenever the field is not spatially uniform AND
  // the grid's area weights are not all equal (i.e. cos(lat) varies).
  // For such fields the unweighted mean differs from the area-weighted mean.
  RETURN (NOT spatially_uniform(X.tas)) AND (cos(X.lat) is not constant)
END FUNCTION
```

Both properties below assert values that are known analytically — a chosen
constant `c` and the geometric surface area `4π` — never an output of our own
mean function and never a re-implementation of the same weighting. This keeps
each assertion exact-or-wrong rather than approximately right, and avoids
comparing two outputs of our own code to each other.

**Weighting source.** The weights MUST be the cell areas derived from the grid's
`lat_bnds` / `lon_bnds` (CF conventions, written by `make_sample.py`), not from
`cos(lat)` of the cell centres. For a unit sphere the exact area of a cell
spanning `[lat_lower, lat_upper] × [lon_lower, lon_upper]` is

```
area = (sin(lat_upper) - sin(lat_lower)) * (lon_upper_rad - lon_lower_rad)
```

The centre-`cos(lat)` form is only an approximation of this; the bounds-based
form is the analytically correct cell area and is what sums exactly to `4π`
(Property 2 below). The design phase MUST therefore read `lat_bnds` / `lon_bnds`
and use the sin-of-bounds area as the weights.

### Property 1: Constant field returns the constant (preservation, known value)

For a spatially uniform field holding a known constant `c` at every grid point,
the fixed function returns `c`. `c` is a value we choose, not an output of our
code, so this pins both the preservation goal (`¬isBugCondition`) and the fix to
a known answer.

```pascal
// Property 1: Constant field - known value c
FOR ALL c IN chosen_constants DO
  X ← uniform_field(value = c over (time, lat, lon))   // NOT isBugCondition(X)
  result ← global_mean'(X)
  ASSERT result = c      // tolerance: rtol ~1e-12 (a few ULPs)
END FOR
```

Tolerance: `rtol ~1e-12` (exact to a few ULPs). Justification: averaging a
constant field with any correctly normalized set of nonnegative weights reduces
algebraically to `c`; the only departure from `c` is floating-point rounding in
the weighted sum and the division by the weight total, which is bounded by a few
ULPs for these grid sizes.

### Property 2: Cell areas sum to 4π (known analytic total)

The cell areas used as weights, computed from `lat_bnds` / `lon_bnds` on a unit
sphere, sum to the sphere's surface area `4π`. `4π` is known from geometry, not
produced by our mean function, so this anchors the weighting scheme to an
external truth independent of the code under test.

```pascal
// Property 2: Area normalization - known total 4*pi
areas ← FOR each cell:
          (sin(lat_upper) - sin(lat_lower)) * (lon_upper_rad - lon_lower_rad)
ASSERT sum(areas) = 4 * pi      // tolerance: atol/rtol ~1e-12
```

Tolerance: `atol`/`rtol ~1e-12`. Justification: the total is a finite sum of
exact analytic terms (`sin` of the bounds times the longitude span in radians);
the latitude terms telescope to `sin(90°) - sin(-90°) = 2` and the longitude
spans cover `2π` exactly, so the sum equals `4π` up to the rounding of a finite
number of floating-point additions, bounded well within `1e-12` for this grid.

Together these give a fix check anchored to a known value (`c`) and a weighting
check anchored to a known total (`4π`), neither of which is an output of
`global_mean`.
