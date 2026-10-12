-- Publication tables for pygeoapi: simplified WGS84 geometry, primary key, joined SQL results.
-- Analysis used full-resolution geometry; simplification (metres, EPSG:3844) only lightens the API payload.
DROP TABLE IF EXISTS access_index_pub;
CREATE TABLE access_index_pub AS
SELECT a.lau_id, a.name, a.county, a.population, a.area_km2,
       a.dist_hosp_km, a.dist_primary_km, a.n_pharmacies, a.pharm_per_10k,
       a.share_area_hosp_buffer, a.hai, a.hai_quintile,
       n.hospital_name AS nearest_hospital,
       ST_Multi(ST_Transform(ST_SimplifyPreserveTopology(a.geom, 50), 4326))::geometry(MultiPolygon, 4326) AS geom
FROM access_index a
LEFT JOIN uat_nearest_hospital n USING (lau_id);
ALTER TABLE access_index_pub ADD PRIMARY KEY (lau_id);
CREATE INDEX access_index_pub_gix ON access_index_pub USING GIST (geom);

-- County roll-up: population-weighted mean index and dissolved geometry.
DROP TABLE IF EXISTS county_summary;
CREATE TABLE county_summary AS
SELECT coalesce(a.county, 'unknown') AS county,
       sum(a.population)::bigint AS population,
       round((sum(a.hai * a.population) / nullif(sum(a.population), 0))::numeric, 1) AS hai_pop_weighted,
       round(avg(a.dist_hosp_km)::numeric, 2) AS mean_dist_hosp_km,
       ST_Multi(ST_Transform(ST_SimplifyPreserveTopology(ST_Union(a.geom), 100), 4326))::geometry(MultiPolygon, 4326) AS geom
FROM access_index a
GROUP BY 1;
ALTER TABLE county_summary ADD PRIMARY KEY (county);
