# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from abc import ABC, abstractmethod

import frappe
from frappe.utils import today


class BaseLLM(ABC):
	"""Base class for LLM integrations"""

	def __init__(self, api_key: str, model: str, max_tokens: int = 2048, temperature: float = 0.3):
		self.api_key = api_key
		self.model = model
		self.max_tokens = max_tokens
		self.temperature = temperature

	@abstractmethod
	def chat(self, messages: list, system_prompt: str = None) -> dict:
		"""
		Send messages to the LLM and get a response.

		Args:
		        messages: List of message dicts with 'role' and 'content'
		        system_prompt: Optional system prompt to prepend

		Returns:
		        dict with 'message', 'intent', 'entities', 'action', 'confidence'
		"""
		pass

	def chat_with_tools(self, messages: list, tools: list) -> dict:
		"""
		Send messages with tool definitions. If model returns tool_calls, caller executes them.
		Override in subclasses that support tool/function calling.
		Returns: dict with 'message', 'tool_calls' (list of {id, function: {name, arguments}})
		"""
		# Default: ignore tools, use plain chat
		system = ""
		msgs = []
		for m in messages:
			if m.get("role") == "system":
				system = m.get("content", "")
			else:
				msgs.append(m)
		result = self.chat(messages=msgs, system_prompt=system or None)
		return {"message": result.get("message", ""), "tool_calls": []}

	def parse_response(self, response_text: str) -> dict:
		"""Parse LLM response to extract structured data"""
		# Try to extract JSON from response
		try:
			# Look for JSON block in response
			if "```json" in response_text:
				json_start = response_text.index("```json") + 7
				json_end = response_text.index("```", json_start)
				json_str = response_text[json_start:json_end].strip()
			elif "{" in response_text and "}" in response_text:
				# Try to find JSON object
				json_start = response_text.index("{")
				json_end = response_text.rindex("}") + 1
				json_str = response_text[json_start:json_end]
			else:
				# No JSON found, return plain text response
				return {
					"message": response_text,
					"intent": "general",
					"entities": {},
					"action": "none",
					"confidence": 0.5,
				}

			data = json.loads(json_str)
			return {
				"message": data.get("message", response_text),
				"intent": data.get("intent", "general"),
				"entities": data.get("entities", {}),
				"action": data.get("action", "none"),
				"confidence": float(data.get("confidence", 0.5)),
			}
		except (json.JSONDecodeError, ValueError) as e:
			frappe.log_error(f"Failed to parse LLM response: {e}", "Smart ERP AI LLM Parse Error")
			return {
				"message": response_text,
				"intent": "general",
				"entities": {},
				"action": "none",
				"confidence": 0.5,
			}

	def get_system_prompt(self, employee_context: dict, company_policies: str, base_prompt: str, language: str = "ar") -> str:
		"""
		Legacy system prompt builder.
		Now primarily handled by FAC Prompt Templates in ConversationManager.
		"""
		return f"{base_prompt}\n\n[Warning: Hardcoded prompt removed. Please ensure FAC Prompt Templates are configured.]"

	def _format_leave_balances(self, balances: list) -> str:
		"""Format leave balances for prompt"""
		if not balances:
			return "No leave balance information available"

		lines = []
		for b in balances:
			lines.append(f"- {b.get('leave_type', 'Unknown')}: {b.get('balance', 0)} days remaining")
		return "\n".join(lines)

	def _format_leave_balances_arabic(self, balances: list) -> str:
		"""Format leave balances for Arabic prompt"""
		if not balances:
			return "لا توجد معلومات عن رصيد الإجازات"

		lines = []
		for b in balances:
			leave_type = b.get('leave_type', 'غير معروف')
			# Use Frappe's translation system for dynamic translation
			arabic_type = frappe._(leave_type)
			lines.append(f"- {arabic_type}: {b.get('balance', 0)} يوم متبقي")
		return "\n".join(lines)

	def _format_pending_requests(self, requests: list) -> str:
		"""Format pending requests for prompt"""
		if not requests:
			return "No pending requests"

		lines = []
		for r in requests:
			lines.append(f"- {r.get('doctype', 'Request')}: {r.get('name', '')} - {r.get('status', 'Pending')}")
		return "\n".join(lines)

	def _format_pending_requests_arabic(self, requests: list) -> str:
		"""Format pending requests for Arabic prompt"""
		if not requests:
			return "لا توجد طلبات معلقة"

		lines = []
		for r in requests:
			doctype = r.get('doctype', 'طلب')
			# Use Frappe's translation system for dynamic translation
			arabic_doctype = frappe._(doctype)
			status = r.get('status', 'Pending')
			arabic_status = frappe._(status)
			lines.append(f"- {arabic_doctype}: {r.get('name', '')} - {arabic_status}")
		return "\n".join(lines)

	def _format_leave_types_arabic(self, leave_types: list) -> str:
		"""Format leave types from ERPNext for Arabic prompt"""
		if not leave_types:
			return "- لم يتم تحديد أنواع إجازات في النظام"

		# Explicit Arabic translations for common leave types
		leave_type_translations = {
			"Annual Leave": "إجازة سنوية",
			"Sick Leave": "إجازة مرضية",
			"Casual Leave": "إجازة عارضة",
			"Compensatory Off": "إجازة تعويضية",
			"Leave Without Pay": "إجازة بدون راتب",
			"Maternity Leave": "إجازة أمومة",
			"Paternity Leave": "إجازة أبوة",
			"Privilege Leave": "إجازة امتياز",
			"Study Leave": "إجازة دراسية",
		}

		lines = []
		for lt in leave_types:
			name = lt.get('name', '')
			# Use explicit translation, fall back to Frappe translation, then name
			arabic_name = leave_type_translations.get(name, frappe._(name))
			details = []

			# Add max days if specified
			max_days = lt.get('max_continuous_days_allowed')
			if max_days and max_days > 0:
				details.append(f"الحد الأقصى: {max_days} يوم متواصل")

			# Add LWP warning
			if lt.get('is_lwp'):
				details.append("بدون راتب")

			if details:
				lines.append(f"- {arabic_name}: {' | '.join(details)}")
			else:
				lines.append(f"- {arabic_name}")

		return "\n".join(lines)

	def _format_leave_types_english(self, leave_types: list) -> str:
		"""Format leave types from ERPNext for English prompt"""
		if not leave_types:
			return "- No leave types configured in the system"

		lines = []
		for lt in leave_types:
			name = lt.get('name', '')
			details = []

			# Add max days if specified
			max_days = lt.get('max_continuous_days_allowed')
			if max_days and max_days > 0:
				details.append(f"Max: {max_days} consecutive days")

			# Add LWP warning
			if lt.get('is_lwp'):
				details.append("Without Pay")

			if details:
				lines.append(f"- {name}: {' | '.join(details)}")
			else:
				lines.append(f"- {name}")

		return "\n".join(lines)

	def _format_expense_types_arabic(self, expense_types: list) -> str:
		"""Format expense types from ERPNext for Arabic prompt"""
		if not expense_types:
			return "- لم يتم تحديد أنواع مصروفات في النظام"

		# Arabic translations for expense types
		type_translations = {
			"Meals and Entertainment": "وجبات وضيافة",
			"Transportation": "مواصلات",
			"Travel": "سفر",
			"Office Supplies": "مستلزمات مكتبية",
			"Communication": "اتصالات",
			"Training and Education": "تدريب وتعليم",
			"Medical": "طبي",
			"Other": "أخرى",
		}

		lines = []
		for et in expense_types:
			name = et.get('name', '')
			arabic_name = type_translations.get(name, frappe._(name))
			description = et.get('description', '')
			if description:
				lines.append(f"- {arabic_name} ({name}): {description}")
			else:
				lines.append(f"- {arabic_name} ({name})")

		return "\n".join(lines)

	def _format_expense_types_english(self, expense_types: list) -> str:
		"""Format expense types from ERPNext for English prompt"""
		if not expense_types:
			return "- No expense types configured in the system"

		lines = []
		for et in expense_types:
			name = et.get('name', '')
			description = et.get('description', '')
			if description:
				lines.append(f"- {name}: {description}")
			else:
				lines.append(f"- {name}")

		return "\n".join(lines)

	def _format_recent_expenses_arabic(self, expenses: list) -> str:
		"""Format recent expenses for Arabic prompt"""
		if not expenses:
			return "لا توجد مصروفات سابقة"

		lines = []
		for exp in expenses:
			amount = exp.get('amount', 0)
			status = exp.get('status', 'Draft')
			arabic_status = frappe._(status)
			expense_date = exp.get('date', '')
			lines.append(f"- {expense_date}: {amount} ر.س - {arabic_status}")

		return "\n".join(lines)

	def _format_recent_expenses_english(self, expenses: list) -> str:
		"""Format recent expenses for English prompt"""
		if not expenses:
			return "No recent expenses"

		lines = []
		for exp in expenses:
			amount = exp.get('amount', 0)
			status = exp.get('status', 'Draft')
			expense_date = exp.get('date', '')
			lines.append(f"- {expense_date}: {amount} SAR - {status}")

		return "\n".join(lines)
