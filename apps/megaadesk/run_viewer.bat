@echo off
rem MeGaADesk - open the QML viewer (needs: pip install PySide6)
cd /d "%~dp0"
python viewer_qml.py %*
if errorlevel 1 pause
