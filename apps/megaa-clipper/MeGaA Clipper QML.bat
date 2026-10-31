@echo off
rem Opens MeGaA Clipper (QML edition). Drag a video onto this file to open it straight away.
cd /d "%~dp0"
start "" pythonw "%~dp0clipper_qml.py" %*
