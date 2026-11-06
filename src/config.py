"""
Project-wide settings in one place.

Why a config file: every script reads the campus location, budgets, and
commute limits from here, so changing an assumption means editing ONE line
(and logging it in DECISIONS.md), not hunting through every script.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# ROOT is the project folder, found relative to this file so scripts work no
# matter which directory you run them from.
ROOT = Path(__file__).resolve().parent.parent

DATA_RAW = ROOT / "data" / "raw"              # untouched downloads, never edited
DATA_INTERIM = ROOT / "data" / "interim"      # cleaned / partly joined (CSV, Excel-friendly)
DATA_PROCESSED = ROOT / "data" / "processed"  # final Tableau-ready CSVs
SQL_DIR = ROOT / "sql"
DB_PATH = DATA_INTERIM / "rent_map.duckdb"    # rebuildable at any time from raw data

# ---------------------------------------------------------------------------
# Campuses
# ---------------------------------------------------------------------------
# The campus list lives in a CSV so it's easy to edit in Excel:
#   data/reference/campuses.csv
# To use YOUR campus: add a row (lat/lon from NYC GeoSearch or Google Maps)
# and set is_home_campus = TRUE on it (and FALSE on all others). The home
# campus is the one the headline insight in Phase 5 is written about.
CAMPUSES_FILE = ROOT / "data" / "reference" / "campuses.csv"

# ---------------------------------------------------------------------------
# Analysis parameters
# ---------------------------------------------------------------------------
# Monthly rent PER PERSON, in US dollars.
BUDGETS = [1000, 1500, 2000]

# Door-to-door commute limits in minutes. 45 is the headline number.
COMMUTE_LIMITS = [30, 45, 60]
DEFAULT_COMMUTE_LIMIT = 45

# How many people share each unit type. Per-person rent = unit rent / occupants.
# Assumption: one person per bedroom, no living-room conversions (DECISIONS D-006).
# StreetEasy's top category is "3+ bedrooms", so we split it 3 ways (D-007).
OCCUPANTS_PER_UNIT = {
    "studio": 1,
    "1br": 1,
    "2br": 2,
    "3br_plus": 3,
}

# ---------------------------------------------------------------------------
# Rent summary settings (Phase 2)
# ---------------------------------------------------------------------------
# We summarise the most recent N months of data instead of a single month,
# which smooths out month-to-month noise and seasonality (D-005).
RENT_WINDOW_MONTHS = 12

# "Peak season" = the months students actually sign leases (June to September).
PEAK_SEASON_MONTHS = [6, 7, 8, 9]

# ---------------------------------------------------------------------------
# Commute model settings (Phase 4, DECISIONS.md D-018 to D-020)
# ---------------------------------------------------------------------------
AM_PEAK = ("07:30", "09:30")   # weekday window used for train times and headways
WALK_M_PER_MIN = 80            # ~3 mph, a normal walking pace
WALK_DETOUR = 1.3              # streets aren't straight: walk distance ~ 1.3 x straight line
MAX_ACCESS_KM = 1.6            # consider stations up to ~1 mile (straight line) from home
MIN_ACCESS_STATIONS = 3        # ...but always at least the 3 nearest
DIRECT_WALK_MAX_KM = 4.0       # allow walking the whole way if campus is this close
STATION_ENTRY_MIN = 2          # street -> platform (stairs, turnstile)
STATION_EXIT_DEFAULT_MIN = 3   # platform -> street/other platform, if GTFS gives none
MAX_WAIT_MIN = 15              # cap on waiting time (half headway) for rare services
MAX_SUBWAY_WALK_MIN = 20       # more walking than this at either end = "needs bus or rail" flag

# ---------------------------------------------------------------------------
# Analysis settings (Phase 5, DECISIONS.md D-021 to D-024)
# ---------------------------------------------------------------------------
POPULAR_TOP_N = 15             # "popular" = the 15 NTAs with the most rental listings
MAX_EXTRA_MIN = 15             # a "swap" may add at most this many minutes each way
HEADLINE_BEDROOMS = "2br"      # housing type for the headline insight (2 roommates)

# ---------------------------------------------------------------------------
# Survey (Phase 7, DECISIONS.md D-026)
# ---------------------------------------------------------------------------
SURVEY_FILE = DATA_RAW / "survey" / "survey_responses.csv"   # git-ignored, never committed
SURVEY_MIN_GROUP = 5           # never publish a group with fewer responses (privacy)
