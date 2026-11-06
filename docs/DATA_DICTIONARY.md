# Data dictionary: Tableau files (`data/processed/`)

All files are produced by `src/p6_tableau_export.py`. Yes/no columns are `TRUE` / `FALSE` / **blank**. Blank means *unknown*, not "no".

## `tableau_main.csv`: one row per campus × NTA × housing type

| Column | Meaning |
|---|---|
| `campus_id`, `campus_name` | Destination campus (from `data/reference/campuses.csv`) |
| `nta2020` | NTA code: **join key** to `tableau_nta_boundaries.geojson` |
| `nta_name`, `borough` | NTA name and borough (2020 NTAs, NYC Dept. of City Planning) |
| `lat`, `lon` | NTA centre point used as the commute origin (D-017) |
| `housing` | Studio (alone) · 1BR (alone) · 2BR (2 roommates) · 3BR+ (3 roommates) · Cheapest option |
| `cheapest_housing` | Only on "Cheapest option" rows: which type was cheapest per person there |
| `occupants` | People sharing the unit (rent is split equally, D-006) |
| `rent_per_person` | $/month per person: median of monthly StreetEasy median asking rents, latest 12 months (D-005) |
| `rent_per_person_peak` | Same, June–September only (lease-signing season) |
| `rent_reliability` | high / medium / low / no_data, based on listing volume (D-009) |
| `rent_usable` | TRUE if reliability is high or medium; the analysis only uses these |
| `mapping_confidence` | high / medium / low: how sure we are which StreetEasy neighborhood(s) this NTA's rent comes from (D-016) |
| `uses_proxy` | TRUE if rent was borrowed from an adjacent neighborhood because StreetEasy doesn't list this area |
| `commute_min` | Door-to-door weekday AM-peak subway commute, minutes (D-018) |
| `commute_status` | `subway`, `walk` (walking is fastest), or `needs_bus_or_rail` (over 20 min of walking at one end: real trip uses a bus or LIRR, time is an upper bound) |
| `commute_known` | FALSE when `commute_status = needs_bus_or_rail` |
| `lines` | Subway lines in order, e.g. `G > F` |
| `n_transfers` | Number of train changes |
| `board_station` | Station where the trip boards the first train |
| `within_30_min`, `within_45_min`, `within_60_min` | Commute ≤ limit. Blank if commute unknown |
| `affordable_1000`, `affordable_1500`, `affordable_2000` | `rent_per_person` ≤ budget. Blank if rent not usable |
| `is_best_value` | TRUE if no other NTA (same campus, same housing) is both cheaper **and** faster (Pareto frontier, D-021) |
| `is_popular` | Among the 15 NTAs with the most rental listings (D-023) |
| `popularity_rank` | 1 = most listings |
| `listings_per_year_est` | Estimated rental listings per year in this NTA (all bedroom types) |

## `tableau_nta_boundaries.geojson`
NTA polygons (WGS84), simplified about 15 ft. Fields: `nta2020`, `nta_name`, `borough`, `nta_type` (residential / park / cemetery / airport / special_use / rikers_island), `in_scope` (residential and not Staten Island). Out-of-scope polygons are included so the map has no holes. Grey them out.

## `tableau_swaps.csv`: "live here instead of there"
One row per campus × housing type × popular NTA: the cheapest alternative NTA that adds at most 15 minutes each way. Alternatives never use proxy rents.

| Column | Meaning |
|---|---|
| `popular_nta`, `popular_rent`, `popular_commute_min` | The popular area |
| `alternative_nta`, `alternative_borough`, `alternative_rent`, `alternative_commute_min`, `alternative_lines` | Its best cheaper alternative |
| `monthly_savings`, `yearly_savings` | Rent saved per person |
| `extra_minutes_one_way` | Alternative minus popular commute (negative = alternative is *faster*) |
| `alternative_rent_reliability`, `alternative_mapping_confidence` | Data quality of the alternative |

## `tableau_scenarios.csv`: how many NTAs work
One row per campus × housing type × budget × commute limit: `ntas_with_rent`, `ntas_affordable`, `ntas_reachable`, `ntas_affordable_and_reachable`, and `which_ntas` (names, cheapest first).

## `tableau_campuses.csv`, `tableau_stations.csv`
Campus points (name, address, lat/lon, `is_home_campus`) and subway station points (from MTA GTFS), for extra map layers.
