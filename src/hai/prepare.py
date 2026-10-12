"""Validate, repair, reproject and normalise boundaries and facilities."""
import json

import geopandas as gpd
import pandas as pd
import shapely

from . import lineage
from .config import path, settings

POLYGONAL = ("Polygon", "MultiPolygon")


def fix_geometries(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    """make_valid every invalid geometry, keep only its polygonal parts, drop empties."""
    gdf = gdf.copy()
    invalid = ~gdf.geometry.is_valid
    report = {"features": len(gdf), "invalid_before": int(invalid.sum())}
    gdf.loc[invalid, "geometry"] = shapely.make_valid(gdf.loc[invalid, "geometry"].values)

    def polygonal_part(g):
        if g is None or g.geom_type in POLYGONAL:
            return g
        parts = [p for p in getattr(g, "geoms", []) if p.geom_type in POLYGONAL]
        return shapely.union_all(parts) if parts else None

    gdf["geometry"] = gdf.geometry.apply(polygonal_part)
    empty = gdf.geometry.isna() | gdf.geometry.is_empty
    report["dropped_empty"] = int(empty.sum())
    gdf = gdf[~empty]
    report["invalid_after"] = int((~gdf.geometry.is_valid).sum())
    return gdf, report


def classify(tags: dict) -> str | None:
    amenity, hc = tags.get("amenity"), tags.get("healthcare")
    if "hospital" in (amenity, hc):
        return "hospital"
    if "pharmacy" in (amenity, hc):
        return "pharmacy"
    if amenity in ("clinic", "doctors") or hc in ("clinic", "doctor", "centre"):
        return "primary"
    return None


def osm_to_points(elements: list) -> gpd.GeoDataFrame:
    rows = []
    for e in elements:
        lon, lat = (e["lon"], e["lat"]) if e["type"] == "node" else (e["center"]["lon"], e["center"]["lat"])
        tags = e.get("tags", {})
        rows.append({
            "osm_id": f"{e['type'][0]}{e['id']}",
            "name": tags.get("name"),
            "category": classify(tags),
            "amenity": tags.get("amenity"),
            "healthcare": tags.get("healthcare"),
            "geometry": shapely.Point(lon, lat),
        })
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    return gdf[gdf["category"].notna()].reset_index(drop=True)


def dedupe(fac: gpd.GeoDataFrame, distance_m: float) -> gpd.GeoDataFrame:
    """Collapse points of the same category within distance_m whose names match or are missing.

    OSM often maps one hospital as both a node and a building polygon.
    Expects a projected CRS (metres).
    """
    pairs = gpd.sjoin(fac, fac, predicate="dwithin", distance=distance_m)
    pairs = pairs[pairs.index < pairs["index_right"]]
    pairs = pairs[pairs["category_left"] == pairs["category_right"]]
    nl, nr = pairs["name_left"].str.lower(), pairs["name_right"].str.lower()
    pairs = pairs[nl.isna() | nr.isna() | (nl == nr)]
    return fac.drop(index=pairs["index_right"].unique())


def boundaries():
    crs = settings()["crs"]["analysis"]
    adm1 = gpd.read_file(path("raw", "rou_adm1.geojson"))
    adm2 = gpd.read_file(path("raw", "rou_adm2.geojson"))
    reports = {}
    adm1, reports["adm1"] = fix_geometries(adm1)
    adm2, reports["adm2"] = fix_geometries(adm2)
    adm1, adm2 = adm1.to_crs(crs), adm2.to_crs(crs)

    counties = adm1[["shapeID", "shapeName", "geometry"]].rename(
        columns={"shapeID": "county_id", "shapeName": "county"})
    uat = adm2[["shapeID", "shapeName", "geometry"]].rename(columns={"shapeID": "lau_id", "shapeName": "name"})
    # attach the county through a point guaranteed to lie inside each UAT
    pts = uat.set_geometry(uat.geometry.representative_point())
    pts = gpd.sjoin(pts, counties, predicate="within", how="left")
    uat = uat.merge(pts[["lau_id", "county_id", "county"]], on="lau_id", how="left")
    # geoBoundaries stores exclaves as separate features with the same name; one UAT = one feature
    n_parts = len(uat)
    uat = uat.dissolve(by=["county_id", "name"], aggfunc={"lau_id": "first", "county": "first"}, as_index=False)
    reports["exclave_parts_merged"] = n_parts - len(uat)
    uat["area_km2"] = uat.geometry.area / 1e6
    reports["uat_without_county"] = int(uat["county_id"].isna().sum())
    reports["duplicate_lau_id"] = int(uat["lau_id"].duplicated().sum())

    out = path("interim", "boundaries.gpkg")
    counties.to_file(out, layer="counties", driver="GPKG")
    uat.to_file(out, layer="uat", driver="GPKG")
    print(json.dumps(reports, indent=2))
    lineage.record("prepare.boundaries", [path("raw", "rou_adm1.geojson"), path("raw", "rou_adm2.geojson")],
                   [out], crs=crs, qc=reports)


def facilities():
    cfg = settings()
    elements = json.loads(path("raw", "osm_health.json").read_text(encoding="utf-8"))["elements"]
    fac = osm_to_points(elements).to_crs(cfg["crs"]["analysis"])
    n_raw = len(fac)
    fac = dedupe(fac, cfg["facilities"]["dedupe_distance_m"])

    # keep only facilities inside Romania's UATs (Overpass areas can leak at borders)
    uat = gpd.read_file(path("interim", "boundaries.gpkg"), layer="uat")
    fac = gpd.sjoin(fac, uat[["lau_id", "geometry"]], predicate="within", how="inner").drop(columns="index_right")

    out = path("interim", "facilities.gpkg")
    fac.to_file(out, layer="facilities", driver="GPKG")
    counts = fac["category"].value_counts().to_dict()
    print(f"{n_raw} raw points -> {len(fac)} after dedupe and clip: {counts}")
    lineage.record("prepare.facilities", [path("raw", "osm_health.json")], [out],
                   raw_points=n_raw, kept=len(fac), by_category=counts,
                   dedupe_distance_m=cfg["facilities"]["dedupe_distance_m"])


def run():
    boundaries()
    facilities()
