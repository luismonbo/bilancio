# Bilancio Infrastructure

Bicep templates for the Azure production environment. All resources deploy to `italynorth`.

## Prerequisites

- Azure CLI (`az`) installed and logged in: `az login`
- Bicep CLI: `az bicep install`
- A resource group already created: `az group create -n rg-bilancio-prod -l italynorth`
- GitHub OIDC federation configured (see below)

## First Deployment

```bash
az deployment group create \
  --resource-group rg-bilancio-prod \
  --template-file infra/main.bicep \
  --parameters infra/parameters.prod.bicepparam
```

This provisions (in order):
1. Log Analytics Workspace + Application Insights
2. Key Vault (access policies for deploying user + Container App managed identity)
3. Azure Container Registry
4. Azure Database for PostgreSQL Flexible Server (Entra admin configured)
5. Azure Blob Storage (containers: `uploads`, `backups` with 90-day lifecycle)
6. Container Apps Environment + Container App (Bilancio)

After first deploy, **manually create secrets in Key Vault** (not in any file):
- `azure-foundry-api-key` — if using Azure AI Foundry LLM backend

## Updating Infrastructure

Re-run the same `az deployment group create` command. Bicep deployments are idempotent.

## Updating the Application

Normal deploys happen automatically via `deploy.yml` on push to `main`.

Manual deploy:

```bash
az acr build --registry <acr-name> --image bilancio:latest .
az containerapp update \
  --name bilancio \
  --resource-group rg-bilancio-prod \
  --image <acr-name>.azurecr.io/bilancio:latest
```

## Setting Up GitHub Actions OIDC Federation

This is a one-time setup that allows GitHub Actions to authenticate to Azure without storing any
secrets.

```bash
# 1. Create an App Registration (or use an existing service principal)
APP_ID=$(az ad app create --display-name "bilancio-github-deploy" --query appId -o tsv)
SP_OBJ_ID=$(az ad sp create --id $APP_ID --query id -o tsv)

# 2. Assign the Contributor role on the resource group
az role assignment create \
  --assignee $SP_OBJ_ID \
  --role Contributor \
  --scope /subscriptions/<subscription-id>/resourceGroups/rg-bilancio-prod

# 3. Create the federated credential (scoped to main branch of your repo)
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "bilancio-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<github-owner>/bilancio:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# 4. Add these as GitHub Actions variables (NOT secrets):
#    AZURE_CLIENT_ID = $APP_ID
#    AZURE_TENANT_ID = $(az account show --query tenantId -o tsv)
#    AZURE_SUBSCRIPTION_ID = $(az account show --query id -o tsv)
```

## Destroying the Environment

```bash
az group delete --name rg-bilancio-prod --yes
```

Warning: this deletes all data permanently including the database. Export a backup first.
