@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/entorno.ps1
if errorlevel 1 pause
