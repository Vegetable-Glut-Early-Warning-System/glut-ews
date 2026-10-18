-- Schema of the parent dataset (data/glut_ews.duckdb), applied to a brand-new database by scripts/build_db.py.
-- raw.* tables are created from data/raw/extracts and data/raw/sources exactly as published (no DDL here).
-- Change the schema by editing this file (reviewed in Git) and rebuilding; there are no migrations.

CREATE SCHEMA core;
CREATE SCHEMA outputs;
CREATE SCHEMA outputs_history;
CREATE SCHEMA views;

-- ---------------------------------------------------------------- reference (from data/reference/*.csv)
CREATE TABLE core.dim_crop (
    crop VARCHAR PRIMARY KEY, crop_group VARCHAR, harti_item_name VARCHAR);
CREATE TABLE core.dim_district (
    district VARCHAR PRIMARY KEY, province VARCHAR, climatic_zone VARCHAR,
    latitude DOUBLE, longitude DOUBLE, elevation_m INTEGER);
CREATE TABLE core.dim_economic_centre (
    economic_centre VARCHAR PRIMARY KEY, located_in_district VARCHAR, centre_type VARCHAR);
CREATE TABLE core.dim_season (
    season VARCHAR PRIMARY KEY, season_type VARCHAR, season_year INTEGER, season_start DATE, season_end DATE,
    planting_months VARCHAR, harvest_months VARCHAR, split VARCHAR);
CREATE TABLE core.dim_calendar (
    week_start_date DATE PRIMARY KEY, year INTEGER, week INTEGER, season VARCHAR, season_type VARCHAR,
    month INTEGER, is_harvest_week BOOLEAN, harvest_of_season VARCHAR);
CREATE TABLE core.dim_crop_district (
    crop VARCHAR, district VARCHAR, status VARCHAR NOT NULL, justification VARCHAR, source VARCHAR,
    PRIMARY KEY (crop, district));
CREATE TABLE core.bridge_district_centre (
    district VARCHAR, economic_centre VARCHAR, weight DOUBLE NOT NULL, PRIMARY KEY (district, economic_centre));
CREATE TABLE core.cost_season (
    season VARCHAR, crop VARCHAR, farmgate_rs_kg DOUBLE, unit_cost_rs_kg DOUBLE, PRIMARY KEY (season, crop));
CREATE TABLE core.macro_monthly (
    month VARCHAR PRIMARY KEY, ccpi_2021_100 DOUBLE);

-- ---------------------------------------------------------------- generated (scripts/build_db.py, seeded)
CREATE TABLE core.national_supply_season (
    season VARCHAR, crop VARCHAR, extent_ha DOUBLE, production_t DOUBLE, yield_t_ha DOUBLE, PRIMARY KEY (season, crop));
CREATE TABLE core.supply_season (
    season VARCHAR, district VARCHAR, crop VARCHAR, extent_ha DOUBLE NOT NULL, production_t DOUBLE NOT NULL,
    yield_t_ha DOUBLE NOT NULL, PRIMARY KEY (season, district, crop));
CREATE TABLE core.planting_target_season (
    season VARCHAR, district VARCHAR, crop VARCHAR, target_ha DOUBLE NOT NULL, PRIMARY KEY (season, district, crop));
CREATE TABLE core.market_prices_weekly (
    week_start_date DATE, economic_centre VARCHAR, crop VARCHAR, wholesale_price_rs_kg DOUBLE NOT NULL,
    retail_price_rs_kg DOUBLE NOT NULL, PRIMARY KEY (week_start_date, economic_centre, crop));
CREATE TABLE core.market_arrivals_weekly (
    week_start_date DATE, economic_centre VARCHAR, crop VARCHAR, arrivals_t DOUBLE NOT NULL, wastage_t DOUBLE NOT NULL,
    PRIMARY KEY (week_start_date, economic_centre, crop));
CREATE TABLE core.harvest_weekly_national (
    week_start_date DATE, crop VARCHAR, harvest_t DOUBLE, farm_transport_loss_t DOUBLE, PRIMARY KEY (week_start_date, crop));
CREATE TABLE core.weather_daily (
    date DATE, district VARCHAR, rainfall_mm DOUBLE, temp_mean_c DOUBLE, temp_max_c DOUBLE, et0_mm DOUBLE,
    PRIMARY KEY (date, district));
CREATE TABLE core.model_parameters (
    parameter VARCHAR, crop VARCHAR, value VARCHAR, low DOUBLE, high DOUBLE, source VARCHAR);
CREATE TABLE core.known_issues (
    issue_id VARCHAR PRIMARY KEY, "table" VARCHAR, issue VARCHAR, core_handling VARCHAR);

-- ---------------------------------------------------------------- module outputs (contracts: src/glut_ews/common/contracts.py)
CREATE TABLE outputs.c1_glut_season (
    season VARCHAR, economic_centre VARCHAR, crop VARCHAR, glut_weeks INTEGER, historical_glut_label VARCHAR,
    cobweb_index DOUBLE, weeks_observed INTEGER, source_version VARCHAR, PRIMARY KEY (season, economic_centre, crop));
CREATE TABLE outputs.c2_pressure_score (
    season VARCHAR, district VARCHAR, crop VARCHAR, supply_pressure_score DOUBLE, pressure_class VARCHAR,
    top_drivers VARCHAR, source_version VARCHAR, PRIMARY KEY (season, district, crop));
CREATE TABLE outputs.c3_training_label (
    season VARCHAR, district VARCHAR, crop VARCHAR, glut_risk_label VARCHAR, source_version VARCHAR,
    PRIMARY KEY (season, district, crop));
CREATE TABLE outputs.c3_risk_prediction (
    season VARCHAR, district VARCHAR, crop VARCHAR, predicted_risk_label VARCHAR, prob_low DOUBLE, prob_medium DOUBLE,
    prob_high DOUBLE, top_reasons VARCHAR, source_version VARCHAR, PRIMARY KEY (season, district, crop));
CREATE TABLE outputs.c4_advisory (
    plan_season VARCHAR, district VARCHAR, crop VARCHAR, recent_avg_extent_ha DOUBLE, recommended_ha DOUBLE,
    change_pct DOUBLE, action VARCHAR, suggested_alternatives VARCHAR, explanation VARCHAR, source_version VARCHAR,
    PRIMARY KEY (plan_season, district, crop));
