# Image deployed to Azure Container Apps: pygeoapi + the exported GeoPackage, no database.
FROM geopython/pygeoapi:0.19.0
COPY config/pygeoapi.azure.yml /pygeoapi/local.config.yml
COPY data/processed/publish.gpkg /data/publish.gpkg
