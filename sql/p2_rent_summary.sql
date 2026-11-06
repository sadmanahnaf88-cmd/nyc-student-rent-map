-- =============================================================================
-- Phase 2: rent summary per area x bedroom type
-- =============================================================================
-- Inputs (created by src/p2b_rent_summary.py before this runs):
--   rent_long   one row per area x bedroom type x month (from p2a_load_rent.py)
--   occupants   bedroom type -> number of people sharing    (from config.py)
--   params      window_months, peak_months                  (from config.py)
--
-- Output:
--   rent_summary  one row per area x bedroom type
--
-- Method (see DECISIONS.md D-005 to D-009):
--   * Summarise the latest N months (default 12), not one month: smooths noise
--     and seasonality.
--   * Typical rent = MEDIAN of the monthly medians in that window. Using a
--     median, not an average, means one strange month (e.g. a month where the
--     "median" was a single apartment) can't drag the number around.
--   * listing_months = sum of monthly listing counts. A listing that stays up
--     for 2 months counts twice, so this measures data volume, not unique units.
--   * Missing rents stay missing (no_data). We never fill them with guesses.
-- =============================================================================

CREATE OR REPLACE TABLE rent_summary AS

WITH window_bounds AS (
    -- The window ends at the latest month in the data and goes back N-1 months.
    SELECT
        max(r.month)                                                AS window_end,
        CAST(max(r.month) - to_months(p.window_months - 1) AS DATE) AS window_start
    FROM rent_long AS r
    CROSS JOIN params AS p
    GROUP BY p.window_months
),

in_window AS (
    -- Keep only rows inside the window, and flag peak-season months.
    SELECT
        r.*,
        list_contains(p.peak_months, extract(month FROM r.month)) AS is_peak
    FROM rent_long AS r
    CROSS JOIN window_bounds AS w
    CROSS JOIN params AS p
    WHERE r.month BETWEEN w.window_start AND w.window_end
),

per_area AS (
    -- One row per area x bedroom type.
    -- median() ignores NULLs, so months without a published rent just drop out.
    SELECT
        area_name,
        borough,
        area_type,
        bedrooms,
        median(median_rent)                               AS rent_unit,
        median(CASE WHEN is_peak THEN median_rent END)    AS rent_unit_peak,
        min(median_rent)                                  AS rent_unit_min_month,
        max(median_rent)                                  AS rent_unit_max_month,
        count(median_rent)                                AS months_with_rent,
        coalesce(sum(listings), 0)                        AS listing_months
    FROM in_window
    GROUP BY area_name, borough, area_type, bedrooms
)

SELECT
    pa.area_name,
    pa.borough,
    pa.area_type,
    pa.bedrooms,
    o.occupants,

    -- Whole-unit rent (what the listing says)
    round(pa.rent_unit)                        AS rent_unit,
    round(pa.rent_unit_peak)                   AS rent_unit_peak,

    -- Per-person rent = unit rent / people sharing (equal split assumed, D-006)
    round(pa.rent_unit      / o.occupants)     AS rent_per_person,
    round(pa.rent_unit_peak / o.occupants)     AS rent_per_person_peak,

    -- Spread within the window: a quick way to spot unstable numbers
    round(pa.rent_unit_min_month)              AS rent_unit_min_month,
    round(pa.rent_unit_max_month)              AS rent_unit_max_month,

    -- Reliability inputs
    pa.months_with_rent,
    pa.listing_months,

    -- Reliability tier (thresholds explained in D-009)
    CASE
        WHEN pa.months_with_rent = 0                                   THEN 'no_data'
        WHEN pa.listing_months >= 60 AND pa.months_with_rent >= 10     THEN 'high'
        WHEN pa.listing_months >= 24 AND pa.months_with_rent >= 6      THEN 'medium'
        ELSE                                                                'low'
    END                                         AS reliability,

    w.window_start,
    w.window_end

FROM per_area AS pa
JOIN occupants AS o USING (bedrooms)
CROSS JOIN window_bounds AS w
ORDER BY pa.area_type, pa.borough, pa.area_name, o.occupants, pa.bedrooms;
