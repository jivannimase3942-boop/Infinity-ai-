"""
Infinity AI - Modern Desktop Markdown Renderer
Renders markdown syntax visually using styled Tkinter Text widgets with:
- H1, H2, H3 headers with hierarchy and distinct styling
- Bold, Italic, and Bold-Italic inline styling
- Monospace inline code (`code`) with subtle neutral badges
- Monospace multi-line code blocks (```lang ... ```) with distinct container styling
- Bullet lists (-, *) with clean bullet points (•) and proper hanging indentation
- Numbered lists (1., 2.) with numbers and proper hanging indentation
- Blockquotes (>) with indented italicized styling
- Horizontal rules (---) with clean divider characters
- Markdown tables cleanly formatted and aligned across themes
- Dynamic height calculation to eliminate clipping and internal scrollbars
- Progressive token streaming support
- Dual-theme (Light & Dark) responsive styling
"""

import re
import tkinter as tk
from typing import Optional, List, Dict, Any
import customtkinter as ctk

from frontend.theme import THEME, register_theme_listener, get_current_theme


class RichMarkdownText(tk.Text):
    """
    A high-performance rich text renderer for Markdown.
    Supports inline formatting, block formatting, dynamic sizing, and user text selection.
    """
    def __init__(
        self,
        master,
        bg_color: Optional[str] = None,
        fg_color: Optional[str] = None,
        base_size: int = 13,
        max_width: int = 680,
        **kwargs
    ):
        is_light = get_current_theme() == "light"
        bg = bg_color or THEME.get("ai_bubble", "transparent")
        if bg == "transparent":
            bg = THEME.get("bg_secondary", "#FFFFFF" if is_light else "#18181C")
        fg = fg_color or THEME.get("text_primary", "#18181C" if is_light else "#F4F4F6")

        super().__init__(
            master,
            wrap="word",
            bg=bg,
            fg=fg,
            bd=0,
            highlightthickness=0,
            relief="flat",
            cursor="xterm",
            font=("Segoe UI", base_size),
            selectbackground=THEME.get("accent_dim", "#26262B"),
            selectforeground=fg,
            **kwargs
        )
        self.base_size = base_size
        self.bg_color = bg
        self.fg_color = fg
        self._raw_markdown = ""
        self._setup_tags()

        # Prevent keyboard typing while allowing mouse selection and copying
        self.bind("<KeyPress>", self._block_typing)
        self.bind("<Control-c>", self._allow_copy)
        self.bind("<Control-C>", self._allow_copy)

    def _block_typing(self, event):
        if event.keysym in ["Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"]:
            return None
        if event.state & 0x0004 and event.keysym.lower() == "c":  # Ctrl+C
            return None
        return "break"

    def _allow_copy(self, event):
        return None

    def _setup_tags(self):
        s = self.base_size
        text_primary = THEME.get("text_primary", "#F4F4F6")
        text_secondary = THEME.get("text_secondary", "#A1A1AA")
        border = THEME.get("border", "#2E2E34")
        code_bg = THEME.get("code_bg", THEME.get("bg_panel", "#161619"))
        table_hdr_bg = THEME.get("table_header_bg", THEME.get("bg_panel", "#202024"))
        table_bdr = THEME.get("table_border", "#2E2E34")

        # Headings: clear hierarchy, professional line spacing
        self.tag_configure("h1", font=("Segoe UI", s + 5, "bold"), foreground=text_primary, spacing1=14, spacing3=6)
        self.tag_configure("h2", font=("Segoe UI", s + 3, "bold"), foreground=text_primary, spacing1=12, spacing3=5)
        self.tag_configure("h3", font=("Segoe UI", s + 1, "bold"), foreground=text_secondary, spacing1=9, spacing3=4)

        # Inline typography: comfortable body readability
        self.tag_configure("bold", font=("Segoe UI", s, "bold"), foreground=text_primary)
        self.tag_configure("italic", font=("Segoe UI", s, "italic"), foreground=text_secondary)
        self.tag_configure("bold_italic", font=("Segoe UI", s, "bold italic"), foreground=text_primary)
        self.tag_configure("normal", font=("Segoe UI", s), foreground=text_primary, spacing1=3, spacing2=2, spacing3=3)

        # Inline code
        self.tag_configure(
            "inline_code",
            font=("Consolas", max(10, s - 1)),
            foreground=text_primary,
            background=code_bg
        )

        # Multi-line Code Block
        self.tag_configure(
            "code_block",
            font=("Consolas", max(10, s - 1)),
            foreground=text_primary,
            background=code_bg,
            lmargin1=16,
            lmargin2=16,
            rmargin=16,
            spacing1=6,
            spacing2=2,
            spacing3=6
        )

        # Lists with hanging indentation
        self.tag_configure(
            "bullet",
            font=("Segoe UI", s),
            foreground=text_primary,
            lmargin1=16,
            lmargin2=36,
            spacing1=3,
            spacing2=1,
            spacing3=3
        )
        self.tag_configure(
            "numlist",
            font=("Segoe UI", s),
            foreground=text_primary,
            lmargin1=16,
            lmargin2=38,
            spacing1=3,
            spacing2=1,
            spacing3=3
        )

        # Blockquote
        self.tag_configure(
            "quote",
            font=("Segoe UI", s, "italic"),
            foreground=text_secondary,
            lmargin1=24,
            lmargin2=24,
            spacing1=5,
            spacing2=1,
            spacing3=5
        )

        # Divider / Horizontal rule
        self.tag_configure(
            "hr",
            font=("Segoe UI", 9),
            foreground=border,
            spacing1=10,
            spacing3=10
        )

        # Table tags
        self.tag_configure(
            "table_header",
            font=("Consolas", max(10, s - 1), "bold"),
            foreground=text_primary,
            background=table_hdr_bg,
            lmargin1=12,
            lmargin2=12,
            spacing1=5,
            spacing3=4
        )
        self.tag_configure(
            "table_row",
            font=("Consolas", max(10, s - 1)),
            foreground=text_primary,
            background=code_bg,
            lmargin1=12,
            lmargin2=12,
            spacing1=3,
        )

    def update_theme(self, new_bg: Optional[str] = None, new_fg: Optional[str] = None):
        """Refreshes widget background, foreground, and tags when theme changes."""
        is_light = get_current_theme() == "light"
        bg = new_bg or THEME.get("ai_bubble", "transparent")
        if bg == "transparent":
            bg = THEME.get("bg_secondary", "#FFFFFF" if is_light else "#18181C")
        fg = new_fg or THEME.get("text_primary", "#18181C" if is_light else "#F4F4F6")

        self.bg_color = bg
        self.fg_color = fg
        self.configure(
            bg=bg,
            fg=fg,
            selectbackground=THEME.get("accent_dim", "#26262B"),
            selectforeground=fg
        )
        self._setup_tags()
        if self._raw_markdown:
            self.render_markdown(self._raw_markdown)

    def render_markdown(self, markdown_text: str):
        """Completely renders the given markdown text with visual formatting."""
        self._raw_markdown = markdown_text or ""
        self.configure(state="normal")
        self.delete("1.0", "end")

        if not self._raw_markdown.strip():
            self.configure(height=1, state="disabled")
            return

        lines = self._raw_markdown.split("\n")
        in_code_block = False
        code_block_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 1. Code Block fenced with ```
            if stripped.startswith("```"):
                if in_code_block:
                    # Closing code block
                    block_content = "\n".join(code_block_lines) + "\n"
                    self.insert("end", block_content, "code_block")
                    code_block_lines = []
                    in_code_block = False
                else:
                    # Opening code block
                    in_code_block = True
                    code_block_lines = []
                i += 1
                continue

            if in_code_block:
                code_block_lines.append(line)
                i += 1
                continue

            # 2. Horizontal Rule (---, ***, ___)
            if re.match(r"^(\-{3,}|\*{3,}|_{3,})$", stripped):
                self.insert("end", "──────────────────────────────────────────────────\n", "hr")
                i += 1
                continue

            # 3. Tables (| col | col |)
            if stripped.startswith("|") and stripped.endswith("|"):
                # Table divider check (e.g. |---|---|)
                if re.match(r"^\|(?:\s*:?-+:?\s*\|)+$", stripped):
                    i += 1
                    continue
                # Determine if it is a header row (first row or followed by divider)
                is_header = (i + 1 < len(lines) and re.match(r"^\|(?:\s*:?-+:?\s*\|)+$", lines[i + 1].strip()))
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                row_text = "  │  ".join(cells) + "\n"
                tag = "table_header" if is_header else "table_row"
                self.insert("end", row_text, tag)
                i += 1
                continue

            # 4. Headings (#, ##, ###)
            if line.startswith("# "):
                self._insert_styled_line(line[2:].strip() + "\n", "h1")
            elif line.startswith("## "):
                self._insert_styled_line(line[3:].strip() + "\n", "h2")
            elif line.startswith("### "):
                self._insert_styled_line(line[4:].strip() + "\n", "h3")
            elif line.startswith("#### "):
                self._insert_styled_line(line[5:].strip() + "\n", "h3")

            # 5. Blockquote (> quote)
            elif line.startswith("> "):
                self._insert_inline_spans(line[2:].strip() + "\n", extra_tag="quote")

            # 6. Unordered lists (-, *, +)
            elif re.match(r"^\s*[\*\-\+]\s+", line):
                content = re.sub(r"^\s*[\*\-\+]\s+", "•  ", line)
                self._insert_inline_spans(content + "\n", extra_tag="bullet")

            # 7. Ordered lists (1., 2.)
            elif re.match(r"^\s*\d+[\.\)]\s+", line):
                m = re.match(r"^(\s*\d+[\.\)]\s+)(.*)", line)
                if m:
                    num_prefix = m.group(1)
                    rest = m.group(2)
                    self._insert_inline_spans(f"{num_prefix}{rest}\n", extra_tag="numlist")
                else:
                    self._insert_inline_spans(line + "\n", extra_tag="normal")

            # 8. Blank line
            elif not stripped:
                self.insert("end", "\n", "normal")

            # 9. Regular text paragraph
            else:
                self._insert_inline_spans(line + "\n", extra_tag="normal")

            i += 1

        if in_code_block and code_block_lines:
            self.insert("end", "\n".join(code_block_lines) + "\n", "code_block")

        self.configure(state="disabled")
        self.update_dynamic_height()

    def _insert_styled_line(self, text: str, style_tag: str):
        """Cleans asterisks from heading text and inserts with heading style."""
        clean = text.replace("**", "").replace("__", "")
        self.insert("end", clean, style_tag)

    def _insert_inline_spans(self, text: str, extra_tag: str = "normal"):
        """
        Parses inline markdown tokens: `code`, ***bold_italic***, **bold**, *italic*.
        Inserts each segment with appropriate tags.
        """
        pattern = re.compile(
            r"(`(?P<code>[^`]+)`)|"
            r"(\*\*\*(?P<bold_italic>[^\*]+)\*\*\*)|"
            r"(\*\*(?P<bold>[^\*]+)\*\*)|"
            r"(\*(?P<italic>[^\*]+)\*)|"
            r"(__(?P<bold_u>[^_]+)__)|"
            r"(_(?P<italic_u>[^_]+)_)"
        )

        pos = 0
        for match in pattern.finditer(text):
            start, end = match.span()
            if start > pos:
                self.insert("end", text[pos:start], (extra_tag,))

            groups = match.groupdict()
            if groups.get("code"):
                self.insert("end", f" {groups['code']} ", ("inline_code",))
            elif groups.get("bold_italic"):
                self.insert("end", groups["bold_italic"], ("bold_italic", extra_tag))
            elif groups.get("bold") or groups.get("bold_u"):
                b_text = groups.get("bold") or groups.get("bold_u")
                self.insert("end", b_text, ("bold", extra_tag))
            elif groups.get("italic") or groups.get("italic_u"):
                i_text = groups.get("italic") or groups.get("italic_u")
                self.insert("end", i_text, ("italic", extra_tag))
            pos = end

        if pos < len(text):
            self.insert("end", text[pos:], (extra_tag,))

    def update_dynamic_height(self):
        """Computes true display line height and refreshes canvas scrollregion smoothly."""
        try:
            dl = self.count("1.0", "end", "displaylines")
            lines = dl[0] if dl else int(self.index("end-1c").split(".")[0])
            target_h = max(1, lines)
            if self.cget("height") != target_h:
                self.configure(height=target_h)

            parent = self.master
            while parent:
                canvas = getattr(parent, "_parent_canvas", None)
                if canvas:
                    canvas.configure(scrollregion=canvas.bbox("all"))
                    break
                parent = getattr(parent, "master", None)
        except Exception:
            pass

    def get_text(self) -> str:
        return self._raw_markdown


class StreamingMarkdownBubble(ctk.CTkFrame):
    """
    Container frame embedding RichMarkdownText for both streaming and static AI responses.
    """
    def __init__(self, master, bg_color: Optional[str] = None, fg_color: Optional[str] = None, **kwargs):
        bg = bg_color or THEME.get("ai_bubble", "transparent")
        super().__init__(master, fg_color=bg, corner_radius=0, **kwargs)
        self.md_view = RichMarkdownText(self, bg_color=bg, fg_color=fg_color)
        self.md_view.pack(fill="x", padx=4, pady=4)

    def append(self, text: str):
        new_content = self.md_view.get_text() + text
        self.md_view.render_markdown(new_content)

    def set_text(self, text: str):
        self.md_view.render_markdown(text)

    def get_text(self) -> str:
        return self.md_view.get_text()

    def update_theme(self):
        self.configure(fg_color=THEME.get("ai_bubble", "transparent"))
        self.md_view.update_theme()


class MarkdownTextbox(ctk.CTkTextbox):
    """Backward-compatible wrapper for legacy imports."""
    def set_markdown(self, text: str):
        self.delete("1.0", "end")
        self.insert("1.0", text)
