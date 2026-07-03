import asyncio
import json
import os
from typing import Any

from uagents import Model
from uagents.query import send_sync_message

TECHNICAL_ANALYSIS_AGENT_ADDRESS = os.environ.get(
    "TECHNICAL_ANALYSIS_AGENT_ADDRESS",
    "agent1q085746wlr3u2uh4fmwqplude8e0w6fhrmqgsnlp49weawef3ahlutypvu6",
)
TAVILY_SEARCH_AGENT_ADDRESS = os.environ.get(
    "TAVILY_SEARCH_AGENT_ADDRESS",
    "agent1qt5uffgp0l3h9mqed8zh8vy5vs374jl2f8y0mjjvqm44axqseejqzmzx9v8",
)


class WebSearchRequest(Model):
    query: str


class TechAnalysisRequest(Model):
    ticker: str


def _truncate_text(value: Any, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _format_tavily_results(response: str, max_results: int = 5) -> str:
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        return response

    if not isinstance(data, dict):
        return response

    results = data.get("results")
    if not isinstance(results, list):
        return response

    formatted = []
    for result in results[:max_results]:
        if not isinstance(result, dict):
            continue

        title = _truncate_text(result.get("title", ""), 160)
        url = _truncate_text(result.get("url", ""), 240)
        snippet = _truncate_text(result.get("content", ""), 400)

        parts = []
        if title:
            parts.append(f"TITLE: {title}")
        if url:
            parts.append(f"URL: {url}")
        if snippet:
            parts.append(f"SNIPPET: {snippet}")

        if parts:
            formatted.append(f"({' '.join(parts)})")

    return f"({' '.join(formatted)})" if formatted else response

async def _ask_agent(destination: str, request: Model, timeout: int = 60) -> str:
    envelope_or_status = await send_sync_message(
        destination=destination,
        message=request,
        timeout=timeout,
    )
    return str(envelope_or_status)


def technical_analysis(ticker: str, timeout: int = 60) -> str:
    try:
        request = TechAnalysisRequest(ticker=ticker)
        return asyncio.run(
            _ask_agent(TECHNICAL_ANALYSIS_AGENT_ADDRESS, request, int(timeout))
        )
    except Exception as e:
        return f"error: {e}"


def tavily_search(search_query: str, timeout: int = 60) -> str:
    try:
        request = WebSearchRequest(query=search_query)
        response = asyncio.run(
            _ask_agent(TAVILY_SEARCH_AGENT_ADDRESS, request, int(timeout))
        )
        return _format_tavily_results(response)
    except Exception as e:
        return f"error: {e}"
import json
from agentverse import tavily_search
from lib_llm_ext import callProvider

def check_compatibility(json_str: str) -> str:
    """
    Parses a JSON string containing compatibility request details 
    and synthesizes an answer using NVIDIA.
    """
    try:
        # Expected JSON: {"base_lib": "pytorch", "base_ver": "1.0.1", "target_libs": "pandas,scikit-learn"}
        data = json.loads(json_str)
        base_lib = data.get("base_lib")
        base_ver = data.get("base_ver")
        target_libs = data.get("target_libs")
    except json.JSONDecodeError:
        return "Error: Invalid JSON format. Please use: {\"base_lib\": \"...\", \"base_ver\": \"...\", \"target_libs\": \"...\"}"

    # Search for compatibility matrix
    query = f"compatibility matrix for {target_libs} with {base_lib} version {base_ver}"
    search_results = tavily_search(query)
    
    prompt = f"""
    You are a technical expert. Based on these search results, determine the compatible versions for {target_libs} when using {base_lib} {base_ver}.
    
    Search Results:
    {search_results}
    
    Format the output as a clear table. If specific versions are unknown, state that clearly.
    """
    
    # Use your registered NVIDIA provider
    return callProvider("NVIDIA", prompt)