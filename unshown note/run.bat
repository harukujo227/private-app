@echo off
cd /d "%~dp0"
if exist "dist\PrivateNotes.exe" (
  start "" "dist\PrivateNotes.exe"
) else (
  pythonw main.py 2>nul
  if errorlevel 1 python main.py
)
