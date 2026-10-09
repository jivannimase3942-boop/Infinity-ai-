"""
Infinity AI - Consumer Startup-Grade Chat Panel
Inspired by ChatGPT Desktop, Gemini Desktop, and Claude Desktop UX principles.
Provides:
- Minimal top bar (Conversation title on left, subtle '● Private & Offline' status, ••• menu on right)
- Premium empty state screen (Branded ∞ glyph, 3 clear action buttons, 3 subtle suggestion pills)
- Smart AI Composer (Large rounded container, [+] contextual attachments, 🎤 voice, Send/Stop)
- Intelligent automatic context routing (Normal vs Document vs Vision vs Coding)
- Smooth streaming bubble with user-scroll detection
- Clean rendered markdown, code copy, regenerate, feedback, and source citation cards
- 100% offline and backward-compatible with test suite
"""

import os
import queue
import re
import time
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from typing import Optional, Callable, List, Dict, Any

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

from frontend.theme import (
    ENTRY_TEXT_COLORS, OPTION_MENU_COLORS, SCROLLABLE_COLORS,
    TEXTBOX_COLORS, THEME, register_theme_listener, get_current_theme
)
from frontend.markdown_renderer import RichMarkdownText
from frontend.toast import ToastNotification
import pyperclip


def show_toast(parent, message: str, kind: str = "info"):
    try:
        top = parent.winfo_toplevel() if hasattr(parent, "winfo_toplevel") else parent
        ToastNotification.show(top, message, level=kind)
    except Exception:
        pass

from backend.db import (
    create_conversation,
    add_message,
    get_messages,
    get_conversations,
    delete_conversation,
    rename_conversation,
    pin_conversation,
    archive_conversation,
    export_conversation,
    search_conversations,
    get_conversation,
    generate_friendly_title
)
from backend.file_ops import extract_file_content, safe_export_content, is_image_file
from backend.model_manager import get_all_models
from backend.router import route_model, route_model_detailed
from backend.voice import (
    speak_text, stop_speaking, start_listening, stop_listening, cancel_listening,
    get_voice_status, listen_and_transcribe, listen_and_transcribe_result
)


class ConversationHistoryModal(ctk.CTkToplevel):
    """Searchable conversation history dialog with pin, archive, rename, and chronological grouping."""
    _instance: Optional["ConversationHistoryModal"] = None

    def __init__(self, master, current_cid: str, on_select: Callable[[str], None], on_new: Callable[[], None]):
        # Prevent duplicate history modal windows
        if ConversationHistoryModal._instance and ConversationHistoryModal._instance.winfo_exists():
            ConversationHistoryModal._instance.lift()
            ConversationHistoryModal._instance.focus_force()
            super().__init__(master)
            self.destroy()
            return

        super().__init__(master)
        ConversationHistoryModal._instance = self
        self.current_cid = current_cid
        self.on_select = on_select
        self.on_new = on_new

        self.title("Conversation History — Infinity AI")
        self.geometry("540x520")
        self.configure(fg_color=THEME["bg_secondary"])
        self.transient(master)
        self.grab_set()

        self._build()
        self._load_conversations()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        ConversationHistoryModal._instance = None
        self.destroy()

    def _build(self):
        head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        head.pack(fill="x")

        ctk.CTkLabel(
            head,
            text="📜 Past Conversations",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME["text_primary"]
        ).pack(side="left", padx=14, pady=8)

        ctk.CTkButton(
            head,
            text="＋ New Chat",
            width=90,
            height=28,
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME["accent_text"],
            command=self._handle_new
        ).pack(side="right", padx=12)

        # Search Bar
        search_box = ctk.CTkFrame(self, fg_color=THEME["bg_surface"], corner_radius=8, border_color=THEME["border"], border_width=1)
        search_box.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkLabel(search_box, text="🔍", font=ctk.CTkFont(size=12), text_color=THEME["text_muted"]).pack(side="left", padx=(10, 2))
        self.search_entry = ctk.CTkEntry(
            search_box,
            placeholder_text="Search past conversations…",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            border_width=0,
            **ENTRY_TEXT_COLORS
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=4, pady=6)
        self.search_entry.bind("<KeyRelease>", lambda e: self._load_conversations())

        # Scrollable list
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=THEME["bg_secondary"], **SCROLLABLE_COLORS)
        self.list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    def _load_conversations(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        query = self.search_entry.get().strip()
        if query:
            convs = search_conversations(query)
            groups = [("", convs)] if convs else []
        else:
            convs = get_conversations()
            if not convs:
                groups = []
            else:
                from datetime import date, timedelta
                today_str = date.today().isoformat()
                yesterday_str = (date.today() - timedelta(days=1)).isoformat()
                seven_days_ago_str = (date.today() - timedelta(days=7)).isoformat()

                pinned = []
                today = []
                yesterday = []
                prev_7 = []
                older = []

                for c in convs:
                    if c.get("pinned"):
                        pinned.append(c)
                        continue
                    d = str(c.get("updated_at") or c.get("created_at") or "")[:10]
                    if d >= today_str:
                        today.append(c)
                    elif d >= yesterday_str:
                        yesterday.append(c)
                    elif d >= seven_days_ago_str:
                        prev_7.append(c)
                    else:
                        older.append(c)

                groups = []
                if pinned:
                    groups.append(("📌 Pinned", pinned))
                if today:
                    groups.append(("Today", today))
                if yesterday:
                    groups.append(("Yesterday", yesterday))
                if prev_7:
                    groups.append(("Previous 7 Days", prev_7))
                if older:
                    groups.append(("Older", older))

        if not groups:
            ctk.CTkLabel(
                self.list_frame,
                text="No conversations found.",
                font=ctk.CTkFont(size=12),
                text_color=THEME["text_secondary"]
            ).pack(pady=30)
            return

        for group_title, items in groups:
            if not items:
                continue
            if group_title:
                ctk.CTkLabel(
                    self.list_frame,
                    text=group_title,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=THEME["text_muted"]
                ).pack(anchor="w", padx=4, pady=(10, 3))

            for c in items:
                is_active = c["id"] == self.current_cid
                card = ctk.CTkFrame(
                    self.list_frame,
                    fg_color=THEME["accent_dim"] if is_active else THEME["bg_surface"],
                    corner_radius=8,
                    border_color=THEME["border"],
                    border_width=1
                )
                card.pack(fill="x", pady=2)

                pin_icon = "📌 " if c.get("pinned") else ""
                title_text = f"{pin_icon}{c['title']}"

                btn = ctk.CTkButton(
                    card,
                    text=title_text[:36] + ("…" if len(title_text) > 36 else ""),
                    anchor="w",
                    fg_color="transparent",
                    hover_color=THEME["bg_hover"],
                    text_color=THEME["text_primary"],
                    font=ctk.CTkFont(size=12, weight="bold" if is_active else "normal"),
                    command=lambda cid=c["id"]: self._select(cid)
                )
                btn.pack(side="left", fill="x", expand=True, padx=8, pady=4)

                # Actions: Rename, Pin, Delete
                ctk.CTkButton(
                    card,
                    text="✏️",
                    width=24,
                    height=22,
                    fg_color="transparent",
                    hover_color=THEME["bg_hover"],
                    command=lambda cid=c["id"], t=c["title"]: self._rename(cid, t)
                ).pack(side="right", padx=1)

                ctk.CTkButton(
                    card,
                    text="📌",
                    width=24,
                    height=22,
                    fg_color="transparent",
                    hover_color=THEME["bg_hover"],
                    command=lambda cid=c["id"], p=c.get("pinned"): self._toggle_pin(cid, p)
                ).pack(side="right", padx=1)

                ctk.CTkButton(
                    card,
                    text="🗑️",
                    width=24,
                    height=22,
                    fg_color="transparent",
                    hover_color=THEME["error_bg"],
                    text_color=THEME["error"],
                    command=lambda cid=c["id"], t=c["title"]: self._delete(cid, t)
                ).pack(side="right", padx=(1, 4))

    def _select(self, cid: str):
        self._on_close()
        self.on_select(cid)

    def _handle_new(self):
        self._on_close()
        self.on_new()

    def _rename(self, cid: str, current_title: str):
        new_title = simpledialog.askstring("Rename Conversation", "Enter new title:", initialvalue=current_title, parent=self)
        if new_title and new_title.strip():
            rename_conversation(cid, new_title.strip())
            self._load_conversations()

    def _toggle_pin(self, cid: str, currently_pinned: bool):
        pin_conversation(cid, not currently_pinned)
        self._load_conversations()

    def _delete(self, cid: str, title: str):
        if messagebox.askyesno("Delete Conversation", f"Are you sure you want to delete '{title}'?", parent=self):
            delete_conversation(cid)
            if cid == self.current_cid:
                self._on_close()
                self.on_new()
            else:
                self._load_conversations()


class ChatPanel(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_send_message=None,
        on_stop=None,
        on_source_click=None,
        on_close_doc=None,
        on_add_document=None,
        on_open_projects=None,
        on_open_pdf_viewer=None,
        conversation_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.on_send_message = on_send_message
        self.on_stop = on_stop
        self.on_source_click = on_source_click
        self.on_close_doc = on_close_doc
        self.on_add_document = on_add_document
        self.on_open_projects = on_open_projects
        self.on_open_pdf_viewer = on_open_pdf_viewer
        if conversation_id:
            self.conversation_id = conversation_id
            self._is_draft = False
        else:
            import uuid
            self.conversation_id = str(uuid.uuid4())
            self._is_draft = True

        self.conversation: List[Dict[str, Any]] = []
        self.generating = False
        self.attached_file: Optional[str] = None
        self.attached_content: Optional[str] = None
        self.last_user_query: str = ""
        self.active_doc_info: Optional[Dict[str, Any]] = None
        self._content_labels: List[Any] = []
        self._user_bubble_cards: List[Any] = []
        self._current_ui_state: Optional[str] = None
        self._auto_scroll_enabled = True
        self._resize_timer: Optional[str] = None

        self.configure(fg_color=THEME["bg_secondary"], corner_radius=0)
        self._build()
        try:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self.handle_file_drop)
        except Exception:
            pass
        if not self._is_draft:
            self._load_saved_messages()
        else:
            self._show_home_state()

    def _trigger_add_doc(self):
        if self.on_add_document:
            self.on_add_document()
        else:
            self.handle_attach()

    def _trigger_open_projects(self):
        if self.on_open_projects:
            self.on_open_projects()

    def _build(self):
        # 1. Sleek Top Bar (Preserved as attribute without packing to avoid double top bar)
        self.top_frame = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=42, corner_radius=0)
        top = self.top_frame

        # Left: Conversation Title (clean, Segoe UI)
        self.conv_title_label = ctk.CTkLabel(
            top,
            text="New Chat",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=THEME["text_primary"],
            cursor="hand2"
        )
        self.conv_title_label.pack(side="left", padx=(14, 8), pady=8)
        self.conv_title_label.bind("<Button-1>", lambda e: self._handle_title_rename())

        # Center/Left: Active Document Chip in Top Bar (if any)
        self.top_doc_label = ctk.CTkLabel(
            top,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=THEME["accent_hover"]
        )
        self.top_doc_label.pack(side="left", padx=4, pady=8)

        # Right: ••• More Actions Menu
        self.more_menu_btn = ctk.CTkButton(
            top,
            text="•••",
            width=32,
            height=26,
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=THEME["text_secondary"],
            command=self._show_more_menu
        )
        self.more_menu_btn.pack(side="right", padx=(4, 12), pady=8)

        # Right: Subtle "● Private & Offline" Status Pill
        self.offline_pill = ctk.CTkButton(
            top,
            text="● Private & Offline",
            height=24,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=THEME["success_bg"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["success"],
            corner_radius=6,
            command=self._show_privacy_dialog
        )
        self.offline_pill.pack(side="right", padx=6, pady=8)

        # Retain references for backward-compatibility with tests & internal calls
        self.add_doc_btn = ctk.CTkButton(top, text="＋ Add Document", command=self._trigger_add_doc)
        self.context_mode_var = ctk.StringVar(value="Normal")
        self.model_var = ctk.StringVar(value="Auto")
        self.mode_var = ctk.StringVar(value="Balanced")
        self.routing_hint = ctk.CTkLabel(self, text="")

        # 2. Document Card Container (pinned right below header when requested)
        self.doc_card_container = ctk.CTkFrame(self, fg_color="transparent")
        self.doc_card_container.pack(fill="x", padx=0, pady=0)
        self.doc_card = ctk.CTkFrame(self.doc_card_container, fg_color=THEME["bg_surface"], corner_radius=10, border_color=THEME["border"], border_width=1)

        # 3. Scrollable Messages Area
        self.chat = ctk.CTkScrollableFrame(self, fg_color=THEME["bg_secondary"], **SCROLLABLE_COLORS)
        self.chat.bind("<Configure>", self._on_chat_resize)

        # Bottom spacer inside chat to guarantee AI answers are never clipped behind composer
        self.bottom_spacer = ctk.CTkFrame(self.chat, height=28, fg_color="transparent")

        # Track user scrolling to honor auto-scroll suspension
        try:
            self.chat._parent_canvas.bind("<MouseWheel>", self._on_user_scroll)
            self.chat._parent_canvas.bind("<Button-4>", self._on_user_scroll)
            self.chat._parent_canvas.bind("<Button-5>", self._on_user_scroll)
        except Exception:
            pass

        # Home / Welcome Screen Container (State A)
        self.home_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.empty_state = self.home_frame
        self._build_empty_state()

        # 4. Modern Compact AI Composer (Requirement 22 & 36)
        self.composer_card = ctk.CTkFrame(self, fg_color=THEME["bg_surface"], corner_radius=12, border_color=THEME["border"], border_width=1)

        # 4a. Active Document Chip inside composer card
        self.doc_chip = ctk.CTkFrame(self.composer_card, fg_color=THEME["bg_panel"], corner_radius=6, height=28, border_color=THEME["border"], border_width=1)
        self.doc_chip_label = ctk.CTkLabel(self.doc_chip, text="", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_primary"])
        self.doc_chip_label.pack(side="left", padx=(10, 4), pady=3)

        self.doc_chip_open_btn = ctk.CTkButton(
            self.doc_chip,
            text="Open",
            width=46,
            height=20,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=THEME["accent_dim"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_primary"],
            command=self._handle_chip_open
        )
        self.doc_chip_open_btn.pack(side="left", padx=4, pady=3)

        self.doc_chip_close = ctk.CTkButton(
            self.doc_chip,
            text="✕",
            width=22,
            height=22,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=THEME["error_bg"],
            text_color=THEME["text_muted"],
            command=self.close_active_document
        )
        self.doc_chip_close.pack(side="right", padx=(4, 6), pady=3)

        # 4b. Attachment Banner inside composer card
        self.attach_banner = ctk.CTkFrame(self.composer_card, fg_color=THEME["bg_panel"], height=28, corner_radius=6)
        self.attach_label = ctk.CTkLabel(self.attach_banner, text="", font=ctk.CTkFont(size=11), text_color=THEME["text_primary"])
        self.attach_label.pack(side="left", padx=8)
        ctk.CTkButton(
            self.attach_banner,
            text="✕",
            width=20,
            height=20,
            fg_color="transparent",
            hover_color=THEME["error_bg"],
            text_color=THEME["text_muted"],
            command=self.clear_attachment
        ).pack(side="right", padx=4)

        # 4c. Voice Recording In-Progress Banner (Requirement 36)
        self.voice_recording_bar = ctk.CTkFrame(self.composer_card, fg_color=THEME["bg_panel"], corner_radius=8, height=30)
        self.voice_status_label = ctk.CTkLabel(
            self.voice_recording_bar,
            text="🔴 Listening... Speak clearly into your microphone",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME["error"]
        )
        self.voice_status_label.pack(side="left", padx=10, pady=3)

        self.voice_cancel_btn = ctk.CTkButton(
            self.voice_recording_bar,
            text="✕ Cancel",
            width=64,
            height=22,
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            font=ctk.CTkFont(size=11),
            text_color=THEME["text_secondary"],
            command=self._cancel_voice
        )
        self.voice_cancel_btn.pack(side="right", padx=6, pady=3)

        self.voice_done_btn = ctk.CTkButton(
            self.voice_recording_bar,
            text="■ Done",
            width=58,
            height=22,
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME["accent_text"],
            command=self._stop_voice
        )
        self.voice_done_btn.pack(side="right", padx=2, pady=3)

        self.voice_lang_var = ctk.StringVar(value="Auto Detect")
        self.voice_lang_menu = ctk.CTkOptionMenu(
            self.voice_recording_bar,
            values=["Auto Detect", "English", "Hindi", "Marathi"],
            variable=self.voice_lang_var,
            width=96,
            height=22,
            font=ctk.CTkFont(size=10),
            fg_color=THEME["bg_surface"],
            button_color=THEME["bg_hover"],
            button_hover_color=THEME["accent_dim"],
            text_color=THEME["text_primary"],
            dropdown_font=ctk.CTkFont(size=11),
            dynamic_resizing=False
        )
        self.voice_lang_menu.pack(side="right", padx=4, pady=3)

        # 4d. Compact Auto-growing Textbox inside composer card
        self.input = ctk.CTkTextbox(
            self.composer_card,
            height=42,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            text_color=THEME["text_primary"],
            border_width=0
        )
        self.input.pack(fill="x", padx=10, pady=(4, 2))
        self.input.bind("<KeyRelease>", self._auto_size_input)
        self.input.bind("<Return>", self._enter)

        # Composer Bottom Action Row
        action_row = ctk.CTkFrame(self.composer_card, fg_color="transparent", height=32)
        action_row.pack(fill="x", padx=8, pady=(2, 6))

        # Left tools: [+] Attach and 🎤 Voice
        self.plus_btn = ctk.CTkButton(
            action_row,
            text="＋ Attach",
            width=76,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_primary"],
            corner_radius=14,
            command=self._show_plus_menu
        )
        self.plus_btn.pack(side="left", padx=(2, 4))

        self.voice_btn = ctk.CTkButton(
            action_row,
            text="🎤 Voice",
            width=76,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_secondary"],
            corner_radius=14,
            command=self.handle_voice
        )
        self.voice_btn.pack(side="left", padx=2)

        # Right tools: Send and Stop buttons
        self.send_btn = ctk.CTkButton(
            action_row,
            text="Send ↑",
            width=76,
            height=28,
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            text_color=THEME["accent_text"],
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=14,
            command=self.handle_send
        )
        self.send_btn.pack(side="right")

        self.stop_btn = ctk.CTkButton(
            action_row,
            text="■ Stop",
            width=76,
            height=28,
            fg_color=THEME["error"],
            hover_color=THEME["error_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=14,
            command=self.handle_stop
        )

        # Floating "↓ Jump to latest" button (Smart Chat Scrolling - Requirement 11)
        self.jump_latest_btn = ctk.CTkButton(
            self,
            text="↓ Jump to latest",
            width=115,
            height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["accent"],
            border_color=THEME["border"],
            border_width=1,
            corner_radius=13,
            command=self._on_jump_latest_clicked
        )

        register_theme_listener(self.apply_theme)
        self._check_empty_state()

    def _on_user_scroll(self, event=None):
        try:
            yview = self.chat._parent_canvas.yview()
            if yview and len(yview) == 2:
                # If user scrolled up away from bottom (> 8% away from bottom), pause auto-scroll
                is_near_bottom = (yview[1] >= 0.92)
                self._auto_scroll_enabled = is_near_bottom
                if not is_near_bottom and len(self.conversation) > 1:
                    if not self.jump_latest_btn.winfo_ismapped():
                        self.jump_latest_btn.place(relx=0.5, rely=0.88, anchor="center")
                else:
                    if self.jump_latest_btn.winfo_ismapped():
                        self.jump_latest_btn.place_forget()
        except Exception:
            pass

    def _on_jump_latest_clicked(self):
        self._auto_scroll_enabled = True
        self._scroll_bottom()
        if self.jump_latest_btn.winfo_ismapped():
            self.jump_latest_btn.place_forget()

    def _show_plus_menu(self):
        """Displays contextual attachment options upon clicking [+].
        Positioned dynamically relative to the active composer (+ button).
        Home state -> near centered composer.
        Active chat -> near bottom composer.
        Never at the top-left corner.
        """
        menu_w = 230
        menu_h = 168

        try:
            self.update_idletasks()
            top_win = self.winfo_toplevel()
            top_win.update_idletasks()

            btn_x = self.plus_btn.winfo_rootx()
            btn_y = self.plus_btn.winfo_rooty()
            btn_w = self.plus_btn.winfo_width()
            btn_h = self.plus_btn.winfo_height()

            win_x = top_win.winfo_rootx()
            win_y = top_win.winfo_rooty()
            win_w = top_win.winfo_width()
            win_h = top_win.winfo_height()

            # Space available below plus button
            space_below = (win_y + win_h) - (btn_y + btn_h)

            if space_below >= menu_h + 12:
                # In Home state (centered composer) or when ample space exists below
                target_y = btn_y + btn_h + 6
            else:
                # In Active chat (bottom pinned composer) -> pop up right above button
                target_y = btn_y - menu_h - 6

            # Align X with the plus button
            target_x = btn_x

            # Clamp coordinates safely inside top-level window boundaries
            target_x = max(win_x + 10, min(target_x, win_x + win_w - menu_w - 10))
            target_y = max(win_y + 10, min(target_y, win_y + win_h - menu_h - 10))
        except Exception:
            top_win = self.winfo_toplevel()
            target_x = top_win.winfo_rootx() + 80
            target_y = top_win.winfo_rooty() + 200

        menu = ctk.CTkToplevel(self)
        menu.title("Attach")
        menu.geometry(f"{menu_w}x{menu_h}+{int(target_x)}+{int(target_y)}")
        menu.resizable(False, False)
        menu.configure(fg_color=THEME["bg_panel"])
        menu.transient(top_win)
        menu.attributes("-topmost", True)

        ctk.CTkLabel(
            menu,
            text="Add to message",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME["text_muted"]
        ).pack(anchor="w", padx=14, pady=(8, 4))

        def attach_doc():
            menu.destroy()
            self._trigger_add_doc()

        def attach_img():
            menu.destroy()
            f = filedialog.askopenfilename(
                title="Select Image for Vision",
                filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.webp"), ("All Files", "*.*")]
            )
            if f:
                self.attach_file(f)

        def attach_cam():
            menu.destroy()
            self._handle_camera()

        def attach_folder():
            menu.destroy()
            self._handle_add_from_folder()

        btn_opts = dict(
            anchor="w",
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_primary"],
            height=28,
            font=ctk.CTkFont(size=12)
        )
        ctk.CTkButton(menu, text="📄  Upload Document", command=attach_doc, **btn_opts).pack(fill="x", padx=8, pady=1)
        ctk.CTkButton(menu, text="🖼️  Add Image", command=attach_img, **btn_opts).pack(fill="x", padx=8, pady=1)
        ctk.CTkButton(menu, text="📷  Camera", command=attach_cam, **btn_opts).pack(fill="x", padx=8, pady=1)
        ctk.CTkButton(menu, text="📁  Add From Folder", command=attach_folder, **btn_opts).pack(fill="x", padx=8, pady=1)

        menu.bind("<Escape>", lambda e: menu.destroy())

        def _check_focus_out(e=None):
            def _eval():
                try:
                    f = menu.focus_get()
                    if f is None or not (str(f) == str(menu) or str(f).startswith(str(menu) + ".")):
                        menu.destroy()
                except Exception:
                    pass
            menu.after(140, _eval)

        menu.bind("<FocusOut>", _check_focus_out)
        menu.focus_force()

    def _handle_camera(self):
        try:
            from backend.camera import is_camera_available, capture_camera_frame
            if not is_camera_available():
                show_toast(self, "No camera detected on this system.", kind="warning")
                return

            cam_win = ctk.CTkToplevel(self.winfo_toplevel())
            cam_win.title("Camera — Infinity AI")
            cam_win.geometry("420x240")
            cam_win.resizable(False, False)
            cam_win.configure(fg_color=THEME["bg_panel"])
            cam_win.transient(self.winfo_toplevel())
            cam_win.grab_set()

            ctk.CTkLabel(
                cam_win,
                text="📷 Local Camera Capture",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=THEME["text_primary"]
            ).pack(pady=(16, 4))

            status_lbl = ctk.CTkLabel(
                cam_win,
                text="Ready to capture photo. All processing remains 100% offline.",
                font=ctk.CTkFont(size=11),
                text_color=THEME["text_secondary"]
            )
            status_lbl.pack(pady=4)

            def do_capture():
                status_lbl.configure(text="Capturing frame from camera…", text_color=THEME["accent"])
                cam_win.update_idletasks()
                res = capture_camera_frame()
                if res.get("ok"):
                    img_path = res["path"]
                    cam_win.destroy()
                    self.attach_file(img_path)
                    show_toast(self, "Photo attached. Add prompt and click Send.", kind="success")
                else:
                    err = res.get("error", "Camera capture failed.")
                    status_lbl.configure(text=f"⚠️ {err}", text_color=THEME["error"])

            btn_box = ctk.CTkFrame(cam_win, fg_color="transparent")
            btn_box.pack(pady=20)

            ctk.CTkButton(
                btn_box,
                text="📷 Capture & Attach",
                width=140,
                height=32,
                fg_color=THEME["accent"],
                hover_color=THEME["accent_hover"],
                text_color=THEME["accent_text"],
                font=ctk.CTkFont(size=12, weight="bold"),
                command=do_capture
            ).pack(side="left", padx=8)

            ctk.CTkButton(
                btn_box,
                text="Cancel",
                width=80,
                height=32,
                fg_color="transparent",
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_secondary"],
                font=ctk.CTkFont(size=12),
                command=cam_win.destroy
            ).pack(side="left", padx=8)

        except Exception as exc:
            show_toast(self, f"Camera error: {exc}", kind="error")

    def _handle_add_from_folder(self):
        folder = filedialog.askdirectory(title="Select Folder to Index Documents", parent=self.winfo_toplevel())
        if not folder:
            return
        p = Path(folder)
        supported_exts = {".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md", ".json", ".py"}
        found = [str(f) for f in p.glob("**/*") if f.is_file() and f.suffix.lower() in supported_exts]
        if not found:
            show_toast(self, f"No supported documents found in {p.name}.", kind="info")
            return
        first_doc = found[0]
        show_toast(self, f"Found {len(found)} documents in {p.name}. Adding {Path(first_doc).name}…", kind="info")
        top = self.winfo_toplevel()
        if hasattr(top, "process_pdf"):
            top.process_pdf(first_doc)
        elif self.on_add_document:
            self.on_add_document(first_doc)
        else:
            self.attach_file(first_doc)

    def _show_more_menu(self):
        """Displays conversation options (New Chat, Rename, Export, Delete)."""
        menu = ctk.CTkToplevel(self)
        menu.title("Conversation Options")
        menu.geometry("220x165")
        menu.resizable(False, False)
        menu.configure(fg_color=THEME["bg_panel"])
        menu.transient(self.winfo_toplevel())
        menu.grab_set()

        ctk.CTkLabel(menu, text="Conversation", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_muted"]).pack(anchor="w", padx=14, pady=(8, 4))

        def do_new():
            menu.destroy()
            self.start_new_conversation()

        def do_rename():
            menu.destroy()
            self._handle_title_rename()

        def do_export():
            menu.destroy()
            self.handle_export_conversation()

        def do_delete():
            menu.destroy()
            conv = get_conversation(self.conversation_id)
            title = conv["title"] if conv else "Current Chat"
            if messagebox.askyesno("Delete Conversation", f"Delete '{title}'?", parent=self.winfo_toplevel()):
                delete_conversation(self.conversation_id)
                self.start_new_conversation()

        ctk.CTkButton(menu, text="＋  New Chat", anchor="w", fg_color="transparent", hover_color=THEME["bg_hover"], height=26, font=ctk.CTkFont(size=12), command=do_new).pack(fill="x", padx=8, pady=1)
        ctk.CTkButton(menu, text="✏️  Rename", anchor="w", fg_color="transparent", hover_color=THEME["bg_hover"], height=26, font=ctk.CTkFont(size=12), command=do_rename).pack(fill="x", padx=8, pady=1)
        ctk.CTkButton(menu, text="📤  Export conversation", anchor="w", fg_color="transparent", hover_color=THEME["bg_hover"], height=26, font=ctk.CTkFont(size=12), command=do_export).pack(fill="x", padx=8, pady=1)
        ctk.CTkButton(menu, text="🗑️  Delete conversation", anchor="w", fg_color="transparent", hover_color=THEME["error_bg"], text_color=THEME["error"], height=26, font=ctk.CTkFont(size=12), command=do_delete).pack(fill="x", padx=8, pady=1)

    def _show_privacy_dialog(self):
        """Displays verification that workspace is 100% offline and private."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Infinity AI — Privacy & Security Verification")
        dialog.geometry("440x300")
        dialog.resizable(False, False)
        dialog.configure(fg_color=THEME["bg_secondary"])
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        head = ctk.CTkFrame(dialog, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        head.pack(fill="x")
        ctk.CTkLabel(head, text="🔒 100% Private & Air-Gapped", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["success"]).pack(padx=14, pady=10)

        body = ctk.CTkFrame(dialog, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        items = [
            ("• Local AI Engine:", "Ollama running on local loopback (127.0.0.1)"),
            ("• Cloud Telemetry:", "Zero external cloud requests or API keys required"),
            ("• Storage Security:", "All chats, databases, and vectors reside in D:\\PrivateAI"),
            ("• Hardware Key:", "USB acts strictly as an authorization key; no data on USB"),
            ("• Workspace Isolation:", "Bound to this laptop hardware; protected against cloning"),
        ]

        for k, v in items:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=k, font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_primary"]).pack(side="left")
            ctk.CTkLabel(row, text=f" {v}", font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"]).pack(side="left")

        ctk.CTkButton(dialog, text="Got it", fg_color=THEME["accent"], hover_color=THEME["accent_hover"], height=28, command=dialog.destroy).pack(pady=(0, 14))

    def _handle_title_rename(self):
        conv = get_conversation(self.conversation_id)
        current = conv["title"] if conv else "New Chat"
        new_title = simpledialog.askstring("Rename Chat", "Enter new chat title:", initialvalue=current, parent=self.winfo_toplevel())
        if new_title and new_title.strip():
            rename_conversation(self.conversation_id, new_title.strip())
            self.conv_title_label.configure(text=new_title.strip()[:30])

    def _handle_chip_open(self):
        if self.on_open_pdf_viewer:
            self.on_open_pdf_viewer()
        elif hasattr(self.master.winfo_toplevel(), "handle_nav_switch"):
            self.master.winfo_toplevel().handle_nav_switch("Documents")

    def _on_chat_resize(self, event=None):
        if self._resize_timer is not None:
            try:
                self.after_cancel(self._resize_timer)
            except Exception:
                pass
        self._resize_timer = self.after(80, self._do_chat_resize)

    def _do_chat_resize(self):
        self._resize_timer = None
        try:
            w = max(380, self.chat.winfo_width() - 80)
            for item in self._content_labels:
                try:
                    if hasattr(item, "update_dynamic_height"):
                        item.update_dynamic_height()
                    elif hasattr(item, "configure"):
                        item.configure(wraplength=min(560, max(260, int(w * 0.76))))
                except Exception:
                    pass
        except Exception:
            pass

    def _update_status_pill(self):
        pass

    def _build_empty_state(self):
        for w in self.home_frame.winfo_children():
            w.destroy()

        center_box = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        center_box.pack(pady=(35, 10))

        # Brand Glyph & Heading (Requirement 5)
        self.home_glyph = ctk.CTkLabel(
            center_box,
            text="∞",
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color=THEME["accent"]
        )
        self.home_glyph.pack(pady=(0, 2))

        self.home_title = ctk.CTkLabel(
            center_box,
            text="Infinity AI",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=THEME["text_primary"]
        )
        self.home_title.pack(pady=(0, 2))

        self.home_subtitle = ctk.CTkLabel(
            center_box,
            text="Private Local Intelligence. Your private local AI workspace.",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME["text_secondary"]
        )
        self.home_subtitle.pack(pady=(0, 3))

        self.home_desc = ctk.CTkLabel(
            center_box,
            text="Ask anything. Work with your files. Build locally.",
            font=ctk.CTkFont(size=12),
            text_color=THEME["text_muted"]
        )
        self.home_desc.pack(pady=(0, 12))

        # Centered Composer Slot (State A)
        self.home_composer_slot = ctk.CTkFrame(center_box, fg_color="transparent")
        self.home_composer_slot.pack(fill="x", padx=10, pady=(2, 14))

        # Primary Actions: Ask anything | Upload document | Start a project
        self.home_actions_row = ctk.CTkFrame(center_box, fg_color="transparent")
        self.home_actions_row.pack(pady=4)

        actions = [
            ("💬", "Ask anything", lambda: self.input.focus_set()),
            ("📄", "Upload document", self._trigger_add_doc),
            ("📁", "Start a project", self._trigger_open_projects),
        ]

        self.home_action_btns = []
        for icon, label, cmd in actions:
            btn = ctk.CTkButton(
                self.home_actions_row,
                text=f"{icon}  {label}",
                height=36,
                width=150,
                fg_color=THEME["bg_surface"],
                hover_color=THEME["bg_hover"],
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=THEME["text_primary"],
                border_color=THEME["border"],
                border_width=1,
                corner_radius=10,
                command=cmd
            )
            btn.pack(side="left", padx=6)
            self.home_action_btns.append(btn)

        # Subtle suggestion prompts underneath
        self.home_sugg_row = ctk.CTkFrame(center_box, fg_color="transparent")
        self.home_sugg_row.pack(pady=(14, 0))

        suggestions = [
            "Explain Dijkstra algorithm with an example",
            "Write Python code for binary search",
            "Summarize a PDF",
            "Help me build a project"
        ]
        self.home_sugg_btns = []
        for s_prompt in suggestions:
            btn = ctk.CTkButton(
                self.home_sugg_row,
                text=s_prompt,
                height=28,
                fg_color="transparent",
                hover_color=THEME["bg_hover"],
                font=ctk.CTkFont(size=11),
                text_color=THEME["text_secondary"],
                border_color=THEME["border"],
                border_width=1,
                corner_radius=14,
                command=lambda p=s_prompt: self._set_prompt_and_send(p)
            )
            btn.pack(side="left", padx=4)
            self.home_sugg_btns.append(btn)

    def _show_home_state(self):
        self._current_ui_state = "home"
        try:
            self.chat.pack_forget()
            self.home_frame.pack(fill="both", expand=True, padx=8, pady=4)
            self.composer_card.pack_forget()
            if hasattr(self, "home_composer_slot"):
                self.composer_card.pack(fill="x", padx=10, pady=4, in_=self.home_composer_slot)
        except Exception:
            pass

    def _show_active_chat_state(self):
        self._current_ui_state = "active"
        try:
            self.home_frame.pack_forget()
            self.composer_card.pack_forget()
            self.chat.pack(fill="both", expand=True, padx=8, pady=4)
            self.composer_card.pack(fill="x", padx=12, pady=(4, 8), side="bottom", in_=self)
            if hasattr(self, "bottom_spacer"):
                self.bottom_spacer.pack(fill="x", pady=12)
        except Exception:
            pass

    def _check_empty_state(self):
        if not self.conversation:
            self._show_home_state()
        else:
            self._show_active_chat_state()

    def _set_prompt_and_send(self, text: str):
        self.input.delete("1.0", "end")
        self.input.insert("1.0", text)
        self.handle_send()

    def _auto_size_input(self, event=None):
        try:
            text = self.input.get("1.0", "end-1c")
            line_count = len(text.split("\n"))
            target_h = max(42, min(120, 24 + line_count * 18))
            if self.input.cget("height") != target_h:
                self.input.configure(height=target_h)
        except Exception:
            pass

    def _open_history_modal(self):
        ConversationHistoryModal(
            self.winfo_toplevel(),
            current_cid=self.conversation_id,
            on_select=lambda cid: (hasattr(self.master.winfo_toplevel(), "load_selected_chat") and self.master.winfo_toplevel().load_selected_chat(cid)) or self.load_conversation(cid),
            on_new=lambda: (hasattr(self.master.winfo_toplevel(), "handle_new_chat") and self.master.winfo_toplevel().handle_new_chat()) or self.start_new_conversation()
        )

    def _set_prompt_and_focus(self, text: str):
        self.input.delete("1.0", "end")
        self.input.insert("1.0", text + " ")
        self.input.focus_set()

    def set_document_context_mode(self, mode_name: str = "Document"):
        if mode_name in ["Normal", "Document", "RAG"]:
            self.context_mode_var.set(mode_name)

    def set_document_active(self, info: Dict[str, Any], status: str = "Ready", on_summarize=None, on_ask=None, on_open_pdf=None):
        self.active_doc_info = info
        self.active_doc_callbacks = {
            "on_summarize": on_summarize,
            "on_ask": on_ask,
            "on_open_pdf": on_open_pdf
        }
        self.set_document_context_mode("Document")
        self.show_document_card(
            info["name"],
            status=status,
            page_count=info.get("page_count", 1),
            chunk_count=info.get("chunk_count", 1),
            on_summarize=on_summarize,
            on_ask=on_ask,
            on_open_pdf=on_open_pdf
        )
        status_suffix = f" ({status})" if status != "Ready" else ""
        self.doc_chip_label.configure(text=f"📄  {info['name']}{status_suffix}")
        self.doc_chip.pack(fill="x", padx=8, pady=(4, 2), before=self.input)
        self.top_doc_label.configure(text=f"• 📄 {info['name']}")

    def update_document_status(self, status: str, page_count: Any = None):
        if self.active_doc_info:
            self.active_doc_info["status"] = status
            if page_count:
                self.active_doc_info["page_count"] = page_count
            cbs = getattr(self, "active_doc_callbacks", {})
            self.show_document_card(
                self.active_doc_info["name"],
                status=status,
                page_count=self.active_doc_info.get("page_count", 1),
                chunk_count=self.active_doc_info.get("chunk_count", 1),
                on_summarize=cbs.get("on_summarize"),
                on_ask=cbs.get("on_ask"),
                on_open_pdf=cbs.get("on_open_pdf")
            )
            status_suffix = f" ({status})" if status != "Ready" else ""
            self.doc_chip_label.configure(text=f"📄  {self.active_doc_info['name']}{status_suffix}")

    def clear_document_active(self):
        self.active_doc_info = None
        self.active_doc_callbacks = {}
        self.doc_card.pack_forget()
        self.doc_chip.pack_forget()
        self.top_doc_label.configure(text="")
        self.set_document_context_mode("Normal")

    def close_active_document(self):
        self.clear_document_active()
        if self.on_close_doc:
            self.on_close_doc()

    def show_document_card(self, doc_name: str, status: str = "Ready", page_count: Any = 1, chunk_count: int = 1, on_summarize=None, on_ask=None, on_open_pdf=None):
        for w in self.doc_card.winfo_children():
            w.destroy()

        top_row = ctk.CTkFrame(self.doc_card, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            top_row,
            text=f"📄  {doc_name}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=THEME["text_primary"],
            anchor="w"
        ).pack(side="left")

        ctk.CTkButton(
            top_row,
            text="✕",
            width=22,
            height=22,
            fg_color="transparent",
            hover_color=THEME["error_hover"],
            font=ctk.CTkFont(size=11),
            command=self.close_active_document
        ).pack(side="right")

        is_ready = (status == "Ready")
        is_indexing = "index" in status.lower() or "upload" in status.lower() or "process" in status.lower()
        if is_ready:
            pg_str = f"{page_count} pages • " if page_count and page_count != "..." else ""
            meta_txt = f"{pg_str}Ready ✓"
            status_color = THEME["success"]
        elif is_indexing:
            meta_txt = f"{status} Please wait…"
            status_color = THEME["accent"]
        else:
            meta_txt = f"Status: {status}"
            status_color = THEME["text_muted"]

        ctk.CTkLabel(
            self.doc_card,
            text=meta_txt,
            font=ctk.CTkFont(size=11),
            text_color=status_color,
            anchor="w"
        ).pack(fill="x", padx=10, pady=(0, 6))

        btn_row = ctk.CTkFrame(self.doc_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 8))

        ext = Path(doc_name).suffix.lower()
        if is_ready:
            if ext in [".ppt", ".pptx"]:
                if on_open_pdf:
                    ctk.CTkButton(btn_row, text="📖 Open", width=80, height=26, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], font=ctk.CTkFont(size=11, weight="bold"), command=on_open_pdf).pack(side="left", padx=(0, 6))
                ctk.CTkButton(btn_row, text="⚡ Summarize", width=95, height=26, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], font=ctk.CTkFont(size=11, weight="bold"), command=on_summarize or (lambda: self._set_prompt_and_send("Summarize these presentation slides"))).pack(side="left", padx=(0, 6))
                ctk.CTkButton(btn_row, text="💡 Explain Slides", width=110, height=26, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], font=ctk.CTkFont(size=11, weight="bold"), command=lambda: self._set_prompt_and_send("Explain the key concepts across these slides")).pack(side="left", padx=(0, 6))
                ctk.CTkButton(btn_row, text="💬 Ask Presentation", width=125, height=26, fg_color=THEME["accent"], hover_color=THEME["accent_hover"], font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent_text"], command=on_ask or (lambda: self.input.focus_set())).pack(side="left")
            elif ext in [".xlsx", ".xls", ".csv", ".tsv"]:
                ctk.CTkButton(btn_row, text="📊 Analyze", width=85, height=26, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], font=ctk.CTkFont(size=11, weight="bold"), command=lambda: self._set_prompt_and_send("Analyze this dataset, statistics, and column trends")).pack(side="left", padx=(0, 6))
                ctk.CTkButton(btn_row, text="⚡ Summarize", width=95, height=26, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], font=ctk.CTkFont(size=11, weight="bold"), command=on_summarize or (lambda: self._set_prompt_and_send("Summarize the key data metrics and trends"))).pack(side="left", padx=(0, 6))
                ctk.CTkButton(btn_row, text="💬 Ask Data", width=95, height=26, fg_color=THEME["accent"], hover_color=THEME["accent_hover"], font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent_text"], command=on_ask or (lambda: self.input.focus_set())).pack(side="left")
            elif ext in [".py", ".js", ".ts", ".java", ".cpp", ".c", ".html", ".css", ".sql"]:
                ctk.CTkButton(btn_row, text="🔍 Analyze", width=85, height=26, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], font=ctk.CTkFont(size=11, weight="bold"), command=lambda: self._set_prompt_and_send("Analyze this source code structure and components")).pack(side="left", padx=(0, 6))
                ctk.CTkButton(btn_row, text="🐞 Find Bugs", width=95, height=26, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], font=ctk.CTkFont(size=11, weight="bold"), command=lambda: self._set_prompt_and_send("Inspect this code and identify potential bugs or edge cases")).pack(side="left", padx=(0, 6))
                ctk.CTkButton(btn_row, text="💬 Ask Codebase", width=115, height=26, fg_color=THEME["accent"], hover_color=THEME["accent_hover"], font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent_text"], command=on_ask or (lambda: self.input.focus_set())).pack(side="left")
            else:
                if on_open_pdf:
                    ctk.CTkButton(
                        btn_row,
                        text="📖 Open PDF",
                        width=95,
                        height=26,
                        fg_color=THEME["accent"],
                        hover_color=THEME["accent_hover"],
                        font=ctk.CTkFont(size=11, weight="bold"),
                        command=on_open_pdf
                    ).pack(side="left", padx=(0, 6))

                if on_summarize:
                    ctk.CTkButton(
                        btn_row,
                        text="⚡ Summarize",
                        width=95,
                        height=26,
                        fg_color=THEME["bg_panel"],
                        hover_color=THEME["bg_hover"],
                        font=ctk.CTkFont(size=11, weight="bold"),
                        command=on_summarize
                    ).pack(side="left", padx=(0, 6))

                if on_ask:
                    ctk.CTkButton(
                        btn_row,
                        text="💬 Ask Document",
                        width=115,
                        height=26,
                        fg_color=THEME["bg_panel"] if on_open_pdf else THEME["accent"],
                        hover_color=THEME["bg_hover"] if on_open_pdf else THEME["accent_hover"],
                        font=ctk.CTkFont(size=11, weight="bold"),
                        command=on_ask
                    ).pack(side="left")

        self.doc_card.pack(fill="x", padx=8, pady=(4, 4))

    def hide_document_card(self):
        self.close_active_document()

    def start_new_conversation(self):
        """Creates a completely clean temporary draft conversation state with zero document or context inheritance."""
        import uuid
        self.conversation_id = str(uuid.uuid4())
        self._is_draft = True
        self.clear_document_active()
        self.clear_attachment()
        self.clear_conversation()
        self.conv_title_label.configure(text="New Chat")
        self._show_home_state()
        try:
            top = self.winfo_toplevel()
            if hasattr(top, "sidebar") and hasattr(top.sidebar, "set_active_chat"):
                top.sidebar.set_active_chat(None)
        except Exception:
            pass

    def load_conversation(self, cid: str):
        self.conversation_id = cid
        self._is_draft = False
        self.clear_conversation()
        self._load_saved_messages()
        conv = get_conversation(cid)
        if conv:
            self.conv_title_label.configure(text=conv['title'][:30])

    def _enter(self, event):
        if event.state & 0x0001:  # Shift + Enter creates newline
            return
        self.handle_send()
        return "break"

    def _smart_scroll(self, force_bottom: bool = False):
        """Scrolls smoothly. If user manually scrolled upwards, honors user scroll position."""
        try:
            if force_bottom or self._auto_scroll_enabled:
                self.chat._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _scroll_bottom(self):
        self._smart_scroll(force_bottom=True)

    def _load_saved_messages(self):
        try:
            saved = get_messages(self.conversation_id)
            for m in saved:
                if m["role"] == "user":
                    self._bubble("You", m["content"], user=True)
                else:
                    self._bubble("Infinity AI", m["content"], user=False, citations=m.get("citations"), model=m.get("model"))
                self.conversation.append(m)
            self._check_empty_state()
            if self.conversation and len(self.conversation) >= 2:
                last_m = self.conversation[-1]
                if last_m.get("role") == "assistant":
                    last_u = self.conversation[-2].get("content", "")
                    self._show_dynamic_context_suggestions(last_u, ai_response=last_m.get("content"))
            self._scroll_bottom()
        except Exception:
            pass

    def handle_attach(self):
        f = filedialog.askopenfilename(
            title="Attach File or Document",
            filetypes=[
                ("All Supported Files", "*.pdf;*.docx;*.pptx;*.xlsx;*.csv;*.txt;*.md;*.json;*.py;*.js;*.ts;*.html;*.css;*.java;*.cpp;*.c;*.sql;*.log;*.yaml;*.xml;*.png;*.jpg;*.jpeg;*.webp"),
                ("Documents", "*.pdf;*.docx;*.pptx;*.xlsx;*.csv;*.txt;*.md;*.json"),
                ("Images", "*.png;*.jpg;*.jpeg;*.webp"),
                ("All Files", "*.*")
            ]
        )
        if f:
            self.attach_file(f)

    def handle_file_drop(self, event):
        try:
            paths = self.tk.splitlist(event.data)
            if not paths:
                return
            for p in paths:
                if not os.path.exists(p):
                    continue
                abs_p = os.path.abspath(p)
                if is_image_file(abs_p):
                    self.attach_file(abs_p)
                else:
                    top = self.winfo_toplevel()
                    if hasattr(top, "process_pdf"):
                        top.process_pdf(abs_p)
                    elif self.on_add_document:
                        self.on_add_document(abs_p)
                    else:
                        self.attach_file(abs_p)
            return "copy"
        except Exception as exc:
            show_toast(self, f"Drop error: {exc}", kind="error")

    def attach_file(self, path):
        if not os.path.isfile(path):
            messagebox.showerror("Infinity AI", "The selected item is not a file.", parent=self)
            return
        self.attached_file = os.path.abspath(path)
        res = extract_file_content(self.attached_file, max_chars=20000)
        self.attached_content = res.get("content", "")
        icon = "🖼️" if is_image_file(self.attached_file) else "📎"
        self.attach_label.configure(
            text=f"{icon} {Path(self.attached_file).name} ({res.get('file_type', 'file')})"
        )
        self.attach_banner.pack(fill="x", padx=8, pady=(4, 2), before=self.input)

    def clear_attachment(self):
        self.attached_file = None
        self.attached_content = None
        self.attach_banner.pack_forget()

    def _get_selected_voice_lang(self) -> str:
        var = getattr(self, "voice_lang_var", None)
        val = var.get() if var else "Auto Detect"
        mapping = {
            "Auto Detect": "auto",
            "English": "en",
            "Hindi": "hi",
            "Marathi": "mr",
        }
        return mapping.get(val, "auto")

    def handle_voice(self):
        status = get_voice_status()
        if not status["is_listening"]:
            self._voice_cancelled = False
            self.voice_recording_bar.pack(fill="x", padx=8, pady=(4, 2), before=self.input)
            self.voice_status_label.configure(
                text="🔴 Listening... Speak clearly into your microphone",
                text_color=THEME["error"]
            )
            self.voice_btn.configure(
                text="🔴 Recording",
                fg_color=THEME["error_bg"],
                text_color=THEME["error"]
            )

            selected_lang = self._get_selected_voice_lang()

            def record_worker():
                res = listen_and_transcribe_result(timeout_seconds=8, language=selected_lang)
                self.after(0, lambda: self._handle_voice_result(res))

            import threading
            threading.Thread(target=record_worker, daemon=True).start()
        else:
            self._stop_voice()

    def _stop_voice(self):
        self.voice_status_label.configure(
            text="⏳ Transcribing audio...",
            text_color=THEME["accent"]
        )
        stop_listening()

    def _cancel_voice(self):
        self._voice_cancelled = True
        cancel_listening()
        self._finish_voice()

    def _finish_voice(self):
        self.voice_recording_bar.pack_forget()
        self.voice_btn.configure(
            text="🎤 Voice",
            fg_color="transparent",
            text_color=THEME["text_secondary"]
        )

    def _handle_voice_result(self, res: dict):
        self._finish_voice()
        if getattr(self, "_voice_cancelled", False):
            self._voice_cancelled = False
            return

        if not res or not res.get("ok"):
            err = (res or {}).get("error", "Recording failed")
            if "device" in err.lower() or "microphone" in err.lower() or "input" in err.lower():
                show_toast(self, "Microphone unavailable. Check Windows microphone permissions.", kind="error")
            else:
                show_toast(self, f"Voice input: {err}", kind="warning")
            return

        text = res.get("text", "").strip()
        if not text:
            show_toast(self, "No speech detected. Please speak clearly into your microphone.", kind="info")
            return

        # Insert transcript into composer so user can review and edit before sending (Requirement 36)
        current = self.input.get("1.0", "end-1c").strip()
        if current:
            new_text = current + " " + text
        else:
            new_text = text
        self.input.delete("1.0", "end")
        self.input.insert("1.0", new_text)
        self._auto_size_input()
        self.input.focus_set()
        show_toast(self, "Transcript inserted. Please review before sending.", kind="success")

    def handle_export_conversation(self):
        if not self.conversation:
            messagebox.showinfo("Export", "No messages in the current conversation to export.")
            return

        fmt_choice = simpledialog.askstring("Export Format", "Enter export format (markdown / txt / json):", initialvalue="markdown", parent=self)
        if not fmt_choice:
            return

        fmt = fmt_choice.strip().lower()
        if fmt not in ["markdown", "md", "txt", "json"]:
            fmt = "markdown"

        ext = ".json" if fmt == "json" else (".txt" if fmt in ["txt", "text"] else ".md")
        content = export_conversation(self.conversation_id, fmt=fmt)

        target = filedialog.asksaveasfilename(
            title="Export Conversation",
            defaultextension=ext,
            initialfile=f"chat_export_{self.conversation_id[:8]}{ext}",
            filetypes=[("Export File", f"*{ext}")]
        )
        if target:
            with open(target, "w", encoding="utf-8") as fp:
                fp.write(content)
            messagebox.showinfo("Export Complete", f"Conversation exported to:\n{target}")

    def add_user_message(self, text: str):
        if hasattr(self, "dynamic_sugg_frame"):
            self.dynamic_sugg_frame.pack_forget()
        self._show_active_chat_state()
        self._bubble("You", text, user=True)
        self.conversation.append({"role": "user", "content": text})

        # Zero-history mode (Requirement 5): RAM session only, never persist to SQLite
        smart_title = generate_friendly_title(text) or "Conversation"
        if getattr(self, "_is_draft", False):
            self._is_draft = False
            self.conv_title_label.configure(text=smart_title[:30])
        elif self.conv_title_label.cget("text") in ["", "New Chat", "New Conversation"]:
            self.conv_title_label.configure(text=smart_title[:30])

        self.last_user_query = text

    def _show_dynamic_context_suggestions(self, query: str, ai_response: Optional[str] = None):
        if not hasattr(self, "dynamic_sugg_frame") or not self.dynamic_sugg_frame.winfo_exists():
            self.dynamic_sugg_frame = ctk.CTkFrame(self.chat, fg_color="transparent")
        else:
            for w in self.dynamic_sugg_frame.winfo_children():
                w.destroy()

        has_doc = (self.active_doc_info is not None)
        active_project = None
        try:
            from backend.projects import project_service
            active_project = project_service.get_active_project()
        except Exception:
            pass

        try:
            from backend.intent_engine import intent_engine
            analysis = intent_engine.analyze(
                query,
                ai_response=ai_response,
                has_active_document=has_doc,
                active_document=self.active_doc_info,
                active_project=active_project
            )
            suggestions = analysis.get("suggestions", [])[:5]
        except Exception:
            suggestions = []

        if not suggestions:
            if hasattr(self, "dynamic_sugg_frame") and self.dynamic_sugg_frame.winfo_exists():
                self.dynamic_sugg_frame.pack_forget()
            return

        header_lbl = ctk.CTkLabel(
            self.dynamic_sugg_frame,
            text="Related topics & actions:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME["text_muted"],
            anchor="w"
        )
        header_lbl.pack(fill="x", padx=10, pady=(6, 2))

        # Compact pill layout across 1 or 2 rows so chips are never truncated
        row1 = ctk.CTkFrame(self.dynamic_sugg_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=(0, 2))

        row2 = None
        if len(suggestions) > 3:
            row2 = ctk.CTkFrame(self.dynamic_sugg_frame, fg_color="transparent")
            row2.pack(fill="x", padx=10, pady=(0, 4))

        for idx, s in enumerate(suggestions):
            target_row = row2 if (row2 is not None and idx >= 3) else row1
            btn = ctk.CTkButton(
                target_row,
                text=f"• {s}",
                height=26,
                fg_color=THEME["bg_surface"],
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_primary"],
                border_color=THEME["border"],
                border_width=1,
                corner_radius=13,
                font=ctk.CTkFont(size=11),
                command=lambda p=s: self._set_prompt_and_send(p)
            )
            btn.pack(side="left", padx=(0, 6), pady=2)

        self.dynamic_sugg_frame.pack(fill="x", padx=6, pady=4)
        if hasattr(self, "bottom_spacer"):
            self.bottom_spacer.pack_forget()
            self.bottom_spacer.pack(fill="x", pady=12)
        self._smart_scroll()

    def _edit_message(self, text: str):
        self.input.delete("1.0", "end")
        self.input.insert("1.0", text)
        self.input.focus_set()

    def _bubble(self, label: str, text: str, user: bool = False, citations: Optional[List[Dict[str, Any]]] = None, model: Optional[str] = None):
        row = ctk.CTkFrame(self.chat, fg_color="transparent")
        row.pack(fill="x", padx=4, pady=3)

        chat_w = max(380, self.chat.winfo_width() - 90)

        if user:
            card = ctk.CTkFrame(row, fg_color=THEME["user_bubble"], corner_radius=14, border_width=0)
            self._user_bubble_cards.append(card)
            card.pack(side="right", padx=(50, 4), pady=2)

            header_box = ctk.CTkFrame(card, fg_color="transparent")
            header_box.pack(fill="x", padx=12, pady=(6, 0))

            ctk.CTkLabel(
                header_box,
                text="You",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=THEME["text_muted"]
            ).pack(side="left")

            body = ctk.CTkLabel(
                card,
                text=text,
                anchor="w",
                justify="left",
                wraplength=min(560, chat_w),
                font=ctk.CTkFont(size=13),
                text_color=THEME["text_primary"]
            )
            body.pack(fill="x", padx=12, pady=(4, 6))
            self._content_labels.append(body)

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", padx=8, pady=(0, 4))
            ctk.CTkButton(
                actions,
                text="✏️ Edit",
                width=45,
                height=18,
                fg_color="transparent",
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_muted"],
                font=ctk.CTkFont(size=10),
                command=lambda t=text: self._edit_message(t)
            ).pack(side="right")
            return card
        else:
            # Seamless canvas layout, no giant card container or heavy borders (Requirement 12)
            card = ctk.CTkFrame(row, fg_color="transparent", corner_radius=0, border_width=0)
            card.pack(fill="x", padx=(4, 20), pady=4)

            header_box = ctk.CTkFrame(card, fg_color="transparent")
            header_box.pack(fill="x", padx=8, pady=(4, 2))

            ctk.CTkLabel(
                header_box,
                text="Infinity AI",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=THEME["accent"]
            ).pack(side="left")

            body = RichMarkdownText(card, bg_color=THEME["bg_secondary"], fg_color=THEME["text_primary"])
            body.pack(fill="x", padx=8, pady=(2, 6))
            body.render_markdown(text)
            self._content_labels.append(body)

            # Citations card
            if citations:
                cit_frame = ctk.CTkFrame(card, fg_color=THEME["bg_surface"], corner_radius=8, border_color=THEME["border"], border_width=1)
                cit_frame.pack(fill="x", padx=8, pady=(4, 6))
                ctk.CTkLabel(
                    cit_frame,
                    text="📌 SOURCES & CITATIONS:",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=THEME["text_muted"]
                ).pack(anchor="w", padx=10, pady=(6, 2))
                for c in citations[:4]:
                    doc_n = c.get("document", c.get("filename", "Doc"))
                    pg = c.get("page", 1)
                    c_lbl = ctk.CTkLabel(
                        cit_frame,
                        text=f"• {doc_n} (Page {pg})",
                        font=ctk.CTkFont(size=10),
                        text_color=THEME["accent"]
                    )
                    c_lbl.pack(anchor="w", padx=14, pady=1)

            # Response action bar
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", padx=6, pady=(0, 6))

            code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
            if code_blocks:
                ctk.CTkButton(
                    actions,
                    text="📋 Copy Code",
                    width=85,
                    height=22,
                    fg_color=THEME["bg_panel"],
                    hover_color=THEME["bg_hover"],
                    text_color=THEME["text_primary"],
                    font=ctk.CTkFont(size=10),
                    command=lambda cb=code_blocks[0]: self._copy(cb)
                ).pack(side="right", padx=2)

            ctk.CTkButton(
                actions,
                text="Copy",
                width=45,
                height=22,
                fg_color=THEME["bg_panel"],
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_primary"],
                font=ctk.CTkFont(size=10),
                command=lambda t=text: self._copy(t)
            ).pack(side="right", padx=2)

            ctk.CTkButton(
                actions,
                text="🔄 Retry",
                width=55,
                height=22,
                fg_color=THEME["bg_panel"],
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_primary"],
                font=ctk.CTkFont(size=10),
                command=self._regenerate_last
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                actions,
                text="👍",
                width=28,
                height=22,
                fg_color="transparent",
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_secondary"],
                command=lambda: None
            ).pack(side="left", padx=1)

            ctk.CTkButton(
                actions,
                text="👎",
                width=28,
                height=22,
                fg_color="transparent",
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_secondary"],
                command=lambda: None
            ).pack(side="left", padx=1)

            ctk.CTkButton(
                actions,
                text="🔊",
                width=28,
                height=22,
                fg_color="transparent",
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_secondary"],
                command=lambda t=text: speak_text(t)
            ).pack(side="left", padx=1)

            if hasattr(self, "bottom_spacer"):
                self.bottom_spacer.pack_forget()
                self.bottom_spacer.pack(fill="x", pady=12)

            return card

    def _regenerate_last(self):
        if self.last_user_query and not self.generating:
            target_model = self.get_selected_model(prompt=self.last_user_query)
            if self.on_send_message:
                self.on_send_message(
                    self.last_user_query,
                    None,
                    self.mode_var.get(),
                    target_model,
                    context_mode=self.context_mode_var.get().lower()
                )

    def add_user_and_send(self, prompt: str):
        if not self.generating:
            self.add_user_message(prompt)
            target_model = self.get_selected_model(prompt=prompt)
            if self.on_send_message:
                self.on_send_message(
                    prompt,
                    None,
                    self.mode_var.get(),
                    target_model,
                    context_mode=self.context_mode_var.get().lower()
                )

    def create_ai_stream_bubble(self, citations: Optional[List[Dict[str, Any]]] = None, initial_status: str = "Thinking…"):
        self._show_active_chat_state()
        row = ctk.CTkFrame(self.chat, fg_color="transparent")
        row.pack(fill="x", padx=4, pady=3)

        card = ctk.CTkFrame(row, fg_color="transparent", corner_radius=0, border_width=0)
        card.pack(fill="x", padx=(4, 20), pady=4)

        header_box = ctk.CTkFrame(card, fg_color="transparent")
        header_box.pack(fill="x", padx=8, pady=(4, 2))

        ctk.CTkLabel(
            header_box,
            text="Infinity AI",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=THEME["accent"]
        ).pack(side="left")

        lbl = RichMarkdownText(card, bg_color=THEME["bg_secondary"], fg_color=THEME["text_primary"])
        lbl.pack(fill="x", padx=8, pady=(2, 6))
        lbl.render_markdown(initial_status)
        self._content_labels.append(lbl)

        buf = []
        token_q = queue.Queue()
        self.generating = True
        self._auto_scroll_enabled = True
        self.send_btn.pack_forget()
        self.stop_btn.pack(side="right")
        self.stop_btn.configure(state="normal")

        # Worker calls append and set_status safely from background threads
        def append(text):
            if text:
                token_q.put(("token", text))

        def set_status(msg):
            if msg:
                token_q.put(("status", msg))

        append.set_status = set_status

        def finish():
            token_q.put(("finish", None))

        stream_state = {"completed": False}

        def _complete_stream(final_text: str):
            if stream_state["completed"]:
                return
            stream_state["completed"] = True

            clean_text = final_text.strip() if final_text else ""
            if not clean_text:
                if not self.generating or getattr(self, "_stop_requested", False):
                    final_text = "*[Generation stopped by user]*"
                else:
                    final_text = (
                        "⚠️ **No response received.**\n\n"
                        "The local model is unavailable, timed out, or returned an empty response. "
                        "Please verify that Ollama is running and has a compatible model loaded.\n\n"
                        "Click **🔄 Retry** below to try generating this response again."
                    )
            elif (not self.generating or getattr(self, "_stop_requested", False)) and not clean_text.endswith("*"):
                final_text = clean_text + "\n\n*[Generation stopped by user]*"

            self._stop_requested = False
            self._update_stream_label(lbl, final_text)

            # Citations Box
            if citations:
                cit_frame = ctk.CTkFrame(card, fg_color=THEME["bg_surface"], corner_radius=8, border_color=THEME["border"], border_width=1)
                cit_frame.pack(fill="x", padx=8, pady=(4, 6))
                ctk.CTkLabel(
                    cit_frame,
                    text="📌 SOURCES & CITATIONS:",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=THEME["text_muted"]
                ).pack(anchor="w", padx=10, pady=(6, 2))
                for c in citations[:4]:
                    ctk.CTkLabel(
                        cit_frame,
                        text=f"• {c.get('document', 'Doc')} (Page {c.get('page', 1)})",
                        font=ctk.CTkFont(size=10),
                        text_color=THEME["accent"]
                    ).pack(anchor="w", padx=14, pady=1)

            # Actions
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", padx=6, pady=(0, 6))

            ctk.CTkButton(
                actions,
                text="🔊",
                width=28,
                height=22,
                fg_color="transparent",
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_secondary"],
                command=lambda t=final_text: speak_text(t)
            ).pack(side="left", padx=1)

            ctk.CTkButton(
                actions,
                text="🔄 Retry",
                width=55,
                height=22,
                fg_color=THEME["bg_panel"],
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_primary"],
                font=ctk.CTkFont(size=10),
                command=self._regenerate_last
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                actions,
                text="👍",
                width=28,
                height=22,
                fg_color="transparent",
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_secondary"],
                command=lambda: None
            ).pack(side="left", padx=1)

            ctk.CTkButton(
                actions,
                text="👎",
                width=28,
                height=22,
                fg_color="transparent",
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_secondary"],
                command=lambda: None
            ).pack(side="left", padx=1)

            # Code block copy button
            code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", final_text, re.DOTALL)
            if code_blocks:
                ctk.CTkButton(
                    actions,
                    text="📋 Copy Code",
                    width=85,
                    height=22,
                    fg_color=THEME["bg_panel"],
                    hover_color=THEME["bg_hover"],
                    text_color=THEME["text_primary"],
                    font=ctk.CTkFont(size=10),
                    command=lambda cb=code_blocks[0]: self._copy(cb)
                ).pack(side="right", padx=2)

            ctk.CTkButton(
                actions,
                text="Copy",
                width=45,
                height=22,
                fg_color=THEME["bg_panel"],
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_primary"],
                font=ctk.CTkFont(size=10),
                command=lambda t=final_text: self._copy(t)
            ).pack(side="right", padx=2)

            active_m = self.get_selected_model()
            self.conversation.append({"role": "assistant", "content": final_text, "citations": citations or [], "model": active_m})

            # Adaptive preference learning (Requirement 24 - local & transparent)
            try:
                from backend.adaptive_preferences import adaptive_preference_engine
                adaptive_preference_engine.observe_user_interaction(self.last_user_query)
            except Exception:
                pass

            # Context-aware dynamic suggestions updated after every AI response
            try:
                self._show_dynamic_context_suggestions(self.last_user_query, ai_response=final_text)
            except Exception:
                pass

            self.generating = False
            self.stop_btn.pack_forget()
            self.send_btn.pack(side="right")
            if hasattr(self, "bottom_spacer"):
                self.bottom_spacer.pack_forget()
                self.bottom_spacer.pack(fill="x", pady=12)
            self._smart_scroll()

        def _poll_stream():
            if stream_state["completed"]:
                return
            new_tokens = []
            is_finished = False

            while not token_q.empty():
                try:
                    kind, val = token_q.get_nowait()
                    if kind == "token":
                        new_tokens.append(val)
                    elif kind == "status":
                        if not buf:
                            self._update_stream_label(lbl, val)
                    elif kind == "finish":
                        is_finished = True
                except Exception:
                    break

            if new_tokens:
                buf.extend(new_tokens)
                self._update_stream_label(lbl, "".join(buf))

            if not self.generating or is_finished:
                _complete_stream("".join(buf))
                return

            self.after(35, _poll_stream)

        self.after(35, _poll_stream)
        return append, finish

    def _update_stream_label(self, label, text):
        try:
            if hasattr(label, "render_markdown"):
                label.render_markdown(text)
            else:
                label.configure(text=text)
            self._smart_scroll()
        except Exception:
            pass

    def handle_send(self):
        q = self.input.get("1.0", "end").strip()
        if not q or self.generating:
            return

        self.input.delete("1.0", "end")

        attached = self.attached_file
        attached_txt = self.attached_content
        if attached:
            self.clear_attachment()

        # Augment prompt if a file was attached
        if attached and attached_txt and not is_image_file(attached):
            full_prompt = f"[Attached File: {Path(attached).name}]\n```\n{attached_txt[:12000]}\n```\n\nUser Question: {q}"
        else:
            full_prompt = q

        self.add_user_message(q)

        # Route model
        route_info = route_model_detailed(
            q,
            override_mode=self.model_var.get(),
            has_image=bool(attached and is_image_file(attached))
        )
        target_model = route_info["model_used"]

        # Intelligent context mode selection:
        # If document active and user question, use document mode
        c_mode = self.context_mode_var.get().lower()
        if self.active_doc_info and c_mode != "rag":
            c_mode = "document"

        if self.on_send_message:
            self.on_send_message(
                full_prompt,
                attached if (attached and is_image_file(attached)) else None,
                self.mode_var.get(),
                target_model,
                context_mode=c_mode
            )

    def get_selected_model(self, prompt: str = "", has_image: bool = False) -> str:
        selected_option = self.model_var.get()
        model_name, category, exp = route_model(prompt, override_mode=selected_option, has_image=has_image)
        return model_name

    def handle_stop(self):
        self._stop_requested = True
        if self.on_stop:
            self.on_stop()
        stop_speaking()
        self.generating = False
        self.stop_btn.pack_forget()
        self.send_btn.pack(side="right")
        self.send_btn.configure(state="normal")

    def clear_conversation(self):
        if self.generating:
            return
        self.conversation.clear()
        self._content_labels.clear()
        self._user_bubble_cards.clear()
        for widget in self.chat.winfo_children():
            if widget != getattr(self, "bottom_spacer", None):
                widget.destroy()
        self._check_empty_state()
        if self.active_doc_info:
            self.set_document_context_mode("Document")
            if not self.doc_card.winfo_ismapped():
                self.doc_card.pack(fill="x", padx=8, pady=(4, 4))
            if not self.doc_chip.winfo_ismapped():
                self.doc_chip.pack(fill="x", padx=8, pady=(4, 2), before=self.input)

    def set_selected_text_focus(self, text: str):
        self.input.delete("1.0", "end")
        self.input.insert("1.0", "Explain this selected text:\n" + text[:5000])
        self.input.focus_set()

    def clear_conversation_for_lock(self):
        """Immediately hides and clears sensitive in-memory UI state upon USB removal."""
        self.handle_stop()
        self.conversation.clear()
        self._content_labels.clear()
        self._user_bubble_cards.clear()
        self.last_user_query = ""
        self.clear_document_active()
        self.clear_attachment()
        self.input.delete("1.0", "end")
        for widget in self.chat.winfo_children():
            if widget != getattr(self, "bottom_spacer", None):
                widget.destroy()
        self.conv_title_label.configure(text="")
        self._show_home_state()
        self.send_btn.configure(state="disabled")
        self.plus_btn.configure(state="disabled")
        self.voice_btn.configure(state="disabled")

    def enable_after_unlock(self):
        """Re-enables user interaction after USB is re-verified and unlocked."""
        self.send_btn.configure(state="normal")
        self.plus_btn.configure(state="normal")
        self.voice_btn.configure(state="normal")
        self.conv_title_label.configure(text="New Chat")
        self._show_home_state()

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        return list(self.conversation)

    def apply_theme(self, theme_name=None):
        """Dynamically re-applies the active theme across all ChatPanel elements."""
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            self.top_frame.configure(fg_color=THEME["bg_panel"])
            self.conv_title_label.configure(text_color=THEME["text_primary"])
            self.top_doc_label.configure(text_color=THEME["accent_hover"])
            self.more_menu_btn.configure(text_color=THEME["text_secondary"], hover_color=THEME["bg_hover"])
            self.offline_pill.configure(fg_color=THEME["success_bg"], text_color=THEME["success"])
            self.chat.configure(
                fg_color=THEME["bg_secondary"],
                scrollbar_fg_color=THEME["bg_secondary"],
                scrollbar_button_color=THEME["bg_panel"],
                scrollbar_button_hover_color=THEME["bg_hover"]
            )
            self.composer_card.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"])
            self.doc_card.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"])
            self.doc_chip.configure(fg_color=THEME["bg_panel"], border_color=THEME["border"])
            self.doc_chip_label.configure(text_color=THEME["text_primary"])
            self.doc_chip_open_btn.configure(fg_color=THEME["accent_dim"], text_color=THEME["text_primary"])
            self.attach_banner.configure(fg_color=THEME["bg_panel"])
            self.attach_label.configure(text_color=THEME["text_primary"])
            self.voice_recording_bar.configure(fg_color=THEME["bg_panel"])
            self.input.configure(text_color=THEME["text_primary"])
            self.plus_btn.configure(fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], text_color=THEME["text_primary"])
            self.voice_btn.configure(hover_color=THEME["bg_hover"], text_color=THEME["text_secondary"])
            self.send_btn.configure(fg_color=THEME["accent"], hover_color=THEME["accent_hover"], text_color=THEME["accent_text"])
            self.jump_latest_btn.configure(
                fg_color=THEME["bg_panel"],
                hover_color=THEME["bg_hover"],
                text_color=THEME["accent"],
                border_color=THEME["border"]
            )

            # Home screen elements
            if hasattr(self, "home_glyph"):
                self.home_glyph.configure(text_color=THEME["accent"])
            if hasattr(self, "home_title"):
                self.home_title.configure(text_color=THEME["text_primary"])
            if hasattr(self, "home_subtitle"):
                self.home_subtitle.configure(text_color=THEME["text_secondary"])
            if hasattr(self, "home_desc"):
                self.home_desc.configure(text_color=THEME["text_muted"])
            for btn in getattr(self, "home_action_btns", []):
                try:
                    btn.configure(
                        fg_color=THEME["bg_surface"],
                        hover_color=THEME["bg_hover"],
                        text_color=THEME["text_primary"],
                        border_color=THEME["border"]
                    )
                except Exception:
                    pass
            for btn in getattr(self, "home_sugg_btns", []):
                try:
                    btn.configure(
                        hover_color=THEME["bg_hover"],
                        text_color=THEME["text_secondary"],
                        border_color=THEME["border"]
                    )
                except Exception:
                    pass

            # User bubbles
            for card in getattr(self, "_user_bubble_cards", []):
                try:
                    card.configure(fg_color=THEME["user_bubble"])
                except Exception:
                    pass

            # Content labels and markdown
            for item in self._content_labels:
                if hasattr(item, "update_theme"):
                    item.update_theme()
                elif hasattr(item, "configure"):
                    try:
                        item.configure(text_color=THEME["text_primary"])
                    except Exception:
                        pass
        except Exception:
            pass

    @staticmethod
    def _copy(text: str):
        try:
            pyperclip.copy(text)
        except Exception:
            pass

