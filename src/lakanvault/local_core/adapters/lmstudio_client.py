"""Backward-compatible re-export — use local_llm_client.LocalLLMClient instead."""
from lakanvault.local_core.adapters.local_llm_client import LocalLLMClient as LMStudioClient

__all__ = ["LMStudioClient"]
