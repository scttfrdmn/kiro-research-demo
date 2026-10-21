"""Bugfix exploration tests for global_mean (cos(latitude) area weighting).

Reproducibility
---------------
Package versions (pinned in requirements.txt; installed in this session's venv):
    numpy  2.5.4
    xarray 2026.9.0
Grid matches make_sample.py: 2-degree cells, latitude centres -89..89,
longitude centres 1..359. No random temperature noise is used in the
constructed field, so the hand-computed target stays analytically exact.
A numpy RNG seed is pinned below for the grid-size parameterization only.
"""
import math

import numpy as np
import xarray as xr

from global_mean import global_mean

# Pinned seed for any grid-size parameterization (not used for temperatures,
# which are exact constants so the target stays analytically known).
SEED = 20261020

# Grid identical to make_sample.py.
LAT = np.arange(-89.0, 90.0, 2.0)   # centres -89, -87, ..., 89  (90 latitudes)
LON = np.arange(1.0, 360.0, 2.0)    # centres 1, 3, ..., 359    (180 longitudes)
TIME = np.array([f"2000-{m:02d}-15" for m in range(1, 13)], dtype="datetime64[ns]")


def _two_band_field(a, b):
    """Return a tas(time, lat, lon) DataArray: constant `a` over the equatorial
    band |lat| <= 29, constant `b` over the polar bands |lat| >= 31.

    The field is constant in longitude and time, so the unweighted mean reduces
    to a per-latitude count-weighted average and the area-weighted mean reduces
    to a cos(lat)-weighted average -- both computable by hand.
    """
    warm = np.abs(LAT) <= 29.0      # 30 latitudes: -29, -27, ..., 29
    cold = np.abs(LAT) >= 31.0      # 60 latitudes: the wider polar bands
    # Partition is exact: every grid latitude is in exactly one band.
    assert (warm | cold).all()
    assert not (warm & cold).any()

    band_value = np.where(warm, a, b)                     # (lat,)
    temp = np.broadcast_to(
        band_value[None, :, None],
        (TIME.size, LAT.size, LON.size),
    ).astype("float64")
    return xr.DataArray(
        temp,
        dims=("time", "lat", "lon"),
        coords={"time": TIME, "lat": LAT, "lon": LON},
        attrs={"units": "K"},
    )


def _hand_target(a, b):
    """Area-weighted target computed BY HAND from the chosen constants and the
    fixed latitude list -- NOT from any production reduction.

        w(lat)  = cos(deg2rad(lat))               (cell area factor on a reg grid)
        target  = (a*sum(w_warm) + b*sum(w_cold)) / (sum(w_warm) + sum(w_cold))

    The field is constant in lon/time, so those dimensions drop out of the ratio.
    """
    warm = np.abs(LAT) <= 29.0
    cold = np.abs(LAT) >= 31.0
    w = np.cos(np.deg2rad(LAT))
    sw = w[warm].sum()
    sc = w[cold].sum()
    return (a * sw + b * sc) / (sw + sc)


def _global_mean_on_field(field, tmp_path):
    """Write the field to a temp NetCDF file and run the production global_mean."""
    ds = xr.Dataset({"tas": field})
    nc = tmp_path / "two_band.nc"
    ds.to_netcdf(nc, encoding={"time": {"units": "days since 2000-01-01"}})
    return global_mean(str(nc))


def test_bug_condition_latitude_varying_field_is_biased_cold(tmp_path):
    """Property 1: Bug Condition -- latitude-varying field must equal the
    area-weighted target.

    **Validates: Requirements 1.1, 1.2**

    This is a FIX-VALIDATION test asserted against the analytically-known
    area-weighted target. It FAILS on the unfixed code and PASSES after the fix:

        - Unfixed global_mean uses np.mean over every cell, giving each
          (lat, lon) cell equal weight. Because the cold polar band spans more
          latitudes than the warm equatorial band while carrying (per the
          construction) nearly equal total cos(lat) area, the unweighted mean
          sits BELOW the true area-weighted mean. Result = 266.666... K != target.
        - Fixed global_mean applies cos(latitude) area weighting, so the result
          equals the hand-computed target. Result = 275.0 K == target.

    Documented counterexample (exact constants, this session's unfixed run,
    numpy 2.5.4):
        A (warm, |lat| <= 29)  = 300.0 K  over 30 latitudes
        B (cold, |lat| >= 31)  = 250.0 K  over 60 latitudes
        sum(w_warm) = 28.649344249275085   (cos-weight, warm band)
        sum(w_cold) = 28.649344249275092   (cos-weight, cold band)
        bands differ by only 7.1e-15, so target-275.0 == 0.0 in float64
        hand target (area-weighted) = (300*sw + 250*sc)/(sw+sc) = 275.0 K
        unfixed np.mean value       = (300*30 + 250*60)/90      = 266.666... K
        cold bias  = target - unfixed = 8.333... K

    On unfixed code the equality assertion below FAILS (266.666... != 275.0),
    and that failure confirms the cold bias. On fixed code it PASSES.
    """
    a, b = 300.0, 250.0
    assert b < a

    field = _two_band_field(a, b)
    target = _hand_target(a, b)          # 275.0 K, analytically exact
    result = _global_mean_on_field(field, tmp_path)

    # Tolerance justification (NOT a physical tolerance): the target 275.0 K is
    # analytically exact (the two bands' cos-weights differ by only 7.1e-15, so
    # target - 275.0 == 0.0 in float64). The only deviation the FIXED code can
    # introduce is floating-point summation rounding over 90 lat * 180 lon * 12
    # time cells, which is ~1e-12 relative. rel_tol/abs_tol = 1e-9 sits far above
    # that rounding floor yet far below the 8.33 K bug gap, so the assertion is
    # "exact or wrong," not approximately right.
    assert math.isclose(result, target, rel_tol=1e-9, abs_tol=1e-9), (
        f"area-weighted mean mismatch: result={result} K should equal "
        f"target={target} K (unfixed code yields 266.666... K)"
    )


# ---------------------------------------------------------------------------
# Property 2: Preservation -- Weight Identity And Constant-Field Baseline
#
# Observation-first methodology: both tests below MUST PASS on the UNFIXED
# global_mean.py. They record the baseline to preserve across the fix:
#   (a) the bounds-based per-cell area sums to 4*pi (independent of the code);
#   (b) the unweighted mean of a constant field already returns that constant.
#
# Reproducibility
#   Package versions (pinned in requirements.txt; installed in this session's
#   venv): numpy 2.5.4, xarray 2026.9.0.
#   Data source: data/sample.nc, produced deterministically by make_sample.py
#   with SEED = 20261020 on a 2-degree CF grid (lat_bnds/lon_bnds written by
#   make_sample.py). sha256(data/sample.nc) =
#       766614bd7cd884d131aec35a7eab0b930690789823e9f6f80232ad52a14c5ad6
#   Only lat_bnds/lon_bnds (not the noisy tas field) feed the weight-identity
#   test, so the 4*pi target is independent of the temperature noise.
# ---------------------------------------------------------------------------

SAMPLE_NC = "data/sample.nc"


def test_weight_identity_cell_areas_sum_to_four_pi():
    """Property 2 (weight identity): bounds-based cell areas sum to 4*pi.

    **Validates: Requirements 3.1**

    Reads lat_bnds/lon_bnds from data/sample.nc (the CF cell bounds written by
    make_sample.py) and computes each cell's exact unit-sphere area

        A = deg2rad(lon2 - lon1) * (sin(deg2rad(lat2)) - sin(deg2rad(lat1)))

    then asserts the total equals 4*pi.

    Why 4*pi, and why this tolerance:
        4*pi is the analytic surface area of the unit sphere -- known exactly,
        not recomputed from the code. Summing A over the full global grid
        telescopes in latitude: the sin(lat2)-sin(lat1) terms cancel across
        adjacent bands to sin(90deg)-sin(-90deg) = 2, and the longitude factors
        sum to 2*pi, giving 2*pi * 2 = 4*pi. The ONLY deviation is accumulated
        floating-point rounding over the telescoping sin-difference sum, which
        is a few ULP (~1e-12 relative on this grid). rel_tol = abs_tol = 1e-12
        therefore makes the check "exact or wrong," not approximately right.

    Scope note: this validates the AREA GEOMETRY that the fix's cos(latitude)
    centre weights approximate -- it does NOT assert the code's center-based
    weights directly. That renormalization is validated by the constant-field
    test below (and, after the fix, by the two-band test in task 3.2).
    """
    ds = xr.open_dataset(SAMPLE_NC)
    lat_bnds = ds["lat_bnds"].values     # (lat, 2): column 0 lower, column 1 upper
    lon_bnds = ds["lon_bnds"].values     # (lon, 2)

    # Exact unit-sphere area per cell: outer product of the longitude width (rad)
    # and the sin-latitude band height. No center-based approximation here.
    dlon = np.deg2rad(lon_bnds[:, 1] - lon_bnds[:, 0])                     # (lon,)
    dsin_lat = np.sin(np.deg2rad(lat_bnds[:, 1])) - np.sin(np.deg2rad(lat_bnds[:, 0]))  # (lat,)
    area = dsin_lat[:, None] * dlon[None, :]                              # (lat, lon)
    total = float(area.sum())

    assert math.isclose(total, 4.0 * math.pi, rel_tol=1e-12, abs_tol=1e-12), (
        f"cell areas must sum to the unit-sphere surface area 4*pi="
        f"{4.0 * math.pi!r}; got {total!r} (diff {total - 4.0 * math.pi!r})"
    )


def _constant_field(const, lat_centres, n_lon, n_time):
    """Return a tas(time, lat, lon) DataArray equal to `const` at every cell.

    Temperatures are an exact constant (no noise), so the mean target stays
    analytically known: it is exactly `const`.
    """
    lat = np.asarray(lat_centres, dtype="float64")
    lon = np.linspace(1.0, 359.0, n_lon)
    time = np.array(
        [f"2000-{m:02d}-15" for m in range(1, n_time + 1)],
        dtype="datetime64[ns]",
    )
    temp = np.full((time.size, lat.size, lon.size), float(const), dtype="float64")
    return xr.DataArray(
        temp,
        dims=("time", "lat", "lon"),
        coords={"time": time, "lat": lat, "lon": lon},
        attrs={"units": "K"},
    )


# Property-based coverage: several chosen constants C and several grid sizes.
# Grids are drawn from a pinned numpy RNG (SEED) so the parameterization is
# reproducible; latitudes are bounded to [-90, 90]. Temperatures stay exact
# constants, so each target is analytically known (== C).
def _constant_field_cases():
    rng = np.random.default_rng(SEED)
    constants = [0.0, 1.0, 250.0, 300.0, 1234.5]
    cases = []
    for const in constants:
        n_lat = int(rng.integers(3, 20))
        n_lon = int(rng.integers(3, 20))
        n_time = int(rng.integers(1, 6))
        # Sorted latitude centres strictly inside [-90, 90].
        lat_centres = np.sort(rng.uniform(-90.0, 90.0, size=n_lat))
        cases.append((const, tuple(lat_centres.tolist()), n_lon, n_time))
    return cases


import pytest


@pytest.mark.parametrize("const,lat_centres,n_lon,n_time", _constant_field_cases())
def test_constant_field_baseline_returns_the_constant(
    const, lat_centres, n_lon, n_time, tmp_path
):
    """Property 2 (constant-field baseline): a uniform field averages to C.

    **Validates: Requirements 3.1, 3.2, 3.3**

    Builds a tas(time, lat, lon) field equal to a single chosen constant C at
    every cell and runs the (currently UNFIXED) global_mean. The unweighted
    np.mean of identical values is that value, so this PASSES on unfixed code
    and records the baseline the fix must preserve (any area weighting of a
    constant field is a convex combination of equal values and still equals C).

    Why this tolerance:
        C is a chosen constant, known exactly -- not recomputed by any
        reduction. A mean of identical float64 values equals that value to a
        few ULP of accumulated summation rounding, i.e. ~1e-12 relative. So
        rel_tol = 1e-12 is the smallest tolerance that cannot be defeated by
        pure rounding, keeping the assertion "exact or wrong."
    """
    field = _constant_field(const, lat_centres, n_lon, n_time)
    ds = xr.Dataset({"tas": field})
    nc = tmp_path / "constant.nc"
    ds.to_netcdf(nc, encoding={"time": {"units": "days since 2000-01-01"}})

    result = global_mean(str(nc))

    assert math.isclose(result, const, rel_tol=1e-12, abs_tol=1e-12), (
        f"constant field at C={const} must average to C; got {result!r}"
    )
