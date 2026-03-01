// Smart ERP AI Chat Widget
// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// Supports Arabic (RTL) and English (LTR)

class SmartERPAIWidget {
	constructor() {
		this.conversation_id = null;
		this.is_open = false;
		this.is_loading = false;
		this.messages = [];
		this.isRTL = false;
		this.pendingAttachments = []; // Store uploaded files

		this.init();
	}

	async init() {
		// Check if assistant is enabled
		const status = await this.checkStatus();
		if (!status.enabled) {
			return;
		}

		// Detect RTL language (Arabic)
		this.isRTL = document.documentElement.lang === "ar" ||
					 document.documentElement.dir === "rtl" ||
					 (frappe.boot && frappe.boot.lang === "ar");

		this.createWidget();
		this.bindEvents();
	}

	async checkStatus() {
		try {
			const response = await frappe.call({
				method: "smart_erp_ai.api.check_status",
			});
			return response.message || { enabled: false };
		} catch (e) {
			console.error("Smart ERP AI status check failed:", e);
			return { enabled: false };
		}
	}

	// Get translated text - supports Arabic
	getText(key) {
		const translations = {
			ar: {
				"Smart ERP AI": "مساعد ERP الذكي",
				"New Conversation": "محادثة جديدة",
				"Minimize": "تصغير",
				"Close": "إغلاق",
				"Request Leave": "طلب إجازة",
				"Check Balance": "رصيد الإجازات",
				"Policy Info": "معلومات السياسات",
				"Type your message...": "اكتب رسالتك...",
				"Success!": "تم بنجاح!",
				"View Document": "عرض المستند",
				"Escalated to HR": "تم التصعيد للموارد البشرية",
				"Error": "خطأ",
				"Confirm Request": "تأكيد الطلب",
				"Please confirm the following request:": "يرجى تأكيد الطلب التالي:",
				"Confirm": "تأكيد",
				"Sorry, I'm having trouble connecting. Please try again later.": "عذراً، أواجه مشكلة في الاتصال. يرجى المحاولة لاحقاً.",
				"Sorry, I couldn't start a new conversation.": "عذراً، لم أتمكن من بدء محادثة جديدة.",
				"An error occurred.": "حدث خطأ.",
				"Sorry, I couldn't process your message. Please try again.": "عذراً، لم أتمكن من معالجة رسالتك. يرجى المحاولة مرة أخرى.",
				"Sorry, I couldn't complete the request.": "عذراً، لم أتمكن من إكمال الطلب.",
				"I would like to request leave": "أرغب في طلب إجازة",
				"What is my leave balance?": "ما هو رصيد إجازاتي؟",
				"Tell me about the leave policy": "أخبرني عن سياسة الإجازات",
				"Attach File": "إرفاق ملف",
				"Remove": "إزالة",
				"Uploading...": "جاري الرفع...",
				"File uploaded": "تم رفع الملف",
				"Upload failed": "فشل الرفع",
				"File too large. Maximum size is 10MB.": "الملف كبير جداً. الحد الأقصى 10 ميجابايت.",
				"Invalid file type. Allowed: images, PDF, documents.": "نوع ملف غير مسموح. المسموح: صور، PDF، مستندات."
			}
		};

		// Check if Arabic and translation exists
		if (this.isRTL && translations.ar[key]) {
			return translations.ar[key];
		}
		// Fallback to Frappe translation or original
		return __(key);
	}

	createWidget() {
		// Create floating button
		this.button = $(`
			<div class="hr-assistant-button" title="${this.getText("Smart ERP AI")}">
				<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
				</svg>
			</div>
		`);

		// Create chat window
		this.window = $(`
			<div class="hr-assistant-window" style="display: none;">
				<div class="hr-assistant-header">
					<div class="hr-assistant-title">
						<span class="indicator green"></span>
						${this.getText("Smart ERP AI")}
					</div>
					<div class="hr-assistant-actions">
						<button class="btn btn-xs btn-default hr-assistant-new" title="${this.getText("New Conversation")}">
							<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M12 5v14M5 12h14"/>
							</svg>
						</button>
						<button class="btn btn-xs btn-default hr-assistant-minimize" title="${this.getText("Minimize")}">
							<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M5 12h14"/>
							</svg>
						</button>
						<button class="btn btn-xs btn-default hr-assistant-close" title="${this.getText("Close")}">
							<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M18 6L6 18M6 6l12 12"/>
							</svg>
						</button>
					</div>
				</div>
				<div class="hr-assistant-messages">
					<div class="hr-assistant-messages-inner"></div>
				</div>
				<div class="hr-assistant-input-area">
					<div class="hr-assistant-quick-actions">
						<button class="btn btn-xs" data-action="leave">${this.getText("Request Leave")}</button>
						<button class="btn btn-xs" data-action="balance">${this.getText("Check Balance")}</button>
						<button class="btn btn-xs" data-action="policy">${this.getText("Policy Info")}</button>
					</div>
					<div class="hr-assistant-attachments-preview"></div>
					<div class="hr-assistant-input-wrapper">
						<input type="file" class="hr-assistant-file-input" accept="image/*,.pdf,.doc,.docx" multiple style="display: none;">
						<button class="btn btn-default btn-sm hr-assistant-attach" title="${this.getText("Attach File")}">
							<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
							</svg>
						</button>
						<textarea class="hr-assistant-input" placeholder="${this.getText("Type your message...")}" rows="1"></textarea>
						<button class="btn btn-primary btn-sm hr-assistant-send" disabled>
							<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
							</svg>
						</button>
					</div>
				</div>
			</div>
		`);

		// Append to body
		$("body").append(this.button).append(this.window);

		// Store references
		this.$messages = this.window.find(".hr-assistant-messages-inner");
		this.$input = this.window.find(".hr-assistant-input");
		this.$sendBtn = this.window.find(".hr-assistant-send");
		this.$attachBtn = this.window.find(".hr-assistant-attach");
		this.$fileInput = this.window.find(".hr-assistant-file-input");
		this.$attachmentsPreview = this.window.find(".hr-assistant-attachments-preview");
	}

	bindEvents() {
		// Toggle chat window
		this.button.on("click", () => this.toggle());

		// Close button
		this.window.find(".hr-assistant-close").on("click", () => this.close());

		// Minimize button
		this.window.find(".hr-assistant-minimize").on("click", () => this.minimize());

		// New conversation button
		this.window.find(".hr-assistant-new").on("click", () => this.startNewConversation());

		// Send message
		this.$sendBtn.on("click", () => this.sendMessage());

		// Input handling
		this.$input.on("input", () => {
			this.autoResizeInput();
			this.updateSendButton();
		});

		this.$input.on("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				this.sendMessage();
			}
		});

		// Quick actions
		this.window.find(".hr-assistant-quick-actions button").on("click", (e) => {
			const action = $(e.currentTarget).data("action");
			this.handleQuickAction(action);
		});

		// File attachment
		this.$attachBtn.on("click", () => this.$fileInput.click());
		this.$fileInput.on("change", (e) => this.handleFileSelect(e));
	}

	async toggle() {
		if (this.is_open) {
			this.close();
		} else {
			await this.open();
		}
	}

	async open() {
		this.is_open = true;
		this.button.addClass("active");
		this.window.show().addClass("open");

		// Load conversation if not loaded
		if (this.messages.length === 0) {
			await this.loadConversation();
		}

		// Focus input
		this.$input.focus();
	}

	close() {
		this.is_open = false;
		this.button.removeClass("active");
		this.window.removeClass("open").hide();
	}

	minimize() {
		this.close();
	}

	async loadConversation() {
		this.setLoading(true);

		try {
			// Get welcome message and any existing conversation
			const response = await frappe.call({
				method: "smart_erp_ai.api.get_welcome_message",
			});

			if (response.message && !response.message.error) {
				// Check for existing conversation
				const historyResponse = await frappe.call({
					method: "smart_erp_ai.api.get_conversation_history",
				});

				if (
					historyResponse.message &&
					!historyResponse.message.error &&
					historyResponse.message.messages &&
					historyResponse.message.messages.length > 0
				) {
					// Load existing messages
					this.conversation_id = historyResponse.message.conversation_id;
					this.messages = historyResponse.message.messages;
					this.renderMessages();
				} else {
					// Show welcome message
					this.addMessage("assistant", response.message.message);
				}
			}
		} catch (e) {
			console.error("Failed to load conversation:", e);
			this.addMessage(
				"assistant",
				this.getText("Sorry, I'm having trouble connecting. Please try again later.")
			);
		}

		this.setLoading(false);
	}

	async startNewConversation() {
		this.setLoading(true);
		this.messages = [];
		this.$messages.empty();

		try {
			const response = await frappe.call({
				method: "smart_erp_ai.api.start_new_conversation",
			});

			if (response.message && !response.message.error) {
				this.conversation_id = response.message.conversation_id;
				this.addMessage("assistant", response.message.message);
			}
		} catch (e) {
			console.error("Failed to start new conversation:", e);
			this.addMessage("assistant", this.getText("Sorry, I couldn't start a new conversation."));
		}

		this.setLoading(false);
	}

	async sendMessage() {
		const message = this.$input.val().trim();
		const hasAttachments = this.pendingAttachments.length > 0;

		if ((!message && !hasAttachments) || this.is_loading) return;

		// Clear input
		this.$input.val("");
		this.autoResizeInput();

		// Prepare attachment info for display and sending
		const attachments = [...this.pendingAttachments];
		this.clearAttachments();
		this.updateSendButton();

		// Add user message to UI (with attachment info)
		let displayMessage = message;
		if (attachments.length > 0) {
			const attachmentNames = attachments.map(a => a.file_name).join(", ");
			displayMessage += (message ? "\n" : "") + "📎 " + attachmentNames;
		}
		this.addMessage("user", displayMessage || "📎 " + attachments.map(a => a.file_name).join(", "));

		// Send to server
		this.setLoading(true);

		try {
			const response = await frappe.call({
				method: "smart_erp_ai.api.send_message",
				args: {
					message: message,
					conversation_id: this.conversation_id,
					attachments: JSON.stringify(attachments),
				},
			});

			if (response.message) {
				if (response.message.error) {
					this.addMessage("assistant", response.message.message || this.getText("An error occurred."));
				} else {
					this.conversation_id = response.message.conversation_id;
					this.addMessage("assistant", response.message.response);

					// Handle any action results
					if (response.message.action_result) {
						this.handleActionResult(response.message.action_result);
					}
				}
			}
		} catch (e) {
			console.error("Failed to send message:", e);
			this.addMessage("assistant", this.getText("Sorry, I couldn't process your message. Please try again."));
		}

		this.setLoading(false);
	}

	handleQuickAction(action) {
		const messages = {
			leave: this.getText("I would like to request leave"),
			balance: this.getText("What is my leave balance?"),
			policy: this.getText("Tell me about the leave policy"),
		};

		if (messages[action]) {
			this.$input.val(messages[action]);
			this.sendMessage();
		}
	}

	// File upload handling
	handleFileSelect(e) {
		const files = Array.from(e.target.files);
		const maxSize = 10 * 1024 * 1024; // 10MB
		const allowedTypes = [
			"image/jpeg", "image/png", "image/gif", "image/webp",
			"application/pdf",
			"application/msword",
			"application/vnd.openxmlformats-officedocument.wordprocessingml.document"
		];

		for (const file of files) {
			// Validate file size
			if (file.size > maxSize) {
				frappe.show_alert({
					message: this.getText("File too large. Maximum size is 10MB."),
					indicator: "red"
				});
				continue;
			}

			// Validate file type
			if (!allowedTypes.includes(file.type)) {
				frappe.show_alert({
					message: this.getText("Invalid file type. Allowed: images, PDF, documents."),
					indicator: "red"
				});
				continue;
			}

			// Upload the file
			this.uploadFile(file);
		}

		// Clear input for re-selection
		this.$fileInput.val("");
	}

	async uploadFile(file) {
		const previewId = "attachment-" + Date.now();

		// Show upload preview
		this.addAttachmentPreview(previewId, file.name, true);

		try {
			// Use Frappe's file upload
			const response = await new Promise((resolve, reject) => {
				const formData = new FormData();
				formData.append("file", file);
				formData.append("is_private", "1");
				formData.append("folder", "Home/Attachments");

				$.ajax({
					url: "/api/method/upload_file",
					type: "POST",
					data: formData,
					processData: false,
					contentType: false,
					headers: {
						"X-Frappe-CSRF-Token": frappe.csrf_token
					},
					success: (r) => resolve(r),
					error: (xhr) => reject(xhr)
				});
			});

			if (response.message && response.message.file_url) {
				// Update preview to show success
				this.updateAttachmentPreview(previewId, {
					name: response.message.name,
					file_name: file.name,
					file_url: response.message.file_url,
					uploading: false
				});

				// Add to pending attachments
				this.pendingAttachments.push({
					name: response.message.name,
					file_name: file.name,
					file_url: response.message.file_url
				});

				this.updateSendButton();
			}
		} catch (e) {
			console.error("Upload failed:", e);
			// Remove failed preview
			this.$attachmentsPreview.find(`[data-id="${previewId}"]`).remove();
			frappe.show_alert({
				message: this.getText("Upload failed"),
				indicator: "red"
			});
		}
	}

	addAttachmentPreview(id, fileName, uploading = false) {
		const isImage = /\.(jpg|jpeg|png|gif|webp)$/i.test(fileName);
		const icon = isImage ? "image" : "file";

		const $preview = $(`
			<div class="hr-assistant-attachment-item" data-id="${id}">
				<span class="attachment-icon">
					${isImage ?
						'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>' :
						'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>'
					}
				</span>
				<span class="attachment-name">${fileName}</span>
				${uploading ?
					'<span class="attachment-loading"><span class="spinner-border spinner-border-sm"></span></span>' :
					`<button class="attachment-remove" title="${this.getText("Remove")}">
						<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
					</button>`
				}
			</div>
		`);

		// Bind remove event
		$preview.find(".attachment-remove").on("click", () => this.removeAttachment(id));

		this.$attachmentsPreview.append($preview);
	}

	updateAttachmentPreview(id, data) {
		const $item = this.$attachmentsPreview.find(`[data-id="${id}"]`);
		if ($item.length) {
			$item.attr("data-file-name", data.name);
			$item.find(".attachment-loading").replaceWith(
				`<button class="attachment-remove" title="${this.getText("Remove")}">
					<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
				</button>`
			);
			$item.find(".attachment-remove").on("click", () => this.removeAttachment(id));
		}
	}

	removeAttachment(id) {
		const $item = this.$attachmentsPreview.find(`[data-id="${id}"]`);
		const fileName = $item.attr("data-file-name");

		// Remove from pending attachments
		this.pendingAttachments = this.pendingAttachments.filter(a => a.name !== fileName);

		// Remove preview
		$item.remove();
		this.updateSendButton();
	}

	clearAttachments() {
		this.pendingAttachments = [];
		this.$attachmentsPreview.empty();
	}

	handleActionResult(result) {
		if (!result) return;

		if (result.type === "success") {
			// Show success message with link to document
			const docLink = `/app/${frappe.router.slug(result.doctype)}/${result.docname}`;
			this.addSystemMessage(
				`<div class="hr-assistant-action-result success">
					<strong>${this.getText("Success!")}</strong><br>
					${result.message}<br>
					<a href="${docLink}" target="_blank">${this.getText("View Document")}</a>
				</div>`
			);
		} else if (result.type === "confirmation") {
			// Show confirmation dialog
			this.showConfirmation(result);
		} else if (result.type === "escalated") {
			this.addSystemMessage(
				`<div class="hr-assistant-action-result info">
					<strong>${this.getText("Escalated to HR")}</strong><br>
					${result.message}
				</div>`
			);
		} else if (result.type === "error") {
			this.addSystemMessage(
				`<div class="hr-assistant-action-result error">
					<strong>${this.getText("Error")}</strong><br>
					${result.message}
				</div>`
			);
		}
	}

	showConfirmation(data) {
		const dialog = new frappe.ui.Dialog({
			title: this.getText("Confirm Request"),
			fields: [
				{
					fieldtype: "HTML",
					options: `<div class="hr-assistant-confirmation">
						<p>${this.getText("Please confirm the following request:")}</p>
						<pre>${JSON.stringify(data.entities, null, 2)}</pre>
					</div>`,
				},
			],
			primary_action_label: this.getText("Confirm"),
			primary_action: async () => {
				dialog.hide();
				this.setLoading(true);

				try {
					const response = await frappe.call({
						method: "smart_erp_ai.api.confirm_action",
						args: {
							conversation_id: this.conversation_id,
							action_type: data.intent,
							entities: JSON.stringify(data.entities),
						},
					});

					if (response.message && response.message.result) {
						this.handleActionResult(response.message.result);
					}
				} catch (e) {
					console.error("Confirmation failed:", e);
					this.addMessage("assistant", this.getText("Sorry, I couldn't complete the request."));
				}

				this.setLoading(false);
			},
		});

		dialog.show();
	}

	addMessage(role, content) {
		const message = { role, content, timestamp: new Date().toISOString() };
		this.messages.push(message);

		const $message = $(`
			<div class="hr-assistant-message ${role}">
				<div class="hr-assistant-message-content">${this.formatMessage(content)}</div>
				<div class="hr-assistant-message-time">${this.formatTime(message.timestamp)}</div>
			</div>
		`);

		this.$messages.append($message);
		this.scrollToBottom();
	}

	addSystemMessage(html) {
		const $message = $(`
			<div class="hr-assistant-message system">
				<div class="hr-assistant-message-content">${html}</div>
			</div>
		`);

		this.$messages.append($message);
		this.scrollToBottom();
	}

	renderMessages() {
		this.$messages.empty();
		for (const msg of this.messages) {
			const $message = $(`
				<div class="hr-assistant-message ${msg.role}">
					<div class="hr-assistant-message-content">${this.formatMessage(msg.content)}</div>
					<div class="hr-assistant-message-time">${this.formatTime(msg.timestamp)}</div>
				</div>
			`);
			this.$messages.append($message);
		}
		this.scrollToBottom();
	}

	formatMessage(content) {
		// Basic markdown-like formatting
		return content
			.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
			.replace(/\*(.*?)\*/g, "<em>$1</em>")
			.replace(/\n/g, "<br>");
	}

	formatTime(timestamp) {
		if (!timestamp) return "";
		const date = new Date(timestamp);
		// Use Arabic locale for RTL
		const locale = this.isRTL ? "ar-SA" : undefined;
		return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
	}

	scrollToBottom() {
		const container = this.window.find(".hr-assistant-messages");
		container.scrollTop(container[0].scrollHeight);
	}

	autoResizeInput() {
		this.$input.css("height", "auto");
		this.$input.css("height", Math.min(this.$input[0].scrollHeight, 100) + "px");
	}

	updateSendButton() {
		const hasText = this.$input.val().trim().length > 0;
		const hasAttachments = this.pendingAttachments.length > 0;
		this.$sendBtn.prop("disabled", (!hasText && !hasAttachments) || this.is_loading);
	}

	setLoading(loading) {
		this.is_loading = loading;
		this.updateSendButton();

		if (loading) {
			this.$messages.find(".hr-assistant-typing").remove();
			this.$messages.append(`
				<div class="hr-assistant-message assistant hr-assistant-typing">
					<div class="hr-assistant-message-content">
						<span class="typing-indicator">
							<span></span><span></span><span></span>
						</span>
					</div>
				</div>
			`);
			this.scrollToBottom();
		} else {
			this.$messages.find(".hr-assistant-typing").remove();
		}
	}
}

// Initialize widget when app is ready
$(document).on("app_ready", function () {
	// Only initialize for logged-in users
	if (frappe.session.user !== "Guest") {
		window.smartErpAi = new SmartERPAIWidget();
	}
});
