# خطة دمج Smart ERP AI

## الهدف

دمج ميزات **frappe_assistant_core** و **hr_assistant** في تطبيق **smart_erp_ai**، والاستغناء عن hr_assistant، وتوسيع المساعد من الموارد البشرية فقط إلى نظام ERPNext كامل.

---

## نظرة عامة على التطبيقات

| التطبيق | الوظيفة |
|---------|---------|
| **frappe_assistant_core** | MCP Server، OAuth 2.0، أدوات CRUD، تحليلات، لوحات تفاعلية (~23 أداة) |
| **hr_assistant** | مساعد محادثة HR (إجازات، مصروفات، سلف، سياسات)، واجهة عربية، واتساب |
| **smart_erp_ai** | الهيكل المستهدف: مساعد موحد لـ ERPNext كامل |

---

## الاستراتيجية

### 1. frappe_assistant_core كـ Dependency

- **لا ندمج** frappe_assistant_core داخل smart_erp_ai (معقد: MCP، OAuth، إلخ).
- smart_erp_ai يعتمد على frappe_assistant_core كـ **required_app**.
- استخدام **assistant_tools** hook لتسجيل أدوات ERP مخصصة.
- واجهة FAC Admin تبقى كما هي لإدارة MCP و OAuth.

### 2. نقل ميزات hr_assistant

- نقل DocTypes، API، Conversation Manager، LLM، Widget، WhatsApp.
- إعادة تسمية من HR-specific إلى ERP عام:
  - HR Assistant Settings → Smart ERP AI Settings
  - HR Assistant Conversation → Smart ERP AI Conversation
  - إلخ.

### 3. التوسع نحو ERP كامل

- إضافة نوايا (intents) جديدة: مبيعات، مشتريات، مخزون، محاسبة.
- إنشاء Context Services لكل وحدة (Employee، Customer، Item، إلخ).
- تسجيل أدوات MCP مخصصة للعمليات الشائعة في ERPNext.

---

## مراحل التنفيذ

### المرحلة 1: إعداد smart_erp_ai (Dependencies + Structure) ✅

- [x] إضافة `required_apps = ["frappe", "erpnext", "hrms", "frappe_assistant_core"]`
- [x] إنشاء هيكل المجلدات المطلوب
- [x] إعداد `modules.txt` و `patches.txt`

### المرحلة 2: نقل DocTypes من hr_assistant ✅

| DocType الحالي | DocType الجديد |
|----------------|----------------|
| HR Assistant Settings | Smart ERP AI Settings |
| HR Assistant Conversation | Smart ERP AI Conversation |
| HR Assistant Message | Smart ERP AI Message |
| HR Assistant Created Document | Smart ERP AI Created Document |

- [x] إنشاء JSON و Python لكل DocType
- [x] إضافة حقل `module` = "Smart erp ai"
- [x] تحديث العلاقات (fieldname، links)

### المرحلة 3: نقل الخدمات والـ API ✅

- [x] `employee_service.py` (يحتفظ بوظيفة HR)
- [x] `conversation_manager.py` (تعديل للإشارة إلى DocTypes الجديدة)
- [x] `llm/` (Claude، OpenAI)
- [x] `api.py` تحديث المسارات والاستيرادات
- [x] `whatsapp.py` تحديث webhook و route

### المرحلة 4: واجهة المستخدم (Widget) ✅

- [x] نسخ وإعادة تسمية Widget و CSS
- [x] تحديث API endpoints (smart_erp_ai.api)
- [x] دعم RTL والعربية

### المرحلة 5: التوسع نحو ERP (للمستقبل)

- [ ] إضافة **ERP Context Service** يجمع سياق المستخدم (Employee، Customer، permissions)
- [ ] توسيع **intents** في ConversationManager:
  - `leave_request`, `expense_claim`, `employee_advance` (موجودة)
  - `sales_order`, `purchase_order`, `invoice`, `stock_entry`, `payment_entry`, إلخ.
- [ ] إنشاء **assistant_tools** في smart_erp_ai:
  - أدوات لإنشاء/استعلام أوامر مبيعات، فواتير، إلخ.
- [ ] تحديث System Prompt ليشمل وحدات ERP المختلفة

### المرحلة 6: التكامل مع frappe_assistant_core

- [ ] تسجيل `assistant_tools` في hooks.py
- [ ] (اختياري) ربط واجهة المحادثة مع MCP كـ frontend بديل
- [ ] توحيد إعدادات LLM إن أمكن

### المرحلة 7: إزالة hr_assistant

- [ ] migration script لنسخ البيانات من HR Assistant إلى Smart ERP AI (إن وجدت)
- [ ] تحديث الوثائق
- [ ] إلغاء تثبيت hr_assistant من bench

---

## هيكل smart_erp_ai بعد الدمج

```
smart_erp_ai/
├── smart_erp_ai/
│   ├── hooks.py
│   ├── api.py
│   ├── conversation_manager.py
│   ├── modules.txt
│   ├── patches.txt
│   ├── assistant_tools/           # أدوات MCP مخصصة
│   │   ├── __init__.py
│   │   ├── sales_tools.py
│   │   └── ...
│   ├── services/
│   │   ├── employee_service.py
│   │   ├── erp_context_service.py
│   │   └── ...
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── claude.py
│   │   └── openai.py
│   ├── smart_erp_ai/              # module
│   │   ├── doctype/
│   │   │   ├── smart_erp_ai_settings/
│   │   │   ├── smart_erp_ai_conversation/
│   │   │   ├── smart_erp_ai_message/
│   │   │   └── smart_erp_ai_created_document/
│   │   └── workspace/
│   ├── public/
│   │   ├── css/smart_erp_ai.css
│   │   └── js/smart_erp_ai_widget.js
│   └── whatsapp.py
├── pyproject.toml
└── README.md
```

---

## الـ Hooks المطلوبة في smart_erp_ai

```python
# hooks.py

required_apps = ["frappe", "erpnext", "hrms", "frappe_assistant_core"]

app_include_js = "/assets/smart_erp_ai/js/smart_erp_ai_widget.js"
app_include_css = "/assets/smart_erp_ai/css/smart_erp_ai.css"

after_install = "smart_erp_ai.install.after_install"

# WhatsApp
website_route_rules = [
    {"from_route": "/whatsapp/webhook", "to_route": "smart_erp_ai.whatsapp.handle_webhook"}
]
override_whitelisted_methods = {
    "smart_erp_ai.whatsapp.handle_webhook": "smart_erp_ai.whatsapp.handle_webhook"
}

# أدوات MCP للتكامل مع frappe_assistant_core
assistant_tools = [
    # "smart_erp_ai.assistant_tools.sales_order.SalesOrderTool",
    # ...
]
```

---

## ملاحظات

- **الترخيص**: hr_assistant (MIT)، frappe_assistant_core (AGPL-3.0). التأكد من التوافق.
- **البيانات الموجودة**: إن كان hr_assistant مستخدماً، يلزم migration script لنسخ Conversations و Messages.
- **اللغة**: الحفاظ على دعم العربية والإنجليزية كما في hr_assistant.
