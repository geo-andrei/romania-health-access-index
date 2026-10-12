# Deploy the pygeoapi image to Azure Container Apps (consumption plan, scales to zero).
# Prerequisites: Azure CLI, `az login`, Docker Desktop running, and data/processed/publish.gpkg from `hai export`.
# Run from the repo root:  .\deploy\azure\deploy.ps1
# Student subscriptions only allow some regions: .\deploy\azure\deploy.ps1 -Location polandcentral
param([string]$Location = "westeurope")
$ErrorActionPreference = "Stop"

$rg       = "rg-hai-$Location"   # a resource group cannot change region
$location = $Location
$app      = "hai-api"

az extension add --name containerapp --upgrade --only-show-errors
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait
az provider register --namespace Microsoft.ContainerRegistry --wait
az group create --name $rg --location $location --output none
if ($LASTEXITCODE -ne 0) { throw "Could not create the resource group; run 'az login' and retry." }  # Stop doesn't cover native commands in PowerShell 5

# Build locally with Docker and push to Azure Container Registry
# (student subscriptions block ACR Tasks, so `containerapp up --source .` cannot build in the cloud)
$acr = az acr list --resource-group $rg --query "[0].name" -o tsv
if (-not $acr) {
  $acr = "hai$(Get-Random -Maximum 999999)"
  az acr create --resource-group $rg --name $acr --sku Basic --location $location --output none
  if ($LASTEXITCODE -ne 0) { throw "Could not create the container registry." }
}
az acr update --name $acr --admin-enabled true --output none   # lets Container Apps pull with registry credentials
az acr login --name $acr
if ($LASTEXITCODE -ne 0) { throw "ACR login failed; is Docker Desktop running?" }

$image = "$acr.azurecr.io/hai-api:$(Get-Date -Format yyyyMMddHHmm)"   # new tag per deploy = new revision
docker build -t $image .
if ($LASTEXITCODE -ne 0) { throw "docker build failed." }
docker push $image
if ($LASTEXITCODE -ne 0) { throw "docker push failed." }

# Plain create/update instead of `containerapp up`: `up` adds a system-assigned managed identity,
# which the express environment (what `up` created here) rejects
$acrUser = az acr credential show --name $acr --query username -o tsv
$acrPass = az acr credential show --name $acr --query "passwords[0].value" -o tsv

$envName = az containerapp env list --resource-group $rg --query "[0].name" -o tsv
if (-not $envName) {
  $envName = "hai-api-env"
  az containerapp env create --name $envName --resource-group $rg --location $location `
    --environment-mode express --logs-destination none --output none
  if ($LASTEXITCODE -ne 0) { throw "Could not create the Container Apps environment." }
}

$exists = az containerapp list --resource-group $rg --query "[?name=='$app'].name" -o tsv   # list, not show: show errors when missing
if ($exists) {
  az containerapp registry set --name $app --resource-group $rg `
    --server "$acr.azurecr.io" --username $acrUser --password $acrPass --output none
  if ($LASTEXITCODE -ne 0) { throw "Could not set the registry credentials." }
  az containerapp ingress enable --name $app --resource-group $rg --type external --target-port 80 --output none
  if ($LASTEXITCODE -ne 0) { throw "Could not enable ingress." }
  az containerapp update --name $app --resource-group $rg --image $image --output none
} else {
  az containerapp create --name $app --resource-group $rg --environment $envName `
    --image $image `
    --registry-server "$acr.azurecr.io" --registry-username $acrUser --registry-password $acrPass `
    --ingress external --target-port 80 `
    --min-replicas 0 --max-replicas 1 --output none
}
if ($LASTEXITCODE -ne 0) { throw "Container app create/update failed; see the error above." }

$fqdn = az containerapp show --name $app --resource-group $rg --query properties.configuration.ingress.fqdn -o tsv
az containerapp update --name $app --resource-group $rg `
  --set-env-vars "PYGEOAPI_SERVER_URL=https://$fqdn" --output none

Write-Host "OGC API - Features live at https://$fqdn"
Write-Host "Collections: https://$fqdn/collections?f=json"
