@echo off
rem Build a self-contained VortexClientNative folder (no Python needed on the gaming PCs).
rem Needs:  pip install pyinstaller
rem Notes:
rem  --collect-all PySide6 is REQUIRED: PyInstaller does not scan .qml files, so without it the
rem  QtQuick QML modules are missing and the app crashes on start. prune_dist.py then strips the
rem  unused Qt bits (WebEngine/Quick3D/docs/...) to get the folder from ~670 MB down to ~335 MB.
rem  --paths ..\client bundles the shared vortex_client backend.
cd /d "%~dp0"
pyinstaller --noconfirm --clean --name VortexClientNative --windowed ^
  --paths "..\client" ^
  --collect-all PySide6 ^
  --add-data "qml;qml" --add-data "fonts;fonts" --add-data "catalog.json;." ^
  --hidden-import websockets --hidden-import psutil ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineQuick ^
  --exclude-module PySide6.QtQuick3D --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtPdf ^
  --exclude-module PySide6.QtCharts --exclude-module PySide6.QtDataVisualization ^
  run_native.py
if errorlevel 1 (echo BUILD FAILED & pause & exit /b 1)
python tools\prune_dist.py
copy /y run_native_dist.bat dist\VortexClientNative\run_native.bat >nul 2>&1
echo.
echo Built: dist\VortexClientNative\   (copy to each PC, then edit client.json)
pause
