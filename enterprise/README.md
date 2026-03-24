# 第二部分：企業級架構 — Hosted Agent + Foundry IQ + MAF Architecture

**同一個 Agent、同一份程式碼、企業級基礎設施。**

這是 [Hosted Agent 教學](../README.md) 的**第二部分**。它部署的是與第一部分完全相同的 HR Agent，但運行在企業級基礎設施上：

| 企業功能 | 說明 |
|---|---|
| **Customer-Managed Keys (CMK)** | 所有靜態資料皆使用你自己的 Key Vault 中的金鑰加密 |
| **無金鑰驗證（Managed Identity）** | 全程零 API 金鑰 — 所有驗證透過 User-Assigned Managed Identity + RBAC |
| **Private Endpoint** | 每個服務都在 VNET 後方 — 不暴露於公開網際網路 |

> **關鍵觀念：** 你的應用程式碼完全不需要修改。`main.py`、`deploy.py`、`Dockerfile` — 皆與第一部分相同。企業級安全性完全在基礎設施層（Bicep）處理。

---

## 架構

```
┌──────────────────── Virtual Network (10.0.0.0/16) ────────────────────┐
│                                                                        │
│  Private Endpoints Subnet (10.0.1.0/24)                               │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                                                                │   │
│  │   ┌──────────────── Microsoft Foundry ──────────────────┐      │   │
│  │   │                                                     │      │   │
│  │   │  ┌──────────────┐       ┌──────────────────────┐   │      │   │
│  │   │  │ Hosted Agent  │──MI──▶│ AI Services (OpenAI)  │   │      │   │
│  │   │  │ (container)   │       │ 🔒 CMK │ 🔑 MI only   │   │      │   │
│  │   │  │  :8088        │       └──────────────────────┘   │      │   │
│  │   │  └──────┬───────┘                                   │      │   │
│  │   │         │              ┌──────────────────────┐     │      │   │
│  │   │         └─────MI──────▶│ AI Search            │     │      │   │
│  │   │                        │ 🔒 CMK │ 🔑 MI only   │     │      │   │
│  │   │                        └──────────────────────┘     │      │   │
│  │   └─────────────────────────────────────────────────────┘      │   │
│  │                                                                │   │
│  │   ┌──────────┐  ┌───────────┐  ┌──────────────────────┐      │   │
│  │   │ Key Vault │  │ Storage   │  │ Container Registry   │      │   │
│  │   │ 🔑 CMK src│  │ 🔒 CMK    │  │ 🔒 CMK │ Premium     │      │   │
│  │   │ 🔐 RBAC   │  │ 🔑 MI     │  │ 🔑 MI only          │      │   │
│  │   └──────────┘  └───────────┘  └──────────────────────┘      │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  🔐 User-Assigned Managed Identity（單一身分識別，所有 RBAC 角色） │
│  🔑 來自 Key Vault 的 Customer-Managed Key（RSA-2048，所有靜態資料） │
│  🔒 Private Endpoint + Private DNS Zone（零公開暴露）              │
└────────────────────────────────────────────────────────────────────────┘
```

### 與第一部分的差異

| 面向 | 第一部分（標準版） | 第二部分（企業版） |
|---|---|---|
| **網路** | 公開端點 | Private Endpoint + VNET |
| **加密** | Microsoft 管理的金鑰 | Customer-Managed Keys (CMK)，來自你自己的 Key Vault |
| **驗證** | DefaultAzureCredential（任何方式） | 僅限 Managed Identity — 所有服務的 API 金鑰皆停用 |
| **Key Vault** | 不需要 | 僅限 RBAC、啟用清除保護、啟用虛刪除 |
| **ACR** | Basic SKU | Premium SKU（Private Endpoint + CMK 所需） |
| **AI Services** | `disableLocalAuth: false` | `disableLocalAuth: true` |
| **AI Search** | 可使用 API 金鑰 | `disableLocalAuth: true`，啟用 CMK 強制加密 |
| **Storage** | 共用金鑰存取 | `allowSharedKeyAccess: false` |
| **服務驗證** | 金鑰式連線 | 身分識別式（MI + RBAC，無金鑰） |
| **應用程式碼** | `main.py` | **完全相同** — 不需修改 |

---

## 專案結構

```
enterprise/
├── infra/                              # 🏗️  Bicep 基礎設施即程式碼
│   ├── main.bicep                      #     協調器 — 部署所有資源
│   └── modules/
│       ├── managed-identity.bicep      #     User-Assigned MI（單一身分識別）
│       ├── network.bicep               #     VNET + 子網路 + 7 個 Private DNS Zone
│       ├── keyvault.bicep              #     Key Vault + CMK 金鑰 + PE
│       ├── storage.bicep               #     Storage + CMK + PE（Blob + File）
│       ├── ai-services.bicep           #     AI Services + 模型 + Foundry 專案 + CMK + PE
│       ├── ai-search.bicep             #     AI Search + CMK 強制加密 + PE
│       └── acr.bicep                   #     Container Registry + CMK + PE
├── main.py                             # ⭐ Agent 程式碼（與第一部分相同）
├── deploy.py                           # 🚀 在 Foundry 中註冊 Agent（與第一部分相同）
├── deploy-infra.ps1                    # 🏗️  部署所有基礎設施的 PowerShell 腳本
├── Dockerfile                          # 🐳 容器映像（與第一部分相同）
├── requirements.txt                    # 📦 相依套件（與第一部分相同）
├── agent.yaml                          # 📄 Agent 中繼資料
└── README.md                           # 📖 本檔案
```

---

## 先決條件

### Azure 權限

部署者需要：
- 訂用帳戶/資源群組的 **Contributor** 角色（用於建立資源）
- **User Access Administrator** 角色（用於建立 RBAC 角色指派）
- 部署腳本會自動授予 **Key Vault Crypto Officer** 以建立 CMK 金鑰

### 本機工具

- **Azure CLI**（含 Bicep）— `az --version` 應顯示 Bicep CLI
- **Docker** — 用於本機建置（選用：`az acr build` 可在雲端建置，無需 Docker）
- **Python 3.12+** — 用於 `deploy.py`
- **PowerShell** — 用於 `deploy-infra.ps1`

---

## 逐步部署指南

### 步驟 1：部署企業級基礎設施

```powershell
# 登入 Azure
az login

# 部署所有資源（VNET、Key Vault、Storage、AI Services + Foundry 專案、AI Search、ACR）
cd enterprise
.\deploy-infra.ps1 -ResourceGroup "rg-hr-agent-enterprise" -Location "eastus2" -Prefix "hragent"
```

這會建立**所有** Azure 資源，包含：
- ✅ 每個服務都有 Private Endpoint
- ✅ Storage、AI Services、ACR 都啟用 CMK 加密（AI Search 啟用 CMK 強制加密）
- ✅ AI Services、AI Search、Storage 的 API 金鑰皆停用
- ✅ RBAC 角色已指派給 Managed Identity

腳本會輸出後續步驟所需的所有設定值。

### 步驟 1.5：暫時開啟公開存取（用於初始設定）

> **重要：** 所有服務預設部署為公開存取**停用**。若要從你的本機推送容器映像和註冊 Agent，
> 需要暫時開啟公開存取。這是初始設定的預期流程 — 你會在步驟 5 中重新鎖定。
>
> 在實際企業環境中，你會從 VNET 內部操作（透過 VPN、ExpressRoute 或搭配
> Azure Bastion 的跳板機 VM）。此範例/教學中，我們暫時開啟存取。

```powershell
# 開啟 AI Services 的公開存取
az cognitiveservices account update -g <rg> -n <ai-services-name> `
    --custom-domain <ai-services-name> `
    --set properties.publicNetworkAccess=Enabled

# 開啟 ACR 的公開存取
az acr update -n <acr-name> --public-network-enabled true

# 開啟 AI Search 的公開存取（透過 REST — CLI 對 UserAssigned Identity 有 bug）
az rest --method PATCH `
    --url "https://management.azure.com/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<search-name>?api-version=2024-06-01-preview" `
    --headers Content-Type=application/json `
    --body '{"properties":{"publicNetworkAccess":"enabled"}}'
```

### 步驟 2：建置並推送容器映像

```powershell
# 方案 A：雲端建置（建議 — 即使有 Private Endpoint 也可運作，無需本機 Docker）
az acr build --registry <acr-name> --image hosted-agents-on-microsoft-foundry:latest --platform linux/amd64 .

# 方案 B：本機建置 + 推送（需要 Docker Desktop 執行中）
docker build --platform linux/amd64 -t <acr-login-server>/hosted-agents-on-microsoft-foundry:latest .
az acr login --name <acr-name>
docker push <acr-login-server>/hosted-agents-on-microsoft-foundry:latest
```

### 步驟 3：在 Foundry 中註冊 Agent

```powershell
# 設定環境變數（使用步驟 1 輸出的值）
$env:AZURE_AI_PROJECT_ENDPOINT = "<project-endpoint-from-step-1>"
$env:AZURE_SEARCH_ENDPOINT = "<search-endpoint-from-step-1>"
$env:CONTAINER_IMAGE = "<acr-login-server>/hosted-agents-on-microsoft-foundry:latest"

# 部署
python deploy.py
```

### 步驟 4：啟動 Agent

前往 **Microsoft Foundry 入口網站** → **Agents** → 找到你的 Agent → **Start**。

### 步驟 5：重新停用公開存取（鎖定）

> Agent 部署並運行後，請重新停用公開存取。Hosted Agent 在 Foundry 的受管理基礎設施
> **內部**運行，透過 Private Endpoint 與所有服務通訊 — 它不需要公開存取。

```powershell
# 停用 AI Services 的公開存取
az cognitiveservices account update -g <rg> -n <ai-services-name> `
    --custom-domain <ai-services-name> `
    --set properties.publicNetworkAccess=Disabled

# 停用 ACR 的公開存取
az acr update -n <acr-name> --public-network-enabled false

# 停用 AI Search 的公開存取
az rest --method PATCH `
    --url "https://management.azure.com/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<search-name>?api-version=2024-06-01-preview" `
    --headers Content-Type=application/json `
    --body '{"properties":{"publicNetworkAccess":"disabled"}}'
```

After this, the only way to reach these services is through the private endpoints inside the VNET.
The hosted agent continues to work because Foundry routes traffic through the private network.

---

## Bicep 模組詳解

### Managed Identity（`managed-identity.bicep`）

建立單一 **User-Assigned Managed Identity**，供所有資源共用。這是無金鑰驗證策略的基石 — 一個身分識別、所有 RBAC 角色：

| 角色 | 資源 | 用途 |
|---|---|---|
| Key Vault Crypto User | Key Vault | 使用 CMK 金鑰進行加密/解密 |
| Storage Blob Data Contributor | Storage | 讀寫 Blob |
| Cognitive Services OpenAI Contributor | AI Services | 呼叫 OpenAI 模型 |
| Search Index Data Reader | AI Search | 查詢搜尋索引 |
| Search Service Contributor | AI Search | 管理搜尋服務 |
| AcrPull + AcrPush | Container Registry | 拉取/推送容器映像 |

### 網路（`network.bicep`）

建立包含 Private Endpoint 子網路和 **7 個 Private DNS Zone** 的 VNET：

| DNS Zone | 服務 |
|---|---|
| `privatelink.cognitiveservices.azure.com` | AI Services |
| `privatelink.openai.azure.com` | OpenAI 端點 |
| `privatelink.search.windows.net` | AI Search |
| `privatelink.blob.core.windows.net` | Storage (Blob) |
| `privatelink.file.core.windows.net` | Storage (File) |
| `privatelink.vaultcore.azure.net` | Key Vault |
| `privatelink.azurecr.io` | Container Registry |

每個 DNS Zone 皆連結至 VNET，使 Private Endpoint 的 DNS 解析自動生效。

### Key Vault（`keyvault.bicep`）

- **僅限 RBAC**（`enableRbacAuthorization: true`）— 不使用存取原則
- **啟用清除保護**（CMK 所需）
- 建立 **RSA-2048 CMK 金鑰**，供所有其他服務使用
- 防火牆：`defaultAction: Deny`、`bypass: AzureServices`

### AI Services（`ai-services.bicep`）

- **`disableLocalAuth: true`** — 完全停用 API 金鑰
- **`allowProjectManagement: true`** — 允許以子資源形式建立 Foundry 專案
- 使用 User-Assigned MI 進行 CMK 加密
- 部署 OpenAI 模型（預設：`gpt-4.1`）
- 建立 **Foundry 專案**（作為 AI Services 帳戶的子資源）
- Private Endpoint 同時包含 `cognitiveservices` 和 `openai` DNS Zone

### AI Search（`ai-search.bicep`）

- **`disableLocalAuth: true`** — 無 API 金鑰或查詢金鑰
- **`encryptionWithCmk.enforcement: 'Enabled'`** — 所有新索引必須使用 CMK
- 啟用語意搜尋（用於知識庫 Grounding）

> **注意：** CMK 強制加密是在服務層級設定。實際的 CMK 金鑰必須在透過 SDK 建立索引時配置。請參閱 [Azure AI Search CMK 文件](https://learn.microsoft.com/en-us/azure/search/search-security-manage-encryption-keys)。

### ACR（`acr.bicep`）

- **Premium SKU**（CMK + Private Endpoint 所需）
- **停用管理員使用者** — 僅透過 RBAC 拉取/推送
- 使用無版本號的金鑰 URI 進行 CMK 加密（相容自動輪替）

---

## 初始設定 vs. 正式環境（Private Endpoint 工作流程）

當所有服務的 `publicNetworkAccess: 'Disabled'` 時，你無法從公開網際網路存取它們 — 包括你的筆電和 Microsoft Foundry 入口網站。

**初始設定時**（推送映像、部署 Agent、在入口網站驗證），你有三個選項：

1. **暫時開啟公開存取**（最簡單 — 本教學使用此方式）
   - 開啟公開存取 → 推送映像 → 部署 Agent → 驗證 → 重新停用
   - 請參閱上方部署指南的步驟 1.5 和步驟 5

2. **使用 VNET 內的跳板機 VM**（企業標準做法）
   - 在 VNET 中部署 VM + Azure Bastion
   - 透過 RDP/SSH 連入 VM 執行 `az acr build`、`python deploy.py`，以及存取入口網站

3. **透過 VPN 連線**（擁有現有基礎設施的企業）
   - Point-to-Site VPN 閘道（約 30 分鐘設定）
   - Site-to-Site VPN 或 ExpressRoute（企業網路已連接）

**Agent 部署完成後**，它在 Foundry 的受管理基礎設施內執行，並透過 **Private Endpoint** 與所有服務通訊 — 不需要公開存取。你僅在進行管理操作時才需要公開存取（或 VNET 存取）。

---

## 疑難排解

### 首次部署失敗
RBAC 角色指派可能需要 5-10 分鐘才能生效。如果部署因權限錯誤而失敗（特別是 Key Vault 金鑰建立或 CMK 設定），請等待 5 分鐘後重試。

### ACR 推送失敗
ACR 的 `publicNetworkAccess: 'Disabled'`。若要推送映像：
- 使用 `az acr build` 在雲端建置（建議 — 即使有 Private Endpoint 也可運作）
- 或暫時開啟公開存取：`az acr update --name <acr> --public-network-enabled true`

### Foundry 入口網站顯示「無法連線」
公開存取停用時這是預期行為。請從 VNET 內部存取入口網站（透過 VM/VPN），或暫時開啟 AI Services 的公開存取。

### 模型部署不可用
`gpt-4.1` 模型可能並非在所有地區都可用。請查閱[模型可用性](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models)並調整 `modelDeploymentName` 參數。

---

## 安全性檢核清單

部署完成後（已重新停用公開存取），請驗證：

- [ ] 所有服務的網路設定中顯示「Private Endpoint」
- [ ] AI Services → 金鑰和端點 → 「本機驗證：已停用」
- [ ] AI Search → 金鑰 → 無可用的 API 金鑰
- [ ] Storage → 設定 → 「允許儲存體帳戶金鑰存取：已停用」
- [ ] Key Vault → 存取設定 → 「權限模型：Azure 角色型存取控制」
- [ ] ACR → 存取金鑰 → 「管理員使用者：已停用」
- [ ] 任何服務皆無公用 IP 位址

你可以使用內含的 `validate-enterprise.ps1` 腳本自動驗證：

```powershell
.\validate-enterprise.ps1 -ResourceGroup "rg-hr-agent-enterprise"
```

---

## 相依套件

與第一部分相同 — 應用程式碼不需修改：

| 套件 | 用途 |
|---|---|
| `azure-ai-agentserver-agentframework` | Hosting Adapter |
| `agent-framework-core` | Agent Framework 核心 |
| `agent-framework-azure-ai` | Azure AI 用戶端 |
| `agent-framework-azure-ai-search` | AI Search Context Provider |
| `azure-ai-projects` | Foundry SDK（deploy.py） |
| `azure-identity` | Azure 驗證（DefaultAzureCredential） |
