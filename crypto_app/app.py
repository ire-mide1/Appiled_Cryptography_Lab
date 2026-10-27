"""Entry point: python app.py"""
import tkinter as tk

import ui


def main():
    try:  # crisp text on high-DPI Windows displays
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass
    root = tk.Tk()
    ui.App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
