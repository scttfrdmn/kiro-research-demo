"""Bugfix exploration + property tests for area-weighted global mean.

Data source (integration smoke, Task 2+): data/sample.nc
  SHA-256 = 766614bd7cd884d131aec35a7eab0b930690789823e9f6f80232ad52a14c5ad6
  Verify with:  shasum -a 256 data/sample.nc

All Python is run through `uv run` per the lab reproducibility rules.
"""
import numpy as np
import xarray as xr

from global_mean import global_mean


def _write_latband_dataset(tmp_path, lat_edges, hot_value, cold_value):
    """Build a NetCDF dataset whose field is constant within each latitude band.

    The grid tiles the unit sphere exactly: latitude edges span -90..90 and
    longitude edges span 0..360. The field depends only on latitude: it equals
    `hot_value` in the northern hemisphere (lat centre >= 0) and `cold_value`
    in the southern hemisphere (lat centre < 0).

    Returns the dataset path.
    """
    lat_edges = np.asarray(lat_edges, dtype="float64")
    lat_lower = lat_edges[:-1]
    lat_upper = lat_edges[1:]
    lat_centre = 0.5 * (lat_lower + lat_upper)
    lat_bnds = np.stack([lat_lower, lat_upper], axis=1)  # (lat, 2)

    # A single longitude cell spanning the full circle 0..360.
    lon_edges = np.array([0.0, 360.0], dtype="float64")
    lon_lower = lon_edges[:-1]
    lon_upper = lon_edges[1:]
    lon_centre = 0.5 * (lon_lower + lon_upper)
    lon_bnds = np.stack([lon_lower, lon_upper], axis=1)  # (lon, 2)

    # Two time steps with the SAME spatial field: time averaging must leave the
    # spatial mean unchanged (preservation of time averaging).
    ntime = 2
    field2d = np.where(lat_centre[:, None] >= 0.0, hot_value, cold_value)
    temp = np.broadcast_to(field2d, (ntime, lat_centre.size, lon_centre.size)).copy()

    time = np.array(
        [f"2000-{m:02d}-15" for m in range(1, ntime + 1)], dtype="datetime64[ns]"
    )

    ds = xr.Dataset(
        {"tas": (("time", "lat", "lon"), temp.astype("float64"), {"units": "K"})},
        coords={
            "time": ("time", time),
            "lat": ("lat", lat_centre, {"units": "degrees_north", "bounds": "lat_bnds"}),
            "lon": ("lon", lon_centre, {"units": "degrees_east", "bounds": "lon_bnds"}),
            "lat_bnds": (("lat", "nv"), lat_bnds),
            "lon_bnds": (("lon", "nv"), lon_bnds),
        },
    )
    path = tmp_path / "latband.nc"
    ds.to_netcdf(path, encoding={"time": {"units": "days since 2000-01-01"}})
    return str(path)


# ---------------------------------------------------------------------------
# Task 1: Bug condition exploration test.
#
# This test MUST FAIL on the UNFIXED code (which returns np.mean(temp)).
# The failure confirms the cold-bias bug: equal weighting of unequal-area cells.
#
# Analytic construction (closed form, no re-implementation of our weighting):
#
#   The field takes value H = 300 K over the whole NORTHERN hemisphere and
#   C = 200 K over the whole SOUTHERN hemisphere. On a unit sphere the area
#   weight of a latitude band [a, b] is (sin b - sin a) (times the common
#   longitude span, which cancels in a normalized mean). Each hemisphere's
#   bands telescope to a total weight of exactly 1:
#       north: sin(90 deg) - sin(0 deg) = 1
#       south: sin(0 deg) - sin(-90 deg) = 1
#   independent of how finely each hemisphere is subdivided. So the exact
#   area-weighted (and time-averaged) mean is
#       V = (H * 1 + C * 1) / (1 + 1) = (300 + 200) / 2 = 250.0 K   (exact)
#
#   The grid is deliberately ASYMMETRIC: the northern hemisphere is split into
#   many thin bands and the southern hemisphere into few bands, so the grid has
#   more hot cells than cold cells. The UNWEIGHTED mean therefore leans toward
#   H and departs from V:
#       n_north = 9 cells (hot), n_south = 1 cell (cold)
#       np.mean = (9 * 300 + 1 * 200) / 10 = 290.0 K
#   This is NOT biased cold here; the point is only that the unweighted estimator
#   departs from the analytic area-weighted value V = 250. A latitude-varying
#   field with unequal cell counts breaks np.mean while the area-weighted mean
#   stays pinned to V. (The classic cold bias on a symmetric Earth-like grid is
#   the same mechanism: polar cells are over-weighted by np.mean.)
#
# DOCUMENTED COUNTEREXAMPLE (observed on unfixed code, see test run):
#   analytic V          = 250.0 K
#   F = global_mean(X)  = 290.0 K   (unweighted np.mean over 9 hot + 1 cold cell)
#   gap  F - V          = +40.0 K
#
# Tolerance: rtol = 1e-12. Justification: V = 250 is an exact algebraic value;
# the area-weighted mean of this two-value field reduces to (H*W_hot + C*W_cold)
# / (W_hot + W_cold) with W_hot = W_cold = 1 exactly, so a correct computation
# departs from 250 only by a few ULPs of floating-point rounding in the weighted
# sum and division. rtol 1e-12 sits well above that rounding floor (~1e-13 at
# this magnitude) and far below the 40 K defect, making the assertion
# exact-or-wrong rather than approximately right.
# ---------------------------------------------------------------------------
def test_bug_condition_latitude_varying_field_departs_from_analytic_mean(tmp_path):
    # Northern hemisphere: 9 thin bands (0..90). Southern hemisphere: 1 band (-90..0).
    # Asymmetric on purpose so hot-cell count (9) != cold-cell count (1).
    north_edges = np.linspace(0.0, 90.0, 10)   # 9 bands, edges 0..90
    lat_edges = np.concatenate([[-90.0], north_edges])  # add the single south band
    # lat_edges = [-90, 0, 10, 20, ..., 90]  -> 10 bands total (1 south + 9 north)

    H, C = 300.0, 200.0
    path = _write_latband_dataset(tmp_path, lat_edges, hot_value=H, cold_value=C)

    V = 250.0  # analytic area-weighted, time-averaged mean (exact)

    result = global_mean(path)

    # Asserts ONLY against the analytic value V. On the UNFIXED code this FAILS
    # (F returns 290.0, gap +40.0 K), confirming the equal-weighting bug.
    assert np.isclose(result, V, rtol=1e-12, atol=0.0), (
        f"area-weighted analytic V={V} K, global_mean returned {result} K, "
        f"gap {result - V:+} K"
    )

# ---------------------------------------------------------------------------
# Task 2: Preservation property tests (observation-first; PASS on UNFIXED code).
#
# These tests assert analytic truths that do not depend on the fix:
#   Property 2 tests pure grid geometry (a computation local to the test), and
#   the I/O-contract test checks only the return type of the unchanged
#   `global_mean`. Both therefore hold before the fix is applied.
#
# hypothesis is NOT installed in the pinned environment (requirements.txt lists
# numpy, xarray, netCDF4, pytest, matplotlib only; `uv run python -c "import
# hypothesis"` -> ModuleNotFoundError in this session). Per the task, we fall
# back to a deterministic loop over several generated grids.
# ---------------------------------------------------------------------------

# Generated grids that each tile the unit sphere exactly: latitude edges run
# strictly increasing from -90 to +90, longitude edges from 0 to 360. The grids
# deliberately vary in resolution, symmetry, and spacing (uniform, uneven,
# pole-adjacent thin bands) so the 4*pi total is exercised across edge cases.
def _sphere_tiling_grids():
    grids = []

    # 1. Coarse uniform grid.
    grids.append((np.linspace(-90.0, 90.0, 7), np.linspace(0.0, 360.0, 5)))

    # 2. Finer uniform grid.
    grids.append((np.linspace(-90.0, 90.0, 19), np.linspace(0.0, 360.0, 13)))

    # 3. The sample grid's geometry: 2-degree cells, edges -90..90 and 0..360.
    grids.append((np.linspace(-90.0, 90.0, 91), np.linspace(0.0, 360.0, 181)))

    # 4. Uneven latitude spacing (thin pole-adjacent bands) + uneven longitude.
    lat_uneven = np.array(
        [-90.0, -89.0, -80.0, -45.0, -10.0, 0.0, 15.0, 60.0, 89.0, 90.0]
    )
    lon_uneven = np.array([0.0, 0.5, 30.0, 170.0, 200.0, 359.0, 360.0])
    grids.append((lat_uneven, lon_uneven))

    # 5. Single latitude band spanning the whole sphere, single longitude cell.
    grids.append((np.array([-90.0, 90.0]), np.array([0.0, 360.0])))

    return grids


def _cell_areas_from_bounds(lat_edges, lon_edges):
    """Exact unit-sphere cell areas via the outer product of the bounds terms.

    area(cell) = (sin(lat_upper) - sin(lat_lower)) * (lon_upper_rad - lon_lower_rad)
    """
    lat_edges = np.asarray(lat_edges, dtype="float64")
    lon_edges = np.asarray(lon_edges, dtype="float64")

    lat_rad = np.deg2rad(lat_edges)
    lon_rad = np.deg2rad(lon_edges)

    dsin_lat = np.sin(lat_rad[1:]) - np.sin(lat_rad[:-1])   # (lat,)
    dlon = lon_rad[1:] - lon_rad[:-1]                        # (lon,)

    return dsin_lat[:, None] * dlon[None, :]                 # (lat, lon)


def test_preservation_cell_areas_sum_to_four_pi():
    """Property 2: cell areas from bounds sum to the unit sphere's area 4*pi.

    Tolerance: rtol = atol = 1e-12. Justification: 4*pi is known from geometry,
    independent of `global_mean`. The latitude terms telescope to
    sin(90 deg) - sin(-90 deg) = 2 and the longitude spans cover 2*pi exactly,
    so a correct area array sums to 4*pi. The only departure is the rounding of
    a bounded number of float additions (at most a few thousand cells here),
    which stays well under 1e-12 at this magnitude (4*pi ~ 12.57, ULP ~ 1e-15).
    A wrong area formula would miss 4*pi by far more than rounding, so the check
    is exact-or-wrong rather than approximately right.

    Validates: Requirements 2.1, 3.3
    """
    four_pi = 4.0 * np.pi

    for lat_edges, lon_edges in _sphere_tiling_grids():
        # Guard the generators: edges must strictly increase and tile the sphere.
        assert lat_edges[0] == -90.0 and lat_edges[-1] == 90.0
        assert lon_edges[0] == 0.0 and lon_edges[-1] == 360.0
        assert np.all(np.diff(lat_edges) > 0.0)
        assert np.all(np.diff(lon_edges) > 0.0)

        areas = _cell_areas_from_bounds(lat_edges, lon_edges)
        total = float(np.sum(areas))

        assert np.isclose(total, four_pi, rtol=1e-12, atol=1e-12), (
            f"cell areas sum to {total}, expected 4*pi = {four_pi}, "
            f"gap {total - four_pi:+e} for grid "
            f"(nlat={lat_edges.size - 1}, nlon={lon_edges.size - 1})"
        )


def test_preservation_global_mean_returns_python_float():
    """I/O contract: `global_mean` on the real sample returns a Python float.

    Type check only at this stage; value correctness is pinned by Property 1
    after the fix. This contract holds on the UNFIXED code (which already wraps
    its result in `float(...)`). The sample file is pinned by the SHA-256
    recorded at the top of this module.

    Validates: Requirements 3.2
    """
    result = global_mean("data/sample.nc")
    assert type(result) is float, f"expected Python float, got {type(result)!r}"
