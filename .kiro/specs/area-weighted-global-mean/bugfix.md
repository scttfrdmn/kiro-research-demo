# Bugfix Requirements Document

## Introduction

`global_mean.py` computes the global-mean near-surface temperature (`tas`) from a NetCDF file on a regular latitude-longitude grid. The current implementation averages every grid point with equal weight (`np.mean(temp)`).

On a regular lat-lon grid, cells near the poles span the same number of degrees in latitude and longitude as cells near the equator, but they cover far less physical surface area (cell area scales with the cosine of latitude). Averaging with equal weights over-represents the small, cold polar cells and under-represents the large, warm equatorial cells. The reported global mean is therefore biased cold.

The fix is to area-weight the mean so each cell contributes in proportion to its true surface area. On a regular lat-lon grid this is done by weighting each cell by the cosine of its latitude.

Correctness is verified against values known analytically, never by comparing the area-weighted output to the old uniformly-weighted output (both could share the same mistake). Two exact anchors are available from the sample grid, which writes CF-convention `lat_bnds` and `lon_bnds`: the mean of a constant field must equal that constant exactly, and the per-cell areas derived from the bounds must sum to the total area of the unit sphere, `4*pi` steradians.

## Bug Analysis

### Current Behavior (Defect)

The mean is computed with uniform weights across all grid points, so high-latitude cells are over-represented relative to their surface area and the result is biased cold.

1.1 WHEN the global mean is computed over a lat-lon grid whose latitudes are not all identical THEN the system weights every grid cell equally regardless of latitude
1.2 WHEN grid cells at different latitudes are averaged with equal weight THEN the system over-represents high-latitude (colder) cells relative to their true surface area
1.3 WHEN high-latitude cells are over-represented THEN the system returns a global-mean temperature that is biased cold relative to the true area-weighted mean

### Expected Behavior (Correct)

The mean is area-weighted so each cell contributes in proportion to its surface area, using the cosine of latitude as the per-cell weight. Correctness is pinned to two analytic identities: the mean of a constant field equals that constant, and per-cell areas sum to the total area of the unit sphere.

2.1 WHEN the global mean is computed over a lat-lon grid THEN the system SHALL weight each grid cell by the cosine of its latitude
2.2 WHEN cells are area-weighted by cosine of latitude THEN the system SHALL compute the mean such that high-latitude cells contribute in proportion to their true surface area
2.3 WHEN the temperature field is a constant value C over the whole grid THEN the area-weighted global mean SHALL equal C exactly, regardless of the latitude weighting, within a tolerance of 1e-9 K (a weighted mean of identical values is a convex combination of C and so equals C up to floating-point rounding of the weight normalisation; 1e-9 K is many orders of magnitude below double-precision round-off for values near 300 K, so any deviation above it indicates a weighting defect rather than numerical noise)
2.4 WHEN per-cell areas are computed from `lat_bnds` and `lon_bnds` THEN the sum of all cell areas over the sphere SHALL equal `4*pi` steradians (the unit-sphere total) within a relative tolerance of 1e-12 (the exact closed-form integral of the area element over complete latitude and longitude bands sums analytically to `4*pi`; 1e-12 relative is at the level of accumulated double-precision round-off over the ~16200 cells of the sample grid, so a larger residual indicates an error in the area formula rather than rounding)

### Unchanged Behavior (Regression Prevention)

Area weighting must not alter results that do not depend on the latitude-area imbalance, nor change the script's interface or output format.

3.1 WHEN the latitudes of every grid cell are identical (a single latitude band) THEN the system SHALL CONTINUE TO return the plain mean of the temperature values, because cosine weighting applies one common weight and reduces to the unweighted mean
3.2 WHEN the input NetCDF file and variable (`tas`) are provided THEN the system SHALL CONTINUE TO read the dataset and operate on the same `tas` field
3.3 WHEN a path argument is provided on the command line (or omitted, defaulting to `data/sample.nc`) THEN the system SHALL CONTINUE TO resolve the input path the same way
3.4 WHEN the global mean is printed THEN the system SHALL CONTINUE TO return a Python `float` and print it in the existing `"Global-mean temperature: {value:.3f} K"` format
