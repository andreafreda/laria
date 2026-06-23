"""LARIA core — provider-agnostic agentic engine, modules and storage.

The core runs standalone (no Home Assistant). Configuration comes from the
environment (see ``laria.config``); LLM access goes through the provider
abstraction in ``laria.llm`` so the engine is not tied to any single vendor.
"""

__version__ = "0.1.0"
