# Loading the data in Tableau Public

## 1. Connect
1. **Connect → Spatial file** → `data/processed/tableau_nta_boundaries.geojson`.
2. In the Data Source pane, **add** `tableau_main.csv` (Text file) and create a **relationship** on `nta2020 = nta2020`.
   - Use a relationship (the "noodle"), not a join. Tableau then keeps the 181 polygons separate from the 15k data rows and avoids duplicating geometry.
3. Optional extra sources: `tableau_swaps.csv`, `tableau_scenarios.csv` (standalone), `tableau_campuses.csv` and `tableau_stations.csv` (for point layers on the map).

## 2. Set data types
Tableau usually guesses right. Check that:
- `TRUE` / `FALSE` columns are **Boolean**
- `nta2020` is **String**
- `lat` / `lon` have **Geographic role → Latitude / Longitude**

## 3. Suggested controls
- **Filter `campus_name`**: single value (dropdown), *Show filter*. Set the default to your campus.
- **Filter `housing`**: single value. Start with "Cheapest option".
- **Parameter "Budget"**: integer list 1000 / 1500 / 2000, and a calculated field:
  `IF NOT [rent_usable] THEN "Not enough rent data" ELSEIF [rent_per_person] <= [Budget] THEN "Affordable" ELSE "Over budget" END`
- **Parameter "Max commute"**: 30 / 45 / 60, and a field:
  `IF NOT [commute_known] THEN "Needs bus/LIRR" ELSEIF [commute_min] <= [Max commute] THEN "Within limit" ELSE "Too far" END`

The pre-computed `affordable_*` and `within_*_min` columns let you skip parameters entirely if you prefer.

## 4. Ideas for views (your design)
- **Map**: polygons coloured by the combination of the two fields above. Grey out `in_scope = FALSE`. Campus as a point layer.
- **Scatter**: `commute_min` (x) vs `rent_per_person` (y), one dot per NTA, with `is_best_value` highlighted. This is the Pareto frontier.
- **Swap table** from `tableau_swaps.csv`: "instead of X, live in Y, save $Z".
- **Scenario bars** from `tableau_scenarios.csv`: number of NTAs affordable and reachable, by budget.
- **Caption / data notes**: the caveats at the bottom of `docs/INSIGHTS.md`, plus why the $1,000 map is almost empty (D-012).

## 5. Tooltip fields worth adding
`nta_name`, `rent_per_person`, `rent_reliability`, `commute_min`, `lines`, `n_transfers`, `mapping_confidence`, and `uses_proxy` (so viewers can see when a number is shaky).
