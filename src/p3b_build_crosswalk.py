"""
Phase 3b: build the crosswalk between StreetEasy neighborhoods and NTAs.

INPUT   data/raw/nta/nta2020.geojson                    (p3a_download_nta.py)
        data/interim/rent_summary.csv                   (Phase 2, for the SE names)
        data/reference/se_nta_crosswalk_manual.csv      hand-built rows with evidence
OUTPUT  data/interim/se_nta_crosswalk.csv/.xlsx         one row per (SE neighborhood, NTA) pair
        data/interim/nta_areas.csv                      one row per NTA: name, type, centroid lat/lon
        data/interim/nta_boundaries.geojson             NTA polygons (for maps / Tableau later)

Why a crosswalk table? The two sources divide the city differently:
  * one SE neighborhood can cover several NTAs   (Astoria -> 4 NTAs)
  * one NTA can contain several SE neighborhoods (Carroll Gardens, Cobble Hill,
    Gowanus, Red Hook -> 1 NTA)
A many-to-many link table is the standard way to model that, and joins
in SQL become simple.

How rows are created:
  1. AUTOMATIC: an SE name exactly equals one of the parts of an NTA name, in the
     same borough. NTA names are split on "-" with parentheses dropped, e.g.
     "Downtown Brooklyn-DUMBO-Boerum Hill" -> {downtown brooklyn, dumbo, boerum hill}
  2. MANUAL: data/reference/se_nta_crosswalk_manual.csv covers everything the
     rule can't, and every row there records its evidence and a confidence level.

Run from the project folder:
    python src/p3b_build_crosswalk.py
"""
import re

import geopandas as gpd
import pandas as pd

import config

NTA_FILE = config.DATA_RAW / "nta" / "nta2020.geojson"
MANUAL_FILE = config.ROOT / "data" / "reference" / "se_nta_crosswalk_manual.csv"

# NTA type codes (checked against the names in the data, see D-015)
NTA_TYPES = {"0": "residential", "5": "rikers_island", "6": "special_use",
             "7": "cemetery", "8": "airport", "9": "park"}

NY_STATE_PLANE = 2263  # coordinate system in feet, accurate for NYC distances/areas


def normalize(name: str) -> str:
    """Lowercase, unify '&'/'St.', strip punctuation so names can be compared."""
    name = name.lower().replace("&", " and ").replace("st.", "saint")
    name = re.sub(r"[^a-z0-9 ]+", " ", name)
    return " ".join(name.split())


def name_parts(nta_name: str) -> set[str]:
    """'Astoria (East)-Woodside (North)' -> {'astoria', 'woodside'}"""
    without_parens = re.sub(r"\(.*?\)", "", nta_name)
    return {normalize(p) for p in without_parens.split("-") if p.strip()}


def load_ntas() -> gpd.GeoDataFrame:
    nta = gpd.read_file(NTA_FILE)
    nta["nta_type"] = nta["ntatype"].map(NTA_TYPES)
    assert nta["nta_type"].notna().all(), "unknown NTA type code"

    # Centroid for commute calculations. Computed in feet-based coordinates
    # (lat/long centroids are slightly distorted). For odd shapes the centroid
    # can fall outside the polygon (e.g. in the water off Breezy Point), so we
    # then use representative_point(), which is guaranteed to be inside (D-017).
    projected = nta.to_crs(NY_STATE_PLANE)
    centroid = projected.centroid
    inside = centroid.within(projected.geometry)
    point = centroid.where(inside, projected.representative_point())
    point_ll = gpd.GeoSeries(point, crs=NY_STATE_PLANE).to_crs(4326)
    nta["lat"], nta["lon"] = point_ll.y.round(6), point_ll.x.round(6)
    nta["centroid_inside"] = inside.values
    nta["area_sq_mi"] = (projected.area / 27_878_400).round(3)  # sq ft -> sq mi
    return nta


def automatic_matches(se: pd.DataFrame, nta: gpd.GeoDataFrame) -> pd.DataFrame:
    residential = nta[nta["nta_type"] == "residential"]
    rows = []
    for s in se.itertuples():
        target = normalize(s.area_name)
        for n in residential[residential["boroname"] == s.borough].itertuples():
            if target in name_parts(n.ntaname):
                rows.append({"se_area_name": s.area_name, "se_borough": s.borough,
                             "nta2020": n.nta2020, "match_type": "auto_name",
                             "confidence": "high",
                             "evidence": f"SE name is part of NTA name '{n.ntaname}'"})
    return pd.DataFrame(rows)


def main() -> None:
    nta = load_ntas()
    se = (pd.read_csv(config.DATA_INTERIM / "rent_summary.csv")
            .drop_duplicates("area_name")[["area_name", "borough"]])

    auto = automatic_matches(se, nta)
    manual = pd.read_csv(MANUAL_FILE)
    xwalk = pd.concat([auto, manual], ignore_index=True)

    # ---- Validation: fail loudly on mistakes in the manual file -------------
    unknown_nta = set(xwalk["nta2020"]) - set(nta["nta2020"])
    assert not unknown_nta, f"manual file has unknown NTA codes: {unknown_nta}"
    unknown_se = set(xwalk["se_area_name"]) - set(se["area_name"])
    assert not unknown_se, f"manual file has unknown SE names: {unknown_se}"
    dupes = xwalk[xwalk.duplicated(["se_area_name", "nta2020"], keep=False)]
    assert dupes.empty, f"duplicate pairs (manual row repeats an auto match?):\n{dupes}"

    # Attach NTA names so the file is readable on its own (e.g. in Excel)
    xwalk = xwalk.merge(nta[["nta2020", "ntaname", "boroname", "nta_type"]],
                        on="nta2020", how="left")
    assert (xwalk["nta_type"] == "residential").all(), "SE mapped to a non-residential NTA"

    # How many NTAs each SE neighborhood spreads over, and vice versa
    xwalk["se_n_ntas"] = xwalk.groupby("se_area_name")["nta2020"].transform("count")
    xwalk["nta_n_se"] = xwalk.groupby("nta2020")["se_area_name"].transform("count")
    xwalk = xwalk.sort_values(["se_borough", "se_area_name", "nta2020"])

    xwalk.to_csv(config.DATA_INTERIM / "se_nta_crosswalk.csv", index=False)
    xwalk.to_excel(config.DATA_INTERIM / "se_nta_crosswalk.xlsx", index=False)

    areas = nta.drop(columns="geometry")[["nta2020", "ntaname", "boroname", "nta_type",
                                          "lat", "lon", "centroid_inside", "area_sq_mi"]]
    areas.to_csv(config.DATA_INTERIM / "nta_areas.csv", index=False)
    nta[["nta2020", "ntaname", "boroname", "nta_type", "geometry"]].to_file(
        config.DATA_INTERIM / "nta_boundaries.geojson", driver="GeoJSON")

    # ---- Coverage report ---------------------------------------------------
    print(f"Crosswalk rows: {len(xwalk)}  (auto {len(auto)}, manual {len(manual)})")
    print("By match type / confidence:")
    print(xwalk.groupby(["match_type", "confidence"]).size().to_string(), "\n")

    unused_se = set(se["area_name"]) - set(xwalk["se_area_name"])
    print(f"SE neighborhoods not linked to any NTA: {len(unused_se)} {sorted(unused_se)}")

    in_scope = nta[(nta["nta_type"] == "residential") & (nta["boroname"] != "Staten Island")]
    no_se = in_scope[~in_scope["nta2020"].isin(xwalk["nta2020"])]
    print(f"Residential NTAs (excl. Staten Island) with no SE rent source: {len(no_se)} "
          f"{list(no_se['ntaname'])}")

    print(f"\nNTAs whose centroid fell outside the polygon (used an inside point instead): "
          f"{list(nta.loc[~nta['centroid_inside'], 'ntaname'])}")

    print("\nSE neighborhoods spread over the most NTAs:")
    print(xwalk.drop_duplicates("se_area_name").nlargest(5, "se_n_ntas")
              [["se_area_name", "se_n_ntas"]].to_string(index=False))
    print("\nNTAs combining the most SE neighborhoods:")
    print(xwalk.drop_duplicates("nta2020").nlargest(5, "nta_n_se")
              [["ntaname", "nta_n_se"]].to_string(index=False))


if __name__ == "__main__":
    main()
