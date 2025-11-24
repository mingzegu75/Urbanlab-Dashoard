-- 0. optional: enable PostGIS if not already
CREATE EXTENSION IF NOT EXISTS postgis;



-- 1. building_base from mappluto (BBL is the building_id)
DROP TABLE IF EXISTS building_base;

CREATE TABLE building_base AS
SELECT
    bbl::bigint AS building_id,
    borough,
    address,
    zipcode,
    geom
FROM mappluto;

ALTER TABLE building_base
    ADD CONSTRAINT building_base_pk PRIMARY KEY (building_id);



-- 2. HPD building: clean bbl -> building_id_bbl
-- column names in your table: project_id, building_id, bbl, latitude, longitude, ...

ALTER TABLE hpd_affordable_building_raw
    DROP COLUMN IF EXISTS building_id_bbl;

ALTER TABLE hpd_affordable_building_raw
    ADD COLUMN building_id_bbl bigint;

UPDATE hpd_affordable_building_raw
SET building_id_bbl = regexp_replace(bbl, '\.0$', '')::bigint
WHERE bbl IS NOT NULL
  AND bbl ~ '^[0-9]+(\.0)?$';



-- 3. LL44 tables: add building_id_bbl column (will fill from HPD mapping)
-- your columns: projectid, buildingid, affordabilityband, totalunits, ...

ALTER TABLE ll44_rent_affordability_raw
    DROP COLUMN IF EXISTS building_id_bbl;

ALTER TABLE ll44_rent_affordability_raw
    ADD COLUMN building_id_bbl bigint;

ALTER TABLE ll44_unit_income_rent_raw
    DROP COLUMN IF EXISTS building_id_bbl;

ALTER TABLE ll44_unit_income_rent_raw
    ADD COLUMN building_id_bbl bigint;



-- 4. Build mapping table: HPD building_id -> BBL
DROP TABLE IF EXISTS hpd_buildingid_to_bbl;

CREATE TABLE hpd_buildingid_to_bbl AS
SELECT DISTINCT
    regexp_replace(building_id, '\.0$', '')::bigint AS hpd_building_id,
    building_id_bbl                                  AS building_id_bbl
FROM hpd_affordable_building_raw
WHERE building_id IS NOT NULL
  AND building_id_bbl IS NOT NULL
  AND building_id ~ '^[0-9]+(\.0)?$';

ALTER TABLE hpd_buildingid_to_bbl
    ADD CONSTRAINT hpd_buildingid_to_bbl_pk PRIMARY KEY (hpd_building_id);



-- 5. Fill building_id_bbl in LL44 tables using the mapping
UPDATE ll44_rent_affordability_raw ra
SET building_id_bbl = m.building_id_bbl
FROM hpd_buildingid_to_bbl m
WHERE ra.buildingid IS NOT NULL
  AND ra.buildingid ~ '^[0-9]+(\.0)?$'
  AND regexp_replace(ra.buildingid, '\.0$', '')::bigint = m.hpd_building_id;

UPDATE ll44_unit_income_rent_raw ur
SET building_id_bbl = m.building_id_bbl
FROM hpd_buildingid_to_bbl m
WHERE ur.buildingid IS NOT NULL
  AND ur.buildingid ~ '^[0-9]+(\.0)?$'
  AND regexp_replace(ur.buildingid, '\.0$', '')::bigint = m.hpd_building_id;



-- 6. Create building_fact as a materialized view joined by building_id / BBL
--    You can add/remove columns here based on what you want in the dashboard.

-- 6. Create building_fact as a materialized view joined by building_id / BBL
DROP MATERIALIZED VIEW IF EXISTS building_fact;

CREATE MATERIALIZED VIEW building_fact AS
SELECT
    b.building_id,
    b.borough,
    b.address,
    b.zipcode,
    b.geom,

    -- HPD building basic info
    MIN(h.project_id)                     AS any_project_id,
    MIN(h.project_name)                  AS any_project_name,
    MIN(h.extended_affordability_status) AS extended_affordability_status,

    -- HPD units by income level (text -> numeric safely)
    SUM(
        CASE
            WHEN h.extremely_low_income_units ~ '^[0-9]+(\.[0-9]+)?$'
            THEN h.extremely_low_income_units::numeric
            ELSE 0
        END
    ) AS hpd_extremely_low_units,

    SUM(
        CASE
            WHEN h.very_low_income_units ~ '^[0-9]+(\.[0-9]+)?$'
            THEN h.very_low_income_units::numeric
            ELSE 0
        END
    ) AS hpd_very_low_units,

    SUM(
        CASE
            WHEN h.low_income_units ~ '^[0-9]+(\.[0-9]+)?$'
            THEN h.low_income_units::numeric
            ELSE 0
        END
    ) AS hpd_low_income_units,

    SUM(
        CASE
            WHEN h.moderate_income_units ~ '^[0-9]+(\.[0-9]+)?$'
            THEN h.moderate_income_units::numeric
            ELSE 0
        END
    ) AS hpd_moderate_income_units,

    SUM(
        CASE
            WHEN h.middle_income_units ~ '^[0-9]+(\.[0-9]+)?$'
            THEN h.middle_income_units::numeric
            ELSE 0
        END
    ) AS hpd_middle_income_units,

    SUM(
        CASE
            WHEN h.total_units ~ '^[0-9]+(\.[0-9]+)?$'
            THEN h.total_units::numeric
            ELSE 0
        END
    ) AS hpd_total_units,

    -- LL44 rent affordability (by building)
    MAX(ra.affordabilityband) AS any_affordability_band,

    SUM(
        CASE
            WHEN ra.totalunits ~ '^[0-9]+(\.[0-9]+)?$'
            THEN ra.totalunits::numeric
            ELSE 0
        END
    ) AS ll44_total_affordable_units,

    -- LL44 unit income / rent (aggregate to building level)
    MAX(
        CASE
            WHEN ur.maxallowableincome ~ '^[0-9]+(\.[0-9]+)?$'
            THEN ur.maxallowableincome::numeric
            ELSE NULL
        END
    ) AS max_allowable_income,

    AVG(
        CASE
            WHEN ur.medianactualrent ~ '^[0-9]+(\.[0-9]+)?$'
            THEN ur.medianactualrent::numeric
            ELSE NULL
        END
    ) AS avg_median_actual_rent

FROM building_base b
LEFT JOIN hpd_affordable_building_raw h
    ON h.building_id_bbl = b.building_id
LEFT JOIN ll44_rent_affordability_raw ra
    ON ra.building_id_bbl = b.building_id
LEFT JOIN ll44_unit_income_rent_raw ur
    ON ur.building_id_bbl = b.building_id
GROUP BY
    b.building_id,
    b.borough,
    b.address,
    b.zipcode,
    b.geom;

-- optional spatial index if PostGIS is enabled
CREATE INDEX IF NOT EXISTS building_fact_geom_gix
    ON building_fact USING GIST (geom);
