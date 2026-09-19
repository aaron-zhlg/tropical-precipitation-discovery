"""Observation/reanalysis diagnostic subagent."""

from __future__ import annotations

import json
from typing import Any

from orchestra import SubAgent

from agents import diagnostics as diag

INSTRUCTIONS = """\
You are the observation diagnostician. You compute the 1979-2024 observational \
fingerprint with frozen tools. You never invent numbers. If a file is missing, \
say so and stop that index.

Tools:
- catalog_datasets: what is on disk
- compute_observational_fingerprint: GPCP PAI, NCEP2 Walker, Berkeley land-sea, OISST IPWP-EEPO
- compute_walker_index / compute_land_sea_contrast / compute_ipwp_eepo / compute_precip_pai: one index
- read_cached_json: reload a previous runs/ JSON file

Method:
1. catalog_datasets first.
2. Run compute_observational_fingerprint (or the individual index tools if the lead asked for one).
3. Return the numeric results with period, units, and source path.

Do not discuss CMIP6. Do not change index definitions.
"""


class ObservationTools:
    def __init__(self) -> None:
        self.touched: list[str] = []

    def _record(self, payload: dict[str, Any]) -> str:
        source = str(payload.get("source") or payload.get("dataset") or "obs")
        if source not in self.touched:
            self.touched.append(source)
        return json.dumps(payload, default=str)

    def catalog_datasets(self) -> str:
        """List observational files and CMIP6 models present under dataset/."""
        payload = diag.catalog()
        self.touched.append("dataset/catalog")
        return json.dumps(payload, default=str)

    def compute_observational_fingerprint(self) -> str:
        """Compute GPCP PAI, NCEP2 Walker, Berkeley land-sea, and OISST IPWP-EEPO."""
        return self._record(diag.observational_fingerprint())

    def compute_walker_index(self, dataset: str = "ncep2") -> str:
        """Walker Circulation Index trend from zonal sea-level pressure."""
        return self._record(diag.walker_index(dataset=dataset))

    def compute_land_sea_contrast(self, dataset: str = "berkeley") -> str:
        """Land-minus-ocean surface temperature trend."""
        return self._record(diag.land_sea_contrast(dataset=dataset))

    def compute_ipwp_eepo(self, dataset: str = "oisst") -> str:
        """Indo-Pacific warm pool, eastern equatorial Pacific, and their difference."""
        return self._record(diag.ipwp_eepo(dataset=dataset))

    def compute_precip_pai(self, dataset: str = "gpcp") -> str:
        """Precipitation asymmetry index and tropical-mean precipitation trend."""
        return self._record(diag.precip_pai(dataset=dataset))

    def read_cached_json(self, relpath: str) -> str:
        """Read a JSON file already written under runs/, e.g. diagnostics/obs/fingerprint.json."""
        payload = diag.cache_read(relpath)
        if payload is None:
            return json.dumps({"error": f"not found: {relpath}"})
        return json.dumps(payload, default=str)

    def as_tools(self):
        return [
            self.catalog_datasets,
            self.compute_observational_fingerprint,
            self.compute_walker_index,
            self.compute_land_sea_contrast,
            self.compute_ipwp_eepo,
            self.compute_precip_pai,
            self.read_cached_json,
        ]

    def sources(self) -> list[str]:
        return list(self.touched)


class ObservationAgent(SubAgent):
    name = "observation"
    description = (
        "Computes the observational/reanalysis fingerprint from GPCP, Berkeley Earth, "
        "OISST, and NCEP2 using frozen paper indices (Walker, land-sea, IPWP, PAI). "
        "Use for the observed baseline, not for CMIP6 models."
    )
    instructions = INSTRUCTIONS

    def create_tools(self) -> ObservationTools:
        return ObservationTools()
