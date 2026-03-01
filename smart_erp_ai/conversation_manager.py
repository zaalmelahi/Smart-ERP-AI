# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
ConversationManager - Uses frappe_assistant_core (FAC) for prompts and tools.

All prompts come from FAC Prompt Templates.
All tools come from FAC Tool Registry (create_document, get_document, etc.)
Tool execution is delegated to FAC execute_tool.
"""

import frappe
from frappe import _
import json

from smart_erp_ai.smart_erp_ai.doctype.smart_erp_ai_conversation.smart_erp_ai_conversation import (
	get_or_create_conversation,
)
from smart_erp_ai.employee_service import EmployeeService
from smart_erp_ai.fac_chat_bridge import (
	get_fac_system_prompt,
	get_fac_tools_for_llm,
	process_chat_with_fac,
)


class ConversationManager:
	"""Manages conversations - delegates to FAC for prompts and tools."""

	def __init__(self, user: str = None, employee: str = None):
		self.user = user or frappe.session.user
		self.employee_service = EmployeeService(employee=employee, user=self.user)
		self.settings = frappe.get_single("Smart ERP AI Settings")
		self.conversation = None

	def process_message(self, message: str, conversation_id: str = None, attachments: list = None) -> dict:
		"""Process a user message using FAC prompts and tools."""
		if conversation_id:
			try:
				self.conversation = frappe.get_doc("Smart ERP AI Conversation", conversation_id)
			except frappe.DoesNotExistError:
				self.conversation = get_or_create_conversation(
					employee=self.employee_service.employee, user=self.user
				)
		else:
			self.conversation = get_or_create_conversation(
				employee=self.employee_service.employee, user=self.user
			)

		# Attachments: persist and include in message
		existing_attachments = []
		if self.conversation.pending_attachments:
			try:
				existing_attachments = json.loads(self.conversation.pending_attachments)
				if not isinstance(existing_attachments, list):
					existing_attachments = []
			except (json.JSONDecodeError, TypeError):
				existing_attachments = []

		new_attachments = attachments or []
		pending = existing_attachments + new_attachments
		if new_attachments:
			self.conversation.pending_attachments = json.dumps(pending)
			self.conversation.save(ignore_permissions=True)
			frappe.db.commit()

		full_message = message
		if new_attachments:
			names = [a.get("file_name", "file") for a in new_attachments]
			info = ", ".join(names)
			full_message = f"{message}\n[Attached: {info}]" if message else f"[Attached: {info}]"

		self.conversation.add_message(role="user", content=full_message)

		# FAC-based flow: prompt + tools from FAC, execute via FAC
		language = getattr(self.settings, "language", "ar") or "ar"
		system_prompt = get_fac_system_prompt(language)
		tools = get_fac_tools_for_llm(user=self.user)
		messages = self.conversation.get_messages_for_llm()

		try:
			result = process_chat_with_fac(
				messages=messages,
				system_prompt=system_prompt,
				tools=tools,
			)
			final_message = result.get("message", "")
		except Exception as e:
			frappe.log_error(f"FAC chat error: {e!s}", "Smart ERP AI")
			final_message = _("حدث خطأ. يرجى المحاولة مرة أخرى أو التواصل مع الموارد البشرية.")

		self.conversation.add_message(role="assistant", content=final_message)

		return {
			"response": final_message,
			"conversation_id": self.conversation.name,
			"action": "none",
			"intent": "general",
			"entities": {},
			"confidence": 0.9,
			"action_result": None,
		}

	def get_welcome_message(self) -> str:
		"""Get the welcome message for a new conversation."""
		if self.settings.welcome_message:
			return self.settings.welcome_message
		return _(
			"Hello! I'm your ERP Assistant. I can help with leave requests, expense claims, "
			"employee management, and more. How can I help you today?"
		)

	def end_conversation(self, conversation_id: str = None) -> bool:
		"""End/resolve a conversation."""
		try:
			if conversation_id:
				conv = frappe.get_doc("Smart ERP AI Conversation", conversation_id)
			elif self.conversation:
				conv = self.conversation
			else:
				return False
			conv.mark_resolved()
			return True
		except Exception:
			return False

	def get_conversation_history(self, conversation_id: str = None, limit: int = 50) -> list:
		"""Get conversation history."""
		if conversation_id:
			conv = frappe.get_doc("Smart ERP AI Conversation", conversation_id)
		elif self.conversation:
			conv = self.conversation
		else:
			conv = get_or_create_conversation(employee=self.employee_service.employee, user=self.user)

		messages = []
		for msg in conv.messages[-limit:]:
			messages.append({
				"role": msg.role,
				"content": msg.content,
				"timestamp": str(msg.timestamp) if msg.timestamp else None,
			})
		return messages
