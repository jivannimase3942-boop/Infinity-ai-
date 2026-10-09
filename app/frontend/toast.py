"""
Infinity AI - Non-Blocking Toast Notification Subsystem
Provides subtle, non-modal status banners for events like:
- Workspace unlocked / locked
- Document indexed
- Artifact saved / exported
- Model switched
Does not interrupt the user's flow or show intrusive modal dialogs.
"""

from typing import Optional
import customtkinter as ctk

from frontend.theme import THEME


class ToastNotification:
    _active_toast: Optional[ctk.CTkFrame] = None
    _dismiss_job = None

    @classmethod
    def show(
        cls,
        parent,
        message: str,
        icon: str = "ℹ️",
        duration_ms: int = 2800,
        level: str = "info"  # info, success, warning, error
    ):
        """Displays a floating toast banner at the top-right of the window."""
        # Dismiss any active toast
        if cls._active_toast:
            try:
                if cls._dismiss_job and hasattr(parent, "after_cancel"):
                    parent.after_cancel(cls._dismiss_job)
                cls._active_toast.destroy()
            except Exception:
                pass
            cls._active_toast = None

        bg_colors = {
            "info": THEME["bg_panel"],
            "success": THEME["success_bg"],
            "warning": THEME["warning_bg"],
            "error": THEME["error_bg"]
        }
        border_colors = {
            "info": THEME["accent"],
            "success": THEME["success"],
            "warning": THEME["warning"],
            "error": THEME["error"]
        }

        fg = bg_colors.get(level, THEME["bg_panel"])
        border = border_colors.get(level, THEME["accent"])

        toast = ctk.CTkFrame(
            parent,
            fg_color=fg,
            border_color=border,
            border_width=1,
            corner_radius=8,
            height=36
        )
        cls._active_toast = toast

        content_box = ctk.CTkFrame(toast, fg_color="transparent")
        content_box.pack(padx=14, pady=8, fill="both")

        ctk.CTkLabel(
            content_box,
            text=f"{icon}  {message}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=THEME["text_primary"]
        ).pack(side="left")

        # Position at top-right
        toast.place(relx=0.98, rely=0.08, anchor="ne")

        def dismiss():
            if cls._active_toast == toast:
                try:
                    toast.destroy()
                except Exception:
                    pass
                cls._active_toast = None

        cls._dismiss_job = parent.after(duration_ms, dismiss)
