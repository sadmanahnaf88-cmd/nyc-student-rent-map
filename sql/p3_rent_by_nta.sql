-- =============================================================================
-- Phase 3: give every NTA a rent, using the StreetEasy neighborhood(s) linked to it
-- =============================================================================
-- Inputs (loaded by src/p3c_rent_by_nta.py):
--   rent_summary   one row per SE neighborhood x bedroom type   (Phase 2)
--   crosswalk      one row per (SE neighborhood, NTA) pair      (Phase 3b)
--   nta_areas      one row per NTA, with centroid               (Phase 3b)
--
-- Output:
--   rent_by_nta    one row per residential NTA x bedroom type
--
-- Combining rules (DECISIONS.md D-016):
--   * One SE neighborhood -> NTA: the NTA simply takes that rent.
--   * Several SE neighborhoods -> one NTA: average their rents WEIGHTED BY
--     listing volume, so a neighborhood with 500 listings counts more than
--     one with 5. Sources with no data are skipped (they'd have weight 0 anyway).
--   * The NTA keeps the WORST mapping confidence among its sources, so a
--     shaky link is never hidden by a solid one.
-- =============================================================================

CREATE OR REPLACE TABLE rent_by_nta AS

WITH linked AS (
    -- The many-to-many join: every NTA x every linked SE neighborhood x bedroom type
    SELECT
        x.nta2020,
        x.se_area_name,
        x.match_type,
        x.confidence,
        r.bedrooms,
        r.occupants,
        r.rent_unit,
        r.rent_per_person,
        r.rent_per_person_peak,
        r.months_with_rent,
        r.listing_months,
        r.reliability
    FROM crosswalk AS x
    JOIN rent_summary AS r
      ON r.area_name = x.se_area_name
),

combined AS (
    SELECT
        nta2020,
        bedrooms,
        any_value(occupants)                                          AS occupants,

        -- Listing-weighted average across sources that have a rent.
        -- sum(rent * weight) / sum(weight), skipping rows without a rent.
        round(sum(rent_per_person * listing_months)
                FILTER (WHERE rent_per_person IS NOT NULL)
              / nullif(sum(listing_months)
                FILTER (WHERE rent_per_person IS NOT NULL), 0))       AS rent_per_person,
        round(sum(rent_per_person_peak * listing_months)
                FILTER (WHERE rent_per_person_peak IS NOT NULL)
              / nullif(sum(listing_months)
                FILTER (WHERE rent_per_person_peak IS NOT NULL), 0))  AS rent_per_person_peak,

        -- Range across sources: a blend can hide big differences
        -- (e.g. SoHo vs Little Italy inside one NTA), so keep them visible.
        min(rent_per_person)                                          AS rent_pp_lowest_source,
        max(rent_per_person)                                          AS rent_pp_highest_source,

        sum(listing_months)                                           AS listing_months,
        max(months_with_rent)                                         AS months_with_rent,
        count(*)                                                      AS n_sources,
        count(rent_per_person)                                        AS n_sources_with_rent,
        string_agg(se_area_name, '; ' ORDER BY listing_months DESC)   AS se_sources,

        -- Worst confidence wins (low < medium < high)
        CASE min(CASE confidence WHEN 'low' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END)
             WHEN 1 THEN 'low' WHEN 2 THEN 'medium' ELSE 'high'
        END                                                           AS mapping_confidence,
        bool_or(match_type = 'proxy')                                 AS uses_proxy
    FROM linked
    GROUP BY nta2020, bedrooms
)

SELECT
    a.nta2020,
    a.ntaname,
    a.boroname,
    a.lat,
    a.lon,
    c.bedrooms,
    c.occupants,
    c.rent_per_person,
    c.rent_per_person_peak,
    c.rent_pp_lowest_source,
    c.rent_pp_highest_source,
    -- Same reliability thresholds as Phase 2 (D-009), applied to the combined volume
    CASE
        WHEN c.n_sources_with_rent = 0                                  THEN 'no_data'
        WHEN c.listing_months >= 60 AND c.months_with_rent >= 10        THEN 'high'
        WHEN c.listing_months >= 24 AND c.months_with_rent >= 6         THEN 'medium'
        ELSE                                                                 'low'
    END                                                               AS rent_reliability,
    c.mapping_confidence,
    c.uses_proxy,
    c.n_sources,
    c.se_sources,
    c.listing_months
FROM combined AS c
JOIN nta_areas AS a USING (nta2020)
ORDER BY a.boroname, a.ntaname, c.occupants, c.bedrooms;
