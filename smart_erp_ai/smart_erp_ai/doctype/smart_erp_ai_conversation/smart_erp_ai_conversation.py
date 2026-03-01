# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class SmartERPAIConversation(Document):
	def before_insert(self):
		if not self.started_at:
			self.started_at = now_datetime()
		if not self.user:
			self.user = frappe.session.user

	def add_message(self, role, content, intent=None, action=None, entities=None):
		"""Add a message to the conversation"""
		self.append(
			"messages",
			{
				"role": role,
				"content": content,
				"timestamp": now_datetime(),
				"intent_detected": intent,
				"action_taken": action,
				"entities_extracted": frappe.as_json(entities) if entities else None,
			},
		)
		self.save(ignore_permissions=True)

	def add_created_document(self, doctype, docname, status, decision, reasoning):
		"""Track a document created by the assistant"""
		self.append(
			"created_documents",
			{
				"reference_doctype": doctype,
				"reference_name": docname,
				"status": status,
				"ai_decision": decision,
				"ai_reasoning": reasoning,
			},
		)
		self.save(ignore_permissions=True)

	def mark_resolved(self, outcome="Completed"):
		"""Mark conversation as resolved"""
		self.status = "Resolved"
		self.outcome = outcome
		self.ended_at = now_datetime()
		self.save(ignore_permissions=True)

	def mark_escalated(self):
		"""Mark conversation as escalated"""
		self.status = "Escalated"
		self.outcome = "Escalated"
		self.save(ignore_permissions=True)

	def get_messages_for_llm(self):
		"""Get messages in format suitable for LLM API"""
		messages = []
		for msg in self.messages:
			messages.append({"role": msg.role, "content": msg.content})
		return messages


def get_or_create_conversation(employee=None, user=None):
	"""Get active conversation or create new one"""
	user = user or frappe.session.user

	if not employee:
		employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

	existing = frappe.db.get_value(
		"Smart ERP AI Conversation",
		{"user": user, "status": "Active"},
		"name",
	)

	if existing:
		return frappe.get_doc("Smart ERP AI Conversation", existing)

	conv = frappe.new_doc("Smart ERP AI Conversation")
	conv.user = user
	conv.employee = employee
	conv.status = "Active"
	conv.insert(ignore_permissions=True)

	return conv
