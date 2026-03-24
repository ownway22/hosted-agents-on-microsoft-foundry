"""將 HR Hosted Agent 部署至 Microsoft Foundry — 企業版。

與第一部分相同。基礎設施（VNET、CMK、MI）由 Bicep 處理。
此腳本僅負責在 Foundry 中註冊容器映像。

使用方式：
    az login
    python deploy.py
"""

import os
from dotenv import load_dotenv
load_dotenv()

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    ImageBasedHostedAgentDefinition,
    ProtocolVersionRecord,
    AgentProtocol,
)
from azure.identity import DefaultAzureCredential

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
CONTAINER_IMAGE = os.environ["CONTAINER_IMAGE"]  # 例如 yourregistry.azurecr.io/hosted-agents-on-microsoft-foundry:latest
SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1")

AGENT_NAME = "hosted-agents-on-microsoft-foundry"
APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")


def main():
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
    )

    agent = client.agents.create_version(
        agent_name=AGENT_NAME,
        description=(
            "HR specialist agent for Zava Corporation (Enterprise). "
            "Answers questions about HR policies, PTO, benefits, and employee handbook. "
            "Deployed with CMK encryption, managed identity auth, and private endpoints."
        ),
        definition=ImageBasedHostedAgentDefinition(
            container_protocol_versions=[
                ProtocolVersionRecord(protocol=AgentProtocol.RESPONSES, version="v1")
            ],
            cpu="1",
            memory="2Gi",
            image=CONTAINER_IMAGE,
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
