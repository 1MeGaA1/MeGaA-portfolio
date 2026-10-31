@echo off
rem  Stop the running Vortex server (the startup task will NOT restart it until the
rem  next boot or until you run start_server.bat). Run as Administrator.
net session >nul 2>&1 || (echo Please run this file as Administrator. & pause & exit /b 1)
schtasks /end /tn "Vortex Server" >nul 2>&1
taskkill /f /im VortexServer.exe >nul 2>&1 && echo Vortex server stopped. || echo Vortex server was not running.
pause
