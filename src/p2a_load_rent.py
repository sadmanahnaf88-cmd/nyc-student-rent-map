"""
Phase 2a: load the StreetEasy rent files and reshape them into one tidy table.

INPUT   data/raw/streeteasy/  8 files (median asking rent + rental inventory,
                              for studio / 1BR / 2BR / 3+BR). See docs/DATA_DOWNLOAD.md.
OUTPUT  data/interim/rent_long.csv
        one row per  area x bedroom type x month, with columns:
        area_name, borough, area_type, bedrooms, month, median_rent, listings

Why reshape? The raw files are "wide": one column per month (200+ columns).
That's convenient to read but awkward to analyse. "Long" (tidy) format, with one
row per observation, is what SQL, pandas groupby, Excel pivot tables and
Tableau all expect.

Run from the project folder:
    python src/p2a_load_rent.py
"""
import argparse
from pathlib import Path

import pandas as pd

import config

# StreetEasy's file suffix  ->  our short bedroom label (matches config.OCCUPANTS_PER_UNIT)
BEDROOM_FILES = {
    "Studio": "studio",
    "OneBd": "1br",
    "TwoBd": "2br",
    "ThreePlusBd": "3br_plus",
}

# StreetEasy report name  ->  the column name we give its values
METRICS = {
    "medianAskingRent": "median_rent",
    "rentalInventory": "listings",
}


def find_file(raw_dir: Path, stem: str) -> Path:
    """Return the .csv or .zip for a file stem, or fail with a helpful message."""
    for ext in (".csv", ".zip"):
        path = raw_dir / f"{stem}{ext}"
        if path.exists():
            return path
    raise FileNotFoundError(
        f"Missing {stem}.zip (or .csv) in {raw_dir}. "
        "See docs/DATA_DOWNLOAD.md for the list of files to download."
    )


def load_one(raw_dir: Path, metric: str, se_suffix: str) -> pd.DataFrame:
    """Read one wide StreetEasy file and melt it to long format."""
    path = find_file(raw_dir, f"{metric}_{se_suffix}")
    wide = pd.read_csv(path)  # pandas unzips single-file .zip archives itself

    id_cols = ["areaName", "Borough", "areaType"]
    month_cols = [c for c in wide.columns if c not in id_cols]

    # Guard: every non-ID column should look like YYYY-MM. If StreetEasy ever
    # changes the format, fail loudly instead of producing garbage.
    bad = [c for c in month_cols if not pd.Series([c]).str.fullmatch(r"\d{4}-\d{2}").iloc[0]]
    if bad:
        raise ValueError(f"{path.name}: unexpected columns {bad[:5]}")

    long = wide.melt(id_vars=id_cols, value_vars=month_cols,
                     var_name="month", value_name=METRICS[metric])
    long["bedrooms"] = BEDROOM_FILES[se_suffix]
    return long


def main(raw_dir: Path) -> pd.DataFrame:
    frames = []
    for se_suffix in BEDROOM_FILES:
        rent = load_one(raw_dir, "medianAskingRent", se_suffix)
        inv = load_one(raw_dir, "rentalInventory", se_suffix)

        # Join rent and inventory on area + month. how="outer" keeps rows that
        # appear in only one file, so nothing is silently lost; we check below.
        keys = ["areaName", "Borough", "areaType", "month", "bedrooms"]
        merged = rent.merge(inv, on=keys, how="outer", validate="one_to_one")
        frames.append(merged)

    df = pd.concat(frames, ignore_index=True)

    # Tidy names and types
    df = df.rename(columns={"areaName": "area_name", "Borough": "borough",
                            "areaType": "area_type"})
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m")
    df = df[["area_name", "borough", "area_type", "bedrooms", "month",
             "median_rent", "listings"]]
    df = df.sort_values(["area_type", "borough", "area_name", "bedrooms", "month"])

    # ---- Sanity checks (fail loudly rather than continue with bad data) ----
    dupes = df.duplicated(["area_name", "borough", "bedrooms", "month"]).sum()
    assert dupes == 0, f"{dupes} duplicate area/bedroom/month rows"

    # Implausible rents (e.g. a $352,000 "2BR rent" in Marine Park, 2011: almost
    # certainly a sale price listed as a rental). We don't silently drop them:
    # they're saved to a separate file, then blanked out in the main table (D-008).
    LOW, HIGH = 300, 50_000
    implausible = df["median_rent"].notna() & ~df["median_rent"].between(LOW, HIGH)
    rejected = df[implausible].assign(reason=f"median_rent outside ${LOW:,}-${HIGH:,}")
    rejected.to_csv(config.DATA_INTERIM / "rent_rejected.csv", index=False,
                    date_format="%Y-%m-%d")
    df.loc[implausible, "median_rent"] = pd.NA
    print(f"Rejected implausible rent values: {len(rejected)} (see data/interim/rent_rejected.csv)")

    # Rows with a rent but no listings count would be strange, so report them
    odd = df[df["median_rent"].notna() & (df["listings"].isna() | (df["listings"] == 0))]
    print(f"Rows with a median rent but 0/missing listings: {len(odd)}")

    out = config.DATA_INTERIM / "rent_long.csv"
    df.to_csv(out, index=False, date_format="%Y-%m-%d")
    print(f"Wrote {len(df):,} rows -> {out.relative_to(config.ROOT)}")
    print(f"Months: {df['month'].min():%Y-%m} to {df['month'].max():%Y-%m}")
    print(f"Areas by type: {df.drop_duplicates('area_name')['area_type'].value_counts().to_dict()}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--raw-dir", type=Path,
                        default=config.DATA_RAW / "streeteasy",
                        help="folder containing the 8 StreetEasy files")
    args = parser.parse_args()
    main(args.raw_dir)
