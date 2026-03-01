# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def after_install():
	"""Setup Smart ERP AI after installation."""
	create_smart_erp_ai_settings()
	add_naming_series_options()
	install_fac_hr_assistant_prompt()


def create_smart_erp_ai_settings():
	"""Create Smart ERP AI Settings if it doesn't exist."""
	if not frappe.db.exists("DocType", "Smart ERP AI Settings"):
		return

	try:
		frappe.get_single("Smart ERP AI Settings")
	except Exception:
		# Settings will be created automatically on first access
		pass


def add_naming_series_options():
	"""Add naming series options for Smart ERP AI Conversation."""
	try:
		# Create naming series for SEA-CONV-.YYYY.-
		# Use exists() for Series - get_value adds ORDER BY modified which Series table lacks
		if frappe.db.exists("DocType", "Smart ERP AI Conversation"):
			series_exists = frappe.db.exists("Series", "SEA-CONV-.YYYY.-")
			if not series_exists:
				frappe.get_doc(
					{
						"doctype": "Series",
						"name": "SEA-CONV-.YYYY.-",
						"current": 0,
					}
				).insert(ignore_permissions=True)
				frappe.db.commit()
	except Exception as e:
		frappe.log_error(f"Smart ERP AI install: {e}", "Smart ERP AI Install")


def install_fac_hr_assistant_prompt():
	"""Install or update HR Assistant conversational prompt in FAC Prompt Templates."""
	if not frappe.db.table_exists("Prompt Template"):
		return
	# Template content - also used when updating existing prompt
	prompt_content = """You are an intelligent HR/ERP assistant. EXECUTE ACTIONS - do not just describe DocTypes.

**CRITICAL: When user requests to create something (add employee, leave request, etc.), you MUST call create_document and report the result. NEVER respond with DocType field descriptions instead of executing the action.**

**Key tools:**
- get_employee_context: Call first for add employee AND leave requests. Returns employee ID, default_company, leave_balances.
- create_document: Create Employee, Leave Application, Expense Claim. Call it to perform the action.
- get_doctype_info: Use only when unsure of fields. Do NOT paste its output to the user when they asked to create something.

**Add employee workflow (EXECUTE, do not describe):**
1. Call get_employee_context → get default_company
2. Parse from user message: first_name, last_name (split full name), gender, date_of_birth, date_of_joining
3. **Gender mapping** - normalize to exact values: ذكر=male→"Male", أنثى=female→"Female"
4. Call create_document for Employee with: doctype="Employee", data={first_name, last_name, gender, date_of_birth, date_of_joining, company, status}
5. Respond with the creation result (success + employee name/number, or error message)

**Gender recognition:** Map any of these to "Male": ذكر, male, Male. Map to "Female": أنثى, female, Female.

**Leave/expense:** Same principle - execute create_document, then report result. Do not describe fields.

**Response style:** Reply in user's language (Arabic/English). Be brief. Show action outcome."""
	try:
		existing = frappe.db.get_value("Prompt Template", {"prompt_id": "hr_assistant_chat"}, "name")
		if existing:
			doc = frappe.get_doc("Prompt Template", existing)
			doc.template_content = prompt_content
			doc.save(ignore_permissions=True)
			frappe.db.commit()
			return
		doc = frappe.get_doc({
			"doctype": "Prompt Template",
			"prompt_id": "hr_assistant_chat",
			"title": "HR Assistant Chat",
			"description": "Conversational HR assistant - create leave, expense claims, employees; use FAC tools.",
			"status": "Published",
			"visibility": "Public",
			"is_system": 1,
			"category": "hr-payroll",
			"rendering_engine": "Raw",
			"template_content": prompt_content,
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(f"Install FAC hr_assistant_chat prompt: {e}", "Smart ERP AI Install")
