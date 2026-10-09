"""
Infinity AI - Password-Only Local Workspace Security Overlay
Module: frontend/lock_overlay.py

Architecture:
- Pure local password authentication (Zero USB dependency).
- State 1: Locked -> Minimal ChatGPT/Claude-style password unlock screen.
- State 2: Correct Password -> Instant workspace unlock.
- State 3: Incorrect Password -> Sanitized feedback and progressive brute-force lockout.
- State 4: First Run -> "Create Workspace Password" setup with offline recovery code.
- State 5: Offline Recovery -> Reset password using offline recovery code.
"""

import threading
import time
from tkinter import filedialog
from typing import Callable, Optional, Dict, Any
import customtkinter as ctk

from frontend.theme import THEME, ENTRY_COLORS
from frontend.toast import ToastNotification
import backend.security as security

def unlock_workspace(*args, **kwargs):
    return security.unlock_workspace(*args, **kwargs)

def lock_workspace(*args, **kwargs):
    return security.lock_workspace(*args, **kwargs)

def set_password_authenticated(*args, **kwargs):
    return security.set_password_authenticated(*args, **kwargs)

def is_password_authenticated(*args, **kwargs):
    return security.is_password_authenticated(*args, **kwargs)

def verify_usb_authorization(*args, **kwargs):
    return security.verify_usb_authorization(*args, **kwargs)

from backend.password_auth import password_auth_service


class WorkspaceLockOverlay(ctk.CTkFrame):
    """Full-window modal security overlay for Infinity AI (Password-Only Authentication)."""

    def __init__(
        self,
        master,
        on_unlocked: Optional[Callable[[], None]] = None,
        on_read_only: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        **kw
    ):
        super().__init__(master, fg_color=THEME["bg_primary"], corner_radius=0, **kw)
        self.on_unlocked = on_unlocked
        self.on_read_only = on_read_only
        self.on_exit = on_exit

        self._current_mode: str = "password_unlock"
        self._lockout_countdown_active: bool = False
        self._lockout_seconds_left: int = 0
        self._show_pwd_state: bool = False

        self._build_container()

    def _build_container(self):
        """Creates the centered card container for all security modes."""
        self.card = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_secondary"],
            border_color=THEME["border"],
            border_width=1,
            corner_radius=14,
            width=540
        )
        self.card.place(relx=0.5, rely=0.5, anchor="center")

    def _clear_card(self):
        """Clears all widgets inside the card before building a new view state."""
        for widget in self.card.winfo_children():
            widget.destroy()

    def update_state(self, *args, **kwargs):
        """
        Evaluates the local workspace authentication state.
        Renders password setup on first run, or password unlock screen.
        """
        if not password_auth_service.is_password_configured():
            self._current_mode = "password_setup"
            self._render_password_setup_view()
        elif not is_password_authenticated():
            self._current_mode = "password_unlock"
            self._render_password_unlock_view()
        else:
            self.hide()
            if self.on_unlocked:
                self.on_unlocked()

    # =========================================================================
    # MINIMAL CHATGPT/CLAUDE-STYLE PASSWORD UNLOCK SCREEN
    # =========================================================================
    def _render_password_unlock_view(self, *args, **kwargs):
        self._clear_card()
        self._current_mode = "password_unlock"

        # 🔐 Icon
        ctk.CTkLabel(self.card, text="🔐", font=ctk.CTkFont(size=42)).pack(pady=(36, 6))

        # Title: Private Workspace Locked
        ctk.CTkLabel(
            self.card,
            text="Private Workspace Locked",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=THEME["text_primary"]
        ).pack(pady=(0, 4))

        # Subtitle: Enter your workspace password
        ctk.CTkLabel(
            self.card,
            text="Enter your workspace password",
            font=ctk.CTkFont(size=12),
            text_color=THEME["text_secondary"]
        ).pack(pady=(0, 16))

        # Fields container
        fields_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        fields_frame.pack(fill="x", padx=48, pady=(0, 4))

        # Password input row: [ ••••••••••••••••••  👁 ]
        pwd_row = ctk.CTkFrame(fields_frame, fg_color="transparent")
        pwd_row.pack(fill="x", pady=(0, 4))

        self.unlock_pwd_entry = ctk.CTkEntry(
            pwd_row,
            placeholder_text="Workspace password",
            show="•",
            font=ctk.CTkFont(size=13),
            height=38,
            **ENTRY_COLORS
        )
        self.unlock_pwd_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.unlock_eye_btn = ctk.CTkButton(
            pwd_row,
            text="👁",
            width=38,
            height=38,
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_secondary"],
            command=self._toggle_unlock_password_visibility
        )
        self.unlock_eye_btn.pack(side="right")

        # Key bindings: Enter to unlock, Escape to clear
        self.unlock_pwd_entry.bind("<Return>", lambda e: self._submit_unlock_password())
        self.unlock_pwd_entry.bind("<Escape>", lambda e: self.unlock_pwd_entry.delete(0, "end"))

        # Feedback / Error Label
        self.unlock_feedback_label = ctk.CTkLabel(
            fields_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=THEME["error"]
        )
        self.unlock_feedback_label.pack(anchor="w", pady=(2, 6))

        # Primary Button: [ Unlock ]
        self.unlock_btn = ctk.CTkButton(
            self.card,
            text="Unlock",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            text_color=THEME["accent_text"],
            height=38,
            command=self._submit_unlock_password
        )
        self.unlock_btn.pack(fill="x", padx=48, pady=(2, 14))

        # Check existing lockout after creating controls
        is_locked, rem_secs = password_auth_service.is_locked_out()
        if is_locked:
            self._start_lockout_countdown(rem_secs)

        # Footer Actions: [ Recovery ] and [ Exit ]
        footer_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        footer_frame.pack(fill="x", padx=48, pady=(0, 26))

        ctk.CTkButton(
            footer_frame,
            text="Recovery",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_muted"],
            height=26,
            command=self._render_recovery_entry_view
        ).pack(side="left")

        ctk.CTkButton(
            footer_frame,
            text="Exit",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_secondary"],
            width=50,
            height=26,
            command=self._handle_exit
        ).pack(side="right")

        # Autofocus password field
        self.unlock_pwd_entry.focus_set()

    def _toggle_unlock_password_visibility(self):
        self._show_pwd_state = not self._show_pwd_state
        show_char = "" if self._show_pwd_state else "•"
        if hasattr(self, "unlock_pwd_entry"):
            self.unlock_pwd_entry.configure(show=show_char)

    def _submit_unlock_password(self):
        if not hasattr(self, "unlock_pwd_entry"):
            return

        pwd = self.unlock_pwd_entry.get()
        if not pwd:
            if hasattr(self, "unlock_feedback_label"):
                self.unlock_feedback_label.configure(text="Please enter your password.", text_color=THEME["error"])
            return

        # Disable button momentarily to indicate work
        if hasattr(self, "unlock_btn"):
            self.unlock_btn.configure(state="disabled", text="Verifying…")
        self.update_idletasks()

        self._pending_verify_result = None

        def do_verify():
            self._pending_verify_result = password_auth_service.verify_password(pwd)

        threading.Thread(target=do_verify, daemon=True).start()
        self._poll_verify_completion()

    def _poll_verify_completion(self):
        """Polls for password verification completion on main thread."""
        if getattr(self, "_pending_verify_result", None) is not None:
            res = self._pending_verify_result
            self._pending_verify_result = None
            self._on_password_verify_result(res)
        else:
            try:
                self.after(25, self._poll_verify_completion)
            except Exception:
                pass

    # =========================================================================
    # STATE: Verify Result (Success vs Incorrect / Lockout)
    # =========================================================================
    def _on_password_verify_result(self, res: Dict[str, Any]):
        if res.get("success"):
            # Password Correct -> Unlock workspace
            if hasattr(self, "unlock_pwd_entry"):
                self.unlock_pwd_entry.delete(0, "end")
            password_auth_service.clear_sensitive_state()
            set_password_authenticated(True)
            unlock_workspace()
            self.hide()
            ToastNotification.show(self.master, "Workspace Unlocked — Welcome back!", icon="🔓", level="success")
            if self.on_unlocked:
                self.on_unlocked()
        else:
            # Password Incorrect
            if hasattr(self, "unlock_btn"):
                self.unlock_btn.configure(state="normal", text="Unlock")

            if res.get("locked_out"):
                dur = res.get("lockout_remaining_seconds", 30)
                self._start_lockout_countdown(dur)
            else:
                msg = res.get("message", "Incorrect password.")
                if hasattr(self, "unlock_feedback_label"):
                    self.unlock_feedback_label.configure(text=msg, text_color=THEME["error"])
                if hasattr(self, "unlock_pwd_entry"):
                    self.unlock_pwd_entry.focus_set()
                    self.unlock_pwd_entry.select_range(0, "end")

    def _start_lockout_countdown(self, seconds: int):
        if getattr(self, "_lockout_job", None):
            try:
                self.after_cancel(self._lockout_job)
            except Exception:
                pass
            self._lockout_job = None
        self._lockout_seconds_left = seconds
        self._lockout_countdown_active = True
        if hasattr(self, "unlock_pwd_entry"):
            try:
                self.unlock_pwd_entry.configure(state="disabled")
            except Exception:
                pass
        if hasattr(self, "unlock_btn"):
            try:
                self.unlock_btn.configure(state="disabled")
            except Exception:
                pass
        self._tick_lockout()

    def _tick_lockout(self):
        if not self._lockout_countdown_active:
            return
        if self._lockout_seconds_left <= 0:
            self._lockout_countdown_active = False
            self._lockout_job = None
            if hasattr(self, "unlock_pwd_entry"):
                try:
                    self.unlock_pwd_entry.configure(state="normal")
                    self.unlock_pwd_entry.delete(0, "end")
                    self.unlock_pwd_entry.focus_set()
                except Exception:
                    pass
            if hasattr(self, "unlock_btn"):
                try:
                    self.unlock_btn.configure(state="normal", text="Unlock")
                except Exception:
                    pass
            if hasattr(self, "unlock_feedback_label"):
                try:
                    self.unlock_feedback_label.configure(text="")
                except Exception:
                    pass
            return

        if hasattr(self, "unlock_feedback_label"):
            try:
                self.unlock_feedback_label.configure(
                    text=f"Too many unsuccessful attempts. Try again in {self._lockout_seconds_left}s."
                )
            except Exception:
                pass
        self._lockout_seconds_left -= 1
        try:
            self._lockout_job = self.after(1000, self._tick_lockout)
        except Exception:
            pass

    # =========================================================================
    # First Run / Password Not Configured
    # =========================================================================
    def _render_password_setup_view(self):
        self._clear_card()
        self._current_mode = "password_setup"

        # 🔐 Icon
        ctk.CTkLabel(self.card, text="🔐", font=ctk.CTkFont(size=40)).pack(pady=(22, 4))

        # Title: Create Workspace Password
        ctk.CTkLabel(
            self.card,
            text="Create Workspace Password",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=THEME["text_primary"]
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            self.card,
            text="Protect Infinity AI with a local workspace password.",
            font=ctk.CTkFont(size=12),
            text_color=THEME["text_secondary"],
            justify="center",
            wraplength=440
        ).pack(padx=24, pady=(0, 14))

        fields_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        fields_frame.pack(fill="x", padx=44, pady=(0, 8))

        # Password
        ctk.CTkLabel(
            fields_frame,
            text="Password",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME["text_secondary"]
        ).pack(anchor="w", pady=(0, 3))

        pwd_row = ctk.CTkFrame(fields_frame, fg_color="transparent")
        pwd_row.pack(fill="x", pady=(0, 6))

        self.setup_pwd_entry = ctk.CTkEntry(
            pwd_row,
            placeholder_text="Enter password (minimum 8 characters)",
            show="•",
            font=ctk.CTkFont(size=13),
            height=36,
            **ENTRY_COLORS
        )
        self.setup_pwd_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.setup_eye_btn = ctk.CTkButton(
            pwd_row,
            text="👁",
            width=36,
            height=36,
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_secondary"],
            command=self._toggle_setup_password_visibility
        )
        self.setup_eye_btn.pack(side="right")

        # Password strength indicator
        self.setup_strength_label = ctk.CTkLabel(
            fields_frame,
            text="Strength: Minimum 8 characters required",
            font=ctk.CTkFont(size=11),
            text_color=THEME["text_muted"]
        )
        self.setup_strength_label.pack(anchor="w", pady=(0, 8))
        self.setup_pwd_entry.bind("<KeyRelease>", self._on_setup_pwd_change)

        # Confirm Password
        ctk.CTkLabel(
            fields_frame,
            text="Confirm Password",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME["text_secondary"]
        ).pack(anchor="w", pady=(0, 3))

        self.setup_confirm_entry = ctk.CTkEntry(
            fields_frame,
            placeholder_text="Re-enter password",
            show="•",
            font=ctk.CTkFont(size=13),
            height=36,
            **ENTRY_COLORS
        )
        self.setup_confirm_entry.pack(fill="x", pady=(0, 8))
        self.setup_confirm_entry.bind("<Return>", lambda e: self._submit_create_password())

        # Error / Feedback
        self.setup_feedback_label = ctk.CTkLabel(
            fields_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=THEME["error"]
        )
        self.setup_feedback_label.pack(anchor="w", pady=(0, 6))

        # Privacy notice
        ctk.CTkLabel(
            self.card,
            text="Your password stays on this device. It is never uploaded or sent to the AI.",
            font=ctk.CTkFont(size=11),
            text_color=THEME["text_muted"],
            justify="center"
        ).pack(padx=24, pady=(0, 14))

        # Action: [ Create Password ]
        btn_box = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_box.pack(fill="x", padx=44, pady=(0, 22))

        ctk.CTkButton(
            btn_box,
            text="Create Password",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            text_color=THEME["accent_text"],
            height=36,
            command=self._submit_create_password
        ).pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            btn_box,
            text="Exit",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_secondary"],
            height=28,
            command=self._handle_exit
        ).pack(fill="x")

        # Autofocus
        self.setup_pwd_entry.focus_set()

    def _toggle_setup_password_visibility(self):
        self._show_pwd_state = not self._show_pwd_state
        show_char = "" if self._show_pwd_state else "•"
        if hasattr(self, "setup_pwd_entry"):
            self.setup_pwd_entry.configure(show=show_char)
        if hasattr(self, "setup_confirm_entry"):
            self.setup_confirm_entry.configure(show=show_char)

    def _on_setup_pwd_change(self, event=None):
        if not hasattr(self, "setup_pwd_entry") or not hasattr(self, "setup_strength_label"):
            return
        val = self.setup_pwd_entry.get()
        eval_res = password_auth_service.evaluate_password_strength(val)
        self.setup_strength_label.configure(
            text=f"Strength: {eval_res['label']}",
            text_color=eval_res["color"]
        )

    def _submit_create_password(self):
        pwd = self.setup_pwd_entry.get()
        confirm = self.setup_confirm_entry.get()

        if len(pwd) < 8:
            self.setup_feedback_label.configure(text="Password must be at least 8 characters.")
            return

        if pwd != confirm:
            self.setup_feedback_label.configure(text="Passwords do not match.")
            return

        res = password_auth_service.create_password(pwd, confirm)
        if res.get("success"):
            rec_code = res.get("recovery_code", "")
            self.setup_pwd_entry.delete(0, "end")
            self.setup_confirm_entry.delete(0, "end")
            self._render_recovery_code_display_view(rec_code)
        else:
            self.setup_feedback_label.configure(text=res.get("message", "Error creating password."))

    def _render_recovery_code_display_view(self, recovery_code: str):
        self._clear_card()

        ctk.CTkLabel(self.card, text="🔑", font=ctk.CTkFont(size=36)).pack(pady=(22, 2))

        ctk.CTkLabel(
            self.card,
            text="Save Your Recovery Code",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=THEME["text_primary"]
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            self.card,
            text=(
                "Save your recovery code somewhere secure.\n"
                "If you lose your password, Infinity AI cannot restore access without this code."
            ),
            font=ctk.CTkFont(size=12),
            text_color=THEME["text_secondary"],
            justify="center",
            wraplength=440
        ).pack(padx=24, pady=(0, 14))

        # Code box
        code_box = ctk.CTkFrame(self.card, fg_color=THEME["bg_panel"], border_color=THEME["border"], border_width=1, corner_radius=8)
        code_box.pack(fill="x", padx=44, pady=(0, 16))

        code_lbl = ctk.CTkLabel(
            code_box,
            text=recovery_code,
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color=THEME["accent"]
        )
        code_lbl.pack(padx=16, pady=12)

        # Buttons
        actions_row = ctk.CTkFrame(self.card, fg_color="transparent")
        actions_row.pack(fill="x", padx=44, pady=(0, 12))

        def copy_code():
            self.clipboard_clear()
            self.clipboard_append(recovery_code)
            copy_btn.configure(text="✔ Copied to Clipboard")
            self.after(2000, lambda: copy_btn.configure(text="📋 Copy Code"))

        def save_code_to_file():
            path = filedialog.asksaveasfilename(
                title="Save Recovery Code",
                defaultextension=".txt",
                initialfile="infinity-ai-recovery-code.txt",
                filetypes=[("Text file", "*.txt")]
            )
            if path:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(f"Infinity AI Workspace Recovery Code:\n{recovery_code}\n\nKeep this file in a safe, offline location.\n")
                    ToastNotification.show(self.master, "Recovery code saved to file.", icon="💾", level="success")
                except Exception:
                    pass

        copy_btn = ctk.CTkButton(
            actions_row,
            text="📋 Copy Code",
            font=ctk.CTkFont(size=11),
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_secondary"],
            height=32,
            command=copy_code
        )
        copy_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        save_btn = ctk.CTkButton(
            actions_row,
            text="💾 Save to File",
            font=ctk.CTkFont(size=11),
            fg_color=THEME["bg_panel"],
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_secondary"],
            height=32,
            command=save_code_to_file
        )
        save_btn.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # Continue Button
        ctk.CTkButton(
            self.card,
            text="✔ I've Saved It — Unlock Workspace",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=THEME["success"],
            hover_color=THEME["success_bg"],
            text_color="#FFFFFF",
            height=36,
            command=self._finish_initial_setup
        ).pack(fill="x", padx=44, pady=(0, 24))

    def _finish_initial_setup(self):
        set_password_authenticated(True)
        unlock_workspace()
        self.hide()
        ToastNotification.show(self.master, "Password created successfully. Workspace Unlocked.", icon="✨", level="success")
        if self.on_unlocked:
            self.on_unlocked()

    # =========================================================================
    # Offline Password Recovery (Zero USB required)
    # =========================================================================
    def _render_recovery_entry_view(self):
        self._clear_card()
        self._current_mode = "recovery"

        ctk.CTkLabel(self.card, text="🔑", font=ctk.CTkFont(size=36)).pack(pady=(22, 2))

        ctk.CTkLabel(
            self.card,
            text="Password Recovery",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=THEME["text_primary"]
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            self.card,
            text="Enter your offline recovery code to set a new workspace password.",
            font=ctk.CTkFont(size=12),
            text_color=THEME["text_secondary"],
            justify="center",
            wraplength=440
        ).pack(padx=24, pady=(0, 14))

        rec_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        rec_frame.pack(fill="x", padx=44, pady=(0, 10))

        # Recovery code
        ctk.CTkLabel(
            rec_frame,
            text="Recovery Code",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME["text_secondary"]
        ).pack(anchor="w", pady=(0, 3))

        self.rec_code_entry = ctk.CTkEntry(
            rec_frame,
            placeholder_text="e.g. A1B2C3D4-E5F67890",
            font=ctk.CTkFont(size=13),
            height=36,
            **ENTRY_COLORS
        )
        self.rec_code_entry.pack(fill="x", pady=(0, 8))

        # New Password
        ctk.CTkLabel(
            rec_frame,
            text="New Password",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME["text_secondary"]
        ).pack(anchor="w", pady=(0, 3))

        self.rec_new_pwd_entry = ctk.CTkEntry(
            rec_frame,
            placeholder_text="Enter new password (min 8 characters)",
            show="•",
            font=ctk.CTkFont(size=13),
            height=36,
            **ENTRY_COLORS
        )
        self.rec_new_pwd_entry.pack(fill="x", pady=(0, 8))

        # Confirm New Password
        ctk.CTkLabel(
            rec_frame,
            text="Confirm New Password",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME["text_secondary"]
        ).pack(anchor="w", pady=(0, 3))

        self.rec_confirm_pwd_entry = ctk.CTkEntry(
            rec_frame,
            placeholder_text="Confirm new password",
            show="•",
            font=ctk.CTkFont(size=13),
            height=36,
            **ENTRY_COLORS
        )
        self.rec_confirm_pwd_entry.pack(fill="x", pady=(0, 6))

        # Feedback
        self.rec_feedback_label = ctk.CTkLabel(
            rec_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=THEME["error"]
        )
        self.rec_feedback_label.pack(anchor="w", pady=(0, 6))

        # Actions
        btn_box = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_box.pack(fill="x", padx=44, pady=(0, 22))

        ctk.CTkButton(
            btn_box,
            text="Reset Password",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            text_color=THEME["accent_text"],
            height=36,
            command=self._submit_recovery_reset
        ).pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            btn_box,
            text="← Back to Password Login",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=THEME["bg_hover"],
            text_color=THEME["text_secondary"],
            height=28,
            command=lambda: self.update_state()
        ).pack(fill="x")

        self.rec_code_entry.focus_set()

    def _submit_recovery_reset(self):
        code = self.rec_code_entry.get().strip()
        pwd = self.rec_new_pwd_entry.get()
        confirm = self.rec_confirm_pwd_entry.get()

        if not code:
            self.rec_feedback_label.configure(text="Please enter your recovery code.")
            return

        if len(pwd) < 8:
            self.rec_feedback_label.configure(text="New password must be at least 8 characters.")
            return

        if pwd != confirm:
            self.rec_feedback_label.configure(text="Passwords do not match.")
            return

        res = password_auth_service.reset_password_with_recovery_code(code, pwd, confirm)
        if res.get("success"):
            new_code = res.get("new_recovery_code", "")
            self.rec_code_entry.delete(0, "end")
            self.rec_new_pwd_entry.delete(0, "end")
            self.rec_confirm_pwd_entry.delete(0, "end")
            self._render_recovery_code_display_view(new_code)
        else:
            self.rec_feedback_label.configure(text=res.get("message", "Invalid recovery code."))

    # =========================================================================
    # Compatibility & Lifecycle Helpers
    # =========================================================================
    def _render_no_usb_view(self, *args, **kwargs):
        self._render_password_unlock_view()

    def _render_unauthorized_usb_view(self, *args, **kwargs):
        self._render_password_unlock_view()

    def _render_device_setup_view(self, *args, **kwargs):
        self._render_password_unlock_view()

    def check_and_unlock(self):
        self.update_state()

    def _poll_usb_state(self):
        pass

    def _start_polling(self):
        pass

    def _stop_polling(self):
        pass

    def _handle_exit(self):
        if self.on_exit:
            self.on_exit()
        else:
            self.winfo_toplevel().destroy()

    def show(self, *args, **kwargs):
        """Displays overlay over the entire application."""
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self.update_state()

    def hide(self):
        """Hides overlay and clears sensitive field state."""
        self.place_forget()
        self._lockout_countdown_active = False
        if getattr(self, "_lockout_job", None):
            try:
                self.after_cancel(self._lockout_job)
            except Exception:
                pass
            self._lockout_job = None
        if hasattr(self, "unlock_pwd_entry"):
            try:
                self.unlock_pwd_entry.delete(0, "end")
            except Exception:
                pass

    @property
    def is_visible(self) -> bool:
        """Returns True if the lock overlay is currently placed/visible."""
        try:
            return bool(self.place_info())
        except Exception:
            return False

    def apply_theme(self, theme_name=None):
        """Refreshes overlay styling following theme changes."""
        try:
            self.configure(fg_color=THEME["bg_primary"])
            if hasattr(self, "card"):
                self.card.configure(fg_color=THEME["bg_secondary"], border_color=THEME["border"])
            self.update_state()
        except Exception:
            pass
