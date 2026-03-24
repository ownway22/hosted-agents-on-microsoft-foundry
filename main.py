"""Hosted agent entry point — containerizes an Agent Framework agent for Microsoft Foundry.

This file is the ONLY file that matters for containerization. It takes your agent logic
and wraps it with the hosting adapter so Foundry can run it as a managed service.

HOW TO ADAPT THIS TO YOUR OWN AGENT:
    1. Replace the instructions (HR_INSTRUCTIONS) with your own agent's instructions.
    2. Replace/remove the context providers (AzureAISearchContextProvider) with whatever
       your agent needs — or use none if your agent doesn't need grounding data.
    3. Update the agent name and id to match your agent.
    4. The last line (from_agent_framework(agent).run()) NEVER changes — it starts
       the HTTP server on port 8088 that Foundry communicates with.

REQUIRED:
    - ChatAgent (not Agent) — the hosting adapter requires this class.
    - from_agent_framework() — wraps your ChatAgent into a Uvicorn HTTP server.
    - Sync DefaultAzureCredential (not async) — the adapter manages the async lifecycle.
    - Environment variables for configuration (set in deploy.py or agent.yaml, NOT .env).
"""

import os

from dotenv import load_dotenv
load_dotenv()

# --- OpenTelemetry (OPTIONAL — remove if you don't need tracing) ---
# Instruments Azure SDK calls and exports traces to Azure Monitor / Application Insights.
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

# --- Azure identity (REQUIRED) ---
# Use the SYNC credential. The hosting adapter handles async internally.
from azure.identity import DefaultAzureCredential

# --- Agent Framework (REQUIRED) ---
# ChatAgent is the class compatible with the hosting adapter.
from agent_framework import ChatAgent

# --- Azure AI integrations (OPTIONAL — depends on your agent) ---
# AzureAIAgentClient: connects your agent to a Foundry project + model deployment.
# AzureAISearchContextProvider: gives your agent access to an Azure AI Search knowledge base.
# Remove or replace these if your agent uses different tools/providers.
from agent_framework.azure import AzureAIAgentClient, AzureAISearchContextProvider

# --- Hosting adapter (REQUIRED — this is what makes containerization work) ---
# from_agent_framework() wraps your ChatAgent into an HTTP server on port 8088.
# It exposes POST /responses (OpenAI Responses API) and GET /readiness (health check).
from azure.ai.agentserver.agentframework import from_agent_framework

# ---------------------------------------------------------------------------
# Configuration — these come from environment variables set in deploy.py.
# When running locally, set them in your shell or a .env file.
# ---------------------------------------------------------------------------
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
MODEL = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4.1")
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")

_credential = DefaultAzureCredential()

# ---------------------------------------------------------------------------
# YOUR AGENT LOGIC BELOW — replace this with your own agent's setup.
# See original/hr_agent.py for the standalone version this was adapted from.
# ---------------------------------------------------------------------------

HR_INSTRUCTIONS = """You are an HR Specialist Agent for Zava Corporation.
Answer questions about HR policies, PTO, benefits, and employee handbook using the knowledge base.
Be specific and cite sources when possible."""


def main():
    # Step 1: Create the AI client (connects to your Foundry project + model)
    client = AzureAIAgentClient(
        project_endpoint=PROJECT_ENDPOINT,
        model_deployment_name=MODEL,
        credential=_credential,
    )

    # Step 2: Create context providers (optional — remove if your agent doesn't need them)
    # This example uses Azure AI Search to ground the agent with an HR knowledge base.
    # TODO: Uncomment when kb1-hr index is created in AI Search
    # kb_context = AzureAISearchContextProvider(
    #     endpoint=SEARCH_ENDPOINT,
    #     knowledge_base_name="kb1-hr",
    #     credential=_credential,
    #     mode="agentic",
    #     knowledge_base_output_mode="answer_synthesis",
    # )

    # Step 3: Build the ChatAgent
    # - name/id: identifier for this agent
    # - instructions: your agent's system prompt
    # - context_providers: list of knowledge sources (can be empty [])
    agent = ChatAgent(
        client,
        name="hr-agent",
        id="hr-agent",
        instructions=HR_INSTRUCTIONS,
        context_providers=[],  # TODO: Add [kb_context] when AI Search index is ready
    )

    # Step 4: Start the hosted agent server (NEVER CHANGES)
    # This starts a Uvicorn server on port 8088 with:
    #   POST /responses  — receives user messages, returns agent responses
    #   GET  /readiness  — health check for Foundry
    from_agent_framework(agent).run()


if __name__ == "__main__":
    main()
