"""Bug-condition exploration tests for the area-weighted global mean.

These tests encode Property 1 from the design: the reported global mean must
equal the TRUE spherical-cell-area-weighted mean of the time-averaged field,

    result == sum(area * tas_tmean) / sum(area)

where, for a cell spanning [lat_lo, lat_hi] x [lon_lo, lon_hi] (radians),

    area = (sin(lat_hi) - sin(lat_lo)) * (lon_hi - lon_lo)

and tas_tmean is tas averaged (unweighted) over time.

STATUS: run against the UNFIXED `global_mean` (which returns the unweighted
`float(np.mean(temp))`), these assertions are EXPECTED TO FAIL. The failure is
the correct, intended outcome at this step: it demonstrates the cold bias --
the unweighted mean over-weights the small, cold polar cells, so it comes out
colder than the true area-weighted mean. The same tests validate the fix once
they pass after `global_mean` is made area-weighted.

Reproducibility:
- `data/sample.nc` is the committed artifact of `make_sample.py` (SEED = 20261020),
  used only for the directional bias check whose sign is known analytically.
- The synthetic dataset in Case B is built deterministically from explicit
  values, so its closed-form expected mean is known exactly.
"""
import numpy as np
import xarray as xr

from global_mean import global_mean


def _area_weights_from_bounds(lat_bnds, lon_bnds):
    """True unit-sphere cell areas from CF cell edges (degrees -> radians).

    area[i, j] = (sin(lat_hi_i) - sin(lat_lo_i)) * (lon_hi_j - lon_lo_j)
    """
    lat_bnds = np.asarray(lat_bnds, dtype="float64")
    lon_bnds = np.asarray(lon_bnds, dtype="float64")
    d_sin = np.sin(np.deg2rad(lat_bnds[:, 1])) - np.sin(np.deg2rad(lat_bnds[:, 0]))
    d_lon = np.deg2rad(lon_bnds[:, 1]) - np.deg2rad(lon_bnds[:, 0])
    return np.outer(d_sin, d_lon)  # shape (lat, lon)


def test_case_a_sample_nc_equals_area_weighted_mean():
    """Case A - cold-bias direction on data/sample.nc.

    Independently compute the true area-weighted mean from lat_bnds/lon_bnds
    and assert `global_mean("data/sample.nc")` equals it (Property 1). As a
    direction check, this area-weighted value is strictly WARMER than the
    unweighted mean, because the field is coldest at the poles where cells are
    smallest, so down-weighting those cold cells raises the mean.

    Tolerance: rtol = 1e-9. Justification: the reference value is itself a
    reduction over ~16200 cells (differences of sin and of longitudes),
    accumulating rounding on the order of eps * sqrt(N) ~ 2.2e-16 * 127 ~ 3e-14
    relative; 1e-9 sits well above worst-case accumulated rounding yet far below
    any structural difference between a weighted and an unweighted mean (here
    ~8 K out of ~283 K, i.e. ~3e-2 relative), so the check is exact-or-wrong,
    not approximately right.

    On UNFIXED code `global_mean` returns the unweighted mean (~274.999 K),
    which is NOT equal to the area-weighted mean (~283.331 K) -> this FAILS.
    """
    ds = xr.open_dataset("data/sample.nc")
    temp = ds["tas"].values  # (time, lat, lon)
    area = _area_weights_from_bounds(ds["lat_bnds"].values, ds["lon_bnds"].values)
    tas_tmean = temp.mean(axis=0)  # unweighted time average -> (lat, lon)
    area_weighted = float(np.sum(area * tas_tmean) / np.sum(area))

    reported = global_mean("data/sample.nc")

    # Direction known analytically: the area-weighted mean is warmer than the
    # unweighted mean for this cold-pole / warm-tropic field.
    unweighted = float(np.mean(temp))
    assert area_weighted > unweighted

    # Property 1: the reported value must equal the area-weighted mean.
    assert reported == area_weighted or abs(reported - area_weighted) <= 1e-9 * abs(
        area_weighted
    )


def test_case_b_synthetic_latitude_gradient_equals_closed_form():
    """Case B - synthetic latitude gradient with strongly unequal cell areas.

    Build an in-test NetCDF on a coarse 3-band x 2-column grid whose cell areas
    are strongly unequal and whose field rises monotonically with latitude.
    Assert `global_mean(path)` equals the closed-form area-weighted mean of the
    time-averaged field.

    Grid (latitude bands chosen so d_sin differs sharply between bands):
      lat edges: [-90, -30], [-30, 30], [30, 90]  (degrees)
      lon edges: [0, 180], [180, 360]             (degrees)
    Field is constant in time and in longitude, rising with latitude band:
      T = 250, 290, 270  for the three bands (monotone up then the warm-tropic
      band is warmest -- picked so the plain row-average differs from the
      area-weighted value).

    Closed form (analytic target, computed from the same exact edge arithmetic
    the fix will use):
      d_sin[k] = sin(hi_k) - sin(lo_k),  d_lon = (pi) per column, 2 columns
      area_band[k] = d_sin[k] * (2 * pi)
      result = sum_k area_band[k] * T[k] / sum_k area_band[k]

    Tolerance: rtol = 1e-12. Justification: a short exact-arithmetic chain in
    double precision (a handful of sin/sum/divide operations over 6 cells);
    1e-12 tracks accumulated double-precision rounding (~eps * a few ops) and is
    far below the several-kelvin gap between the area-weighted and unweighted
    means.

    On UNFIXED code `global_mean` returns the unweighted mean of all cells,
    which differs from the area-weighted closed form -> this FAILS.
    """
    lat = np.array([-60.0, 0.0, 60.0])  # band centres (not used in weighting)
    lon = np.array([90.0, 270.0])
    lat_bnds = np.array([[-90.0, -30.0], [-30.0, 30.0], [30.0, 90.0]])
    lon_bnds = np.array([[0.0, 180.0], [180.0, 360.0]])
    time = np.array(
        ["2000-01-15", "2000-02-15"], dtype="datetime64[ns]"
    )  # two identical time steps -> time mean is a no-op

    band_values = np.array([250.0, 290.0, 270.0])  # per latitude band
    # tas shape (time, lat, lon): constant in time and longitude.
    tas = np.empty((time.size, lat.size, lon.size), dtype="float64")
    for k in range(lat.size):
        tas[:, k, :] = band_values[k]

    ds = xr.Dataset(
        {"tas": (("time", "lat", "lon"), tas, {"units": "K"})},
        coords={
            "time": ("time", time),
            "lat": ("lat", lat, {"units": "degrees_north", "bounds": "lat_bnds"}),
            "lon": ("lon", lon, {"units": "degrees_east", "bounds": "lon_bnds"}),
            "lat_bnds": (("lat", "nv"), lat_bnds),
            "lon_bnds": (("lon", "nv"), lon_bnds),
        },
    )

    # Closed-form area-weighted mean from the exact edges.
    d_sin = np.sin(np.deg2rad(lat_bnds[:, 1])) - np.sin(np.deg2rad(lat_bnds[:, 0]))
    d_lon = np.deg2rad(lon_bnds[:, 1]) - np.deg2rad(lon_bnds[:, 0])
    area = np.outer(d_sin, d_lon)  # (lat, lon)
    tas_tmean = tas.mean(axis=0)  # (lat, lon)
    expected = float(np.sum(area * tas_tmean) / np.sum(area))

    import tempfile
    import os

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "gradient.nc")
        ds.to_netcdf(path)
        reported = global_mean(path)

    assert abs(reported - expected) <= 1e-12 * abs(expected)


# ---------------------------------------------------------------------------
# Task 2 - Preservation property tests (Property 2).
#
# These cover inputs where isBugCondition is FALSE: spatially uniform fields
# and equal-area (single-latitude-row) grids, plus the read/time-average/
# return-float contract and the script print format. Every assertion targets a
# value known ANALYTICALLY (a known constant, or the arithmetic mean of known
# values), never a second run of our own code -- so the test and the code
# cannot share the same mistake.
#
# STATUS: run against the UNFIXED `global_mean` (unweighted float(np.mean(temp)))
# these assertions are EXPECTED TO PASS. They capture the baseline behavior the
# fix must preserve: on these inputs the weighted and unweighted means are equal
# analytically, so the fix must not change the result.
# ---------------------------------------------------------------------------

import os
import subprocess
import tempfile
import re


def _write_dataset(path, tas, lat, lon, lat_bnds, lon_bnds, times):
    """Write a CF-style (time, lat, lon) tas dataset with cell bounds."""
    ds = xr.Dataset(
        {"tas": (("time", "lat", "lon"), tas, {"units": "K"})},
        coords={
            "time": ("time", times),
            "lat": ("lat", lat, {"units": "degrees_north", "bounds": "lat_bnds"}),
            "lon": ("lon", lon, {"units": "degrees_east", "bounds": "lon_bnds"}),
            "lat_bnds": (("lat", "nv"), lat_bnds),
            "lon_bnds": (("lon", "nv"), lon_bnds),
        },
    )
    ds.to_netcdf(path)


def test_case_1_uniform_field_returns_constant():
    """Case 1 - spatially uniform field (requirement 3.1).

    Build a synthetic dataset whose `tas` equals a constant T0 at every cell
    and every time, on a grid with known, unequal cell areas (a real lat-lon
    grid). Assert `global_mean(path) == T0`.

    Analytic target: for a constant field the weighted mean is
    sum(area * T0) / sum(area) = T0 for any positive weights, and the unweighted
    mean of a constant is also T0. The target T0 is a known constant, not a
    second run of our code.

    Tolerance: atol = 1e-12. Justification: the only arithmetic is a sum of a
    constant times weights divided by the sum of weights, a handful of rounding
    steps; machine epsilon scaled by T0 ~ 300 is eps*300 ~ 2.2e-16*300 ~ 6.7e-14,
    so 1e-12 sits above worst-case rounding and far below any real deviation.
    This holds on UNFIXED code (unweighted mean of a constant is also T0).
    """
    T0 = 287.125
    lat = np.array([-45.0, 0.0, 45.0])
    lon = np.array([90.0, 270.0])
    lat_bnds = np.array([[-90.0, -30.0], [-30.0, 30.0], [30.0, 90.0]])  # unequal areas
    lon_bnds = np.array([[0.0, 180.0], [180.0, 360.0]])
    times = np.array(["2000-01-15", "2000-02-15", "2000-03-15"], dtype="datetime64[ns]")

    tas = np.full((times.size, lat.size, lon.size), T0, dtype="float64")

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "uniform.nc")
        _write_dataset(path, tas, lat, lon, lat_bnds, lon_bnds, times)
        reported = global_mean(path)

    assert abs(reported - T0) <= 1e-12


def test_case_2_single_latitude_row_returns_arithmetic_mean():
    """Case 2 - equal-area grid / single latitude row (requirement 3.2).

    Build a synthetic one-row grid: a single latitude band, several longitude
    columns of equal width, so every cell shares one and the same area. The
    field varies across longitude (known values) but not across latitude, so
    isBugCondition is false. Assert `global_mean(path)` equals the plain
    arithmetic mean of the known cell values.

    Analytic target: with equal cell areas the weighted mean
    sum(area * T) / sum(area) reduces exactly to mean(T); the unweighted mean is
    also mean(T). The target is the arithmetic mean of explicit known values,
    computed directly from those literals -- not a second run of global_mean.

    Tolerance: rtol = 1e-12. Justification: a short-chain double-precision
    reduction (sum of a few equal-weighted values over a divide); 1e-12 tracks
    accumulated rounding (~eps * a few ops) and is far below any structural
    change. Equal weights make the weighted and arithmetic means identical
    analytically, so this holds on UNFIXED code.
    """
    lat = np.array([0.0])  # single latitude row -> all cells share one area
    lon = np.array([45.0, 135.0, 225.0, 315.0])
    lat_bnds = np.array([[-30.0, 30.0]])
    lon_bnds = np.array([[0.0, 90.0], [90.0, 180.0], [180.0, 270.0], [270.0, 360.0]])
    times = np.array(["2000-01-15", "2000-02-15"], dtype="datetime64[ns]")

    # Known cell values, constant in time, varying across longitude.
    cell_values = np.array([280.0, 290.0, 300.0, 310.0])
    tas = np.empty((times.size, lat.size, lon.size), dtype="float64")
    for j in range(lon.size):
        tas[:, 0, j] = cell_values[j]

    # Analytic arithmetic mean of the known literal values.
    expected = (280.0 + 290.0 + 300.0 + 310.0) / 4.0  # == 295.0

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "single_row.nc")
        _write_dataset(path, tas, lat, lon, lat_bnds, lon_bnds, times)
        reported = global_mean(path)

    assert abs(reported - expected) <= 1e-12 * abs(expected)


def test_case_3_contract_returns_python_float():
    """Case 3a - return-type contract (requirement 3.3).

    `global_mean(path)` returns a Python `float` (not a numpy scalar or array).
    Structural assertion; holds on UNFIXED code.
    """
    T0 = 300.0
    lat = np.array([-45.0, 45.0])
    lon = np.array([90.0, 270.0])
    lat_bnds = np.array([[-90.0, 0.0], [0.0, 90.0]])
    lon_bnds = np.array([[0.0, 180.0], [180.0, 360.0]])
    times = np.array(["2000-01-15"], dtype="datetime64[ns]")
    tas = np.full((times.size, lat.size, lon.size), T0, dtype="float64")

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "contract.nc")
        _write_dataset(path, tas, lat, lon, lat_bnds, lon_bnds, times)
        reported = global_mean(path)

    assert type(reported) is float


def test_case_3_time_axis_is_averaged_and_reorder_invariant():
    """Case 3b - the time axis is averaged (requirement 3.3).

    Construct a time-symmetric field: the per-time spatial means are {a, b}, and
    the field is reused so that reordering the two time steps leaves the set of
    time slices unchanged. Averaging over time must therefore give the same
    result regardless of time order. Assert the result is invariant under time
    reordering AND equals the analytic average of the two time-slice values.

    Analytic target: the global mean of a single-latitude-row (equal-area) grid
    is the arithmetic mean of its cells; with two time steps whose values are
    known literals, the time-averaged global mean is (mean(slice0)+mean(slice1))/2,
    computed from the literals -- not a second run of global_mean. Invariance
    under reordering is a structural property of averaging over time.

    Tolerance: rtol = 1e-12 (short double-precision reduction, as in Case 2).
    Holds on UNFIXED code, which averages over all of (time, lat, lon).
    """
    lat = np.array([0.0])  # single row -> equal areas, arithmetic spatial mean
    lon = np.array([90.0, 270.0])
    lat_bnds = np.array([[-30.0, 30.0]])
    lon_bnds = np.array([[0.0, 180.0], [180.0, 360.0]])
    times = np.array(["2000-01-15", "2000-02-15"], dtype="datetime64[ns]")

    # Time slice 0 cells -> spatial mean 285.0; time slice 1 cells -> 295.0.
    slice0 = np.array([280.0, 290.0])  # mean 285.0
    slice1 = np.array([290.0, 300.0])  # mean 295.0
    tas = np.empty((2, 1, 2), dtype="float64")
    tas[0, 0, :] = slice0
    tas[1, 0, :] = slice1

    # Reversed-time version: same two slices, swapped order.
    tas_rev = tas[::-1].copy()

    # Analytic time-and-space average of the known literals.
    expected = ((280.0 + 290.0) / 2.0 + (290.0 + 300.0) / 2.0) / 2.0  # == 290.0

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "time_fwd.nc")
        path_rev = os.path.join(d, "time_rev.nc")
        _write_dataset(path, tas, lat, lon, lat_bnds, lon_bnds, times)
        _write_dataset(path_rev, tas_rev, lat, lon, lat_bnds, lon_bnds, times)
        reported = global_mean(path)
        reported_rev = global_mean(path_rev)

    # Result equals the analytic time-and-space mean.
    assert abs(reported - expected) <= 1e-12 * abs(expected)
    # Averaging over time is order-invariant.
    assert abs(reported - reported_rev) <= 1e-12 * abs(expected)


def test_case_3_script_output_format():
    """Case 3c - script print format (requirement 3.4).

    Running the module as a script prints exactly one line matching
    `Global-mean temperature: {value:.3f} K`. Structural assertion on the output
    format; holds on UNFIXED code. Run through `uv run` per workspace rules.
    """
    proc = subprocess.run(
        ["uv", "run", "python", "global_mean.py", "data/sample.nc"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert re.fullmatch(r"Global-mean temperature: -?\d+\.\d{3} K", lines[0]), lines[0]


# ---------------------------------------------------------------------------
# Task 3.2 - Cell-area helper unit test: area sum equals 4*pi.
#
# Anchors the area weighting against an exact analytic total: the true
# unit-sphere cell areas over a full, non-overlapping tiling of the sphere sum
# to the surface area of the unit sphere, 4*pi. This is what makes the weights
# the TRUE spherical cell areas rather than a proxy.
# ---------------------------------------------------------------------------


def test_cell_area_full_grid_sums_to_four_pi():
    """Cell areas over a full sphere tiling sum to 4*pi (requirement 2.1).

    Build the full 90 lat x 180 lon grid implied by data/sample.nc bounds: a
    non-overlapping tiling with latitude edges spanning [-90, 90] in 90 equal
    2-degree bands and longitude edges spanning [0, 360] in 180 equal 2-degree
    columns. Compute the true unit-sphere cell areas with the same
    `_area_weights_from_bounds` helper the fix's weighting is built on, and
    assert the total equals 4*pi (the surface area of the unit sphere).

    By construction the tiling is exact: the latitude edges are the endpoints of
    `np.linspace(-90, 90, 91)` (so adjacent bands share an edge and the first/
    last edges are exactly +/-90), and the longitude edges are the endpoints of
    `np.linspace(0, 360, 181)`. The sin-differences telescope to
    sin(90deg) - sin(-90deg) = 2 and the longitude widths telescope to
    2*pi, so the analytic total is exactly 2 * 2*pi = 4*pi, independent of the
    band sizes -- the assertion targets the exact analytic value, not a second
    run of our own code.

    Tolerance: abs(sum(area) - 4*pi) <= 1e-9. Justification: the sum accumulates
    90*180 = 16200 cell areas, each a difference of sin values and of
    longitudes; worst-case accumulated rounding is on the order of
    eps * 4*pi * sqrt(N) ~ 2.2e-16 * 12.57 * 127 ~ 3.6e-13. 1e-9 sits well above
    that yet far below any structurally meaningful error, so the check is
    exact-or-wrong, not approximately right.
    """
    lat_edges = np.linspace(-90.0, 90.0, 91)   # 90 bands, edges include +/-90
    lon_edges = np.linspace(0.0, 360.0, 181)   # 180 columns, edges 0..360
    lat_bnds = np.column_stack([lat_edges[:-1], lat_edges[1:]])   # (90, 2)
    lon_bnds = np.column_stack([lon_edges[:-1], lon_edges[1:]])   # (180, 2)

    area = _area_weights_from_bounds(lat_bnds, lon_bnds)   # (90, 180)
    assert area.shape == (90, 180)

    total = float(np.sum(area))
    assert abs(total - 4.0 * np.pi) <= 1e-9


# ---------------------------------------------------------------------------
# Task 3.3 - Integration bound check.
#
# A necessary bound for any weighted mean with strictly positive weights: the
# result must lie within the [min, max] of the (time-averaged) field. This is
# an analytic bound (a convex combination of the cell values cannot fall
# outside their own range), not a second run of our own code, so it is a valid
# independent sanity check on the fixed result.
# ---------------------------------------------------------------------------


def test_case_a_fixed_result_within_field_min_max():
    """Fixed global mean lies within the field min/max (requirements 2.1, 2.2).

    The area-weighted mean is a convex combination of the time-averaged cell
    values with strictly positive weights, so it MUST satisfy
    min(tas_tmean) <= result <= max(tas_tmean). The bounds are known exactly
    from the data (the extreme cell values themselves), not from another run of
    global_mean. Exact inequality, no tolerance needed (a convex combination can
    never exceed its own endpoints in exact arithmetic; floating-point rounding
    of a weighted average stays within the endpoints to rounding, and the
    several-kelvin margin here is far larger than any rounding step).
    """
    ds = xr.open_dataset("data/sample.nc")
    tas_tmean = ds["tas"].values.mean(axis=0)  # (lat, lon)
    field_min = float(np.min(tas_tmean))
    field_max = float(np.max(tas_tmean))

    result = global_mean("data/sample.nc")

    assert field_min <= result <= field_max
