# 企業級基礎設施部署腳本
# 部署所有 Azure 資源，包含 CMK + Managed Identity + Private Endpoint
#
# 先決條件：
#   - 已安裝 Azure CLI 並已登入（az login）
#   - 目標訂用帳戶需有 Contributor + User Access Administrator 權限
#   - Bicep CLI（隨 Azure CLI 附帶）
#
# 使用方式：
#   .\deploy-infra.ps1 -ResourceGroup "rg-hr-agent-enterprise" -Location "eastus2" -Prefix "hragent"

param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $true)]
    [string]$Location,

    [Parameter(Mandatory = $true)]
    [ValidateLength(3, 10)]
    [string]$Prefix,

    [string]$ModelDeploymentName = "gpt-4.1",
    [string]$SearchSku = "standard"
)

$ErrorActionPreference = "Stop"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " 企業級基礎設施部署" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# --- 取得部署者的 Object ID（用於 Key Vault Crypto Officer 角色）---
Write-Host "正在取得部署者身分識別..." -ForegroundColor Yellow
$deployerObjectId = az ad signed-in-user show --query id -o tsv
if ($LASTEXITCODE -ne 0) {
    Write-Error "無法取得部署者身分識別。請確認已透過 'az login' 登入。"
    exit 1
}
Write-Host "  部署者 Object ID: $deployerObjectId"

# --- 建立資源群組 ---
Write-Host "`n正在建立資源群組 '$ResourceGroup'（位於 '$Location'）..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location --output none

# --- 部署 Bicep ---
Write-Host "`n正在部署企業級基礎設施..." -ForegroundColor Yellow
Write-Host "  將建立：VNET、Key Vault (CMK)、Storage、AI Services + Foundry 專案、AI Search、ACR"
Write-Host "  所有資源皆含 Private Endpoint、CMK 加密及 Managed Identity 驗證。"
Write-Host "  可能需要 15-30 分鐘。`n"

$deploymentName = "enterprise-$((Get-Date).ToString('yyyyMMddHHmmss'))"

$result = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file infra/main.bicep `
    --parameters prefix=$Prefix `
                 deployerPrincipalId=$deployerObjectId `
                 modelDeploymentName=$ModelDeploymentName `
                 searchSku=$SearchSku `
    --name $deploymentName `
    --query "properties.outputs" `
    --output json

if ($LASTEXITCODE -ne 0) {
    Write-Error "`n部署失敗。請在 Azure 入口網站查看詳細資訊。"
    Write-Host "  常見問題：" -ForegroundColor Yellow
    Write-Host "    - RBAC 生效延遲：請等待 5 分鐘後重試"
    Write-Host "    - 配額限制：請檢查你所在區域的 AI Services 和 Search 配額"
    Write-Host "    - 名稱衝突：請嘗試不同的 prefix"
    exit 1
}

$outputs = $result | ConvertFrom-Json

# --- 顯示結果 ---
Write-Host "`n========================================" -ForegroundColor Green
Write-Host " 部署完成！" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "資源摘要：" -ForegroundColor Cyan
Write-Host "  Project Endpoint:     $($outputs.projectEndpoint.value)"
Write-Host "  AI Services Endpoint: $($outputs.aiServicesEndpoint.value)"
Write-Host "  Search Endpoint:      $($outputs.searchEndpoint.value)"
Write-Host "  ACR Login Server:     $($outputs.acrLoginServer.value)"
Write-Host "  MI Client ID:         $($outputs.managedIdentityClientId.value)"
Write-Host "  Key Vault:            $($outputs.keyVaultName.value)"

Write-Host "`n--- 後續步驟 ---" -ForegroundColor Yellow
Write-Host "1. 暫時開啟公開存取（服務預設部署為公開存取停用）："
Write-Host "   請參閱 README.md 步驟 1.5 的命令。"
Write-Host ""
Write-Host "2. 建置並推送你的容器映像（雲端建置 — 無需本機 Docker）："
Write-Host "   az acr build --registry $($outputs.acrLoginServer.value.Split('.')[0]) --image hosted-agents-on-microsoft-foundry:latest --platform linux/amd64 ."
Write-Host ""
Write-Host "3. 設定環境變數並部署 Agent："
Write-Host "   `$env:AZURE_AI_PROJECT_ENDPOINT = '$($outputs.projectEndpoint.value)'"
Write-Host "   `$env:AZURE_SEARCH_ENDPOINT = '$($outputs.searchEndpoint.value)'"
Write-Host "   `$env:CONTAINER_IMAGE = '$($outputs.acrLoginServer.value)/hosted-agents-on-microsoft-foundry:latest'"
Write-Host "   python deploy.py"
Write-Host ""
Write-Host "4. 在 Microsoft Foundry 入口網站中啟動 Agent。"
Write-Host ""
Write-Host "5. 重新停用公開存取（請參閱 README.md 步驟 5）。"
