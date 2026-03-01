# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SmartERPAISettings(Document):
	def validate(self):
		if self.enabled and not self.api_key:
			frappe.throw("API Key is required when Smart ERP AI is enabled")

		if self.temperature < 0 or self.temperature > 1:
			frappe.throw("Temperature must be between 0 and 1")

		if self.max_tokens < 100 or self.max_tokens > 8000:
			frappe.throw("Max Tokens must be between 100 and 8000")

	@frappe.whitelist()
	def test_connection(self):
		"""Test the LLM API connection"""
		from smart_erp_ai.llm import get_llm_client

		try:
			client = get_llm_client()
			response = client.chat("Hello, this is a test message. Please respond with 'Connection successful!'")
			return {"status": "success", "message": response}
		except Exception as e:
			return {"status": "error", "message": str(e)}


def get_settings():
	"""Get Smart ERP AI Settings"""
	return frappe.get_single("Smart ERP AI Settings")


def is_enabled():
	"""Check if Smart ERP AI is enabled"""
	try:
		settings = get_settings()
		return settings.enabled
	except Exception:
		return False
