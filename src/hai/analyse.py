"""Population per UAT, proximity indicators and the composite accessibility index."""
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from . import lineage
from .config import path, settings


def population_per_uat(uat: gpd.GeoDataFrame, raster_path) -> pd.Series:
    """Sum WorldPop people-per-pixel inside each UAT (zonal statistics in the raster's CRS)."""
    import rasterio
    from rasterstats import zonal_stats

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
    stats = zonal_stats(uat.to_crs(raster_crs), str(raster_path), stats=["sum"], nodata=-99999)
    return pd.Series([s["sum"] or 0.0 for s in stats], index=uat.index).round()


def nearest_km(origins: gpd.GeoDataFrame, targets: gpd.GeoDataFrame) -> pd.Series:
    """Euclidean distance (km) from each origin point to the nearest target."""
    joined = gpd.sjoin_nearest(origins[["geometry"]], targets[["geometry"]], distance_col="d")
    return joined.groupby(level=0)["d"].first() / 1000


def coverage_share(uat: gpd.GeoDataFrame, points: gpd.GeoDataFrame, buffer_m: float) -> pd.Series:
    """Share of each UAT's area within buffer_m of any point."""
    covered = shapely.union_all(points.geometry.buffer(buffer_m).values)
    return pd.Series(uat.geometry.intersection(covered).area / uat.geometry.area, index=uat.index)


def minmax(s: pd.Series, invert: bool = False) -> pd.Series:
    span = s.max() - s.min()
    scaled = (s - s.min()) / span if span else pd.Series(0.5, index=s.index)
    return 1 - scaled if invert else scaled


def composite_index(ind: pd.DataFrame, weights: dict) -> pd.Series:
    """Weighted mean of min-max scaled indicators, 0-100, higher = better access."""
    assert abs(sum(weights.values()) - 1) < 1e-9, "weights must sum to 1"
    scaled = pd.DataFrame({
        "hospital": minmax(ind["dist_hosp_km"], invert=True),
        "primary": minmax(ind["dist_primary_km"], invert=True),
        "pharmacy": minmax(ind["pharm_per_10k"]),
        "coverage": minmax(ind["share_area_hosp_buffer"]),
    })
    return (sum(scaled[k] * w for k, w in weights.items()) * 100).round(1)


def run():
    cfg = settings()
    a = cfg["analysis"]
    uat = gpd.read_file(path("interim", "boundaries.gpkg"), layer="uat")
    fac = gpd.read_file(path("interim", "facilities.gpkg"), layer="facilities")
    hosp, prim, pharm = (fac[fac["category"] == c] for c in ("hospital", "primary", "pharmacy"))

    uat["population"] = population_per_uat(uat, path("raw", "worldpop_rou_2020.tif"))

    # origin = a point guaranteed inside the UAT; population-weighted centres are a listed improvement
    origins = uat.set_geometry(uat.geometry.representative_point())
    uat["dist_hosp_km"] = nearest_km(origins, hosp).round(2)
    uat["dist_primary_km"] = nearest_km(origins, prim).round(2)

    n_pharm = gpd.sjoin(pharm, uat[["lau_id", "geometry"]].rename(columns={"lau_id": "uat_id"}),
                        predicate="within").groupby("uat_id").size()
    uat["n_pharmacies"] = uat["lau_id"].map(n_pharm).fillna(0).astype(int)
    uat["pharm_per_10k"] = np.where(uat["population"] > 0,
                                    uat["n_pharmacies"] / uat["population"] * 1e4, 0).round(2)
    uat["share_area_hosp_buffer"] = coverage_share(uat, hosp, a["hospital_buffer_m"]).round(3)

    uat["hai"] = composite_index(uat, a["weights"])
    uat["hai_quintile"] = pd.qcut(uat["hai"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)

    # sensitivity: does the ranking survive equal weights?
    equal = composite_index(uat, {k: 0.25 for k in a["weights"]})
    rho = uat["hai"].rank().corr(equal.rank())
    print(f"Spearman rank correlation, chosen vs equal weights: {rho:.3f}")

    out = path("processed", "access_index.gpkg")
    uat.to_file(out, layer="access_index", driver="GPKG")
    lineage.record("analyse", [path("interim", "boundaries.gpkg"), path("interim", "facilities.gpkg"),
                               path("raw", "worldpop_rou_2020.tif")], [out],
                   weights=a["weights"], hospital_buffer_m=a["hospital_buffer_m"],
                   spearman_vs_equal_weights=round(float(rho), 3))
