"""
Phase 3a: download the 2020 Neighborhood Tabulation Area (NTA) boundaries.

SOURCE  NYC Open Data, dataset 9nt8-h7nd, published by NYC Dept. of City Planning
        https://data.cityofnewyork.us/City-Government/2020-Neighborhood-Tabulation-Areas-NTAs-/9nt8-h7nd
OUTPUT  data/raw/nta/nta2020.geojson  (+ a row in docs/raw_data_manifest.csv)

Why script this instead of a manual download (like StreetEasy)? NYC Open Data
has a stable API meant for programs, so a script is more reproducible.
StreetEasy offers no API, so that one stays manual.

Run from the project folder:
    python src/p3a_download_nta.py
"""
import config
from manifest import download

URL = "https://data.cityofnewyork.us/resource/9nt8-h7nd.geojson"
# The API returns at most 1,000 rows by default; NYC has ~260 NTAs, but we ask
# for more explicitly so we never silently get a truncated file.
PARAMS = {"$limit": 5000}


def main() -> None:
    content = download(URL, config.DATA_RAW / "nta" / "nta2020.geojson", PARAMS)
    n_features = content.count(b'"type":"Feature"')
    print(f"{n_features} NTA features")
    assert n_features > 250, "fewer NTAs than expected: download may be truncated"


if __name__ == "__main__":
    main()
