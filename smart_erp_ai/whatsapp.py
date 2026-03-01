# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
WhatsApp Integration for Smart ERP AI

This module handles WhatsApp Business API integration, allowing employees
to interact with the Smart ERP AI via WhatsApp.
"""

import hashlib
import hmac
import json
import re

import frappe
import requests
from frappe import _


WHATSAPP_API_URL = "https://graph.facebook.com/v18.0"


def get_whatsapp_settings():
	"""Get WhatsApp configuration from Smart ERP AI Settings"""
	settings = frappe.get_single("Smart ERP AI Settings")

	if not settings.whatsapp_enabled:
		return None

	return {
		"phone_number_id": settings.whatsapp_phone_number_id,
		"business_account_id": settings.whatsapp_business_account_id,
		"access_token": settings.get_password("whatsapp_access_token"),
		"verify_token": settings.whatsapp_verify_token,
		"app_secret": settings.get_password("whatsapp_app_secret"),
	}


def normalize_phone_number(phone: str) -> str:
	"""
	Normalize phone number to E.164 format for matching

	Examples:
	- +966501234567 -> 966501234567
	- 00966501234567 -> 966501234567
	- 0501234567 -> 501234567 (local format)
	"""
	if not phone:
		return ""

	# Remove all non-digit characters
	digits = re.sub(r"\D", "", phone)

	# Remove leading zeros
	digits = digits.lstrip("0")

	# Remove 00 prefix (international format)
	if digits.startswith("00"):
		digits = digits[2:]

	return digits


def get_employee_by_phone(phone: str) -> str | None:
	"""
	Find employee by matching phone number

	Args:
		phone: The sender's phone number from WhatsApp (E.164 format)

	Returns:
		Employee name (ID) or None if not found
	"""
	normalized_phone = normalize_phone_number(phone)

	if not normalized_phone:
		return None

	# Search for employee with matching cell_number
	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "cell_number", "personal_email", "company_email"],
	)

	for emp in employees:
		if emp.cell_number:
			emp_normalized = normalize_phone_number(emp.cell_number)
			# Match if the numbers end with the same digits (at least 9 digits)
			if emp_normalized and (
				emp_normalized == normalized_phone
				or emp_normalized.endswith(normalized_phone[-9:])
				or normalized_phone.endswith(emp_normalized[-9:])
			):
				return emp.name

	return None


def verify_webhook_signature(payload: bytes, signature: str, app_secret: str) -> bool:
	"""
	Verify the webhook signature from Meta

	Args:
		payload: Raw request body bytes
		signature: X-Hub-Signature-256 header value
		app_secret: App secret from Meta dashboard

	Returns:
		True if signature is valid
	"""
	if not signature or not app_secret:
		return False

	# Signature format: sha256=<hash>
	if not signature.startswith("sha256="):
		return False

	expected_signature = signature[7:]  # Remove "sha256=" prefix

	# Calculate HMAC-SHA256
	calculated = hmac.new(
		app_secret.encode("utf-8"), payload, hashlib.sha256
	).hexdigest()

	return hmac.compare_digest(calculated, expected_signature)


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def handle_webhook():
	"""
	Handle incoming WhatsApp webhook requests

	GET: Webhook verification (Meta challenge)
	POST: Incoming messages
	"""
	if frappe.request.method == "GET":
		return verify_webhook()
	else:
		return process_webhook()


def verify_webhook():
	"""
	Handle webhook verification from Meta

	Meta sends a GET request with:
	- hub.mode: "subscribe"
	- hub.challenge: A random string to return
	- hub.verify_token: The token we configured

	Returns the challenge as plain text (required by Meta).
	"""
	from werkzeug.wrappers import Response

	mode = frappe.request.args.get("hub.mode")
	token = frappe.request.args.get("hub.verify_token")
	challenge = frappe.request.args.get("hub.challenge")

	settings = get_whatsapp_settings()

	if not settings:
		frappe.log_error("WhatsApp webhook verification failed: Not enabled", "WhatsApp Error")
		return Response("WhatsApp not enabled", status=403, content_type="text/plain")

	if mode == "subscribe" and token == settings["verify_token"]:
		frappe.log_error("WhatsApp webhook verified successfully", "WhatsApp Info")
		# Return plain text challenge - exactly what Meta expects
		return Response(challenge, status=200, content_type="text/plain")
	else:
		frappe.log_error(
			f"WhatsApp webhook verification failed: mode={mode}, token_match={token == settings['verify_token']}",
			"WhatsApp Error",
		)
		return Response("Verification failed", status=403, content_type="text/plain")


# Alternative webhook endpoint that returns plain text for verification
# Use this URL in Meta: /api/method/smart_erp_ai.whatsapp.webhook_verify
@frappe.whitelist(allow_guest=True, methods=["GET"])
def webhook_verify():
	"""
	Dedicated webhook verification endpoint that returns plain text challenge.
	Use this URL in Meta's webhook configuration.
	"""
	from werkzeug.wrappers import Response

	mode = frappe.request.args.get("hub.mode")
	token = frappe.request.args.get("hub.verify_token")
	challenge = frappe.request.args.get("hub.challenge")

	settings = get_whatsapp_settings()

	if not settings:
		return Response("WhatsApp not enabled", status=403, content_type="text/plain")

	if mode == "subscribe" and token == settings["verify_token"]:
		frappe.log_error("WhatsApp webhook verified successfully", "WhatsApp Info")
		# Return plain text challenge - exactly what Meta expects
		return Response(challenge, status=200, content_type="text/plain")
	else:
		frappe.log_error(
			f"WhatsApp webhook verification failed: mode={mode}",
			"WhatsApp Error",
		)
		return Response("Verification failed", status=403, content_type="text/plain")


def process_webhook():
	"""
	Process incoming WhatsApp message webhook

	Webhook payload structure:
	{
		"object": "whatsapp_business_account",
		"entry": [{
			"id": "BUSINESS_ACCOUNT_ID",
			"changes": [{
				"value": {
					"messaging_product": "whatsapp",
					"metadata": {"phone_number_id": "...", "display_phone_number": "..."},
					"contacts": [{"profile": {"name": "..."}, "wa_id": "..."}],
					"messages": [{
						"from": "SENDER_PHONE",
						"id": "MESSAGE_ID",
						"timestamp": "...",
						"text": {"body": "MESSAGE_TEXT"},
						"type": "text"
					}]
				},
				"field": "messages"
			}]
		}]
	}
	"""
	settings = get_whatsapp_settings()

	if not settings:
		return {"status": "error", "message": "WhatsApp not enabled"}

	# Get raw body for signature verification
	raw_body = frappe.request.get_data()

	# Verify signature (optional but recommended)
	signature = frappe.request.headers.get("X-Hub-Signature-256")
	if settings["app_secret"] and signature:
		if not verify_webhook_signature(raw_body, signature, settings["app_secret"]):
			frappe.log_error("WhatsApp webhook signature verification failed", "WhatsApp Error")
			frappe.throw(_("Invalid signature"), frappe.AuthenticationError)

	try:
		data = json.loads(raw_body)
	except json.JSONDecodeError:
		frappe.log_error("WhatsApp webhook: Invalid JSON payload", "WhatsApp Error")
		return {"status": "error", "message": "Invalid JSON"}

	# Process entries
	if data.get("object") != "whatsapp_business_account":
		return {"status": "ok", "message": "Not a WhatsApp event"}

	for entry in data.get("entry", []):
		for change in entry.get("changes", []):
			if change.get("field") != "messages":
				continue

			value = change.get("value", {})
			messages = value.get("messages", [])

			for message in messages:
				msg_type = message.get("type")
				if msg_type == "text":
					process_text_message(message, value, settings)
				elif msg_type == "image":
					process_image_message(message, value, settings)
				elif msg_type == "document":
					process_document_message(message, value, settings)

	return {"status": "ok"}


def process_text_message(message: dict, value: dict, settings: dict):
	"""
	Process an incoming text message

	Args:
		message: The message object
		value: The full value object from webhook
		settings: WhatsApp settings
	"""
	sender_phone = message.get("from")
	message_id = message.get("id")
	message_text = message.get("text", {}).get("body", "")

	# Get sender name from contacts
	contacts = value.get("contacts", [])
	sender_name = contacts[0].get("profile", {}).get("name", "") if contacts else ""

	frappe.log_error(
		f"WhatsApp message from {sender_phone} ({sender_name}): {message_text[:100]}",
		"WhatsApp Debug",
	)

	# Find employee by phone number
	employee = get_employee_by_phone(sender_phone)

	if not employee:
		# Send "not registered" response
		send_whatsapp_message(
			sender_phone,
			_(
				"عذراً، رقم هاتفك غير مسجل في النظام. يرجى التواصل مع قسم الموارد البشرية.\n\n"
				"Sorry, your phone number is not registered in the system. Please contact HR."
			),
			settings,
		)
		frappe.log_error(
			f"WhatsApp: Unknown phone number {sender_phone}", "WhatsApp Warning"
		)
		return

	# Process ALL messages through the AI (including first message of new conversations)
	# The AI will generate appropriate greeting if it's a new session
	try:
		response, is_new, request_completed = process_smart_erp_ai_message(
			employee=employee,
			phone=sender_phone,
			message=message_text,
		)

		# Send response to their message
		send_whatsapp_message(sender_phone, response, settings)

		# If a request was successfully completed, close the conversation
		# so the next message starts a fresh session
		if request_completed:
			close_whatsapp_conversation(sender_phone)

	except Exception as e:
		frappe.log_error(
			f"WhatsApp message processing error: {e!s}\n\nMessage: {message_text}",
			"WhatsApp Error",
		)
		send_whatsapp_message(
			sender_phone,
			_(
				"عذراً، حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى.\n\n"
				"Sorry, an error occurred while processing your request. Please try again."
			),
			settings,
		)


def process_image_message(message: dict, value: dict, settings: dict):
	"""
	Process an incoming image message (e.g., expense receipt)

	Args:
		message: The message object
		value: The full value object from webhook
		settings: WhatsApp settings
	"""
	sender_phone = message.get("from")
	image_info = message.get("image", {})
	image_id = image_info.get("id")
	caption = image_info.get("caption", "")
	mime_type = image_info.get("mime_type", "image/jpeg")

	# Find employee
	employee = get_employee_by_phone(sender_phone)

	if not employee:
		send_whatsapp_message(
			sender_phone,
			_(
				"عذراً، رقم هاتفك غير مسجل في النظام.\n\n"
				"Sorry, your phone number is not registered."
			),
			settings,
		)
		return

	# Process image message through AI (for all conversations, including new ones)
	try:
		image_data = download_whatsapp_media(image_id, settings)
		if image_data:
			# Save as attachment and process with caption
			response, is_new, request_completed = process_smart_erp_ai_message(
				employee=employee,
				phone=sender_phone,
				message=caption or _("صورة مرفقة / Attached image"),
				attachment_data=image_data,
				attachment_filename=None,  # Will auto-generate
				attachment_mime_type=mime_type,
			)

			send_whatsapp_message(sender_phone, response, settings)

			# If a request was successfully completed, close the conversation
			if request_completed:
				close_whatsapp_conversation(sender_phone)
	except Exception as e:
		frappe.log_error(f"WhatsApp image processing error: {e!s}", "WhatsApp Error")
		send_whatsapp_message(
			sender_phone,
			_("عذراً، تعذر معالجة الصورة. يرجى المحاولة مرة أخرى."),
			settings,
		)


def process_document_message(message: dict, value: dict, settings: dict):
	"""
	Process an incoming document message (e.g., PDF receipts, medical reports)

	Args:
		message: The message object
		value: The full value object from webhook
		settings: WhatsApp settings
	"""
	sender_phone = message.get("from")
	doc_info = message.get("document", {})
	doc_id = doc_info.get("id")
	filename = doc_info.get("filename", "document")
	caption = doc_info.get("caption", "")
	mime_type = doc_info.get("mime_type", "application/pdf")

	# Find employee
	employee = get_employee_by_phone(sender_phone)

	if not employee:
		send_whatsapp_message(
			sender_phone,
			_(
				"عذراً، رقم هاتفك غير مسجل في النظام.\n\n"
				"Sorry, your phone number is not registered."
			),
			settings,
		)
		return

	# Process document message through AI
	try:
		doc_data = download_whatsapp_media(doc_id, settings)
		if doc_data:
			# Save as attachment and process with caption
			response, is_new, request_completed = process_smart_erp_ai_message(
				employee=employee,
				phone=sender_phone,
				message=caption or _("مستند مرفق / Attached document") + f": {filename}",
				attachment_data=doc_data,
				attachment_filename=filename,
				attachment_mime_type=mime_type,
			)

			send_whatsapp_message(sender_phone, response, settings)

			# If a request was successfully completed, close the conversation
			if request_completed:
				close_whatsapp_conversation(sender_phone)
	except Exception as e:
		frappe.log_error(f"WhatsApp document processing error: {e!s}", "WhatsApp Error")
		send_whatsapp_message(
			sender_phone,
			_("عذراً، تعذر معالجة المستند. يرجى المحاولة مرة أخرى."),
			settings,
		)


def download_whatsapp_media(media_id: str, settings: dict) -> bytes | None:
	"""
	Download media file from WhatsApp

	Args:
		media_id: The media ID from the webhook
		settings: WhatsApp settings

	Returns:
		File content as bytes or None
	"""
	# First, get the media URL
	url = f"{WHATSAPP_API_URL}/{media_id}"
	headers = {"Authorization": f"Bearer {settings['access_token']}"}

	response = requests.get(url, headers=headers, timeout=30)

	if response.status_code != 200:
		frappe.log_error(
			f"WhatsApp media URL fetch failed: {response.status_code} - {response.text}",
			"WhatsApp Error",
		)
		return None

	media_url = response.json().get("url")

	if not media_url:
		return None

	# Download the actual file
	file_response = requests.get(media_url, headers=headers, timeout=60)

	if file_response.status_code != 200:
		frappe.log_error(
			f"WhatsApp media download failed: {file_response.status_code}",
			"WhatsApp Error",
		)
		return None

	return file_response.content


def process_smart_erp_ai_message(
	employee: str,
	phone: str,
	message: str,
	attachment_data: bytes | None = None,
	attachment_filename: str | None = None,
	attachment_mime_type: str | None = None,
) -> tuple[str, bool, bool]:
	"""
	Process a message through the Smart ERP AI ConversationManager

	Args:
		employee: Employee name (ID)
		phone: Sender's phone number
		message: Message text
		attachment_data: Optional attachment bytes
		attachment_filename: Optional original filename
		attachment_mime_type: Optional MIME type of attachment

	Returns:
		Tuple of (response text, is_new_conversation: bool, request_completed: bool)
	"""

	# Get or create conversation for this phone number
	conversation, is_new = get_or_create_whatsapp_conversation(employee, phone)

	# Get the employee's user_id for context
	emp_doc = frappe.get_doc("Employee", employee)
	user = emp_doc.user_id

	# Create manager with the employee - this ensures employee_service is properly initialized
	from smart_erp_ai.conversation_manager import ConversationManager

	manager = ConversationManager(user=user, employee=employee)
	manager.conversation = conversation

	# Handle attachment if present
	attachments = []
	if attachment_data:
		# Save as temporary file and add to attachments
		file_doc = save_whatsapp_attachment(
			attachment_data,
			conversation.name,
			filename=attachment_filename,
			mime_type=attachment_mime_type,
		)
		if file_doc:
			attachments.append({
				"name": file_doc.name,  # File docname - required for _attach_files_to_doc
				"file_url": file_doc.file_url,
				"file_name": file_doc.file_name,
			})

	# Process the message
	result = manager.process_message(
		message=message,
		conversation_id=conversation.name,
		attachments=attachments,
	)

	# Check if a request was successfully completed (created in ERP)
	request_completed = False
	action_result = result.get("action_result")
	if action_result and action_result.get("type") == "success":
		request_completed = True

	return result.get("response", _("حدث خطأ / An error occurred")), is_new, request_completed


def close_whatsapp_conversation(phone: str) -> bool:
	"""
	Close the active WhatsApp conversation for a phone number.
	This allows the next message to start a fresh conversation.

	Args:
		phone: WhatsApp phone number

	Returns:
		True if conversation was closed, False otherwise
	"""
	try:
		existing = frappe.db.get_value(
			"Smart ERP AI Conversation",
			{"whatsapp_phone": phone, "status": "Active", "channel": "WhatsApp"},
			"name",
		)

		if existing:
			frappe.db.set_value(
				"Smart ERP AI Conversation",
				existing,
				"status",
				"Completed"
			)
			frappe.db.commit()
			return True
		return False
	except Exception as e:
		frappe.log_error(f"Error closing WhatsApp conversation: {e!s}", "WhatsApp Error")
		return False


def get_or_create_whatsapp_conversation(employee: str, phone: str) -> tuple:
	"""
	Get existing active WhatsApp conversation or create a new one

	Args:
		employee: Employee name (ID)
		phone: WhatsApp phone number

	Returns:
		Tuple of (Smart ERP AI Conversation document, is_new: bool)
	"""
	# Look for active conversation with this phone
	existing = frappe.db.get_value(
		"Smart ERP AI Conversation",
		{"whatsapp_phone": phone, "status": "Active", "channel": "WhatsApp"},
		"name",
	)

	if existing:
		return frappe.get_doc("Smart ERP AI Conversation", existing), False

	# Get employee's user
	emp_doc = frappe.get_doc("Employee", employee)
	user = emp_doc.user_id

	# Create new conversation
	conv = frappe.get_doc(
		{
			"doctype": "Smart ERP AI Conversation",
			"employee": employee,
			"user": user,
			"channel": "WhatsApp",
			"whatsapp_phone": phone,
			"status": "Active",
			"started_at": frappe.utils.now(),
		}
	)
	conv.insert(ignore_permissions=True)
	frappe.db.commit()

	return conv, True


def save_whatsapp_attachment(
	file_data: bytes,
	conversation_id: str,
	filename: str | None = None,
	mime_type: str | None = None,
):
	"""
	Save WhatsApp attachment as a File document

	Args:
		file_data: File content bytes
		conversation_id: Associated conversation ID
		filename: Optional original filename
		mime_type: Optional MIME type

	Returns:
		File document or None
	"""
	import hashlib
	from frappe.utils.file_manager import save_file

	# Generate filename based on mime type if not provided
	file_hash = hashlib.md5(file_data).hexdigest()[:8]

	if filename:
		# Use original filename but add hash for uniqueness
		name_parts = filename.rsplit(".", 1)
		if len(name_parts) == 2:
			final_filename = f"{name_parts[0]}_{file_hash}.{name_parts[1]}"
		else:
			final_filename = f"{filename}_{file_hash}"
	else:
		# Determine extension from mime type
		mime_to_ext = {
			"image/jpeg": "jpg",
			"image/png": "png",
			"image/gif": "gif",
			"image/webp": "webp",
			"application/pdf": "pdf",
			"application/msword": "doc",
			"application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
			"application/vnd.ms-excel": "xls",
			"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
		}
		ext = mime_to_ext.get(mime_type, "jpg")  # Default to jpg for images
		final_filename = f"whatsapp_attachment_{file_hash}.{ext}"

	try:
		file_doc = save_file(
			fname=final_filename,
			content=file_data,
			dt="Smart ERP AI Conversation",
			dn=conversation_id,
			is_private=1,
		)
		return file_doc
	except Exception as e:
		frappe.log_error(f"Failed to save WhatsApp attachment: {e!s}", "WhatsApp Error")
		return None


def send_whatsapp_message(to: str, message: str, settings: dict) -> bool:
	"""
	Send a WhatsApp message

	Args:
		to: Recipient phone number (E.164 format without +)
		message: Message text
		settings: WhatsApp settings

	Returns:
		True if sent successfully
	"""
	url = f"{WHATSAPP_API_URL}/{settings['phone_number_id']}/messages"

	headers = {
		"Authorization": f"Bearer {settings['access_token']}",
		"Content-Type": "application/json",
	}

	payload = {
		"messaging_product": "whatsapp",
		"recipient_type": "individual",
		"to": to,
		"type": "text",
		"text": {"preview_url": False, "body": message},
	}

	try:
		response = requests.post(url, headers=headers, json=payload, timeout=30)

		if response.status_code == 200:
			frappe.log_error(
				f"WhatsApp message sent to {to}: {message[:50]}...", "WhatsApp Debug"
			)
			return True
		else:
			frappe.log_error(
				f"WhatsApp send failed: {response.status_code} - {response.text}",
				"WhatsApp Error",
			)
			return False

	except Exception as e:
		frappe.log_error(f"WhatsApp send error: {e!s}", "WhatsApp Error")
		return False


def send_whatsapp_template(
	to: str, template_name: str, language_code: str, components: list, settings: dict
) -> bool:
	"""
	Send a WhatsApp template message (for proactive messages outside 24-hour window)

	Args:
		to: Recipient phone number
		template_name: Pre-approved template name
		language_code: Template language code (e.g., "ar", "en")
		components: Template component parameters
		settings: WhatsApp settings

	Returns:
		True if sent successfully
	"""
	url = f"{WHATSAPP_API_URL}/{settings['phone_number_id']}/messages"

	headers = {
		"Authorization": f"Bearer {settings['access_token']}",
		"Content-Type": "application/json",
	}

	payload = {
		"messaging_product": "whatsapp",
		"recipient_type": "individual",
		"to": to,
		"type": "template",
		"template": {
			"name": template_name,
			"language": {"code": language_code},
			"components": components,
		},
	}

	try:
		response = requests.post(url, headers=headers, json=payload, timeout=30)

		if response.status_code == 200:
			return True
		else:
			frappe.log_error(
				f"WhatsApp template send failed: {response.status_code} - {response.text}",
				"WhatsApp Error",
			)
			return False

	except Exception as e:
		frappe.log_error(f"WhatsApp template send error: {e!s}", "WhatsApp Error")
		return False


# Utility function to notify employee via WhatsApp
def notify_employee_whatsapp(employee: str, message: str) -> bool:
	"""
	Send a notification to an employee via WhatsApp

	Args:
		employee: Employee name (ID)
		message: Message to send

	Returns:
		True if sent successfully
	"""
	settings = get_whatsapp_settings()

	if not settings:
		return False

	# Get employee phone number
	phone = frappe.db.get_value("Employee", employee, "cell_number")

	if not phone:
		frappe.log_error(
			f"Cannot send WhatsApp to {employee}: No phone number", "WhatsApp Warning"
		)
		return False

	# Normalize phone number
	normalized = normalize_phone_number(phone)

	# Add country code if needed (assuming Saudi Arabia)
	if len(normalized) == 9:  # Local number without country code
		normalized = "966" + normalized

	return send_whatsapp_message(normalized, message, settings)
