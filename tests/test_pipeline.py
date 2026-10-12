import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

from hai.analyse import composite_index, coverage_share, minmax, nearest_km
from hai.prepare import classify, dedupe, fix_geometries, osm_to_points

CRS = "EPSG:3844"


def test_fix_geometries_repairs_bowtie():
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    square = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    gdf = gpd.GeoDataFrame({"id": [1, 2]}, geometry=[bowtie, square], crs=CRS)
    fixed, report = fix_geometries(gdf)
    assert report["invalid_before"] == 1
    assert report["invalid_after"] == 0
    assert fixed.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all()
    assert fixed.geometry.area.iloc[0] == pytest.approx(2.0)


@pytest.mark.parametrize("tags,expected", [
    ({"amenity": "hospital"}, "hospital"),
    ({"healthcare": "hospital", "amenity": "clinic"}, "hospital"),
    ({"amenity": "pharmacy"}, "pharmacy"),
    ({"amenity": "doctors"}, "primary"),
    ({"healthcare": "centre"}, "primary"),
    ({"healthcare": "dentist"}, None),
])
def test_classify(tags, expected):
    assert classify(tags) == expected


def test_osm_to_points_uses_center_for_ways():
    elements = [
        {"type": "node", "id": 1, "lat": 45.75, "lon": 21.23, "tags": {"amenity": "pharmacy"}},
        {"type": "way", "id": 2, "center": {"lat": 45.76, "lon": 21.22}, "tags": {"amenity": "hospital"}},
        {"type": "node", "id": 3, "lat": 45.0, "lon": 21.0, "tags": {"healthcare": "dentist"}},
    ]
    gdf = osm_to_points(elements)
    assert list(gdf["osm_id"]) == ["n1", "w2"]


def test_dedupe_merges_node_and_polygon_of_same_hospital_only():
    fac = gpd.GeoDataFrame({
        "category": ["hospital", "hospital", "pharmacy", "pharmacy"],
        "name": ["Spital X", None, "Farmacia A", "Farmacia B"],
    }, geometry=[Point(0, 0), Point(50, 0), Point(1000, 0), Point(1040, 0)], crs=CRS)
    out = dedupe(fac, 150)
    assert len(out) == 3  # the two hospital points merge; differently named pharmacies stay


def test_nearest_and_coverage():
    origins = gpd.GeoDataFrame(geometry=[Point(0, 0), Point(30000, 0)], crs=CRS)
    hosp = gpd.GeoDataFrame(geometry=[Point(0, 5000)], crs=CRS)
    assert list(nearest_km(origins, hosp).round(3)) == [5.0, pytest.approx(30.414, abs=1e-3)]

    sq = Polygon([(-1000, -1000), (1000, -1000), (1000, 1000), (-1000, 1000)])
    far = Polygon([(50000, 0), (51000, 0), (51000, 1000), (50000, 1000)])
    uat = gpd.GeoDataFrame(geometry=[sq, far], crs=CRS)
    share = coverage_share(uat, hosp, 10000)
    assert share.iloc[0] == pytest.approx(1.0)
    assert share.iloc[1] == 0


def test_composite_index_bounds_and_direction():
    ind = pd.DataFrame({
        "dist_hosp_km": [1, 20, 60],
        "dist_primary_km": [0.5, 5, 15],
        "pharm_per_10k": [3, 1, 0],
        "share_area_hosp_buffer": [1, 0.4, 0],
    })
    w = {"hospital": 0.35, "primary": 0.25, "pharmacy": 0.15, "coverage": 0.25}
    hai = composite_index(ind, w)
    assert hai.iloc[0] == 100 and hai.iloc[2] == 0
    assert hai.is_monotonic_decreasing
    with pytest.raises(AssertionError):
        composite_index(ind, {**w, "hospital": 0.5})


def test_minmax_constant_series():
    assert (minmax(pd.Series([2.0, 2.0])) == 0.5).all()
