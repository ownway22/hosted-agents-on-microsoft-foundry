# Containerize Any Agent Framework Agent for Microsoft Foundry

![Architecture Diagram — How to import any Agent as a Hosted Agent on Microsoft Foundry](architecture-diagram-hosted-agents.png)

This repo is a **template + tutorial** for containerizing a [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) agent and deploying it as a **hosted agent** on [Microsoft Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents).

The included HR agent is just a **sample** — you can replace it with your own agent built on Agent Framework.

---

## How It Works

Foundry hosted agents are Docker containers that expose a REST API. Your agent runs inside the container as an HTTP server. Foundry manages scaling, identity, networking, and observability — you just provide the container image.

The key technology is the **hosting adapter** (`from_agent_framework()`), which wraps any `ChatAgent` into a Uvicorn web server on port 8088:

```
Your ChatAgent  →  from_agent_framework(agent).run()  →  HTTP server (:8088)
                                                            ├── POST /responses   (OpenAI Responses API)
                                                            └── GET  /readiness   (health check)
```

Foundry sends user messages to `POST /responses`, your agent processes them, and the response goes back through the same endpoint.

---

## Step-by-Step Guide

### Step 0: Build your agent (or use the sample)

The file `original/hr_agent.py` is a **sample agent** — a standalone Agent Framework script that answers HR questions using an Azure AI Search knowledge base. It's included only as a reference to show what a typical agent looks like before containerization.

**You don't need to use this agent.** Replace it with any agent you've built using Microsoft Agent Framework.

### Step 1: Adapt your agent for hosting (`main.py`)

`main.py` is where containerization happens. It takes your agent logic and wraps it with the hosting adapter. The file is heavily commented — open it to see exactly what's required vs. optional.

**The 4 things you must do:**

1. Use `ChatAgent` (not `Agent`) — the hosting adapter requires this class
2. Use sync `DefaultAzureCredential` (not async) — the adapter manages async internally
3. Build your `ChatAgent` with your instructions and context providers
4. Call `from_agent_framework(agent).run()` — this starts the HTTP server

**To swap in your own agent**, edit `main.py`:
- Replace `HR_INSTRUCTIONS` with your agent's system prompt
- Replace/remove `AzureAISearchContextProvider` with your agent's tools or context providers (or use `context_providers=[]` if none)
- Update `name` and `id` in the `ChatAgent` constructor

### Step 2: Containerize (`Dockerfile`)

The Dockerfile packages your agent into a Docker image:

```bash
# Build the image (always target linux/amd64 — Foundry runs on AMD64)
docker build --platform linux/amd64 -t my-agent:latest .
```

The image uses Python 3.12, installs dependencies with `uv` (fast pip alternative), and runs `python main.py` as the entry point. Port 8088 is exposed for the hosting adapter.

### Step 3: Push to Azure Container Registry

You need an ACR to store your container image. Foundry pulls from it at deployment time.

```bash
# Create an ACR (one-time)
az acr create --name <your-acr-name> --resource-group <your-rg> --sku Basic

# Login, tag, and push
az acr login --name <your-acr-name>
docker tag my-agent:latest <your-acr-name>.azurecr.io/my-agent:latest
docker push <your-acr-name>.azurecr.io/my-agent:latest
```

### Step 4: Register the agent in Foundry (`deploy.py`)

`deploy.py` uses the `azure-ai-projects` SDK to tell Foundry about your container:

```bash
# Set environment variables
export AZURE_AI_PROJECT_ENDPOINT="https://<your-resource>.services.ai.azure.com/api/projects/<your-project>"
export CONTAINER_IMAGE="<your-acr-name>.azurecr.io/my-agent:latest"
export AZURE_SEARCH_ENDPOINT="https://<your-search>.search.windows.net"

# Login and deploy
az login
python deploy.py
```

This creates an agent entry in Foundry with the container image, resource allocation (CPU/memory), and environment variables your agent needs at runtime.

**To customize for your agent**, edit `deploy.py`:
- Change `AGENT_NAME` and `description`
- Update `environment_variables` to match what your agent reads from `os.getenv()`

### Step 5: Start the agent in Foundry

Go to the **Foundry portal** → **Agents** → find your agent → click **Start**. Foundry pulls your image from ACR, starts the container, and begins routing requests to it.

---

## Project Structure

```
hosted-agents-on-microsoft-foundry/
├── main.py                   # ⭐ Hosted agent entry point (the containerization layer)
├── original/
│   └── hr_agent.py           # 📋 Sample agent code (standalone, for reference only)
├── Dockerfile                # 🐳 Container image definition
├── deploy.py                 # 🚀 SDK script to register agent in Foundry
├── requirements.txt          # 📦 Python dependencies (pinned versions)
├── agent.yaml                # 📄 Agent metadata (for azd CLI deployment)
├── .env.example              # 🔑 Environment variable template
├── .gitignore
└── README.md
```

### What each file does

| File | Purpose | Do you need to edit it? |
|---|---|---|
| `main.py` | Wraps your agent with the hosting adapter for containerization | **Yes** — replace the sample agent logic with yours |
| `original/hr_agent.py` | Sample standalone agent (reference only, not used in the container) | No — it's just a reference |
| `Dockerfile` | Builds the container image | Rarely — only if you add extra files |
| `deploy.py` | Registers the agent in Foundry via SDK | **Yes** — update agent name, description, env vars |
| `requirements.txt` | Pinned Python dependencies | Only if your agent needs additional packages |
| `agent.yaml` | Declarative agent definition (alternative to deploy.py, for `azd` CLI) | Optional |
| `.env.example` | Template for environment variables | Copy to `.env` for local dev |

---

## What Changed: Original Agent → Hosted Agent

| Aspect | Original (`original/hr_agent.py`) | Hosted (`main.py`) |
|---|---|---|
| **Class** | `Agent` | `ChatAgent` |
| **Execution** | One-shot async script (`asyncio.run`) | Long-running HTTP server (Uvicorn on :8088) |
| **Credential** | Async `DefaultAzureCredential` | Sync `DefaultAzureCredential` |
| **Entry point** | `asyncio.run(main())` | `from_agent_framework(agent).run()` |
| **API** | None — prints to console | REST: `POST /responses`, `GET /readiness` |
| **Packaging** | Bare Python script | Docker container |
| **Deployment** | Run locally | Foundry Agent Service (managed) |
| **Observability** | None | Built-in OpenTelemetry |

---

## Prerequisites

### Local tools

- **Python 3.12+**
- **[Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)** — for `az login` and ACR operations
- **[Docker](https://docs.docker.com/get-docker/)** — for building the container image

### Azure resources

These are the Azure resources required to run this demo end-to-end:

| Resource | What it's for | Required? |
|---|---|---|
| **[Azure AI Foundry project](https://learn.microsoft.com/en-us/azure/foundry/foundry-portal/create-project)** | Hosts the agent, provides the project endpoint, and manages agent lifecycle | Yes |
| **[Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/overview)** (model deployment) | The LLM that powers your agent (e.g. `gpt-4.1`). Created inside the Foundry project. | Yes |
| **[Azure Container Registry (ACR)](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-intro)** | Stores the Docker image. Foundry pulls from here at deployment time. | Yes |
| **[Azure AI Search](https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search)** | Knowledge base for grounding (the HR sample uses index `kb1-hr`). | Only if your agent uses knowledge base grounding |
| **[Azure Storage Account](https://learn.microsoft.com/en-us/azure/storage/common/storage-account-overview)** | Auto-provisioned by the Foundry project for internal state management. You don't interact with it directly. | Auto-created |

> **RBAC:** The Foundry project's managed identity needs **AcrPull** on the ACR, and if using AI Search, the identity also needs **Search Index Data Reader** on the search service.

### Architecture diagram

```
┌─────────────────────────────────────────────────────────┐
│                   Azure AI Foundry                       │
│                                                          │
│   ┌──────────────┐     pulls image     ┌─────────────┐  │
│   │ Hosted Agent  │◄────────────────────│     ACR     │  │
│   │ (container)   │                     └─────────────┘  │
│   │  :8088        │                                      │
│   └──────┬───────┘                                      │
│          │ calls                                         │
│          ▼                                               │
│   ┌──────────────┐     ┌──────────────────┐             │
│   │ Azure OpenAI  │     │  Azure AI Search  │             │
│   │ (gpt-4.1)     │     │  (knowledge base) │             │
│   └──────────────┘     └──────────────────┘             │
└─────────────────────────────────────────────────────────┘
```

## Dependencies

| Package | Purpose |
|---|---|
| `azure-ai-agentserver-agentframework` | Hosting adapter (`from_agent_framework()`) |
| `agent-framework-core` | Core Agent Framework (`ChatAgent`) |
| `agent-framework-azure-ai` | Azure AI client integration |
| `agent-framework-azure-ai-search` | Azure AI Search context provider (optional) |
| `azure-ai-projects` | SDK to register agents in Foundry |
| `azure-identity` | Azure authentication |

All packages are in preview — the `--pre` flag is required when installing.

---

## Run Locally (for testing)

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env with your values

# 2. Install dependencies
pip install --pre -r requirements.txt

# 3. Start the agent
python main.py
# Agent starts on http://localhost:8088
```

Test it:
```bash
curl -X POST http://localhost:8088/responses \
  -H "Content-Type: application/json" \
  -d '{"input": "What is the PTO policy?", "stream": false}'
```

> **Note:** Running locally requires Azure CLI authentication (`az login`) since there's no managed identity outside Foundry.

---

## Key Concepts

### The Hosting Adapter

`from_agent_framework()` from `azure-ai-agentserver-agentframework` is the bridge between your Agent Framework code and the Foundry runtime. It:

- Starts a Uvicorn web server on port 8088
- Translates Foundry request/response formats to Agent Framework data structures
- Handles conversation management, streaming, and serialization
- Exports OpenTelemetry traces, metrics, and logs

### Agent Identity & RBAC

- **Before publishing**: the agent runs with the Foundry project's managed identity
- **After publishing**: Foundry provisions a dedicated agent identity — you must grant RBAC roles for any Azure resources the agent accesses (ACR pull, AI Search reader, etc.)

### Can I use LangChain / other frameworks?

This template is specifically for **Microsoft Agent Framework** agents. The hosting adapter (`from_agent_framework()`) only wraps `ChatAgent` from Agent Framework. For LangChain or other frameworks, you'd need a different hosting approach (e.g. custom FastAPI server exposing the same `/responses` endpoint).

---

## References

- [What are hosted agents?](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Foundry samples — hosted agents](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents)
- [Azure Developer CLI ai agent extension](https://aka.ms/azdaiagent/docs)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [Original HR agent source](https://github.com/leyredelacalzada/FoundryIQ-and-Agent-Framework-demo/blob/main/app/backend/agents/hr_agent.py)
- [Deploy Hosted Agents on Microsoft Foundry: Complete Guide](https://medium.com/@arnaud.tincelin/deploy-hosted-agents-on-microsoft-foundry-complete-guide-0de13e4f835f)