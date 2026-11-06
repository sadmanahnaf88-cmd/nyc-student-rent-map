"""
Phase 3c: attach rent to every NTA (runs sql/p3_rent_by_nta.sql in DuckDB).

INPUT   data/interim/rent_summary.csv, se_nta_crosswalk.csv, nta_areas.csv
OUTPUT  DuckDB tables crosswalk, nta_areas, rent_by_nta (in data/interim/rent_map.duckdb)
        data/interim/rent_by_nta.csv/.xlsx

Run from the project folder (after p2b and p3b):
    python src/p3c_rent_by_nta.py
"""
import duckdb

import config


def main() -> None:
    con = duckdb.connect(str(config.DB_PATH))

    for table, file in [("crosswalk", "se_nta_crosswalk.csv"), ("nta_areas", "nta_areas.csv")]:
        path = (config.DATA_INTERIM / file).as_posix()
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv('{path}', header = true)")

    con.execute((config.SQL_DIR / "p3_rent_by_nta.sql").read_text())

    df = con.sql("SELECT * FROM rent_by_nta").df()
    df.to_csv(config.DATA_INTERIM / "rent_by_nta.csv", index=False)
    df.to_excel(config.DATA_INTERIM / "rent_by_nta.xlsx", index=False, sheet_name="rent_by_nta")

    print(f"Wrote {len(df)} rows ({df['nta2020'].nunique()} NTAs x {df['bedrooms'].nunique()} bedroom types)\n")
    print("Rent reliability by mapping confidence (rows):")
    print(df.pivot_table(index="mapping_confidence", columns="rent_reliability",
                         values="nta2020", aggfunc="count", fill_value=0)
            .reindex(index=["high", "medium", "low"],
                     columns=["high", "medium", "low", "no_data"], fill_value=0))

    # Check: an NTA built from a single SE neighborhood must reproduce that rent exactly
    mismatches = con.execute("""
        SELECT count(*) FROM rent_by_nta n
        JOIN rent_summary r ON r.area_name = n.se_sources AND r.bedrooms = n.bedrooms
        WHERE n.n_sources = 1 AND r.area_type = 'neighborhood'
          AND n.rent_per_person IS DISTINCT FROM r.rent_per_person
    """).fetchone()[0]
    print(f"\nSingle-source NTAs whose rent differs from the source: {mismatches} (should be 0)")


if __name__ == "__main__":
    main()
