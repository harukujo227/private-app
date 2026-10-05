# Caption

Windows tools that hide windows from screen capture and screen sharing (Zoom, Meet, Teams, Chrome tab/screen share, etc.) using `SetWindowDisplayAffinity` / `WDA_EXCLUDEFROMCAPTURE`.

Requires **Windows 10 version 2004+** (build 19041) or **Windows 11**, **64-bit**.

## Apps

### Private Notes (`unshown note/`)

A tray notepad that stays off the taskbar and can be excluded from screen shares.

- Starts in the system tray (no taskbar button)
- **Hide from screen share** toggle (on by default)
- Always-on-top option
- New / Open / Save (`Ctrl+N` / `Ctrl+O` / `Ctrl+S`); Esc hides to tray

**Run from source**

```bat
cd "unshown note"
run.bat
```

**Build portable exe**

```bat
cd "unshown note"
build.bat
```

Output: `unshown note\dist\PrivateNotes.exe`

### Protect Other Apps (`protect-app/`)

Pick any open window and hide it from screen shares. Protected apps are remembered and re-protected when they reopen.

- Lists open top-level windows
- Protect / Unprotect selected window
- Persistent protect list (`%LOCALAPPDATA%\ProtectOtherApps\protect_list.json`)
- System tray (close window → tray; Quit from tray to exit)
- Prefer **Run as administrator** for best results on other processes

**Run from source**

```bat
cd protect-app
run.bat
```

**Build portable exe**

```bat
cd protect-app
build.bat
```

Output: `protect-app\dist\ProtectOtherApps.exe`

## Screen share test

Open `test-share.html` in Chrome (or Edge), start a screen share of the entire screen, and confirm protected windows are missing or blacked out in the preview.

## Requirements

Python 3 with:

- `pystray`
- `Pillow`
- `pyinstaller` (build only)

Install via each app’s `requirements.txt` (the `run.bat` / `build.bat` scripts do this).

## Notes

- Exclusion applies to capture APIs that honor window display affinity. Behavior can vary by app and share mode (entire screen vs window).
- If Windows Defender blocks a built exe, allow it under Protection history.
- Crash logs for Protect Other Apps: `%LOCALAPPDATA%\ProtectOtherApps\crash.log`
