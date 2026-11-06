"""
Phase 7: compare student survey answers with the public data.

INPUT   data/raw/survey/survey_responses.csv   (columns: data/reference/survey_template.csv;
                                                questions: docs/SURVEY_QUESTIONS.md)
        data/interim/rent_summary.csv, se_nta_crosswalk.csv, commute_times.csv
OUTPUT  data/reference/survey_neighborhood_options.csv   dropdown list for the survey form
                                                          (written every run, even without responses)
        data/interim/survey_matched.csv                  every response + its public-data match
                                                          (interim = git-ignored: has individual rows)
        data/processed/tableau_survey_comparison.csv     group summaries, only groups with >= 5 responses
        docs/SURVEY_FINDINGS.md                          auto-generated write-up

What gets compared (each answer lines up with a public-data column):
  * rent:     my_monthly_rent   vs  StreetEasy rent_per_person (same neighborhood + bedrooms)
  * sharing:  people_in_unit    vs  bedrooms (tests the one-person-per-bedroom assumption, D-006)
  * commute:  commute_min_typical vs modelled commute (campus x the neighborhood's NTAs)

Privacy (D-026): individual responses never leave data/interim/ (git-ignored).
Anything in data/processed/ or docs/ is aggregated to groups of >= SURVEY_MIN_GROUP.

Run from the project folder:
    python src/p7_survey_compare.py                         # uses config.SURVEY_FILE
    python src/p7_survey_compare.py --input other.csv --out-dir somewhere/   # e.g. testing
"""
import argparse
from pathlib import Path

import pandas as pd

import config

TEMPLATE = config.ROOT / "data" / "reference" / "survey_template.csv"
ALLOWED = {
    "bedrooms": {"studio", "1br", "2br", "3br_plus"},
    "utilities_included": {"yes", "no", "not sure"},
    "rent_stabilized": {"yes", "no", "not sure"},
    "lives_with_family": {"yes", "no"},
}


def write_dropdown_list() -> None:
    """Neighborhood names for the survey form, so answers match StreetEasy names exactly."""
    se = pd.read_csv(config.DATA_INTERIM / "rent_summary.csv")
    opts = se.drop_duplicates("area_name")[["borough", "area_name"]].sort_values(["borough", "area_name"])
    opts.rename(columns={"area_name": "neighborhood"}).to_csv(
        config.ROOT / "data" / "reference" / "survey_neighborhood_options.csv", index=False)


def load_and_validate(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = list(pd.read_csv(TEMPLATE).columns)
    missing = set(expected) - set(df.columns)
    if missing:
        raise SystemExit(f"Survey file is missing columns {sorted(missing)}. "
                         f"Rename your export's columns to match {TEMPLATE.name}.")

    # Normalise text answers so "Yes", "yes " and "YES" all count the same
    for c in ["consent", "utilities_included", "rent_stabilized", "lives_with_family", "commute_mode"]:
        df[c] = df[c].astype(str).str.strip().str.lower()
    df["bedrooms"] = df["bedrooms"].astype(str).str.strip().str.lower()

    n0 = len(df)
    df = df[df["consent"] == "yes"]
    print(f"Responses: {n0}; with consent: {len(df)}")

    problems = []
    for col, ok in ALLOWED.items():
        bad = ~df[col].isin(ok)
        if bad.any():
            problems.append(f"{bad.sum()} rows with unexpected {col}: {sorted(df.loc[bad, col].unique())[:5]}")
    se_names = set(pd.read_csv(config.DATA_INTERIM / "rent_summary.csv")["area_name"])
    unknown = ~df["neighborhood"].isin(se_names)
    if unknown.any():
        problems.append(f"{unknown.sum()} rows with a neighborhood not in StreetEasy's list "
                        f"(e.g. {sorted(df.loc[unknown, 'neighborhood'].astype(str).unique())[:5]}); "
                        "kept, but they can't be matched to public rent")
    for p in problems:
        print("  WARNING:", p)

    # Plausibility: drop impossible numbers, but say how many (never silently)
    rent_ok = df["my_monthly_rent"].between(100, 20_000)
    commute_ok = df["commute_min_typical"].between(1, 240)
    print(f"  Implausible rent values set to blank: {(~rent_ok & df['my_monthly_rent'].notna()).sum()}")
    print(f"  Implausible commute values set to blank: {(~commute_ok & df['commute_min_typical'].notna()).sum()}")
    df.loc[~rent_ok, "my_monthly_rent"] = pd.NA
    df.loc[~commute_ok, "commute_min_typical"] = pd.NA
    return df


def match_public(df: pd.DataFrame) -> pd.DataFrame:
    rent = pd.read_csv(config.DATA_INTERIM / "rent_summary.csv")[
        ["area_name", "bedrooms", "rent_per_person", "occupants", "reliability"]]
    xwalk = pd.read_csv(config.DATA_INTERIM / "se_nta_crosswalk.csv")[["se_area_name", "nta2020"]]
    commute = pd.read_csv(config.DATA_INTERIM / "commute_times.csv")

    # Modelled commute for a StreetEasy neighborhood = average over its NTAs
    # (only trips the subway model can handle)
    nb_commute = (xwalk.merge(commute[~commute["needs_bus_or_rail"]], on="nta2020")
                       .groupby(["se_area_name", "campus_id"], as_index=False)["commute_min"].mean()
                       .rename(columns={"se_area_name": "neighborhood",
                                        "commute_min": "model_commute_min"}))

    m = (df.merge(rent.rename(columns={"area_name": "neighborhood",
                                       "rent_per_person": "public_rent_per_person",
                                       "occupants": "assumed_occupants",
                                       "reliability": "public_rent_reliability"}),
                  on=["neighborhood", "bedrooms"], how="left")
           .merge(nb_commute, on=["neighborhood", "campus_id"], how="left"))

    # Rent comparison only for market-rate payers with a usable public number
    comparable = ((m["lives_with_family"] != "yes")
                  & m["public_rent_reliability"].isin(["high", "medium"]))
    m["rent_gap"] = (m["my_monthly_rent"] - m["public_rent_per_person"]).where(comparable)
    m["rent_gap_pct"] = (m["rent_gap"] / m["public_rent_per_person"] * 100).round(1)
    m["extra_people_vs_assumption"] = m["people_in_unit"] - m["assumed_occupants"]
    m["commute_gap_min"] = (m["commute_min_typical"] - m["model_commute_min"]).round(1)
    m["lease_year"] = pd.to_datetime(m["lease_start"], format="%Y-%m", errors="coerce").dt.year
    return m


def summarise(m: pd.DataFrame) -> pd.DataFrame:
    """Group summaries, suppressing any group smaller than SURVEY_MIN_GROUP."""
    rows = []
    groupings = {"all": None, "borough": "borough", "bedrooms": "bedrooms",
                 "rent_stabilized": "rent_stabilized", "lease_year": "lease_year",
                 "commute_mode": "commute_mode", "campus_id": "campus_id"}
    for name, col in groupings.items():
        groups = [("all", m)] if col is None else m.groupby(col, dropna=True)
        for value, g in groups:
            rows.append({
                "grouping": name, "group": value, "n_responses": len(g),
                "n_rent_compared": int(g["rent_gap"].notna().sum()),
                # Both medians over the SAME rows (those with a valid comparison)
                "median_my_rent": g.loc[g["rent_gap"].notna(), "my_monthly_rent"].median(),
                "median_public_rent": g.loc[g["rent_gap"].notna(), "public_rent_per_person"].median(),
                "median_rent_gap": g["rent_gap"].median(),
                "median_rent_gap_pct": g["rent_gap_pct"].median(),
                "share_more_people_than_bedrooms": (g["extra_people_vs_assumption"] > 0).mean(),
                "n_commute_compared": int(g["commute_gap_min"].notna().sum()),
                "median_commute_gap_min": g["commute_gap_min"].median(),
            })
    s = pd.DataFrame(rows)
    small = s["n_responses"] < config.SURVEY_MIN_GROUP
    value_cols = [c for c in s.columns if c not in ("grouping", "group", "n_responses")]
    s.loc[small, value_cols] = pd.NA
    s["suppressed_small_group"] = small
    return s.round(2)


def write_findings(s: pd.DataFrame, out_doc: Path) -> None:
    overall = s[s["grouping"] == "all"].iloc[0]
    fmt = lambda v, f="{:,.0f}": "n/a" if pd.isna(v) else f.format(v)
    lines = ["# Survey findings (auto-generated by `src/p7_survey_compare.py`)", "",
             f"Responses analysed: **{int(overall.n_responses)}**. Groups with fewer than "
             f"{config.SURVEY_MIN_GROUP} responses are hidden.", "",
             "## Overall", "",
             f"- Median rent students report paying: **${fmt(overall.median_my_rent)}** vs. public "
             f"asking rent for the same neighborhood/bedrooms: **${fmt(overall.median_public_rent)}** "
             f"(median gap **{fmt(overall.median_rent_gap_pct, '{:+.1f}')}%**, n={int(overall.n_rent_compared)}).",
             f"- Share living with more people than bedrooms (D-006 test): "
             f"**{fmt(overall.share_more_people_than_bedrooms, '{:.0%}')}**.",
             f"- Median reported commute minus modelled commute: "
             f"**{fmt(overall.median_commute_gap_min, '{:+.1f}')} min** (n={int(overall.n_commute_compared)}).", ""]
    for grouping in ["borough", "bedrooms", "rent_stabilized", "lease_year", "commute_mode"]:
        g = s[(s["grouping"] == grouping) & ~s["suppressed_small_group"]]
        if g.empty:
            continue
        lines += [f"## By {grouping.replace('_', ' ')}", "",
                  "| Group | n | Median rent gap | More people than bedrooms | Commute gap (min) |",
                  "|---|---|---|---|---|"]
        for r in g.itertuples():
            lines.append(f"| {r.group} | {r.n_responses} | {fmt(r.median_rent_gap_pct, '{:+.1f}')}% | "
                         f"{fmt(r.share_more_people_than_bedrooms, '{:.0%}')} | "
                         f"{fmt(r.median_commute_gap_min, '{:+.1f}')} |")
        lines.append("")
    lines += ["## How to read this", "",
              "- A negative rent gap = students pay less than today's asking rents (expected for older "
              "leases and rent-stabilized units, D-011).",
              "- A positive commute gap = real commutes are longer than the model (delays, buses, "
              "living far from the NTA centre point)."]
    out_doc.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(survey_path: Path, out_dir: Path | None) -> None:
    write_dropdown_list()
    if not survey_path.exists():
        print(f"No survey responses yet at {survey_path}.\n"
              "Wrote data/reference/survey_neighborhood_options.csv for your form's dropdown.\n"
              "See docs/SURVEY_QUESTIONS.md, then re-run this script once you have responses.")
        return

    interim = out_dir or config.DATA_INTERIM
    processed = out_dir or config.DATA_PROCESSED
    doc = (out_dir or config.ROOT / "docs") / "SURVEY_FINDINGS.md"

    m = match_public(load_and_validate(survey_path))
    m.to_csv(interim / "survey_matched.csv", index=False)
    s = summarise(m)
    s.to_csv(processed / "tableau_survey_comparison.csv", index=False)
    write_findings(s, doc)
    print(f"Wrote survey_matched.csv (individual rows, private), "
          f"tableau_survey_comparison.csv ({len(s)} groups), {doc.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--input", type=Path, default=config.SURVEY_FILE)
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="write all outputs here instead (for testing)")
    args = parser.parse_args()
    main(args.input, args.out_dir)
