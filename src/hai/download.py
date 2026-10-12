"""Fetch raw inputs: geoBoundaries ADM1/ADM2, OSM health facilities (Overpass), WorldPop."""
import json

import requests

# Overpass (and some CDNs) reject the default python-requests User-Agent with 406
HTTP = requests.Session()
HTTP.headers.update({
    "User-Agent": "romania-health-access-index/0.1 (healthcare accessibility portfolio project)",
    "Accept": "*/*",
})

from . import lineage
from .config import path, settings

OVERPASS_QUERY = """
[out:json][timeout:600];
area["ISO3166-1"="RO"][admin_level=2]->.ro;
(
  nwr["amenity"~"^(hospital|clinic|doctors|pharmacy)$"](area.ro);
  nwr["healthcare"~"^(hospital|clinic|doctor|centre|pharmacy)$"](area.ro);
);
out center tags;
"""


def _get(url: str, dest):
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip {dest.name} (already downloaded; delete it to refresh)")
        return dest
    print(f"GET {url}")
    with HTTP.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return dest


def boundaries():
    src = settings()["sources"]["boundaries"]
    outs = []
    for level in ("adm1", "adm2"):
        meta = HTTP.get(src[f"{level}_api"], timeout=60).json()
        dest = path("raw", f"rou_{level}.geojson")
        _get(meta["gjDownloadURL"], dest)
        path("raw", f"rou_{level}_meta.json").write_text(json.dumps(meta, indent=2))
        outs.append(dest)
    lineage.record("download.boundaries", [src["adm1_api"], src["adm2_api"]], outs)


def facilities():
    dest = path("raw", "osm_health.json")
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip {dest.name} (already downloaded; delete it to refresh)")
        return
    urls = settings()["sources"]["osm"]["overpass_urls"]
    for url in urls:  # main instance first, mirrors if it is busy or refuses
        print(f"POST {url} (Overpass query, can take a few minutes)")
        try:
            r = HTTP.post(url, data={"data": OVERPASS_QUERY}, timeout=900)
            r.raise_for_status()
            elements = r.json()["elements"]
            break
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"  failed: {e}")
    else:
        raise RuntimeError("all Overpass endpoints failed; try again later")
    dest.write_text(r.text, encoding="utf-8")
    n = len(elements)
    print(f"{n} OSM elements")
    lineage.record("download.facilities", [url], [dest], query=OVERPASS_QUERY.strip(), elements=n)


def population():
    url = settings()["sources"]["population"]["url"]
    dest = _get(url, path("raw", "worldpop_rou_2020.tif"))
    lineage.record("download.population", [url], [dest])


def run():
    boundaries()
    facilities()
    population()
