-- =============================================================================
-- Phase 5: affordability analysis
-- =============================================================================
-- Inputs (loaded by src/p5_analysis.py):
--   rent_by_nta      NTA x bedroom type: per-person rent + reliability     (Phase 3)
--   commute          campus x NTA: commute minutes + flags                 (Phase 4)
--   campuses         campus list                                           (reference)
--   crosswalk, rent_summary                                                (Phases 2-3)
--   budgets(budget), commute_limits(limit_min), params5(top_n, max_extra_min)
--
-- Outputs:
--   affordability     campus x NTA x housing type: everything needed to judge one option
--   nta_popularity    estimated yearly listings per NTA ("popular" proxy)
--   swaps             for each popular NTA, its best cheaper alternative
--   scenario_summary  campus x housing type x budget x limit: how many NTAs work
--
-- Definitions (DECISIONS.md D-021 to D-024):
--   * usable rent     = rent reliability high or medium (D-009)
--   * reachable       = commute <= limit AND not flagged needs_bus_or_rail.
--                       Flagged trips count as UNKNOWN, not as "too long" (D-020).
--   * best value      = Pareto-efficient: no other NTA is both cheaper and faster
--   * popular         = top N NTAs by estimated rental listings per year
--   * any (cheapest)  = the cheapest usable housing type in that NTA
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1. Every option: campus x NTA x housing type
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE options AS
SELECT
    c.campus_id,
    cp.campus_name,
    r.nta2020, r.ntaname, r.boroname, r.lat, r.lon,
    r.bedrooms,
    r.occupants,
    r.rent_per_person,
    r.rent_per_person_peak,
    r.rent_reliability,
    r.mapping_confidence,
    r.uses_proxy,
    r.rent_reliability IN ('high', 'medium')                  AS rent_usable,
    c.commute_min,
    c.n_transfers,
    c.lines,
    c.board_station,
    CASE WHEN c.needs_bus_or_rail THEN 'needs_bus_or_rail'
         ELSE c.mode END                                      AS commute_status,
    NOT c.needs_bus_or_rail                                   AS commute_known
FROM rent_by_nta AS r
JOIN commute     AS c  USING (nta2020)
JOIN campuses    AS cp USING (campus_id);


-- ---------------------------------------------------------------------------
-- 2. Add an "any (cheapest)" row per campus x NTA: the cheapest usable type
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE affordability AS
SELECT *, bedrooms AS cheapest_type FROM options
UNION ALL
SELECT * REPLACE ('any (cheapest)' AS bedrooms), bedrooms AS cheapest_type
FROM options
WHERE rent_usable
QUALIFY row_number() OVER (PARTITION BY campus_id, nta2020
                           ORDER BY rent_per_person, occupants) = 1;


-- ---------------------------------------------------------------------------
-- 3. Best value (Pareto frontier)
--    An option is "best value" if NO other option for the same campus and
--    housing type is at least as cheap AND at least as fast, and strictly
--    better on one of the two. Everything else is "dominated": there's a
--    choice that beats it without any trade-off.
-- ---------------------------------------------------------------------------
ALTER TABLE affordability ADD COLUMN is_best_value BOOLEAN DEFAULT FALSE;

UPDATE affordability AS a
SET is_best_value = TRUE
WHERE a.rent_usable AND a.commute_known
  AND NOT EXISTS (
        SELECT 1
        FROM affordability AS b
        WHERE b.campus_id = a.campus_id
          AND b.bedrooms  = a.bedrooms
          AND b.rent_usable AND b.commute_known
          AND b.rent_per_person <= a.rent_per_person
          AND b.commute_min     <= a.commute_min
          AND (b.rent_per_person < a.rent_per_person OR b.commute_min < a.commute_min)
  );


-- ---------------------------------------------------------------------------
-- 4. Popularity: estimated rental listings per year in each NTA
--    A StreetEasy neighborhood's listings are spread evenly over its NTAs,
--    so Astoria's listings aren't counted 4 times (D-023).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE nta_popularity AS
SELECT
    x.nta2020,
    any_value(x.ntaname)                          AS ntaname,
    round(sum(r.listing_months / x.se_n_ntas))    AS listings_per_year_est
FROM crosswalk    AS x
JOIN rent_summary AS r ON r.area_name = x.se_area_name
WHERE r.area_type = 'neighborhood'
GROUP BY x.nta2020;

ALTER TABLE nta_popularity ADD COLUMN popularity_rank INTEGER;
UPDATE nta_popularity AS p
SET popularity_rank = ranked.rk
FROM (SELECT nta2020, rank() OVER (ORDER BY listings_per_year_est DESC) AS rk
      FROM nta_popularity) AS ranked
WHERE p.nta2020 = ranked.nta2020;


-- ---------------------------------------------------------------------------
-- 5. Swaps: for each popular NTA, the cheapest alternative that adds at most
--    max_extra_min minutes of commute (it may even be faster!).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE swaps AS
WITH usable AS (
    SELECT * FROM affordability
    WHERE rent_usable AND commute_known AND bedrooms <> 'any (cheapest)'
),
popular AS (
    SELECT u.*
    FROM usable AS u
    JOIN nta_popularity AS p USING (nta2020)
    WHERE p.popularity_rank <= (SELECT top_n FROM params5)
)
SELECT
    p.campus_id,
    p.campus_name,
    p.bedrooms,
    p.ntaname                                   AS popular_nta,
    p.rent_per_person                           AS popular_rent,
    round(p.commute_min)                        AS popular_commute_min,
    a.ntaname                                   AS alternative_nta,
    a.boroname                                  AS alternative_borough,
    a.rent_per_person                           AS alternative_rent,
    round(a.commute_min)                        AS alternative_commute_min,
    p.rent_per_person - a.rent_per_person       AS monthly_savings,
    -- difference of the ROUNDED times, so "22 -> 23 min" always reads as +1
    round(a.commute_min) - round(p.commute_min) AS extra_minutes_one_way,
    a.rent_reliability                          AS alternative_rent_reliability,
    a.mapping_confidence                        AS alternative_mapping_confidence,
    a.lines                                     AS alternative_lines
FROM popular AS p
JOIN usable  AS a
  ON  a.campus_id = p.campus_id
  AND a.bedrooms  = p.bedrooms
  AND a.nta2020  <> p.nta2020
WHERE a.rent_per_person < p.rent_per_person
  AND a.commute_min - p.commute_min <= (SELECT max_extra_min FROM params5)
  -- Never recommend a place whose rent is borrowed from a neighbor (D-022)
  AND a.mapping_confidence <> 'low'
QUALIFY row_number() OVER (PARTITION BY p.campus_id, p.bedrooms, p.nta2020
                           ORDER BY p.rent_per_person - a.rent_per_person DESC) = 1;


-- ---------------------------------------------------------------------------
-- 6. Scenario summary: how many NTAs work for each budget x commute limit
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE scenario_summary AS
SELECT
    a.campus_id,
    a.campus_name,
    a.bedrooms,
    b.budget,
    l.limit_min,
    count(*) FILTER (WHERE a.rent_usable)                                    AS ntas_with_rent,
    count(*) FILTER (WHERE a.rent_usable AND a.rent_per_person <= b.budget)  AS ntas_affordable,
    count(*) FILTER (WHERE a.commute_known AND a.commute_min <= l.limit_min) AS ntas_reachable,
    count(*) FILTER (WHERE a.rent_usable AND a.rent_per_person <= b.budget
                       AND a.commute_known AND a.commute_min <= l.limit_min) AS ntas_affordable_and_reachable,
    string_agg(a.ntaname, '; ' ORDER BY a.rent_per_person)
        FILTER (WHERE a.rent_usable AND a.rent_per_person <= b.budget
                  AND a.commute_known AND a.commute_min <= l.limit_min)      AS which_ntas
FROM affordability AS a
CROSS JOIN budgets AS b
CROSS JOIN commute_limits AS l
GROUP BY a.campus_id, a.campus_name, a.bedrooms, b.budget, l.limit_min
ORDER BY a.campus_id, a.bedrooms, b.budget, l.limit_min;
