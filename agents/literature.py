"""Methods-lock subagent: read research_goal.md, do not invent index boxes."""

from __future__ import annotations

from orchestra import SubAgent

from agents.paths import RESEARCH_GOAL, ROADMAP

INSTRUCTIONS = """\
You lock index definitions to research_goal.md and the Nature Communications \
methods (Walker boxes, IPWP, EEPO, PAI, period 1979-2024, historical+SSP2-4.5). \
You do not compute data. Quote the file. If the objective is about running \
diagnostics, say which other subagent should do it.
"""


class LiteratureTools:
    def __init__(self) -> None:
        self.touched: list[str] = []

    def read_research_goal(self) -> str:
        """Return the project research_goal.md text."""
        self.touched.append(str(RESEARCH_GOAL))
        return RESEARCH_GOAL.read_text(encoding="utf-8")

    def read_roadmap(self) -> str:
        """Return ROADMAP.md."""
        self.touched.append(str(ROADMAP))
        return ROADMAP.read_text(encoding="utf-8")

    def index_definitions(self) -> str:
        """Return the frozen index boxes used by the diagnostic tools."""
        self.touched.append("agents/diagnostics.py")
        return (
            "Walker east: 5S-5N, 160W-80W (lon 200-280). "
            "Walker west: 5S-5N, 80E-160E. WCI = east SLP minus west SLP. "
            "IPWP: 5S-5N, 80E-150E SST. EEPO: 5S-5N, 180-80W SST. "
            "PAI: (0-20N precip minus 0-20S) / 20S-20N mean. "
            "Period: obs 1979-2024; models historical to 2014 unless ssp245 is present. "
            "Precip skill: cosine-weighted pattern correlation of tropical trend vs GPCP."
        )

    def as_tools(self):
        return [self.read_research_goal, self.read_roadmap, self.index_definitions]

    def sources(self) -> list[str]:
        return list(self.touched)


class LiteratureAgent(SubAgent):
    name = "literature"
    description = (
        "Reads research_goal.md and the frozen index definitions. Use to lock "
        "methods, not to compute climate fields."
    )
    instructions = INSTRUCTIONS

    def create_tools(self) -> LiteratureTools:
        return LiteratureTools()
