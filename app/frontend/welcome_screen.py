from typing import Optional, Callable
import customtkinter as ctk

from frontend.branding import load_logo_image
from frontend.theme import THEME


class WelcomeScreen(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_add_document: Optional[Callable[[], None]] = None,
        on_ask_anything: Optional[Callable[[], None]] = None,
        on_open_projects: Optional[Callable[[], None]] = None,
        on_analyze_doc: Optional[Callable[[], None]] = None,
        on_start_coding: Optional[Callable[[], None]] = None,
        **kw
    ):
        super().__init__(master, **kw)
        self.on_add_document = on_add_document
        self.on_ask_anything = on_ask_anything
        self.on_open_projects = on_open_projects
        self.on_analyze_doc = on_analyze_doc
        self.on_start_coding = on_start_coding
        self.logo_image = load_logo_image((56, 56))
        self.configure(fg_color=THEME["bg_primary"], corner_radius=0)

        box = ctk.CTkFrame(self, fg_color="transparent")
        box.place(relx=0.5, rely=0.5, anchor="center")

        # Logo and Title
        ctk.CTkLabel(box, text="", image=self.logo_image).pack(pady=(0, 6))
        self.title_lbl = ctk.CTkLabel(
            box,
            text="Infinity AI",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=THEME["text_primary"]
        )
        self.title_lbl.pack(pady=(0, 2))
        self.sub_lbl = ctk.CTkLabel(
            box,
            text="Your private AI workspace.",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME["text_secondary"]
        )
        self.sub_lbl.pack(pady=(0, 4))
        self.desc_lbl = ctk.CTkLabel(
            box,
            text="Ask anything, work with your documents, or start a project.",
            font=ctk.CTkFont(size=12),
            text_color=THEME["text_muted"]
        )
        self.desc_lbl.pack(pady=(0, 20))

        # Primary Actions Container
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(pady=4)

        actions = [
            ("💬", "Ask anything", self._handle_ask),
            ("📄", "Upload document", self._handle_upload),
            ("📁", "Start a project", self._handle_project),
        ]

        self.action_btns = []
        for icon, title, callback in actions:
            btn = ctk.CTkButton(
                row,
                text=f"{icon}  {title}",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=38,
                width=160,
                fg_color=THEME["bg_surface"],
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_primary"],
                border_color=THEME["border"],
                border_width=1,
                corner_radius=10,
                command=callback
            )
            btn.pack(side="left", padx=8)
            self.action_btns.append(btn)

    def apply_theme(self, theme_name=None):
        try:
            self.configure(fg_color=THEME["bg_primary"])
            if hasattr(self, "title_lbl"):
                self.title_lbl.configure(text_color=THEME["text_primary"])
            if hasattr(self, "sub_lbl"):
                self.sub_lbl.configure(text_color=THEME["text_secondary"])
            if hasattr(self, "desc_lbl"):
                self.desc_lbl.configure(text_color=THEME["text_muted"])
            for b in getattr(self, "action_btns", []):
                try:
                    b.configure(
                        fg_color=THEME["bg_surface"],
                        hover_color=THEME["bg_hover"],
                        text_color=THEME["text_primary"],
                        border_color=THEME["border"]
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def _handle_ask(self):
        if self.on_ask_anything:
            self.on_ask_anything()
        elif self.on_add_document:
            self.on_add_document()

    def _handle_upload(self):
        if self.on_add_document:
            self.on_add_document()

    def _handle_project(self):
        if self.on_open_projects:
            self.on_open_projects()
        elif self.on_ask_anything:
            self.on_ask_anything()

    def _handle_analyze(self):
        if self.on_analyze_doc:
            self.on_analyze_doc()
        elif self.on_add_document:
            self.on_add_document()

    def _handle_code(self):
        if self.on_start_coding:
            self.on_start_coding()
        elif self.on_ask_anything:
            self.on_ask_anything()
