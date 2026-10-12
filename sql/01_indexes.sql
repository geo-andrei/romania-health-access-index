-- Spatial (GiST) and key indexes; without these every query below is a full scan.
CREATE INDEX IF NOT EXISTS uat_geom_gix          ON uat          USING GIST (geom);
CREATE INDEX IF NOT EXISTS counties_geom_gix     ON counties     USING GIST (geom);
CREATE INDEX IF NOT EXISTS facilities_geom_gix   ON facilities   USING GIST (geom);
CREATE INDEX IF NOT EXISTS access_index_geom_gix ON access_index USING GIST (geom);
CREATE INDEX IF NOT EXISTS facilities_cat_idx    ON facilities (category);
ALTER TABLE uat ADD PRIMARY KEY (lau_id);
ANALYZE;
