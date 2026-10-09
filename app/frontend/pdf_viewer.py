import bisect
import threading
from pathlib import Path
import tkinter as tk

import customtkinter as ctk

from frontend.theme import ENTRY_COLORS, THEME, register_theme_listener
import pymupdf
from PIL import Image, ImageTk


class PDFViewer(ctk.CTkFrame):
    """Lightweight PDF viewer with virtual/lazy page rendering.

    Only pages near the viewport are rendered. This avoids creating hundreds of
    Tk widgets for a 300-500 page PDF and keeps scrolling responsive.
    """

    def __init__(self, master, ask_ai_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.ask_ai_callback = ask_ai_callback
        self.doc = None
        self.path = None
        self.page = 1
        self.zoom = 1.0
        self._pages = []
        self._offsets = []
        self._rendered = {}
        self._rendering = set()
        self._scroll_job = None
        self._layout_job = None
        self._generation = 0
        self._build()
        register_theme_listener(self.apply_theme)

    def _build(self):
        self.configure(fg_color=THEME["bg_secondary"], corner_radius=0)

        self.bar = ctk.CTkFrame(self, height=46, fg_color=THEME["bg_panel"], corner_radius=0)
        self.bar.pack(fill="x")
        bar = self.bar

        self.bar_btns = []
        b_zout = ctk.CTkButton(bar, text="−", width=28, height=28, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], text_color=THEME["text_primary"], command=lambda: self.zoom_by(-0.1))
        b_zout.pack(side="left", padx=(10, 4), pady=8)
        self.bar_btns.append(b_zout)

        self.zoom_label = ctk.CTkLabel(bar, text="100%", width=56, font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME["text_primary"])
        self.zoom_label.pack(side="left", padx=4)

        b_zin = ctk.CTkButton(bar, text="+", width=28, height=28, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], text_color=THEME["text_primary"], command=lambda: self.zoom_by(0.1))
        b_zin.pack(side="left", padx=(4, 10), pady=8)
        self.bar_btns.append(b_zin)

        b_fit = ctk.CTkButton(bar, text="Fit Width", width=90, height=28, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], text_color=THEME["text_primary"], command=self.fit)
        b_fit.pack(side="left", padx=8, pady=8)
        self.bar_btns.append(b_fit)

        b_prev = ctk.CTkButton(bar, text="◀", width=28, height=28, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], text_color=THEME["text_primary"], command=lambda: self.jump(self.page - 1))
        b_prev.pack(side="left", padx=(12, 4), pady=8)
        self.bar_btns.append(b_prev)

        self.entry = ctk.CTkEntry(bar, width=62, border_width=1, **ENTRY_COLORS)
        self.entry.insert(0, "1")
        self.entry.pack(side="left", padx=4, pady=8)
        self.entry.bind("<Return>", self._jump_from_entry)

        self.total = ctk.CTkLabel(bar, text="/ 0", width=48, font=ctk.CTkFont(size=11), text_color=THEME["text_secondary"])
        self.total.pack(side="left", padx=(2, 8))

        b_next = ctk.CTkButton(bar, text="▶", width=28, height=28, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], text_color=THEME["text_primary"], command=lambda: self.jump(self.page + 1))
        b_next.pack(side="left", padx=(4, 12), pady=8)
        self.bar_btns.append(b_next)

        self.ask_page_btn = ctk.CTkButton(bar, text="Ask Page", width=82, height=28, fg_color=THEME["bg_panel"], hover_color=THEME["bg_hover"], text_color=THEME["text_primary"], command=self.ask_current_page, state="disabled")
        self.ask_page_btn.pack(side="right", padx=(8, 10), pady=8)

        # Document Intelligence Action Strip
        self.intel_bar = ctk.CTkFrame(self, height=32, fg_color=THEME["bg_panel"], corner_radius=0)
        self.intel_bar.pack(fill="x")
        intel_bar = self.intel_bar

        self.action_btns = []
        intel_actions = [
            ("Explain 💡", "Explain the key concepts on this page in clear, intuitive terms with an example:"),
            ("Quiz 📝", "Generate 5 multiple choice questions with explanations based on this page:"),
            ("Flashcards 🗂️", "Create active recall flashcards with Question, Answer, and Memory Anchor for this page:"),
            ("Notes 📓", "Generate comprehensive, structured revision notes for this page:"),
            ("References 🔎", "Identify and extract all citations, formulas, and references from this page:"),
        ]

        for label, prompt_prefix in intel_actions:
            b = ctk.CTkButton(
                intel_bar,
                text=label,
                height=24,
                font=ctk.CTkFont(size=10),
                fg_color=THEME["bg_panel"],
                hover_color=THEME["bg_hover"],
                text_color=THEME["text_primary"],
                command=lambda p=prompt_prefix: self._run_intel_action(p),
                state="disabled"
            )
            b.pack(side="left", padx=3, pady=4)
            self.action_btns.append(b)

        self.holder = ctk.CTkFrame(self, fg_color=THEME["bg_secondary"], corner_radius=0)
        self.holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(self.holder, background=THEME["bg_secondary"], highlightthickness=0, bd=0)
        self.vbar = ctk.CTkScrollbar(
            self.holder,
            orientation="vertical",
            fg_color=THEME["bg_secondary"],
            button_color=THEME["bg_panel"],
            button_hover_color=THEME["bg_hover"],
            command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vbar.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self._schedule_layout)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._on_wheel(e, 1))
        self.canvas.bind("<Button-5>", lambda e: self._on_wheel(e, -1))
        self.canvas.bind("<ButtonRelease-1>", lambda e: self._schedule_render())

    def _jump_from_entry(self, _event=None):
        try:
            self.jump(int(self.entry.get()))
        except ValueError:
            self.entry.delete(0, "end")
            self.entry.insert(0, str(self.page))

    def _update_zoom_label(self):
        self.zoom_label.configure(text=f"{int(round(self.zoom * 100))}%")

    def _on_wheel(self, event, direction=None):
        if direction is None:
            direction = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(direction * 4, "units")
        self._schedule_render()
        return "break"

    def load_pdf(self, path):
        self._generation += 1
        self._rendering.clear()
        self._rendered.clear()
        if self.doc:
            try:
                self.doc.close()
            except Exception:
                pass
        self.doc = pymupdf.open(path)
        self.path = str(Path(path).resolve())
        self.page = 1
        self.total.configure(text=f"/ {len(self.doc)}")
        self.entry.delete(0, "end")
        self.entry.insert(0, "1")
        self.ask_page_btn.configure(state="normal")
        for b in self.action_btns:
            b.configure(state="normal")
        self._update_zoom_label()
        self._rebuild_layout()
        self.after(80, self.fit)

    def _rebuild_layout(self):
        if not self.doc:
            return
        self.canvas.delete("all")
        self._pages = []
        self._offsets = []
        width = max(450, self.canvas.winfo_width() - 50)
        y = 20
        gap = 24
        for i, page in enumerate(self.doc):
            rect = page.rect
            display_w = max(300, rect.width * self.zoom)
            if self.zoom <= 1.0 and display_w > width:
                display_w = width
            display_h = display_w * rect.height / max(1, rect.width)
            h = max(80, display_h)
            self._offsets.append(y)
            self._pages.append({"index": i, "x": 25, "y": y, "w": display_w, "h": h, "image_id": None})
            self.canvas.create_rectangle(25, y, 25 + display_w, y + h, fill=THEME["bg_panel"], outline=THEME["border"], tags=(f"page_{i}",))
            self.canvas.create_text(35, y + 14, text=f"Page {i + 1}", anchor="nw", fill=THEME["text_secondary"], tags=(f"label_{i}",))
            y += h + gap
        self.canvas.configure(scrollregion=(0, 0, max(width + 50, 1000), y + 20))
        self._schedule_render()

    def _schedule_layout(self, _event=None):
        if self._layout_job:
            self.after_cancel(self._layout_job)
        self._layout_job = self.after(100, self._rebuild_layout)

    def _schedule_render(self):
        if self._scroll_job:
            self.after_cancel(self._scroll_job)
        self._scroll_job = self.after(70, self._render_visible)

    def _visible_indices(self):
        if not self._pages:
            return []
        top = self.canvas.canvasy(0)
        bottom = top + max(1, self.canvas.winfo_height())
        center = (top + bottom) / 2
        pos = bisect.bisect_right(self._offsets, center) - 1
        pos = max(0, min(len(self._pages) - 1, pos))
        return range(max(0, pos - 1), min(len(self._pages), pos + 2))

    def _render_visible(self):
        if not self.doc or not self.path:
            return
        indices = list(self._visible_indices())
        if indices:
            current_page = indices[0] + 1
            self.page = current_page
            self.entry.delete(0, "end")
            self.entry.insert(0, str(current_page))
        generation = self._generation
        for index in indices:
            if index in self._rendered or index in self._rendering:
                continue
            self._rendering.add(index)
            geom = self._pages[index].copy()
            threading.Thread(target=self._render_worker, args=(index, geom, generation), daemon=True).start()

    def _render_worker(self, index, geom, generation):
        try:
            with pymupdf.open(self.path) as doc:
                page = doc[index]
                target_w = max(300, int(geom["w"]))
                scale = target_w / max(1, page.rect.width)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                data = (pix.width, pix.height, pix.samples)
            try:
                if self.winfo_exists():
                    self.after(0, lambda d=data: self._apply_render(index, d, generation))
            except Exception:
                pass
        except Exception as exc:
            try:
                if self.winfo_exists():
                    self.after(0, lambda: self._render_error(index, str(exc), generation))
            except Exception:
                pass

    def _apply_render(self, index, data, generation):
        self._rendering.discard(index)
        if generation != self._generation or not self._pages:
            return
        try:
            w, h, samples = data
            image = Image.frombytes("RGB", (w, h), samples)
            photo = ImageTk.PhotoImage(image)
            # Keep the image alive on the page record.
            page_info = self._pages[index]
            page_info["photo"] = photo
            if page_info.get("image_id"):
                self.canvas.delete(page_info["image_id"])
            page_info["image_id"] = self.canvas.create_image(page_info["x"], page_info["y"], anchor="nw", image=photo, tags=(f"page_image_{index}",))
            self._rendered[index] = True
        except Exception as exc:
            self._render_error(index, str(exc), generation)

    def _render_error(self, index, message, generation):
        self._rendering.discard(index)
        if generation != self._generation or index >= len(self._pages):
            return
        p = self._pages[index]
        self.canvas.create_text(p["x"] + 10, p["y"] + 35, text=f"Unable to render page: {message}", anchor="nw", fill=THEME["error"])

    def fit(self):
        if not self.doc:
            return
        width = max(400, self.canvas.winfo_width() - 50)
        first = self.doc[0].rect
        self.zoom = min(1.8, max(0.35, width / max(1, first.width)))
        self._update_zoom_label()
        self._generation += 1
        self._rendered.clear()
        self._rendering.clear()
        self._rebuild_layout()

    def zoom_by(self, delta):
        if not self.doc:
            return
        self.zoom = min(2.0, max(0.35, self.zoom + delta))
        self._update_zoom_label()
        current = self.page
        self._generation += 1
        self._rendered.clear()
        self._rendering.clear()
        self._rebuild_layout()
        self.after(80, lambda: self.jump(current))

    def jump(self, page_number):
        if not self.doc:
            return
        n = max(1, min(len(self.doc), int(page_number)))
        self.page = n
        self.entry.delete(0, "end")
        self.entry.insert(0, str(n))
        if self._offsets:
            total = max(1, self.canvas.bbox("all")[3] - self.canvas.winfo_height())
            target = max(0, self._offsets[n - 1] - 20)
            self.canvas.yview_moveto(min(1, target / total))
        self._schedule_render()

    def ask_current_page(self):
        if not self.doc or not self.ask_ai_callback:
            return
        try:
            page = self.doc[self.page - 1]
            text = page.get_text("text", sort=True).strip()
            if not text or len(text) < 20:
                try:
                    from backend.pdf_processor import _ocr
                    ocr_t = _ocr(page)
                    if len(ocr_t) > len(text):
                        text = ocr_t
                except Exception:
                    pass
        except Exception:
            text = ""
        if text:
            self.ask_ai_callback(text, self.page)

    def _run_intel_action(self, prompt_prefix: str):
        if not self.doc or not self.ask_ai_callback:
            return
        try:
            page = self.doc[self.page - 1]
            text = page.get_text("text", sort=True).strip()
            if not text or len(text) < 20:
                try:
                    from backend.pdf_processor import _ocr
                    ocr_t = _ocr(page)
                    if len(ocr_t) > len(text):
                        text = ocr_t
                except Exception:
                    pass
        except Exception:
            text = ""
        if text:
            doc_name = Path(self.path).name if self.path else "Document"
            full_msg = f"{prompt_prefix}\n\n[Excerpt from '{doc_name}' - Page {self.page}]:\n{text}"
            self.ask_ai_callback(full_msg, self.page)

    def close(self):
        self._generation += 1
        self.ask_page_btn.configure(state="disabled")
        for b in self.action_btns:
            b.configure(state="disabled")
        if self.doc:
            try:
                self.doc.close()
            except Exception:
                pass
            self.doc = None

    def apply_theme(self, theme_name=None):
        """Refreshes PDF viewer controls, canvas background, scrollbar, and layout to match current theme."""
        try:
            self.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "holder"):
                self.holder.configure(fg_color=THEME["bg_secondary"])
            if hasattr(self, "canvas"):
                self.canvas.configure(background=THEME["bg_secondary"])
            if hasattr(self, "vbar"):
                self.vbar.configure(
                    fg_color=THEME["bg_secondary"],
                    button_color=THEME["bg_panel"],
                    button_hover_color=THEME["bg_hover"]
                )
            if hasattr(self, "bar"):
                self.bar.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "intel_bar"):
                self.intel_bar.configure(fg_color=THEME["bg_panel"])
            if hasattr(self, "zoom_label"):
                self.zoom_label.configure(text_color=THEME["text_primary"])
            if hasattr(self, "total"):
                self.total.configure(text_color=THEME["text_secondary"])
            if hasattr(self, "entry"):
                self.entry.configure(
                    fg_color=THEME["bg_surface"],
                    border_color=THEME["border"],
                    text_color=THEME["text_primary"]
                )
            if hasattr(self, "ask_page_btn"):
                self.ask_page_btn.configure(
                    fg_color=THEME["bg_panel"],
                    hover_color=THEME["bg_hover"],
                    text_color=THEME["text_primary"]
                )
            for b in getattr(self, "bar_btns", []):
                try:
                    b.configure(
                        fg_color=THEME["bg_panel"],
                        hover_color=THEME["bg_hover"],
                        text_color=THEME["text_primary"]
                    )
                except Exception:
                    pass
            for b in getattr(self, "action_btns", []):
                try:
                    b.configure(
                        fg_color=THEME["bg_panel"],
                        hover_color=THEME["bg_hover"],
                        text_color=THEME["text_primary"]
                    )
                except Exception:
                    pass
            if self.doc:
                self._rebuild_layout()
        except Exception:
            pass

