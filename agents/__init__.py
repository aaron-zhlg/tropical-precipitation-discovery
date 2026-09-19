"""Hypothesis-driven multi-agent tests of CMIP6 tropical precipitation error."""

from agents.hypothesis import HypothesisAgent
from agents.lead import DEFAULT_GOAL, build
from agents.literature import LiteratureAgent
from agents.model import ModelAgent
from agents.observation import ObservationAgent

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_GOAL",
    "HypothesisAgent",
    "LiteratureAgent",
    "ModelAgent",
    "ObservationAgent",
    "build",
]
