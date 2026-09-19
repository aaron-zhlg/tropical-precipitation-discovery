"""Repo, dataset, and run-cache locations."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = REPO_ROOT / "dataset"
RUNS_ROOT = REPO_ROOT / "runs"
RESEARCH_GOAL = REPO_ROOT / "research_goal.md"
ROADMAP = REPO_ROOT / "ROADMAP.md"

PERIOD_START = 1979
PERIOD_END = 2024
HISTORICAL_END = 2014
TROPICS = (-30.0, 30.0)
