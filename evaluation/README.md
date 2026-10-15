# Omen evaluation study

Code, data manifests, and paper records for the empirical evaluation of Omen
described in
[`scoping-out-a-journal-submission/evaluation-plan.md`](../scoping-out-a-journal-submission/evaluation-plan.md)
and tracked in issue #59 (Eval 01–16).

This directory is **not part of the `omen` package**: it isn't shipped in the
PyPI wheel or sdist, and it has its own dependencies.

```bash
pip install -r evaluation/requirements.txt
pytest evaluation/tests                            # offline tests
python evaluation/prepare_data.py --set pilot      # build the pilot dataset
```

## Layout

| Path | What | Committed? |
|---|---|---|
| `omen_eval/` | Evaluation code (`config.py` holds every dataset parameter) | Yes |
| `prepare_data.py` | Builds a dataset set (Eval 02) | Yes |
| `tests/` | Offline tests | Yes |
| `records/` | Paper records, one per Eval issue (`eval-NN-<slug>.md`) | Yes |
| `data/manifests/` | Per-set manifests (ids, date ranges, file checksums) and M4 checksums | Yes |
| `data/snapshots/` | Frozen API responses for the fresh contamination-control series | Yes |
| `data/raw/` | Downloaded M4 files (no license to redistribute) | No |
| `data/prepared/<set>/train/` | Train CSVs: the **only** data an agent may see | No |
| `data/prepared/<set>/heldout/` | Held-out test periods, for scoring only | No |

## Data sources and attribution

- **M4**: Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2020). The M4
  Competition: 100,000 time series and 61 forecasting methods. *International
  Journal of Forecasting*, 36(1), 54–74. Downloaded from
  [Mcompetitions/M4-methods](https://github.com/Mcompetitions/M4-methods),
  which has no license file, so the data are not redistributed here.
- **Wikimedia pageviews**: Wikimedia REST API, CC0 1.0.
- **Open-Meteo**: Weather data by [Open-Meteo.com](https://open-meteo.com/),
  CC BY 4.0. Cite: Zippenfenig, P. (2023). Open-Meteo.com Weather API.
  Zenodo. doi:10.5281/ZENODO.7970649.
