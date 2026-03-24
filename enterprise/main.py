"""Hosted Agent 進入點 — 與第一部分完全相同。

企業版架構的重點在於：你的應用程式碼完全不需要修改。
所有企業級安全性（CMK、Managed Identity、Private Endpoint）皆在基礎設施層透過
Bicep 處理。Agent 程式碼維持不變。

DefaultAzureCredential() 會在執行時自動取得 Foundry 管理的 Managed Identity。
程式碼中沒有 API 金鑰、沒有連線字串、沒有密鑰。
"""

import os

# --- OpenTelemetry（選用 — 不需要追蹤時可移除）---
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

if APPLICATIONINSIGHTS_CONNECTION_STRING:
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

    provider = TracerProvider()
    provider.add_span_processor(
        SimpleSpanProcessor(
            AzureMonitorTraceExporter(connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING)
        )
    )
    trace.set_tracer_provider(provider)

# --- Azure 身分識別（必要）---
# DefaultAzureCredential 會在執行時取得 Foundry 的 Managed Identity。
# 在企業版架構中，此身分識別擁有所有資源的 RBAC 角色 — 不需要 API 金鑰。
from azure.identity import DefaultAzureCredential

# --- Agent Framework（必要）---
from agent_framework import ChatAgent

# --- Azure AI 整合 ---
from agent_framework.azure import AzureAIAgentClient, AzureAISearchContextProvider

# --- Hosting Adapter（必要）---
from azure.ai.agentserver.agentframework import from_agent_framework

# ---------------------------------------------------------------------------
# 組態 — 來自環境變數（在 deploy.py 或 Foundry 中設定）
# ---------------------------------------------------------------------------
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
MODEL = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1")
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")

_credential = DefaultAzureCredential()

# ---------------------------------------------------------------------------
# Agent 邏輯 — 與第一部分相同
# ---------------------------------------------------------------------------
HR_INSTRUCTIONS = """You are an HR Specialist Agent for Zava Corporation.
Answer questions about HR policies, PTO, benefits, and employee handbook using the knowledge base.
Be specific and cite sources when possible."""


def main():
    client = AzureAIAgentClient(
        project_endpoint=PROJECT_ENDPOINT,
        model_deployment_name=MODEL,
        credential=_credential,
    )

    kb_context = AzureAISearchContextProvider(
        endpoint=SEARCH_ENDPOINT,
        knowledge_base_name="kb1-hr",
        credential=_credential,
        mode="agentic",
        knowledge_base_output_mode="answer_synthesis",
    )

    agent = ChatAgent(
        client,
        name="hr-agent",
        id="hr-agent",
        instructions=HR_INSTRUCTIONS,
        context_providers=[kb_context],
    )

    from_agent_framework(agent).run()


if __name__ == "__main__":
    main()
