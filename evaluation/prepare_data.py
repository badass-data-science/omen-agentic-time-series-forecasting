"""Build an evaluation dataset set (Eval 02, #44).

    python evaluation/prepare_data.py --set pilot
    python evaluation/prepare_data.py --set full            # size fixed at Eval 08
    python evaluation/prepare_data.py --set pilot --refresh-fresh   # re-fetch snapshots

Downloads M4 (verified against recorded checksums), reads the frozen fresh-data
snapshots (fetching any that are missing), samples with a fixed seed, writes
train/ and heldout/ CSVs, runs every leakage and contamination check, and
writes the manifest. Exits non-zero if any check fails.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from omen_eval import config, prepare


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", choices=sorted(config.SETS), required=True)
    parser.add_argument("--refresh-fresh", action="store_true",
                        help="re-fetch fresh-data snapshots instead of reading the frozen ones")
    args = parser.parse_args()

    series, dropped = prepare.collect(args.set, refresh_fresh=args.refresh_fresh)
    manifest = prepare.write_set(args.set, series, dropped)
    by_source: dict[str, int] = {}
    for entry in manifest["series"]:
        key = f"{entry['source']}/{entry['frequency']}"
        by_source[key] = by_source.get(key, 0) + 1
    print(f"set '{args.set}': {manifest['n_series']} series, all checks passed")
    for key, n in sorted(by_source.items()):
        print(f"  {key}: {n}")
    if dropped:
        print(f"  dropped {len(dropped)} candidate(s); see manifest 'dropped'")
    print(f"  written to {config.PREPARED_DIR / args.set}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
