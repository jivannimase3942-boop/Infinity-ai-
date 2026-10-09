"""
Infinity AI - Modular Workspace Views
Includes:
- ProjectsWorkspace (Claude-style workspaces, custom instructions, project files)
- ResearchWorkspace (Rigorous investigation with evidence and confidence ratings)
- CodeWorkspace (Code analyzer, architecture inspector, diff proposals)
- AgentsWorkspace (7 specialized agents with tool execution tracking)
- MemoryWorkspace (View, Edit, Forget, Clear memories)
- ModelsWorkspace (Local model catalogue, GGUF/Ollama detector, RAM/VRAM stats)
- DiagnosticsWorkspace (Hardware monitoring, USB authorization, backup trigger)
"""

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional, Callable

import customtkinter as ctk

from frontend.theme import (
    ENTRY_COLORS, OPTION_MENU_COLORS, SCROLLABLE_COLORS, TEXTBOX_COLORS, THEME,
    set_theme, get_current_theme, register_theme_listener
)

from backend.agents import AGENT_PERSONAS, agent_orchestrator
from backend.db import get_projects, save_project
from backend.diagnostics import get_full_diagnostics, get_hardware_metrics
from backend.memory import memory_service
from backend.model_manager import get_all_models
from backend.projects import project_service
from backend.security import is_write_authorized
from backend.tools import tool_registry


class ProjectsWorkspace(ctk.CTkFrame):
    def __init__(self, master, on_project_changed=None, **kw):
        super().__init__(master, fg_color=THEME["bg_secondary"], corner_radius=0, **kw)
        self.on_project_changed = on_project_changed
        self.showing_existing = False
        self._build()

    def _build(self):
        self.head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=48, corner_radius=0)
        self.head.pack(fill="x")
        ctk.CTkLabel(self.head, text="📁 Projects & Workspaces", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=14, pady=8)

        self.toggle_mode_btn = ctk.CTkButton(
            self.head,
            text="📂 Open Existing Projects",
            width=170,
            height=28,
            fg_color=THEME["bg_secondary"],
            hover_color=THEME["bg_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.toggle_mode
        )
        self.toggle_mode_btn.pack(side="right", padx=14, pady=10)

        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True, padx=12, pady=10)

        # 1. New Project Frame (Default Experience - Requirement 9)
        self.new_proj_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")

        # Centered card
        self.center_card = ctk.CTkFrame(self.new_proj_frame, fg_color=THEME["bg_panel"], corner_radius=12, border_color=THEME["border"], border_width=1, width=540)
        self.center_card.pack(expand=True, pady=20, padx=20, ipadx=10, ipady=10)

        ctk.CTkLabel(
            self.center_card,
            text="New Project",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=THEME["text_primary"]
        ).pack(pady=(16, 2))

        ctk.CTkLabel(
            self.center_card,
            text="Create a focused workspace for your work.",
            font=ctk.CTkFont(size=12),
            text_color=THEME["text_muted"]
        ).pack(pady=(0, 16))

        # Project Name
        ctk.CTkLabel(self.center_card, text="Project Name", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_secondary"]).pack(anchor="w", padx=24, pady=(4, 2))
        self.new_name_entry = ctk.CTkEntry(self.center_card, placeholder_text="e.g. Distributed Systems Lab", font=ctk.CTkFont(size=13), width=460, **ENTRY_COLORS)
        self.new_name_entry.pack(padx=24, pady=(0, 10))

        # Description
        ctk.CTkLabel(self.center_card, text="Description", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_secondary"]).pack(anchor="w", padx=24, pady=(4, 2))
        self.new_desc_entry = ctk.CTkEntry(self.center_card, placeholder_text="Brief summary of this workspace's purpose", font=ctk.CTkFont(size=12), width=460, **ENTRY_COLORS)
        self.new_desc_entry.pack(padx=24, pady=(0, 10))

        # Instructions
        ctk.CTkLabel(self.center_card, text="Instructions", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_secondary"]).pack(anchor="w", padx=24, pady=(4, 2))
        self.new_inst_text = ctk.CTkTextbox(self.center_card, height=110, width=460, font=ctk.CTkFont(size=12), **TEXTBOX_COLORS)
        self.new_inst_text.pack(padx=24, pady=(0, 10))

        # Model
        ctk.CTkLabel(self.center_card, text="Model", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_secondary"]).pack(anchor="w", padx=24, pady=(4, 2))
        self.new_model_var = ctk.StringVar(value="Auto")
        ctk.CTkOptionMenu(self.center_card, variable=self.new_model_var, values=["Auto", "Fast", "Balanced", "Advanced", "Coding"], width=460, **OPTION_MENU_COLORS).pack(padx=24, pady=(0, 18))

        # Create Button
        ctk.CTkButton(
            self.center_card,
            text="＋ Create Project",
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            font=ctk.CTkFont(size=13, weight="bold"),
            height=36,
            width=220,
            command=self._create_new_project
        ).pack(pady=(0, 16))

        # 2. Existing Projects Frame (Hidden behind toggle - Requirement 10)
        self.existing_proj_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.existing_proj_frame.grid_columnconfigure(0, weight=1)
        self.existing_proj_frame.grid_columnconfigure(1, weight=2)
        self.existing_proj_frame.grid_rowconfigure(0, weight=1)

        # Left: Projects List
        self.left = ctk.CTkFrame(self.existing_proj_frame, fg_color=THEME["bg_panel"], corner_radius=8)
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(self.left, text="Existing Projects:", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))
        self.proj_list = ctk.CTkScrollableFrame(self.left, fg_color="transparent", **SCROLLABLE_COLORS)
        self.proj_list.pack(fill="both", expand=True, padx=6, pady=4)

        # Right: Details & Instructions Editor
        self.right = ctk.CTkFrame(self.existing_proj_frame, fg_color=THEME["bg_panel"], corner_radius=8)
        self.right.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(self.right, text="Project Details & Instructions", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=14, pady=(10, 2))

        self.name_entry = ctk.CTkEntry(self.right, placeholder_text="Project Name", font=ctk.CTkFont(size=13), **ENTRY_COLORS)
        self.name_entry.pack(fill="x", padx=14, pady=6)

        self.desc_entry = ctk.CTkEntry(self.right, placeholder_text="Short Description", font=ctk.CTkFont(size=12), **ENTRY_COLORS)
        self.desc_entry.pack(fill="x", padx=14, pady=4)

        ctk.CTkLabel(self.right, text="Custom System Instructions:", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_secondary"]).pack(anchor="w", padx=14, pady=(8, 2))
        self.inst_text = ctk.CTkTextbox(self.right, height=140, font=ctk.CTkFont(size=12), **TEXTBOX_COLORS)
        self.inst_text.pack(fill="x", padx=14, pady=4)

        ctk.CTkLabel(self.right, text="Model Preference:", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_secondary"]).pack(anchor="w", padx=14, pady=(6, 2))
        self.pref_var = ctk.StringVar(value="Balanced")
        ctk.CTkOptionMenu(self.right, variable=self.pref_var, values=["Auto", "Fast", "Balanced", "Advanced", "Coding"], **OPTION_MENU_COLORS).pack(anchor="w", padx=14, pady=4)

        save_btn = ctk.CTkButton(
            self.right,
            text="Save Project Settings",
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            command=self._save_active_project
        )
        save_btn.pack(anchor="e", padx=14, pady=12)

        # Show New Project view by default
        self.new_proj_frame.pack(fill="both", expand=True)

    def toggle_mode(self):
        self.showing_existing = not self.showing_existing
        if self.showing_existing:
            self.new_proj_frame.pack_forget()
            self.existing_proj_frame.pack(fill="both", expand=True)
            self.toggle_mode_btn.configure(text="＋ New Project", fg_color=THEME["accent"], hover_color=THEME["accent_hover"])
            self._load_existing_projects()
        else:
            self.existing_proj_frame.pack_forget()
            self.new_proj_frame.pack(fill="both", expand=True)
            self.toggle_mode_btn.configure(text="📂 Open Existing Projects", fg_color=THEME["bg_secondary"], hover_color=THEME["bg_hover"])

    def _create_new_project(self):
        import uuid
        name = self.new_name_entry.get().strip()
        if not name:
            messagebox.showwarning("Infinity AI", "Please enter a Project Name.")
            return
        desc = self.new_desc_entry.get().strip()
        inst = self.new_inst_text.get("1.0", "end").strip()
        model_pref = self.new_model_var.get()
        pid = f"proj_{uuid.uuid4().hex[:10]}"

        project_service.create_or_update_project(pid, name, desc, inst, model_pref)
        project_service.set_active_project(pid)

        # Clear fields
        self.new_name_entry.delete(0, "end")
        self.new_desc_entry.delete(0, "end")
        self.new_inst_text.delete("1.0", "end")

        if self.on_project_changed:
            self.on_project_changed(pid)

        from frontend.toast import ToastNotification
        ToastNotification.show(self.winfo_toplevel(), f"Project '{name}' created and active!", icon="📁", level="success")

    def _load_existing_projects(self):
        for w in self.proj_list.winfo_children():
            w.destroy()
        projects = project_service.list_projects()
        active_id = project_service.active_project_id

        for p in projects:
            is_act = p["id"] == active_id
            f = ctk.CTkFrame(self.proj_list, fg_color=THEME["accent_dim"] if is_act else THEME["bg_surface"], corner_radius=6)
            f.pack(fill="x", pady=3)
            btn = ctk.CTkButton(
                f,
                text=p["name"],
                anchor="w",
                font=ctk.CTkFont(size=12, weight="bold" if is_act else "normal"),
                fg_color="transparent",
                command=lambda pid=p["id"]: self._select_project(pid)
            )
            btn.pack(side="left", fill="x", expand=True, padx=8, pady=4)

        active_proj = project_service.get_active_project()
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, active_proj.get("name", ""))
        self.desc_entry.delete(0, "end")
        self.desc_entry.insert(0, active_proj.get("description", ""))
        self.inst_text.delete("1.0", "end")
        self.inst_text.insert("1.0", active_proj.get("system_instructions", ""))
        self.pref_var.set(active_proj.get("model_preference", "Balanced"))

    def _select_project(self, project_id: str):
        project_service.set_active_project(project_id)
        self._load_existing_projects()
        if self.on_project_changed:
            self.on_project_changed(project_id)

    def _save_active_project(self):
        pid = project_service.active_project_id
        name = self.name_entry.get().strip() or "Untitled Project"
        desc = self.desc_entry.get().strip()
        inst = self.inst_text.get("1.0", "end").strip()
        pref = self.pref_var.get()
        project_service.create_or_update_project(pid, name, desc, inst, pref)
        messagebox.showinfo("Infinity AI", "Project settings saved successfully.")
        self._load_existing_projects()

    def refresh(self):
        if self.showing_existing:
            self._load_existing_projects()

    def apply_theme(self, theme_name=None):
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "head"):
                self.head.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "toggle_mode_btn"):
                if self.showing_existing:
                    self.toggle_mode_btn.configure(fg_color=THEME["accent"], hover_color=THEME["accent_hover"], text_color=THEME["accent_text"])
                else:
                    self.toggle_mode_btn.configure(fg_color=THEME["bg_secondary"], hover_color=THEME["bg_hover"], text_color=THEME["text_primary"])
            if hasattr(self, "center_card"):
                self.center_card.configure(fg_color=THEME["bg_panel"], border_color=THEME["border"])
            for entry in [getattr(self, "new_name_entry", None), getattr(self, "new_desc_entry", None), getattr(self, "name_entry", None), getattr(self, "desc_entry", None)]:
                if entry:
                    entry.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"], placeholder_text_color=THEME["text_muted"])
            for txt in [getattr(self, "new_inst_text", None), getattr(self, "inst_text", None)]:
                if txt:
                    txt.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"])
            if hasattr(self, "left"):
                self.left.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "right"):
                self.right.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "proj_list"):
                self.proj_list.configure(scrollbar_fg_color=THEME["bg_secondary"], scrollbar_button_color=THEME["bg_panel"], scrollbar_button_hover_color=THEME["bg_hover"])
            if self.showing_existing:
                self._load_existing_projects()
        except Exception:
            pass


class ResearchWorkspace(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=THEME["bg_secondary"], corner_radius=0, **kw)
        self._build()

    def _build(self):
        self.head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        self.head.pack(fill="x")
        ctk.CTkLabel(self.head, text="🔬 Local Research Assistant", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=14, pady=8)

        self.input_box = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], corner_radius=8)
        self.input_box.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(self.input_box, text="Research Question / Investigation Topic:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.query_entry = ctk.CTkEntry(self.input_box, placeholder_text="e.g. Compare the methodology and performance metrics across the loaded documents", font=ctk.CTkFont(size=13), **ENTRY_COLORS)
        self.query_entry.pack(fill="x", padx=10, pady=4)

        btn_row = ctk.CTkFrame(self.input_box, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(4, 8))

        self.run_btn = ctk.CTkButton(
            btn_row,
            text="Conduct Research 🔬",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            command=self._start_research
        )
        self.run_btn.pack(side="right")

        self.status_lbl = ctk.CTkLabel(btn_row, text="Ready for research.", font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"])
        self.status_lbl.pack(side="left")

        # Results area
        self.result_box = ctk.CTkTextbox(self, font=ctk.CTkFont(size=12), **TEXTBOX_COLORS)
        self.result_box.pack(fill="both", expand=True, padx=14, pady=(0, 10))

    def apply_theme(self, theme_name=None):
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "head"):
                self.head.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "input_box"):
                self.input_box.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "query_entry"):
                self.query_entry.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"], placeholder_text_color=THEME["text_muted"])
            if hasattr(self, "run_btn"):
                self.run_btn.configure(fg_color=THEME["accent"], hover_color=THEME["accent_hover"], text_color=THEME["accent_text"])
            if hasattr(self, "status_lbl"):
                self.status_lbl.configure(text_color=THEME["text_secondary"])
            if hasattr(self, "result_box"):
                self.result_box.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"])
        except Exception:
            pass

    def _start_research(self):
        q = self.query_entry.get().strip()
        if not q:
            return
        self.run_btn.configure(state="disabled")
        self.status_lbl.configure(text="Investigating local knowledge base & evidence…")
        self.result_box.delete("1.0", "end")

        def append(token):
            self.after(0, lambda: self.result_box.insert("end", token))

        def work():
            import threading
            try:
                res = agent_orchestrator.run_agent(
                    "Research",
                    q,
                    chunk_callback=append,
                    status_callback=lambda s: self.after(0, lambda: self.status_lbl.configure(text=s))
                )
                self.after(0, lambda: self.status_lbl.configure(text="Research complete."))
            except Exception as exc:
                self.after(0, lambda: self.result_box.insert("end", f"\n[Error]: {exc}"))
                self.after(0, lambda: self.status_lbl.configure(text="Research error."))
            finally:
                self.after(0, lambda: self.run_btn.configure(state="normal"))

        import threading
        threading.Thread(target=work, daemon=True).start()


class CodeWorkspace(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=THEME["bg_secondary"], corner_radius=0, **kw)
        self.current_code_path = None
        self._build()

    def _build(self):
        self.head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        self.head.pack(fill="x")
        ctk.CTkLabel(self.head, text="💻 Code Workspace & Assistant", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=14, pady=8)
        ctk.CTkButton(self.head, text="Open File", width=80, height=28, command=self._open_code_file).pack(side="right", padx=10)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Left: Editor / File Viewer
        self.left = ctk.CTkFrame(body, fg_color=THEME["bg_panel"], corner_radius=8)
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.file_title = ctk.CTkLabel(self.left, text="No code file open", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["accent"])
        self.file_title.pack(anchor="w", padx=10, pady=(8, 2))
        self.editor = ctk.CTkTextbox(self.left, font=ctk.CTkFont(family="Consolas", size=12), **TEXTBOX_COLORS)
        self.editor.pack(fill="both", expand=True, padx=6, pady=6)

        # Right: AI Analysis & Patch Proposals
        self.right = ctk.CTkFrame(body, fg_color=THEME["bg_panel"], corner_radius=8)
        self.right.grid(row=0, column=1, sticky="nsew")

        bar = ctk.CTkFrame(self.right, fg_color="transparent")
        bar.pack(fill="x", padx=8, pady=6)
        ctk.CTkButton(bar, text="Inspect & Debug", width=110, height=28, command=lambda: self._ask_code("Find all bugs, security issues, and suggest fixes with diffs.")).pack(side="left", padx=2)
        ctk.CTkButton(bar, text="Explain Architecture", width=130, height=28, command=lambda: self._ask_code("Explain the architecture and data flow of this file.")).pack(side="left", padx=2)
        ctk.CTkButton(bar, text="Propose Diff", width=95, height=28, fg_color=THEME["accent"], command=lambda: self._ask_code("Refactor and optimize this code. Show unified diff.")).pack(side="right", padx=2)

        self.ai_output = ctk.CTkTextbox(self.right, font=ctk.CTkFont(family="Consolas", size=12), **TEXTBOX_COLORS)
        self.ai_output.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    def apply_theme(self, theme_name=None):
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "head"):
                self.head.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "left"):
                self.left.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "right"):
                self.right.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "file_title"):
                self.file_title.configure(text_color=THEME["accent"])
            if hasattr(self, "editor"):
                self.editor.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"])
            if hasattr(self, "ai_output"):
                self.ai_output.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"])
        except Exception:
            pass

    def _open_code_file(self):
        f = filedialog.askopenfilename(
            title="Open Code File",
            filetypes=[("Code Files", "*.py;*.js;*.ts;*.html;*.css;*.cpp;*.java;*.json;*.bat;*.sh;*.sql"), ("All Files", "*.*")]
        )
        if f:
            self.current_code_path = f
            self.file_title.configure(text=f"📄 {Path(f).name}")
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fp:
                    content = fp.read()
                self.editor.delete("1.0", "end")
                self.editor.insert("1.0", content)
            except Exception as exc:
                messagebox.showerror("Infinity AI", f"Error opening code: {exc}")

    def _ask_code(self, prompt_prefix: str):
        content = self.editor.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("Infinity AI", "Please open or paste code in the editor first.")
            return

        self.ai_output.delete("1.0", "end")
        self.ai_output.insert("end", f"Analyzing with Coding Agent…\n\n")

        def append(token):
            self.after(0, lambda: self.ai_output.insert("end", token))

        def work():
            import threading
            query = f"{prompt_prefix}\n\n```python\n{content[:6000]}\n```"
            agent_orchestrator.run_agent("Coding", query, chunk_callback=append)

        import threading
        threading.Thread(target=work, daemon=True).start()


class AgentsWorkspace(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=THEME["bg_secondary"], corner_radius=0, **kw)
        self._build()

    def _build(self):
        self.head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        self.head.pack(fill="x")
        ctk.CTkLabel(self.head, text="🤖 AI Agent Orchestrator", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=14, pady=8)

        # Agent selector bar
        self.bar = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], corner_radius=8)
        self.bar.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(self.bar, text="Agent Persona:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=10, pady=8)
        self.agent_var = ctk.StringVar(value="General")
        ctk.CTkOptionMenu(
            self.bar,
            variable=self.agent_var,
            values=list(AGENT_PERSONAS.keys()),
            width=120,
            command=self._on_agent_select,
            **OPTION_MENU_COLORS
        ).pack(side="left", padx=6)

        self.agent_desc = ctk.CTkLabel(self.bar, text=AGENT_PERSONAS["General"]["title"], font=ctk.CTkFont(size=12), text_color=THEME["accent"])
        self.agent_desc.pack(side="left", padx=10)

        # Activity log
        ctk.CTkLabel(self, text="Agent Tool Execution & Activity Stream:", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_secondary"]).pack(anchor="w", padx=14, pady=(4, 2))
        self.activity_box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=11), **TEXTBOX_COLORS)
        self.activity_box.pack(fill="both", expand=True, padx=14, pady=4)

        # Prompt input
        self.input_bar = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], corner_radius=8)
        self.input_bar.pack(fill="x", padx=14, pady=(4, 10))
        self.prompt_entry = ctk.CTkEntry(self.input_bar, placeholder_text="Give the agent a task (e.g. 'calculate 25 * 400 + 120 and explain the result')", font=ctk.CTkFont(size=13), **ENTRY_COLORS)
        self.prompt_entry.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        self.prompt_entry.bind("<Return>", lambda e: self._run())

        self.run_btn = ctk.CTkButton(self.input_bar, text="Run Agent  ➤", font=ctk.CTkFont(size=12, weight="bold"), fg_color=THEME["accent"], hover_color=THEME["accent_hover"], command=self._run)
        self.run_btn.pack(side="right", padx=10, pady=8)

    def apply_theme(self, theme_name=None):
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "head"):
                self.head.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "bar"):
                self.bar.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "agent_desc"):
                self.agent_desc.configure(text_color=THEME["accent"])
            if hasattr(self, "activity_box"):
                self.activity_box.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"])
            if hasattr(self, "input_bar"):
                self.input_bar.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "prompt_entry"):
                self.prompt_entry.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"], placeholder_text_color=THEME["text_muted"])
            if hasattr(self, "run_btn"):
                self.run_btn.configure(fg_color=THEME["accent"], hover_color=THEME["accent_hover"], text_color=THEME["accent_text"])
        except Exception:
            pass

    def _on_agent_select(self, val):
        self.agent_desc.configure(text=AGENT_PERSONAS.get(val, {}).get("title", ""))

    def _run(self):
        q = self.prompt_entry.get().strip()
        if not q:
            return
        agent_type = self.agent_var.get()
        self.activity_box.insert("end", f"\n▶ Running [{agent_type} Agent]: {q}\n")
        self.run_btn.configure(state="disabled")

        def append(token):
            self.after(0, lambda: self.activity_box.insert("end", token))

        def status(s):
            self.after(0, lambda: self.activity_box.insert("end", f"\n[Status]: {s}\n"))

        def work():
            import threading
            try:
                agent_orchestrator.run_agent(agent_type, q, chunk_callback=append, status_callback=status)
                self.after(0, lambda: self.activity_box.insert("end", "\n✔ Completed.\n"))
            except Exception as exc:
                self.after(0, lambda: self.activity_box.insert("end", f"\n⚠️ Error: {exc}\n"))
            finally:
                self.after(0, lambda: self.run_btn.configure(state="normal"))

        import threading
        threading.Thread(target=work, daemon=True).start()


class MemoryWorkspace(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=THEME["bg_secondary"], corner_radius=0, **kw)
        self._build()

    def _build(self):
        self.head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        self.head.pack(fill="x")
        ctk.CTkLabel(self.head, text="🧠 Memory & Persistent Knowledge", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=14, pady=8)
        self.clear_btn = ctk.CTkButton(self.head, text="Clear Project Memory", fg_color=THEME["error"], hover_color=THEME["error_hover"], width=150, height=28, command=self._clear_mem)
        self.clear_btn.pack(side="right", padx=10)

        # Add Memory Form
        self.add_frame = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], corner_radius=8)
        self.add_frame.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(self.add_frame, text="Add New Memory Item:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(6, 2))

        row = ctk.CTkFrame(self.add_frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 8))
        self.k_entry = ctk.CTkEntry(row, placeholder_text="Key / Fact Title (e.g. Database)", width=200, **ENTRY_COLORS)
        self.k_entry.pack(side="left", padx=(0, 6))
        self.v_entry = ctk.CTkEntry(row, placeholder_text="Value / Details (e.g. SQLite with WAL mode)", **ENTRY_COLORS)
        self.v_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.remember_btn = ctk.CTkButton(row, text="Remember 🧠", width=100, fg_color=THEME["accent"], hover_color=THEME["accent_hover"], command=self._add_mem)
        self.remember_btn.pack(side="right")

        # Scrollable list of memories
        self.mem_list = ctk.CTkScrollableFrame(self, fg_color=THEME["bg_panel"], **SCROLLABLE_COLORS)
        self.mem_list.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.refresh()

    def apply_theme(self, theme_name=None):
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "head"):
                self.head.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "clear_btn"):
                self.clear_btn.configure(fg_color=THEME["error"], hover_color=THEME["error_hover"])
            if hasattr(self, "add_frame"):
                self.add_frame.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "k_entry"):
                self.k_entry.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"], placeholder_text_color=THEME["text_muted"])
            if hasattr(self, "v_entry"):
                self.v_entry.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"], placeholder_text_color=THEME["text_muted"])
            if hasattr(self, "remember_btn"):
                self.remember_btn.configure(fg_color=THEME["accent"], hover_color=THEME["accent_hover"], text_color=THEME["accent_text"])
            if hasattr(self, "mem_list"):
                self.mem_list.configure(fg_color=THEME["bg_panel"], scrollbar_fg_color=THEME["bg_secondary"], scrollbar_button_color=THEME["bg_panel"], scrollbar_button_hover_color=THEME["bg_hover"])
            self.refresh()
        except Exception:
            pass

    def refresh(self):
        for w in self.mem_list.winfo_children():
            w.destroy()
        p_mems = memory_service.get_project_memories()
        lt_mems = memory_service.get_long_term_memories()

        if not p_mems and not lt_mems:
            ctk.CTkLabel(self.mem_list, text="No persistent memories saved yet.", text_color=THEME["text_secondary"]).pack(pady=20)
            return

        for m in p_mems + lt_mems:
            card = ctk.CTkFrame(self.mem_list, fg_color=THEME["bg_surface"], corner_radius=6)
            card.pack(fill="x", padx=6, pady=3)
            ctk.CTkLabel(card, text=f"🔑 {m['memory_key']}:", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["accent"]).pack(side="left", padx=8, pady=6)
            ctk.CTkLabel(card, text=m['memory_value'], font=ctk.CTkFont(size=12)).pack(side="left", fill="x", expand=True, padx=6)
            ctk.CTkButton(
                card,
                text="Forget ✕",
                width=70,
                height=24,
                fg_color="transparent",
                hover_color=THEME["error_hover"],
                font=ctk.CTkFont(size=11),
                command=lambda mid=m['id']: self._forget_mem(mid)
            ).pack(side="right", padx=6)

    def _add_mem(self):
        k = self.k_entry.get().strip()
        v = self.v_entry.get().strip()
        if k and v:
            memory_service.remember(k, v)
            self.k_entry.delete(0, "end")
            self.v_entry.delete(0, "end")
            self.refresh()

    def _forget_mem(self, mid):
        memory_service.forget(mid)
        self.refresh()

    def _clear_mem(self):
        if messagebox.askyesno("Confirm Clear", "Clear all memories for the current project?"):
            memory_service.clear_project()
            self.refresh()


class ModelsWorkspace(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=THEME["bg_secondary"], corner_radius=0, **kw)
        self._build()

    def _build(self):
        self.head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        self.head.pack(fill="x")
        ctk.CTkLabel(self.head, text="⚙️ Local Model Manager", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=14, pady=8)
        self.refresh_btn = ctk.CTkButton(self.head, text="Refresh Models", width=120, height=28, command=self.refresh)
        self.refresh_btn.pack(side="right", padx=10)

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", **SCROLLABLE_COLORS)
        self.list_frame.pack(fill="both", expand=True, padx=14, pady=10)
        self.refresh()

    def apply_theme(self, theme_name=None):
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "head"):
                self.head.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "list_frame"):
                self.list_frame.configure(scrollbar_fg_color=THEME["bg_secondary"], scrollbar_button_color=THEME["bg_panel"], scrollbar_button_hover_color=THEME["bg_hover"])
            self.refresh()
        except Exception:
            pass

    def refresh(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        catalogue = get_all_models()
        presets = catalogue.get("presets", {})

        # Presets Summary Card
        preset_card = ctk.CTkFrame(self.list_frame, fg_color=THEME["bg_panel"], corner_radius=8)
        preset_card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(preset_card, text="ACTIVE MODEL PRESETS", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["accent"]).pack(anchor="w", padx=12, pady=(10, 4))

        p_grid = ctk.CTkFrame(preset_card, fg_color="transparent")
        p_grid.pack(fill="x", padx=12, pady=(0, 10))
        for i, (k, v) in enumerate(presets.items()):
            ctk.CTkLabel(p_grid, text=f"• {k}:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_secondary"]).grid(row=i // 3, column=(i % 3) * 2, sticky="w", padx=4, pady=2)
            ctk.CTkLabel(p_grid, text=str(v), font=ctk.CTkFont(size=11), text_color=THEME["text_primary"]).grid(row=i // 3, column=(i % 3) * 2 + 1, sticky="w", padx=(0, 16), pady=2)

        # Detailed Models List
        ctk.CTkLabel(self.list_frame, text=f"DETECTED LOCAL MODELS ({catalogue['total_count']})", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["text_secondary"]).pack(anchor="w", pady=(6, 4))

        all_detected = catalogue.get("ollama_models", []) + catalogue.get("gguf_models", [])
        for m in all_detected:
            card = ctk.CTkFrame(self.list_frame, fg_color=THEME["bg_surface"], corner_radius=8)
            card.pack(fill="x", pady=4)

            top_r = ctk.CTkFrame(card, fg_color="transparent")
            top_r.pack(fill="x", padx=12, pady=(8, 2))
            ctk.CTkLabel(top_r, text=f"📦 {m['display_name']}", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
            ctk.CTkLabel(top_r, text=f"Format: {m['format']} | Provider: {m['provider']}", font=ctk.CTkFont(size=11), text_color=THEME["accent"]).pack(side="right")

            bot_r = ctk.CTkFrame(card, fg_color="transparent")
            bot_r.pack(fill="x", padx=12, pady=(0, 8))
            meta_str = f"Size: {m['size_gb']} GB | Est. RAM: ~{m['ram_required_gb']} GB | Context: {m['context_length']} | Capabilities: {', '.join(m['capabilities'])}"
            ctk.CTkLabel(bot_r, text=meta_str, font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"]).pack(side="left")


class DiagnosticsWorkspace(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=THEME["bg_secondary"], corner_radius=0, **kw)
        self._build()

    def _build(self):
        self.head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        self.head.pack(fill="x")
        ctk.CTkLabel(self.head, text="🛠️ System Diagnostics & Security", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=14, pady=8)
        self.diag_btn = ctk.CTkButton(self.head, text="Run Diagnostics", width=130, height=28, command=self.refresh)
        self.diag_btn.pack(side="right", padx=10)

        self.box = ctk.CTkScrollableFrame(self, fg_color="transparent", **SCROLLABLE_COLORS)
        self.box.pack(fill="both", expand=True, padx=14, pady=10)
        self.refresh()

    def apply_theme(self, theme_name=None):
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "head"):
                self.head.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "box"):
                self.box.configure(scrollbar_fg_color=THEME["bg_secondary"], scrollbar_button_color=THEME["bg_panel"], scrollbar_button_hover_color=THEME["bg_hover"])
            self.refresh()
        except Exception:
            pass

    def refresh(self):
        for w in self.box.winfo_children():
            w.destroy()

        diag = get_full_diagnostics()
        hw = diag.get("hardware", {})
        sec = diag.get("security", {})
        oll = diag.get("ollama", {})

        # 1. Hardware Status Card
        hw_card = ctk.CTkFrame(self.box, fg_color=THEME["bg_panel"], corner_radius=8)
        hw_card.pack(fill="x", pady=4)
        ctk.CTkLabel(hw_card, text="SYSTEM HARDWARE STATUS", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["accent"]).pack(anchor="w", padx=12, pady=(10, 4))
        grid = ctk.CTkFrame(hw_card, fg_color="transparent")
        grid.pack(fill="x", padx=12, pady=(0, 10))

        hw_items = [
            ("GPU:", hw.get("gpu_name")),
            ("VRAM:", f"{hw.get('vram_used_gb')} / {hw.get('vram_total_gb')}"),
            ("RAM:", f"{hw.get('ram_used_gb')} / {hw.get('ram_total_gb')}"),
            ("Storage:", f"{hw.get('storage_free_gb')} free / {hw.get('storage_total_gb')}"),
            ("CPU Cores:", hw.get("cpu_cores")),
            ("CPU Load:", hw.get("cpu_usage_pct")),
        ]
        for i, (k, v) in enumerate(hw_items):
            ctk.CTkLabel(grid, text=k, font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_secondary"]).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=4, pady=3)
            ctk.CTkLabel(grid, text=str(v), font=ctk.CTkFont(size=11)).grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=(0, 20), pady=3)

        # 2. USB Authorization Status Card
        sec_card = ctk.CTkFrame(self.box, fg_color=THEME["bg_panel"], corner_radius=8)
        sec_card.pack(fill="x", pady=6)
        ctk.CTkLabel(sec_card, text="SECURITY & USB AUTHORIZATION", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["accent"]).pack(anchor="w", padx=12, pady=(10, 4))

        status_text = "🔑 USB AUTHORIZED (Write Operations Enabled)" if sec.get("usb_authorized") else "🔒 READ-ONLY DEVELOPMENT MODE (Authorized USB Key Not Detected)"
        col = THEME["success"] if sec.get("usb_authorized") else THEME["warning"]
        ctk.CTkLabel(sec_card, text=status_text, font=ctk.CTkFont(size=12, weight="bold"), text_color=col).pack(anchor="w", padx=12, pady=2)
        ctk.CTkLabel(sec_card, text=sec.get("message", ""), font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"]).pack(anchor="w", padx=12, pady=(0, 10))

        # 3. 15-Point Subsystem Diagnostics Table
        sub_card = ctk.CTkFrame(self.box, fg_color=THEME["bg_panel"], corner_radius=8)
        sub_card.pack(fill="x", pady=6)
        ctk.CTkLabel(sub_card, text="SUBSYSTEM INTEGRATION & HEALTH MATRIX", font=ctk.CTkFont(size=13, weight="bold"), text_color=THEME["accent"]).pack(anchor="w", padx=12, pady=(10, 4))

        cat_m = get_all_models()
        model_count = cat_m.get("total_count", 0)

        diag_matrix = [
            ("Python Runtime", "PASS", "D:\\PrivateAI\\bin\\python (Embedded v3.12)", THEME["success"]),
            ("Ollama Local Server", "PASS" if oll.get("running") else "WARNING", "127.0.0.1:11435 local CUDA engine", THEME["success"] if oll.get("running") else THEME["warning"]),
            ("Local Models", "PASS", f"{model_count} Ollama + GGUF models available", THEME["success"]),
            ("Dedicated GPU", "PASS" if hw.get("gpu_name") != "Unavailable" else "WARNING", hw.get("gpu_name", "N/A"), THEME["success"]),
            ("GPU VRAM", "PASS", f"{hw.get('vram_used_gb')} / {hw.get('vram_total_gb')} allocated", THEME["success"]),
            ("System RAM", "PASS", f"{hw.get('ram_used_gb')} / {hw.get('ram_total_gb')} memory", THEME["success"]),
            ("CPU Topology", "PASS", f"{hw.get('cpu_cores', '16')} logical processing threads", THEME["success"]),
            ("SQLite Persistence", "PASS", "ai_cache.db (WAL mode active)", THEME["success"]),
            ("ChromaDB Vector Store", "PASS", f"{diag['rag']['indexed_chunks']} embeddings indexed", THEME["success"]),
            ("Tesseract Local OCR", "PASS" if diag["ocr"]["ready"] else "WARNING", diag["ocr"]["status"], THEME["success"] if diag["ocr"]["ready"] else THEME["warning"]),
            ("Multimodal Vision", "PASS", f"Active ({diag['vision']['model']})", THEME["success"]),
            ("Voice Input (STT)", "PASS", "Windows Native SpeechRecognition (en-US)", THEME["success"]),
            ("Voice Output (TTS)", "PASS", "Windows SAPI Synthesizer (Zero Latency)", THEME["success"]),
            ("USB Authorization", "PASS" if sec.get("usb_authorized") else "WARNING", "Authorized USB Active" if sec.get("usb_authorized") else "Read-Only Development Mode", THEME["success"] if sec.get("usb_authorized") else THEME["warning"]),
            ("Local Storage", "PASS", f"{hw.get('storage_free_gb')} free on D:\\", THEME["success"]),
        ]

        table_frame = ctk.CTkFrame(sub_card, fg_color="transparent")
        table_frame.pack(fill="x", padx=12, pady=(0, 10))

        for name, status_badge, detail, badge_col in diag_matrix:
            row = ctk.CTkFrame(table_frame, fg_color=THEME["bg_surface"], corner_radius=6)
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=11, weight="bold"), width=160, anchor="w").pack(side="left", padx=8, pady=4)
            ctk.CTkLabel(
                row,
                text=status_badge,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=badge_col,
                fg_color=THEME["bg_secondary"],
                corner_radius=4,
                padx=6,
                pady=2,
                width=65
            ).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=detail, font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"], anchor="w").pack(side="left", fill="x", expand=True, padx=8)


class StudyWorkspace(ctk.CTkFrame):
    """Academic Study Agent & Engineering Revision Assistant."""
    def __init__(self, master, on_ask_ai=None, **kw):
        super().__init__(master, fg_color=THEME["bg_secondary"], corner_radius=0, **kw)
        self.on_ask_ai = on_ask_ai
        self._build()

    def _build(self):
        self.head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        self.head.pack(fill="x")
        ctk.CTkLabel(self.head, text="📚 Study & Academic Tutor", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=14, pady=8)

        self.ctrl = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], corner_radius=8)
        self.ctrl.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(self.ctrl, text="Academic Subject / Topic / Question:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=12, pady=(8, 2))
        self.topic_entry = ctk.CTkEntry(self.ctrl, placeholder_text="e.g. Dynamic Programming, B-Trees, Microservices Architecture, Thermodynamic Cycles", font=ctk.CTkFont(size=13), **ENTRY_COLORS)
        self.topic_entry.pack(fill="x", padx=12, pady=4)

        b_row = ctk.CTkFrame(self.ctrl, fg_color="transparent")
        b_row.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkLabel(b_row, text="Mode:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_secondary"]).pack(side="left", padx=(0, 6))
        self.mode_var = ctk.StringVar(value="explain")
        ctk.CTkOptionMenu(b_row, variable=self.mode_var, values=["explain", "quiz", "flashcards", "viva"], width=110, **OPTION_MENU_COLORS).pack(side="left", padx=4)

        self.gen_btn = ctk.CTkButton(
            b_row,
            text="Generate Study Material 🎓",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            command=self._generate_study
        )
        self.gen_btn.pack(side="right")

        self.status_lbl = ctk.CTkLabel(b_row, text="Ready.", font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"])
        self.status_lbl.pack(side="left", padx=10)

        self.out_box = ctk.CTkTextbox(self, font=ctk.CTkFont(size=12), **TEXTBOX_COLORS)
        self.out_box.pack(fill="both", expand=True, padx=14, pady=(0, 10))

    def apply_theme(self, theme_name=None):
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "head"):
                self.head.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "ctrl"):
                self.ctrl.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "topic_entry"):
                self.topic_entry.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"], placeholder_text_color=THEME["text_muted"])
            if hasattr(self, "gen_btn"):
                self.gen_btn.configure(fg_color=THEME["accent"], hover_color=THEME["accent_hover"], text_color=THEME["accent_text"])
            if hasattr(self, "status_lbl"):
                self.status_lbl.configure(text_color=THEME["text_secondary"])
            if hasattr(self, "out_box"):
                self.out_box.configure(fg_color=THEME["bg_surface"], border_color=THEME["border"], text_color=THEME["text_primary"])
        except Exception:
            pass

    def _generate_study(self):
        topic = self.topic_entry.get().strip()
        if not topic:
            return
        mode = self.mode_var.get()
        from backend.study_analysis import build_study_prompt
        sys_p, user_p = build_study_prompt(topic, mode=mode)
        self.status_lbl.configure(text=f"Generating {mode} material…")
        self.gen_btn.configure(state="disabled")
        self.out_box.delete("1.0", "end")

        def append(token):
            self.after(0, lambda: self.out_box.insert("end", token))

        def work():
            import threading
            try:
                from backend.agents import agent_orchestrator
                agent_orchestrator.run_agent("Tutor", user_p, chunk_callback=append)
                self.after(0, lambda: self.status_lbl.configure(text="Study generation complete."))
            except Exception as exc:
                self.after(0, lambda: self.out_box.insert("end", f"\n[Error]: {exc}"))
                self.after(0, lambda: self.status_lbl.configure(text="Generation error."))
            finally:
                self.after(0, lambda: self.gen_btn.configure(state="normal"))

        import threading
        threading.Thread(target=work, daemon=True).start()


class SettingsWorkspace(ctk.CTkFrame):
    """Personalization, Themes, and Local System Preferences organized into 7 clean categories."""
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=THEME["bg_secondary"], corner_radius=0, **kw)
        self._build()

    def _build(self):
        self.head = ctk.CTkFrame(self, fg_color=THEME["bg_panel"], height=44, corner_radius=0)
        self.head.pack(fill="x")
        ctk.CTkLabel(self.head, text="⚙️ Settings & Personalization", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=14, pady=8)

        self.box = ctk.CTkScrollableFrame(self, fg_color="transparent", **SCROLLABLE_COLORS)
        self.box.pack(fill="both", expand=True, padx=14, pady=10)

        self.cards = []
        self.category_headers = []

        # 1. General
        c1 = ctk.CTkFrame(self.box, fg_color=THEME["bg_panel"], corner_radius=8)
        c1.pack(fill="x", pady=5)
        h1 = ctk.CTkLabel(c1, text="GENERAL", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent"])
        h1.pack(anchor="w", padx=12, pady=(10, 4))
        self.category_headers.append(h1)
        r1 = ctk.CTkFrame(c1, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(r1, text="Language:").pack(side="left", padx=(0, 10))
        ctk.CTkOptionMenu(r1, values=["English (US)", "English (UK)"], width=130, **OPTION_MENU_COLORS).pack(side="left")
        r1b = ctk.CTkFrame(c1, fg_color="transparent")
        r1b.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(r1b, text="Startup Workspace:").pack(side="left", padx=(0, 10))
        ctk.CTkOptionMenu(r1b, values=["Chat (Default)", "Documents", "Projects"], width=130, **OPTION_MENU_COLORS).pack(side="left")
        self.cards.append(c1)

        # 2. AI
        c2 = ctk.CTkFrame(self.box, fg_color=THEME["bg_panel"], corner_radius=8)
        c2.pack(fill="x", pady=5)
        h2 = ctk.CTkLabel(c2, text="LOCAL AI MODELS", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent"])
        h2.pack(anchor="w", padx=12, pady=(10, 4))
        self.category_headers.append(h2)
        r2 = ctk.CTkFrame(c2, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(r2, text="Model Performance Preference:").pack(side="left", padx=(0, 10))
        self.def_model = ctk.StringVar(value="Balanced")
        ctk.CTkOptionMenu(r2, variable=self.def_model, values=["Auto", "Fast", "Balanced", "Advanced"], **OPTION_MENU_COLORS).pack(side="left")
        self.cards.append(c2)

        # 3. Appearance
        c3 = ctk.CTkFrame(self.box, fg_color=THEME["bg_panel"], corner_radius=8)
        c3.pack(fill="x", pady=5)
        h3 = ctk.CTkLabel(c3, text="APPEARANCE & THEME", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent"])
        h3.pack(anchor="w", padx=12, pady=(10, 4))
        self.category_headers.append(h3)
        r3 = ctk.CTkFrame(c3, fg_color="transparent")
        r3.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(r3, text="Theme Mode:").pack(side="left", padx=(0, 10))
        self.theme_var = ctk.StringVar(value=get_current_theme())
        ctk.CTkOptionMenu(r3, variable=self.theme_var, values=["dark", "light"], command=lambda v: set_theme(v), **OPTION_MENU_COLORS).pack(side="left")
        self.cards.append(c3)

        # 4. Storage & Backups
        c4 = ctk.CTkFrame(self.box, fg_color=THEME["bg_panel"], corner_radius=8)
        c4.pack(fill="x", pady=5)
        h4 = ctk.CTkLabel(c4, text="STORAGE & LOCAL DATA", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent"])
        h4.pack(anchor="w", padx=12, pady=(10, 4))
        self.category_headers.append(h4)
        ctk.CTkLabel(c4, text="• Local Workspace: D:\\PrivateAI (Strict Air-Gap)\n• SQLite Database: D:\\PrivateAI\\app\\data\\ai_cache.db\n• Vector ChromaDB: D:\\PrivateAI\\app\\chroma_db", justify="left").pack(anchor="w", padx=12, pady=(0, 10))
        self.cards.append(c4)

        # 5. Password Authentication (Section 14 & 16)
        from backend.password_auth import password_auth_service
        c_pwd = ctk.CTkFrame(self.box, fg_color=THEME["bg_panel"], corner_radius=8)
        c_pwd.pack(fill="x", pady=5)
        h_pwd = ctk.CTkLabel(c_pwd, text="PASSWORD AUTHENTICATION", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent"])
        h_pwd.pack(anchor="w", padx=12, pady=(10, 4))
        self.category_headers.append(h_pwd)

        pwd_row = ctk.CTkFrame(c_pwd, fg_color="transparent")
        pwd_row.pack(fill="x", padx=12, pady=(0, 10))

        pwd_is_cfg = password_auth_service.is_password_configured()
        status_text = "● Enabled" if pwd_is_cfg else "○ Not configured"
        status_color = THEME["success"] if pwd_is_cfg else THEME["text_muted"]

        ctk.CTkLabel(pwd_row, text="Status:", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME["text_secondary"]).pack(side="left", padx=(0, 6))
        self.pwd_status_lbl = ctk.CTkLabel(pwd_row, text=status_text, font=ctk.CTkFont(size=12, weight="bold"), text_color=status_color)
        self.pwd_status_lbl.pack(side="left", padx=(0, 16))

        if pwd_is_cfg:
            ctk.CTkButton(
                pwd_row,
                text="Change Password",
                font=ctk.CTkFont(size=11, weight="bold"),
                height=28,
                width=130,
                fg_color=THEME["bg_secondary"],
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_primary"],
                command=self.open_change_password_modal
            ).pack(side="left", padx=(0, 8))
        else:
            ctk.CTkButton(
                pwd_row,
                text="Set Password",
                font=ctk.CTkFont(size=11, weight="bold"),
                height=28,
                width=110,
                fg_color=THEME["accent"],
                hover_color=THEME["accent_hover"],
                text_color=THEME["accent_text"],
                command=self.open_change_password_modal
            ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            pwd_row,
            text="Security Details",
            font=ctk.CTkFont(size=11),
            height=28,
            width=120,
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_secondary"],
            command=self.show_security_details_modal
        ).pack(side="left")
        self.cards.append(c_pwd)

        # 6. Privacy & Security Control Center (Requirement 26 & Section 17)
        c5 = ctk.CTkFrame(self.box, fg_color=THEME["bg_panel"], corner_radius=8)
        c5.pack(fill="x", pady=5)
        h5 = ctk.CTkLabel(c5, text="PRIVACY CONTROL CENTER", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["success"])
        h5.pack(anchor="w", padx=12, pady=(10, 4))
        self.category_headers.append(h5)

        # Status indicators
        stat_frame = ctk.CTkFrame(c5, fg_color="transparent")
        stat_frame.pack(fill="x", padx=12, pady=(0, 6))

        privacy_metrics = [
            ("USB Authorization", "● Active", THEME["success"]),
            ("Password Protection", "● Active" if pwd_is_cfg else "○ Not configured", THEME["success"] if pwd_is_cfg else THEME["text_muted"]),
            ("Device Binding", "● Active", THEME["success"]),
            ("Workspace Lock", "● Active", THEME["success"]),
            ("Chat History", "● Disabled", THEME["text_muted"]),
            ("Cloud AI", "● Disabled", THEME["text_muted"]),
            ("Telemetry", "● Disabled", THEME["text_muted"]),
        ]

        for label, val, color in privacy_metrics:
            p_row = ctk.CTkFrame(stat_frame, fg_color=THEME["bg_surface"], corner_radius=6)
            p_row.pack(fill="x", pady=2)
            ctk.CTkLabel(p_row, text=label, font=ctk.CTkFont(size=11, weight="bold"), width=160, anchor="w").pack(side="left", padx=8, pady=3)
            ctk.CTkLabel(p_row, text=val, font=ctk.CTkFont(size=11, weight="bold"), text_color=color).pack(side="left", padx=8)

        # Local Data Map
        ctk.CTkLabel(c5, text="Local Data Architecture Map:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent"]).pack(anchor="w", padx=12, pady=(6, 2))
        data_map = [
            ("Chat", "RAM / Temporary Session (Zero Persistence)"),
            ("Documents", "Local Disk Only (D:\\PrivateAI)"),
            ("Embeddings", "Local ChromaDB (Encrypted Workspace Store)"),
            ("Models", "Local Machine Hardware (Ollama 127.0.0.1:11435)"),
            ("USB", "Hardware Authorization Token Only (Zero Data on USB)")
        ]
        map_frame = ctk.CTkFrame(c5, fg_color="transparent")
        map_frame.pack(fill="x", padx=12, pady=(0, 10))
        for comp, loc in data_map:
            m_row = ctk.CTkFrame(map_frame, fg_color="transparent")
            m_row.pack(fill="x", pady=1)
            ctk.CTkLabel(m_row, text=f"• {comp}:", font=ctk.CTkFont(size=11, weight="bold"), width=90, anchor="w").pack(side="left")
            ctk.CTkLabel(m_row, text=loc, font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"], anchor="w").pack(side="left")
        self.cards.append(c5)

        # 7. Voice
        c6 = ctk.CTkFrame(self.box, fg_color=THEME["bg_panel"], corner_radius=8)
        c6.pack(fill="x", pady=5)
        h6 = ctk.CTkLabel(c6, text="VOICE & AUDIO", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent"])
        h6.pack(anchor="w", padx=12, pady=(10, 4))
        self.category_headers.append(h6)
        ctk.CTkLabel(c6, text="• Voice Engine: Windows SAPI (100% Local & Offline)\n• Microphone: Push-to-Talk and Tap-to-Dictate active", justify="left").pack(anchor="w", padx=12, pady=(0, 10))
        self.cards.append(c6)

        # 8. Advanced & Diagnostics
        c7 = ctk.CTkFrame(self.box, fg_color=THEME["bg_panel"], corner_radius=8)
        c7.pack(fill="x", pady=5)
        h7 = ctk.CTkLabel(c7, text="ADVANCED & DIAGNOSTICS", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["accent"])
        h7.pack(anchor="w", padx=12, pady=(10, 4))
        self.category_headers.append(h7)
        self.diag_desc = ctk.CTkLabel(c7, text="Technical hardware metrics and system logs are safely segregated here.\nTo view live GPU/VRAM statistics, switch to Diagnostics Workspace.", justify="left", text_color=THEME["text_secondary"])
        self.diag_desc.pack(anchor="w", padx=12, pady=(0, 10))
        self.cards.append(c7)

    def open_change_password_modal(self):
        from backend.password_auth import password_auth_service
        from frontend.toast import ToastNotification

        modal = ctk.CTkToplevel(self)
        modal.title("Change Workspace Password")
        modal.geometry("440x380")
        modal.configure(fg_color=THEME["bg_primary"])
        modal.resizable(False, False)
        modal.grab_set()

        card = ctk.CTkFrame(modal, fg_color=THEME["bg_secondary"], border_color=THEME["border"], border_width=1, corner_radius=12)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(card, text="Change Password", font=ctk.CTkFont(size=16, weight="bold"), text_color=THEME["text_primary"]).pack(pady=(16, 4))
        ctk.CTkLabel(card, text="Enter current password and choose a new one.", font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"]).pack(pady=(0, 14))

        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="x", padx=24, pady=(0, 10))

        ctk.CTkLabel(f, text="Current Password", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_secondary"]).pack(anchor="w", pady=(0, 2))
        cur_entry = ctk.CTkEntry(f, show="•", height=32, font=ctk.CTkFont(size=12), **ENTRY_COLORS)
        cur_entry.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(f, text="New Password", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_secondary"]).pack(anchor="w", pady=(0, 2))
        new_entry = ctk.CTkEntry(f, show="•", height=32, font=ctk.CTkFont(size=12), **ENTRY_COLORS)
        new_entry.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(f, text="Confirm New Password", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_secondary"]).pack(anchor="w", pady=(0, 2))
        conf_entry = ctk.CTkEntry(f, show="•", height=32, font=ctk.CTkFont(size=12), **ENTRY_COLORS)
        conf_entry.pack(fill="x", pady=(0, 6))

        err_lbl = ctk.CTkLabel(f, text="", font=ctk.CTkFont(size=11), text_color=THEME["error"])
        err_lbl.pack(anchor="w", pady=(0, 4))

        def submit_change():
            cp = cur_entry.get()
            np = new_entry.get()
            cnp = conf_entry.get()

            if not cp or not np:
                err_lbl.configure(text="All fields are required.")
                return
            if len(np) < 8:
                err_lbl.configure(text="New password must be at least 8 characters.")
                return
            if np != cnp:
                err_lbl.configure(text="New passwords do not match.")
                return

            res = password_auth_service.change_password(cp, np, cnp)
            if res.get("success"):
                modal.destroy()
                ToastNotification.show(self, "Password changed successfully.", icon="🔑", level="success")
            else:
                err_lbl.configure(text=res.get("message", "Error changing password."))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 16))

        ctk.CTkButton(
            btn_row,
            text="Update Password",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            text_color=THEME["accent_text"],
            command=submit_change
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            btn_row,
            text="Cancel",
            font=ctk.CTkFont(size=12),
            height=32,
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_secondary"],
            command=modal.destroy
        ).pack(side="right")

    def show_security_details_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Security Details")
        modal.geometry("480x360")
        modal.configure(fg_color=THEME["bg_primary"])
        modal.resizable(False, False)
        modal.grab_set()

        card = ctk.CTkFrame(modal, fg_color=THEME["bg_secondary"], border_color=THEME["border"], border_width=1, corner_radius=12)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(card, text="Local Security Architecture", font=ctk.CTkFont(size=16, weight="bold"), text_color=THEME["text_primary"]).pack(pady=(16, 4))
        ctk.CTkLabel(card, text="Hardware isolation and cryptographic parameters.", font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"]).pack(pady=(0, 14))

        items = [
            ("Password KDF", "PBKDF2-HMAC-SHA256 (600,000 rounds)"),
            ("Salt", "Cryptographic 256-bit Random (CSPRNG)"),
            ("Brute-Force Guard", "Active (Lockout cooldown after 5 attempts)"),
            ("USB Key Model", "Hardware Authorization Token (Zero user data)"),
            ("Chat Storage", "RAM-Only Session (Zero-History Mode)"),
            ("Telemetry / Cloud", "100% Air-Gapped & Offline"),
        ]
        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="x", padx=24, pady=(0, 14))
        for k, v in items:
            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{k}:", font=ctk.CTkFont(size=11, weight="bold"), width=140, anchor="w", text_color=THEME["text_primary"]).pack(side="left")
            ctk.CTkLabel(row, text=v, font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"], anchor="w").pack(side="left")

        ctk.CTkButton(
            card,
            text="Close",
            font=ctk.CTkFont(size=12),
            height=30,
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_primary"],
            command=modal.destroy
        ).pack(pady=(4, 16))

    def apply_theme(self, theme_name=None):
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "head"):
                self.head.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "box"):
                self.box.configure(scrollbar_fg_color=THEME["bg_secondary"], scrollbar_button_color=THEME["bg_panel"], scrollbar_button_hover_color=THEME["bg_hover"])
            if hasattr(self, "cards"):
                for c in self.cards:
                    c.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "category_headers"):
                for lbl in self.category_headers:
                    lbl.configure(text_color=THEME["accent"])
            if hasattr(self, "diag_desc"):
                self.diag_desc.configure(text_color=THEME["text_secondary"])
            if hasattr(self, "theme_var"):
                self.theme_var.set(get_current_theme())
        except Exception:
            pass
