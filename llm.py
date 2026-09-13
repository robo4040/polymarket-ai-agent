"""
Thin LLM wrapper. Supports Anthropic, OpenAI, or any OpenAI-compatible endpoint.
Falls back to a simple heuristic if no key is provided (useful for testing).
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from config import cfg


def chat(messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    """messages = [{"role": "system"|"user"|"assistant", "content": "..."}]"""
    if cfg.anthropic_api_key:
        return _anthropic(messages, temperature)
    if cfg.openai_api_key or cfg.llm_base_url:
        return _openai_compatible(messages, temperature)
    return _heuristic_fallback(messages)


def _anthropic(messages: List[Dict[str, str]], temperature: float) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
        # Convert to Anthropic format
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msgs = [m for m in messages if m["role"] != "system"]
        resp = client.messages.create(
            model=cfg.llm_model,
            max_tokens=1024,
            temperature=temperature,
            system=system,
            messages=user_msgs,
        )
        return resp.content[0].text
    except Exception as e:
        return f"[LLM error] {e}"


def _openai_compatible(messages: List[Dict[str, str]], temperature: float) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=cfg.openai_api_key or "sk-dummy",
            base_url=cfg.llm_base_url or None,
        )
        resp = client.chat.completions.create(
            model=cfg.llm_model,
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[LLM error] {e}"


def _heuristic_fallback(messages: List[Dict[str, str]]) -> str:
    """Very dumb fallback so the agent still runs without keys.
    Stays close to the market price so edge remains small until a real LLM key is added.
    """
    last = messages[-1]["content"] if messages else ""
    if "probability" in last.lower() or "estimate" in last.lower():
        import re
        m = re.search(r"Current YES price:\s*([0-9.]+)", last)
        if m:
            p = float(m.group(1))
            return f"{max(0.05, min(0.95, p + 0.03)):.2f}"
        return "0.50"
    return "No strong edge detected. Skipping."
