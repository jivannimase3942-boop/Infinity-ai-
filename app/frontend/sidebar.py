"""
Infinity AI - Minimal Navigation Sidebar
"SIMPLE OUTSIDE, POWERFUL INSIDE."

Sidebar Navigation Structure:
INFINITY AI

Chats
Documents
Projects

Settings
Security

Navigation Architecture & Classification:
- CHATS: primary conversational interface
- WORKSPACE: Projects and Documents
- TOOLS: Specialized capabilities (Vision, Voice, Coding, Research)
- SYSTEM: Settings and Security
"""

import time
from pathlib import Path
from tkinter import simpledialog, messagebox
from typing import Optional, Callable, Dict, Any, List
import customtkinter as ctk

from frontend.branding import load_logo_image
from frontend.theme import SCROLLABLE_COLORS, THEME, register_theme_listener
from backend.db import get_grouped_conversations, rename_conversation, delete_conversation


class SidebarTooltip:
    _active = None

    @classmethod
    def show(cls, widget, text):
        cls.hide()
        try:
            widget.update_idletasks()
            x = widget.winfo_rootx() + widget.winfo_width() + 8
            y = widget.winfo_rooty() + 4
            tip = ctk.CTkToplevel(widget)
            tip.overrideredirect(True)
            tip.geometry(f"+{x}+{y}")
            tip.configure(fg_color=THEME["bg_panel"])
            tip.attributes("-topmost", True)
            lbl = ctk.CTkLabel(
                tip,
                text=text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=THEME["text_primary"],
                padx=8,
                pady=4
            )
            lbl.pack()
            cls._active = tip
        except Exception:
            pass

    @classmethod
    def hide(cls):
        if cls._active:
            try:
                cls._active.destroy()
            except Exception:
                pass
            cls._active = None


class Sidebar(ctk.CTkFrame):
    """
    Infinity AI Minimal Navigation Sidebar.
    Maintains categorization architecture:
    - CHATS: Zero-history mode active; persistent chat history removed per privacy specification
    - WORKSPACE: Documents and Projects
    - TOOLS: Vision, Voice, Research
    - SYSTEM: Settings and Security
    """
    def __init__(
        self,
        master,
        on_add=None,
        on_select=None,
        on_remove=None,
        on_nav_change: Optional[Callable[[str], None]] = None,
        on_new_chat: Optional[Callable[[], None]] = None,
        on_search: Optional[Callable[[], None]] = None,
        on_recent: Optional[Callable[[], None]] = None,
        on_voice: Optional[Callable[[], None]] = None,
        on_vision: Optional[Callable[[], None]] = None,
        on_security: Optional[Callable[[], None]] = None,
        on_select_chat: Optional[Callable[[str], None]] = None,
        **kw
    ):
        super().__init__(master, **kw)
        self.on_add = on_add
        self.on_select = on_select
        self.on_remove = on_remove
        self.on_nav_change = on_nav_change
        self.on_new_chat = on_new_chat
        self.on_search = on_search
        self.on_recent = on_recent
        self.on_voice = on_voice
        self.on_vision = on_vision
        self.on_security = on_security
        self.on_select_chat = on_select_chat
        self.documents = []
        self.active_path = None
        self.active_nav = "Chat"
        self.active_chat_id: Optional[str] = None
        self.is_collapsed = False

        self.configure(fg_color=THEME["bg_sidebar"], corner_radius=0)
        self.pack_propagate(False)
        self._build_sidebar()
        register_theme_listener(self.apply_theme)

    def _build_sidebar(self):
        # 1. Header with Collapse Toggle only (no duplicate Infinity AI branding in sidebar)
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent", height=40)
        self.header_frame.pack(fill="x", padx=10, pady=(10, 6))

        self.logo_image = load_logo_image((22, 22))
        self.brand_btn = ctk.CTkButton(
            self.header_frame,
            text="∞  Infinity AI",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_primary"],
            anchor="w",
            height=28,
            corner_radius=6,
            command=lambda: self.select_nav("Chat")
        )
        self.brand_btn.pack(side="left", padx=(2, 0))

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="",
            image=None,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=THEME["text_muted"],
            anchor="w"
        )

        self.collapse_btn = ctk.CTkButton(
            self.header_frame,
            text="◀",
            width=28,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_primary"],
            command=self.toggle_collapse
        )
        self.collapse_btn.pack(side="right")

        # 2. Attribute preservation for backward compatibility
        self.new_chat_btn = ctk.CTkButton(
            self,
            text="＋ New Chat",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            height=32,
            corner_radius=8,
            command=self._handle_new_chat
        )

        # 3. Clean Primary Navigation Container (Requirement 4 & 29)
        self.scroll_container = ctk.CTkScrollableFrame(self, fg_color="transparent", **SCROLLABLE_COLORS)
        self.scroll_container.pack(fill="both", expand=True, padx=6, pady=4)

        # Architectural definition:
        # WORKSPACE: Documents and Projects
        # SYSTEM: Settings and Security
        self.sections_def = [
            ("WORKSPACE", [
                ("Documents", "📄", "Documents"),
                ("Projects", "📁", "Projects"),
            ]),
            ("SYSTEM", [
                ("Settings", "⚙️", "Settings"),
                ("Security", "🔒", "Security"),
            ]),
        ]

        self.section_labels: Dict[str, ctk.CTkLabel] = {}
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}

        # Primary items: Documents, Projects
        self.history_container = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        for sec_name, items in self.sections_def[:1]:
            for nav_key, icon, label in items:
                btn = ctk.CTkButton(
                    self.scroll_container,
                    text=f"{icon}  {label}",
                    anchor="w",
                    font=ctk.CTkFont(size=12),
                    fg_color=THEME["accent_dim"] if nav_key == self.active_nav else "transparent",
                    hover_color=THEME["bg_hover"],
                    text_color=THEME["accent_hover"] if nav_key == self.active_nav else THEME["text_secondary"],
                    height=32,
                    corner_radius=6,
                    command=lambda k=nav_key: self.select_nav(k)
                )
                btn.pack(fill="x", pady=2)
                btn.bind("<Enter>", lambda e, b=btn, l=label: self._on_btn_hover(b, l))
                btn.bind("<Leave>", lambda e: SidebarTooltip.hide())
                self.nav_buttons[nav_key] = btn

        # Subtle separator before Settings & Security
        self.divider = ctk.CTkFrame(self.scroll_container, height=1, fg_color=THEME["border"])
        self.divider.pack(fill="x", padx=4, pady=10)

        # System items: Settings, Security
        for nav_key, icon, label in self.sections_def[1][1]:
            btn = ctk.CTkButton(
                self.scroll_container,
                text=f"{icon}  {label}",
                anchor="w",
                font=ctk.CTkFont(size=12),
                fg_color=THEME["accent_dim"] if nav_key == self.active_nav else "transparent",
                hover_color=THEME["bg_hover"],
                text_color=THEME["accent_hover"] if nav_key == self.active_nav else THEME["text_secondary"],
                height=32,
                corner_radius=6,
                command=lambda k=nav_key: self.select_nav(k)
            )
            btn.pack(fill="x", pady=2)
            btn.bind("<Enter>", lambda e, b=btn, l=label: self._on_btn_hover(b, l))
            btn.bind("<Leave>", lambda e: SidebarTooltip.hide())
            self.nav_buttons[nav_key] = btn

        # Preserved attributes for backward-compatibility with tests & modals
        self.list = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        self.files_section_label = ctk.CTkLabel(self.scroll_container, text="")
        self.add_pdf_btn = ctk.CTkButton(self.scroll_container, text="")
        self._last_toggle_time = 0.0

    def refresh_conversations(self):
        """Zero-history mode: sidebar does not expose chat history."""
        pass

    def _handle_chat_click(self, cid: str):
        self.active_chat_id = cid
        self.select_nav("Chat")
        if self.on_select_chat:
            self.on_select_chat(cid)

    def set_active_chat(self, cid: Optional[str]):
        self.active_chat_id = cid

    def _on_btn_hover(self, btn, label):
        if getattr(self, "is_collapsed", False):
            SidebarTooltip.show(btn, label)

    def _render_collapsed(self):
        self.header_frame.pack_configure(padx=2)
        self.collapse_btn.configure(text="▶", width=28, height=28)
        if hasattr(self, "brand_btn"):
            self.brand_btn.configure(text="∞", width=36, font=ctk.CTkFont(size=18, weight="bold"))
        self.title_label.configure(text="", image=None)
        if hasattr(self, "divider"):
            self.divider.pack_configure(padx=4, pady=6)
        if hasattr(self, "history_container"):
            self.history_container.pack_forget()
        for _, items in self.sections_def:
            for nav_key, icon, _ in items:
                if nav_key in self.nav_buttons:
                    self.nav_buttons[nav_key].configure(
                        text=icon,
                        anchor="center",
                        width=52,
                        height=38,
                        font=ctk.CTkFont(size=18, weight="bold")
                    )
                    self.nav_buttons[nav_key].pack_configure(pady=3)

    def _render_expanded(self):
        SidebarTooltip.hide()
        self.header_frame.pack_configure(padx=10)
        self.collapse_btn.configure(text="◀", width=28, height=28)
        if hasattr(self, "brand_btn"):
            self.brand_btn.configure(text="∞  Infinity AI", width=0, font=ctk.CTkFont(size=13, weight="bold"))
        self.title_label.configure(text="", image=None)
        if hasattr(self, "divider"):
            self.divider.pack_configure(padx=4, pady=10)
        for _, items in self.sections_def:
            for nav_key, icon, label in items:
                if nav_key in self.nav_buttons:
                    self.nav_buttons[nav_key].configure(
                        text=f"{icon}  {label}",
                        anchor="w",
                        width=0,
                        height=32,
                        font=ctk.CTkFont(size=12)
                    )
                    self.nav_buttons[nav_key].pack_configure(pady=2)

    def toggle_collapse(self):
        """Toggles between expanded and collapsed icon-only sidebar with debounce."""
        now = time.time()
        if now - getattr(self, "_last_toggle_time", 0.0) < 0.22:
            return
        self._last_toggle_time = now
        self.is_collapsed = not self.is_collapsed
        target_width = 68 if self.is_collapsed else 210
        if self.is_collapsed:
            self._render_collapsed()
        else:
            self._render_expanded()
        self._animate_width(target_width)

    def _animate_width(self, target_width: int):
        if getattr(self, "_width_animation_job", None):
            self.after_cancel(self._width_animation_job)
            self._width_animation_job = None
        start_width = self.winfo_width()
        steps = 4
        delta = target_width - start_width
        if not delta:
            self.configure(width=target_width)
            return

        def step(index: int):
            if index >= steps:
                self.configure(width=target_width)
                self._width_animation_job = None
                return
            progress = index / steps
            width = start_width + round(delta * progress)
            self.configure(width=width)
            self._width_animation_job = self.after(16, lambda: step(index + 1))

        step(0)

    def select_nav(self, nav_key: str, notify: bool = True):
        if nav_key == "Search":
            self._handle_search()
            return
        if nav_key == "Security":
            self.active_nav = "Security"
            self._update_button_highlights("Security")
            if self.on_security:
                self.on_security()
            elif notify and self.on_nav_change:
                self.on_nav_change("Diagnostics")
            return

        already_active = (self.active_nav == nav_key)
        self.active_nav = nav_key
        self._update_button_highlights(nav_key)
        if notify and self.on_nav_change and not already_active:
            self.on_nav_change(nav_key)

    def _update_button_highlights(self, active_key: str):
        for k, btn in self.nav_buttons.items():
            is_active = (k == active_key)
            f_size = 18 if getattr(self, "is_collapsed", False) else 12
            btn.configure(
                fg_color=THEME["accent_dim"] if is_active else "transparent",
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_primary"] if is_active else THEME["text_secondary"],
                font=ctk.CTkFont(size=f_size, weight="bold" if is_active else "normal")
            )

    def apply_theme(self, theme_name=None):
        """Refreshes sidebar container and button colors to match active theme."""
        try:
            self.configure(fg_color=THEME["bg_sidebar"])
            self.title_label.configure(text_color=THEME["text_primary"])
            if hasattr(self, "brand_btn"):
                self.brand_btn.configure(text_color=THEME["text_primary"])
            self.collapse_btn.configure(fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], text_color=THEME["text_primary"])
            if hasattr(self, "scroll_container"):
                self.scroll_container.configure(
                    scrollbar_fg_color=THEME["bg_sidebar"],
                    scrollbar_button_color=THEME["bg_panel"],
                    scrollbar_button_hover_color=THEME["bg_hover"]
                )
            if hasattr(self, "divider"):
                self.divider.configure(fg_color=THEME["border"])
            self._update_button_highlights(self.active_nav)
            self.refresh_conversations()
        except Exception:
            pass

    def _handle_new_chat(self):
        self.active_chat_id = None
        self.select_nav("Chat")
        if self.on_new_chat:
            self.on_new_chat()

    def _handle_search(self):
        if self.on_search:
            self.on_search()
        elif hasattr(self.master.winfo_toplevel(), "open_command_palette"):
            self.master.winfo_toplevel().open_command_palette()

    def _add(self):
        if self.on_add:
            self.on_add()

    def add_document(self, path):
        if path not in self.documents:
            self.documents.append(path)

    def remove_document(self, path):
        if path in self.documents:
            self.documents.remove(path)

    def set_active(self, path):
        self.active_path = path

    def clear_for_lock(self):
        """Hides conversation titles and lists immediately when USB key is removed."""
        self.active_chat_id = None
        if hasattr(self, "history_container"):
            for w in self.history_container.winfo_children():
                w.destroy()
        self.documents = []

    def restore_after_unlock(self):
        """Restores local conversation history and documents when USB is reinserted."""
        self.refresh_conversations()
        self.refresh_files_list()

    def refresh_files_list(self):
        pass
