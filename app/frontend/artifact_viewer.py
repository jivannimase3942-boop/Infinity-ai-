"""
Infinity AI - Claude-Style Artifact Viewer & Editor
Allows previewing, editing, saving, copying, and exporting AI-generated documents,
code files, reports, and study materials separately from the conversational stream.
"""

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional, Callable, Dict, Any

import customtkinter as ctk

from frontend.theme import TEXTBOX_COLORS, THEME
import pyperclip

from backend.artifacts import export_artifact
from backend.db import save_artifact, get_artifact


class ArtifactViewer(ctk.CTkFrame):
    def __init__(self, master, on_close=None, **kw):
        super().__init__(master, fg_color=THEME["bg_secondary"], corner_radius=0, **kw)
        self.on_close = on_close
        self.current_artifact_id: Optional[str] = None
        self.is_editing = False
        self._build()

    def _build(self):
        # 1. Header Toolbar
        self.head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        self.head.pack(fill="x")

        self.title_lbl = ctk.CTkLabel(
            self.head,
            text="📄 Artifact: None",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME["accent"]
        )
        self.title_lbl.pack(side="left", padx=12, pady=6)

        # Right Actions: Close, Export, Copy, Edit/Preview
        if self.on_close:
            ctk.CTkButton(
                self.head,
                text="✕",
                width=28,
                height=26,
                fg_color="transparent",
                hover_color=THEME["error_hover"],
                font=ctk.CTkFont(size=12, weight="bold"),
                command=self.on_close
            ).pack(side="right", padx=(2, 8))

        ctk.CTkButton(
            self.head,
            text="💾 Export",
            width=70,
            height=26,
            fg_color=THEME["accent_dim"],
            hover_color=THEME["accent"],
            font=ctk.CTkFont(size=11),
            command=self._handle_export
        ).pack(side="right", padx=3)

        ctk.CTkButton(
            self.head,
            text="📋 Copy",
            width=60,
            height=26,
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            font=ctk.CTkFont(size=11),
            command=self._handle_copy
        ).pack(side="right", padx=3)

        self.edit_btn = ctk.CTkButton(
            self.head,
            text="✏️ Edit",
            width=65,
            height=26,
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            font=ctk.CTkFont(size=11),
            command=self._toggle_edit_mode
        )
        self.edit_btn.pack(side="right", padx=3)

        # 2. Main Content Editor / Viewer
        self.editor = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
            **TEXTBOX_COLORS
        )
        self.editor.pack(fill="both", expand=True, padx=8, pady=8)

        # 3. Footer status
        self.footer = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=24, corner_radius=0)
        self.footer.pack(fill="x")
        self.status_lbl = ctk.CTkLabel(
            self.footer,
            text="Viewing artifact in read-only mode.",
            font=ctk.CTkFont(size=10),
            text_color=THEME["text_secondary"]
        )
        self.status_lbl.pack(side="left", padx=10, pady=2)

    def load_artifact(self, artifact_id: str):
        """Loads and displays an artifact by ID from SQLite."""
        self.current_artifact_id = artifact_id
        art = get_artifact(artifact_id)
        if not art:
            self.title_lbl.configure(text="Artifact not found.")
            return

        self.title_lbl.configure(text=f"📄 {art['title']} (v{art.get('version', 1)})")
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", art["content"])
        self.editor.configure(state="disabled")
        self.is_editing = False
        self.edit_btn.configure(text="✏️ Edit", fg_color=THEME["bg_panel"])
        self.status_lbl.configure(text=f"Loaded {art.get('artifact_type', 'document')} • {len(art['content'].splitlines())} lines • Read-only")

    def _toggle_edit_mode(self):
        if not self.current_artifact_id:
            return

        if not self.is_editing:
            # Switch to edit mode
            self.is_editing = True
            self.editor.configure(state="normal")
            self.edit_btn.configure(text="💾 Save", fg_color=THEME["success"])
            self.status_lbl.configure(text="Editing mode active. Click Save to record changes.")
        else:
            # Save edits to SQLite
            new_content = self.editor.get("1.0", "end").strip()
            art = get_artifact(self.current_artifact_id)
            if art:
                save_artifact(
                    title=art["title"],
                    content=new_content,
                    artifact_type=art.get("artifact_type", "document"),
                    language=art.get("language", "markdown"),
                    conversation_id=art.get("conversation_id"),
                    project_id=art.get("project_id", "default"),
                    artifact_id=self.current_artifact_id
                )
            self.is_editing = False
            self.editor.configure(state="disabled")
            self.edit_btn.configure(text="✏️ Edit", fg_color=THEME["bg_panel"])
            self.status_lbl.configure(text="Changes saved successfully to SQLite.")

    def _handle_copy(self):
        content = self.editor.get("1.0", "end").strip()
        if content:
            pyperclip.copy(content)
            self.status_lbl.configure(text="Copied artifact to clipboard!")

    def _handle_export(self):
        if not self.current_artifact_id:
            return
        art = get_artifact(self.current_artifact_id)
        if not art:
            return

        fname = art["title"]
        if not Path(fname).suffix:
            fname += ".py" if art.get("language") == "python" else ".md"

        target_path = filedialog.asksaveasfilename(
            title="Export Artifact to Local Disk",
            initialfile=fname,
            defaultextension=Path(fname).suffix,
            filetypes=[("All Files", "*.*"), ("Markdown", "*.md"), ("Text File", "*.txt"), ("Python", "*.py")]
        )
        if target_path:
            res = export_artifact(self.current_artifact_id, target_path=target_path)
            if res.get("status") == "success":
                messagebox.showinfo("Export Successful", f"Artifact exported to:\n{target_path}")
                self.status_lbl.configure(text=f"Exported to {Path(target_path).name}")
            else:
                messagebox.showerror("Export Failed", res.get("message", "Unknown error"))

    def apply_theme(self, theme_name=None):
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "head"):
                self.head.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "title_lbl"):
                self.title_lbl.configure(text_color=THEME["accent"])
            if hasattr(self, "textbox"):
                self.textbox.configure(
                    fg_color=THEME["bg_surface"],
                    text_color=THEME["text_primary"],
                    border_color=THEME["border"]
                )
            if hasattr(self, "markdown_view") and hasattr(self.markdown_view, "update_theme"):
                self.markdown_view.update_theme()
        except Exception:
            pass
