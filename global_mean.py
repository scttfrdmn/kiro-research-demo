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
    lat = ds["lat"].values           # (lat,)
    w = np.cos(np.deg2rad(lat))      # cos(lat) area weight, 1-D over lat
    # Broadcast the weight onto the lat axis (axis=1) of (time, lat, lon) and
    # take a convex-combination weighted mean: normalise by the summed weights
    # over the same elements, so a constant field returns the constant exactly
    # and a single latitude band reduces to the plain mean.
    w_broadcast = np.broadcast_to(w[np.newaxis, :, np.newaxis], temp.shape)
    return float(np.sum(temp * w_broadcast) / np.sum(w_broadcast))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/sample.nc"
    print(f"Global-mean temperature: {global_mean(path):.3f} K")
