# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import requests

from smart_erp_ai.llm.base import BaseLLM


class ClaudeLLM(BaseLLM):
	"""Claude API integration for Smart ERP AI"""

	API_URL = "https://api.anthropic.com/v1/messages"
	API_VERSION = "2023-06-01"

	def chat(self, messages: list, system_prompt: str = None) -> dict:
		"""
		Send messages to Claude API and get a response.

		Args:
		        messages: List of message dicts with 'role' and 'content'
		        system_prompt: Optional system prompt

		Returns:
		        dict with 'message', 'intent', 'entities', 'action', 'confidence'
		"""
		headers = {
			"Content-Type": "application/json",
			"x-api-key": self.api_key,
			"anthropic-version": self.API_VERSION,
		}

		# Format messages for Claude API
		formatted_messages = []
		for msg in messages:
			role = msg.get("role", "user")
			# Claude only accepts 'user' and 'assistant' roles in messages
			if role == "system":
				continue
			if role not in ["user", "assistant"]:
				role = "user"
			formatted_messages.append({"role": role, "content": msg.get("content", "")})

		payload = {
			"model": self.model,
			"max_tokens": self.max_tokens,
			"messages": formatted_messages,
		}

		if system_prompt:
			payload["system"] = system_prompt

		try:
			response = requests.post(self.API_URL, headers=headers, json=payload, timeout=30)
			response.raise_for_status()

			data = response.json()

			# Extract text from Claude response
			content = data.get("content", [])
			if content and len(content) > 0:
				response_text = content[0].get("text", "")
			else:
				response_text = "I apologize, but I couldn't generate a response. Please try again."

			# Parse the response to extract structured data
			return self.parse_response(response_text)

		except requests.exceptions.Timeout:
			frappe.log_error("Claude API timeout", "HR Assistant Error")
			return {
				"message": "I'm taking longer than expected to respond. Please try again in a moment.",
				"intent": "error",
				"entities": {},
				"action": "none",
				"confidence": 0,
			}
		except requests.exceptions.RequestException as e:
			frappe.log_error(f"Claude API error: {e!s}", "HR Assistant Error")
			return {
				"message": "I'm having trouble connecting right now. Please try again later.",
				"intent": "error",
				"entities": {},
				"action": "none",
				"confidence": 0,
			}
		except Exception as e:
			frappe.log_error(f"Unexpected error in Claude integration: {e!s}", "HR Assistant Error")
			return {
				"message": "Something went wrong. Please try again or contact HR directly.",
				"intent": "error",
				"entities": {},
				"action": "none",
				"confidence": 0,
			}
