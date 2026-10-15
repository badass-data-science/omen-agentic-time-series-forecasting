"""Fixed parameters for the evaluation datasets (Eval 02, #44).

Everything that determines *which* series and *which* dates end up in a set
lives here, so the paper record can cite one file. Changing any value here
changes the dataset: record it as a deviation in
evaluation/records/eval-02-datasets.md.
"""

from pathlib import Path

import pandas as pd

EVAL_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = EVAL_DIR / "data"
RAW_DIR = DATA_DIR / "raw"  # gitignored: downloaded M4 files
SNAPSHOT_DIR = DATA_DIR / "snapshots"  # committed: frozen fresh-data API responses
MANIFEST_DIR = DATA_DIR / "manifests"  # committed: checksums and per-set manifests
PREPARED_DIR = DATA_DIR / "prepared"  # gitignored: train/ and heldout/ CSVs per set

SEED = 20261015

# --- Contamination control -------------------------------------------------
# Test windows of the fresh (contamination-control) series must start on or
# after this date. It is the later of: the Claude 5 generation's June 2026
# training cutoff, and GLM-5.2's release (mid-June 2026; Z.ai publishes no
# cutoff, and a model can't have trained on data from after its release).
# Re-check if a model with a later cutoff is added at Eval 08.
CONTAMINATION_TEST_START = pd.Timestamp("2026-07-01")

# --- M4 ---------------------------------------------------------------------
M4_BASE_URL = "https://raw.githubusercontent.com/Mcompetitions/M4-methods/master/Dataset"
# frequency label -> (M4 file prefix, horizon, pandas frequency kind)
M4_FREQUENCIES = {
    "daily": ("Daily", 14, "D"),
    "weekly": ("Weekly", 13, "W"),
    "monthly": ("Monthly", 18, "MS"),
}
# M4 data were collected up to 2018; used to resolve two-digit start years.
M4_LATEST_PLAUSIBLE_END = pd.Timestamp("2018-12-31")

# --- Fresh daily series -----------------------------------------------------
FRESH_TRAIN_START = pd.Timestamp("2023-07-01")
FRESH_DATA_END = pd.Timestamp("2026-10-11")  # last day of every fresh series (test end)
FRESH_HORIZON = 14

USER_AGENT = "omen-eval/0.1 (https://github.com/badass-data-science/omen-agentic-time-series-forecasting)"

# A fixed, a-priori list of evergreen general-topic English Wikipedia articles,
# chosen to avoid news-driven topics. Order doesn't matter (sampling is seeded).
WIKIMEDIA_ARTICLES = [
    "Coffee", "Bicycle", "Volcano", "Photosynthesis", "Chess",
    "Jazz", "Moon", "Pizza", "Mathematics", "Rainbow",
    "Library", "Honey", "Piano", "Weather", "Tea",
]
WIKIMEDIA_LICENSE = "CC0 1.0 (Wikimedia Analytics datasets)"

# Warm-climate cities, so daily mean temperature (deg C) stays strictly positive
# and percentage-error metrics (sMAPE, MAPE) stay meaningful.
OPEN_METEO_CITIES = {
    "singapore": (1.2897, 103.8501),
    "mumbai": (19.0760, 72.8777),
    "lagos": (6.5244, 3.3792),
    "bangkok": (13.7563, 100.5018),
    "jakarta": (-6.2088, 106.8456),
    "manila": (14.5995, 120.9842),
    "miami": (25.7617, -80.1918),
    "dubai": (25.2048, 55.2708),
    "brasilia": (-15.7939, -47.8828),
    "honolulu": (21.3069, -157.8583),
}
OPEN_METEO_VARIABLE = "temperature_2m_mean"
OPEN_METEO_LICENSE = "CC BY 4.0, attribution: 'Weather data by Open-Meteo.com'"

# --- Sets -------------------------------------------------------------------
# Counts per M4 frequency and per fresh source. "pilot" is fixed (Eval 01/02);
# "full" is a placeholder until the main study's scale is approved at Eval 08.
SETS = {
    "pilot": {"m4_per_frequency": 5, "wikimedia": 3, "open_meteo": 2},
    "full": {"m4_per_frequency": 100, "wikimedia": 15, "open_meteo": 10},
}
