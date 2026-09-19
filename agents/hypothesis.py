"""H1 hypothesis tester. Reads cached diagnostics; does not open NetCDF."""

from __future__ import annotations

import json

from orchestra import SubAgent

from agents import diagnostics as diag

INSTRUCTIONS = """\
You are the hypothesis tester for H1. You do not compute new climate indices. \
You only read cached model rows and compare them to the registered predictions.

H1 prediction:
- precip skill vs double-ITCZ/cold-tongue bias should be the stronger relationship
- precip skill vs land-sea or IPWP trends should be weaker
- larger southern ITCZ excess should mean lower skill (negative correlation)

Tools:
- list_h1_rows: which models already have cached H1 rows
- test_h1: Pearson correlations and a verdict (supported / not_supported / ...)
- read_hypothesis_state: last verdict written to runs/hypothesis.json

If too few models are cached, say how many are missing and stop. Do not invent \
correlations. Do not declare a paper result; 12 models is exploratory only.
"""


class HypothesisTools:
    def __init__(self) -> None:
        self.touched: list[str] = []

    def list_h1_rows(self) -> str:
        """List cached per-model H1 diagnostic rows under runs/diagnostics/models."""
        rows = diag.load_h1_table()
        self.touched.append("runs/diagnostics/models")
        return json.dumps(
            {
                "n": len(rows),
                "models": [r.get("model") for r in rows],
                "has_skill": [
                    r.get("model")
                    for r in rows
                    if (r.get("precip_skill") or {}).get("pattern_correlation") is not None
                ],
            }
        )

    def test_h1(self) -> str:
        """Correlate cached precip skill with mean-state bias vs thermal-driver trends."""
        payload = diag.test_h1()
        self.touched.append("runs/hypothesis.json")
        return json.dumps(payload, default=str)

    def read_hypothesis_state(self) -> str:
        """Read the last written runs/hypothesis.json, if any."""
        payload = diag.cache_read("hypothesis.json")
        self.touched.append("runs/hypothesis.json")
        if payload is None:
            return json.dumps({"error": "no hypothesis.json yet; call test_h1 after model rows exist"})
        return json.dumps(payload, default=str)

    def as_tools(self):
        return [self.list_h1_rows, self.test_h1, self.read_hypothesis_state]

    def sources(self) -> list[str]:
        return list(self.touched)


class HypothesisAgent(SubAgent):
    name = "hypothesis_tester"
    description = (
        "Tests registered H1 against cached diagnostic tables: does precipitation "
        "skill track mean-state bias more than land-sea/warm-pool trends? Does not "
        "open NetCDF. Call after observation and model diagnostics have written cache."
    )
    instructions = INSTRUCTIONS

    def create_tools(self) -> HypothesisTools:
        return HypothesisTools()
