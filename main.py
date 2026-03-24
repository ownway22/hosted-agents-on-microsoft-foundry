"""Hosted Agent 進入點 — 容器化你的 Agent 並部署至 Microsoft Foundry。

這個檔案做三件事：
    1. 讀取環境變數（Foundry 專案端點、模型名稱等）
    2. 用你的邏輯建立 ChatAgent
    3. 透過 Hosting Adapter 啟動 HTTP 伺服器，讓 Foundry 能收發訊息

換成你自己的 Agent 只要改三個地方：
    - HR_INSTRUCTIONS → 你的 System Prompt
    - AzureAISearchContextProvider → 你的 Context Provider（不需要就留空 []）
    - ChatAgent 的 name 和 id

注意事項：
    - 必須用 ChatAgent（不是 Agent）— Hosting Adapter 只接受這個類別
    - 必須用同步的 DefaultAzureCredential — Adapter 內部自己處理非同步
    - 最後一行 from_agent_framework(agent).run() 不要動 — 那是啟動伺服器的
"""

import os

from dotenv import load_dotenv
load_dotenv()

# ── 匯入 ──────────────────────────────────────────────────────────────────

from azure.identity import DefaultAzureCredential
from agent_framework import ChatAgent
from agent_framework.azure import AzureAIAgentClient, AzureAISearchContextProvider
from azure.ai.agentserver.agentframework import from_agent_framework

# OpenTelemetry（選用 — 不需要追蹤時整段移除即可）
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# ── 環境變數 ──────────────────────────────────────────────────────────────
# 部署時由 deploy.py 設定；本機測試時從 .env 讀取

PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
MODEL = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1")
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

# ── OpenTelemetry 初始化（選用）────────────────────────────────────────────

if APPLICATIONINSIGHTS_CONNECTION_STRING:
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

    provider = TracerProvider()
    provider.add_span_processor(
        SimpleSpanProcessor(
            AzureMonitorTraceExporter(connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING)
        )
    )
    trace.set_tracer_provider(provider)

# ── 認證 ──────────────────────────────────────────────────────────────────

_credential = DefaultAzureCredential()

# ── Agent 邏輯（這裡替換成你的）──────────────────────────────────────────
# 原始版本可參考 original/hr_agent.py

HR_INSTRUCTIONS = """You are an HR Specialist Agent for Zava Corporation.
Answer questions about HR policies, PTO, benefits, and employee handbook using the knowledge base.
Be specific and cite sources when possible."""


def main():
    # 1. 建立 AI 用戶端 — 連接 Foundry 專案和模型
    client = AzureAIAgentClient(
        project_endpoint=PROJECT_ENDPOINT,
        model_deployment_name=MODEL,
        credential=_credential,
    )

    # 2. 建立 Context Provider（選用 — 不需要知識庫就跳過）
    # TODO: 在 AI Search 建好 kb1-hr 索引後取消註解
    # kb_context = AzureAISearchContextProvider(
    #     endpoint=SEARCH_ENDPOINT,
    #     knowledge_base_name="kb1-hr",
    #     credential=_credential,
    #     mode="agentic",
    #     knowledge_base_output_mode="answer_synthesis",
    # )

    # 3. 組裝 ChatAgent
    agent = ChatAgent(
        client,
        name="hr-agent",
        id="hr-agent",
        instructions=HR_INSTRUCTIONS,
        context_providers=[],  # TODO: 索引就緒後改為 [kb_context]
    )

    # 4. 啟動 HTTP 伺服器（這行不要動）
    #    POST /responses — 接收訊息、回傳 Agent 回應
    #    GET  /readiness — 健康檢查
    from_agent_framework(agent).run()


if __name__ == "__main__":
    main()
