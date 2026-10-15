# Eval 02: Dataset preparation: train-only CSVs with held-out test sets

- Date(s): 2026-10-15
- Versions: Omen 0.0.5 (`main` at `a3bd5c1`); Python 3.14; pandas, numpy (see
  `evaluation/requirements.txt`); no LLMs evaluated in this step
- AI assistance for this step: Claude Code 2.1.301 with Claude Opus 5.5
  (`claude-opus-5-5`) researched sources, wrote the pipeline, tests, and this
  record; the maintainer chose the fresh-data sources and pilot composition.
  Logged in `scoping-out-a-journal-submission/ai-model-ledger.md`.
- Issue: #44 (tracking issue #59)
- Plan: `scoping-out-a-journal-submission/evaluation-plan.md`, Section 2

## Procedure

`python evaluation/prepare_data.py --set <pilot|full>` builds a dataset set:

1. **M4:** downloads `M4-info.csv` and the Daily/Weekly/Monthly train and
   test CSVs from the M4-methods repository. SHA-256 checksums are recorded
   on first download (`evaluation/data/manifests/m4_checksums.json`) and
   verified on every later run.
2. **Fresh series:** reads frozen API responses from
   `evaluation/data/snapshots/` (fetching any that are missing). All 25
   candidates (15 Wikimedia articles, 10 cities) were fetched on 2026-10-15
   and committed, so later builds don't depend on the APIs.
3. **Sampling:** a seeded permutation per M4 frequency and per fresh source;
   a set takes the first *n* valid candidates. Smaller sets are therefore
   prefixes of larger ones, so the pilot set is a subset of the full set.
4. **Validity checks** drop and replace a candidate (in seeded order) if
   it has missing values or any non-positive value. Dropped candidates are
   listed in the manifest.
5. **Split:** M4 keeps its official split (its test file is exactly the
   horizon). Fresh series hold out their last 14 days.
6. **Write:** `train/<id>.csv` and `heldout/<id>.csv` (`date,value`) in
   separate sibling directories under `evaluation/data/prepared/<set>/`. Only
   `train/` is ever given to an agent.
7. **Leakage and contamination checks** (`omen_eval/checks.py`) run on the
   in-memory split and again on the written files, and fail the build on any
   problem:
   - held-out length equals the horizon;
   - held-out dates strictly follow train with no shared dates;
   - train+held-out dates form a regular series (`pd.infer_freq`), with no
     gaps;
   - the `train/` and `heldout/` directories don't overlap or nest;
   - no held-out date appears in any written train CSV;
   - every contamination-control series' test window starts on or after
     2026-07-01.
8. **Manifest:** written per set with the parameters, every series' source,
   frequency, horizon, license, date ranges, and SHA-256 of both CSVs.
   It contains no data values. A copy is committed at
   `evaluation/data/manifests/<set>.json`.

## Parameters and configuration

All in `evaluation/omen_eval/config.py`:

| Parameter | Value |
|---|---|
| Seed | 20261015 |
| M4 frequencies and horizons | daily 14, weekly 13, monthly 18 (M4 standard) |
| Fresh series range | 2023-07-01 to 2026-10-11, last 14 days held out |
| Contamination cutoff for test windows | 2026-07-01 |
| Pilot set | 5 M4 per frequency, 3 Wikimedia, 2 Open-Meteo (20 series) |
| Full set | placeholder: 100 M4 per frequency, 15 Wikimedia, 10 Open-Meteo (**set at Eval 08**) |
| Wikimedia | en.wikipedia, `all-access`, `agent=user` (excludes bots), daily |
| Open-Meteo | `temperature_2m_mean` (°C), historical archive API, `timezone=auto` |

**Wikimedia articles:** a fixed a-priori list of 15 evergreen
general-topic articles, chosen to avoid news-driven traffic: Coffee,
Bicycle, Volcano, Photosynthesis, Chess, Jazz, Moon, Pizza, Mathematics,
Rainbow, Library, Honey, Piano, Weather, Tea.

**Open-Meteo cities:** 10 warm-climate cities (Singapore, Mumbai, Lagos,
Bangkok, Jakarta, Manila, Miami, Dubai, Brasília, Honolulu), chosen so daily
mean temperature stays strictly positive.

### Contamination cutoff (2026-07-01)

The contamination cutoff is the later of the evaluated models' training cutoffs:

- **Claude 5 generation:** June 2026 cutoff.
- **GLM-5.2:** Z.ai publishes no knowledge cutoff for any GLM model
  ([fixaeo.com cutoff table](https://fixaeo.com/ai-knowledge-cutoff/)). One
  secondary source claims March 2026
  ([Handy AI](https://handyai.substack.com/p/model-drop-glm-52)), with no
  official source behind it. GLM-5.2 was released around 2026-06-13 to
  06-16, and a model can't have trained on data from after its release, so
  the release date is used as a conservative upper bound on its cutoff.

Both bounds fall within June 2026, so test windows must start on or after
2026-07-01. **Re-check this at Eval 08** if the chosen Claude model has a
later cutoff.

### M4 date reconstruction

M4-info gives each start as `dd-mm-yy HH:MM`, and the two-digit year is
ambiguous. The century is chosen as the latest (20yy, else 19yy) for which
the whole series (train + test) ends no later than 2018-12-31, when M4 was
collected. The frequencies are built as follows:

- **Monthly:** starts are normalized to the 1st of the month (`MS`).
- **Weekly:** anchored to the start date's weekday.
- **Daily:** consecutive calendar days.

M4's dates are known to be only nominal; they're reconstructed so that Omen's
date-based tools (`load_series`, frequency inference) work. No date-derived
features enter the comparison.

## Deviations from plan

- **Weather series are restricted to warm-climate cities.** This was not in
  the plan. It keeps every value strictly positive so sMAPE/MAPE are well
  defined. The trade-off is that the weather series all have muted
  seasonality, and that limitation should be stated.
- **Positivity is a validity rule for every series**, not just weather. M4
  values are positive by construction, and pageviews almost always are.
- **The contamination cutoff uses GLM-5.2's release date**, because no
  official training cutoff exists (see above).
- **M4 raw data are not committed**, because the source repository has no
  license. Reproducibility relies on the download URL and the recorded
  checksums.
- **The full-set size is a placeholder** (100 per M4 frequency). The real
  size is fixed at Eval 08; only the pilot set was built here.

## Results

Pilot set built 2026-10-15: **20 series, all checks passed, no candidates
dropped**. A rebuild produced a byte-identical manifest, and Omen 0.0.5's
`load_series` and `basic_stats` read every train CSV with a regular inferred
frequency.

| Group | Series | Train length | Test window |
|---|---|---|---|
| M4 daily | D3783, D3147, D4064, D2880, D1909 | 112–4,197 | 14 days, ending 1998–2013 |
| M4 weekly | W302, W264, W126, W138, W171 | 80–1,044 | 13 weeks, ending 2014–2017 |
| M4 monthly | M33997, M9617, M1241, M20642, M10818 | 69–306 | 18 months, ending 2016–2017 |
| Wikimedia | Library, Piano, Tea | 1,185 | 2026-09-28 to 2026-10-11 |
| Open-Meteo | Miami, Manila | 1,185 | 2026-09-28 to 2026-10-11 |

Exact date ranges and file checksums are in `evaluation/data/manifests/pilot.json`.

Testing: 16 offline tests (`pytest evaluation/tests`) cover the M4 date
rule, sampling determinism and prefix stability, parsing, gap detection, and
every check. The package's own 161 tests still pass, and `ruff check .` is
clean.

## Cost

No LLM tokens. Network: ~195 MB of M4 downloads plus 25 small API requests.

## Artifacts

- `evaluation/data/manifests/pilot.json`: pilot manifest (ids, ranges, SHA-256 of every CSV).
- `evaluation/data/manifests/m4_checksums.json`: SHA-256 of the downloaded M4 files.
- `evaluation/data/snapshots/`: frozen Wikimedia and Open-Meteo responses
  for all 25 fresh candidates (fetched 2026-10-15; ~2.8 MB).
- Prepared CSVs and raw M4 files are regenerated locally and are not
  committed.

## Notes for the paper

- Feeds **Methods (data)**: the sources, the sampling rule, the M4
  horizons, the date reconstruction, and the leakage checks.
- Feeds the contamination-control rationale and its date bound.
- **Limitations:**
  - the fresh set is daily only (too little post-cutoff time for other
    frequencies);
  - the weather series are warm-climate only;
  - M4 dates are nominal;
  - Open-Meteo's most recent archive values were preliminary when frozen;
    the snapshot is the reference, not the live API.
- **Citations:**
  - Makridakis, Spiliotis & Assimakopoulos (2020), *IJF* 36(1), 54–74.
  - Open-Meteo: Zippenfenig (2023), doi:10.5281/ZENODO.7970649, with the
    attribution line "Weather data by Open-Meteo.com" (CC BY 4.0).
  - Wikimedia pageviews: CC0.
