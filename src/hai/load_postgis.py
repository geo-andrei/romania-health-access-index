"""Load prepared layers into PostGIS and run the SQL in sql/ in order."""
import os

import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import create_engine

from . import lineage
from .config import ROOT, path


def engine():
    load_dotenv(ROOT / ".env")
    e = os.environ
    url = (f"postgresql+psycopg2://{e['POSTGRES_USER']}:{e['POSTGRES_PASSWORD']}"
           f"@{e.get('POSTGRES_HOST', 'localhost')}:{e.get('POSTGRES_PORT', '5432')}/{e['POSTGRES_DB']}")
    return create_engine(url)


def run():
    eng = engine()
    layers = {
        "uat": (path("interim", "boundaries.gpkg"), "uat"),
        "counties": (path("interim", "boundaries.gpkg"), "counties"),
        "facilities": (path("interim", "facilities.gpkg"), "facilities"),
        "access_index": (path("processed", "access_index.gpkg"), "access_index"),
    }
    for table, (src, layer) in layers.items():
        gdf = gpd.read_file(src, layer=layer).rename_geometry("geom")
        gdf.to_postgis(table, eng, if_exists="replace", index=False)
        print(f"loaded {table}: {len(gdf)} rows")

    scripts = sorted((ROOT / "sql").glob("*.sql"))
    with eng.begin() as conn:
        for sql in scripts:
            print(f"running {sql.name}")
            conn.exec_driver_sql(sql.read_text(encoding="utf-8"))
    lineage.record("load_postgis", [s for s, _ in layers.values()],
                   [f"postgis:{t}" for t in layers] + ["postgis:access_index_pub", "postgis:county_summary"],
                   sql=[s.name for s in scripts])
