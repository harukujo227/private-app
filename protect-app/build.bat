@echo off
cd /d "%~dp0"
echo Installing build dependencies...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo Failed to install requirements.
  pause
  exit /b 1
)

echo Building portable 64-bit exe (no UPX, requests Administrator)...
python -m PyInstaller --noconfirm ProtectOtherApps.spec
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo OK: dist\ProtectOtherApps.exe
echo Copy that single file to any Windows 10/11 64-bit PC.
echo First run: allow UAC / Defender if prompted, then Protect an app.
echo.
pause
