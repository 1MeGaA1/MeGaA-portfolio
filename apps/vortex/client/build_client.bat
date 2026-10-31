@echo off
rem Build a self-contained VortexClient folder (no Python needed on the gaming PCs).
rem Needs:  pip install pyinstaller
cd /d "%~dp0"
pyinstaller --noconfirm --clean --name VortexClient --windowed ^
  --add-data "ui;ui" ^
  --collect-data webview --hidden-import webview.platforms.edgechromium --hidden-import webview.platforms.winforms ^
  --hidden-import clr --hidden-import websockets --hidden-import psutil ^
  --exclude-module PySide6 --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module qtpy ^
  --exclude-module gi --exclude-module tkinter --exclude-module webview.platforms.qt --exclude-module webview.platforms.gtk ^
  run_client.py
if errorlevel 1 (echo BUILD FAILED & pause & exit /b 1)
copy /y run_client_dist.bat dist\VortexClient\run_client.bat >nul
xcopy /e /i /y tools dist\VortexClient\tools >nul
echo.
echo Built: dist\VortexClient\   (copy that folder to each gaming PC, then edit client.json)
pause
