@echo off
rem Build a self-contained VortexServer folder for the counter PC.
rem Needs:  pip install pyinstaller
rem Notes:
rem  Do NOT use --collect-all fastapi/starlette/pydantic: fastapi.cli drags in typer -> rich ->
rem  IPython -> matplotlib/numpy/scipy/torch (gigabytes). Plain imports are found by PyInstaller;
rem  only uvicorn/websockets/anyio load submodules dynamically and need collecting.
rem  Verify the package with:  python tools\smoke_test.py
cd /d "%~dp0"
pyinstaller --noconfirm --clean --name VortexServer ^
  --add-data "admin;admin" ^
  --add-data "vortex_server/seed_media;vortex_server/seed_media" ^
  --collect-all uvicorn --collect-all websockets --collect-submodules anyio ^
  --hidden-import fastapi --hidden-import starlette --hidden-import pydantic ^
  --exclude-module fastapi.cli --exclude-module fastapi_cli --exclude-module typer --exclude-module rich ^
  --exclude-module IPython --exclude-module matplotlib --exclude-module numpy --exclude-module scipy ^
  --exclude-module pandas --exclude-module torch --exclude-module PIL --exclude-module PySide6 ^
  --exclude-module tkinter --exclude-module pygments --exclude-module httpx --exclude-module trio ^
  run_server.py
if errorlevel 1 (echo BUILD FAILED & pause & exit /b 1)
rem the deploy kit (firewall / autostart / check scripts + README) ships next to the exe
copy /y deploy\*.bat dist\VortexServer\ >nul
copy /y deploy\README-DEPLOY.txt dist\VortexServer\ >nul
echo.
echo Built: dist\VortexServer\   (copy the whole folder to the server PC; data\ is created on first run)
if /i not "%~1"=="nopause" pause
