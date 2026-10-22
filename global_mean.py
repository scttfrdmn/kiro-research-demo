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

    # True unit-sphere cell areas from the grid cell edges (degrees -> radians).
    lat_bnds = np.deg2rad(ds["lat_bnds"].values)   # (lat, 2)
    lon_bnds = np.deg2rad(ds["lon_bnds"].values)   # (lon, 2)
    d_sin = np.sin(lat_bnds[:, 1]) - np.sin(lat_bnds[:, 0])   # per-lat band
    d_lon = lon_bnds[:, 1] - lon_bnds[:, 0]                   # per-lon width
    area = np.outer(d_sin, d_lon)    # (lat, lon)

    tas_tmean = temp.mean(axis=0)    # unweighted time average -> (lat, lon)

    # Area-weighted spatial mean.
    return float(np.sum(area * tas_tmean) / np.sum(area))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/sample.nc"
    print(f"Global-mean temperature: {global_mean(path):.3f} K")
