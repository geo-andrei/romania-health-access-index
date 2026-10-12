# Data lineage

Every step appends a machine-readable record (inputs, outputs, parameters, git commit, timestamp) to `lineage.jsonl`. This page is the human-readable view.

```mermaid
flowchart LR
  subgraph Sources
    GB[geoBoundaries<br/>ROU ADM1 + ADM2]
    OSM[OpenStreetMap<br/>Overpass API]
    WP[WorldPop 2020<br/>100 m raster]
  end
  subgraph Prepare["prepare.py (GeoPandas + Shapely)"]
    B[boundaries.gpkg<br/>make_valid, EPSG:3844,<br/>UAT to county join]
    F[facilities.gpkg<br/>classify, centroid,<br/>dedupe 150 m, clip]
  end
  subgraph Analyse["analyse.py"]
    A[access_index.gpkg<br/>population, distances,<br/>10 km coverage, HAI]
  end
  subgraph PostGIS["PostGIS (sql/)"]
    P1[uat_facility_counts<br/>uat_hospitals_10km]
    P2[uat_nearest_hospital<br/>KNN &lt;-&gt;]
    P3[access_index_pub<br/>county_summary<br/>EPSG:4326]
  end
  subgraph Publish
    G[publish.gpkg + GeoJSON]
    API[pygeoapi<br/>OGC API - Features<br/>Azure Container Apps]
  end
  GB --> B
  OSM --> F
  B --> F
  B --> A
  F --> A
  WP --> A
  A --> P1 & P2 --> P3
  P3 --> G --> API
```

| Step | Script | Input | Output | Key parameters |
|---|---|---|---|---|
| Download | `download.py` | geoBoundaries API, Overpass, WorldPop | `data/raw/*` | Overpass query stored in the log |
| Prepare boundaries | `prepare.py` | `rou_adm1/2.geojson` | `boundaries.gpkg` | CRS EPSG:3844; repair counts |
| Prepare facilities | `prepare.py` | `osm_health.json` | `facilities.gpkg` | categories, dedupe distance |
| Analyse | `analyse.py` | the two GeoPackages + raster | `access_index.gpkg` | weights, buffer, Spearman check |
| Load + SQL | `load_postgis.py`, `sql/*.sql` | GeoPackages | PostGIS tables | script order |
| Export | `export.py` | PostGIS publication tables | `publish.gpkg`, GeoJSON | |
| Serve | `Dockerfile`, `config/pygeoapi.*.yml` | `publish.gpkg` | OGC API endpoint | |
