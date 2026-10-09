"""
Infinity AI - Modern Monochrome Design System & Dual Theme Engine
Provides complete Light and Dark theme palettes following the startup-grade
black/white/grayscale design language.
"""

from typing import Dict, Any, List, Callable, Optional
import customtkinter as ctk

DARK_PALETTE: Dict[str, str] = {
    # Canvas & Layout
    "bg_primary": "#0D0D10",       # Main window & canvas
    "bg_sidebar": "#131316",       # Left navigation sidebar
    "bg_secondary": "#18181C",     # Panels & containers
    "bg_panel": "#202024",         # Cards, headers, elevated surfaces
    "bg_surface": "#26262B",       # Inputs, active cards
    "bg_hover": "#2E2E34",         # Hover states
    "border": "#2E2E34",           # Subtle borders
    "border_subtle": "#222226",    # Hairline dividers

    # Monochrome Accents & Buttons
    "accent": "#F4F4F6",           # Primary CTA background (white on dark)
    "accent_text": "#0D0D10",      # Text on primary CTA (dark on light)
    "accent_hover": "#E4E4E7",     # Primary CTA hover
    "accent_dim": "#26262B",       # Subtle selected state background

    # Typography
    "text_primary": "#F4F4F6",     # Main body text (near-white)
    "text_secondary": "#A1A1AA",   # Subheadings & metadata (neutral gray)
    "text_muted": "#71717A",       # Placeholders & subtle captions

    # Chat Bubbles
    "user_bubble": "#26262B",      # Compact user bubble background
    "user_bubble_border": "#323238",
    "ai_bubble": "transparent",    # Borderless, clean reading experience

    # Code & Tables
    "code_bg": "#161619",
    "code_border": "#27272A",
    "table_header_bg": "#202024",
    "table_border": "#2E2E34",

    # Status & Alerts (subtle accents only)
    "success": "#10B981",
    "success_bg": "#122A22",
    "warning": "#F59E0B",
    "warning_bg": "#2E2312",
    "error": "#EF4444",
    "error_hover": "#DC2626",
    "error_bg": "#321619",
    "link": "#60A5FA",
}

LIGHT_PALETTE: Dict[str, str] = {
    # Canvas & Layout
    "bg_primary": "#FAFAFA",       # Main window & canvas (clean near-white)
    "bg_sidebar": "#F4F4F6",       # Left navigation sidebar
    "bg_secondary": "#FFFFFF",     # Panels & containers
    "bg_panel": "#EAEAEF",         # Cards, headers, elevated surfaces
    "bg_surface": "#F4F4F6",       # Inputs, active cards
    "bg_hover": "#E4E4E8",         # Hover states
    "border": "#E4E4E8",           # Subtle light borders
    "border_subtle": "#ECECEF",    # Hairline dividers

    # Monochrome Accents & Buttons
    "accent": "#18181C",           # Primary CTA background (black on light)
    "accent_text": "#FFFFFF",      # Text on primary CTA
    "accent_hover": "#26262B",     # Primary CTA hover
    "accent_dim": "#EAEAEF",       # Subtle selected state background

    # Typography
    "text_primary": "#18181C",     # Main body text (near-black)
    "text_secondary": "#71717A",   # Subheadings & metadata (neutral gray)
    "text_muted": "#A1A1AA",       # Placeholders & subtle captions

    # Chat Bubbles
    "user_bubble": "#F4F4F6",      # Compact user bubble background
    "user_bubble_border": "#E4E4E8",
    "ai_bubble": "transparent",    # Borderless, clean reading experience

    # Code & Tables
    "code_bg": "#F4F4F6",
    "code_border": "#E4E4E8",
    "table_header_bg": "#EAEAEF",
    "table_border": "#E4E4E8",

    # Status & Alerts (subtle accents only)
    "success": "#059669",
    "success_bg": "#ECFDF5",
    "warning": "#D97706",
    "warning_bg": "#FFFBEB",
    "error": "#DC2626",
    "error_hover": "#B91C1C",
    "error_bg": "#FEF2F2",
    "link": "#2563EB",
}

# The active global THEME dictionary (modified in-place on theme switch)
THEME: Dict[str, str] = dict(DARK_PALETTE)

ENTRY_COLORS: Dict[str, str] = {}
TEXTBOX_COLORS: Dict[str, str] = {}
OPTION_MENU_COLORS: Dict[str, str] = {}
SCROLLABLE_COLORS: Dict[str, str] = {}
ENTRY_TEXT_COLORS: Dict[str, str] = {}

_CURRENT_THEME = "dark"
_THEME_LISTENERS: List[Callable[[str], None]] = []


def _refresh_derived_token_dicts():
    ENTRY_COLORS.clear()
    ENTRY_COLORS.update({
        "fg_color": THEME["bg_surface"],
        "border_color": THEME["border"],
        "text_color": THEME["text_primary"],
        "placeholder_text_color": THEME["text_muted"],
    })

    TEXTBOX_COLORS.clear()
    TEXTBOX_COLORS.update({
        "fg_color": THEME["bg_surface"],
        "border_color": THEME["border"],
        "text_color": THEME["text_primary"],
        "scrollbar_button_color": THEME["bg_panel"],
        "scrollbar_button_hover_color": THEME["bg_hover"],
    })

    OPTION_MENU_COLORS.clear()
    OPTION_MENU_COLORS.update({
        "fg_color": THEME["bg_panel"],
        "button_color": THEME["bg_surface"],
        "button_hover_color": THEME["accent_dim"],
        "dropdown_fg_color": THEME["bg_panel"],
        "dropdown_hover_color": THEME["accent_dim"],
        "dropdown_text_color": THEME["text_primary"],
        "text_color": THEME["text_primary"],
    })

    SCROLLABLE_COLORS.clear()
    SCROLLABLE_COLORS.update({
        "scrollbar_fg_color": THEME["bg_secondary"],
        "scrollbar_button_color": THEME["bg_panel"],
        "scrollbar_button_hover_color": THEME["bg_hover"],
    })

    ENTRY_TEXT_COLORS.clear()
    ENTRY_TEXT_COLORS.update({
        "text_color": THEME["text_primary"],
        "placeholder_text_color": THEME["text_muted"],
    })


def register_theme_listener(callback: Callable[[str], None]):
    """Registers a listener to be called when the theme switches."""
    if callback not in _THEME_LISTENERS:
        _THEME_LISTENERS.append(callback)


def unregister_theme_listener(callback: Callable[[str], None]):
    """Removes a registered theme listener."""
    if callback in _THEME_LISTENERS:
        _THEME_LISTENERS.remove(callback)


def get_current_theme() -> str:
    """Returns 'dark' or 'light'."""
    return _CURRENT_THEME


def set_theme(theme_name: str, notify: bool = True):
    """
    Switches theme globally, updates derived tokens, sets CustomTkinter appearance mode,
    persists the selection to SQLite settings, and notifies all registered listeners.
    """
    global _CURRENT_THEME
    normalized = "light" if theme_name.lower().startswith("light") else "dark"
    palette = LIGHT_PALETTE if normalized == "light" else DARK_PALETTE

    _CURRENT_THEME = normalized
    THEME.clear()
    THEME.update(palette)
    _refresh_derived_token_dicts()

    try:
        ctk.set_appearance_mode("Light" if normalized == "light" else "Dark")
    except Exception:
        pass

    # Persist in SQLite
    try:
        from backend.db import set_setting
        set_setting("theme", normalized)
    except Exception:
        pass

    if notify:
        for cb in list(_THEME_LISTENERS):
            try:
                cb(normalized)
            except Exception:
                pass


def toggle_theme():
    """Toggles between Dark and Light mode."""
    target = "light" if _CURRENT_THEME == "dark" else "dark"
    set_theme(target)
    return target


def initialize_saved_theme():
    """Loads and applies the saved theme from database or defaults to dark."""
    saved = "dark"
    try:
        from backend.db import get_setting
        val = get_setting("theme")
        if val in ["dark", "light"]:
            saved = val
    except Exception:
        pass
    set_theme(saved, notify=False)


# Initialize derived tokens on import
_refresh_derived_token_dicts()
try:
    initialize_saved_theme()
except Exception:
    pass
