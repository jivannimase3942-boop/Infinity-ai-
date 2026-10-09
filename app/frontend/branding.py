"""Shared brand assets for the Infinity AI desktop frontend."""

from functools import lru_cache
from pathlib import Path

import customtkinter as ctk
from PIL import Image


def load_logo_image(size: tuple[int, int]) -> ctk.CTkImage:
    logo_path = Path(__file__).resolve().parent.parent / "assets" / "infinity_logo.png"
    with Image.open(logo_path) as logo:
        image = logo.convert("RGBA")
    return ctk.CTkImage(light_image=image, dark_image=image, size=size)
