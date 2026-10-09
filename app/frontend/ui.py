"""
Infinity AI - Master Desktop Workspace & AI Assistant
Upgraded offline-first architecture integrating:
- Advanced Chat & ChatGPT-style UX
- PDF Viewer & Multi-Document Workspace
- Intelligent Model Router & Model Manager
- Safe Tool Registry & AI Agents Orchestrator
- Projects, Memory & Knowledge Base
- OCR & Multimodal Vision
- Live Hardware Monitoring & Diagnostics
- USB Authorization Protection
"""

import hashlib
import os
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, Optional

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

from frontend.theme import THEME, get_current_theme, toggle_theme, register_theme_listener

from backend.ai_engine import ask_document, check_ollama, stop_generation, preload_model, is_summary_intent
from backend.capability_engine import check_unsupported_capability
from backend.datetime_engine import is_datetime_query, handle_datetime_query
from backend.chunker import create_chunks
from backend.db import get_conversations, get_projects
from backend.diagnostics import get_hardware_metrics, get_full_diagnostics
from backend.model_manager import get_all_models
from backend.ocr_vision import analyze_image_with_vision
from backend.pdf_processor import extract_full_text, extract_text_from_pdf
from backend.projects import project_service
from backend.rag_engine import index_any_file, parse_any_document, retrieve_context_with_citations
from backend.router import route_model
import backend.security as security

def verify_usb_authorization(*args, **kwargs):
    return security.verify_usb_authorization(*args, **kwargs)
from backend.slash_commands import process_slash_command
from backend.summarizer import stop_summary, summarize_document
from backend.vector_store import add_chunks, document_hash, document_needs_indexing, remove_document_chunks
from frontend.artifact_viewer import ArtifactViewer
from frontend.branding import load_logo_image
from frontend.chat_panel import ChatPanel
from frontend.lock_overlay import WorkspaceLockOverlay
from frontend.pdf_viewer import PDFViewer
from frontend.sidebar import Sidebar
from frontend.toast import ToastNotification
from frontend.welcome_screen import WelcomeScreen
from frontend.workspaces import (
    ProjectsWorkspace,
    ResearchWorkspace,
    CodeWorkspace,
    AgentsWorkspace,
    MemoryWorkspace,
    ModelsWorkspace,
    DiagnosticsWorkspace,
    StudyWorkspace,
    SettingsWorkspace
)


class DocumentAssistant(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        curr_mode = "Light" if get_current_theme() == "light" else "Dark"
        ctk.set_appearance_mode(curr_mode)
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.configure(fg_color=THEME["bg_primary"])
        self.title("Infinity AI | Private Local Intelligence")
        self.geometry("1340x860")
        self.minsize(1050, 700)
        self.loaded = {}
        self.selected_file = None
        self.selected_doc_id = None
        self.ai_running = False
        self.summary_running = False
        self.current_nav = "Chat"
        self.doc_ratio = 0.62
        self._drop_queue = []
        self._drop_active = False

        self._build()
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._handle_file_drop)
        self._bind_keyboard_shortcuts()
        register_theme_listener(self.apply_theme)
        self._initial_security_check()
        self._startup_job = self.after(300, self._startup_check)
        self._hw_poll_job = self.after(2000, self._start_hardware_polling)

    def _build(self):
        # 0. Full Workspace Lock Overlay Container
        self.lock_overlay = WorkspaceLockOverlay(
            self,
            on_unlocked=self._on_workspace_unlocked,
            on_read_only=self._on_read_only_selected,
            on_exit=self.destroy
        )
        # 1. Header Bar (Clean startup-grade top bar)
        self.head = ctk.CTkFrame(self, height=48, fg_color=THEME["bg_secondary"], corner_radius=0)
        self.head.pack(fill="x")
        self.logo_image = load_logo_image((22, 22))
        logo = ctk.CTkLabel(
            self.head,
            text="",
            image=self.logo_image,
            fg_color="transparent"
        )
        logo.pack(side="left", padx=(14, 6))
        logo.bind("<Button-1>", lambda e: self.handle_nav_switch("Chat"))

        self.brand_title = ctk.CTkLabel(
            self.head,
            text="Infinity AI",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=THEME["text_primary"],
            cursor="hand2"
        )
        self.brand_title.pack(side="left")
        self.brand_title.bind("<Button-1>", lambda e: self.handle_nav_switch("Chat"))

        self.brand_tagline = ctk.CTkLabel(
            self.head,
            text="| Private Local Intelligence",
            font=ctk.CTkFont(size=12),
            text_color=THEME["text_muted"]
        )
        self.brand_tagline.pack(side="left", padx=(6, 0))

        # Active document indicator
        self.doc_indicator = ctk.CTkButton(
            self.head,
            text="",
            height=26,
            fg_color=THEME["accent_dim"],
            hover_color=THEME["bg_panel"],
            text_color=THEME["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=6,
            command=lambda: self.handle_nav_switch("Documents")
        )

        self.file_label = ctk.CTkLabel(
            self.head,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=THEME["text_muted"],
            anchor="w"
        )

        self.proj_badge = ctk.CTkLabel(
            self.head,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME["accent"],
            fg_color=THEME["bg_panel"],
            corner_radius=6,
            padx=8,
            pady=3
        )

        # Theme Toggle Button (Rightmost)
        curr_t = get_current_theme()
        theme_icon = "☀️" if curr_t == "dark" else "🌙"
        self.theme_toggle_btn = ctk.CTkButton(
            self.head,
            text=theme_icon,
            width=32,
            height=28,
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            font=ctk.CTkFont(size=13),
            corner_radius=6,
            command=self.handle_theme_toggle
        )
        self.theme_toggle_btn.pack(side="right", padx=(2, 12))

        # Primary Top Bar Action: + New Chat
        self.new_chat_top_btn = ctk.CTkButton(
            self.head,
            text="＋ New Chat",
            width=96,
            height=28,
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            text_color=THEME["accent_text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=6,
            command=self.handle_new_chat
        )
        self.new_chat_top_btn.pack(side="right", padx=4)

        # Preserved reference for backward compatibility (Zero-history mode: not packed in top bar)
        self.history_top_btn = ctk.CTkButton(
            self.head,
            text="🕘 History",
            width=80,
            height=28,
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_primary"],
            font=ctk.CTkFont(size=11),
            corner_radius=6,
            command=self.open_history_modal
        )

        # Contextual: Add Document
        self.add_doc_top_btn = ctk.CTkButton(
            self.head,
            text="＋ Add Document",
            width=116,
            height=28,
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_primary"],
            font=ctk.CTkFont(size=11),
            corner_radius=6,
            command=self.add_pdf
        )
        self.add_doc_top_btn.pack(side="right", padx=4)

        # Preserved references
        self.summary_btn = ctk.CTkButton(self.head, text="Summarize", command=self.handle_doc_summary)

        # USB Key status pill
        self.usb_pill = ctk.CTkLabel(
            self.head,
            text="● Secured",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=THEME["success"],
            fg_color=THEME["success_bg"],
            corner_radius=6,
            padx=8,
            pady=3
        )
        self.usb_pill.pack(side="right", padx=(4, 8))

        # 2. Main Body Container
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.body.grid_columnconfigure(1, weight=1)
        self.body.grid_rowconfigure(0, weight=1)

        # Sidebar with full navigation callbacks
        self.sidebar = Sidebar(
            self.body,
            on_add=self.add_pdf,
            on_select=self.open_document,
            on_remove=self.remove_document,
            on_nav_change=self.handle_nav_switch,
            on_new_chat=self.handle_new_chat,
            on_recent=lambda: self.chat._open_history_modal(),
            on_search=self.open_command_palette,
            on_voice=lambda: self.chat.handle_voice(),
            on_vision=lambda: self.chat.handle_attach(),
            on_security=lambda: self.handle_nav_switch("Diagnostics"),
            on_select_chat=self.load_selected_chat,
            width=230
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # Workspace Center Container
        self.center = ctk.CTkFrame(self.body, fg_color="transparent")
        self.center.grid(row=0, column=1, sticky="nsew")
        self.center.grid_columnconfigure(0, weight=62)
        self.center.grid_columnconfigure(1, weight=0)
        self.center.grid_columnconfigure(2, weight=38)
        self.center.grid_rowconfigure(0, weight=1)

        self.splitter = ctk.CTkFrame(self.center, width=10, fg_color=THEME["bg_panel"], corner_radius=0, cursor="sb_h_double_arrow")
        self.splitter.grid(row=0, column=1, sticky="ns")
        self.splitter.grid_remove()
        self.splitter.bind("<Button-1>", self._begin_split_drag)
        self.splitter.bind("<B1-Motion>", self._drag_split)
        self.splitter.bind("<Enter>", lambda e: self.splitter.configure(fg_color=THEME["accent_dim"]))
        self.splitter.bind("<Leave>", lambda e: self.splitter.configure(fg_color=THEME["bg_panel"]))

        # Workspaces
        # A. Documents & PDF Workspace (Split: PDF Viewer on col 0, Chat on col 2)
        self.pdf = PDFViewer(self.center, ask_ai_callback=self.handle_page_question)
        self.pdf.grid(row=0, column=0, sticky="nsew")
        self.pdf.grid_remove()

        # Clean empty state for PDF viewer pane when no file is selected
        self.pdf_empty_frame = ctk.CTkFrame(self.center, fg_color=THEME["bg_secondary"], corner_radius=0)
        p_box = ctk.CTkFrame(self.pdf_empty_frame, fg_color="transparent")
        p_box.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(p_box, text="📄", font=ctk.CTkFont(size=36)).pack(pady=(0, 6))
        self.pdf_empty_title = ctk.CTkLabel(p_box, text="No Document Open", font=ctk.CTkFont(size=16, weight="bold"), text_color=THEME["text_primary"])
        self.pdf_empty_title.pack(pady=(0, 4))
        self.pdf_empty_sub = ctk.CTkLabel(p_box, text="Open or drop a PDF to view pages alongside AI chat.", font=ctk.CTkFont(size=12), text_color=THEME["text_muted"])
        self.pdf_empty_sub.pack(pady=(0, 16))
        self.pdf_empty_btn = ctk.CTkButton(p_box, text="＋ Open PDF Document", font=ctk.CTkFont(size=12, weight="bold"), fg_color=THEME["accent"], hover_color=THEME["accent_hover"], text_color=THEME["accent_text"], height=32, command=self.add_pdf)
        self.pdf_empty_btn.pack()
        self.pdf_empty_frame.grid(row=0, column=0, sticky="nsew")
        self.pdf_empty_frame.grid_remove()

        self.welcome = WelcomeScreen(
            self.center,
            on_add_document=self.add_pdf,
            on_ask_anything=lambda: (self.handle_nav_switch("Chat"), self.chat.input.focus_set()),
            on_open_projects=lambda: self.handle_nav_switch("Projects"),
            on_analyze_doc=lambda: self.handle_nav_switch("Documents"),
            on_start_coding=lambda: self.handle_nav_switch("Code")
        )
        self.welcome.grid(row=0, column=0, sticky="nsew")

        self.chat = ChatPanel(
            self.center,
            on_send_message=self.handle_ai_query,
            on_stop=self.stop_ai_generation,
            on_close_doc=self.close_active_document,
            on_add_document=self.add_pdf,
            on_open_projects=lambda: self.handle_nav_switch("Projects"),
            on_open_pdf_viewer=lambda: self.handle_nav_switch("Documents"),
            width=460
        )
        self.chat.grid(row=0, column=2, sticky="nsew")

        # B. Specialized Workspaces
        self.ws_projects = ProjectsWorkspace(self.center, on_project_changed=self.handle_project_changed)
        self.ws_artifacts = ArtifactViewer(self.center, on_close=lambda: self.handle_nav_switch("Chat"))
        self.ws_research = ResearchWorkspace(self.center)
        self.ws_study = StudyWorkspace(self.center)
        self.ws_code = CodeWorkspace(self.center)
        self.ws_agents = AgentsWorkspace(self.center)
        self.ws_memory = MemoryWorkspace(self.center)
        self.ws_models = ModelsWorkspace(self.center)
        self.ws_diagnostics = DiagnosticsWorkspace(self.center)
        self.ws_settings = SettingsWorkspace(self.center)

        self.specialized_views = {
            "Projects": self.ws_projects,
            "Artifacts": self.ws_artifacts,
            "Research": self.ws_research,
            "Study": self.ws_study,
            "Code": self.ws_code,
            "Agents": self.ws_agents,
            "Memory": self.ws_memory,
            "Models": self.ws_models,
            "Diagnostics": self.ws_diagnostics,
            "Security": self.ws_diagnostics,
            "Settings": self.ws_settings,
        }

        # Initialize primary screen as full-width Chat
        self.handle_nav_switch("Chat")

        # 3. Bottom Status Bar with Hardware Monitor
        self.status_bar = ctk.CTkFrame(self, height=28, fg_color=THEME["bg_secondary"], corner_radius=0)
        self.status_bar.pack(fill="x")

        self.status = ctk.CTkLabel(self.status_bar, text="Ready", anchor="w", font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"])
        self.status.pack(side="left", padx=14)

        # Telemetry is preserved for Diagnostics workspace, but removed from customer-facing status bar
        self.hw_label = ctk.CTkLabel(self.status_bar, text="", anchor="e", font=ctk.CTkFont(size=11), text_color=THEME["text_muted"])

    def _begin_split_drag(self, event):
        self._drag_split(event)

    def _drag_split(self, event):
        if self.current_nav != "Documents":
            return
        width = max(1, self.center.winfo_width())
        pointer_x = event.x_root - self.center.winfo_rootx()
        ratio = max(0.3, min(0.7, pointer_x / width))
        self.doc_ratio = ratio
        self._apply_split_layout()

    def _apply_split_layout(self):
        doc_weight = max(1, int(self.doc_ratio * 100))
        chat_weight = max(1, 100 - doc_weight)
        self.center.grid_columnconfigure(0, weight=doc_weight)
        self.center.grid_columnconfigure(1, weight=0)
        self.center.grid_columnconfigure(2, weight=chat_weight)
        self.center.update_idletasks()

    def handle_theme_toggle(self):
        new_theme = toggle_theme()
        icon = "☀️" if new_theme == "dark" else "🌙"
        if hasattr(self, "theme_toggle_btn"):
            self.theme_toggle_btn.configure(text=icon)
        self.apply_theme(new_theme)

    def apply_theme(self, new_theme=None):
        try:
            self.configure(fg_color=THEME["bg_primary"])
            self.head.configure(fg_color=THEME["bg_secondary"])
            self.new_chat_top_btn.configure(fg_color=THEME["accent"], hover_color=THEME["accent_hover"], text_color=THEME["accent_text"])
            self.history_top_btn.configure(fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], text_color=THEME["text_primary"])
            self.add_doc_top_btn.configure(fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], text_color=THEME["text_primary"])
            if hasattr(self, "brand_title"):
                self.brand_title.configure(text_color=THEME["text_primary"])
            if hasattr(self, "brand_tagline"):
                self.brand_tagline.configure(text_color=THEME["text_muted"])
            if hasattr(self, "file_label"):
                self.file_label.configure(text_color=THEME["text_muted"])
            if hasattr(self, "usb_pill"):
                if getattr(self, "_last_auth_state", False):
                    self.usb_pill.configure(fg_color=THEME["success_bg"], text_color=THEME["success"])
                else:
                    self.usb_pill.configure(fg_color=THEME["error_bg"], text_color=THEME["error"])
            if hasattr(self, "doc_indicator"):
                self.doc_indicator.configure(fg_color=THEME["accent_dim"], text_color=THEME["accent_hover"])
            if hasattr(self, "proj_badge"):
                self.proj_badge.configure(fg_color=THEME["bg_panel"], text_color=THEME["accent"])
            if hasattr(self, "theme_toggle_btn"):
                icon = "☀️" if get_current_theme() == "dark" else "🌙"
                self.theme_toggle_btn.configure(text=icon, hover_color=THEME["bg_hover"])
            if hasattr(self, "status_bar"):
                self.status_bar.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "status"):
                self.status.configure(text_color=THEME["text_secondary"])
            if hasattr(self, "hw_label"):
                self.hw_label.configure(text_color=THEME["text_muted"])
            if hasattr(self, "splitter"):
                self.splitter.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "pdf_empty_frame"):
                self.pdf_empty_frame.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "pdf_empty_title"):
                self.pdf_empty_title.configure(text_color=THEME["text_primary"])
            if hasattr(self, "pdf_empty_sub"):
                self.pdf_empty_sub.configure(text_color=THEME["text_muted"])
            if hasattr(self, "pdf_empty_btn"):
                self.pdf_empty_btn.configure(fg_color=THEME["accent"], hover_color=THEME["accent_hover"], text_color=THEME["accent_text"])
            if hasattr(self, "sidebar") and hasattr(self.sidebar, "apply_theme"):
                self.sidebar.apply_theme(new_theme)
            if hasattr(self, "chat") and hasattr(self.chat, "apply_theme"):
                self.chat.apply_theme(new_theme)
            if hasattr(self, "pdf") and hasattr(self.pdf, "apply_theme"):
                self.pdf.apply_theme(new_theme)
            if hasattr(self, "welcome") and hasattr(self.welcome, "apply_theme"):
                self.welcome.apply_theme(new_theme)
            if hasattr(self, "lock_overlay") and hasattr(self.lock_overlay, "apply_theme"):
                self.lock_overlay.apply_theme(new_theme)
            if hasattr(self, "specialized_views"):
                for view in self.specialized_views.values():
                    if hasattr(view, "apply_theme"):
                        view.apply_theme(new_theme)
        except Exception:
            pass

    def open_history_modal(self):
        if hasattr(self, "chat") and hasattr(self.chat, "_open_history_modal"):
            self.chat._open_history_modal()

    def load_selected_chat(self, cid: str):
        self.handle_nav_switch("Chat")
        if hasattr(self, "chat") and hasattr(self.chat, "load_conversation"):
            self.chat.load_conversation(cid)

    def handle_nav_switch(self, nav_key: str):
        self.current_nav = nav_key

        # Hide all specialized views
        for view in self.specialized_views.values():
            view.grid_forget()

        if nav_key == "Chat":
            self.pdf.grid_remove()
            self.pdf_empty_frame.grid_remove()
            self.welcome.grid_remove()
            self.splitter.grid_remove()
            self.chat.grid(row=0, column=0, columnspan=3, sticky="nsew")
            self.center.grid_columnconfigure(0, weight=1)
            self.center.grid_columnconfigure(1, weight=0)
            self.center.grid_columnconfigure(2, weight=0)
            self.sidebar.select_nav("Chat", notify=False)

        elif nav_key == "Documents":
            self.welcome.grid_remove()
            if self.selected_file and os.path.isfile(self.selected_file) and self.selected_file.lower().endswith(".pdf"):
                self.pdf_empty_frame.grid_remove()
                self.pdf.grid(row=0, column=0, sticky="nsew")
                if not self.pdf.doc or self.pdf.path != str(Path(self.selected_file).resolve()):
                    try:
                        self.pdf.load_pdf(self.selected_file)
                    except Exception:
                        pass
            else:
                self.pdf.grid_remove()
                self.pdf_empty_frame.grid(row=0, column=0, sticky="nsew")
            self.chat.grid(row=0, column=2, sticky="nsew")
            self.splitter.grid(row=0, column=1, sticky="ns")
            self._apply_split_layout()
            self.sidebar.select_nav("Documents", notify=False)

        elif nav_key in self.specialized_views:
            self.pdf.grid_remove()
            self.pdf_empty_frame.grid_remove()
            self.welcome.grid_remove()
            self.chat.grid_remove()
            self.splitter.grid_remove()
            target_view = self.specialized_views[nav_key]
            target_view.grid(row=0, column=0, columnspan=3, sticky="nsew")
            self.center.grid_columnconfigure(0, weight=1)
            self.center.grid_columnconfigure(1, weight=0)
            self.center.grid_columnconfigure(2, weight=0)
            self.sidebar.select_nav(nav_key, notify=False)
            if hasattr(target_view, "refresh"):
                target_view.refresh()

    def handle_new_chat(self):
        # 1. Cleanly detach active document session and viewer context (Requirements 18 & 20)
        self.selected_file = None
        self.selected_doc_id = None
        if hasattr(self, "doc_indicator"):
            self.doc_indicator.pack_forget()
        self.file_label.configure(text="No document selected")
        self.summary_btn.configure(state="disabled")
        self.sidebar.set_active(None)

        # 2. Reset chat panel document and attachment state
        self.chat.clear_document_active()
        self.chat.clear_attachment()

        # 3. Start a brand new clean conversation
        self.chat.start_new_conversation()
        self.sidebar.set_active_chat(self.chat.conversation_id)

        # 4. Return view to Chat
        self.handle_nav_switch("Chat")
        self.chat.input.delete("1.0", "end")
        self.chat.input.focus_set()
        self.status.configure(text="Started a new conversation.")
        ToastNotification.show(self, "Started new chat", icon="💬", level="info")

    def open_history_modal(self):
        self.chat._open_history_modal()

    def load_selected_chat(self, cid: str):
        self.selected_file = None
        self.selected_doc_id = None
        self.chat.close_active_document()
        self.chat.clear_attachment()
        self.chat.load_conversation(cid)
        self.sidebar.set_active_chat(cid)
        self.sidebar.set_active(None)
        if hasattr(self, "doc_indicator"):
            self.doc_indicator.pack_forget()
        self.file_label.configure(text="No document selected")
        self.handle_nav_switch("Chat")

    def handle_project_changed(self, project_id: str):
        proj = project_service.get_active_project()
        self.proj_badge.configure(text=f"📁 {proj.get('name', 'General')}")
        self.status.configure(text=f"Switched project to: {proj.get('name')}")
        ToastNotification.show(self, f"Switched to project: {proj.get('name')}", icon="📁", level="info")

    def _bind_keyboard_shortcuts(self):
        """Binds universal keyboard shortcuts per Phase 3 requirements."""
        self.bind_all("<Control-n>", lambda e: self.handle_new_chat())
        self.bind_all("<Control-N>", lambda e: self.handle_new_chat())
        self.bind_all("<Control-k>", lambda e: self.open_command_palette())
        self.bind_all("<Control-K>", lambda e: self.open_command_palette())
        self.bind_all("<Control-Shift-P>", lambda e: self.open_command_palette())
        self.bind_all("<Control-Shift-p>", lambda e: self.open_command_palette())
        self.bind_all("<Control-o>", lambda e: self.add_pdf())
        self.bind_all("<Control-O>", lambda e: self.add_pdf())
        self.bind_all("<Control-l>", lambda e: self._focus_composer())
        self.bind_all("<Control-L>", lambda e: self._focus_composer())
        self.bind_all("<Control-Shift-V>", lambda e: self.chat.handle_voice())
        self.bind_all("<Control-Shift-v>", lambda e: self.chat.handle_voice())
        self.bind_all("<Control-Shift-L>", lambda e: self.explicit_lock_workspace())
        self.bind_all("<Control-Shift-l>", lambda e: self.explicit_lock_workspace())
        self.bind_all("<Escape>", lambda e: self.stop_ai_generation())

    def _focus_composer(self):
        self.handle_nav_switch("Chat")
        self.chat.input.focus_set()

    def _lock_ui_and_clear_sensitive_state(self, *args, **kwargs):
        """Immediately locks the workspace and hides all sensitive in-memory UI state."""
        self._last_auth_state = False
        from backend.security import set_password_authenticated, lock_workspace, invalidate_session
        invalidate_session()
        set_password_authenticated(False)
        lock_workspace()
        self.stop_ai_generation()
        if hasattr(self, "chat"):
            self.chat.clear_conversation_for_lock()
        if hasattr(self, "sidebar"):
            self.sidebar.clear_for_lock()
        self.selected_file = None
        self.selected_doc_id = None
        if hasattr(self, "doc_indicator"):
            self.doc_indicator.pack_forget()
        if hasattr(self, "file_label"):
            self.file_label.configure(text="")
        # Return view to Chat so specialized views are not left exposed
        self.handle_nav_switch("Chat")
        self.lock_overlay.show()
        self.usb_pill.configure(text="🔒 Workspace Locked", text_color=THEME["error"], fg_color=THEME["error_bg"])
        self.status.configure(text="Workspace Locked — Enter password to resume.")

    def _unlock_ui_and_restore_state(self):
        """Restores current device workspace state and local conversations without duplicates."""
        self._last_auth_state = True
        self.lock_overlay.hide()
        self.usb_pill.configure(text="● Secured", text_color=THEME["success"], fg_color=THEME["success_bg"])
        if hasattr(self, "sidebar"):
            self.sidebar.restore_after_unlock()
        if hasattr(self, "chat"):
            self.chat.enable_after_unlock()
        self.status.configure(text="Ready")
        ToastNotification.show(self, "Workspace Unlocked — Welcome back!", icon="🔓", level="success")

    def explicit_lock_workspace(self):
        from backend.security import lock_workspace, invalidate_session
        invalidate_session()
        lock_workspace()
        self._lock_ui_and_clear_sensitive_state()
        ToastNotification.show(self, "Workspace locked by user request.", icon="🔒", level="warning")

    def _on_workspace_unlocked(self):
        self._unlock_ui_and_restore_state()

    def _on_read_only_selected(self):
        self.usb_pill.configure(text="🔒 Read-Only", text_color=THEME["warning"], fg_color=THEME["warning_bg"])
        self.status.configure(text="Operating in Read-Only Mode.")

    def open_command_palette(self):
        from frontend.command_palette import CommandPalette
        actions = [
            {"title": "New Chat", "icon": "💬", "category": "Navigation", "shortcut": "Ctrl+N", "callback": self.handle_new_chat},
            {"title": "Search Workspace", "icon": "🔍", "category": "Search", "shortcut": "Ctrl+K", "callback": self.open_workspace_search},
            {"title": "Open Documents", "icon": "📄", "category": "Workspace", "shortcut": "Ctrl+O", "callback": lambda: self.handle_nav_switch("Documents")},
            {"title": "Create Project", "icon": "📁", "category": "Workspace", "callback": lambda: self.handle_nav_switch("Projects")},
            {"title": "Settings", "icon": "⚙️", "category": "System", "callback": lambda: self.handle_nav_switch("Settings")},
            {"title": "Lock Workspace", "icon": "🔒", "category": "Security", "shortcut": "Ctrl+Shift+L", "callback": self.explicit_lock_workspace},
        ]
        CommandPalette(self, actions)

    def open_workspace_search(self):
        from frontend.command_palette import WorkspaceSearchModal
        WorkspaceSearchModal(
            self,
            on_open_chat=self.load_selected_chat,
            on_open_project=lambda pid: (project_service.set_active_project(pid), self.handle_nav_switch("Projects")),
            on_open_document=lambda dname: self.handle_nav_switch("Documents")
        )

    def _initial_security_check(self):
        """Immediately checks password authentication state at startup."""
        from backend.security import is_password_authenticated
        from backend.password_auth import password_auth_service

        if not password_auth_service.is_password_configured() or not is_password_authenticated():
            self.lock_overlay.show()
            self.usb_pill.configure(text="🔒 Workspace Locked", text_color=THEME["error"], fg_color=THEME["error_bg"])
        else:
            self.lock_overlay.hide()
            self.usb_pill.configure(text="● Secured", text_color=THEME["success"], fg_color=THEME["success_bg"])

    def _startup_usb_retry(self):
        """No-op stub for backward compatibility."""
        pass

    def _startup_check(self):
        # 1. Ollama Check
        result = check_ollama()
        if result["ok"]:
            self.status.configure(text="Ready")
            threading.Thread(target=lambda: preload_model(), daemon=True).start()
        else:
            self.status.configure(text=result.get("error", "Ollama starting…"))

        # 2. Workspace & Data Isolation Check
        from backend.db import verify_and_isolate_database
        from backend.vector_store import verify_and_isolate_chroma
        from backend.security import is_running_on_removable_media

        db_check = verify_and_isolate_database()
        verify_and_isolate_chroma()

        if db_check.get("status") == "quarantined_foreign_workspace":
            ToastNotification.show(
                self,
                "Foreign workspace detected and quarantined. Fresh local workspace created.",
                icon="🛡️",
                level="warning"
            )

        # 3. Removable Media Installation Check
        is_removable, rem_msg = is_running_on_removable_media()
        if is_removable:
            ToastNotification.show(
                self,
                "Notice: Installed on removable drive D:. For standard security, install on fixed internal drive.",
                icon="⚠️",
                level="warning"
            )

        # 4. Password Authentication Check
        from backend.password_auth import password_auth_service
        from backend.security import is_password_authenticated
        if not password_auth_service.is_password_configured() or not is_password_authenticated():
            if not self.lock_overlay.is_visible:
                self.lock_overlay.show()
            self.usb_pill.configure(text="🔒 Workspace Locked", text_color=THEME["error"], fg_color=THEME["error_bg"])
        else:
            self.usb_pill.configure(text="● Secured", text_color=THEME["success"], fg_color=THEME["success_bg"])
            self.lock_overlay.hide()

        # 5. Initialize default full-width Chat view
        self.handle_nav_switch("Chat")

        # 6. Hardware Metrics Refresh
        self._update_hw_stats()

    def _start_hardware_polling(self):
        def poll_worker():
            try:
                hw = get_hardware_metrics()
                self.after(0, lambda: self._apply_hw_and_usb_status(hw))
            except Exception:
                pass

        threading.Thread(target=poll_worker, daemon=True).start()
        self.after(2000, self._start_hardware_polling)

    def _apply_hw_and_usb_status(self, hw, *args):
        try:
            self._update_hw_stats(hw)
        except Exception:
            pass

    def _update_hw_stats(self, hw=None):
        if not hw:
            return
        gpu_name = hw.get("gpu_name", "Unavailable")
        gpu_txt = f"GPU: {gpu_name.replace('NVIDIA GeForce ', '')}" if gpu_name != "Unavailable" else "CPU Mode"
        vram_used = hw.get("vram_used_gb")
        vram_tot = hw.get("vram_total_gb")
        vram_txt = f"VRAM: {vram_used}/{vram_tot}" if (vram_used is not None and vram_tot is not None and vram_tot != "Unavailable") else ""
        ram_used = hw.get("ram_used_gb")
        ram_tot = hw.get("ram_total_gb")
        ram_txt = f"RAM: {ram_used}/{ram_tot}" if (ram_used is not None and ram_tot is not None and ram_tot != "Unavailable") else ""
        
        stat_parts = [p for p in [gpu_txt, vram_txt, ram_txt] if p]
        self.hw_label.configure(text=" | ".join(stat_parts) if stat_parts else "Hardware: Ready")

    def add_pdf(self):
        path = filedialog.askopenfilename(
            title="Open Document",
            filetypes=[
                (
                    "All Supported Documents",
                    "*.pdf;*.docx;*.pptx;*.csv;*.tsv;*.txt;*.md;*.markdown;*.json;"
                    "*.py;*.js;*.ts;*.html;*.css;*.java;*.c;*.cpp;*.sh;*.bat;"
                    "*.xml;*.yaml;*.yml;*.sql;*.log"
                ),
                ("PDF files", "*.pdf"),
                ("Word Documents", "*.docx"),
                ("PowerPoint Slides", "*.pptx"),
                ("Tabular Data", "*.csv;*.tsv"),
                (
                    "Text / Code",
                    "*.txt;*.md;*.markdown;*.json;*.py;*.js;*.ts;*.html;*.css;"
                    "*.java;*.c;*.cpp;*.sh;*.bat;*.xml;*.yaml;*.yml;*.sql;*.log"
                )
            ]
        )
        if path:
            self.process_pdf(path)

    def _handle_file_drop(self, event):
        paths = self.tk.splitlist(event.data)
        supported_extensions = {
            ".pdf", ".docx", ".pptx", ".csv", ".tsv", ".txt", ".md", ".markdown",
            ".json", ".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp",
            ".sh", ".bat", ".xml", ".yaml", ".yml", ".sql", ".log"
        }
        accepted = []
        rejected = []
        for path in paths:
            if not os.path.isfile(path):
                rejected.append(Path(path).name or path)
            elif Path(path).suffix.lower() not in supported_extensions:
                rejected.append(Path(path).name)
            else:
                accepted.append(os.path.abspath(path))

        if rejected:
            messagebox.showwarning(
                "Unsupported dropped files",
                "These files could not be added as workspace documents:\n"
                + "\n".join(rejected),
                parent=self
            )
        self._drop_queue.extend(accepted)
        self._process_next_dropped_file()
        return "copy"

    def _process_next_dropped_file(self):
        if self._drop_active or not self._drop_queue:
            return
        self._drop_active = True
        path = self._drop_queue.pop(0)
        self.process_pdf(path, on_complete=self._finish_dropped_file)

    def _finish_dropped_file(self):
        self._drop_active = False
        self._process_next_dropped_file()

    @staticmethod
    def _doc_id(path):
        return hashlib.sha256(os.path.abspath(path).encode("utf-8")).hexdigest()[:24]

    def process_pdf(self, path, on_complete: Optional[Callable[[], None]] = None):
        path = os.path.abspath(path)
        fname = Path(path).name
        self.status.configure(text=f"Uploading {fname}…")
        self.summary_btn.configure(state="disabled")

        # Immediately display provisional document card/chip in chat panel (Requirement 15)
        doc_id = self._doc_id(path)
        provisional_info = {
            "name": fname,
            "path": path,
            "doc_id": doc_id,
            "status": "Indexing...",
            "page_count": "..."
        }
        self.chat.set_document_active(
            provisional_info,
            status="Indexing...",
            on_summarize=self.handle_doc_summary,
            on_ask=lambda: (self.chat.set_document_context_mode("Document"), self.chat.input.focus_set()),
            on_open_pdf=lambda: self.handle_nav_switch("Documents")
        )

        def work():
            try:
                # Universal document parser supporting PDF, DOCX, PPTX, CSV, TXT
                info = index_any_file(
                    path,
                    project_id=project_service.active_project_id,
                    progress_callback=lambda i, total, msg: self.after(0, lambda: (
                        self.status.configure(text=f"{msg}"),
                        self.chat.update_document_status(f"Indexing… ({msg})")
                    ))
                )
                self.loaded[info["doc_id"]] = info
                self.after(0, lambda: self._finish_document_processing(info, on_complete))
            except Exception as exc:
                self.after(0, lambda e=str(exc): self._fail(path, e, on_complete))

        threading.Thread(target=work, daemon=True).start()

    def _finish_document_processing(self, info, on_complete=None):
        self._activate(info)
        if on_complete:
            on_complete()

    def _fail(self, path, error, on_complete=None):
        fname = Path(path).name
        self.status.configure(text=f"Processing failed: {fname}")
        self.chat.update_document_status("Failed ⚠️")
        ToastNotification.show(self, f"Processing failed for {fname}", icon="⚠️", level="error")
        if messagebox.askretrycancel("Infinity AI - Processing Failed", f"Failed to process {fname}:\n{error}\n\nWould you like to retry?"):
            self.after(100, lambda: self.process_pdf(path, on_complete=on_complete))
        elif on_complete:
            on_complete()

    def _activate(self, info):
        self.selected_file = info["path"]
        self.selected_doc_id = info["doc_id"]
        self.sidebar.add_document(info["path"])
        self.sidebar.set_active(info["path"])
        self.file_label.configure(text=f"Selected document: {info['name']}")
        if hasattr(self, "doc_indicator"):
            fname = info["name"]
            display_n = fname[:20] + ("…" if len(fname) > 20 else "")
            self.doc_indicator.configure(text=f"📄 {display_n}")
            self.doc_indicator.pack(side="left", padx=(10, 6))
        self.summary_btn.configure(state="normal")
        self.welcome.grid_remove()

        # Requirement 16 & 17: Document Session Isolation
        # If current chat had unrelated conversation messages, start a fresh document-scoped session
        if self.chat.conversation:
            self.chat.start_new_conversation()
            self.sidebar.set_active_chat(self.chat.conversation_id)

        # Show document card and chip in chat panel as Ready
        self.chat.set_document_active(
            info,
            status="Ready",
            on_summarize=self.handle_doc_summary,
            on_ask=lambda: (self.chat.set_document_context_mode("Document"), self.chat.input.focus_set()),
            on_open_pdf=lambda: self.handle_nav_switch("Documents")
        )

        # If it's a PDF, display in PDFViewer; otherwise show document loaded notice
        if info["path"].lower().endswith(".pdf"):
            if hasattr(self, "pdf_empty_frame"):
                self.pdf_empty_frame.grid_remove()
            self.pdf.grid(row=0, column=0, sticky="nsew")
            self.pdf.load_pdf(info["path"])
        else:
            self.pdf.grid_remove()
            if hasattr(self, "pdf_empty_frame"):
                self.pdf_empty_frame.grid(row=0, column=0, sticky="nsew")

        self.chat.grid(row=0, column=2, sticky="nsew")
        self.handle_nav_switch("Documents")
        self.status.configure(text=f"Ready: {info['name']} ({info.get('page_count', 1)} pages)")

    def close_active_document(self):
        self.selected_file = None
        self.selected_doc_id = None
        self.summary_btn.configure(state="disabled")
        self.file_label.configure(text="No document selected")
        if hasattr(self, "doc_indicator"):
            self.doc_indicator.pack_forget()
        self.sidebar.set_active(None)
        self.chat.clear_document_active()
        if hasattr(self, "pdf") and self.pdf.doc:
            self.pdf.close()
        if self.current_nav == "Documents":
            self.pdf.grid_remove()
            if hasattr(self, "pdf_empty_frame"):
                self.pdf_empty_frame.grid(row=0, column=0, sticky="nsew")
        self.status.configure(text="Document closed.")

    def open_document(self, path):
        for info in self.loaded.values():
            if info["path"] == path:
                self._activate(info)
                return
        self.process_pdf(path)

    def remove_document(self, path):
        doc_id = self._doc_id(path)
        try:
            remove_document_chunks(doc_id)
        except Exception:
            pass
        self.loaded.pop(doc_id, None)
        self.sidebar.remove_document(path)
        if self.selected_file == path:
            self.close_active_document()

    def handle_page_question(self, text, page):
        self.chat.set_selected_text_focus(f"Page {page}:\n{text}")
        self.chat.input.focus_set()

    def handle_ai_query(self, query: str, attached_file: Optional[str] = None, mode: str = "Balanced", model_name: Optional[str] = None, context_mode: str = "normal"):
        if self.ai_running:
            return

        self.ai_running = True

        # 1. Check for Slash Commands
        is_cmd, final_query, target_agent, override_inst = process_slash_command(query, active_doc_id=self.selected_doc_id)

        # 2. Check for Unsupported Capabilities (e.g. image, video, music generation)
        is_unsupported, cap_type, explanation = check_unsupported_capability(
            final_query,
            has_image_attachment=bool(attached_file and attached_file.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))
        )
        if is_unsupported and explanation:
            append, finish = self.chat.create_ai_stream_bubble(initial_status="Checking capability…")
            self.status.configure(text=f"Capability notice ({cap_type})")
            append(explanation)
            finish()
            self.ai_running = False
            return

        # 3. Check for Real-time Date / Time Queries
        if is_datetime_query(final_query):
            append, finish = self.chat.create_ai_stream_bubble(initial_status="Checking system clock & timezone…")
            self.status.configure(text="Checking clock & timezone…")
            dt_res = handle_datetime_query(final_query)
            append(dt_res.get("answer", ""))
            finish()
            self.status.configure(text=f"Time/Date ({dt_res.get('timezone', 'Asia/Kolkata')})")
            self.ai_running = False
            return

        # 4. Check for Document Summary Intent
        if is_summary_intent(final_query):
            if self.selected_doc_id:
                info = self.loaded.get(self.selected_doc_id, {})
                doc_name = info.get("name") or "the uploaded document"
                self.status.configure(text=f"Generating summary of {doc_name}…")
                append, finish = self.chat.create_ai_stream_bubble(initial_status=f"Generating summary of {doc_name}…")

                def sum_work():
                    try:
                        if "pages" in info:
                            full_text = extract_full_text(info["pages"])
                        elif "text" in info:
                            full_text = info["text"]
                        else:
                            from backend.vector_store import get_all_document_text
                            full_text = get_all_document_text(self.selected_doc_id)
                        summarize_document(full_text, append, model_name=model_name or self.chat.get_selected_model())
                        self.after(0, finish)
                        self.after(0, lambda: self.status.configure(text=f"Summary of {doc_name} generated."))
                    except Exception as exc:
                        self.after(0, lambda e=str(exc): append(f"\n⚠️ {e}"))
                        self.after(0, finish)
                        self.after(0, lambda: self.status.configure(text="Summary error"))
                    finally:
                        self.ai_running = False

                threading.Thread(target=sum_work, daemon=True).start()
                return
            else:
                append, finish = self.chat.create_ai_stream_bubble(initial_status="")
                append("No active document selected. Please upload or select a document to summarize.")
                finish()
                self.ai_running = False
                self.status.configure(text="No document selected")
                return

        # 5. Check for Image Attachment (Multimodal / Vision)
        if attached_file and attached_file.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            append, finish = self.chat.create_ai_stream_bubble(initial_status="Analyzing image with Vision/OCR…")
            self.status.configure(text="Analyzing image with Vision/OCR…")

            def img_work():
                try:
                    analyze_image_with_vision(attached_file, prompt=final_query, chunk_callback=append)
                    self.after(0, finish)
                    self.after(0, lambda: self.status.configure(text="Image analysis complete."))
                except Exception as exc:
                    self.after(0, lambda e=str(exc): append(f"\n⚠️ {e}"))
                    self.after(0, finish)
                finally:
                    self.ai_running = False

            threading.Thread(target=img_work, daemon=True).start()
            return

        # 6. Retrieve Context & Citations
        doc_hash = self.loaded.get(self.selected_doc_id, {}).get("hash", "") if self.selected_doc_id else ""
        all_doc_ids = list(self.loaded.keys()) if len(self.loaded) > 1 else None

        citations = []
        c_mode = context_mode.lower()
        active_doc_name = self.loaded.get(self.selected_doc_id, {}).get("name") if self.selected_doc_id else None

        if c_mode in ["document", "rag"] or (self.selected_doc_id and c_mode != "normal"):
            n_cit = {"Basic": 2, "Balanced": 3, "Advanced": 5}.get(mode, 3)
            active_id = self.selected_doc_id if c_mode == "document" else None
            _, citations = retrieve_context_with_citations(
                final_query,
                doc_id=active_id,
                all_doc_ids=all_doc_ids if c_mode == "rag" else ([self.selected_doc_id] if self.selected_doc_id else None),
                n_results=n_cit
            )

        init_status = "Reading document & retrieving context…" if (c_mode in ["document", "rag"] and (self.selected_doc_id or all_doc_ids)) else "Thinking…"
        append, finish = self.chat.create_ai_stream_bubble(citations=citations, initial_status=init_status)
        history = self.chat.get_conversation_history()[:-1]

        def work():
            try:
                if target_agent and target_agent != "Document":
                    # Route through Agent Orchestrator
                    agent_orchestrator.run_agent(target_agent, final_query, model_name=model_name, chunk_callback=append)
                else:
                    # Standard RAG & Conversational flow with context_mode
                    ask_document(
                        final_query,
                        selected_text=None,
                        mode=mode,
                        doc_id=self.selected_doc_id if c_mode != "normal" else None,
                        history=history,
                        chunk_callback=append,
                        document_hash_value=doc_hash,
                        all_doc_ids=all_doc_ids if c_mode == "rag" else None,
                        model_name=model_name,
                        context_mode=c_mode,
                        doc_name=active_doc_name
                    )
                self.after(0, finish)
                self.after(0, lambda: self.status.configure(text="Answer generated"))
            except Exception as exc:
                self.after(0, lambda e=str(exc): append("\n⚠️ " + e))
                self.after(0, finish)
                self.after(0, lambda: self.status.configure(text="AI error"))
            finally:
                self.ai_running = False

        threading.Thread(target=work, daemon=True).start()

    def stop_ai_generation(self):
        stop_generation()
        stop_summary()
        self.ai_running = False
        self.summary_running = False

    def handle_doc_summary(self):
        if not self.selected_doc_id or self.selected_doc_id not in self.loaded or self.summary_running:
            return
        self.summary_running = True
        self.summary_btn.configure(state="disabled")
        info = self.loaded[self.selected_doc_id]
        if self.current_nav not in ["Chat", "Documents"]:
            self.handle_nav_switch("Chat")
        self.chat.add_user_message("Generate a structured executive summary for " + info["name"])
        append, finish = self.chat.create_ai_stream_bubble(initial_status=f"Generating hierarchical summary of {info['name']}…")
        self.status.configure(text=f"Generating summary of {info['name']}…")

        def work():
            try:
                full_text = extract_full_text(info["pages"]) if "pages" in info else info.get("text", "")
                if not full_text:
                    from backend.vector_store import get_all_document_text
                    full_text = get_all_document_text(self.selected_doc_id)
                summarize_document(full_text, append, model_name=self.chat.get_selected_model())
                self.after(0, finish)
                self.after(0, lambda: self.status.configure(text="Summary generated"))
            except Exception as exc:
                self.after(0, lambda e=str(exc): append("\n⚠️ " + e))
                self.after(0, finish)
            finally:
                self.summary_running = False
                self.after(0, lambda: self.summary_btn.configure(state="normal"))

        threading.Thread(target=work, daemon=True).start()

    def on_close(self):
        try:
            if hasattr(self, "_startup_job") and self._startup_job:
                try: self.after_cancel(self._startup_job)
                except Exception: pass
            if hasattr(self, "_hw_poll_job") and self._hw_poll_job:
                try: self.after_cancel(self._hw_poll_job)
                except Exception: pass
            if hasattr(self, "lock_overlay"):
                self.lock_overlay._stop_polling()
            stop_generation()
            stop_summary()
            self.pdf.close()
        finally:
            self.destroy()
