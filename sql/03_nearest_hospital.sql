-- K-nearest-neighbour with the <-> operator: the closest hospital to each UAT, by name.
-- Cross-checks the GeoPandas sjoin_nearest result (dist_km should match dist_hosp_km).
DROP TABLE IF EXISTS uat_nearest_hospital;
CREATE TABLE uat_nearest_hospital AS
SELECT u.lau_id,
       h.osm_id   AS hospital_osm_id,
       h.name     AS hospital_name,
       round((ST_Distance(ST_PointOnSurface(u.geom), h.geom) / 1000)::numeric, 2) AS dist_km
FROM uat u
CROSS JOIN LATERAL (
    SELECT f.osm_id, f.name, f.geom
    FROM facilities f
    WHERE f.category = 'hospital'
    ORDER BY f.geom <-> ST_PointOnSurface(u.geom)
    LIMIT 1
) h;
