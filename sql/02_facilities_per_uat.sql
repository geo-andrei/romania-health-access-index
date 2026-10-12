-- Point-in-polygon aggregation: facility counts by category per UAT.
DROP TABLE IF EXISTS uat_facility_counts;
CREATE TABLE uat_facility_counts AS
SELECT u.lau_id,
       count(f.*) FILTER (WHERE f.category = 'hospital') AS n_hospitals,
       count(f.*) FILTER (WHERE f.category = 'primary')  AS n_primary,
       count(f.*) FILTER (WHERE f.category = 'pharmacy') AS n_pharmacies
FROM uat u
LEFT JOIN facilities f ON ST_Intersects(u.geom, f.geom)
GROUP BY u.lau_id;

-- Facilities within 10 km of each UAT's interior point (ST_DWithin uses the GiST index).
DROP TABLE IF EXISTS uat_hospitals_10km;
CREATE TABLE uat_hospitals_10km AS
SELECT u.lau_id, count(f.*) AS hospitals_within_10km
FROM uat u
LEFT JOIN facilities f
  ON f.category = 'hospital'
 AND ST_DWithin(ST_PointOnSurface(u.geom), f.geom, 10000)
GROUP BY u.lau_id;
