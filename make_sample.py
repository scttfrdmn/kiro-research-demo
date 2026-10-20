"""Build data/sample.nc: a synthetic monthly surface-air-temperature field.

Deterministic (fixed seed), so every run produces the same bytes' worth of
values. The field is shaped like Earth's: warm tropics, cold poles, a
seasonal cycle that flips between hemispheres, and a little noise.

    T(lat, lon, t) = 300 - 50 sin^2(lat)
                     + 3 cos(lat) cos(lon)
                     + 5 sin(lat) cos(2*pi*t/12)
                     + noise(sd = 0.5 K)

Grid: 2-degree cells, latitude centres -89..89, longitude centres 1..359,
12 monthly time steps (mid-month, year 2000). Cell bounds are written as
lat_bnds / lon_bnds, following the CF conventions.
"""
import numpy as np
import xarray as xr

SEED = 20261020

lat = np.arange(-89.0, 90.0, 2.0)
lon = np.arange(1.0, 360.0, 2.0)
time = np.array([f"2000-{m:02d}-15" for m in range(1, 13)], dtype="datetime64[ns]")

phi = np.deg2rad(lat)[None, :, None]
lam = np.deg2rad(lon)[None, None, :]
t = np.arange(12)[:, None, None]

rng = np.random.default_rng(SEED)
temp = (
    300.0
    - 50.0 * np.sin(phi) ** 2
    + 3.0 * np.cos(phi) * np.cos(lam)
    + 5.0 * np.sin(phi) * np.cos(2 * np.pi * t / 12)
    + rng.normal(0.0, 0.5, size=(time.size, lat.size, lon.size))
)

ds = xr.Dataset(
    {"tas": (("time", "lat", "lon"), temp.astype("float64"),
             {"units": "K", "long_name": "near-surface air temperature"})},
    coords={
        "time": ("time", time),
        "lat": ("lat", lat, {"units": "degrees_north", "bounds": "lat_bnds"}),
        "lon": ("lon", lon, {"units": "degrees_east", "bounds": "lon_bnds"}),
        "lat_bnds": (("lat", "nv"), np.stack([lat - 1.0, lat + 1.0], axis=1)),
        "lon_bnds": (("lon", "nv"), np.stack([lon - 1.0, lon + 1.0], axis=1)),
    },
    attrs={"title": "Synthetic monthly temperature field for the Kiro demo",
           "seed": SEED},
)
ds.to_netcdf("data/sample.nc", encoding={"time": {"units": "days since 2000-01-01"}})
print("wrote data/sample.nc", dict(ds.sizes))
