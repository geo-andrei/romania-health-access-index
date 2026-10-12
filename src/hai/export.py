"""Export the PostGIS publication tables to GeoPackage (served on Azure) and GeoJSON (downloads)."""
import geopandas as gpd

from . import lineage
from .config import path
from .load_postgis import engine

TABLES = ("access_index_pub", "county_summary")


def run():
    eng = engine()
    gpkg = path("processed", "publish.gpkg")
    gpkg.unlink(missing_ok=True)  # GeoPackage (SQLite) never shrinks in place; start from a clean file
    outs = [gpkg]
    for table in TABLES:
        gdf = gpd.read_postgis(f"SELECT * FROM {table}", eng, geom_col="geom")
        layer = table.removesuffix("_pub")
        gdf.to_file(gpkg, layer=layer, driver="GPKG")
        geojson = path("processed", f"{layer}.geojson")
        gdf.to_file(geojson, driver="GeoJSON", COORDINATE_PRECISION=6)
        outs.append(geojson)
        print(f"exported {layer}: {len(gdf)} features")
    lineage.record("export", [f"postgis:{t}" for t in TABLES], outs)
