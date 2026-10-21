"""Global-mean near-surface temperature from a NetCDF file.

Usage:
    python global_mean.py data/sample.nc
"""
import sys

import numpy as np
import xarray as xr


def global_mean(path):
    ds = xr.open_dataset(path)
    temp = ds["tas"].values                       # (time, lat, lon)
    lat_bnds = np.radians(ds["lat_bnds"].values)  # (lat, 2)
    lon_bnds = np.radians(ds["lon_bnds"].values)  # (lon, 2)

    dsin_lat = np.sin(lat_bnds[:, 1]) - np.sin(lat_bnds[:, 0])  # (lat,)
    dlon = lon_bnds[:, 1] - lon_bnds[:, 0]                      # (lon,)
    area = dsin_lat[:, None] * dlon[None, :]                    # (lat, lon)

    w = np.broadcast_to(area, temp.shape)         # (time, lat, lon)
    return float(np.sum(temp * w) / np.sum(w))    # area-weighted, time-averaged


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/sample.nc"
    print(f"Global-mean temperature: {global_mean(path):.3f} K")
