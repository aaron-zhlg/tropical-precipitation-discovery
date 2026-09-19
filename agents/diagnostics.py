"""Frozen climate diagnostics used by the subagents.

Index boxes follow the 2026 Nature Communications tropical-rainfall paper.
Results are cached as JSON under ``runs/``. Agents call these functions; they
do not invent new index definitions at runtime.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from agents.paths import (
    DATASET_ROOT,
    HISTORICAL_END,
    PERIOD_END,
    PERIOD_START,
    RUNS_ROOT,
    TROPICS,
)

# Paper methods: Walker Circulation Index, IPWP, EEPO, PAI.
WALKER_EAST = dict(lat=(-5.0, 5.0), lon=(200.0, 280.0))  # 160W-80W
WALKER_WEST = dict(lat=(-5.0, 5.0), lon=(80.0, 160.0))  # 80E-160E
IPWP_BOX = dict(lat=(-5.0, 5.0), lon=(80.0, 150.0))
EEPO_BOX = dict(lat=(-5.0, 5.0), lon=(180.0, 280.0))  # 180-80W
PAI_NH = dict(lat=(0.0, 20.0))
PAI_SH = dict(lat=(-20.0, 0.0))
PAI_TROP = dict(lat=(-20.0, 20.0))
ITCZ_PACIFIC = dict(lat=(-20.0, 20.0), lon=(160.0, 270.0))
COLD_TONGUE = dict(lat=(-5.0, 5.0), lon=(180.0, 270.0))

OBS_FILES = {
    "gpcp": DATASET_ROOT / "gpcp" / "precip.mon.mean.nc",
    "oisst": DATASET_ROOT / "oisst" / "sst.mon.mean.nc",
    "ncep2_mslp": DATASET_ROOT / "ncep2" / "mslp.mon.mean.nc",
    "berkeley": DATASET_ROOT / "berkeley_earth" / "Land_and_Ocean_LatLong1.nc",
}

CMIP6_EXPERIMENTS = ("historical", "ssp245")


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, Path):
        return str(value)
    return value


def cache_write(relpath: str, payload: dict[str, Any]) -> Path:
    path = RUNS_ROOT / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
    return path


def cache_read(relpath: str) -> dict[str, Any] | None:
    path = RUNS_ROOT / relpath
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _drop_bounds(path: Path) -> list[str]:
    with xr.open_dataset(path, decode_times=False) as raw:
        return [name for name in raw.variables if "bnds" in name.lower() or name.endswith("_bounds")]


def open_nc(path: Path) -> xr.Dataset:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    ds = xr.open_dataset(path, drop_variables=_drop_bounds(path) or None)
    if "time" in ds.coords and np.issubdtype(ds["time"].dtype, np.floating):
        year = np.floor(ds["time"].values)
        month = np.clip(np.round((ds["time"].values - year) * 12.0 + 0.5), 1, 12)
        times = pd.to_datetime({"year": year.astype(int), "month": month.astype(int), "day": 15})
        ds = ds.assign_coords(time=("time", times.to_numpy()))
    elif "time" in ds.coords:
        try:
            times = pd.to_datetime([str(v)[:19].replace("T", " ") for v in ds["time"].values])
            ds = ds.assign_coords(time=("time", times.to_numpy()))
        except (ValueError, TypeError):
            pass
    return ds


def _lat_name(da: xr.DataArray) -> str:
    for name in ("lat", "latitude"):
        if name in da.coords or name in da.dims:
            return name
    raise KeyError(f"no latitude coordinate on {da.name}")


def _lon_name(da: xr.DataArray) -> str:
    for name in ("lon", "longitude"):
        if name in da.coords or name in da.dims:
            return name
    raise KeyError(f"no longitude coordinate on {da.name}")


def _to_lon360(lon: xr.DataArray) -> xr.DataArray:
    wrapped = (lon.astype("float64") + 360.0) % 360.0
    return wrapped


def _sel_lat(da: xr.DataArray, lat_min: float, lat_max: float) -> xr.DataArray:
    name = _lat_name(da)
    lat = da[name]
    if float(lat[0]) > float(lat[-1]):
        return da.sel({name: slice(lat_max, lat_min)})
    return da.sel({name: slice(lat_min, lat_max)})


def _sel_lon(da: xr.DataArray, lon_west: float, lon_east: float) -> xr.DataArray:
    name = _lon_name(da)
    lon360 = _to_lon360(da[name])
    west = lon_west % 360.0
    east = lon_east % 360.0
    work = da.assign_coords({name: lon360}).sortby(name)
    if west <= east:
        return work.sel({name: slice(west, east)})
    left = work.sel({name: slice(west, 360.0)})
    right = work.sel({name: slice(0.0, east)})
    return xr.concat([left, right], dim=name)


def _sel_box(da: xr.DataArray, lat: tuple[float, float], lon: tuple[float, float] | None = None) -> xr.DataArray:
    out = _sel_lat(da, lat[0], lat[1])
    if lon is not None:
        out = _sel_lon(out, lon[0], lon[1])
    return out


def _sel_years(da: xr.DataArray, start: int, end: int) -> xr.DataArray:
    return da.sel(time=slice(f"{start}-01-01", f"{end}-12-31"))


def area_mean(da: xr.DataArray) -> xr.DataArray:
    lat = da[_lat_name(da)]
    weights = np.cos(np.deg2rad(lat))
    return da.weighted(weights).mean(dim=[_lat_name(da), _lon_name(da)])


def annual_mean(da: xr.DataArray) -> xr.DataArray:
    return da.resample(time="YS").mean()


def linear_trend(series: xr.DataArray) -> dict[str, float]:
    years = series["time"].dt.year.astype("float64")
    y = series.astype("float64")
    valid = np.isfinite(y.values) & np.isfinite(years.values)
    if valid.sum() < 8:
        return {"slope_per_year": float("nan"), "n": int(valid.sum())}
    slope = np.polyfit(years.values[valid], y.values[valid], 1)[0]
    return {"slope_per_year": float(slope), "n": int(valid.sum())}


def _first_var(ds: xr.Dataset, names: tuple[str, ...]) -> xr.DataArray:
    for name in names:
        if name in ds.data_vars:
            return ds[name]
    raise KeyError(f"none of {names} in {list(ds.data_vars)}")


def to_mm_day(da: xr.DataArray) -> xr.DataArray:
    units = str(da.attrs.get("units", "")).lower()
    if "kg" in units or "s-1" in units:
        return da * 86400.0
    return da


def catalog() -> dict[str, Any]:
    obs = {}
    for key, path in OBS_FILES.items():
        obs[key] = {"path": str(path), "exists": path.is_file(), "bytes": path.stat().st_size if path.is_file() else 0}

    models: dict[str, dict[str, list[str]]] = {}
    cmip6 = DATASET_ROOT / "cmip6"
    if cmip6.is_dir():
        for path in sorted(cmip6.glob("*/*/*.nc")):
            match = re.search(r"_(ACCESS-|BCC-|CESM|CanESM|GFDL-|IPSL-|MIROC|MPI-|MRI-|NorESM|TaiESM)[^_]*", path.name)
            source = path.name.split("_")[2] if path.name.startswith(("pr_", "tas_", "tos_", "psl_")) else None
            if source is None:
                parts = path.name.split("_")
                source = parts[2] if len(parts) > 2 else path.stem
            experiment = path.parent.parent.name
            variable = path.parent.name
            models.setdefault(source, {}).setdefault(f"{experiment}:{variable}", []).append(path.name)

    return {
        "dataset_root": str(DATASET_ROOT),
        "period": f"{PERIOD_START}-{PERIOD_END}",
        "observations": obs,
        "cmip6_models": sorted(models),
        "cmip6_files": models,
    }


def _obs_da(dataset: str) -> tuple[xr.DataArray, str]:
    if dataset == "gpcp":
        da = _first_var(open_nc(OBS_FILES["gpcp"]), ("precip", "pr"))
        return to_mm_day(da), "mm/day"
    if dataset == "oisst":
        da = _first_var(open_nc(OBS_FILES["oisst"]), ("sst", "tos"))
        return _sel_lat(da, -10.0, 10.0), "degC"
    if dataset == "ncep2":
        da = _first_var(open_nc(OBS_FILES["ncep2_mslp"]), ("mslp", "psl"))
        return da, str(da.attrs.get("units", "Pa"))
    if dataset == "berkeley":
        da = _first_var(open_nc(OBS_FILES["berkeley"]), ("temperature", "tas"))
        return da, "degC"
    raise ValueError(f"unknown observational dataset: {dataset}")


def walker_index(dataset: str = "ncep2", start: int = PERIOD_START, end: int = PERIOD_END) -> dict[str, Any]:
    da, units = _obs_da(dataset)
    da = _sel_years(da, start, end)
    east = area_mean(_sel_box(da, WALKER_EAST["lat"], WALKER_EAST["lon"]))
    west = area_mean(_sel_box(da, WALKER_WEST["lat"], WALKER_WEST["lon"]))
    index = annual_mean(east - west)
    trend = linear_trend(index)
    payload = {
        "index": "walker_wci",
        "dataset": dataset,
        "definition": "SLP east (5S-5N, 160W-80W) minus west (5S-5N, 80E-160E)",
        "units": units,
        "period": f"{start}-{end}",
        **trend,
        "source": str(OBS_FILES["ncep2_mslp"] if dataset == "ncep2" else dataset),
    }
    cache_write(f"diagnostics/obs/{dataset}_walker.json", payload)
    return payload


def land_sea_contrast(dataset: str = "berkeley", start: int = PERIOD_START, end: int = PERIOD_END) -> dict[str, Any]:
    ds = open_nc(OBS_FILES["berkeley"])
    tas = _sel_years(ds["temperature"], start, end)
    mask = ds["land_mask"]
    land = tas.where(mask >= 0.5)
    ocean = tas.where(mask < 0.5)
    index = annual_mean(area_mean(land) - area_mean(ocean))
    trend = linear_trend(index)
    payload = {
        "index": "land_sea_contrast",
        "dataset": dataset,
        "definition": "area-mean land t2m minus ocean t2m (Berkeley Earth land_mask)",
        "units": "degC",
        "period": f"{start}-{end}",
        **trend,
        "source": str(OBS_FILES["berkeley"]),
    }
    cache_write(f"diagnostics/obs/{dataset}_land_sea.json", payload)
    return payload


def ipwp_eepo(dataset: str = "oisst", start: int = max(PERIOD_START, 1981), end: int = PERIOD_END) -> dict[str, Any]:
    da, units = _obs_da("oisst")
    da = _sel_years(da, start, end)
    ipwp = annual_mean(area_mean(_sel_box(da, IPWP_BOX["lat"], IPWP_BOX["lon"])))
    eepo = annual_mean(area_mean(_sel_box(da, EEPO_BOX["lat"], EEPO_BOX["lon"])))
    grad = ipwp - eepo
    payload = {
        "index": "ipwp_eepo",
        "dataset": dataset,
        "units": units,
        "period": f"{start}-{end}",
        "ipwp_trend_per_year": linear_trend(ipwp)["slope_per_year"],
        "eepo_trend_per_year": linear_trend(eepo)["slope_per_year"],
        "ipwp_minus_eepo_trend_per_year": linear_trend(grad)["slope_per_year"],
        "n": linear_trend(ipwp)["n"],
        "source": str(OBS_FILES["oisst"]),
        "note": "OISST v2.1 highres starts 1981-09; period is the overlap with 1979-2024",
    }
    cache_write(f"diagnostics/obs/{dataset}_ipwp_eepo.json", payload)
    return payload


def precip_pai(dataset: str = "gpcp", start: int = PERIOD_START, end: int = PERIOD_END) -> dict[str, Any]:
    da, units = _obs_da("gpcp")
    da = _sel_years(da, start, end)
    nh = annual_mean(area_mean(_sel_box(da, PAI_NH["lat"])))
    sh = annual_mean(area_mean(_sel_box(da, PAI_SH["lat"])))
    trop = annual_mean(area_mean(_sel_box(da, PAI_TROP["lat"])))
    pai = (nh - sh) / trop
    trop_mean = annual_mean(area_mean(_sel_box(da, TROPICS)))
    payload = {
        "index": "precip_pai",
        "dataset": dataset,
        "units": "dimensionless_pai; trop_mean in " + units,
        "period": f"{start}-{end}",
        "pai_trend_per_year": linear_trend(pai)["slope_per_year"],
        "tropical_mean_trend_mm_day_per_year": linear_trend(trop_mean)["slope_per_year"],
        "n": linear_trend(pai)["n"],
        "source": str(OBS_FILES["gpcp"]),
    }
    cache_write(f"diagnostics/obs/{dataset}_pai.json", payload)
    return payload


def precip_trend_map(dataset: str = "gpcp", start: int = PERIOD_START, end: int = PERIOD_END) -> xr.DataArray:
    da, _ = _obs_da("gpcp")
    da = _sel_box(_sel_years(da, start, end), TROPICS)
    annual = annual_mean(da)
    years = annual["time"].dt.year.astype("float64")
    year0 = years - years.mean()
    trend = (annual * year0).mean("time") / (year0**2).mean("time")
    trend.name = "precip_trend"
    trend.attrs["units"] = "mm/day/year"
    return trend


def _cmip6_files(model: str, variable: str) -> list[Path]:
    files: list[Path] = []
    root = DATASET_ROOT / "cmip6"
    for experiment in CMIP6_EXPERIMENTS:
        folder = root / experiment / variable
        if not folder.is_dir():
            continue
        files.extend(sorted(folder.glob(f"{variable}_*_{model}_*.nc")))
    return files


def list_cmip6_models() -> list[str]:
    names = set()
    root = DATASET_ROOT / "cmip6"
    if not root.is_dir():
        return []
    for path in root.glob("*/*/*.nc"):
        parts = path.name.split("_")
        if len(parts) >= 3:
            names.add(parts[2])
    return sorted(names)


def open_cmip6(model: str, variable: str, start: int = PERIOD_START, end: int = PERIOD_END) -> xr.DataArray:
    files = _cmip6_files(model, variable)
    if not files:
        raise FileNotFoundError(f"no CMIP6 {variable} files for {model}")
    datasets = [open_nc(path) for path in files]
    ds = xr.concat(datasets, dim="time") if len(datasets) > 1 else datasets[0]
    ds = ds.sortby("time")
    da = _first_var(ds, (variable,))
    if variable == "pr":
        da = to_mm_day(da)
    da = _sel_years(da, start, min(end, int(pd.Timestamp(da["time"].values[-1]).year)))
    _, index = np.unique(da["time"].values, return_index=True)
    return da.isel(time=index)


def model_coverage(model: str) -> dict[str, Any]:
    coverage = {"model": model, "variables": {}}
    for variable in ("pr", "tas", "tos", "psl"):
        files = _cmip6_files(model, variable)
        coverage["variables"][variable] = {
            "n_files": len(files),
            "files": [p.name for p in files],
        }
    return coverage


def _pattern_correlation(model_trend: xr.DataArray, obs_trend: xr.DataArray) -> float:
    lat_name = _lat_name(obs_trend)
    lon_name = _lon_name(obs_trend)
    interp = model_trend.interp({_lat_name(model_trend): obs_trend[lat_name], _lon_name(model_trend): obs_trend[lon_name]})
    aligned = xr.align(interp, obs_trend, join="inner")
    a, b = aligned
    weights = np.cos(np.deg2rad(a[lat_name]))
    a = a.astype("float64")
    b = b.astype("float64")
    mask = np.isfinite(a.values) & np.isfinite(b.values)
    if mask.sum() < 50:
        return float("nan")
    aw = a.where(mask)
    bw = b.where(mask)
    w = weights
    a_mean = aw.weighted(w).mean()
    b_mean = bw.weighted(w).mean()
    cov = ((aw - a_mean) * (bw - b_mean)).weighted(w).mean()
    va = ((aw - a_mean) ** 2).weighted(w).mean()
    vb = ((bw - b_mean) ** 2).weighted(w).mean()
    denom = float(np.sqrt(va * vb))
    if denom == 0:
        return float("nan")
    return float(cov / denom)


def model_precip_skill(model: str, start: int = PERIOD_START, end: int = HISTORICAL_END) -> dict[str, Any]:
    obs_trend = precip_trend_map("gpcp", start, end)
    pr = _sel_box(open_cmip6(model, "pr", start, end), TROPICS)
    annual = annual_mean(pr)
    years = annual["time"].dt.year.astype("float64")
    year0 = years - years.mean()
    trend = (annual * year0).mean("time") / (year0**2).mean("time")
    skill = _pattern_correlation(trend, obs_trend)
    payload = {
        "model": model,
        "index": "precip_skill_vs_gpcp",
        "period": f"{start}-{end}",
        "pattern_correlation": skill,
        "obs": "gpcp",
        "note": "historical-only end year is used when SSP2-4.5 is absent",
    }
    cache_write(f"diagnostics/models/{model}_precip_skill.json", payload)
    return payload


def model_walker(model: str, start: int = PERIOD_START, end: int = HISTORICAL_END) -> dict[str, Any]:
    da = open_cmip6(model, "psl", start, end)
    east = area_mean(_sel_box(da, WALKER_EAST["lat"], WALKER_EAST["lon"]))
    west = area_mean(_sel_box(da, WALKER_WEST["lat"], WALKER_WEST["lon"]))
    trend = linear_trend(annual_mean(east - west))
    payload = {"model": model, "index": "walker_wci", "period": f"{start}-{end}", **trend}
    cache_write(f"diagnostics/models/{model}_walker.json", payload)
    return payload


def model_thermal_drivers(model: str, start: int = PERIOD_START, end: int = HISTORICAL_END) -> dict[str, Any]:
    tas = open_cmip6(model, "tas", start, end)
    mask_ds = open_nc(OBS_FILES["berkeley"])
    land_mask = mask_ds["land_mask"]
    model_lon = tas[_lon_name(tas)]
    lon180 = ((model_lon + 180.0) % 360.0) - 180.0
    land_on_model = land_mask.interp(
        latitude=tas[_lat_name(tas)],
        longitude=lon180,
    )
    land = tas.where(land_on_model >= 0.5)
    ocean = tas.where(land_on_model < 0.5)
    ls = linear_trend(annual_mean(area_mean(land) - area_mean(ocean)))
    tos = open_cmip6(model, "tos", start, end)
    ipwp = linear_trend(annual_mean(area_mean(_sel_box(tos, IPWP_BOX["lat"], IPWP_BOX["lon"]))))
    payload = {
        "model": model,
        "index": "thermal_drivers",
        "period": f"{start}-{end}",
        "land_sea_trend_per_year": ls["slope_per_year"],
        "ipwp_trend_per_year": ipwp["slope_per_year"],
    }
    cache_write(f"diagnostics/models/{model}_thermal.json", payload)
    return payload


def model_mean_state_bias(model: str, start: int = PERIOD_START, end: int = HISTORICAL_END) -> dict[str, Any]:
    pr = _sel_years(open_cmip6(model, "pr", start, end), start, end)
    obs = _sel_years(_obs_da("gpcp")[0], start, end)
    model_clim = _sel_box(pr.mean("time"), ITCZ_PACIFIC["lat"], ITCZ_PACIFIC["lon"])
    obs_clim = _sel_box(obs.mean("time"), ITCZ_PACIFIC["lat"], ITCZ_PACIFIC["lon"])
    model_nh = float(area_mean(_sel_lat(model_clim, 0.0, 20.0)))
    model_sh = float(area_mean(_sel_lat(model_clim, -20.0, 0.0)))
    obs_nh = float(area_mean(_sel_lat(obs_clim, 0.0, 20.0)))
    obs_sh = float(area_mean(_sel_lat(obs_clim, -20.0, 0.0)))
    double_itcz = (model_sh - model_nh) - (obs_sh - obs_nh)

    cold_tongue = float("nan")
    try:
        tos = open_cmip6(model, "tos", start, end).mean("time")
        sst = _sel_years(_obs_da("oisst")[0], max(start, 1981), end).mean("time")
        model_ct = float(area_mean(_sel_box(tos, COLD_TONGUE["lat"], COLD_TONGUE["lon"])))
        obs_ct = float(area_mean(_sel_box(sst, COLD_TONGUE["lat"], COLD_TONGUE["lon"])))
        cold_tongue = model_ct - obs_ct
    except FileNotFoundError:
        pass

    payload = {
        "model": model,
        "index": "mean_state_bias",
        "period": f"{start}-{end}",
        "double_itcz_bias_mm_day": double_itcz,
        "cold_tongue_bias_degC": cold_tongue,
        "definition": "Pacific SH-minus-NH precip clim minus GPCP; EEP SST clim minus OISST",
    }
    cache_write(f"diagnostics/models/{model}_mean_state.json", payload)
    return payload


def model_h1_row(model: str) -> dict[str, Any]:
    coverage = model_coverage(model)
    row: dict[str, Any] = {"model": model, "coverage": coverage["variables"]}
    errors: dict[str, str] = {}
    try:
        row["precip_skill"] = model_precip_skill(model)
    except Exception as exc:  # noqa: BLE001 — report missing/partial files to the agent
        errors["precip_skill"] = str(exc)
    try:
        row["mean_state"] = model_mean_state_bias(model)
    except Exception as exc:  # noqa: BLE001
        errors["mean_state"] = str(exc)
    try:
        row["thermal"] = model_thermal_drivers(model)
    except Exception as exc:  # noqa: BLE001
        errors["thermal"] = str(exc)
    try:
        row["walker"] = model_walker(model)
    except Exception as exc:  # noqa: BLE001
        errors["walker"] = str(exc)
    if errors:
        row["errors"] = errors
    cache_write(f"diagnostics/models/{model}_h1_row.json", row)
    return row


def observational_fingerprint() -> dict[str, Any]:
    payload = {
        "period": f"{PERIOD_START}-{PERIOD_END}",
        "gpcp_pai": precip_pai(),
        "ncep2_walker": walker_index(),
        "berkeley_land_sea": land_sea_contrast(),
        "oisst_ipwp_eepo": ipwp_eepo(),
    }
    cache_write("diagnostics/obs/fingerprint.json", payload)
    return payload


def load_h1_table() -> list[dict[str, Any]]:
    folder = RUNS_ROOT / "diagnostics" / "models"
    if not folder.is_dir():
        return []
    rows = []
    for path in sorted(folder.glob("*_h1_row.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def pearson(xs: list[float], ys: list[float]) -> float | None:
    a = np.array(xs, dtype=float)
    b = np.array(ys, dtype=float)
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 4:
        return None
    return float(np.corrcoef(a[mask], b[mask])[0, 1])


def test_h1() -> dict[str, Any]:
    rows = load_h1_table()
    skill, bias, land_sea, ipwp = [], [], [], []
    used = []
    for row in rows:
        s = (row.get("precip_skill") or {}).get("pattern_correlation")
        if s is None:
            s = row.get("pattern_correlation")
        b = (row.get("mean_state") or {}).get("double_itcz_bias_mm_day")
        ls = (row.get("thermal") or {}).get("land_sea_trend_per_year")
        ip = (row.get("thermal") or {}).get("ipwp_trend_per_year")
        if s is None:
            continue
        used.append(row["model"])
        skill.append(float(s))
        bias.append(float(b) if b is not None else float("nan"))
        land_sea.append(float(ls) if ls is not None else float("nan"))
        ipwp.append(float(ip) if ip is not None else float("nan"))

    r_bias = pearson(skill, bias)
    r_ls = pearson(skill, land_sea)
    r_ipwp = pearson(skill, ipwp)
    # H1: |r_bias| > |r_ls| and |r_bias| > |r_ipwp|, and r_bias is negative
    # (larger SH ITCZ excess => worse skill).
    verdict = "insufficient_models"
    if r_bias is not None and len(used) >= 4:
        bias_wins = abs(r_bias) > abs(r_ls or 0.0) and abs(r_bias) > abs(r_ipwp or 0.0)
        right_sign = r_bias < 0
        if bias_wins and right_sign:
            verdict = "supported"
        elif bias_wins or right_sign:
            verdict = "weakened_or_conditional"
        else:
            verdict = "not_supported"

    payload = {
        "hypothesis": "H1",
        "n_models": len(used),
        "models": used,
        "corr_skill_vs_double_itcz_bias": r_bias,
        "corr_skill_vs_land_sea_trend": r_ls,
        "corr_skill_vs_ipwp_trend": r_ipwp,
        "verdict": verdict,
        "prediction": (
            "precip skill should track double-ITCZ / cold-tongue bias more than "
            "land-sea or warm-pool trend skill; larger SH ITCZ excess => lower skill"
        ),
    }
    cache_write("hypothesis.json", payload)
    cache_write("tables/h1.json", payload)
    return payload
