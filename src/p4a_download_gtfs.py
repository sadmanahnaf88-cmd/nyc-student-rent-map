"""
Phase 4a: download the MTA subway GTFS (static schedule) feed.

SOURCE  MTA developer data: regular (not supplemented) subway GTFS
        https://new.mta.info/developers
OUTPUT  data/raw/gtfs/gtfs_subway.zip  (+ a row in docs/raw_data_manifest.csv)

GTFS ("General Transit Feed Specification") is the standard format for
transit schedules: a zip of CSV-like .txt files: stops, routes, trips,
stop_times (every train's arrival at every stop), transfers, calendar.

We use the REGULAR feed, not the "supplemented" one: the supplemented feed
includes short-term planned service changes (weekend work etc.), which would
make our "typical commute" depend on whichever week we downloaded (D-019).

Run from the project folder:
    python src/p4a_download_gtfs.py
"""
import zipfile

import config
from manifest import download

URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"
OUT = config.DATA_RAW / "gtfs" / "gtfs_subway.zip"


def main() -> None:
    download(URL, OUT)
    with zipfile.ZipFile(OUT) as z:
        names = z.namelist()
    print("Files in feed:", ", ".join(sorted(names)))
    required = {"stops.txt", "routes.txt", "trips.txt", "stop_times.txt", "calendar.txt"}
    missing = required - set(names)
    assert not missing, f"GTFS feed is missing {missing}"


if __name__ == "__main__":
    main()
