#!/usr/bin/env python3
"""Download the monthly datasets used in research_goal.md.

Default destination is <repo>/dataset. Period follows the primary paper: 1979-2024.
The research claim is that CMIP6 misses recent tropical rainfall because
mean-state biases mute the circulation response, not because land-sea / warm-pool
drivers are missing.

Public HTTP sources (no login):
  GPCP, Berkeley Earth, NOAA OISST v2.1, NCEP/DOE Reanalysis 2

Need credentials:
  ERA5  — Copernicus CDS key in .env (CDSAPI_KEY) or ~/.cdsapirc
  CMIP6 — ESGF is public, but the full ensemble is large. Default is a 12-model
  core; pass --cmip6-all for the inter-model test. Large ensembles are separate.

Examples:
  uv run python scripts/data_prepare.py
  uv run python scripts/data_prepare.py --only gpcp,oisst,ncep2
  uv run python scripts/data_prepare.py --skip cmip6 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

PERIOD_START = 1979
PERIOD_END = 2024
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "dataset"
USER_AGENT = "tropical-precipitation-discovery/0.1 (research data prep)"
TIMEOUT = 120
RETRIES = 4

SSL_CONTEXT = ssl.create_default_context()

DATASETS = (
    "gpcp",
    "berkeley_earth",
    "oisst",
    "ncep2",
    "era5",
    "cmip6",
)

PSL = "https://downloads.psl.noaa.gov/Datasets"

HTTP_FILES: dict[str, list[tuple[str, str]]] = {
    "gpcp": [
        (f"{PSL}/gpcp/precip.mon.mean.nc", "precip.mon.mean.nc"),
    ],
    "berkeley_earth": [
        (
            "https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/"
            "Global/Gridded/Land_and_Ocean_LatLong1.nc",
            "Land_and_Ocean_LatLong1.nc",
        ),
    ],
    "oisst": [
        (f"{PSL}/noaa.oisst.v2.highres/sst.mon.mean.nc", "sst.mon.mean.nc"),
    ],
    "ncep2": [
        (f"{PSL}/ncep.reanalysis2/Monthlies/pressure/uwnd.mon.mean.nc", "uwnd.mon.mean.nc"),
        (f"{PSL}/ncep.reanalysis2/Monthlies/pressure/vwnd.mon.mean.nc", "vwnd.mon.mean.nc"),
        (f"{PSL}/ncep.reanalysis2/Monthlies/pressure/omega.mon.mean.nc", "omega.mon.mean.nc"),
        (f"{PSL}/ncep.reanalysis2/Monthlies/surface/mslp.mon.mean.nc", "mslp.mon.mean.nc"),
    ],
}

# Diverse r1i1p1f1 models commonly used for CMIP6 tropical-precip comparisons.
# Paper MME list is in Supplementary Table 1; pass --cmip6-all to take every hit.
DEFAULT_CMIP6_MODELS = (
    "ACCESS-CM2",
    "ACCESS-ESM1-5",
    "BCC-CSM2-MR",
    "CESM2",
    "CanESM5",
    "GFDL-ESM4",
    "IPSL-CM6A-LR",
    "MIROC6",
    "MPI-ESM1-2-HR",
    "MRI-ESM2-0",
    "NorESM2-LM",
    "TaiESM1",
)

CMIP6_REQUESTS = (
    ("historical", "Amon", "pr", PERIOD_START, 2014),
    ("historical", "Amon", "tas", PERIOD_START, 2014),
    ("historical", "Amon", "psl", PERIOD_START, 2014),
    ("historical", "Omon", "tos", PERIOD_START, 2014),
    ("ssp245", "Amon", "pr", 2015, PERIOD_END),
    ("ssp245", "Amon", "tas", 2015, PERIOD_END),
    ("ssp245", "Amon", "psl", 2015, PERIOD_END),
    ("ssp245", "Omon", "tos", 2015, PERIOD_END),
    ("ssp585", "Amon", "pr", 2081, 2100),
)

ESGF_SEARCH = (
    "https://esgf-node.llnl.gov/esg-search/search",
    "https://esgf.ceda.ac.uk/esg-search/search",
    "https://esgf-data.dkrz.de/esg-search/search",
)

ERA5_SINGLE_VARIABLES = (
    "2m_temperature",
    "sea_surface_temperature",
    "total_precipitation",
    "evaporation",
    "mean_sea_level_pressure",
)

ERA5_PRESSURE_VARIABLES = (
    "u_component_of_wind",
    "v_component_of_wind",
    "vertical_velocity",
    "specific_humidity",
)

ERA5_PRESSURE_LEVELS = ("200", "300", "500", "700", "850", "925")


@dataclass
class DownloadResult:
    dataset: str
    path: Path
    status: str
    bytes: int = 0
    detail: str = ""


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def log(message: str) -> None:
    print(message, flush=True)


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def ensure_out_dir(path: Path) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SystemExit(
            f"Cannot create {path}: {exc}\n"
            "Create it first or pass --out."
        ) from exc
    probe = path / ".write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise SystemExit(f"Cannot write to {path}: {exc}") from exc
    return path


def format_bytes(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{n} B"


def open_url(url: str, headers: dict[str, str] | None = None):
    merged = {"User-Agent": USER_AGENT}
    if headers:
        merged.update(headers)
    request = urllib.request.Request(url, headers=merged)
    return urllib.request.urlopen(request, timeout=TIMEOUT, context=SSL_CONTEXT)


def download_file(url: str, dest: Path, dry_run: bool = False) -> DownloadResult:
    dataset = dest.parent.name
    if dry_run:
        return DownloadResult(dataset, dest, "dry-run", detail=url)

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return DownloadResult(dataset, dest, "exists", dest.stat().st_size)

    part = dest.with_name(dest.name + ".part")
    existing = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": USER_AGENT}
    if existing:
        headers["Range"] = f"bytes={existing}-"

    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            with open_url(url, headers) as response:
                status = getattr(response, "status", 200)
                total = response.headers.get("Content-Length")
                total_i = int(total) if total and total.isdigit() else None
                mode = "ab" if status == 206 and existing else "wb"
                if mode == "wb":
                    existing = 0
                downloaded = existing
                expected = downloaded + total_i if total_i is not None else None
                last_report = downloaded
                log(f"  GET {url}")
                with part.open(mode) as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if downloaded - last_report >= 32 * 1024 * 1024 or downloaded == expected:
                            if expected:
                                pct = 100 * downloaded / expected
                                print(
                                    f"    {format_bytes(downloaded)} / {format_bytes(expected)} ({pct:5.1f}%)",
                                    flush=True,
                                )
                            else:
                                print(f"    {format_bytes(downloaded)}", flush=True)
                            last_report = downloaded
            part.replace(dest)
            return DownloadResult(dataset, dest, "downloaded", dest.stat().st_size)
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, ConnectionError) as exc:
            last_error = exc
            wait = 2 ** attempt
            log(f"  retry {attempt}/{RETRIES} after {wait}s: {exc}")
            time.sleep(wait)

    return DownloadResult(dataset, dest, "error", existing, str(last_error))


def download_http_dataset(name: str, out: Path, dry_run: bool) -> list[DownloadResult]:
    results = []
    log(f"\n== {name} ==")
    for url, filename in HTTP_FILES[name]:
        results.append(download_file(url, out / name / filename, dry_run=dry_run))
    return results


def years_between(start: int, end: int) -> list[str]:
    return [str(year) for year in range(start, end + 1)]


def cds_client():
    try:
        import cdsapi
    except ImportError as exc:
        raise RuntimeError(
            "ERA5 needs cdsapi. Install with: uv add cdsapi\n"
            "Then put CDSAPI_KEY in .env or ~/.cdsapirc."
        ) from exc
    url = os.environ.get("CDSAPI_URL")
    key = os.environ.get("CDSAPI_KEY")
    if url and key:
        return cdsapi.Client(url=url, key=key)
    if key:
        return cdsapi.Client(key=key)
    return cdsapi.Client()


def retrieve_era5(client, dataset: str, request: dict, dest: Path, dry_run: bool) -> DownloadResult:
    if dry_run:
        return DownloadResult("era5", dest, "dry-run", detail=dataset)
    if dest.exists() and dest.stat().st_size > 0:
        return DownloadResult("era5", dest, "exists", dest.stat().st_size)
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"  CDS {dataset} -> {dest.name}")
    try:
        client.retrieve(dataset, request, str(dest))
    except Exception as exc:
        return DownloadResult("era5", dest, "error", detail=str(exc))
    size = dest.stat().st_size if dest.exists() else 0
    return DownloadResult("era5", dest, "downloaded", size)


def download_era5(out: Path, dry_run: bool) -> list[DownloadResult]:
    log("\n== era5 ==")
    dest_dir = out / "era5"
    months = [f"{m:02d}" for m in range(1, 13)]
    try:
        client = None if dry_run else cds_client()
    except RuntimeError as exc:
        log(f"  skip: {exc}")
        return [DownloadResult("era5", dest_dir, "skipped", detail=str(exc))]

    single = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": list(ERA5_SINGLE_VARIABLES),
        "month": months,
        "time": ["00:00"],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    pressure = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": list(ERA5_PRESSURE_VARIABLES),
        "pressure_level": list(ERA5_PRESSURE_LEVELS),
        "month": months,
        "time": ["00:00"],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    results = []
    for start in range(PERIOD_START, PERIOD_END + 1, 10):
        stop = min(start + 9, PERIOD_END)
        chunk_years = years_between(start, stop)
        single_req = {**single, "year": chunk_years}
        pressure_req = {**pressure, "year": chunk_years}
        results.append(
            retrieve_era5(
                client,
                "reanalysis-era5-single-levels-monthly-means",
                single_req,
                dest_dir / f"single_levels_monthly_{start}-{stop}.nc",
                dry_run,
            )
        )
        results.append(
            retrieve_era5(
                client,
                "reanalysis-era5-pressure-levels-monthly-means",
                pressure_req,
                dest_dir / f"pressure_levels_monthly_{start}-{stop}.nc",
                dry_run,
            )
        )
    return results


def esgf_http_urls(urls: Iterable[str]) -> list[str]:
    http = []
    for item in urls:
        parts = item.split("|")
        if len(parts) >= 3 and parts[2] == "HTTPServer":
            http.append(parts[0])
        elif item.startswith("http") and "HTTPServer" in item:
            http.append(parts[0])
    return http


def _first(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def _cmip6_file_key(filename: str) -> tuple[str, str]:
    stem = filename.removesuffix(".nc")
    parts = stem.split("_")
    if len(parts) >= 2:
        return "_".join(parts[:-2]), parts[-1]
    return stem, ""


def file_year_range(filename: str) -> tuple[int, int] | None:
    stem = filename.removesuffix(".nc")
    tail = stem.split("_")[-1]
    start, sep, end = tail.partition("-")
    if not sep or len(start) < 4 or len(end) < 4 or not start[:4].isdigit() or not end[:4].isdigit():
        return None
    return int(start[:4]), int(end[:4])


def years_overlap(span: tuple[int, int] | None, start: int, end: int) -> bool:
    if span is None:
        return True
    return span[0] <= end and span[1] >= start


def pick_cmip6_docs(docs: list[dict]) -> list[dict]:
    preferred = {"gn": 0, "gr": 1, "gr1": 2, "gr2": 3}
    best: dict[tuple[str, str], tuple[int, dict]] = {}
    for doc in docs:
        filename = doc.get("title") or ""
        key = _cmip6_file_key(filename)
        grid = _first(doc.get("grid_label"))
        rank = preferred.get(grid, 50)
        current = best.get(key)
        if current is None or rank < current[0]:
            best[key] = (rank, doc)
    return [item[1] for item in best.values()]


def esgf_search(
    experiment: str,
    table: str,
    variable: str,
    models: list[str] | None,
    variant: str,
) -> list[dict]:
    params = {
        "project": "CMIP6",
        "type": "File",
        "latest": "true",
        "distrib": "true",
        "format": "application/solr+json",
        "limit": "200",
        "offset": "0",
        "activity_id": "CMIP" if experiment == "historical" else "ScenarioMIP",
        "experiment_id": experiment,
        "table_id": table,
        "variable_id": variable,
        "frequency": "mon",
        "variant_label": variant,
    }
    if models:
        params["source_id"] = ",".join(models)

    last_error: Exception | None = None
    for replica in ("false", "true"):
        params["replica"] = replica
        query = urllib.parse.urlencode(params)
        for node in ESGF_SEARCH:
            url = f"{node}?{query}"
            try:
                with open_url(url) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                docs = pick_cmip6_docs(payload.get("response", {}).get("docs", []))
                if docs:
                    log(
                        f"  ESGF {experiment} {table} {variable}: "
                        f"{len(docs)} files from {node} (replica={replica})"
                    )
                    return docs
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                log(f"  ESGF node failed {node}: {exc}")
    log(f"  ESGF found no files for {experiment} {table} {variable}")
    if last_error:
        raise RuntimeError(f"All ESGF search nodes failed: {last_error}")
    return []


def download_cmip6(
    out: Path,
    dry_run: bool,
    models: list[str] | None,
    all_models: bool,
    variant: str,
) -> list[DownloadResult]:
    log("\n== cmip6 ==")
    chosen = None if all_models else (models or list(DEFAULT_CMIP6_MODELS))
    if chosen:
        log("  models: " + ", ".join(chosen))
    else:
        log("  models: all ESGF matches")

    results: list[DownloadResult] = []
    seen: set[str] = set()
    try:
        for experiment, table, variable, year_start, year_end in CMIP6_REQUESTS:
            docs = esgf_search(experiment, table, variable, chosen, variant)
            for doc in docs:
                filename = doc.get("title") or ""
                if not years_overlap(file_year_range(filename), year_start, year_end):
                    continue
                urls = esgf_http_urls(doc.get("url", []))
                if not urls:
                    continue
                if not filename:
                    filename = Path(urllib.parse.urlparse(urls[0]).path).name
                dest = out / "cmip6" / experiment / variable / filename
                key = str(dest)
                if key in seen:
                    continue
                seen.add(key)
                result = download_file(urls[0], dest, dry_run=dry_run)
                if result.status == "error" and len(urls) > 1:
                    result = download_file(urls[1], dest, dry_run=dry_run)
                results.append(result)
    except RuntimeError as exc:
        log(f"  skip: {exc}")
        results.append(DownloadResult("cmip6", out / "cmip6", "skipped", detail=str(exc)))
    if not results:
        results.append(DownloadResult("cmip6", out / "cmip6", "skipped", detail="no files found"))
    return results


def write_manifest(out: Path, results: list[DownloadResult]) -> None:
    payload = {
        "created": datetime.now(timezone.utc).isoformat(),
        "period": f"{PERIOD_START}-{PERIOD_END}",
        "root": str(out),
        "files": [
            {
                "dataset": item.dataset,
                "path": str(item.path),
                "status": item.status,
                "bytes": item.bytes,
                "detail": item.detail,
            }
            for item in results
        ],
    }
    path = out / "MANIFEST.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log(f"\nWrote {path}")


def summarize(results: list[DownloadResult]) -> int:
    counts: dict[str, int] = {}
    for item in results:
        counts[item.status] = counts.get(item.status, 0) + 1
        mark = {
            "downloaded": "ok",
            "exists": "ok",
            "dry-run": "dry",
            "skipped": "skip",
            "error": "ERR",
        }.get(item.status, item.status)
        extra = f" ({item.detail})" if item.detail and item.status != "dry-run" else ""
        log(f"[{mark}] {item.path} {format_bytes(item.bytes)}{extra}")
    log(
        "\nSummary: "
        + ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    )
    return 1 if counts.get("error") else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Destination root (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated datasets to download: " + ", ".join(DATASETS),
    )
    parser.add_argument(
        "--skip",
        default="",
        help="Comma-separated datasets to skip",
    )
    parser.add_argument(
        "--cmip6-models",
        default="",
        help="Comma-separated CMIP6 source_id values (default: 12-model core; use --cmip6-all for H1)",
    )
    parser.add_argument(
        "--cmip6-all",
        action="store_true",
        help="Download every ESGF match instead of the default model list",
    )
    parser.add_argument(
        "--cmip6-variant",
        default="r1i1p1f1",
        help="CMIP6 variant label (default: r1i1p1f1)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print targets, do not download")
    return parser.parse_args(argv)


def selected_datasets(args: argparse.Namespace) -> list[str]:
    only = parse_csv(args.only)
    skip = set(parse_csv(args.skip))
    unknown = [name for name in only + list(skip) if name not in DATASETS]
    if unknown:
        raise SystemExit(f"Unknown dataset(s): {', '.join(unknown)}")
    chosen = only or list(DATASETS)
    return [name for name in chosen if name not in skip]


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)
    names = selected_datasets(args)
    out = args.out if args.dry_run else ensure_out_dir(args.out)
    log(f"Destination: {out}")
    log(f"Period: {PERIOD_START}-{PERIOD_END}")
    log("Datasets: " + ", ".join(names))

    results: list[DownloadResult] = []
    for name in names:
        if name in HTTP_FILES:
            results.extend(download_http_dataset(name, out, args.dry_run))
        elif name == "era5":
            results.extend(download_era5(out, args.dry_run))
        elif name == "cmip6":
            models = parse_csv(args.cmip6_models)
            results.extend(
                download_cmip6(
                    out,
                    args.dry_run,
                    models or None,
                    args.cmip6_all,
                    args.cmip6_variant,
                )
            )

    if not args.dry_run:
        write_manifest(out, results)
    return summarize(results)


if __name__ == "__main__":
    sys.exit(main())
