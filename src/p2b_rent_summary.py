"""
Phase 2b: summarise rents in DuckDB and export Excel-friendly files.

INPUT   data/interim/rent_long.csv            (from p2a_load_rent.py)
        sql/p2_rent_summary.sql               (the actual logic, in SQL)
OUTPUT  data/interim/rent_map.duckdb          tables: rent_long, occupants, params, rent_summary
        data/interim/rent_summary.csv/.xlsx   neighborhoods only, one row per neighborhood x bedrooms
        data/interim/rent_reference.csv       borough + citywide rows (for sanity checks)

The division of labour: Python handles files and settings; SQL does the
joining and aggregating. That way the SQL file reads on its own as the method.

Run from the project folder:
    python src/p2b_rent_summary.py
"""
import duckdb
import pandas as pd

import config


def main() -> None:
    con = duckdb.connect(str(config.DB_PATH))

    # --- 1. Load inputs into DuckDB -----------------------------------------
    rent_csv = (config.DATA_INTERIM / "rent_long.csv").as_posix()
    con.execute(f"""
        CREATE OR REPLACE TABLE rent_long AS
        SELECT * FROM read_csv('{rent_csv}', header = true,
                               columns = {{
                                   'area_name': 'VARCHAR', 'borough': 'VARCHAR',
                                   'area_type': 'VARCHAR', 'bedrooms': 'VARCHAR',
                                   'month': 'DATE', 'median_rent': 'DOUBLE',
                                   'listings': 'DOUBLE'}})
    """)  # explicit column types so DuckDB never guesses wrong

    occupants = pd.DataFrame(list(config.OCCUPANTS_PER_UNIT.items()),
                             columns=["bedrooms", "occupants"])
    con.execute("CREATE OR REPLACE TABLE occupants AS SELECT * FROM occupants")
    # ^ DuckDB can query a pandas DataFrame directly by its variable name.

    con.execute("CREATE OR REPLACE TABLE params AS SELECT ?::INTEGER AS window_months, "
                "?::INTEGER[] AS peak_months",
                [config.RENT_WINDOW_MONTHS, config.PEAK_SEASON_MONTHS])

    # --- 2. Run the SQL -------------------------------------------------------
    con.execute((config.SQL_DIR / "p2_rent_summary.sql").read_text())

    # --- 3. Export -----------------------------------------------------------
    nb = con.sql("SELECT * EXCLUDE (area_type) FROM rent_summary "
                 "WHERE area_type = 'neighborhood'").df()
    ref = con.sql("SELECT * FROM rent_summary WHERE area_type <> 'neighborhood'").df()

    nb.to_csv(config.DATA_INTERIM / "rent_summary.csv", index=False)
    nb.to_excel(config.DATA_INTERIM / "rent_summary.xlsx", index=False, sheet_name="rent_summary")
    ref.to_csv(config.DATA_INTERIM / "rent_reference.csv", index=False)

    w_start, w_end = nb["window_start"].iloc[0], nb["window_end"].iloc[0]
    print(f"Window: {w_start:%Y-%m} to {w_end:%Y-%m}")
    print(f"Wrote {len(nb)} neighborhood rows and {len(ref)} reference rows\n")

    # --- 4. Quick validation printout ----------------------------------------
    print("Reliability by bedroom type (number of neighborhoods):")
    print(nb.pivot_table(index="bedrooms", columns="reliability", values="area_name",
                         aggfunc="count", fill_value=0)
            .reindex(index=list(config.OCCUPANTS_PER_UNIT),
                     columns=["high", "medium", "low", "no_data"], fill_value=0))

    print("\nReliability by borough, all bedroom types (does missing data cluster anywhere?):")
    print(nb.pivot_table(index="borough", columns="reliability", values="area_name",
                         aggfunc="count", fill_value=0)
            .reindex(columns=["high", "medium", "low", "no_data"], fill_value=0))

    print("\nBorough/citywide per-person rent, 12-month median:")
    print(ref.pivot(index="area_name", columns="bedrooms", values="rent_per_person")
             [list(config.OCCUPANTS_PER_UNIT)].to_string())


if __name__ == "__main__":
    main()
