# Data download instructions

## 1. StreetEasy (manual, Phase 2)

**Page:** https://streeteasy.com/blog/data-dashboard/ → *Download Data* section.

1. Set **Property type** = **Rentals**.
2. Set **Bedroom count** to each of these in turn: **Studio**, **One Bedroom**, **Two Bedrooms**, **Three+ Bedrooms**.
3. For each bedroom count, click two report tiles: **Median Asking Rent** and **Rental Inventory**.

That gives **8 zip files**. Save them, unchanged, into `data/raw/streeteasy/`:

| Bedroom count | Median Asking Rent | Rental Inventory |
|---|---|---|
| Studio | `medianAskingRent_Studio.zip` | `rentalInventory_Studio.zip` |
| One Bedroom | `medianAskingRent_OneBd.zip` | `rentalInventory_OneBd.zip` |
| Two Bedrooms | `medianAskingRent_TwoBd.zip` | `rentalInventory_TwoBd.zip` |
| Three+ Bedrooms | `medianAskingRent_ThreePlusBd.zip` | `rentalInventory_ThreePlusBd.zip` |

- You can leave them zipped (pandas reads a zipped CSV directly) or unzip them into the same folder. The script accepts either `.zip` or `.csv`.
- Don't rename or edit them. If you want to explore in Excel, unzip a **copy** somewhere else, or open the cleaned files in `data/interim/` instead.
- Write the download date in the table below. StreetEasy revises recent months, so the date matters for reproducibility.

**What's inside each file:** one row per area (176 neighborhoods + 5 boroughs + NYC), columns `areaName, Borough, areaType`, then one column per month from `2010-01` to the latest month. *Wide* format.

- **Median Asking Rent:** "the exact middle asking rent among all rental listings available on StreetEasy at any point during the month" (StreetEasy's definition). Blank when there weren't enough listings.
- **Rental Inventory:** number of rental listings that month. We use it to judge how reliable each median is.

**Not used:** *Rental Index* (a price index, not dollars) and *Share of Rent Cuts* (interesting, but not needed for this question).

| File set | Downloaded on | Latest month in data |
|---|---|---|
| StreetEasy rentals (8 files) | 2026-11-05 | 2026-10 |

## 2. MTA GTFS subway feed (Phase 4: scripted, nothing to do yet)
## 3. NTA boundaries (Phase 3: scripted, nothing to do yet)
## 4. Student survey (Phase 7: goes in `data/raw/survey/`, never committed)
