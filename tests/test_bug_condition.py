"""Bug condition exploration test for area-weighted global mean.

Property 1: Bug Condition - Area-Weighted Mean Uses Cosine-of-Latitude Weights.

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**

These tests encode the EXPECTED (fixed) behavior as analytic anchors:
- A constant field averages to that constant (2.3).
- A multi-latitude field averages to its hand-computed cos(lat)-weighted mean
  (2.1, 2.2).

On the UNFIXED code (plain ``np.mean``) the multi-latitude anchor is EXPECTED
TO FAIL: uniform ``1/N`` weighting ignores the ``cos(lat)`` area factor and the
result is biased cold relative to the analytic area-weighted target. That
failure confirms the bug exists. Do NOT compare the area-weighted output
against the old uniform output here; every assertion targets a value known
analytically.
"""
import numpy as np
import xarray as xr

from global_mean import global_mean


def _write_dataset(tmp_path, lat, lon, time, temp):
    """Build an in-memory xarray.Dataset with tas(time, lat, lon) and persist it.

    Returns the path to the written NetCDF file so global_mean(path) can open it.
    """
    ds = xr.Dataset(
        {
            "tas": (
                ("time", "lat", "lon"),
                np.asarray(temp, dtype="float64"),
                {"units": "K", "long_name": "near-surface air temperature"},
            )
        },
        coords={
            "time": ("time", np.asarray(time)),
            "lat": ("lat", np.asarray(lat, dtype="float64"),
                    {"units": "degrees_north"}),
            "lon": ("lon", np.asarray(lon, dtype="float64"),
                    {"units": "degrees_east"}),
        },
    )
    path = tmp_path / "grid.nc"
    ds.to_netcdf(path)
    return str(path)


def test_constant_field_anchor(tmp_path):
    """A constant field C over a multi-latitude grid must average to C (2.3).

    This is an analytic anchor, not an F-vs-F' comparison: a (weighted) mean of
    identical values is a convex combination of C and so equals C. This input
    is NOT in the bug condition and passes on both unfixed and fixed code; it
    confirms the harness works.
    """
    C = 287.5
    lat = np.array([-60.0, -20.0, 10.0, 45.0, 80.0])  # multiple distinct lats
    lon = np.array([10.0, 100.0, 250.0])
    time = np.array(["2000-01-15", "2000-02-15"], dtype="datetime64[ns]")
    temp = np.full((time.size, lat.size, lon.size), C, dtype="float64")

    path = _write_dataset(tmp_path, lat, lon, time, temp)

    assert abs(global_mean(path) - C) < 1e-9


def test_analytic_area_weighted_target(tmp_path):
    """A multi-latitude field must equal its hand-computed cos(lat) mean (2.1, 2.2).

    Grid has two distinct latitudes (bug condition holds). The field is
    constant along each latitude band, so the true cos(deg2rad(lat))-weighted
    mean is computable by hand:

        lat = 0 deg  -> weight cos(0)   = 1.0, value 300 K
        lat = 60 deg -> weight cos(60)  = 0.5, value 240 K

        target = (1.0 * 300 + 0.5 * 240) / (1.0 + 0.5)
               = (300 + 120) / 1.5
               = 280.0 K

    The unfixed uniform mean is (300 + 240) / 2 = 270.0 K, which lies 10 K BELOW
    the analytic area-weighted target -- the cold bias. On UNFIXED code this
    assertion FAILS (counterexample: expected 280.0 K, got 270.0 K). On FIXED
    code it passes within 1e-9 K.
    """
    lat = np.array([0.0, 60.0])
    lon = np.array([30.0, 150.0, 270.0])
    time = np.array(["2000-06-15"], dtype="datetime64[ns]")

    temp = np.empty((time.size, lat.size, lon.size), dtype="float64")
    temp[:, 0, :] = 300.0  # lat 0 deg band
    temp[:, 1, :] = 240.0  # lat 60 deg band

    path = _write_dataset(tmp_path, lat, lon, time, temp)

    w0 = np.cos(np.deg2rad(0.0))
    w60 = np.cos(np.deg2rad(60.0))
    analytic_target = (w0 * 300.0 + w60 * 240.0) / (w0 + w60)

    assert analytic_target == 280.0  # self-check of the hand computation
    assert abs(global_mean(path) - analytic_target) < 1e-9
