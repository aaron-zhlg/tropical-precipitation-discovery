# Why CMIP6 Misses Recent Tropical Precipitation Change

## Working claim

> Recent tropical precipitation errors in CMIP6 are not caused by missing
> land–sea thermal contrast or Indo-Pacific warm-pool intensification. Those
> thermal drivers are already captured. Mean-state biases (double-ITCZ, equatorial
> cold tongue) suppress the asymmetric circulation response that should follow.
> The relationship still holds after internal variability is accounted for.

This is a registered hypothesis, not an open search for “some physical
difference” among models.

## Reference papers

### Primary paper

**Tropical precipitation response to anthropogenic climate change in recent decades**
*Nature Communications* (2026)

[Full paper](https://www.nature.com/articles/s41467-026-71187-4)

The paper asks whether recent tropical rainfall trends are thermodynamic
(Wet-Get-Wetter / Warm-Get-Wetter) or dynamical, and which surface-temperature
drivers can produce the observed circulation.

### Related work

**Effect of atmospheric circulation on surface air temperature trends in years 1979–2018**
*Climate Dynamics* (2021)

[Full paper](https://link.springer.com/article/10.1007/s00382-020-05590-y)

Trajectory-based attribution of circulation contributions to surface-temperature
trends in ERA5.

---

## What the primary paper already established

Over 1979–2024, observed/reanalysis tropical precipitation trends are dominated
by spatial shifts in atmospheric circulation, not by Clausius–Clapeyron moisture
increase. Robust features include:

- northward-shifted rainfall; wetting over the western/northern equatorial
  Pacific, Maritime Continent, and northern India; drying south of the equator
  and over South America
- a La Niña-like Pacific SST pattern and a strengthened Walker circulation
- enhanced land–sea and inter-hemispheric thermal contrasts
- intensification of the Indo-Pacific warm pool
- Southern Ocean cooling (not robustly simulated)

CMIP6 historical+SSP2-4.5 multi-model means miss the rainfall pattern and the
Walker strengthening. They instead produce an El Niño-like rainfall trend that
resembles their late-century SSP5-8.5 response.

The same paper shows, with ERA5 regressions and coupled albedo experiments
(CFS, SINTEX), that amplified Northern Hemisphere land warming / desert
amplification *can* force an observed-like Indo-Pacific rainfall and circulation
response.

## What it hypothesized but did not test

Two statements in the Discussion are the actual gap.

1. **CMIP6 already reproduces the three large-scale thermal drivers** (global
   mean temperature, land–sea contrast, Indo-Pacific warm pool) **but still
   fails on rainfall and Walker.** The suggested reason is not a missing driver.
   It is that double-ITCZ and cold-tongue biases mute the *asymmetric*
   circulation response to those drivers.

2. **Three scenarios remain formally open:** (i) the observed rainfall trend is
   internal decadal variability; (ii) it is a transient adjustment to radiative
   forcing; (iii) models systematically fail to simulate the forced tropical
   rainfall response. The paper prefers (iii) on physical grounds, without a
   large-ensemble test of (i).

The paper also notes that land–sea and inter-hemispheric gradients are nearly
degenerate, and that NH land warming alone does not fully explain the observed
Walker pattern.

This project tests (1), with (2) as a required robustness check. It does not
re-ask whether the ensemble mean disagrees with observations, and it does not
treat “inter-model spread” as an open-ended discovery problem.

---

## Research question

> If CMIP6 already captures land–sea warming and warm-pool intensification, why
> does it still miss the 1979–2024 tropical precipitation trend pattern? Do
> climatological double-ITCZ and cold-tongue biases block the pathway
> land–sea contrast → asymmetric circulation → observed-like rainfall, and does
> that still hold after internal variability is removed?

## Falsifiable predictions

Let **precip skill** be the spatial pattern correlation of a model’s tropical
precipitation trend (1979–2024, historical concatenated with SSP2-4.5) against
GPCP/ERA5. Let **mean-state bias** be double-ITCZ and equatorial cold-tongue
error in the climatology. Let **thermal-driver skill** be how well the model
reproduces observed trends in land–sea contrast and Indo-Pacific warm-pool SST.

**H1 (primary).** Thermal-driver skill is high across models and does not
separate high vs low precip skill. Mean-state bias does: smaller double-ITCZ /
cold-tongue bias predicts higher precip skill and a more observed-like Walker /
asymmetric upper-level response.

**H1 fails if** precip skill tracks land–sea or warm-pool trends instead of
mean-state bias, or if models with small ITCZ/cold-tongue bias still produce
El Niño-like rainfall trends.

**H2 (required check).** The H1 relationship is not an accident of one
realization. In large ensembles, the observed rainfall pattern lies outside the
internal-variability envelope of models whose forced response is El Niño-like;
or, equivalently, member-to-member noise does not erase the mean-state-bias vs
skill link.

**H2 fails if** observed 1979–2024 rainfall is a plausible IPO/ENSO draw inside
those ensembles. Then the Nature paper’s preference for scenario (iii) is not
supported, and H1 cannot be read as a forced-response mechanism.

**H3 (optional, cleaner causality).** The same atmosphere in AMIP (observed SST)
recovers more of the observed rainfall pattern than the coupled historical run.
If AMIP still fails, the atmospheric mean state (not the coupled SST trend) is
the bottleneck, which is what H1 claims.

---

## How to test it

Do not retrain climate models. Run the same frozen diagnostics on observations
and on each CMIP6 model, then update the hypothesis.

0. **Reproduce, do not discover.** Confirm the observational fingerprint and
   that the multi-model mean misses it.
1. **Show the drivers are not the error.** Per model, land–sea contrast and
   warm-pool trends vs observed; these should *not* rank precip skill.
2. **Test the mean-state bottleneck.** Per model, double-ITCZ and cold-tongue
   bias vs precip skill, Walker trend, and the asymmetry of the 200 hPa
   circulation response. This is the main experiment.
3. **Remove internal variability.** Repeat with large ensembles (multiple
   members of CESM2, CanESM5, MPI-ESM, etc.).
4. **Seasonal split (supporting).** JJA vs DJF: the primary paper’s summer
   pattern is the land-driven asymmetric teleconnection; winter is more Walker /
   warm-pool. If models fail in only one season, the mechanism is localized.
5. **Stop.** H1 holds with H2 intact; or H1 is rejected with a stated
   alternative (internal variability, missing Pacific gradient, atmospheric
   AMIP failure). Do not keep adding indices after the fact.

Index definitions follow the primary paper (Walker Circulation Index from zonal
sea-level pressure; land–sea contrast; IPWP; EEPO; IPWP−EEPO; Precipitation
Asymmetry Index). Changing an index definition is a new experiment, not a new
hypothesis test.

---

## Datasets

Period: 1979–2024, as in the primary paper. CMIP6 historical (to 2014) is
concatenated with SSP2-4.5 (2015–2024).

| Dataset | Role |
| --- | --- |
| GPCP | Independent observed precipitation trends and skill target |
| ERA5 | Primary reanalysis: precipitation, t2m, SST, winds, humidity, MSLP |
| Berkeley Earth | Independent t2m / land–sea contrast |
| NOAA OISST | Independent SST, warm pool, cold tongue |
| NCEP/DOE Reanalysis 2 | Independent circulation |
| CMIP6 `pr`, `tas`, `tos`, `psl` | Per-model trends, mean-state biases, Walker index. Prefer far more than 12 models |
| CMIP6 large ensembles | H2: internal variability vs forced response |
| CMIP6 AMIP (optional) | H3: atmosphere-only vs coupled |

`scripts/data_prepare.py` downloads the observational/reanalysis stack and a
CMIP6 core set. Use `--cmip6-all` when testing H1. Large ensembles and AMIP are
required for a paper-level H2/H3 test and are not yet in the default download.

---

## What would count as a result

A paper result is a bounded statement such as:

> Across N CMIP6 models, precipitation-trend skill is unrelated to land–sea and
> warm-pool trend skill, and is predicted by double-ITCZ / cold-tongue bias;
> models with smaller mean-state bias produce a more asymmetric, observed-like
> circulation response. Large ensembles show this is not a single-member IPO
> accident.

Or an equally valid rejection:

> Mean-state bias does not separate precipitation skill once internal variability
> is included; the 1979–2024 observed pattern is within the unforced range.

Repeating the primary paper’s multi-model mean comparison is not a result.
