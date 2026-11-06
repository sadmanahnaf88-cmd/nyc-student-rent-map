"""
Phase 6: export Tableau-ready files to data/processed/.

INPUT   DuckDB tables from Phase 5 (affordability, swaps, scenario_summary, nta_popularity)
        data/interim/nta_boundaries.geojson, subway_stations.csv, data/reference/campuses.csv
OUTPUT  data/processed/
          tableau_main.csv              campus x NTA x housing type: the main table
          tableau_nta_boundaries.geojson  NTA polygons (join to tableau_main on nta2020)
          tableau_swaps.csv             "live here instead of there" pairs
          tableau_scenarios.csv         counts per campus x housing x budget x limit
          tableau_campuses.csv          campus points
          tableau_stations.csv          subway station points
See docs/DATA_DICTIONARY.md for every column and docs/TABLEAU_GUIDE.md for how to load them.

Design choices (D-025):
  * Long ("tidy") main table: one row per campus x NTA x housing type. Tableau
    filters/parameters pick the campus and housing type; nothing is hard-coded.
  * Explicit TRUE/FALSE flags per budget and commute limit, so you can drag a
    flag onto Color without writing calculated fields. A flag is BLANK when we
    don't know (unreliable rent, or a trip that needs a bus): blank != FALSE.
  * Readable labels ("2BR (2 roommates)") instead of codes.

Run from the project folder (after Phase 5):
    python src/p6_tableau_export.py
"""
import duckdb
import geopandas as gpd
import pandas as pd

import config

OUT = config.DATA_PROCESSED

HOUSING_LABELS = {
    "studio": "Studio (alone)",
    "1br": "1BR (alone)",
    "2br": "2BR (2 roommates)",
    "3br_plus": "3BR+ (3 roommates)",
    "any (cheapest)": "Cheapest option",
}


def main_table(con) -> pd.DataFrame:
    df = con.sql("""
        SELECT a.*, p.listings_per_year_est, p.popularity_rank
        FROM affordability a LEFT JOIN nta_popularity p USING (nta2020)
    """).df()

    df["housing"] = df["bedrooms"].map(HOUSING_LABELS)
    # Only meaningful on "Cheapest option" rows: which type turned out cheapest
    df["cheapest_housing"] = (df["cheapest_type"].map(HOUSING_LABELS)
                                .where(df["bedrooms"] == "any (cheapest)"))
    df["is_popular"] = df["popularity_rank"] <= config.POPULAR_TOP_N
    df["commute_min"] = df["commute_min"].round(0)

    # Commute flags: blank where the subway model can't give a real answer
    for limit in config.COMMUTE_LIMITS:
        df[f"within_{limit}_min"] = (df["commute_min"] <= limit).where(df["commute_known"])
    # Budget flags: blank where the rent isn't reliable enough to judge
    for budget in config.BUDGETS:
        df[f"affordable_{budget}"] = (df["rent_per_person"] <= budget).where(df["rent_usable"])

    # Write every yes/no column the same way: TRUE / FALSE / blank (= unknown)
    flag_cols = [c for c in df.columns if c.startswith(("within_", "affordable_"))]
    bool_cols = flag_cols + ["rent_usable", "uses_proxy", "commute_known",
                             "is_best_value", "is_popular"]
    for c in bool_cols:
        df[c] = df[c].map({True: "TRUE", False: "FALSE"})

    cols = (["campus_id", "campus_name", "nta2020", "ntaname", "boroname", "lat", "lon",
             "housing", "cheapest_housing", "occupants",
             "rent_per_person", "rent_per_person_peak", "rent_reliability", "rent_usable",
             "mapping_confidence", "uses_proxy",
             "commute_min", "commute_status", "commute_known", "lines", "n_transfers", "board_station"]
            + flag_cols
            + ["is_best_value", "is_popular", "popularity_rank", "listings_per_year_est"])
    order = {label: i for i, label in enumerate(HOUSING_LABELS.values())}
    df = df.sort_values(["campus_id", "nta2020", "housing"], key=lambda s: s.map(order) if s.name == "housing" else s)
    return df[cols].rename(columns={"ntaname": "nta_name", "boroname": "borough"})


def main() -> None:
    con = duckdb.connect(str(config.DB_PATH), read_only=True)

    main_df = main_table(con)
    main_df.to_csv(OUT / "tableau_main.csv", index=False)

    swaps = con.sql("SELECT * FROM swaps").df()
    swaps["housing"] = swaps["bedrooms"].map(HOUSING_LABELS)
    swaps["yearly_savings"] = swaps["monthly_savings"] * 12
    swaps.drop(columns="bedrooms").to_csv(OUT / "tableau_swaps.csv", index=False)

    sc = con.sql("SELECT * EXCLUDE (which_ntas), which_ntas FROM scenario_summary").df()
    sc["housing"] = sc["bedrooms"].map(HOUSING_LABELS)
    sc.drop(columns="bedrooms").to_csv(OUT / "tableau_scenarios.csv", index=False)

    pd.read_csv(config.CAMPUSES_FILE).to_csv(OUT / "tableau_campuses.csv", index=False)
    pd.read_csv(config.DATA_INTERIM / "subway_stations.csv").to_csv(
        OUT / "tableau_stations.csv", index=False)

    # Boundaries: simplify (~15 ft tolerance) so the file is small and fast in
    # Tableau Public, without visible change at city scale.
    nta = gpd.read_file(config.DATA_INTERIM / "nta_boundaries.geojson").to_crs(2263)
    nta["geometry"] = nta.simplify(15, preserve_topology=True)
    nta["in_scope"] = (nta["nta_type"] == "residential") & (nta["boroname"] != "Staten Island")
    nta.to_crs(4326).rename(columns={"ntaname": "nta_name", "boroname": "borough"}).to_file(
        OUT / "tableau_nta_boundaries.geojson", driver="GeoJSON")

    for f in sorted(OUT.glob("tableau_*")):
        print(f"{f.name:34} {f.stat().st_size / 1e6:6.2f} MB")
    print(f"\ntableau_main: {len(main_df):,} rows x {main_df.shape[1]} columns")

    # Integrity checks
    assert main_df.duplicated(["campus_id", "nta2020", "housing"]).sum() == 0, "duplicate rows"
    assert main_df["nta2020"].isin(nta["nta2020"]).all(), "NTA code missing from boundaries"


if __name__ == "__main__":
    main()
