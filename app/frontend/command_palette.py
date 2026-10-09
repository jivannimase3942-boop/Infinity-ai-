"""
Infinity AI - Modern Command Palette & Workspace Search
Inspired by VS Code, Raycast, and modern desktop AI workspaces.
Includes:
- CommandPalette: Fast navigation commands (New Chat, Search, Open Documents, Create Project, Settings, Lock)
- WorkspaceSearchModal: Unified search across Chats, Projects, and Documents grouped cleanly
"""

from typing import Callable, List, Dict, Any, Optional
import customtkinter as ctk

from frontend.theme import ENTRY_TEXT_COLORS, SCROLLABLE_COLORS, THEME
from backend.db import search_workspace


class CommandPalette(ctk.CTkToplevel):
    def __init__(self, master, actions: List[Dict[str, Any]]):
        super().__init__(master)
        self.actions = actions
        self.filtered_actions = list(actions)
        self.selected_index = 0

        self.title("Infinity AI — Command Palette")
        self.geometry("580x420")
        self.resizable(False, False)
        self.configure(fg_color=THEME["bg_secondary"])

        self.transient(master)
        self.grab_set()

        self._build()
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Down>", self._on_arrow_down)
        self.bind("<Up>", self._on_arrow_up)
        self.bind("<Return>", self._on_return)

    def _build(self):
        # 1. Search Box
        box = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], corner_radius=8)
        box.pack(fill="x", padx=14, pady=(14, 8))

        ctk.CTkLabel(box, text="🔍", font=ctk.CTkFont(size=14)).pack(side="left", padx=(10, 4))
        self.search_entry = ctk.CTkEntry(
            box,
            placeholder_text="Type a command or search action (e.g. 'New Chat', 'Projects')…",
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            border_width=0,
            **ENTRY_TEXT_COLORS
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=4, pady=8)
        self.search_entry.bind("<KeyRelease>", self._on_filter)
        self.search_entry.focus_set()

        # 2. Scrollable Action List
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=THEME["bg_secondary"], **SCROLLABLE_COLORS)
        self.list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        # 3. Footer with shortcut hints
        footer = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=28, corner_radius=0)
        footer.pack(fill="x")
        ctk.CTkLabel(
            footer,
            text="↑↓ to navigate  •  ↵ to execute  •  Esc to close",
            font=ctk.CTkFont(size=11),
            text_color=THEME["text_secondary"]
        ).pack(side="left", padx=12, pady=4)

        self._render_items()

    def _on_filter(self, event):
        q = self.search_entry.get().strip().lower()
        if not q:
            self.filtered_actions = list(self.actions)
        else:
            self.filtered_actions = [
                a for a in self.actions
                if q in a["title"].lower() or q in a.get("category", "").lower() or q in a.get("shortcut", "").lower()
            ]
        self.selected_index = 0
        self._render_items()

    def _render_items(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        if not self.filtered_actions:
            ctk.CTkLabel(self.list_frame, text="No matching commands found.", text_color=THEME["text_secondary"]).pack(pady=20)
            return

        for idx, item in enumerate(self.filtered_actions):
            is_sel = idx == self.selected_index
            row = ctk.CTkFrame(self.list_frame, fg_color=THEME["accent_dim"] if is_sel else THEME["bg_surface"], corner_radius=6)
            row.pack(fill="x", pady=2)

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=8, pady=4)

            icon = item.get("icon", "⚡")
            ctk.CTkLabel(
                left,
                text=f"{icon}  {item['title']}",
                font=ctk.CTkFont(size=12, weight="bold" if is_sel else "normal"),
                text_color=THEME["text_primary"]
            ).pack(side="left")

            if "category" in item:
                ctk.CTkLabel(
                    left,
                    text=f"[{item['category']}]",
                    font=ctk.CTkFont(size=10),
                    text_color=THEME["text_secondary"]
                ).pack(side="left", padx=(8, 0))

            if "shortcut" in item:
                ctk.CTkLabel(
                    row,
                    text=item["shortcut"],
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=THEME["accent"],
                    fg_color=THEME["accent_dim"],
                    corner_radius=4,
                    padx=6,
                    pady=2
                ).pack(side="right", padx=8)

            row.bind("<Button-1>", lambda e, act=item: self._execute_and_close(act))

    def _on_arrow_down(self, event):
        if self.selected_index < len(self.filtered_actions) - 1:
            self.selected_index += 1
            self._render_items()

    def _on_arrow_up(self, event):
        if self.selected_index > 0:
            self.selected_index -= 1
            self._render_items()

    def _on_return(self, event):
        if 0 <= self.selected_index < len(self.filtered_actions):
            act = self.filtered_actions[self.selected_index]
            self._execute_and_close(act)

    def _execute_and_close(self, action: Dict[str, Any]):
        callback = action.get("callback")
        self.destroy()
        if callback:
            callback()


class WorkspaceSearchModal(ctk.CTkToplevel):
    """Unified search across Chats, Projects, and Documents grouped cleanly."""
    def __init__(
        self,
        master,
        on_open_chat: Optional[Callable[[str], None]] = None,
        on_open_project: Optional[Callable[[str], None]] = None,
        on_open_document: Optional[Callable[[str], None]] = None
    ):
        super().__init__(master)
        self.on_open_chat = on_open_chat
        self.on_open_project = on_open_project
        self.on_open_document = on_open_document

        self.title("Search Workspace — Infinity AI")
        self.geometry("620x480")
        self.configure(fg_color=THEME["bg_secondary"])
        self.transient(master)
        self.grab_set()

        self._build()
        self.bind("<Escape>", lambda e: self.destroy())

    def _build(self):
        head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        head.pack(fill="x")
        ctk.CTkLabel(head, text="🔍 Search Workspace", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=14, pady=8)

        # Search Bar
        search_box = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], corner_radius=8)
        search_box.pack(fill="x", padx=14, pady=(10, 8))

        ctk.CTkLabel(search_box, text="🔍", font=ctk.CTkFont(size=13)).pack(side="left", padx=(10, 4))
        self.search_entry = ctk.CTkEntry(
            search_box,
            placeholder_text="Search all chats, documents, and projects…",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            border_width=0,
            **ENTRY_TEXT_COLORS
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=4, pady=8)
        self.search_entry.bind("<KeyRelease>", lambda e: self._perform_search())
        self.search_entry.focus_set()

        # Results Frame
        self.results_frame = ctk.CTkScrollableFrame(self, fg_color=THEME["bg_secondary"], **SCROLLABLE_COLORS)
        self.results_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        self._perform_search()

    def _perform_search(self):
        for w in self.results_frame.winfo_children():
            w.destroy()

        q = self.search_entry.get().strip()
        results = search_workspace(q)

        has_any = any(len(v) > 0 for v in results.values())
        if not has_any:
            ctk.CTkLabel(
                self.results_frame,
                text="Type a query to search your private workspace." if not q else f"No results found for '{q}'.",
                text_color=THEME["text_muted"]
            ).pack(pady=30)
            return

        categories = [
            ("CHATS", results.get("chats", []), "💬", self._select_chat),
            ("PROJECTS", results.get("projects", []), "📁", self._select_project),
            ("DOCUMENTS", results.get("documents", []), "📄", self._select_document),
        ]

        for cat_name, items, icon, click_handler in categories:
            if not items:
                continue

            ctk.CTkLabel(
                self.results_frame,
                text=cat_name,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=THEME["text_muted"],
                anchor="w"
            ).pack(fill="x", padx=6, pady=(8, 2))

            for item in items:
                card = ctk.CTkFrame(self.results_frame, fg_color=THEME["bg_surface"], corner_radius=6)
                card.pack(fill="x", pady=2)

                btn = ctk.CTkButton(
                    card,
                    text=f"{icon}  {item['title']}",
                    anchor="w",
                    fg_color="transparent",
                    hover_color=THEME["bg_hover"],
                    font=ctk.CTkFont(size=12, weight="bold"),
                    command=lambda it=item, h=click_handler: h(it)
                )
                btn.pack(side="left", fill="x", expand=True, padx=6, pady=4)

                if item.get("snippet"):
                    ctk.CTkLabel(
                        card,
                        text=item["snippet"][:35],
                        font=ctk.CTkFont(size=10),
                        text_color=THEME["text_secondary"]
                    ).pack(side="right", padx=8)

    def _select_chat(self, item):
        self.destroy()
        if self.on_open_chat:
            self.on_open_chat(item["id"])

    def _select_project(self, item):
        self.destroy()
        if self.on_open_project:
            self.on_open_project(item["id"])

    def _select_document(self, item):
        self.destroy()
        if self.on_open_document:
            self.on_open_document(item["title"])
