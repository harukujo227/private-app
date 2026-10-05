@echo off
cd /d "%~dp0"
python create_icon.py
python -m PyInstaller --noconfirm --onefile --windowed --name PrivateNotes --icon app.ico --add-data "app.png;." --add-data "app.ico;." main.py
echo.
echo Built: dist\PrivateNotes.exe
pause
