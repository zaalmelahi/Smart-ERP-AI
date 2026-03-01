# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, today


class EmployeeService:
	"""Service class to fetch employee-related data for AI context"""

	def __init__(self, employee: str = None, user: str = None):
		"""
		Initialize with either employee ID or user ID

		Args:
		        employee: Employee document name
		        user: User email/name
		"""
		self.user = user or frappe.session.user
		self.employee = employee or self._get_employee_from_user()
		self.employee_doc = None

		if self.employee:
			self.employee_doc = frappe.get_cached_doc("Employee", self.employee)

	def _get_employee_from_user(self) -> str | None:
		"""Get employee ID from user"""
		return frappe.db.get_value("Employee", {"user_id": self.user, "status": "Active"}, "name")

	def get_context(self) -> dict:
		"""Get complete employee context for AI prompt"""
		if not self.employee_doc:
			return {
				"employee_id": None,
				"employee_name": self.user,
				"department": "Unknown",
				"designation": "Unknown",
				"reports_to": None,
				"date_of_joining": None,
				"leave_balances": [],
				"pending_requests": [],
				"company": frappe.defaults.get_user_default("Company"),
			}

		return {
			"employee_id": self.employee,
			"employee_name": self.employee_doc.employee_name,
			"department": self.employee_doc.department,
			"designation": self.employee_doc.designation,
			"reports_to": self._get_manager_name(),
			"date_of_joining": str(self.employee_doc.date_of_joining) if self.employee_doc.date_of_joining else None,
			"leave_balances": self.get_leave_balances(),
			"pending_requests": self.get_pending_requests(),
			"recent_leaves": self.get_recent_leaves(),
			"leave_types": self.get_leave_types(),
			"leave_policy": self.get_leave_policy_details(),
			"company": self.employee_doc.company,
			"holiday_list": self.employee_doc.holiday_list,
			# Expense-related context
			"expense_types": self.get_expense_types(),
			"recent_expenses": self.get_recent_expenses(),
			"pending_expenses": self.get_pending_expense_claims(),
		}

	def _get_manager_name(self) -> str | None:
		"""Get manager's name"""
		if not self.employee_doc.reports_to:
			return None
		return frappe.db.get_value("Employee", self.employee_doc.reports_to, "employee_name")

	def get_leave_balances(self) -> list:
		"""Get leave balances for the employee"""
		if not self.employee:
			return []

		# Check if HRMS is installed by checking if Leave Allocation exists
		if not frappe.db.table_exists("Leave Allocation"):
			return []

		try:
			# Get leave types allocated to employee
			allocations = frappe.get_all(
				"Leave Allocation",
				filters={
					"employee": self.employee,
					"docstatus": 1,
					"from_date": ("<=", today()),
					"to_date": (">=", today()),
				},
				fields=["leave_type", "total_leaves_allocated", "new_leaves_allocated"],
			)

			balances = []
			for alloc in allocations:
				# Calculate used leaves
				used = (
					frappe.db.sql(
						"""
					SELECT COALESCE(SUM(total_leave_days), 0)
					FROM `tabLeave Application`
					WHERE employee = %s
					AND leave_type = %s
					AND docstatus = 1
					AND status = 'Approved'
					AND from_date >= %s
				""",
						(self.employee, alloc.leave_type, frappe.utils.get_first_day(today())),
					)[0][0]
					or 0
				)

				balance = alloc.total_leaves_allocated - used
				balances.append(
					{
						"leave_type": alloc.leave_type,
						"allocated": alloc.total_leaves_allocated,
						"used": used,
						"balance": balance,
					}
				)

			return balances
		except Exception as e:
			frappe.log_error(f"Error fetching leave balances: {e}", "Smart ERP AI")
			return []

	def get_pending_requests(self) -> list:
		"""Get pending requests for the employee"""
		if not self.employee:
			return []

		pending = []

		# Check for pending leave applications (if HRMS installed)
		if frappe.db.table_exists("Leave Application"):
			try:
				leaves = frappe.get_all(
					"Leave Application",
					filters={"employee": self.employee, "docstatus": 0},
					fields=["name", "leave_type", "from_date", "to_date", "status"],
					limit=10,
				)
				for leave in leaves:
					pending.append(
						{
							"doctype": "Leave Application",
							"name": leave.name,
							"type": leave.leave_type,
							"from_date": str(leave.from_date),
							"to_date": str(leave.to_date),
							"status": leave.status,
						}
					)
			except Exception:
				pass

		# Check for pending expense claims
		if frappe.db.table_exists("Expense Claim"):
			try:
				expenses = frappe.get_all(
					"Expense Claim",
					filters={"employee": self.employee, "docstatus": 0},
					fields=["name", "total_claimed_amount", "approval_status"],
					limit=10,
				)
				for exp in expenses:
					pending.append(
						{
							"doctype": "Expense Claim",
							"name": exp.name,
							"amount": exp.total_claimed_amount,
							"status": exp.approval_status,
						}
					)
			except Exception:
				pass

		return pending

	def get_recent_leaves(self, limit: int = 5) -> list:
		"""Get recent leave applications"""
		if not self.employee:
			return []

		if not frappe.db.table_exists("Leave Application"):
			return []

		try:
			leaves = frappe.get_all(
				"Leave Application",
				filters={"employee": self.employee, "docstatus": 1},
				fields=["name", "leave_type", "from_date", "to_date", "total_leave_days", "status"],
				order_by="from_date desc",
				limit=limit,
			)

			return [
				{
					"name": l.name,
					"leave_type": l.leave_type,
					"from_date": str(l.from_date),
					"to_date": str(l.to_date),
					"days": l.total_leave_days,
					"status": l.status,
				}
				for l in leaves
			]
		except Exception:
			return []

	def get_upcoming_holidays(self, limit: int = 5) -> list:
		"""Get upcoming holidays from employee's holiday list"""
		if not self.employee_doc or not self.employee_doc.holiday_list:
			return []

		try:
			holidays = frappe.get_all(
				"Holiday",
				filters={
					"parent": self.employee_doc.holiday_list,
					"holiday_date": (">=", today()),
				},
				fields=["holiday_date", "description"],
				order_by="holiday_date asc",
				limit=limit,
			)

			return [{"date": str(h.holiday_date), "description": h.description} for h in holidays]
		except Exception:
			return []

	def get_leave_types(self) -> list:
		"""Get available leave types with their rules from ERPNext"""
		if not frappe.db.table_exists("Leave Type"):
			return []

		try:
			leave_types = frappe.get_all(
				"Leave Type",
				filters={"is_active": 1} if frappe.db.has_column("Leave Type", "is_active") else {},
				fields=[
					"name",
					"max_continuous_days_allowed",
					"is_carry_forward",
					"include_holiday",
					"is_compensatory",
					"is_earned_leave",
					"is_lwp",
				],
			)
			return leave_types
		except Exception as e:
			frappe.log_error(f"Error fetching leave types: {e}", "Smart ERP AI")
			return []

	def get_leave_policy_details(self) -> dict:
		"""Get leave policy details for the employee from ERPNext"""
		if not self.employee:
			return {}

		# Check if Leave Policy Assignment exists
		if not frappe.db.table_exists("Leave Policy Assignment"):
			return {}

		try:
			# Get active leave policy assignment
			assignment = frappe.db.get_value(
				"Leave Policy Assignment",
				{
					"employee": self.employee,
					"docstatus": 1,
				},
				["leave_policy", "effective_from", "effective_to"],
				as_dict=True,
			)

			if not assignment:
				return {}

			# Get leave policy details
			policy = frappe.get_doc("Leave Policy", assignment.leave_policy)
			details = {
				"policy_name": policy.name,
				"effective_from": str(assignment.effective_from) if assignment.effective_from else None,
				"effective_to": str(assignment.effective_to) if assignment.effective_to else None,
				"allocations": [],
			}

			for d in policy.leave_policy_details:
				details["allocations"].append({
					"leave_type": d.leave_type,
					"annual_allocation": d.annual_allocation,
				})

			return details
		except Exception as e:
			frappe.log_error(f"Error fetching leave policy: {e}", "Smart ERP AI")
			return {}

	def validate_leave_request(self, leave_type: str, from_date: str, to_date: str, has_attachment: bool = False) -> dict:
		"""
		Validate a leave request against ERPNext HRMS rules

		This method uses ERPNext's built-in validation:
		- Leave balance from Leave Allocation
		- Leave Type rules (max_continuous_days, etc.)
		- Overlapping leave checks

		Args:
		        leave_type: The type of leave being requested
		        from_date: Start date of the leave
		        to_date: End date of the leave
		        has_attachment: Whether a medical certificate/supporting document is attached
		                        (bypasses max_continuous_days for sick leave)

		Returns:
		        dict with 'valid', 'message', and 'warnings'
		"""
		result = {"valid": True, "message": "", "warnings": []}

		if not self.employee:
			result["valid"] = False
			result["message"] = "Employee not found for current user"
			return result

		from_date = getdate(from_date)
		to_date = getdate(to_date)

		# Calculate days
		days_requested = (to_date - from_date).days + 1

		# Check if dates are valid
		if from_date > to_date:
			result["valid"] = False
			result["message"] = "From date cannot be after to date"
			return result

		if from_date < getdate(today()):
			result["warnings"].append("Leave request is for past dates")

		# Check leave balance from ERPNext Leave Allocation
		balances = self.get_leave_balances()
		balance_info = next((b for b in balances if b["leave_type"] == leave_type), None)

		if balance_info:
			if balance_info["balance"] < days_requested:
				result["valid"] = False
				result["message"] = f"Insufficient {leave_type} balance. Available: {balance_info['balance']} days, Requested: {days_requested} days"
				return result
		else:
			result["warnings"].append(f"Could not verify {leave_type} balance")

		# Check Leave Type rules from ERPNext
		if frappe.db.table_exists("Leave Type"):
			try:
				leave_type_doc = frappe.db.get_value(
					"Leave Type",
					leave_type,
					["max_continuous_days_allowed", "is_lwp"],
					as_dict=True,
				)
				if leave_type_doc:
					# Check max continuous days
					if leave_type_doc.max_continuous_days_allowed and leave_type_doc.max_continuous_days_allowed > 0:
						if days_requested > leave_type_doc.max_continuous_days_allowed:
							# Skip max_continuous_days validation for sick leave if medical certificate is attached
							is_sick_leave = leave_type and "sick" in leave_type.lower() or "مرض" in leave_type
							if is_sick_leave and has_attachment:
								# Medical certificate attached - allow extended sick leave with a warning
								result["warnings"].append(
									f"Extended sick leave ({days_requested} days) approved with medical certificate"
								)
							else:
								result["valid"] = False
								result["message"] = f"Maximum {leave_type_doc.max_continuous_days_allowed} continuous days allowed for {leave_type}"
								return result

					# Warn if it's Leave Without Pay
					if leave_type_doc.is_lwp:
						result["warnings"].append("This is Leave Without Pay - salary will be deducted")
			except Exception:
				pass

		# Check for overlapping leaves in ERPNext
		if frappe.db.table_exists("Leave Application"):
			overlapping = frappe.db.count(
				"Leave Application",
				filters={
					"employee": self.employee,
					"docstatus": ["<", 2],
					"from_date": ("<=", to_date),
					"to_date": (">=", from_date),
				},
			)

			if overlapping > 0:
				result["warnings"].append("There are overlapping leave requests for these dates")

		result["message"] = "Leave request can be submitted"
		return result

	# ==================== EXPENSE CLAIM METHODS ====================

	def get_expense_types(self) -> list:
		"""Get available expense claim types from ERPNext"""
		if not frappe.db.table_exists("Expense Claim Type"):
			return []

		try:
			expense_types = frappe.get_all(
				"Expense Claim Type",
				fields=["name", "description"],
			)
			return expense_types
		except Exception as e:
			frappe.log_error(f"Error fetching expense types: {e}", "Smart ERP AI")
			return []

	def get_recent_expenses(self, limit: int = 5) -> list:
		"""Get recent expense claims for the employee"""
		if not self.employee:
			return []

		if not frappe.db.table_exists("Expense Claim"):
			return []

		try:
			expenses = frappe.get_all(
				"Expense Claim",
				filters={"employee": self.employee},
				fields=[
					"name", "posting_date", "total_claimed_amount",
					"approval_status", "status", "docstatus"
				],
				order_by="posting_date desc",
				limit=limit,
			)

			return [
				{
					"name": e.name,
					"date": str(e.posting_date) if e.posting_date else None,
					"amount": float(e.total_claimed_amount or 0),
					"approval_status": e.approval_status,
					"status": e.status,
				}
				for e in expenses
			]
		except Exception:
			return []

	def get_pending_expense_claims(self) -> list:
		"""Get pending expense claims for the employee"""
		if not self.employee:
			return []

		if not frappe.db.table_exists("Expense Claim"):
			return []

		try:
			expenses = frappe.get_all(
				"Expense Claim",
				filters={
					"employee": self.employee,
					"docstatus": 0,
				},
				fields=[
					"name", "posting_date", "total_claimed_amount",
					"approval_status"
				],
			)

			return [
				{
					"name": e.name,
					"date": str(e.posting_date) if e.posting_date else None,
					"amount": float(e.total_claimed_amount or 0),
					"status": e.approval_status,
				}
				for e in expenses
			]
		except Exception:
			return []

	def validate_expense_request(
		self,
		expense_type: str,
		amount: float,
		expense_date: str,
		expense_policies: dict = None
	) -> dict:
		"""
		Validate an expense request against policies

		Args:
			expense_type: Type of expense (e.g., "Meals and Entertainment")
			amount: Amount claimed
			expense_date: Date of expense
			expense_policies: Policy rules from HR Assistant Settings

		Returns:
			dict with 'valid', 'message', and 'warnings'
		"""
		result = {"valid": True, "message": "", "warnings": []}

		if not self.employee:
			result["valid"] = False
			result["message"] = "Employee not found for current user"
			return result

		# Validate expense type exists
		if not frappe.db.table_exists("Expense Claim Type"):
			result["warnings"].append("Expense Claim Type table not found")
		elif not frappe.db.exists("Expense Claim Type", expense_type):
			result["valid"] = False
			result["message"] = f"Invalid expense type: {expense_type}"
			return result

		# Validate amount
		if amount <= 0:
			result["valid"] = False
			result["message"] = "Expense amount must be greater than zero"
			return result

		# Validate date
		expense_date_obj = getdate(expense_date)
		today_date = getdate(today())

		# Check if expense is too old (default: 30 days)
		max_days_old = 30
		if expense_policies and expense_policies.get("max_expense_age_days"):
			max_days_old = expense_policies.get("max_expense_age_days")

		days_old = (today_date - expense_date_obj).days
		if days_old > max_days_old:
			result["valid"] = False
			result["message"] = f"Expense is too old. Must be submitted within {max_days_old} days. This expense is {days_old} days old."
			return result

		if expense_date_obj > today_date:
			result["valid"] = False
			result["message"] = "Expense date cannot be in the future"
			return result

		# Check policy limits if provided
		if expense_policies:
			# Check per-transaction limit
			per_transaction_limit = expense_policies.get("per_transaction_limit", 0)
			if per_transaction_limit > 0 and amount > per_transaction_limit:
				result["valid"] = False
				result["message"] = f"Amount exceeds per-transaction limit of {per_transaction_limit}"
				return result

			# Check receipt requirement
			receipt_threshold = expense_policies.get("receipt_required_above", 50)
			if amount > receipt_threshold:
				result["warnings"].append(f"Receipt required for expenses above {receipt_threshold}")

			# Check daily limit (would need to aggregate daily expenses)
			daily_limit = expense_policies.get("daily_limit", 0)
			if daily_limit > 0:
				# Get today's total expenses
				daily_total = self._get_daily_expense_total(expense_date)
				if daily_total + amount > daily_limit:
					result["warnings"].append(
						f"This expense would exceed daily limit of {daily_limit}. "
						f"Current daily total: {daily_total}"
					)

		result["message"] = "Expense request can be submitted"
		return result

	def _get_daily_expense_total(self, date: str) -> float:
		"""Get total expenses for a specific date"""
		if not self.employee or not frappe.db.table_exists("Expense Claim Detail"):
			return 0.0

		try:
			total = frappe.db.sql(
				"""
				SELECT COALESCE(SUM(ecd.amount), 0) as total
				FROM `tabExpense Claim Detail` ecd
				JOIN `tabExpense Claim` ec ON ec.name = ecd.parent
				WHERE ec.employee = %s
				AND ecd.expense_date = %s
				AND ec.docstatus < 2
				""",
				(self.employee, date),
			)[0][0] or 0.0
			return float(total)
		except Exception:
			return 0.0

	def get_expense_approver(self) -> str | None:
		"""Get the expense approver for this employee"""
		if not self.employee_doc:
			return None

		# First check if employee has expense_approver set
		if hasattr(self.employee_doc, "expense_approver") and self.employee_doc.expense_approver:
			return self.employee_doc.expense_approver

		# Fall back to reports_to manager's user_id
		if self.employee_doc.reports_to:
			manager_user = frappe.db.get_value(
				"Employee",
				self.employee_doc.reports_to,
				"user_id"
			)
			return manager_user

		return None

	# ==================== EMPLOYEE ADVANCE METHODS ====================

	def validate_advance_request(self, amount: float, purpose: str) -> dict:
		"""
		Validate an employee advance request (سلفة/عهدة)

		Args:
			amount: Amount requested
			purpose: Purpose/reason for the advance

		Returns:
			dict with 'valid', 'message', and 'warnings'
		"""
		result = {"valid": True, "message": "", "warnings": []}

		if not self.employee:
			result["valid"] = False
			result["message"] = "الموظف غير موجود للمستخدم الحالي"
			return result

		# Validate amount
		if amount <= 0:
			result["valid"] = False
			result["message"] = "المبلغ يجب أن يكون أكبر من صفر"
			return result

		# Validate purpose is provided
		if not purpose or len(purpose.strip()) < 3:
			result["valid"] = False
			result["message"] = "يرجى توضيح الغرض من السلفة/العهدة"
			return result

		# Check if Employee Advance table exists
		if not frappe.db.table_exists("Employee Advance"):
			result["valid"] = False
			result["message"] = "وحدة السلف غير متوفرة في النظام"
			return result

		# Check for pending (unpaid) advances
		pending_advances = self.get_pending_advances()
		if pending_advances:
			pending_total = sum(adv.get("amount", 0) for adv in pending_advances)
			result["warnings"].append(
				f"لديك سلف معلقة بقيمة {pending_total} ر.س. سيتم مراجعة الطلب من مسؤول المصروفات."
			)

		# Check if company has advance account configured
		if self.employee_doc and self.employee_doc.company:
			advance_account = frappe.db.get_value(
				"Company",
				self.employee_doc.company,
				"default_employee_advance_account"
			)
			if not advance_account:
				result["warnings"].append("حساب السلف غير مُعد في الشركة. قد يتطلب إعداد إضافي.")

		result["message"] = "يمكن تقديم طلب السلفة"
		return result

	def get_pending_advances(self) -> list:
		"""Get pending (unpaid) employee advances for the employee"""
		if not self.employee:
			return []

		if not frappe.db.table_exists("Employee Advance"):
			return []

		try:
			advances = frappe.get_all(
				"Employee Advance",
				filters={
					"employee": self.employee,
					"docstatus": 1,  # Submitted
					"status": ["in", ["Unpaid", "Paid"]],  # Unpaid or Paid but not claimed
				},
				fields=[
					"name", "posting_date", "advance_amount",
					"paid_amount", "claimed_amount", "return_amount", "status"
				],
			)

			return [
				{
					"name": a.name,
					"date": str(a.posting_date) if a.posting_date else None,
					"amount": float(a.advance_amount or 0),
					"paid": float(a.paid_amount or 0),
					"claimed": float(a.claimed_amount or 0),
					"returned": float(a.return_amount or 0),
					"status": a.status,
				}
				for a in advances
			]
		except Exception:
			return []

	def get_advance_balance(self) -> dict:
		"""Get total advance balance (outstanding advances to be settled)"""
		if not self.employee:
			return {"total_outstanding": 0, "advances": []}

		pending = self.get_pending_advances()
		total_outstanding = 0

		for adv in pending:
			# Outstanding = paid - claimed - returned
			outstanding = adv.get("paid", 0) - adv.get("claimed", 0) - adv.get("returned", 0)
			if outstanding > 0:
				total_outstanding += outstanding

		return {
			"total_outstanding": total_outstanding,
			"advances": pending,
		}
