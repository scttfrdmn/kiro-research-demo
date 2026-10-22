# Bugfix Requirements Document

## Introduction

`global_mean.py` reports a global-mean near-surface temperature (variable `tas`, dims `(time, lat, lon)`) that is biased cold. The function `global_mean()` computes `float(np.mean(temp))` over the full array, weighting every grid cell equally. On a regular latitude-longitude grid, grid-cell surface area is not uniform: it shrinks toward the poles, so high-latitude (cold, polar) cells represent much less surface area than low-latitude (warm, tropical) cells. Equal weighting over-counts the cold polar cells and under-counts the warm tropical cells, producing a systematic cold bias in the reported mean.

The fix is to compute an area-weighted global mean in which each grid cell is weighted by its **true spherical cell area** computed from the dataset's `lat_bnds` / `lon_bnds`, rather than an unweighted mean. On the unit sphere a cell bounded by `[lat_lo, lat_hi] x [lon_lo, lon_hi]` (radians) has area `(sin(lat_hi) - sin(lat_lo)) * (lon_hi - lon_lo)`. The point `cos(latitude)` value is only the first-order approximation to this exact cell area; because the dataset carries `lat_bnds` and `lon_bnds`, the fix uses the exact areas.

## Bug Analysis

### Current Behavior (Defect)

The reported global mean treats all grid cells as equal in area, so it is a simple arithmetic mean over `(time, lat, lon)`.

1.1 WHEN `global_mean(path)` is called on a `tas` field whose grid has unequal per-cell spherical areas (areas from `lat_bnds`/`lon_bnds` are not all equal) THEN the system returns `float(np.mean(temp))`, an unweighted mean that over-weights high-latitude cells and under-weights low-latitude cells
1.2 WHEN the temperature field has a realistic pole-to-equator gradient (cold poles, warm tropics) THEN the system returns a value biased cold relative to the true area-weighted global mean

### Expected Behavior (Correct)

The reported global mean weights each grid cell by its true spherical cell area.

2.1 WHEN `global_mean(path)` is called on a `tas` field THEN the system SHALL return the mean of the time-averaged `temp` weighted by the true per-cell spherical area, where each cell's weight is `(sin(lat_hi) - sin(lat_lo)) * (lon_hi - lon_lo)` with the cell edges read from `lat_bnds`/`lon_bnds` and converted to radians
2.2 WHEN the temperature field has a realistic pole-to-equator gradient THEN the system SHALL return the area-weighted global mean, which is warmer than (and not equal to) the unweighted mean of 1.2

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the temperature field is spatially uniform (all grid cells share the same value at a given time) THEN the system SHALL CONTINUE TO return that value, because the area-weighted mean of a constant field equals that constant regardless of weights
3.2 WHEN the grid's cells all have equal true spherical cell area (e.g. a single latitude row) THEN the system SHALL CONTINUE TO return the same value as the unweighted mean, because equal cell-area weights reduce the weighted mean to the arithmetic mean
3.3 WHEN `global_mean(path)` is called THEN the system SHALL CONTINUE TO read the `tas` variable from the NetCDF file at `path`, average over the `time` dimension as well as space, and return a single Python `float`
3.4 WHEN the module is run as a script with a path argument THEN the system SHALL CONTINUE TO print the result in the existing format `Global-mean temperature: {value:.3f} K`

## Bug Condition and Properties

**Definitions**
- **F**: the original function, `global_mean` computing `float(np.mean(temp))`.
- **F'**: the fixed function, `global_mean` computing the true-spherical-cell-area-weighted mean.
- **X**: an input dataset providing `tas` with dims `(time, lat, lon)` and cell-edge arrays `lat_bnds` (shape `(lat, 2)`) and `lon_bnds` (shape `(lon, 2)`).
- **Cell area (unit sphere)**: for a cell bounded by latitudes `lat_lo < lat_hi` and longitudes `lon_lo < lon_hi` (all in radians), `area = (sin(lat_hi) - sin(lat_lo)) * (lon_hi - lon_lo)`. Summed over a full, non-overlapping tiling of the sphere these areas total `4*pi`. The point `cos(latitude)` value is the first-order approximation to this exact cell area.

### Bug Condition

```pascal
FUNCTION isBugCondition(X)
  INPUT:  X with tas(time, lat, lon), and cell edges lat_bnds, lon_bnds
  OUTPUT: boolean

  // Unweighted and area-weighted means differ only when the true per-cell
  // spherical areas are not all equal AND the field varies with latitude.
  // In that case the equal-weight mean is biased relative to the area-weighted mean.
  areas := cellAreas(X.lat_bnds, X.lon_bnds)   // true unit-sphere areas per (lat, lon)
  RETURN (areas are NOT all equal)
         AND (X.tas varies across latitude)
END FUNCTION
```

### Fix Checking (property for buggy inputs)

```pascal
// Property: the reported mean equals the area-weighted mean, not the unweighted mean.
FOR ALL X WHERE isBugCondition(X) DO
  result ← globalMean'(X)
  area   ← cellAreas(X.lat_bnds, X.lon_bnds)        // true unit-sphere cell areas
  tmean  ← timeMean(X.tas)                          // tas averaged over time
  ASSERT result = sum(area * tmean) / sum(area)     // exact, to floating-point rounding
END FOR
```

The cell areas are anchored by the exact total `sum(area) = 4*pi` over a full non-overlapping sphere tiling (to floating-point rounding), which is what makes these weights the true surface areas rather than a proxy. For a field with a cold-pole/warm-tropic gradient this also implies `globalMean'(X) > globalMean(X)` (the cold bias is removed).

### Preservation Checking (property for non-buggy inputs)

```pascal
// Property: where weights are effectively uniform, the fix changes nothing.
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT globalMean'(X) = globalMean(X)             // to floating-point rounding
END FOR
```

This covers the regression cases: a spatially uniform field (3.1) and a grid whose cells all have equal true spherical cell area (3.2) both yield identical results before and after the fix.
