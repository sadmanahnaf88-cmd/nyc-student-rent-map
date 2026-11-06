# Decisions Log

Every judgment call in this project: what was decided, why, what else was considered, and what it affects. Newest entries at the bottom. If a decision is later reversed, don't delete it: mark it **Superseded by D-0XX** and add the new entry.

Template:

```
## D-0XX: <short title>
- **Phase:** 
- **Decision:** 
- **Why:** 
- **Alternatives considered:** 
- **Impact / risk:** 
```

---

## D-001: Python virtual environment inside the project folder
- **Phase:** 1
- **Decision:** Use a `.venv` folder in the project root, created with Python 3.12's built-in `venv`. Loose minimum versions in `requirements.txt`; exact versions frozen in `requirements-lock.txt`.
- **Why:** Isolates this project's packages from other projects. `venv` is built in, so there's nothing extra to install (conda would be heavier). Two files: `requirements.txt` says what we *need*, the lock file says exactly what *worked*, so results can be reproduced.
- **Alternatives considered:** conda (better for some geospatial libraries, but geopandas now installs cleanly with pip on Windows); uv/poetry (faster/fancier, but extra tools to learn for no real gain here).
- **Impact / risk:** The project lives in OneDrive, which tries to sync the ~thousands of files in `.venv`. If syncing gets slow, exclude `.venv` from OneDrive or move the project out of OneDrive.

## D-002: Raw and interim data are not committed to git; processed outputs are
- **Phase:** 1
- **Decision:** `data/raw/` and `data/interim/` are git-ignored. `data/processed/` (final Tableau CSVs) is committed.
- **Why:** Raw files are large (the GTFS feed) and re-downloadable, and the StreetEasy data has its own terms of use. Survey data contains personal information and must never be public. Final outputs are small and are what a portfolio reviewer wants to see.
- **Alternatives considered:** Committing everything (bloated repo, privacy risk); Git LFS (unnecessary complexity).
- **Impact / risk:** Someone cloning the repo must follow the README to re-download raw data.

## D-003: DuckDB instead of SQLite for the SQL work
- **Phase:** 1
- **Decision:** Use DuckDB, stored as `data/interim/rent_map.duckdb`.
- **Why:** DuckDB is built for analytical queries (GROUP BY, joins, window functions), which is exactly this project's workload. It can query CSV files and pandas DataFrames directly (`SELECT * FROM 'file.csv'`), so there's less loading code between Python and SQL. Its SQL dialect is close to PostgreSQL, which is what most analyst jobs use.
- **Alternatives considered:** SQLite: more widely known, but weaker for analytics (limited date functions, no direct CSV querying). Both count as "SQL on a résumé."
- **Impact / risk:** The database file is rebuilt from raw data by the scripts and is never edited by hand.

## D-004: All settings in `src/config.py`
- **Phase:** 1
- **Decision:** Campus location, budgets, commute limits, and occupants per unit type live in one Python file.
- **Why:** One place to change an assumption, and it makes the assumptions easy to find and quote in interviews.
- **Alternatives considered:** A YAML/JSON config file (needs an extra library and is harder to comment well).
- **Impact / risk:** None.

## D-005: Summarise the latest 12 months, using the median of monthly medians
- **Phase:** 2
- **Decision:** For each neighborhood × bedroom type, "typical rent" = the median of the monthly median asking rents over the latest 12 months in the data (first run: Nov 2025 – Oct 2026). A second column gives the same thing for **peak season only (June–September)**, when most students sign leases.
- **Why:** One month is noisy. Small neighborhoods swing hundreds of dollars from month to month, and rents are seasonal. Twelve months covers one full seasonal cycle. Using a *median* of monthly values (not an average) means a single strange month can't move the result much. The peak-season column matters because students don't get to sign in February.
- **Alternatives considered:** Latest month only (too noisy, more missing data); listing-weighted average (more weight to busy months, but sensitive to outlier months and harder to explain); 24-month window (more data, but mixes in older price levels in a rising market).
- **Impact / risk:** Results describe roughly the past year, not today. Peak-season rents ran about 0–15% above the 12-month figure in the spot checks.

## D-006: Per-person rent = unit rent ÷ number of bedrooms (equal split, studio and 1BR = 1 person)
- **Phase:** 2
- **Decision:** studio ÷ 1, 1BR ÷ 1, 2BR ÷ 2, 3+BR ÷ 3. Rent split equally.
- **Why:** The simplest defensible assumption: one person per bedroom. It's the standard way roommates split rent and the easiest to explain.
- **Alternatives considered:** Couples sharing a 1BR (÷2); converting a living room into an extra bedroom (2BR ÷ 3, common among students but often not legal and not universal); splitting by room size. The survey (Phase 7) can test which is realistic.
- **Impact / risk:** Real students who squeeze in extra roommates pay less than our numbers. Ours are a "standard arrangement" baseline. Utilities are **not** included: StreetEasy reports asking rent only.

## D-007: The "3+ bedrooms" category is split three ways
- **Phase:** 2
- **Decision:** Treat StreetEasy's 3+BR median as a 3-bedroom and divide by 3.
- **Why:** StreetEasy doesn't break out 4BR or 5BR. Most 3+ listings are 3BRs, and dividing by 3 is the conservative choice.
- **Alternatives considered:** Dividing by an assumed average bedroom count, such as 3.3 (would be inventing a number we don't have).
- **Impact / risk:** Where many 4–5BR units are in the mix, the 3+ median is pushed up and dividing by 3 **overstates** per-person rent. The error goes in the safe direction for a "can I afford it" question.

## D-008: Implausible rent values are removed, but logged, not silently dropped
- **Phase:** 2
- **Decision:** Monthly medians outside $300–$50,000 are blanked out and written to `data/interim/rent_rejected.csv` with a reason.
- **Why:** The first run hit Marine Park 2BR, Sept 2011 = **$352,000/month**, based on 2 listings. That's almost certainly a sale price entered as a rental. The thresholds are deliberately loose so they only catch obvious errors, not legitimately expensive or cheap units.
- **Alternatives considered:** A statistical outlier rule (e.g. 3 standard deviations), but real luxury rents would trip it.
- **Impact / risk:** 1 value rejected out of 147k rows, and it falls outside the analysis window anyway.

## D-009: Reliability tiers based on data volume; low-volume rows are flagged, not dropped
- **Phase:** 2
- **Decision:** Each neighborhood × bedroom row gets a tier, where *listing-months* = the sum of monthly listing counts over the window:
  - **high**: at least 60 listing-months *and* rent in at least 10 of 12 months
  - **medium**: at least 24 listing-months *and* at least 6 months
  - **low**: some data, but below medium
  - **no_data**: no published rent in the window
- **Why:** StreetEasy publishes a "median" even when there's **only 1 listing**. In the past year, 848 neighborhood-months had a median based on a single apartment. So a published number alone doesn't mean a reliable one. The thresholds work out to roughly 5 listings per month (high) and 2 per month (medium).
- **Alternatives considered:** Dropping low-volume rows. We didn't, because the gaps cluster in the **Bronx and Queens** (the cheaper boroughs: Bronx has 77 low + 21 no_data of 168 rows vs Manhattan 4 + 3 of 128). Dropping them would bias the map toward expensive areas, which is exactly the wrong direction for a student-affordability question.
- **Impact / risk:** The thresholds are judgment calls. Analysis (Phase 5) will by default use high+medium and show low as "limited data". Listing-months count a unit once per month it's listed, so they measure volume, not unique apartments.

## D-010: Only StreetEasy neighborhoods are analysed; Staten Island has no neighborhood-level data
- **Phase:** 2
- **Decision:** The neighborhood rows (176) are the unit of analysis. Borough and citywide rows go to a separate `rent_reference.csv` for sanity checks only.
- **Why:** Mixing levels would double-count in Tableau. StreetEasy publishes **no Staten Island neighborhoods**, only a borough total, and Staten Island isn't on the subway apart from the Staten Island Railway.
- **Impact / risk:** Staten Island is effectively out of scope. We should say so on the dashboard.

## D-011: Known bias: asking rents describe *listed* apartments, not what tenants pay
- **Phase:** 2
- **Decision:** Use StreetEasy as-is, and state the bias clearly rather than trying to "correct" it.
- **Why:** Listings over-represent new construction and units turning over at market price. Rent-stabilized and long-held units (about half of NYC rentals) rarely appear. The spot check shows it: **Mott Haven studios ($2,800) list higher than Washington Heights studios ($2,295)**, probably because Mott Haven's listings are dominated by new buildings.
- **Impact / risk:** Our rents are an upper-end estimate of what a student will find *searching listings today*. Phase 7 (survey) measures the gap directly.

## D-012: Keep the $1,000 budget level even though almost nothing qualifies
- **Phase:** 2
- **Decision:** Budgets stay at $1,000 / $1,500 / $2,000 per person per month.
- **Why:** In the test run, only 5 neighborhoods were affordable at $1,000 per person (high/medium reliability), and only in 3+BR apartments split three ways. Showing that is a finding in itself: at the budget many students actually have, market-rate listings barely work, even with roommates. Removing the level would hide that.
- **Alternatives considered:** Replacing $1,000 with $1,250 so every budget level shows a meaningful spread on the map.
- **Impact / risk:** At $1,000 the map will be almost empty. The dashboard needs a caption explaining that this is the point, not a bug. It also strengthens the Phase 7 survey question of what students on ~$1,000 actually do (more roommates, rent-stabilized units, living with family).

## D-013: Record a checksum for every raw file, because StreetEasy revises published data
- **Phase:** 2
- **Decision:** `docs/raw_data_manifest.csv` (committed to git) records each raw file's name, download date, and SHA-256 checksum, a fingerprint that changes if even one value in the file changes.
- **Why:** On 2026-11-05 two copies of `medianAskingRent_OneBd.zip` downloaded four hours apart differed in **66 values**, some as far back as 2012 (e.g. Gramercy Park 1BR, latest month: $5,495 → $5,250). StreetEasy revises history without notice. Raw files aren't in git (D-002), so without a fingerprint nobody could tell which version produced our results.
- **Alternatives considered:** Committing raw files to git (rejected in D-002); recording the date only (not enough, since the file changed within one day).
- **Impact / risk:** Results are tied to this exact snapshot. If the data is re-downloaded later, numbers may shift slightly. Compare checksums to check.

## D-014: NTAs are the map and commute unit; StreetEasy neighborhoods are the rent source
- **Phase:** 3
- **Decision:** The final dataset has one row per residential NTA (181, excluding Staten Island). Each NTA takes its rent from the StreetEasy neighborhood(s) linked to it.
- **Why:** NTAs are official, non-overlapping polygons that cover the city, so they map cleanly in Tableau. StreetEasy publishes no boundaries at all. NTAs are also smaller than many StreetEasy areas (Astoria is 4 NTAs), which makes commute estimates more precise. They also join directly to census data if we want income or population later.
- **Alternatives considered:** StreetEasy neighborhoods as the unit, with shapes built by merging NTAs. Rejected because where several StreetEasy neighborhoods fall in one NTA (Carroll Gardens, Cobble Hill, Gowanus, Red Hook, Columbia St), they would all get the same overlapping polygon.
- **Impact / risk:** Where one StreetEasy neighborhood covers several NTAs, those NTAs share the same rent, so the map shows uniform rent across them even if reality varies.

## D-015: Non-residential NTAs and Staten Island are excluded
- **Phase:** 3
- **Decision:** Only `ntatype = 0` (residential) NTAs outside Staten Island get rent. The other codes were checked against the NTA names in the data: 5 = Rikers Island, 6 = special use (Navy Yard, UN, Sunnyside Yards), 7 = cemetery, 8 = airport, 9 = park. They stay in the boundaries file, so the map has no holes, but get no rent.
- **Why:** Nobody rents an apartment in Prospect Park or JFK. Staten Island has no StreetEasy neighborhoods (D-010).
- **Impact / risk:** None for the analysis. The dashboard should grey these out and label them.

## D-016: How the crosswalk is built, and how multi-source NTAs are combined
- **Phase:** 3
- **Decision:**
  1. **Automatic link** (182 rows) when a StreetEasy name exactly equals one part of an NTA name in the same borough (NTA names split on "-", parentheses dropped).
  2. **Manual links** (43 rows) in `data/reference/se_nta_crosswalk_manual.csv`, each with a match type, confidence and written evidence:
     - **name_variant**: the same place spelled differently (Seagate / Sea Gate, Central Harlem / Harlem N+S)
     - **evidence**: a Wikipedia article's coordinates fall inside the NTA, or its title redirects to the NTA's name
     - **hierarchy**: StreetEasy groups an un-listed sub-area under a bigger neighborhood (Ravenswood → Long Island City)
     - **judgment** or **proxy** (low confidence): no evidence, so the nearest named neighborhood is used and flagged
  3. When several StreetEasy neighborhoods feed one NTA, the NTA's rent is their **average weighted by listing-months**. The lowest and highest source rents are kept as separate columns, so the blend doesn't hide variation (e.g. SoHo $6,375 vs Little Italy $2,575 per person, 2BR, in one NTA).
  4. Each NTA carries the **worst** confidence of its sources, plus a `uses_proxy` flag.
- **Why:** Name matching handles the easy 81%. The rest needs judgment, and judgment must be visible and reviewable rather than buried in code. Weighting by listings reflects where the apartments actually are.
- **Alternatives considered:** Fuzzy matching (rapidfuzz). It produces confident-looking wrong matches ("East Tremont" ≈ "Tremont") and still needs manual review. NYC GeoSearch geocoder: returns addresses and landmarks, not neighborhoods ("Greenwood" → Greenwood *Lake*). A DCP neighborhood-points dataset: not found in the current NYC Open Data catalog. Simple averages for multi-source NTAs: would let a neighborhood with 5 listings count as much as one with 3,000.
- **Impact / risk:** Coverage is complete in both directions: every StreetEasy neighborhood is used and every in-scope residential NTA has a rent. 10 links are low confidence (9 proxies + East Tremont), marked `REVIEW` in the manual file. **These need checking by someone who knows the neighborhoods.** All are in the West Bronx, Ocean Hill, Madison, Queensboro Hill and Baisley Park.

## D-017: NTA "center" point = centroid, or an inside point if the centroid falls outside the polygon
- **Phase:** 3
- **Decision:** Commute origins (Phase 4) use each NTA's geometric centroid, calculated in NY State Plane feet (EPSG:2263). For 6 oddly shaped NTAs where the centroid lands outside the polygon (e.g. in the water off Breezy Point, or between Pelham Bay and City Island), we use `representative_point()`, which is guaranteed to be inside.
- **Why:** Centroids in lat/long degrees are slightly distorted; a feet-based projection is accurate for NYC. A commute starting from the middle of Jamaica Bay would be meaningless.
- **Alternatives considered:** Population-weighted centroids (better, since people don't live evenly across an NTA, but needs census block data; possible upgrade). Multiple origin points per NTA (more accurate, much more computation).
- **Impact / risk:** For large NTAs, one point can't represent everyone's commute. Pelham Bay-Country Club-City Island is the worst case: City Island is far from the subway.

## D-018: Commute model = graph built from GTFS schedules (not straight-line, not r5py)
- **Phase:** 4
- **Decision:** Door-to-door time = walk to a nearby station + wait (half the AM-peak headway) + scheduled ride time + transfers + walk to campus. Routes are found with Dijkstra's shortest-path algorithm (`networkx`) on a graph of stations and route-platforms built from the MTA GTFS feed.
- **Why:** About 90% of r5py's accuracy for this question, runs in under 30 seconds, and every component can be explained in one sentence. "Half the headway" is the standard expected wait when people don't time their arrival.
- **Alternatives considered:**
  - Straight-line distance ÷ average speed: kept only as a **baseline**. It's off by 14 min on average and by more than 15 min on 38% of trips (see `p4c_validate_commute.py`).
  - **r5py** (full timetable routing on real streets): most accurate, but needs Java 21 (not installed) and a ~400 MB OpenStreetMap extract, and is harder to debug. The best upgrade path, especially for adding buses.
  - Google Maps API: costs money, terms limit storing results, not reproducible.
- **Settings** (all in `config.py`): weekday departures 07:30–09:30; walk at 80 m/min (3 mph) × 1.3 street-detour factor; stations up to 1.6 km from home (always at least the 3 nearest); 2 min street-to-platform; GTFS `min_transfer_time` (usually 3 min) each time you get off a train; wait capped at 15 min; walking the whole way allowed up to 4 km.
- **Impact / risk:** Scheduled service, so no delays. Express and local patterns of the same route share a node, so a path can mix them slightly optimistically. Walking is straight-line × 1.3, not on real streets.

## D-019: Regular GTFS feed, not the "supplemented" one
- **Phase:** 4
- **Decision:** Use `gtfs_subway.zip` (regular schedule).
- **Why:** The supplemented feed includes short-term planned work, so "typical commute" would depend on the week of download. The regular feed already reflects permanent changes. The model routes the F via Court Sq-23 St, matching the December 2025 F/M swap.
- **Impact / risk:** Doesn't reflect current weekend or overnight disruptions, which don't matter for weekday-morning commutes.

## D-020: Trips needing more than 20 min of walking are flagged `needs_bus_or_rail`, not given a fake time
- **Phase:** 4
- **Decision:** If access or egress walking exceeds 20 minutes, the trip is flagged. Its time is kept as an upper bound, but the analysis treats it as **unknown**: neither "reachable" nor "too far".
- **Why:** The first run "walked" up to 2 hours from eastern Queens. People there take a bus or the LIRR, which a subway-only model can't see. Inventing a bus time would be making up data, and calling these areas "unreachable" would be wrong too.
- **Impact / risk:** 27 NTAs are flagged for every campus. These are NYC's known transit deserts: Co-op City, College Point, Bayside, Laurelton, Throgs Neck and others. A few (Hunts Point, Middle Village, Howard Beach, Breezy Point) do have a station, but their single centre point is far from it (D-017). **Queens College and St. John's** are 44 and 23 min walks from the subway, so every trip to them is flagged. The model doesn't suit those two campuses; adding buses via r5py would.

## D-021: "Best value" = Pareto frontier
- **Phase:** 5
- **Decision:** An option is best value if no other NTA (same campus, same housing type) is at least as cheap *and* at least as fast, and strictly better on one. Implemented as a SQL `NOT EXISTS` self-join.
- **Why:** It needs no arbitrary weighting of dollars vs. minutes. Anything off the frontier is beaten by something else with no trade-off.
- **Alternatives considered:** A combined score (e.g. rent + $X per minute). Rejected because it requires a value-of-time assumption students don't share.
- **Impact / risk:** The frontier is small (about 10 NTAs per campus). Near-frontier options can be almost as good; the scatter plot in Tableau shows them.

## D-022: Swaps never recommend a neighborhood with proxy rent
- **Phase:** 5
- **Decision:** Alternatives in `swaps` must have mapping confidence above "low", i.e. no rents borrowed from a neighbor.
- **Why:** The first run's best alternatives were mostly proxy NTAs (Mount Hope, Fordham Heights), which inherit rent from an adjacent area. We shouldn't tell anyone to move somewhere based on a borrowed number.

## D-023: "Popular" = most rental listings (a proxy, until the survey)
- **Phase:** 5
- **Decision:** Popular = the top 15 NTAs by estimated rental listings per year. A StreetEasy neighborhood's listings are split evenly across its NTAs so Astoria isn't counted 4 times.
- **Why:** It's the only public demand signal we have.
- **Impact / risk:** Listings mainly track **big new rental buildings**, so the list skews toward luxury Manhattan and Downtown Brooklyn (Hell's Kitchen is #1). It measures where renters look in general, not where students live. Phase 7 survey data could replace it.

## D-024: Headline rule (and an honest note on how it was chosen)
- **Phase:** 5
- **Decision:** The headline is the biggest monthly saving vs. a popular NTA where: the alternative has **high**-reliability rent; both commutes are within 45 min; and the popular NTA is "typical", at or below the **median rent of the 15 popular NTAs**.
- **How it was chosen:** This rule was set *after* seeing results, which carries a "garden of forking paths" risk, so both rejected attempts are recorded here:
  1. *No rent filter* gave "save $1,862 by living in Chinatown instead of Chelsea-Hudson Yards". True, but comparing to luxury new construction isn't a useful insight.
  2. *Exclude the top 25% of all NTAs by rent* set the cutoff at only $2,012/person, because most NTAs are in the cheaper outer boroughs. That excluded nearly every popular area and left no headline.
  3. *Median of the popular list* (final) compares against a typical popular area, defined from the popular list itself.
- **Impact / risk:** With NYU as home campus the headline is modest (East Village → Chinatown-Two Bridges, $548/month, same commute). Other campuses show larger effects, e.g. Columbia: Upper East Side → University Heights saves $1,734/month with a commute 1 min *shorter*. All campuses are listed in `docs/INSIGHTS.md`.

## D-025: Tableau export format
- **Phase:** 6
- **Decision:** One long main table (campus × NTA × housing type) plus a separate boundaries GeoJSON joined on `nta2020` with a Tableau *relationship*. Yes/no flags are written as TRUE / FALSE / **blank**, where blank = unknown. Readable labels ("2BR (2 roommates)"). Boundaries simplified by about 15 ft.
- **Why:** Long format lets Tableau filters choose the campus and housing type, with nothing hard-coded. Keeping geometry separate avoids repeating 181 polygons 15,000 times. Blank ≠ FALSE keeps "we don't know" distinct from "no".
- **Impact / risk:** Files total about 5 MB, comfortably inside Tableau Public limits.

## D-026: Survey privacy and design
- **Phase:** 7
- **Decision:** The survey collects no names, emails or addresses; neighborhood is the finest location. Raw responses live only in `data/raw/survey/` and `data/interim/` (both git-ignored). Anything published (`data/processed/`, `docs/`) is aggregated, and **groups with fewer than 5 responses are suppressed**. Questions map one-to-one onto public-data columns (`docs/SURVEY_QUESTIONS.md`), and the neighborhood question uses StreetEasy's exact names as a dropdown.
- **Why:** Small groups can identify people ("the one 3BR respondent in Inwood"). Free-text neighborhoods would be unmatchable.
- **Testing:** The comparison script was tested only on randomly generated fake responses kept outside the project (scratchpad). It caught a bug where the two medians were computed over different rows. No real survey data exists yet.

## D-027: Analyse 17 campuses, not one
- **Phase:** 4
- **Decision:** Commutes are computed to 17 major NYC campuses listed in `data/reference/campuses.csv`, with coordinates from NYC GeoSearch. One campus is marked `is_home_campus` for the headline.
- **Why:** The project owner's campus wasn't specified yet. A campus filter also makes the dashboard useful to any NYC student. Adding a campus is one CSV row.
- **Impact / risk:** **The home campus is currently set to NYU as a placeholder.** Change it to the real campus and re-run `python src/run_all.py --skip-download`.
