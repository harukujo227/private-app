"""Protect Other Apps — exclude selected windows from screen capture on Windows."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import json
import struct
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image
import pystray

WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_CREATE_THREAD = 0x0002
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_INJECT_ACCESS = (
    PROCESS_CREATE_THREAD
    | PROCESS_VM_OPERATION
    | PROCESS_VM_WRITE
    | PROCESS_VM_READ
    | PROCESS_QUERY_INFORMATION
)

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_EXECUTE_READWRITE = 0x40
GA_ROOT = 2

# Toggle button colors
COLOR_PROTECT_BG = "#2563eb"  # blue — action: protect (currently visible)
COLOR_PROTECT_FG = "#ffffff"
COLOR_UNPROTECT_BG = "#e5e7eb"  # gray — action: unprotect (currently protected)
COLOR_UNPROTECT_FG = "#111827"
COLOR_DISABLED_BG = "#f3f4f6"
COLOR_DISABLED_FG = "#9ca3af"

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
user32.GetWindowDisplayAffinity.argtypes = [wintypes.HWND, ctypes.POINTER(ctypes.c_uint)]
user32.GetWindowDisplayAffinity.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetAncestor.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.VirtualAllocEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_size_t,
    wintypes.DWORD,
    wintypes.DWORD,
]
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.WriteProcessMemory.restype = wintypes.BOOL
kernel32.CreateRemoteThread.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.CreateRemoteThread.restype = wintypes.HANDLE
kernel32.VirtualFreeEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_size_t,
    wintypes.DWORD,
]
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.GetExitCodeThread.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetCurrentProcessId.restype = wintypes.DWORD
kernel32.GetCurrentProcess.restype = ctypes.c_void_p
kernel32.GetCurrentProcess.argtypes = []

advapi32 = ctypes.windll.advapi32
shell32 = ctypes.windll.shell32

TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


advapi32.OpenProcessToken.argtypes = [
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.HANDLE),
]
advapi32.OpenProcessToken.restype = wintypes.BOOL
advapi32.LookupPrivilegeValueW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    ctypes.POINTER(LUID),
]
advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
advapi32.AdjustTokenPrivileges.argtypes = [
    wintypes.HANDLE,
    wintypes.BOOL,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL
shell32.IsUserAnAdmin.restype = wintypes.BOOL
shell32.IsUserAnAdmin.argtypes = []


def enable_debug_privilege() -> bool:
    """Improve OpenProcess success on locked-down PCs when running elevated."""
    try:
        h_token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(),
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            ctypes.byref(h_token),
        ):
            return False
        try:
            luid = LUID()
            if not advapi32.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid)):
                return False
            tp = TOKEN_PRIVILEGES()
            tp.PrivilegeCount = 1
            tp.Privileges[0].Luid = luid
            tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
            return bool(
                advapi32.AdjustTokenPrivileges(
                    h_token, False, ctypes.byref(tp), 0, None, None
                )
            )
        finally:
            kernel32.CloseHandle(h_token)
    except Exception:
        return False


def is_admin() -> bool:
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def windows_supports_exclude_from_capture() -> bool:
    """WDA_EXCLUDEFROMCAPTURE needs Windows 10 2004 (build 19041) or later."""
    v = sys.getwindowsversion()
    return (v.major, v.minor, v.build) >= (10, 0, 19041)


def crash_log_path() -> Path:
    root = Path.home() / "AppData" / "Local" / "ProtectOtherApps"
    root.mkdir(parents=True, exist_ok=True)
    return root / "crash.log"


def show_fatal(title: str, message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        print(title, message)

_AFFINITY_SHELLCODE = bytes(
    [
        0x49, 0x89, 0xCA,
        0x49, 0x8B, 0x02,
        0x49, 0x8B, 0x4A, 0x08,
        0x41, 0x8B, 0x52, 0x10,
        0x48, 0x83, 0xEC, 0x28,
        0xFF, 0xD0,
        0x48, 0x83, 0xC4, 0x28,
        0xC3,
    ]
)


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def protect_list_path() -> Path:
    root = Path.home() / "AppData" / "Local" / "ProtectOtherApps"
    root.mkdir(parents=True, exist_ok=True)
    return root / "protect_list.json"


def load_protect_list() -> list[dict]:
    path = protect_list_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict) and x.get("exe")]
    except (OSError, json.JSONDecodeError):
        pass
    return []


def save_protect_list(items: list[dict]) -> None:
    path = protect_list_path()
    path.write_text(json.dumps(items, indent=2), encoding="utf-8")


def toplevel_hwnd(widget: tk.Misc) -> int:
    widget.update_idletasks()
    hwnd = int(widget.winfo_id())
    parent = user32.GetParent(hwnd)
    return int(parent) if parent else hwnd


def get_exclude_from_capture(hwnd: int) -> bool | None:
    affinity = ctypes.c_uint(0)
    ok = user32.GetWindowDisplayAffinity(wintypes.HWND(hwnd), ctypes.byref(affinity))
    if not ok:
        return None
    return affinity.value == WDA_EXCLUDEFROMCAPTURE


def _set_affinity_direct(hwnd: int, affinity: int) -> bool:
    kernel32.SetLastError(0)
    return bool(user32.SetWindowDisplayAffinity(wintypes.HWND(hwnd), affinity))


def _set_affinity_injected(hwnd: int, pid: int, affinity: int) -> tuple[bool, str]:
    if struct.calcsize("P") != 8:
        return False, "Need 64-bit Python to protect 64-bit apps."

    fn = ctypes.cast(user32.SetWindowDisplayAffinity, ctypes.c_void_p).value
    if not fn:
        return False, "Could not resolve SetWindowDisplayAffinity."

    h_process = kernel32.OpenProcess(PROCESS_INJECT_ACCESS, False, pid)
    if not h_process:
        # Fallback: broader access mask (helps on some Windows editions)
        h_process = kernel32.OpenProcess(0x1F0FFF, False, pid)  # PROCESS_ALL_ACCESS
    if not h_process:
        err = kernel32.GetLastError()
        hint = " Right-click the exe → Run as administrator." if not is_admin() else ""
        return False, f"OpenProcess failed (error {err}).{hint}"

    remote = None
    h_thread = None
    try:
        remote = kernel32.VirtualAllocEx(
            h_process, None, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE
        )
        if not remote:
            return False, f"VirtualAllocEx failed (error {kernel32.GetLastError()})."

        param_addr = remote + 64
        params = struct.pack("<QQII", int(fn), int(hwnd), int(affinity), 0)
        written = ctypes.c_size_t(0)
        if not kernel32.WriteProcessMemory(
            h_process,
            remote,
            _AFFINITY_SHELLCODE,
            len(_AFFINITY_SHELLCODE),
            ctypes.byref(written),
        ):
            return False, f"WriteProcessMemory failed (error {kernel32.GetLastError()})."
        if not kernel32.WriteProcessMemory(
            h_process, param_addr, params, len(params), ctypes.byref(written)
        ):
            return False, f"WriteProcessMemory(params) failed (error {kernel32.GetLastError()})."

        tid = wintypes.DWORD(0)
        h_thread = kernel32.CreateRemoteThread(
            h_process, None, 0, remote, param_addr, 0, ctypes.byref(tid)
        )
        if not h_thread:
            err = kernel32.GetLastError()
            return False, f"CreateRemoteThread failed (error {err})."

        wait = kernel32.WaitForSingleObject(h_thread, 5000)
        if wait != 0:
            return False, "Timed out waiting for protect thread."

        state = get_exclude_from_capture(hwnd)
        want_protected = affinity == WDA_EXCLUDEFROMCAPTURE
        if state is None:
            code = wintypes.DWORD(0)
            kernel32.GetExitCodeThread(h_thread, ctypes.byref(code))
            return bool(code.value), ""
        if bool(state) == want_protected:
            return True, ""
        return False, "API ran but affinity did not stick (layered window?)."
    finally:
        if h_thread:
            kernel32.CloseHandle(h_thread)
        if remote:
            kernel32.VirtualFreeEx(h_process, remote, 0, MEM_RELEASE)
        kernel32.CloseHandle(h_process)


def set_exclude_from_capture(hwnd: int, enabled: bool) -> tuple[bool, str]:
    affinity = WDA_EXCLUDEFROMCAPTURE if enabled else WDA_NONE
    pid = process_id_for_window(hwnd)
    if not pid:
        return False, "Could not resolve process id."

    if pid == int(kernel32.GetCurrentProcessId()):
        ok = _set_affinity_direct(hwnd, affinity)
        return (
            ok,
            "" if ok else f"SetWindowDisplayAffinity failed (error {kernel32.GetLastError()}).",
        )

    return _set_affinity_injected(hwnd, pid, affinity)


def window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(wintypes.HWND(hwnd))
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buf, length + 1)
    return buf.value.strip()


def process_id_for_window(hwnd: int) -> int:
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return int(pid.value)


def process_exe_name(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(260)
        buf = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ""
        return Path(buf.value).name
    finally:
        kernel32.CloseHandle(handle)


def is_top_level_window(hwnd: int) -> bool:
    if not user32.IsWindowVisible(wintypes.HWND(hwnd)):
        return False
    root = user32.GetAncestor(wintypes.HWND(hwnd), GA_ROOT)
    if int(root or 0) != hwnd:
        return False
    ex = user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE)
    if ex & WS_EX_TOOLWINDOW and not (ex & WS_EX_APPWINDOW):
        return False
    return bool(window_title(hwnd))


def enum_top_level_windows() -> list[dict]:
    results: list[dict] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        h = int(hwnd)
        if not is_top_level_window(h):
            return True
        pid = process_id_for_window(h)
        exe = process_exe_name(pid)
        protected = get_exclude_from_capture(h)
        results.append(
            {
                "hwnd": h,
                "title": window_title(h),
                "pid": pid,
                "exe": exe,
                "protected": bool(protected) if protected is not None else False,
            }
        )
        return True

    user32.EnumWindows(callback, 0)
    results.sort(key=lambda w: (not w["protected"], w["title"].lower()))
    return results


def load_tray_image() -> Image.Image:
    for candidate in (resource_path("app.png"), resource_path("app.ico")):
        if candidate.exists():
            return Image.open(candidate).convert("RGBA")
    return Image.new("RGBA", (64, 64), (15, 118, 110, 255))


class ProtectOtherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Protect Other Apps")
        self.geometry("900x560")
        self.minsize(700, 420)
        self.tray_icon: pystray.Icon | None = None
        self._quitting = False
        self._protected: dict[int, str] = {}  # hwnd -> title (live)
        self._protect_list: list[dict] = load_protect_list()  # [{exe, title}]
        self._toggle_mode = "protect"  # protect | unprotect

        icon_file = resource_path("app.ico")
        if icon_file.exists():
            try:
                self.iconbitmap(default=str(icon_file))
            except tk.TclError:
                pass

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        self.after(80, self._start_tray)
        self.after(120, self.refresh_windows)
        self.after(2000, self._maintain_protection)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=(8, 6))
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="Refresh", command=self.refresh_windows).pack(
            side=tk.LEFT, padx=(0, 10)
        )

        self.toggle_btn = tk.Button(
            toolbar,
            text="Protect",
            width=14,
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._toggle_selected,
            state=tk.DISABLED,
            bg=COLOR_DISABLED_BG,
            fg=COLOR_DISABLED_FG,
            activebackground=COLOR_PROTECT_BG,
            activeforeground=COLOR_PROTECT_FG,
            disabledforeground=COLOR_DISABLED_FG,
        )
        self.toggle_btn.pack(side=tk.LEFT)

        hint = ttk.Label(
            self,
            text="Select a window → Protect hides it from screen shares. Protected apps stay on the list and auto-protect when reopened.",
            padding=(10, 0, 10, 6),
            anchor=tk.W,
        )
        hint.pack(fill=tk.X)

        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # --- All windows ---
        left = ttk.Frame(body)
        body.add(left, weight=3)

        ttk.Label(left, text="Open windows", font=("Segoe UI", 9, "bold")).pack(
            anchor=tk.W, pady=(0, 4)
        )

        win_frame = ttk.Frame(left)
        win_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("status", "title", "exe", "pid")
        self.tree = ttk.Treeview(
            win_frame, columns=cols, show="headings", selectmode="browse"
        )
        self.tree.heading("status", text="Status")
        self.tree.heading("title", text="Window title")
        self.tree.heading("exe", text="Process")
        self.tree.heading("pid", text="PID")
        self.tree.column("status", width=90, stretch=False)
        self.tree.column("title", width=280)
        self.tree.column("exe", width=130, stretch=False)
        self.tree.column("pid", width=70, stretch=False)

        scroll = ttk.Scrollbar(win_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_toggle_button())
        self.tree.bind("<Double-1>", lambda _e: self._toggle_selected())

        # --- Protect list ---
        right = ttk.Frame(body)
        body.add(right, weight=2)

        list_header = ttk.Frame(right)
        list_header.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(list_header, text="Protect list", font=("Segoe UI", 9, "bold")).pack(
            side=tk.LEFT
        )
        ttk.Button(list_header, text="Remove", command=self._remove_from_list).pack(
            side=tk.RIGHT
        )

        list_frame = ttk.Frame(right)
        list_frame.pack(fill=tk.BOTH, expand=True)

        list_cols = ("exe", "title")
        self.list_tree = ttk.Treeview(
            list_frame, columns=list_cols, show="headings", selectmode="browse"
        )
        self.list_tree.heading("exe", text="Process")
        self.list_tree.heading("title", text="Last title")
        self.list_tree.column("exe", width=140, stretch=False)
        self.list_tree.column("title", width=180)
        list_scroll = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.list_tree.yview
        )
        self.list_tree.configure(yscrollcommand=list_scroll.set)
        self.list_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status = ttk.Label(self, text="Ready.", padding=(10, 6), anchor=tk.W)
        self.status.pack(fill=tk.X)

        self.bind("<F5>", lambda _e: self.refresh_windows())
        self.bind("<Escape>", lambda _e: self._hide_to_tray())

        self._refresh_protect_list_ui()

    def _exe_in_protect_list(self, exe: str) -> bool:
        key = exe.lower()
        return any(item.get("exe", "").lower() == key for item in self._protect_list)

    def _add_to_protect_list(self, exe: str, title: str) -> None:
        if not exe:
            return
        key = exe.lower()
        for item in self._protect_list:
            if item.get("exe", "").lower() == key:
                item["title"] = title or item.get("title", "")
                save_protect_list(self._protect_list)
                self._refresh_protect_list_ui()
                return
        self._protect_list.append({"exe": exe, "title": title})
        save_protect_list(self._protect_list)
        self._refresh_protect_list_ui()

    def _remove_exe_from_protect_list(self, exe: str) -> None:
        key = exe.lower()
        self._protect_list = [
            item for item in self._protect_list if item.get("exe", "").lower() != key
        ]
        save_protect_list(self._protect_list)
        self._refresh_protect_list_ui()

    def _refresh_protect_list_ui(self) -> None:
        self.list_tree.delete(*self.list_tree.get_children())
        for item in sorted(self._protect_list, key=lambda x: x.get("exe", "").lower()):
            self.list_tree.insert(
                "",
                tk.END,
                values=(item.get("exe", ""), item.get("title", "")),
            )

    def _remove_from_list(self) -> None:
        sel = self.list_tree.selection()
        if not sel:
            messagebox.showinfo("Protect list", "Select an app in the protect list.")
            return
        vals = self.list_tree.item(sel[0], "values")
        if not vals:
            return
        exe = str(vals[0])
        # Unprotect any running windows for this exe
        for win in enum_top_level_windows():
            if win["exe"].lower() == exe.lower():
                set_exclude_from_capture(win["hwnd"], False)
                self._protected.pop(win["hwnd"], None)
        self._remove_exe_from_protect_list(exe)
        self.refresh_windows()
        self.status.configure(text=f"Removed {exe} from protect list.")

    def _selected_row(self) -> dict | None:
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        if not vals or len(vals) < 4:
            return None
        # hwnd stored in tags
        tags = self.tree.item(sel[0], "tags")
        hwnd = None
        for t in tags:
            if t.startswith("hwnd:"):
                try:
                    hwnd = int(t.split(":", 1)[1])
                except ValueError:
                    pass
        if hwnd is None:
            return None
        return {
            "status": str(vals[0]),
            "title": str(vals[1]),
            "exe": str(vals[2]),
            "pid": str(vals[3]),
            "hwnd": hwnd,
            "protected": str(vals[0]).lower() == "protected",
        }

    def _update_toggle_button(self) -> None:
        row = self._selected_row()
        if not row:
            self._toggle_mode = "protect"
            self.toggle_btn.configure(
                text="Protect",
                state=tk.DISABLED,
                bg=COLOR_DISABLED_BG,
                fg=COLOR_DISABLED_FG,
                activebackground=COLOR_DISABLED_BG,
                activeforeground=COLOR_DISABLED_FG,
            )
            return

        if row["protected"] or row["hwnd"] in self._protected:
            self._toggle_mode = "unprotect"
            self.toggle_btn.configure(
                text="Unprotect",
                state=tk.NORMAL,
                bg=COLOR_UNPROTECT_BG,
                fg=COLOR_UNPROTECT_FG,
                activebackground="#d1d5db",
                activeforeground=COLOR_UNPROTECT_FG,
            )
        else:
            self._toggle_mode = "protect"
            self.toggle_btn.configure(
                text="Protect",
                state=tk.NORMAL,
                bg=COLOR_PROTECT_BG,
                fg=COLOR_PROTECT_FG,
                activebackground="#1d4ed8",
                activeforeground=COLOR_PROTECT_FG,
            )

    def refresh_windows(self) -> None:
        selected_hwnd = None
        row = self._selected_row()
        if row:
            selected_hwnd = row["hwnd"]

        self.tree.delete(*self.tree.get_children())
        windows = enum_top_level_windows()
        own = toplevel_hwnd(self)
        reselect = None
        for win in windows:
            if win["hwnd"] == own:
                continue
            if win["hwnd"] in self._protected or self._exe_in_protect_list(win["exe"]):
                # Prefer live affinity when readable
                if win["hwnd"] in self._protected:
                    win["protected"] = True
            status = "Protected" if win["protected"] else "Visible"
            tags = [f"hwnd:{win['hwnd']}"]
            if win["protected"]:
                tags.append("protected")
            item = self.tree.insert(
                "",
                tk.END,
                values=(status, win["title"], win["exe"], win["pid"]),
                tags=tuple(tags),
            )
            if win["hwnd"] == selected_hwnd:
                reselect = item

        self.tree.tag_configure("protected", foreground="#0f766e")
        if reselect:
            self.tree.selection_set(reselect)
            self.tree.see(reselect)

        self._update_toggle_button()
        n = len(self._protect_list)
        live = sum(1 for w in windows if w["protected"] or w["hwnd"] in self._protected)
        self.status.configure(
            text=f"{len(windows)} windows · {live} protected now · {n} on protect list. F5 refresh · Esc → tray."
        )

    def _toggle_selected(self) -> None:
        row = self._selected_row()
        if not row:
            messagebox.showinfo("Protect", "Select a window in the list first.")
            return

        hwnd = row["hwnd"]
        title = row["title"]
        exe = row["exe"]
        want_protect = self._toggle_mode == "protect"

        ok, err = set_exclude_from_capture(hwnd, want_protect)
        if not ok:
            self.status.configure(text=f"Failed. {err}")
            return

        if want_protect:
            self._protected[hwnd] = title
            self._add_to_protect_list(exe, title)
            self.status.configure(text=f"Protected {title or exe} — added to protect list.")
        else:
            self._protected.pop(hwnd, None)
            self._remove_exe_from_protect_list(exe)
            self.status.configure(text=f"Unprotected {title or exe} — removed from protect list.")

        self.refresh_windows()

    def _maintain_protection(self) -> None:
        if self._quitting:
            return

        # Drop dead hwnds
        dead = [h for h in self._protected if not user32.IsWindow(wintypes.HWND(h))]
        for h in dead:
            self._protected.pop(h, None)

        # Re-apply for protect-list exes + tracked hwnds
        own = toplevel_hwnd(self)
        list_exes = {item.get("exe", "").lower() for item in self._protect_list}

        for win in enum_top_level_windows():
            if win["hwnd"] == own:
                continue
            should = win["hwnd"] in self._protected or win["exe"].lower() in list_exes
            if not should:
                continue
            state = get_exclude_from_capture(win["hwnd"])
            if state is True:
                self._protected[win["hwnd"]] = win["title"]
                continue
            ok, _err = set_exclude_from_capture(win["hwnd"], True)
            if ok:
                self._protected[win["hwnd"]] = win["title"]

        self.after(4000, self._maintain_protection)

    def _start_tray(self) -> None:
        image = load_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Show", self._tray_show, default=True),
            pystray.MenuItem("Refresh", self._tray_refresh),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._tray_quit),
        )
        self.tray_icon = pystray.Icon(
            "ProtectOtherApps", image, "Protect Other Apps", menu
        )
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_show(self, icon=None, item=None) -> None:
        self.after(0, self._show_window)

    def _tray_refresh(self, icon=None, item=None) -> None:
        self.after(0, self.refresh_windows)

    def _tray_quit(self, icon=None, item=None) -> None:
        self.after(0, self._quit_app)

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self.refresh_windows()

    def _hide_to_tray(self) -> None:
        if self._quitting:
            return
        self.withdraw()

    def _quit_app(self) -> None:
        self._quitting = True
        # Keep protect list; clear live affinity so apps aren't stuck protected after quit
        for hwnd in list(self._protected):
            if user32.IsWindow(wintypes.HWND(hwnd)):
                set_exclude_from_capture(hwnd, False)
        self._protected.clear()
        if self.tray_icon is not None:
            self.tray_icon.stop()
        self.destroy()


def main() -> None:
    if sys.platform != "win32":
        show_fatal("Protect Other Apps", "This app requires Windows 10/11 (64-bit).")
        sys.exit(1)

    if struct.calcsize("P") != 8:
        show_fatal(
            "Protect Other Apps",
            "This build is not 64-bit. Use the 64-bit ProtectOtherApps.exe on 64-bit Windows.",
        )
        sys.exit(1)

    if not windows_supports_exclude_from_capture():
        show_fatal(
            "Protect Other Apps",
            "Screen-share hiding needs Windows 10 version 2004 (build 19041) or newer, or Windows 11.",
        )
        sys.exit(1)

    enable_debug_privilege()
    app = ProtectOtherApp()
    if not is_admin():
        app.after(
            400,
            lambda: app.status.configure(
                text="Tip: for best results on other PCs, run as Administrator (right-click the exe)."
            ),
        )
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log = crash_log_path()
        log.write_text(traceback.format_exc(), encoding="utf-8")
        show_fatal(
            "Protect Other Apps — crashed",
            f"The app failed to start.\n\nDetails saved to:\n{log}\n\n"
            "If Windows Defender blocked it, allow the exe under Protection history.",
        )
        sys.exit(1)
