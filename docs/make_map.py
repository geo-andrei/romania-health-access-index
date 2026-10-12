"""Render docs/map.png (README figure) from the exported GeoJSON. Run from the repo root after `hai export`."""
import sys, geopandas as gpd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
src, out = (sys.argv[1:3] if len(sys.argv) > 2 else ("data/processed", "docs/map.png"))
uat = gpd.read_file(f"{src}/access_index.geojson").to_crs(3844)
cty = gpd.read_file(f"{src}/county_summary.geojson").to_crs(3844)
colors = {1: "#b7d3f6", 2: "#6da7ec", 3: "#2a78d6", 4: "#184f95", 5: "#0d366b"}
fig, ax = plt.subplots(figsize=(10, 7.2), dpi=150)
fig.patch.set_facecolor("white")
uat.plot(ax=ax, color=uat["hai_quintile"].map(colors), edgecolor="white", linewidth=0.08)
cty.boundary.plot(ax=ax, color="#ffffff", linewidth=0.7)
ax.set_axis_off()
rng = uat.groupby("hai_quintile")["hai"].agg(["min", "max"])
lab = {1: "lowest access", 5: "highest access"}
handles = [Patch(facecolor=colors[q], edgecolor="none",
                 label=f"Q{q}  {rng.loc[q,'min']:.0f}-{rng.loc[q,'max']:.0f}" + (f"  ({lab[q]})" if q in lab else ""))
           for q in range(1, 6)]
ax.legend(handles=handles, title="HAI quintile (0-100)", loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False,
          fontsize=9, title_fontsize=9.5, labelcolor="#333333")
ax.set_title("Healthcare Accessibility Index by UAT, Romania", loc="left", fontsize=13, color="#1a1a1a", pad=10)
fig.text(0.01, 0.015, "Straight-line proximity to hospitals, primary care and pharmacies. "
         "Data: © OpenStreetMap contributors (ODbL), geoBoundaries, WorldPop 2020. EPSG:3844.",
         fontsize=7.5, color="#555555")
fig.savefig(out, bbox_inches="tight", facecolor="white")
assert uat["hai_quintile"].isin(colors).all()
print(f"wrote {out}")
