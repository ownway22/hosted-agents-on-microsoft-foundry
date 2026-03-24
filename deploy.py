"""將 Hosted Agent 註冊到 Microsoft Foundry。

這個腳本做兩件事：
    1. 連線到你的 Foundry 專案
    2. 告訴 Foundry：用哪個容器映像、給多少 CPU/記憶體、傳哪些環境變數

使用方式：
    az login
    uv run deploy.py
"""

import os

from dotenv import load_dotenv
load_dotenv()

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    ImageBasedHostedAgentDefinition,
    ProtocolVersionRecord,
    AgentProtocol,
)

# ── 環境變數 ──────────────────────────────────────────────────────────────
# 必填：專案端點、容器映像、Search 端點
# 選填：模型名稱（預設 gpt-4.1）、Application Insights 連線字串

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
CONTAINER_IMAGE = os.environ["CONTAINER_IMAGE"]  # 例如 yourregistry.azurecr.io/hosted-agents-on-microsoft-foundry:latest
SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1")
APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")

AGENT_NAME = "hosted-agents-on-microsoft-foundry"


def main():
    # 1. 建立 Foundry 用戶端
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
    )

    # 2. 註冊 Agent 版本 — 告訴 Foundry 映像和執行規格
    agent = client.agents.create_version(
        agent_name=AGENT_NAME,
        description=(
            "HR specialist agent for Zava Corporation. "
            "Answers questions about HR policies, PTO, benefits, and employee handbook."
        ),
        definition=ImageBasedHostedAgentDefinition(
            container_protocol_versions=[
                ProtocolVersionRecord(protocol=AgentProtocol.RESPONSES, version="v1")
            ],
            cpu="1",
            memory="2Gi",
            image=CONTAINER_IMAGE,
            # 這些環境變數會注入到執行中的容器 → main.py 用 os.getenv() 讀取
            environment_variables={
                "AZURE_AI_PROJECT_ENDPOINT": PROJECT_ENDPOINT,
                "AZURE_SEARCH_ENDPOINT": SEARCH_ENDPOINT,
                "MODEL_DEPLOYMENT_NAME": MODEL_DEPLOYMENT_NAME,
                "APPLICATIONINSIGHTS_CONNECTION_STRING": APPLICATIONINSIGHTS_CONNECTION_STRING,
            },
        ),
    )

    print(f"Agent created: {agent.name} (id: {agent.id}, version: {agent.version})")


if __name__ == "__main__":
    main()
