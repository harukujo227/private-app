"""Private Notes — tray notepad excluded from screen capture on Windows 11."""

from __future__ import annotations

import ctypes
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from PIL import Image
import pystray

WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011
GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080

user32 = ctypes.windll.user32
user32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
user32.SetWindowDisplayAffinity.restype = ctypes.c_bool
user32.GetParent.argtypes = [ctypes.c_void_p]
user32.GetParent.restype = ctypes.c_void_p
user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def toplevel_hwnd(widget: tk.Misc) -> int:
    widget.update_idletasks()
    hwnd = int(widget.winfo_id())
    parent = user32.GetParent(hwnd)
    return int(parent) if parent else hwnd


def hide_from_taskbar(hwnd: int) -> None:
    """Keep window off the taskbar; tray icon is the only shell presence."""
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def set_exclude_from_capture(hwnd: int, enabled: bool) -> bool:
    affinity = WDA_EXCLUDEFROMCAPTURE if enabled else WDA_NONE
    return bool(user32.SetWindowDisplayAffinity(hwnd, affinity))


def load_tray_image() -> Image.Image:
    for candidate in (resource_path("app.png"), resource_path("app.ico")):
        if candidate.exists():
            return Image.open(candidate).convert("RGBA")
    # Fallback if assets missing
    img = Image.new("RGBA", (64, 64), (15, 118, 110, 255))
    return img


class PrivateNotesApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Private Notes")
        self.geometry("640x480")
        self.minsize(360, 240)
        self.current_path: Path | None = None
        self.exclude_enabled = True
        self.always_on_top = True
        self.tray_icon: pystray.Icon | None = None
        self._quitting = False

        self.withdraw()  # start hidden; only tray icon shows
        icon_file = resource_path("app.ico")
        if icon_file.exists():
            try:
                self.iconbitmap(default=str(icon_file))
            except tk.TclError:
                pass
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        self.after(50, self._setup_window_chrome)
        self.after(100, self._start_tray)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=(8, 6))
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="New", command=self._new_file).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(toolbar, text="Open", command=self._open_file).pack(side=tk.LEFT, padx=(0, 12))

        self.exclude_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            toolbar,
            text="Hide from screen share",
            variable=self.exclude_var,
            command=self._toggle_exclude,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.topmost_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            toolbar,
            text="Always on top",
            variable=self.topmost_var,
            command=self._toggle_topmost,
        ).pack(side=tk.LEFT)

        text_frame = ttk.Frame(self, padding=(8, 0, 8, 8))
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            undo=True,
            font=("Consolas", 13),
            padx=10,
            pady=10,
            relief=tk.FLAT,
            borderwidth=0,
            cursor="arrow",
            insertwidth=1,
        )
        scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status = ttk.Label(self, text="Starting…", padding=(10, 6), anchor=tk.W)
        self.status.pack(fill=tk.X)

        self.bind("<Control-s>", lambda e: self._save_file())
        self.bind("<Control-o>", lambda e: self._open_file())
        self.bind("<Control-n>", lambda e: self._new_file())
        self.bind("<Escape>", lambda e: self._hide_to_tray())

    def _setup_window_chrome(self) -> None:
        if sys.platform == "win32":
            hwnd = toplevel_hwnd(self)
            hide_from_taskbar(hwnd)
        self.attributes("-topmost", True)
        self._apply_affinity()

    def _apply_affinity(self) -> None:
        if sys.platform != "win32":
            self.status.configure(text="Capture exclusion requires Windows.")
            return

        hwnd = toplevel_hwnd(self)
        hide_from_taskbar(hwnd)
        ok = set_exclude_from_capture(hwnd, self.exclude_enabled)
        if ok and self.exclude_enabled:
            self.status.configure(
                text="Protected — invisible on shared screens. Esc hides to tray."
            )
        elif ok:
            self.status.configure(text="Unprotected — can appear in screen shares.")
        else:
            self.status.configure(
                text="Could not set capture exclusion. Needs Windows 10 2004+ / Windows 11."
            )

    def _start_tray(self) -> None:
        image = load_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Show notes", self._tray_show, default=True),
            pystray.MenuItem("Hide notes", self._tray_hide),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._tray_quit),
        )
        self.tray_icon = pystray.Icon("PrivateNotes", image, "Private Notes", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_show(self, icon=None, item=None) -> None:
        # Show window and make it visible in screen shares
        self.after(0, lambda: self._set_screen_share_visible(True))

    def _tray_hide(self, icon=None, item=None) -> None:
        # Keep window open for you, but hide it from screen shares
        self.after(0, lambda: self._set_screen_share_visible(False))

    def _tray_quit(self, icon=None, item=None) -> None:
        self.after(0, self._quit_app)

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self.after(30, self._setup_window_chrome)

    def _set_screen_share_visible(self, visible: bool) -> None:
        """visible=True → appear in shares; visible=False → exclude from capture."""
        self.exclude_enabled = not visible
        self.exclude_var.set(self.exclude_enabled)
        self._show_window()
        self._apply_affinity()

    def _hide_to_tray(self) -> None:
        if self._quitting:
            return
        self.withdraw()

    def _quit_app(self) -> None:
        if not self._confirm_discard():
            return
        self._quitting = True
        if self.tray_icon is not None:
            self.tray_icon.stop()
        self.destroy()

    def _toggle_exclude(self) -> None:
        self.exclude_enabled = bool(self.exclude_var.get())
        self._apply_affinity()

    def _toggle_topmost(self) -> None:
        self.always_on_top = bool(self.topmost_var.get())
        self.attributes("-topmost", self.always_on_top)

    def _confirm_discard(self) -> bool:
        if not self.text.edit_modified():
            return True
        return messagebox.askyesno(
            "Discard changes?",
            "You have unsaved changes. Continue without saving?",
        )

    def _new_file(self) -> None:
        if not self._confirm_discard():
            return
        self.text.delete("1.0", tk.END)
        self.text.edit_modified(False)
        self.current_path = None
        self.title("Private Notes")

    def _open_file(self) -> None:
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Open",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        file_path = Path(path)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", file_path.read_text(encoding="utf-8"))
        self.text.edit_modified(False)
        self.current_path = file_path
        self.title(f"Private Notes — {file_path.name}")

    def _save_file(self) -> None:
        if self.current_path is None:
            self._save_file_as()
            return
        self.current_path.write_text(self.text.get("1.0", "end-1c"), encoding="utf-8")
        self.text.edit_modified(False)
        self.status.configure(text=f"Saved {self.current_path.name}")
        self.after(2000, self._apply_affinity)

    def _save_file_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save As",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        self.current_path = Path(path)
        self._save_file()
        self.title(f"Private Notes — {self.current_path.name}")


def main() -> None:
    if sys.platform != "win32":
        print("This app is intended for Windows 10/11.")
    app = PrivateNotesApp()
    app.mainloop()


if __name__ == "__main__":
    main()
