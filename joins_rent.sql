BEGIN;

------------------------------------------------------------
-- 1. LL44 unit -> building + bedroom level
--    use building_id_bbl as the building key
------------------------------------------------------------

DROP TABLE IF EXISTS ll44_unit_building_level;

CREATE TABLE ll44_unit_building_level AS
SELECT
    building_id_bbl                             AS building_id,       -- key is building_id_bbl
    bedroomsize                                 AS bedroom_size_raw,
    SUM(
        CASE
            WHEN totalunits ~ '[0-9]'
                THEN totalunits::numeric
            ELSE 0
        END
    ) AS ll44_total_units,
    AVG(
        CASE
            WHEN medianactualrent ~ '[0-9]'
                THEN medianactualrent::numeric
            ELSE NULL
        END
    ) AS ll44_median_actual_rent
FROM ll44_unit_income_rent_raw
WHERE building_id_bbl IS NOT NULL
GROUP BY building_id_bbl, bedroomsize;

-- normalize bedroom size to buckets so we can map to ACS columns
ALTER TABLE ll44_unit_building_level
    ADD COLUMN bedroom_bucket text;

UPDATE ll44_unit_building_level
SET bedroom_bucket = CASE
    WHEN bedroom_size_raw ILIKE 'STUDIO%' OR bedroom_size_raw ILIKE '0-BR%' THEN '0br'
    WHEN bedroom_size_raw ILIKE '1-BR%'                                         THEN '1br'
    WHEN bedroom_size_raw ILIKE '2-BR%'                                         THEN '2br'
    WHEN bedroom_size_raw ILIKE '3-BR%'                                         THEN '3br'
    WHEN bedroom_size_raw ILIKE '4-BR%'                                         THEN '4br'
    WHEN bedroom_size_raw ILIKE '5-BR%' OR bedroom_size_raw ILIKE '6-BR%'       THEN '5plus'
    ELSE 'all'
END;


------------------------------------------------------------
-- 2. Latest ACS 5-year rents (2023) + clean -666666666
--    !!! removed NAME column, only keep fields we really use !!!
------------------------------------------------------------

DROP VIEW IF EXISTS acs_rent_latest;

CREATE VIEW acs_rent_latest AS
SELECT
    year,
    tract_geoid,
    state,
    county,
    tract,
    NULLIF(median_rent_all,   -666666666) AS median_rent_all,
    NULLIF(median_rent_0br,   -666666666) AS median_rent_0br,
    NULLIF(median_rent_1br,   -666666666) AS median_rent_1br,
    NULLIF(median_rent_2br,   -666666666) AS median_rent_2br,
    NULLIF(median_rent_3br,   -666666666) AS median_rent_3br,
    NULLIF(median_rent_4br,   -666666666) AS median_rent_4br,
    NULLIF(median_rent_5plus, -666666666) AS median_rent_5plus
FROM acs_rent5_nyc
WHERE year = 2023;


------------------------------------------------------------
-- 3. Building-unit rent fact:
--    building_base + LL44 + mappluto(tract) + ACS fallback
------------------------------------------------------------

DROP TABLE IF EXISTS building_unit_rent_fact;

CREATE TABLE building_unit_rent_fact AS
WITH mp_with_tract AS (
    SELECT
        bbl::bigint                AS bbl_bigint,
        LPAD(ct2010::text, 6, '0') AS tract_code6,
        geom
    FROM mappluto
)
SELECT
    b.building_id,
    b.borough,
    b.address,
    b.zipcode,
    b.geom,
    mp.tract_code6                         AS tract_code6,
    u.bedroom_size_raw,
    u.bedroom_bucket,
    u.ll44_total_units,
    u.ll44_median_actual_rent,

    -- ACS median rent by bedroom (already cleaned in acs_rent_latest)
    CASE
        WHEN u.bedroom_bucket = '0br'   THEN a.median_rent_0br
        WHEN u.bedroom_bucket = '1br'   THEN a.median_rent_1br
        WHEN u.bedroom_bucket = '2br'   THEN a.median_rent_2br
        WHEN u.bedroom_bucket = '3br'   THEN a.median_rent_3br
        WHEN u.bedroom_bucket = '4br'   THEN a.median_rent_4br
        WHEN u.bedroom_bucket = '5plus' THEN a.median_rent_5plus
        ELSE a.median_rent_all
    END AS acs_median_rent,

    -- Effective rent: LL44 if available, otherwise ACS
    COALESCE(
        u.ll44_median_actual_rent,
        CASE
            WHEN u.bedroom_bucket = '0br'   THEN a.median_rent_0br
            WHEN u.bedroom_bucket = '1br'   THEN a.median_rent_1br
            WHEN u.bedroom_bucket = '2br'   THEN a.median_rent_2br
            WHEN u.bedroom_bucket = '3br'   THEN a.median_rent_3br
            WHEN u.bedroom_bucket = '4br'   THEN a.median_rent_4br
            WHEN u.bedroom_bucket = '5plus' THEN a.median_rent_5plus
            ELSE a.median_rent_all
        END
    ) AS effective_median_rent

FROM building_base b
LEFT JOIN ll44_unit_building_level u
    ON u.building_id = b.building_id        -- building_base.building_id is BBL
LEFT JOIN mp_with_tract mp
    ON mp.bbl_bigint = b.building_id        -- same BBL key to mappluto
LEFT JOIN acs_rent_latest a
    ON RIGHT(a.tract_geoid, 6) = mp.tract_code6;


------------------------------------------------------------
-- 4. Building-level map fact (for visualization)
------------------------------------------------------------

DROP MATERIALIZED VIEW IF EXISTS building_map_fact;

CREATE MATERIALIZED VIEW building_map_fact AS
SELECT
    f.building_id,
    f.borough,
    f.address,
    f.zipcode,
    f.geom,
    MIN(f.effective_median_rent) AS min_effective_median_rent,
    SUM(COALESCE(f.ll44_total_units, 0)) AS total_ll44_units,
    STRING_AGG(
        CONCAT(
            COALESCE(f.bedroom_size_raw, 'N/A'),
            ' | units: ',
            COALESCE(f.ll44_total_units::text, '0'),
            ' | rent: ',
            COALESCE(ROUND(f.effective_median_rent)::text, 'N/A')
        ),
        '; ' ORDER BY f.bedroom_size_raw
    ) AS bedroom_rent_summary
FROM building_unit_rent_fact f
GROUP BY
    f.building_id,
    f.borough,
    f.address,
    f.zipcode,
    f.geom;

CREATE INDEX IF NOT EXISTS building_map_fact_geom_gix
    ON building_map_fact USING GIST (geom);

COMMIT;