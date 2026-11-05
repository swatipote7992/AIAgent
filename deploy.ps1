# Deploys the backend (Azure Container Apps) and the frontend (Static Web Apps) to Azure.
# Run from the repo root in PowerShell after `az login`. Reads the secrets from .env, never prints them.
$ErrorActionPreference = "Continue"   # az writes warnings to stderr; failures are caught by Run via the exit code
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"   # the az build log has characters the Windows code page cannot print

$rg       = "insu_rag_rg"
$location = "uksouth"
$swaLoc   = "eastus2"             # Static Web Apps is not offered in UK South, and West Europe refuses new customers
$acr      = "insurragacr"         # container registry: letters and digits only, globally unique
$env_     = "insur-rag-env"       # Container Apps environment
$api      = "insur-rag-api"       # the backend container app
$web      = "insur-rag-web"       # the Static Web App

function Run($cmd) { Invoke-Expression $cmd; if ($LASTEXITCODE -ne 0) { throw "Failed: $cmd" } }

# 1. Resource group, container registry and the Container Apps extension
Run "az group create --name $rg --location $location --output none"
Run "az acr create --name $acr --resource-group $rg --sku Basic --admin-enabled true --output none"
Run "az extension add --name containerapp --upgrade --yes --only-show-errors"
Run "az provider register --namespace Microsoft.App --wait"
Run "az provider register --namespace Microsoft.OperationalInsights --wait"

# 2. Build the backend image in Azure (no local Docker needed) and wait for it
Run "az acr build --registry $acr --image insur-rag-api:latest --no-logs backend"
do {   # --no-logs returns at once, so wait for the build to finish
    Start-Sleep -Seconds 10
    $status = az acr task list-runs --registry $acr --top 1 --query "[0].status" -o tsv
    Write-Host "Image build: $status"
} while ($status -in @("Queued", "Started", "Running"))
if ($status -ne "Succeeded") { throw "Image build ended with status $status" }

# 3. Frontend: create the static web app first, so its address is known for CORS
Run "az staticwebapp create --name $web --resource-group $rg --location $swaLoc --sku Free --output none"
$webHost = az staticwebapp show --name $web --resource-group $rg --query defaultHostname -o tsv

# 4. Backend: environment, then the container app with every .env value stored as a secret
Run "az containerapp env create --name $env_ --resource-group $rg --location $location --output none"
if (az containerapp list --resource-group $rg --query "[?name=='$api'].name" -o tsv) {
    Run "az containerapp delete --name $api --resource-group $rg --yes --output none"   # recreate on rerun
}
$apiKey = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")   # new shared key on every run
$values = [ordered]@{ "CORS_ORIGINS" = "https://$webHost"; "API_KEY" = $apiKey }
Get-Content .env | Where-Object { $_ -match "^\s*[A-Za-z_]+=.+" } | ForEach-Object {
    $key, $value = $_.Trim().Split("=", 2)
    $values[$key] = $value
}
$secrets = @(); $envVars = @()
foreach ($key in $values.Keys) {
    $name = $key.ToLower().Replace("_", "-")
    $secrets += "$name=$($values[$key])"
    $envVars += "$key=secretref:$name"
}
$acrPassword = az acr credential show --name $acr --query "passwords[0].value" -o tsv
az containerapp create --name $api --resource-group $rg --environment $env_ `
    --image "$acr.azurecr.io/insur-rag-api:latest" `
    --registry-server "$acr.azurecr.io" --registry-username $acr --registry-password $acrPassword `
    --ingress external --target-port 8000 --min-replicas 0 --max-replicas 1 `
    --secrets $secrets --env-vars $envVars --output none
if ($LASTEXITCODE -ne 0) { throw "Failed to create the container app" }
$apiHost = az containerapp show --name $api --resource-group $rg --query properties.configuration.ingress.fqdn -o tsv

# 5. Build the frontend against the backend address and upload it
Push-Location frontend
$env:VITE_API_URL = "https://$apiHost"
$env:VITE_API_KEY = $apiKey
Run "npm install"
Run "npm run build"
$token = az staticwebapp secrets list --name $web --resource-group $rg --query properties.apiKey -o tsv
Run "npx --yes @azure/static-web-apps-cli deploy ./dist --deployment-token $token --env production"
Pop-Location

Write-Host "Frontend: https://$webHost"
Write-Host "Backend:  https://$apiHost/docs"
Write-Host "The backend only answers calls that carry the shared key (API_KEY), which is built into the frontend."
Write-Host "Only invited users can open the frontend. Invite someone with:"
Write-Host "  az staticwebapp users invite --name $web --resource-group $rg --authentication-provider aad --user-details <email> --domain $webHost --roles invited --invitation-expiration-in-hours 24"
