# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
OpenRouter integration for Smart ERP AI.

OpenRouter provides unified access to multiple LLMs (Claude, GPT-4, Llama, etc.)
through a single API: https://openrouter.ai/docs
Model format: provider/model-name (e.g. anthropic/claude-3.5-sonnet, openai/gpt-4)
"""

import frappe
import requests

from smart_erp_ai.llm.base import BaseLLM


class OpenRouterLLM(BaseLLM):
	"""OpenRouter API integration for Smart ERP AI - unified access to multiple LLMs"""

	API_URL = "https://openrouter.ai/api/v1/chat/completions"

	def chat(self, messages: list, system_prompt: str = None) -> dict:
		"""
		Send messages to OpenRouter API and get a response.

		Args:
			messages: List of message dicts with 'role' and 'content'
			system_prompt: Optional system prompt

		Returns:
			dict with 'message', 'intent', 'entities', 'action', 'confidence'
		"""
		headers = {
			"Content-Type": "application/json",
			"Authorization": f"Bearer {self.api_key}",
			"HTTP-Referer": frappe.utils.get_url() or "https://smart-erp-ai.local",
		}

		formatted_messages = []

		if system_prompt:
			formatted_messages.append({"role": "system", "content": system_prompt})

		for msg in messages:
			role = msg.get("role", "user")
			if role not in ["system", "user", "assistant"]:
				role = "user"
			formatted_messages.append({"role": role, "content": msg.get("content", "")})

		payload = {
			"model": self.model,
			"max_tokens": self.max_tokens,
			"temperature": self.temperature,
			"messages": formatted_messages,
		}

		try:
			response = requests.post(self.API_URL, headers=headers, json=payload, timeout=60)
			response.raise_for_status()

			data = response.json()

			choices = data.get("choices", [])
			if choices and len(choices) > 0:
				response_text = choices[0].get("message", {}).get("content", "")
			else:
				response_text = "I apologize, but I couldn't generate a response. Please try again."

			return self.parse_response(response_text)

		except requests.exceptions.Timeout:
			frappe.log_error("OpenRouter API timeout", "Smart ERP AI Error")
			return {
				"message": "I'm taking longer than expected to respond. Please try again in a moment.",
				"intent": "error",
				"entities": {},
				"action": "none",
				"confidence": 0,
			}
		except requests.exceptions.RequestException as e:
			frappe.log_error(f"OpenRouter API error: {e!s}", "Smart ERP AI Error")
			return {
				"message": "I'm having trouble connecting right now. Please try again later.",
				"intent": "error",
				"entities": {},
				"action": "none",
				"confidence": 0,
			}
		except Exception as e:
			frappe.log_error(f"Unexpected error in OpenRouter integration: {e!s}", "Smart ERP AI Error")
			return {
				"message": "Something went wrong. Please try again or contact support.",
				"intent": "error",
				"entities": {},
				"action": "none",
				"confidence": 0,
			}

	def chat_with_tools(self, messages: list, tools: list) -> dict:
		"""Chat with tool/function calling (OpenAI-compatible API)."""
		headers = {
			"Content-Type": "application/json",
			"Authorization": f"Bearer {self.api_key}",
			"HTTP-Referer": frappe.utils.get_url() or "https://smart-erp-ai.local",
		}
		payload = {
			"model": self.model,
			"max_tokens": self.max_tokens,
			"temperature": self.temperature,
			"messages": messages,
			"tools": tools if tools else None,
		}
		if tools:
			payload["tool_choice"] = "auto"
		try:
			response = requests.post(self.API_URL, headers=headers, json=payload, timeout=90)
			response.raise_for_status()
			data = response.json()
			choices = data.get("choices", [])
			if not choices:
				return {"message": "", "tool_calls": []}
			msg = choices[0].get("message", {})
			content = msg.get("content") or ""
			tool_calls = msg.get("tool_calls", [])
			normalized = []
			for tc in tool_calls:
				fn = tc.get("function", {})
				normalized.append({
					"id": tc.get("id", ""),
					"tool_call_id": tc.get("id", ""),
					"function": {"name": fn.get("name", ""), "arguments": fn.get("arguments", "{}")},
				})
			return {"message": content, "tool_calls": normalized}
		except Exception as e:
			frappe.log_error(f"OpenRouter chat_with_tools error: {e!s}", "Smart ERP AI")
			return {"message": str(e), "tool_calls": []}
