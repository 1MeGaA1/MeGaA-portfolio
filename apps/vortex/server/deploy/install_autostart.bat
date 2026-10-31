@echo off
rem ============================================================
rem  Make the Vortex server start with Windows (before anyone logs in) and keep
rem  running in the background. Uses the built-in Task Scheduler - no extra
rem  software. Run once, as Administrator. Safe to run again (replaces the task).
rem ============================================================
net session >nul 2>&1 || (echo Please run this file as Administrator. & pause & exit /b 1)
cd /d "%~dp0"
set "TASK=Vortex Server"
set "CMD=\"%~dp0serve_forever.bat\""

schtasks /delete /tn "%TASK%" /f >nul 2>&1
schtasks /create /tn "%TASK%" /tr "%CMD%" /sc onstart /ru SYSTEM /rl highest /f
if errorlevel 1 (echo FAILED to create the scheduled task. & pause & exit /b 1)

echo.
echo Task "%TASK%" created: starts at every boot as SYSTEM, from
echo   %~dp0
echo Starting it now...
schtasks /run /tn "%TASK%" >nul
ping -n 7 127.0.0.1 >nul
call "%~dp0check_server.bat" quiet
echo.
echo Done. Data (database, pictures, server.log) lives in: %~dp0data\
pause
