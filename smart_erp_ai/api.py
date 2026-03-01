# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from smart_erp_ai.conversation_manager import ConversationManager
from smart_erp_ai.smart_erp_ai.doctype.smart_erp_ai_settings.smart_erp_ai_settings import is_enabled


@frappe.whitelist()
def send_message(message: str, conversation_id: str = None, attachments: str = None) -> dict:
	"""
	Send a message to the Smart ERP AI Assistant

	Args:
	        message: The user's message
	        conversation_id: Optional existing conversation ID
	        attachments: JSON string of uploaded file attachments

	Returns:
	        dict with response, conversation_id, action, etc.
	"""
	if not is_enabled():
		return {"error": True, "message": _("Smart ERP AI is not enabled")}

	# Parse attachments
	parsed_attachments = []
	if attachments:
		import json
		try:
			parsed_attachments = json.loads(attachments)
		except json.JSONDecodeError:
			pass

	# Allow empty message if there are attachments
	if (not message or not message.strip()) and not parsed_attachments:
		return {"error": True, "message": _("Message cannot be empty")}

	try:
		manager = ConversationManager()
		result = manager.process_message(
			message=message.strip() if message else "",
			conversation_id=conversation_id,
			attachments=parsed_attachments
		)

		return {
			"error": False,
			"response": result["response"],
			"conversation_id": result["conversation_id"],
			"action": result.get("action", "none"),
			"intent": result.get("intent"),
			"entities": result.get("entities", {}),
			"action_result": result.get("action_result"),
		}
	except Exception as e:
		frappe.log_error(f"Smart ERP AI send_message error: {e!s}", "Smart ERP AI Error")
		return {"error": True, "message": _("An error occurred. Please try again.")}


@frappe.whitelist()
def get_conversation_history(conversation_id: str = None, limit: int = 50) -> dict:
	"""
	Get conversation history

	Args:
	        conversation_id: Optional conversation ID
	        limit: Maximum number of messages to return

	Returns:
	        dict with messages list
	"""
	if not is_enabled():
		return {"error": True, "message": _("Smart ERP AI is not enabled")}

	try:
		manager = ConversationManager()
		messages = manager.get_conversation_history(conversation_id=conversation_id, limit=limit)

		return {"error": False, "messages": messages, "conversation_id": conversation_id}
	except Exception as e:
		frappe.log_error(f"Smart ERP AI get_history error: {e!s}", "Smart ERP AI Error")
		return {"error": True, "message": _("Failed to load conversation history")}


@frappe.whitelist()
def get_welcome_message() -> dict:
	"""
	Get the welcome message for starting a new conversation

	Returns:
	        dict with welcome message and assistant status
	"""
	if not is_enabled():
		return {"error": True, "enabled": False, "message": _("Smart ERP AI is not enabled")}

	try:
		manager = ConversationManager()
		welcome = manager.get_welcome_message()

		return {"error": False, "enabled": True, "message": welcome}
	except Exception as e:
		frappe.log_error(f"Smart ERP AI get_welcome error: {e!s}", "Smart ERP AI Error")
		return {"error": True, "message": _("Failed to initialize Smart ERP AI")}


@frappe.whitelist()
def end_conversation(conversation_id: str) -> dict:
	"""
	End/resolve a conversation

	Args:
	        conversation_id: The conversation to end

	Returns:
	        dict with success status
	"""
	if not conversation_id:
		return {"error": True, "message": _("Conversation ID is required")}

	try:
		manager = ConversationManager()
		success = manager.end_conversation(conversation_id)

		if success:
			return {"error": False, "message": _("Conversation ended")}
		else:
			return {"error": True, "message": _("Failed to end conversation")}
	except Exception as e:
		frappe.log_error(f"Smart ERP AI end_conversation error: {e!s}", "Smart ERP AI Error")
		return {"error": True, "message": _("Failed to end conversation")}


@frappe.whitelist()
def start_new_conversation() -> dict:
	"""
	Start a new conversation, ending any active one

	Returns:
	        dict with new conversation ID and welcome message
	"""
	if not is_enabled():
		return {"error": True, "message": _("Smart ERP AI is not enabled")}

	try:
		# End any existing active conversation
		existing = frappe.db.get_value(
			"Smart ERP AI Conversation",
			{"user": frappe.session.user, "status": "Active"},
			"name",
		)

		if existing:
			conv = frappe.get_doc("Smart ERP AI Conversation", existing)
			conv.mark_resolved(outcome="Abandoned")

		# Create new conversation
		manager = ConversationManager()
		manager.conversation = None  # Force new conversation
		welcome = manager.get_welcome_message()

		from smart_erp_ai.smart_erp_ai.doctype.smart_erp_ai_conversation.smart_erp_ai_conversation import (
			get_or_create_conversation,
		)
		from smart_erp_ai.employee_service import EmployeeService

		emp_service = EmployeeService()
		conv = get_or_create_conversation(employee=emp_service.employee, user=frappe.session.user)

		return {
			"error": False,
			"conversation_id": conv.name,
			"message": welcome,
		}
	except Exception as e:
		frappe.log_error(f"Smart ERP AI start_new error: {e!s}", "Smart ERP AI Error")
		return {"error": True, "message": _("Failed to start new conversation")}


@frappe.whitelist()
def get_employee_context() -> dict:
	"""
	Get current employee context (for debugging/display)

	Returns:
	        dict with employee information
	"""
	if not is_enabled():
		return {"error": True, "message": _("Smart ERP AI is not enabled")}

	try:
		from smart_erp_ai.employee_service import EmployeeService

		service = EmployeeService()
		context = service.get_context()

		return {"error": False, "context": context}
	except Exception as e:
		frappe.log_error(f"Smart ERP AI get_context error: {e!s}", "Smart ERP AI Error")
		return {"error": True, "message": _("Failed to get employee context")}


@frappe.whitelist()
def confirm_action(conversation_id: str, action_type: str, entities: dict | str) -> dict:
	"""
	Confirm and execute a pending action

	Args:
	        conversation_id: The conversation ID
	        action_type: Type of action (leave_request, expense_claim, etc.)
	        entities: Entity data for the action

	Returns:
	        dict with result of the action
	"""
	if not is_enabled():
		return {"error": True, "message": _("Smart ERP AI is not enabled")}

	if not conversation_id:
		return {"error": True, "message": _("Conversation ID is required")}

	# Parse entities if string
	if isinstance(entities, str):
		import json

		try:
			entities = json.loads(entities)
		except json.JSONDecodeError:
			return {"error": True, "message": _("Invalid entities format")}

	try:
		manager = ConversationManager()
		manager.conversation = frappe.get_doc("Smart ERP AI Conversation", conversation_id)

		result = manager._submit_request(action_type, entities)

		return {"error": result.get("type") == "error", "result": result}
	except Exception as e:
		frappe.log_error(f"Smart ERP AI confirm_action error: {e!s}", "Smart ERP AI Error")
		return {"error": True, "message": _("Failed to execute action")}


@frappe.whitelist(allow_guest=True)
def check_status() -> dict:
	"""
	Check if Smart ERP AI is enabled and properly configured

	Returns:
	        dict with status information
	"""
	try:
		settings = frappe.get_single("Smart ERP AI Settings")

		return {
			"enabled": settings.enabled,
			"provider": settings.ai_provider if settings.enabled else None,
			"has_api_key": bool(settings.api_key) if settings.enabled else False,
			"auto_approve": settings.auto_approve_enabled if settings.enabled else False,
		}
	except Exception as e:
		return {"enabled": False, "error": str(e)}
