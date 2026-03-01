# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe

from smart_erp_ai.llm.base import BaseLLM
from smart_erp_ai.llm.claude import ClaudeLLM
from smart_erp_ai.llm.openai import OpenAILLM
from smart_erp_ai.llm.openrouter import OpenRouterLLM

__all__ = ["BaseLLM", "ClaudeLLM", "OpenAILLM", "OpenRouterLLM", "get_llm_client"]


def get_llm_client() -> BaseLLM:
	"""
	Factory function to get the configured LLM client.

	Returns:
	        BaseLLM: Configured LLM client based on Smart ERP AI Settings
	"""
	settings = frappe.get_single("Smart ERP AI Settings")

	if not settings.enabled:
		frappe.throw("Smart ERP AI is not enabled")

	if not settings.api_key:
		frappe.throw("API Key is not configured for Smart ERP AI")

	provider = settings.ai_provider
	api_key = settings.get_password("api_key")
	model = settings.model_name
	max_tokens = settings.max_tokens or 2048
	temperature = settings.temperature or 0.3

	if provider == "Claude":
		return ClaudeLLM(
			api_key=api_key,
			model=model or "claude-sonnet-4-20250514",
			max_tokens=max_tokens,
			temperature=temperature,
		)
	elif provider == "OpenAI":
		return OpenAILLM(
			api_key=api_key,
			model=model or "gpt-4",
			max_tokens=max_tokens,
			temperature=temperature,
		)
	elif provider == "OpenRouter":
		return OpenRouterLLM(
			api_key=api_key,
			model=model or "anthropic/claude-3.5-sonnet",
			max_tokens=max_tokens,
			temperature=temperature,
		)
	elif provider == "Gemini":
		# TODO: Implement Gemini integration
		frappe.throw("Gemini integration is not yet implemented")
	else:
		frappe.throw(f"Unknown AI provider: {provider}")
