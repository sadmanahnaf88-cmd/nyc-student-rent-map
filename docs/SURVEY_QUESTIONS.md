# Student housing survey: questions

Designed so every answer lines up with a column in the public data, which makes the comparison in Phase 7 possible. Build it in Google Forms / Microsoft Forms / Qualtrics, export as CSV, rename the columns to match `data/reference/survey_template.csv`, and save it as `data/raw/survey/survey_responses.csv` (git-ignored, never committed).

**Privacy rules:** don't collect names, emails, student IDs or exact addresses. The neighborhood is the most precise location we ask for. Published results only show groups with at least 5 responses (`SURVEY_MIN_GROUP` in `config.py`). If your school requires IRB/ethics approval for surveys, get it first.

| # | Question | Answer type | Column | Compared with |
|---|---|---|---|---|
| 0 | I agree to take part. My answers are anonymous and only shown in groups of 5+. | Yes (required) | `consent` | — |
| 1 | Which campus do you attend most days? | Dropdown: campus names from `data/reference/campuses.csv` (+ "Other") | `campus_id` | Commute model destination |
| 2 | Which borough do you live in? | Dropdown: Manhattan / Brooklyn / Queens / Bronx / Staten Island / Outside NYC | `borough` | — |
| 3 | Which neighborhood do you live in? | Dropdown **per borough**: names from `data/reference/survey_neighborhood_options.csv` | `neighborhood` | StreetEasy neighborhood (rent) and its NTAs (commute) |
| 4 | How many bedrooms does your apartment have? | Studio / 1 / 2 / 3 / 4+ | `bedrooms` (`studio`, `1br`, `2br`, `3br_plus`) | StreetEasy bedroom type |
| 5 | How many people (including you) live in the apartment? | Number | `people_in_unit` | Tests the one-person-per-bedroom assumption (D-006) |
| 6 | How much do **you** pay in rent each month (your share only)? | Number ($) | `my_monthly_rent` | `rent_per_person` |
| 7 | Does that include utilities (electricity, gas, internet)? | Yes / No / Not sure | `utilities_included` | Context: StreetEasy is rent only |
| 8 | When did your current lease start? | Month + year (YYYY-MM) | `lease_start` | Older leases tend to be cheaper than today's asking rents |
| 9 | Is your apartment rent-stabilized? | Yes / No / Not sure | `rent_stabilized` | Explains gaps vs. asking rents (D-011) |
| 10 | On a typical weekday, how many minutes does it take you to get from your door to campus? | Number (minutes) | `commute_min_typical` | `commute_min` |
| 11 | How do you usually get there? | Subway / Bus / Subway + bus / LIRR or Metro-North / Walk / Bike / Car / Other | `commute_mode` | Checks the subway-only assumption (D-018) |
| 12 | Do you live with family (not paying market rent)? | Yes / No | `lives_with_family` | Excluded from rent comparison |

Add `response_id` (1, 2, 3…) when you export. Keep the form short: 12 questions takes about 2 minutes, which helps your response rate.
