# Copyright (c) 2025 - Smart ERP AI assistant tools for FAC

"""
Get current user's employee context (employee ID, leave balances).
Use before create_document for Leave Application to get the employee field.
"""

from typing import Any, Dict

import frappe

from frappe_assistant_core.core.base_tool import BaseTool


class GetEmployeeContext(BaseTool):
	"""Tool to get current user's employee and leave balance context."""

	def __init__(self):
		super().__init__()
		self.name = "get_employee_context"
		self.description = (
			"Get the current user's employee record, leave balances, and default company. "
			"Use before: Leave Application (for employee ID), Add Employee (for default company when user doesn't specify it). "
			"Returns: employee, employee_name, company, default_company, leave_balances. "
			"No arguments required."
		)
		self.inputSchema = {"type": "object", "properties": {}, "required": []}

	def _get_default_company(self) -> str:
		"""Get default company for the site (used when user has no employee)."""
		company = frappe.defaults.get_default("company")
		if company:
			return company
		first = frappe.get_all("Company", limit=1, pluck="name")
		return first[0] if first else ""

	def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
		"""Return employee context for current user."""
		user = frappe.session.user
		employee = frappe.db.get_value("Employee", {"user_id": user}, ["name", "employee_name", "company"], as_dict=True)
		default_company = (employee.company if employee else None) or self._get_default_company()

		if not employee:
			return {
				"employee": None,
				"employee_name": None,
				"company": default_company,
				"default_company": default_company,
				"leave_balances": [],
				"message": "No employee linked to current user. Use default_company when creating employees.",
			}

		# Get leave balances if hrms is available
		leave_balances = []
		if frappe.db.table_exists("Leave Allocation"):
			allocations = frappe.get_all(
				"Leave Allocation",
				filters={"employee": employee.name, "docstatus": 1},
				fields=["leave_type", "total_leaves_allocated", "leaves_taken", "name"],
			)
			for a in allocations:
				balance = (a.total_leaves_allocated or 0) - (a.leaves_taken or 0)
				leave_balances.append({
					"leave_type": a.leave_type,
					"balance": balance,
					"allocated": a.total_leaves_allocated,
					"taken": a.leaves_taken,
				})

		return {
			"employee": employee.name,
			"employee_name": employee.employee_name,
			"company": employee.company,
			"default_company": default_company,
			"leave_balances": leave_balances,
		}
