"""Global-mean near-surface temperature from a NetCDF file.

Usage:
    python global_mean.py data/sample.nc
"""
import sys

import numpy as np
import xarray as xr


def global_mean(path):
    ds = xr.open_dataset(path)
    temp = ds["tas"].values          # (time, lat, lon)
    return float(np.mean(temp))      # mean over every grid point


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/sample.nc"
    print(f"Global-mean temperature: {global_mean(path):.3f} K")
