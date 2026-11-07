@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/entorno.ps1 -Original
if errorlevel 1 pause
