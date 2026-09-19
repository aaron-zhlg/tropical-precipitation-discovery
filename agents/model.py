"""Per-model CMIP6 diagnostic subagent."""

from __future__ import annotations

import json
from typing import Any

from orchestra import SubAgent

from agents import diagnostics as diag

INSTRUCTIONS = """\
You are the model diagnostician. Each run should target ONE CMIP6 model unless \
the objective explicitly says to list models. Use frozen tools. Never invent \
numbers; if pr/tas/tos/psl is missing, report the error from the tool.

Tools:
- list_cmip6_models
- model_coverage(model)
- compute_model_h1_row(model): precip skill vs GPCP, mean-state bias, thermal drivers, Walker
- compute_precip_skill / compute_mean_state_bias / compute_thermal_drivers / compute_walker

Method:
1. If you do not know the model id, list_cmip6_models or model_coverage.
2. Call compute_model_h1_row for that model.
3. Return the JSON fields. Do not compare models; the hypothesis_tester does that.
"""


class ModelTools:
    def __init__(self) -> None:
        self.touched: list[str] = []

    def _record(self, payload: dict[str, Any]) -> str:
        model = str(payload.get("model") or "cmip6")
        token = f"cmip6:{model}"
        if token not in self.touched:
            self.touched.append(token)
        return json.dumps(payload, default=str)

    def list_cmip6_models(self) -> str:
        """List CMIP6 source_id values that have at least one file on disk."""
        models = diag.list_cmip6_models()
        self.touched.append("dataset/cmip6")
        return json.dumps({"models": models, "n": len(models)})

    def model_coverage(self, model: str) -> str:
        """Show which pr/tas/tos/psl files exist for one CMIP6 model."""
        return self._record(diag.model_coverage(model))

    def compute_model_h1_row(self, model: str) -> str:
        """Compute the H1 diagnostic row for one model and cache it under runs/."""
        return self._record(diag.model_h1_row(model))

    def compute_precip_skill(self, model: str) -> str:
        """Pattern correlation of tropical precipitation trend vs GPCP."""
        return self._record(diag.model_precip_skill(model))

    def compute_mean_state_bias(self, model: str) -> str:
        """Double-ITCZ and cold-tongue climatological biases vs GPCP/OISST."""
        return self._record(diag.model_mean_state_bias(model))

    def compute_thermal_drivers(self, model: str) -> str:
        """Land-sea contrast and Indo-Pacific warm-pool trends for one model."""
        return self._record(diag.model_thermal_drivers(model))

    def compute_walker(self, model: str) -> str:
        """Walker Circulation Index trend from model psl."""
        return self._record(diag.model_walker(model))

    def as_tools(self):
        return [
            self.list_cmip6_models,
            self.model_coverage,
            self.compute_model_h1_row,
            self.compute_precip_skill,
            self.compute_mean_state_bias,
            self.compute_thermal_drivers,
            self.compute_walker,
        ]

    def sources(self) -> list[str]:
        return list(self.touched)


class ModelAgent(SubAgent):
    name = "model"
    description = (
        "Computes frozen H1 diagnostics for ONE CMIP6 model: precipitation-trend "
        "skill vs GPCP, double-ITCZ/cold-tongue bias, land-sea and warm-pool trends, "
        "and Walker index. Spawn one instance per model."
    )
    instructions = INSTRUCTIONS

    def create_tools(self) -> ModelTools:
        return ModelTools()
