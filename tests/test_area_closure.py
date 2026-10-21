"""Area-closure identity test for area-weighted global mean.

Property 1: Expected Behavior - Area-Weighted Mean Uses Cosine-of-Latitude
Weights (analytic area anchor).

**Validates: Requirements 2.4**

Per-cell areas derived from the CF-convention ``lat_bnds`` / ``lon_bnds`` over
the full sphere must sum to ``4*pi`` steradians (the total solid angle of the
unit sphere). The area element is integrated in closed form over each cell:

    area(cell) = (sin(deg2rad(lat_hi)) - sin(deg2rad(lat_lo)))
                 * deg2rad(lon_hi - lon_lo)

which is the exact integral of ``cos(phi) d_phi d_lambda`` over the latitude
band ``[lat_lo, lat_hi]`` and longitude span ``[lon_lo, lon_hi]`` on the unit
sphere.

IMPORTANT: this exact band-area formula lives in the TEST ONLY. The production
aggregation in ``global_mean.py`` uses ``cos(lat)`` centre weighting and never
reads the bounds. This test is the independent analytic anchor that confirms
the area derivation standing behind that cosine weighting; it does not exercise
the aggregation path.

Tolerance -- 1e-12 relative, justification:
The sample grid's latitude band edges run -90..90 and its longitude band edges
run 0..360, so the bands tile the sphere completely with no gaps or overlaps.
Summing ``(sin(lat_hi) - sin(lat_lo))`` over the complete, contiguous latitude
bands telescopes/integrates analytically to ``sin(90 deg) - sin(-90 deg) = 2``,
and multiplying by the full ``2*pi`` longitude span gives exactly ``4*pi``. The
only departure from ``4*pi`` is accumulated double-precision round-off over the
~16200 cells of the sample grid (90 lat bands x 180 lon bands), which sits at
the ``1e-12`` relative level. A residual larger than that would indicate an
error in the area formula rather than floating-point noise.
"""
import numpy as np
import xarray as xr
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Relative tolerance on the full-sphere area sum vs. 4*pi (see module docstring).
_REL_TOL = 1e-12


def _cell_areas_from_bounds(lat_bnds, lon_bnds):
    """Exact unit-sphere cell areas from CF bounds (test-only, not production).

    Parameters
    ----------
    lat_bnds : array-like, shape (nlat, 2)
        Lower and upper latitude edge of every cell, in degrees.
    lon_bnds : array-like, shape (nlon, 2)
        Lower and upper longitude edge of every cell, in degrees.

    Returns
    -------
    numpy.ndarray, shape (nlat, nlon)
        Per-cell solid angle on the unit sphere, integrated in closed form:
        ``(sin(lat_hi) - sin(lat_lo)) * deg2rad(lon_hi - lon_lo)``.
    """
    lat_bnds = np.asarray(lat_bnds, dtype="float64")
    lon_bnds = np.asarray(lon_bnds, dtype="float64")

    # Latitude factor: sin(deg2rad(lat_hi)) - sin(deg2rad(lat_lo)), one per band.
    dsin_lat = np.sin(np.deg2rad(lat_bnds[:, 1])) - np.sin(np.deg2rad(lat_bnds[:, 0]))
    # Longitude factor: angular span of each cell in radians, one per band.
    dlon = np.deg2rad(lon_bnds[:, 1] - lon_bnds[:, 0])

    # Outer product -> (nlat, nlon) per-cell areas.
    return dsin_lat[:, None] * dlon[None, :]


def _build_sample_bounds():
    """Reconstruct the sample grid's lat_bnds/lon_bnds like make_sample.py.

    2-degree cells, latitude centres -89..89 with ``lat_bnds = [lat-1, lat+1]``
    (edges -90..90), longitude centres 1..359 with ``lon_bnds = [lon-1, lon+1]``
    (edges 0..360). The complete edges make the bands tile the sphere exactly.
    """
    lat = np.arange(-89.0, 90.0, 2.0)
    lon = np.arange(1.0, 360.0, 2.0)
    lat_bnds = np.stack([lat - 1.0, lat + 1.0], axis=1)
    lon_bnds = np.stack([lon - 1.0, lon + 1.0], axis=1)
    return lat_bnds, lon_bnds


def test_area_closure_in_memory_sample_grid():
    """In-memory sample-like grid: cell areas sum to 4*pi within 1e-12 (2.4).

    Build lat_bnds/lon_bnds exactly as make_sample.py does (2-degree cells,
    complete -90..90 / 0..360 edges) and confirm the closed-form per-cell areas
    sum to the full-sphere solid angle ``4*pi`` within relative tolerance 1e-12.
    """
    lat_bnds, lon_bnds = _build_sample_bounds()

    areas = _cell_areas_from_bounds(lat_bnds, lon_bnds)
    total = float(areas.sum())

    expected = 4.0 * np.pi
    rel_err = abs(total - expected) / expected

    # Visible in -v / failure output: the computed sum and its relative error.
    print(f"[in-memory] sphere-area sum = {total!r}, "
          f"4*pi = {expected!r}, relative error = {rel_err:.3e}")

    assert rel_err < _REL_TOL, (
        f"in-memory area sum {total!r} differs from 4*pi {expected!r} "
        f"by relative error {rel_err:.3e} (tol {_REL_TOL:.0e})"
    )


def test_area_closure_on_disk_sample_nc():
    """On-disk data/sample.nc: cell areas sum to 4*pi within 1e-12 (2.4).

    Read ``lat_bnds`` and ``lon_bnds`` straight from the persisted sample file
    and confirm the closed-form areas close to the sphere, so the identity holds
    on the actual on-disk grid, not only an in-memory fixture.
    """
    sample = REPO_ROOT / "data" / "sample.nc"
    assert sample.exists(), "data/sample.nc is required for the area-closure test"

    with xr.open_dataset(sample) as ds:
        lat_bnds = ds["lat_bnds"].values
        lon_bnds = ds["lon_bnds"].values

    areas = _cell_areas_from_bounds(lat_bnds, lon_bnds)
    total = float(areas.sum())

    expected = 4.0 * np.pi
    rel_err = abs(total - expected) / expected

    print(f"[on-disk]   sphere-area sum = {total!r}, "
          f"4*pi = {expected!r}, relative error = {rel_err:.3e}")

    assert rel_err < _REL_TOL, (
        f"on-disk area sum {total!r} differs from 4*pi {expected!r} "
        f"by relative error {rel_err:.3e} (tol {_REL_TOL:.0e})"
    )
