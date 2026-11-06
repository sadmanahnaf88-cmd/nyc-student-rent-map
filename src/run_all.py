"""
Run the whole pipeline, in order, stopping at the first error.

    python src/run_all.py                  # everything, re-downloading NTA + GTFS
    python src/run_all.py --skip-download  # reuse the raw files already on disk

StreetEasy files are a manual download (docs/DATA_DOWNLOAD.md) and must
already be in data/raw/streeteasy/.
"""
import argparse
import os
import subprocess
import sys
import time

import config

STEPS = [
    ("p2a_load_rent.py", "Phase 2: load StreetEasy rents", False),
    ("p2b_rent_summary.py", "Phase 2: rent summary (SQL)", False),
    ("p3a_download_nta.py", "Phase 3: download NTA boundaries", True),
    ("p3b_build_crosswalk.py", "Phase 3: StreetEasy <-> NTA crosswalk", False),
    ("p3c_rent_by_nta.py", "Phase 3: rent by NTA (SQL)", False),
    ("p4a_download_gtfs.py", "Phase 4: download MTA GTFS", True),
    ("p4b_commute_times.py", "Phase 4: commute times", False),
    ("p4c_validate_commute.py", "Phase 4: validate commutes", False),
    ("p5_analysis.py", "Phase 5: analysis + insights (SQL)", False),
    ("p6_tableau_export.py", "Phase 6: Tableau export", False),
    ("p7_survey_compare.py", "Phase 7: survey comparison", False),
]


def main(skip_download: bool) -> None:
    se_files = list((config.DATA_RAW / "streeteasy").glob("*.zip")) + \
               list((config.DATA_RAW / "streeteasy").glob("*.csv"))
    if len(se_files) < 8:
        sys.exit("StreetEasy files missing: see docs/DATA_DOWNLOAD.md")

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}  # DuckDB output on Windows
    for script, label, is_download in STEPS:
        if is_download and skip_download:
            print(f"--- {label}: skipped (--skip-download)")
            continue
        print(f"\n=== {label} ({script}) ===", flush=True)
        t0 = time.time()
        result = subprocess.run([sys.executable, str(config.ROOT / "src" / script)],
                                cwd=config.ROOT, env=env)
        if result.returncode != 0:
            sys.exit(f"\nFAILED at {script}. Fix the error above and re-run.")
        print(f"--- done in {time.time() - t0:.0f}s")
    print("\nAll steps finished. Tableau files are in data/processed/, findings in docs/INSIGHTS.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true")
    main(parser.parse_args().skip_download)
