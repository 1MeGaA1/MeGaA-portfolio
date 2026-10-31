@echo off
rem Watchdog for the packaged client (copied into dist\VortexClient by build_client.bat).
cd /d "%~dp0"
:loop
VortexClient.exe
if %errorlevel%==0 goto end
timeout /t 2 /nobreak >nul
goto loop
:end
