-- ===============================
-- Set DATABASE and SCHEMA (if neccessary)
-- ===============================

USE DATABASE dbt_prod;
-- USE SCHEMA core;

-- ===============================
-- Set Reporting Periods for queries
-- ===============================

WITH reporting_period AS (
    SELECT
        '2025-09-01' AS reporting_start_date_day
        , '2025-10-05' AS  reporting_end_date_day)

-- ===============================
-- Pull Location Data for base query
-- ===============================

, location_data AS (
    SELECT
        loc.id AS location_id
        , loc.friendly_location_name AS mfc_name
        , loc.market_id as region_id
        , CASE  WHEN loc.market_id = '11' THEN 'Inner Capital'
                WHEN loc.market_id = '12' THEN 'Outer Capital'
                WHEN loc.market_id = '13' THEN 'Regional'
                ELSE 'Other' END AS mfc_region
        , loc.regional_manager_1 AS regional_manager
        , loc.site_lead_poc AS site_lead
        , loc.longitude AS mfc_long
        , loc.latitude AS mfc_lat

    FROM
        core.locations AS loc

    WHERE
        loc.country_code = 'GB'
        AND loc.friendly_location_name IS NOT NULL)

-- ===============================
-- Pull Order Data for base query
-- ===============================

, order_list AS (
    SELECT
        o.id AS order_id
        , o.id_obfuscated
        , o.created_at_local
        , o.location_id AS location_id
        , ld.mfc_name
        , o.order_vendor
        , o.order_completed

    FROM
        core.orders AS o
        LEFT JOIN location_data AS ld ON ld.location_id = o.location_id
        CROSS JOIN reporting_period AS rp

    WHERE
        DATE_TRUNC('DAY', o.ops_date)::DATE >= rp.reporting_start_date_day
        AND DATE_TRUNC('DAY', o.ops_date)::DATE <= rp.reporting_end_date_day
        AND o.country_code = 'GB'
        AND LOWER(o.order_vendor) != 'gopuff'
)

-- ===============================
-- Order Financials incl VAT
-- ===============================

, incl_vat_detail AS (
    SELECT
        eo.*

    FROM
        core.eu_orders as eo
        LEFT JOIN order_list AS ol ON ol.order_id = eo.id

    WHERE
        ol.order_id IS NOT NULL
)

-- ===============================
-- Pull Marketplace Order Data for base query
-- ===============================

, mp_order_details AS (
    SELECT
        bpo.id_obfuscated
        , ol.order_id
        , ol.order_completed
        , DATE_TRUNC('DAY', ol.ops_date)::DATE as ops_day
        , ol.mfc_name
        , ol.order_vendor
        , bpo.partner_customer_order_number

    FROM
        core.bse_partner_order AS bpo
        LEFT JOIN order_list AS ol ON ol.id_obfuscated = bpo.id_obfuscated

    WHERE
        ol.order_id IS NOT NULL
)

-- ===============================
-- Main Query
-- ===============================

SELECT 
    * 

FROM 
    mp_order_details AS mp
    LEFT JOIN incl_vat_detail AS ivd ON ivd.id = mp.order_id

WHERE
    LOWER(mp.order_vendor) = 'justeat'

ORDER BY
    mp.order_id