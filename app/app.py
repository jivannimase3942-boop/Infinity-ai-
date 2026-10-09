import customtkinter as ctk
from frontend.theme import get_current_theme
from frontend.ui import DocumentAssistant


def main():
    saved_mode = "Light" if get_current_theme() == "light" else "Dark"
    ctk.set_appearance_mode(saved_mode)
    app = DocumentAssistant()
    app.protocol('WM_DELETE_WINDOW', app.on_close)
    app.mainloop()


if __name__ == '__main__':
    main()
