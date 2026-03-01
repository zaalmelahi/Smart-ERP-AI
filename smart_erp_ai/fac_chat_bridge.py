# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
FAC Chat Bridge - Delegates to frappe_assistant_core for prompts and tools.

Smart ERP AI uses FAC as the source of truth:
- System prompts from FAC Prompt Templates
- Tools from FAC Tool Registry
- Tool execution via FAC execute_tool

HR-specific logic (employee_service, validation) is exposed as FAC tools via assistant_tools hook.
"""

import json
from typing import Any

import frappe
from frappe import _

from smart_erp_ai.llm import get_llm_client

# Default prompt when FAC prompt is not available
DEFAULT_SYSTEM_PROMPT_AR = """أنت مساعد ERP ذكي. استخدم الأدوات المتاحة لمساعدة المستخدم:
- create_document: لإنشاء طلبات الإجازات، المصروفات، الموظفين، وغيرها
- get_document, list_documents: للبحث وعرض البيانات
- get_doctype_info: لمعرفة الحقول المطلوبة قبل الإنشاء

رد باللغة العربية عندما يكتب المستخدم بالعربية. كن موجزاً ومفيداً."""

DEFAULT_SYSTEM_PROMPT_EN = """You are an intelligent ERP assistant. Use the available tools to help the user:
- create_document: to create leave requests, expense claims, employees, etc.
- get_document, list_documents: to search and display data
- get_doctype_info: to learn required fields before creating documents

Respond in the user's language. Be concise and helpful."""


def get_fac_system_prompt(language: str = "ar") -> str:
    """
    Get system prompt from FAC Prompt Templates.
    Prefers hr_assistant_chat, falls back to hr_analysis with defaults, then hardcoded default.
    """
    try:
        from frappe_assistant_core.api.handlers.prompts import get_prompt_manager

        manager = get_prompt_manager()

        # Try hr_assistant_chat first (conversational, no required args)
        name = frappe.db.get_value(
            "Prompt Template", {"prompt_id": "hr_assistant_chat", "status": "Published"}, "name"
        )
        if name:
            prompt_doc = frappe.get_doc("Prompt Template", name)
            return manager.render_prompt(prompt_doc, {})

        # Try hr_analysis with defaults (has required analysis_focus)
        name = frappe.db.get_value(
            "Prompt Template", {"prompt_id": "hr_analysis", "status": "Published"}, "name"
        )
        if name:
            prompt_doc = frappe.get_doc("Prompt Template", name)
            return manager.render_prompt(
                prompt_doc,
                {"analysis_focus": "overall_performance", "time_period": "last_month", "include_payroll": False},
            )
    except Exception as e:
        frappe.log_error(f"FAC prompt load failed: {e}", "Smart ERP AI FAC Bridge")

    return DEFAULT_SYSTEM_PROMPT_AR if language == "ar" else DEFAULT_SYSTEM_PROMPT_EN


def get_fac_tools_for_llm(user: str = None) -> list[dict]:
    """
    Get available FAC tools and convert to OpenAI function format.
    """
    try:
        from frappe_assistant_core.core.tool_registry import get_tool_registry

        registry = get_tool_registry()
        tools = registry.get_available_tools(user=user or frappe.session.user)

        result = []
        for t in tools:
            name = t.get("name")
            desc = t.get("description", "")
            schema = t.get("inputSchema", {})
            if name:
                result.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": desc,
                        "parameters": schema,
                    },
                })
        return result
    except Exception as e:
        frappe.log_error(f"FAC tools load failed: {e}", "Smart ERP AI FAC Bridge")
        return []


def execute_fac_tool(tool_name: str, arguments: dict) -> Any:
    """Execute a tool via FAC tool registry."""
    from frappe_assistant_core.core.tool_registry import get_tool_registry

    registry = get_tool_registry()
    result = registry.execute_tool(tool_name, arguments)

    # FAC tools may return dict; normalize to string for LLM
    if isinstance(result, dict):
        return json.dumps(result, default=str, ensure_ascii=False)
    return str(result)


def process_chat_with_fac(
    messages: list[dict],
    system_prompt: str,
    tools: list[dict],
    max_tool_rounds: int = 5,
) -> dict:
    """
    Run chat loop: LLM with tools, execute tool calls via FAC, repeat until done.

    Returns:
        dict with 'message', 'tool_calls_made' (count)
    """
    llm = get_llm_client()
    if not hasattr(llm, "chat_with_tools") or not callable(getattr(llm, "chat_with_tools", None)):
        # Fallback: simple chat without tools
        response = llm.chat(messages=messages, system_prompt=system_prompt)
        return {"message": response.get("message", ""), "tool_calls_made": 0}

    full_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages
    ]

    tool_calls_count = 0
    for _ in range(max_tool_rounds):
        out = llm.chat_with_tools(
            messages=full_messages,
            tools=tools,
        )
        msg = out.get("message", "")
        tool_calls = out.get("tool_calls", [])

        if not tool_calls:
            return {"message": msg, "tool_calls_made": tool_calls_count}

        # Append assistant message with tool calls (OpenAI format)
        assistant_msg = {"role": "assistant", "content": msg or None}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {"id": t.get("id", ""), "type": "function", "function": t.get("function", {})}
                for t in tool_calls
            ]
        full_messages.append(assistant_msg)

        # Execute each tool call and append results
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name") or tc.get("name")
            args_str = fn.get("arguments") or tc.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}
            try:
                result = execute_fac_tool(name, args)
                tool_calls_count += 1
            except Exception as e:
                result = f"Error: {e!s}"
            full_messages.append({
                "role": "tool",
                "content": result,
                "tool_call_id": tc.get("id") or tc.get("tool_call_id", ""),
            })

    # Max rounds exceeded
    return {"message": _("تم تجاوز الحد الأقصى لاستدعاءات الأدوات. يرجى إعادة المحاولة."), "tool_calls_made": tool_calls_count}
