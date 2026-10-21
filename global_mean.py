"""Global-mean near-surface temperature from a NetCDF file.

Usage:
    python global_mean.py data/sample.nc
"""
import sys

import numpy as np
import xarray as xr


def global_mean(path):
    ds = xr.open_dataset(path)
    # Area-weight by cos(latitude): cells near the poles cover less surface
    # area on a regular lat-lon grid. Longitude/time cells at a fixed latitude
    # share equal area, so only latitude carries a relative weight.
    w_da = xr.DataArray(np.cos(np.deg2rad(ds["lat"])), dims="lat")
    mean = ds["tas"].weighted(w_da).mean(("time", "lat", "lon"))
    return float(mean)               # area-weighted global mean


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/sample.nc"
    print(f"Global-mean temperature: {global_mean(path):.3f} K")
