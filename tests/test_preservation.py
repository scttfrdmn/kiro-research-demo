"""Preservation property tests for area-weighted global mean.

Property 2: Preservation - Interface and Single-Band Reduction.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

These tests cover inputs OUTSIDE the bug condition (``isBugCondition`` is
false): single-latitude-band grids, constant fields, and the script's external
interface. Following the observation-first methodology, every numerical
assertion targets a value known analytically -- the plain unweighted mean --
never the raw output of the old code. On a single latitude band the one common
``cos(lat)`` weight cancels in normalisation, so both the unfixed plain mean and
the fixed weighted mean must equal ``np.mean`` of the field. Because that plain
mean is itself the analytic answer, these tests PASS on the unfixed code and
must continue to pass after the fix.

``hypothesis`` is not installed in this environment, so the property-based
portions are realised as parametrised cases driven by pinned NumPy seeds (per
the lab's reproducibility rule), sampling many single-band grids and constant
fields across the input domain.

Tolerances:
- Single-band reduction and constant-field identity assert equality within
  ``1e-9`` K. The weighted mean of a single band is ``sum(w * x) / sum(w)`` with
  one common ``w``; algebraically this equals ``mean(x)`` exactly, and the only
  departure is double-precision round-off in the normalisation, which for
  values near 300 K sits many orders of magnitude below ``1e-9`` K. A residual
  above ``1e-9`` K would signal a weighting defect, not numerical noise.
"""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from global_mean import global_mean

REPO_ROOT = Path(__file__).resolve().parent.parent

# Pinned seeds drive the property-based sampling deterministically.
_SINGLE_BAND_SEEDS = [20261020, 101, 202, 303, 404, 505, 606, 707]
_CONSTANT_FIELD_SEEDS = [20261020, 11, 22, 33, 44, 55]


def _write_dataset(path, lat, lon, time, temp):
    """Build an xarray.Dataset with tas(time, lat, lon) and persist it to path.

    Returns the string path so global_mean(path) can open it.
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
    ds.to_netcdf(path)
    return str(path)


# ---------------------------------------------------------------------------
# 3.1 Single-latitude-band reduction to the plain mean
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", _SINGLE_BAND_SEEDS)
def test_single_band_reduces_to_plain_mean(tmp_path, seed):
    """A grid where every cell shares one latitude returns the plain mean (3.1).

    Property-based: for each pinned seed we draw a random single-latitude value,
    grid shape, and temperature field. With one common ``cos(lat)`` weight the
    weighted mean reduces to ``np.mean``, which is the analytically known answer
    for a single band -- so we assert against that value, not against the old
    code's output. Passes on unfixed and fixed code alike.
    """
    rng = np.random.default_rng(seed)

    one_lat = float(rng.uniform(-89.0, 89.0))
    n_lon = int(rng.integers(1, 7))
    n_time = int(rng.integers(1, 4))

    # Every cell shares the single latitude -> single latitude band.
    lat = np.array([one_lat], dtype="float64")
    lon = np.sort(rng.uniform(0.0, 360.0, size=n_lon)).astype("float64")
    time = np.arange(
        np.datetime64("2000-01-15"),
        np.datetime64("2000-01-15") + np.timedelta64(n_time, "D"),
    )
    temp = rng.uniform(220.0, 320.0, size=(n_time, lat.size, n_lon))

    path = _write_dataset(tmp_path / "band.nc", lat, lon, time, temp)

    analytic_plain_mean = float(np.mean(temp))
    assert abs(global_mean(path) - analytic_plain_mean) < 1e-9


def test_single_band_fixed_latitude_exact(tmp_path):
    """Deterministic single-band anchor at lat=45 with a known plain mean (3.1).

    The field values are chosen so their plain mean is exactly 275.0 K:
    values [270, 280] over two longitudes, repeated across time. The one common
    cos(45 deg) weight cancels, so the expected result is the analytic plain
    mean 275.0 K.
    """
    lat = np.array([45.0])
    lon = np.array([30.0, 210.0])
    time = np.array(["2000-03-15", "2000-09-15"], dtype="datetime64[ns]")

    temp = np.empty((time.size, lat.size, lon.size), dtype="float64")
    temp[:, 0, 0] = 270.0
    temp[:, 0, 1] = 280.0

    path = _write_dataset(tmp_path / "band45.nc", lat, lon, time, temp)

    analytic_plain_mean = 275.0
    assert float(np.mean(temp)) == analytic_plain_mean  # self-check
    assert abs(global_mean(path) - analytic_plain_mean) < 1e-9


# ---------------------------------------------------------------------------
# Constant-field preservation (part of the not-bug-condition domain)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", _CONSTANT_FIELD_SEEDS)
def test_constant_field_over_single_band_returns_constant(tmp_path, seed):
    """Random constant fields over single-band grids return the constant (3.1).

    Property-based: for each pinned seed we draw a random constant C and a
    random single-latitude-band grid, fill the field with C, and assert the
    result equals C. A (weighted) mean of identical values is a convex
    combination of C and so equals C analytically.
    """
    rng = np.random.default_rng(seed)

    C = float(rng.uniform(200.0, 330.0))
    one_lat = float(rng.uniform(-89.0, 89.0))
    n_lon = int(rng.integers(1, 6))
    n_time = int(rng.integers(1, 4))

    lat = np.array([one_lat], dtype="float64")
    lon = np.sort(rng.uniform(0.0, 360.0, size=n_lon)).astype("float64")
    time = np.arange(
        np.datetime64("2000-01-15"),
        np.datetime64("2000-01-15") + np.timedelta64(n_time, "D"),
    )
    temp = np.full((n_time, lat.size, n_lon), C, dtype="float64")

    path = _write_dataset(tmp_path / "const.nc", lat, lon, time, temp)

    assert abs(global_mean(path) - C) < 1e-9


# ---------------------------------------------------------------------------
# 3.2 Reads the tas variable
# ---------------------------------------------------------------------------

def test_reads_tas_variable(tmp_path):
    """global_mean operates on the `tas` field (3.2).

    We build a dataset whose `tas` is a single-latitude band with a known plain
    mean and add an unrelated decoy variable with a wildly different mean. If
    the function read anything other than `tas`, the result would not match the
    analytic plain mean of `tas`.
    """
    lat = np.array([15.0])
    lon = np.array([45.0, 135.0, 225.0])
    time = np.array(["2000-05-15"], dtype="datetime64[ns]")

    tas = np.array([[[260.0, 270.0, 290.0]]], dtype="float64")  # mean 273.333...
    decoy = np.full_like(tas, 1000.0)

    ds = xr.Dataset(
        {
            "tas": (("time", "lat", "lon"), tas, {"units": "K"}),
            "other": (("time", "lat", "lon"), decoy, {"units": "K"}),
        },
        coords={
            "time": ("time", time),
            "lat": ("lat", lat, {"units": "degrees_north"}),
            "lon": ("lon", lon, {"units": "degrees_east"}),
        },
    )
    path = tmp_path / "with_decoy.nc"
    ds.to_netcdf(path)

    analytic_plain_mean = float(np.mean(tas))
    assert abs(global_mean(str(path)) - analytic_plain_mean) < 1e-9
    # And emphatically not the decoy's mean.
    assert abs(global_mean(str(path)) - 1000.0) > 1.0


# ---------------------------------------------------------------------------
# 3.3 Path resolution: positional argument, default to data/sample.nc
# ---------------------------------------------------------------------------

def test_positional_path_argument_is_resolved(tmp_path):
    """A provided positional path is read as-is (3.3).

    Build a single-band grid at a non-default path and confirm global_mean reads
    it, matching that file's analytic plain mean.
    """
    lat = np.array([-30.0])
    lon = np.array([60.0, 240.0])
    time = np.array(["2000-07-15"], dtype="datetime64[ns]")
    temp = np.array([[[281.0, 285.0]]], dtype="float64")  # plain mean 283.0

    path = _write_dataset(tmp_path / "explicit.nc", lat, lon, time, temp)

    assert abs(global_mean(path) - 283.0) < 1e-9


def test_default_path_resolution_via_main():
    """Omitting the argument resolves to data/sample.nc (3.3).

    The claim under test is purely about path resolution: running the script
    with NO positional argument must behave as if ``data/sample.nc`` had been
    passed explicitly. We assert that the two invocations produce byte-identical
    stdout, so the test is independent of the aggregation math -- it holds on
    both the unfixed plain mean and the fixed area-weighted mean, because both
    invocations run the same code over the same default file. A format check on
    the output line (regex ``^Global-mean temperature: -?\\d+\\.\\d{3} K$``)
    confirms the print contract without hardcoding the numeric value, honouring
    the lab rule against asserting values that are not known-correct.
    """
    sample = REPO_ROOT / "data" / "sample.nc"
    assert sample.exists(), "data/sample.nc is required for the default-path test"

    default_run = subprocess.run(
        [sys.executable, "global_mean.py"],  # no positional argument
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    explicit_run = subprocess.run(
        [sys.executable, "global_mean.py", "data/sample.nc"],  # explicit path
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert default_run.returncode == 0
    assert explicit_run.returncode == 0
    # Default path resolution must match the explicit-path invocation exactly.
    assert default_run.stdout == explicit_run.stdout

    # Confirm the print format without pinning the (possibly-buggy) numeric value.
    format_re = re.compile(r"^Global-mean temperature: -?\d+\.\d{3} K$")
    assert any(
        format_re.match(line) for line in default_run.stdout.splitlines()
    ), f"no formatted output line found in: {default_run.stdout!r}"


# ---------------------------------------------------------------------------
# 3.4 Return type and print format
# ---------------------------------------------------------------------------

def test_return_type_is_python_float(tmp_path):
    """global_mean returns a builtin Python float, not a numpy scalar (3.4)."""
    lat = np.array([5.0])
    lon = np.array([100.0, 300.0])
    time = np.array(["2000-08-15"], dtype="datetime64[ns]")
    temp = np.array([[[301.0, 299.0]]], dtype="float64")

    path = _write_dataset(tmp_path / "typecheck.nc", lat, lon, time, temp)

    result = global_mean(path)
    assert type(result) is float


def test_main_print_format_matches_exactly(tmp_path):
    """The __main__ block prints the exact expected format line (3.4).

    Build a single-band grid with a known plain mean, run the script with that
    file as the positional argument, and assert the output line matches
    "Global-mean temperature: {value:.3f} K" exactly, where value is the
    analytic plain mean. The single-band reduction makes the printed value
    predictable on both unfixed and fixed code.
    """
    lat = np.array([20.0])
    lon = np.array([70.0, 250.0])
    time = np.array(["2000-04-15"], dtype="datetime64[ns]")
    temp = np.array([[[271.0, 277.0]]], dtype="float64")  # plain mean 274.0

    path = _write_dataset(tmp_path / "format.nc", lat, lon, time, temp)

    analytic_plain_mean = 274.0
    assert float(np.mean(temp)) == analytic_plain_mean  # self-check

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "global_mean.py"), path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    expected_line = f"Global-mean temperature: {analytic_plain_mean:.3f} K"
    assert expected_line in result.stdout.splitlines()
    # Exact format: three decimal places and the trailing " K".
    assert "Global-mean temperature: 274.000 K" in result.stdout
