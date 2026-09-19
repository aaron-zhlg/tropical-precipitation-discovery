# tropical-precipitation-discovery

Multi-agent climate research, built on
[orchestra](https://github.com/aaron-zhlg/orchestra).

The system tests a single claim from the 2026 *Nature Communications* tropical
rainfall paper: **CMIP6 already captures land–sea warming and Indo-Pacific
warm-pool intensification, but mean-state biases (double-ITCZ, cold tongue)
suppress the asymmetric circulation response, so recent tropical precipitation
trends are still wrong — including after internal variability is accounted
for.**

That claim is a hypothesis to falsify, not an open search for inter-model
spread. Details, predictions, and datasets are in `research_goal.md`. Build
order is in `ROADMAP.md`.

## Setup

```bash
uv sync
```

Set one LLM key:

```bash
export DEEPSEEK_API_KEY=sk-...
# or OPENAI_API_KEY=...
# or ORCHESTRA_API_KEY + ORCHESTRA_BASE_URL + ORCHESTRA_MODEL
```

## Data

Download the monthly datasets from `research_goal.md` into `dataset/`:

```bash
uv run python scripts/data_prepare.py
```

GPCP, Berkeley Earth, OISST, and NCEP2 are public HTTP downloads. ERA5 needs a
[Copernicus CDS](https://cds.climate.copernicus.eu) key (`~/.cdsapirc` or
`CDSAPI_KEY`). CMIP6 is pulled from ESGF for a 12-model core set (`pr`, `tas`,
`tos`, `psl`; historical + SSP2-4.5, plus SSP5-8.5 precipitation). Use
`--cmip6-all` for the inter-model test; large ensembles are a later download.

```bash
uv run python scripts/data_prepare.py --only gpcp,oisst,ncep2
uv run python scripts/data_prepare.py --skip cmip6
uv run python scripts/data_prepare.py --cmip6-all
uv run python scripts/data_prepare.py --out /data/tropprecip
```

## Run

Diagnostics only (no LLM):

```bash
uv run python -m agents.run --catalog
uv run python -m agents.run --fingerprint
uv run python -m agents.run --h1-row CanESM5
uv run python -m agents.run --test-h1
```

Full lead + subagents (needs an LLM key):

```bash
uv run python -m agents.run
uv run python -m agents.run "Test H1 on CanESM5 and ACCESS-CM2 only"
```

Observation, model, hypothesis_tester, and literature subagents are in `agents/`.
The lead tests registered H1; it does not search for new mechanisms.
