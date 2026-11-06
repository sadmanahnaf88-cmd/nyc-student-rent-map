"""
Phase 4c: sanity-check the commute model and compare it with a straight-line baseline.

INPUT   data/interim/commute_times.csv, nta_areas.csv, data/reference/campuses.csv
OUTPUT  data/interim/commute_baseline_comparison.csv
        printed checks (copy the interesting bits into your write-up)

Three checks:
  1. CAMPUS SIDE: is each campus within walking distance of the subway? If not,
     every trip to it gets flagged and the subway model doesn't suit that campus.
  2. SPOT CHECKS: well-known trips printed with their route, so a person who
     knows NYC can judge them (and compare with Google Maps / the MTA app).
  3. BASELINE: the "simple version" from the project plan, straight-line
     distance / one average speed. Where does it go most wrong, and why?

Run from the project folder:
    python src/p4c_validate_commute.py
"""
import pandas as pd

import config


def main() -> None:
    c = pd.read_csv(config.DATA_INTERIM / "commute_times.csv")
    names = pd.read_csv(config.DATA_INTERIM / "nta_areas.csv")[["nta2020", "ntaname"]]
    campuses = pd.read_csv(config.CAMPUSES_FILE)[["campus_id", "campus_name"]]
    c = c.merge(names, on="nta2020").merge(campuses, on="campus_id")
    pd.set_option("display.width", 220)

    # ---- 1. Campus side ---------------------------------------------------
    print("1. CAMPUS ACCESS: median walk from the subway to campus, share of trips flagged")
    camp = (c[c["mode"] == "subway"].groupby("campus_name")
              .agg(egress_walk_min=("egress_walk_min", "median"),
                   flagged_share=("needs_bus_or_rail", "mean"))
              .sort_values("egress_walk_min", ascending=False).round(2))
    print(camp.to_string(), "\n")

    # ---- 2. Spot checks -----------------------------------------------------
    checks = [("nyu_wsq", "Astoria (Central)"), ("nyu_wsq", "Bushwick (West)"),
              ("nyu_wsq", "Washington Heights (South)"), ("nyu_wsq", "Flatbush"),
              ("columbia", "Upper West Side (Central)"), ("columbia", "Park Slope"),
              ("baruch", "Jackson Heights"), ("brooklyn_college", "Bedford-Stuyvesant (West)"),
              ("hunter", "Long Island City-Hunters Point"), ("fordham_rh", "Harlem (South)")]
    keys = pd.DataFrame(checks, columns=["campus_id", "ntaname"])
    print("2. SPOT CHECKS: do these look right to someone who rides the subway?")
    print(c.merge(keys)[["campus_id", "ntaname", "commute_min", "walk_min", "wait_min",
                          "ride_min", "transfer_min", "lines", "board_station",
                          "alight_station"]].to_string(index=False), "\n")

    # ---- 3. Straight-line baseline ------------------------------------------
    ok = c[(c["mode"] == "subway") & ~c["needs_bus_or_rail"]].copy()
    # One citywide "door-to-door speed" fitted from our own model: the
    # baseline gets the best possible single speed, so differences are due
    # to geography (rivers, express lines), not a bad guess at speed.
    speed_kmh = (ok["straight_line_km"].sum() / (ok["commute_min"].sum() / 60))
    ok["baseline_min"] = ok["straight_line_km"] / speed_kmh * 60
    ok["model_minus_baseline"] = ok["commute_min"] - ok["baseline_min"]
    mae = ok["model_minus_baseline"].abs().mean()

    print(f"3. BASELINE: best single door-to-door speed = {speed_kmh:.1f} km/h "
          f"({speed_kmh / 1.609:.1f} mph, straight-line)")
    print(f"   Average error of the straight-line estimate: {mae:.1f} min")
    print(f"   Share of trips where it's off by more than 15 min: "
          f"{(ok['model_minus_baseline'].abs() > 15).mean():.0%}")
    cols = ["campus_id", "ntaname", "straight_line_km", "baseline_min", "commute_min", "lines"]
    print("\n   Baseline far too OPTIMISTIC (close on a map, slow by subway):")
    print(ok.nlargest(6, "model_minus_baseline")[cols].round(1).to_string(index=False))
    print("\n   Baseline far too PESSIMISTIC (far on a map, fast by express train):")
    print(ok.nsmallest(6, "model_minus_baseline")[cols].round(1).to_string(index=False))

    ok[["campus_id", "nta2020", "ntaname", "straight_line_km", "baseline_min", "commute_min",
        "model_minus_baseline", "lines"]].round(1).to_csv(
        config.DATA_INTERIM / "commute_baseline_comparison.csv", index=False)


if __name__ == "__main__":
    main()
