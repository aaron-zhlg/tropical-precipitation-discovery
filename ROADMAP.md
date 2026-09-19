# Roadmap

The science is in `research_goal.md`. This file is the build order: what to
make first, what “done” means, and what not to do yet.

The claim to test:

> CMIP6 already captures land–sea warming and warm-pool intensification.
> Mean-state biases (double-ITCZ, cold tongue) suppress the asymmetric
> circulation response, so recent tropical rainfall trends are still wrong.
> This still holds after internal variability is accounted for.

Work is a sequence of **frozen diagnostics + hypothesis tests**. Agents wrap
those diagnostics later. They do not invent new indices in the same round they
are used as evidence.

## Rules that apply to every phase

- Index definitions follow the Nature Communications paper (boxes, period
  1979–2024, historical+SSP2-4.5, Walker from `psl`, land–sea, IPWP, PAI).
  Changing a definition is a new experiment, not a silent tweak.
- Results are tables and fields on disk, not chat. Re-running the same command
  must give the same numbers.
- Do not add a coding agent until a registered hypothesis needs an index that
  is not already a function.
- Do not claim the paper result until Phase 4 (H2) passes or cleanly fails.
- 12 models are for learning the pipeline. They are not a paper sample.

```
Phase 0  instruments          no LLM
Phase 1  reproduce the paper  no LLM
Phase 2  H1 on 12 models      no LLM required
Phase 3  agent loop           orchestra around existing tools
Phase 4  H1 at scale + H2     more data, same tools
Phase 5  H3 / seasons         only if H1 still stands
```

---

## Phase 0 — Instruments

**Goal.** A small Python library that computes the paper’s indices from
`dataset/`. No agents. No new science.

**Build**

- Open GPCP, ERA5, OISST, Berkeley Earth, NCEP2, and one CMIP6 model with the
  same grid, units, and time window.
- Functions, not notebooks as the source of truth:
  - tropical precipitation trend map
  - precip skill vs a named observational target
  - land–sea thermal contrast
  - IPWP, EEPO, IPWP−EEPO
  - Walker Circulation Index from `psl`
  - double-ITCZ and cold-tongue climatological bias
  - Precipitation Asymmetry Index
- Cache outputs under `runs/` (gitignored or small csv/json only).

**Done when**

- `uv run python -c ...` (or a `scripts/diagnostics.py` CLI) prints the ERA5
  Walker trend and one model’s precip skill against GPCP, with units and
  period in the output.
- A second run hits cache and does not re-read the full NetCDF stack.

**Not this phase:** orchestra, large ensembles, AMIP, extra indices.

**Data:** finish the default `data_prepare.py` core (GPCP, OISST, NCEP2,
Berkeley Earth, ERA5 if CDS works, 12-model `pr/tas/tos/psl`). Incomplete
CMIP6 files are a blocker, not something to paper over.

---

## Phase 1 — Reproduce, do not discover

**Goal.** Show we can recover the primary paper’s qualitative result with our
instruments: the observed fingerprint exists, the 12-model mean does not match
it, land–sea and warm-pool trends are present in both.

**Build**

- Observational fingerprint maps/tables: precip, t2m, SST, Walker, PAI
  (ERA5 + GPCP/OISST/Berkeley/NCEP2 where the paper compared them).
- 12-model MME precipitation trend vs GPCP/ERA5 (pattern correlation).
- One-page note: what matches the paper, what does not (ERA5 vs GPCP
  disagreements are expected).

**Done when**

- We can state, with numbers from our code: MME precip-trend skill is low;
  observed Walker trend is positive in ERA5; land–sea and IPWP rise in both
  ERA5 and the MME.
- If we cannot reproduce that, stop and fix data/definitions. Do not move to
  H1.

**Not this phase:** ranking individual models, agents, “why models differ”.

---

## Phase 2 — H1 minimum (12 models, scripts)

**Goal.** First real test of the working claim, cheap and honest. Sample size
is too small for a paper; it is enough to see if H1 is even pointing the right
way.

**Build**

- Per model, one row:
  - precip skill (GPCP and ERA5, separately)
  - land–sea trend skill and IPWP trend skill
  - double-ITCZ bias, cold-tongue bias
  - Walker trend, PAI trend
- Two scatter plots (or equivalent tables):
  - precip skill vs thermal-driver skill (H1: should be weak)
  - precip skill vs mean-state bias (H1: should be strong, and the right sign)
- A short H1 verdict: supported / weakened / needs a condition (e.g. only
  Pacific).

**Done when**

- Those two relationships are computed from the same cached diagnostics.
- The verdict is written down *before* adding new predictors.

**Not this phase:** fishing for other indices after seeing the plots; LLM
agents; calling this a paper result.

**If H1 already dies here** (skill tracks warm-pool/land–sea, or bias does not
separate models), the later agent system still has a job: it should converge
on that rejection, not rescue the claim.

---

## Phase 3 — Agent loop on frozen tools

**Goal.** Orchestra runs the same experiments a human just ran, as a
hypothesis state machine, without writing new analysis code.

**Agents (minimum)**

| Agent | Job |
| --- | --- |
| Lead | Register H, predictions, next experiment, stop |
| Observation Diagnostician | Call Phase 0 tools on obs/reanalysis |
| Model Diagnostician | Same tools, one model per instance |
| Hypothesis Tester | Compare predictions to the tables from the two diagnosticians |

Add later, not in the first orchestra run: Literature (index boxes only),
Skeptic (period and dataset swaps), Internal Variability (Phase 4).

**Build**

- Each diagnostic function becomes a SubAgent tool.
- Shared state on disk: current hypothesis, predictions, evidence, status
  (`active` / `supported` / `weakened` / `retired`).
- Lead preamble: one active hypothesis per round; evaluate = “was the
  prediction hit?”, not “is the write-up long enough?”.
- `max_rounds` is hypothesis iterations, not report drafts.

**Done when**

- `lead.run("Test H1 on the 12-model core")` reproduces the Phase 2 verdict
  from tools, not from the model inventing numbers.
- Logs show which tool ran, on which dataset, with which period.

**Not this phase:** a general Python-coder agent; new CMIP6 downloads as the
default path; claiming H2.

---

## Phase 4 — Paper-grade H1 and required H2

**Goal.** The statement that could actually go in a paper, if it survives.

**H1 at scale**

- `--cmip6-all` (or an explicit list much larger than 12), still r1i1p1f1,
  same diagnostics.
- Repeat Phase 2 scatters. Pre-register that this is the confirmatory H1
  sample; Phase 2 was exploratory.

**H2 (required)**

- Download a few large ensembles (e.g. CanESM5, MPI-ESM, CESM2 members).
- For each: is the observed precip-trend pattern inside the member envelope
  of a model whose forced response is El Niño-like?
- Does the bias–skill slope survive swapping members?

**Agents:** add Internal Variability Agent and Skeptic. Skeptic must re-run
H1/H2 for 1979–2014 vs 1979–2024 and GPCP vs ERA5.

**Done when**

- Either: N ≫ 12, H1 direction holds, and H2 does not reduce it to one lucky
  IPO member.
- Or: a written rejection (obs inside the unforced envelope, and/or bias does
  not predict skill once members are included).

Both are valid exits. “Need more indices” is not.

**Not this phase:** new coupled GCM experiments; warm-pool-only perturbations.

---

## Phase 5 — Only if H1 still stands

Do these after Phase 4, not instead of it.

- **H3 AMIP:** same atmosphere, observed SST. If AMIP recovers the rainfall
  pattern, the bottleneck is coupled SST; that *weakens* a pure atmospheric
  mean-state story and must be said plainly. If AMIP still fails, H1’s
  atmospheric-bias claim is stronger.
- **Seasonal split:** JJA (asymmetric land teleconnection) vs DJF (Walker /
  warm pool), as in the primary paper’s Supplementary Fig. 4.
- **Literature agent:** lock remaining index details to the paper methods.

**Done when** the bounded sentence in `research_goal.md` (“What would count as
a result”) can be filled with N, datasets, and which of H1–H3 held.

---

## What “simple start” means this week

Do **Phase 0 then Phase 1** only.

1. Make the default observational downloads complete; do not wait for every
   CMIP6 file.
2. Implement the diagnostic functions against ERA5/GPCP + whichever CMIP6
   models are fully on disk.
3. Reproduce “MME ≠ observed precip trend” with our code.

Do not start orchestra until Phase 2 has one human-run H1 table. The agent
layer is Phase 3. The paper bar is Phase 4.

## Explicitly out of scope until a later decision

- Renaming the repository
- Training or fine-tuning climate models
- A free-form coding agent as the experimenter
- Sensitivity experiments like the paper’s albedo runs (need a coupled GCM)
- Treating 12-model scatters as the result
