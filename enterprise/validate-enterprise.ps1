# 企業級架構驗證腳本
# 驗證 3 大企業支柱是否正確部署：
#   ✅ Customer-Managed Keys (CMK)
#   ✅ 無金鑰驗證（僅限 Managed Identity — 無 API 金鑰）
#   ✅ Private Endpoint（無公開網路存取）
#
# 使用方式：
#   .\validate-enterprise.ps1 -ResourceGroup "rg-hr-agent-enterprise"

param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup
)

$ErrorActionPreference = "Stop"
$pass = 0
$fail = 0
$warn = 0

function Check([string]$Name, [bool]$Condition, [string]$FailMsg = "") {
    if ($Condition) {
        Write-Host "  ✅ $Name" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "  ❌ $Name — $FailMsg" -ForegroundColor Red
        $script:fail++
    }
}

function Warn([string]$Name, [string]$Msg) {
    Write-Host "  ⚠️  $Name — $Msg" -ForegroundColor Yellow
    $script:warn++
}

Write-Host "`n================================================================" -ForegroundColor Cyan
Write-Host " 企業級架構驗證" -ForegroundColor Cyan
Write-Host " 資源群組: $ResourceGroup" -ForegroundColor Cyan
Write-Host "================================================================`n" -ForegroundColor Cyan

# -----------------------------------------------------------------------
# 探索資源
# -----------------------------------------------------------------------
Write-Host "正在探索資源..." -ForegroundColor Yellow

$keyVault = az keyvault list -g $ResourceGroup --query "[0]" -o json | ConvertFrom-Json
$storage = az storage account list -g $ResourceGroup --query "[0]" -o json | ConvertFrom-Json
$aiServices = az cognitiveservices account list -g $ResourceGroup --query "[0]" -o json | ConvertFrom-Json
$search = az search service list -g $ResourceGroup --query "[0]" -o json | ConvertFrom-Json
$acr = az acr list -g $ResourceGroup --query "[0]" -o json | ConvertFrom-Json
$vnet = az network vnet list -g $ResourceGroup --query "[0]" -o json | ConvertFrom-Json
$privateEndpoints = az network private-endpoint list -g $ResourceGroup -o json | ConvertFrom-Json
$identity = az identity list -g $ResourceGroup --query "[0]" -o json | ConvertFrom-Json

Write-Host "  Found: Key Vault=$($keyVault.name), Storage=$($storage.name), AI Services=$($aiServices.name)"
Write-Host "  Found: Search=$($search.name), ACR=$($acr.name), VNET=$($vnet.name)"
Write-Host "  Found: Managed Identity=$($identity.name)"
Write-Host "  Found: $($privateEndpoints.Count) private endpoints`n"

# =======================================================================
# 支柱 1：Private Endpoint（無公開網路存取）
# =======================================================================
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Magenta
Write-Host " 支柱 1：Private Endpoint" -ForegroundColor Magenta
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Magenta

# VNET 存在
Check "VNET 存在" ($null -ne $vnet) "未找到 VNET"

# Private Endpoint 數量（預期：KV + Storage Blob + Storage File + AI Services + AI Search + ACR = 6）
Check "至少部署 6 個 Private Endpoint" ($privateEndpoints.Count -ge 6) "僅找到 $($privateEndpoints.Count) 個"

# 列出所有 PE
Write-Host "`n  Private Endpoint：" -ForegroundColor Gray
foreach ($pe in $privateEndpoints) {
    $target = $pe.privateLinkServiceConnections[0].groupIds -join ","
    Write-Host "    🔒 $($pe.name) → $target" -ForegroundColor Gray
}
Write-Host ""

# 各服務的公開網路存取已停用
$kvNetworkDefault = $keyVault.properties.networkAcls.defaultAction
Check "Key Vault — 網路預設動作: Deny" ($kvNetworkDefault -eq "Deny") "取得: $kvNetworkDefault"

Check "Storage — 公開網路存取: Disabled" ($storage.publicNetworkAccess -eq "Disabled") "取得: $($storage.publicNetworkAccess)"

$aiPub = $aiServices.properties.publicNetworkAccess
Check "AI Services — 公開網路存取: Disabled" ($aiPub -eq "Disabled") "取得: $aiPub"

$searchPub = $search.properties.publicNetworkAccess
Check "AI Search — 公開網路存取: Disabled" ($searchPub -eq "disabled") "取得: $searchPub"

Check "ACR — 公開網路存取: Disabled" ($acr.publicNetworkAccess -eq "Disabled") "取得: $($acr.publicNetworkAccess)"

# Private DNS Zone
$dnsZones = az network private-dns zone list -g $ResourceGroup -o json | ConvertFrom-Json
Write-Host "`n  Private DNS Zone ($($dnsZones.Count))：" -ForegroundColor Gray
foreach ($zone in $dnsZones) {
    Write-Host "    🌐 $($zone.name)" -ForegroundColor Gray
}
Check "`n至少 7 個 Private DNS Zone" ($dnsZones.Count -ge 7) "找到 $($dnsZones.Count) 個"

# =======================================================================
# 支柱 2：無金鑰驗證（僅限 Managed Identity — 無 API 金鑰）
# =======================================================================
Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Magenta
Write-Host " 支柱 2：無金鑰驗證（僅限 Managed Identity）" -ForegroundColor Magenta
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Magenta

# User-Assigned MI 存在
Check "User-Assigned Managed Identity 存在" ($null -ne $identity) "未找到 UAMI"

# Key Vault — RBAC 授權
Check "Key Vault — 已啟用 RBAC 授權（無存取原則）" ($keyVault.properties.enableRbacAuthorization -eq $true) "enableRbacAuthorization 不是 true"

# AI Services — 本機驗證已停用
$aiLocalAuth = $aiServices.properties.disableLocalAuth
Check "AI Services — 本機驗證已停用（無 API 金鑰）" ($aiLocalAuth -eq $true) "disableLocalAuth=$aiLocalAuth"

# 嘗試列出 AI Services 金鑰 — 應該失敗
Write-Host "  測試：嘗試取得 AI Services 金鑰（應該失敗）..." -ForegroundColor Gray
$keyResult = az cognitiveservices account keys list -g $ResourceGroup -n $aiServices.name 2>&1
$keyFailed = $keyResult -match "error|cannot|disabled|forbidden|not allowed"
Check "AI Services — 金鑰取得已阻擋" $keyFailed "金鑰仍可存取！"

# AI Search — 本機驗證已停用
$searchLocalAuth = $search.properties.disableLocalAuth
Check "AI Search — 本機驗證已停用（無 API / 查詢金鑰）" ($searchLocalAuth -eq $true) "disableLocalAuth=$searchLocalAuth"

# Storage — 共用金鑰存取已停用
Check "Storage — 共用金鑰存取已停用" ($storage.allowSharedKeyAccess -eq $false) "allowSharedKeyAccess=$($storage.allowSharedKeyAccess)"

# ACR — 管理員使用者已停用
Check "ACR — 管理員使用者已停用" ($acr.adminUserEnabled -eq $false) "adminUserEnabled=$($acr.adminUserEnabled)"

# MI 上的 RBAC 角色指派
Write-Host "`n  MI ($($identity.principalId)) 的角色指派：" -ForegroundColor Gray
$roles = az role assignment list --assignee $identity.principalId -g $ResourceGroup --query "[].{Role:roleDefinitionName, Scope:scope}" -o json | ConvertFrom-Json
foreach ($role in $roles) {
    $scopeShort = ($role.Scope -split "/")[-1]
    Write-Host "    🔑 $($role.Role) → $scopeShort" -ForegroundColor Gray
}
Check "`nMI 至少有 5 個 RBAC 角色指派" ($roles.Count -ge 5) "找到 $($roles.Count) 個"

# =======================================================================
# 支柱 3：Customer-Managed Keys (CMK)
# =======================================================================
Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Magenta
Write-Host " 支柱 3：Customer-Managed Keys (CMK)" -ForegroundColor Magenta
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Magenta

# Key Vault — 清除保護（CMK 所需）
Check "Key Vault — 已啟用清除保護" ($keyVault.properties.enablePurgeProtection -eq $true) "enablePurgeProtection 不是 true"

# Key Vault — 虛刪除
Check "Key Vault — 已啟用虛刪除" ($keyVault.properties.enableSoftDelete -eq $true) "enableSoftDelete 不是 true"

# CMK 金鑰存在
$keys = az keyvault key list --vault-name $keyVault.name -o json 2>&1 | ConvertFrom-Json
$cmkKey = $keys | Where-Object { $_.name -eq "cmk-encryption-key" }
Check "CMK 金鑰 'cmk-encryption-key' 存在於 Key Vault 中" ($null -ne $cmkKey) "未找到金鑰"

if ($cmkKey) {
    Write-Host "    🔐 Key URI: $($cmkKey.kid)" -ForegroundColor Gray
}

# Storage — CMK 加密
$storageEncryption = $storage.encryption.keySource
Check "Storage — 加密金鑰來源: Microsoft.Keyvault" ($storageEncryption -eq "Microsoft.Keyvault") "取得: $storageEncryption"

# AI Services — CMK 加密
$aiEncryption = $aiServices.properties.encryption.keySource
Check "AI Services — 加密金鑰來源: Microsoft.KeyVault" ($aiEncryption -eq "Microsoft.KeyVault") "取得: $aiEncryption"

# ACR — CMK 加密
$acrEncryption = $acr.encryption.status
Check "ACR — CMK 加密已啟用" ($acrEncryption -eq "enabled") "取得: $acrEncryption"

# AI Search — CMK 強制加密
$searchCmk = $search.properties.encryptionWithCmk.enforcement
Check "AI Search — CMK 強制加密已啟用" ($searchCmk -eq "Enabled") "取得: $searchCmk"

# =======================================================================
# 摘要
# =======================================================================
Write-Host "`n================================================================" -ForegroundColor Cyan
Write-Host " 驗證摘要" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  ✅ 通過: $pass" -ForegroundColor Green
if ($warn -gt 0) { Write-Host "  ⚠️  警告: $warn" -ForegroundColor Yellow }
if ($fail -gt 0) { Write-Host "  ❌ 失敗: $fail" -ForegroundColor Red }
Write-Host ""

if ($fail -eq 0) {
    Write-Host "  🎉 所有檢查皆通過 — 企業級架構已驗證！" -ForegroundColor Green
    Write-Host "  你的部署包含：" -ForegroundColor Green
    Write-Host "    🔒 所有服務皆有 Private Endpoint（零公開暴露）" -ForegroundColor Green
    Write-Host "    🔑 僅限 Managed Identity 驗證（零 API 金鑰）" -ForegroundColor Green
    Write-Host "    🔐 Customer-Managed 加密金鑰（你的金鑰、你的控制）" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  $fail 項檢查失敗。請檢閱上方輸出。" -ForegroundColor Red
}
Write-Host ""
