@echo off
cd /d "%~dp0"
title Zaply Site - Guncelle
if not exist ".venv\Scripts\python.exe" (
  echo Once Siteyi_Ac.bat ile kurulumu yap.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m saas.guncelle
".venv\Scripts\python.exe" -m pip install -q -r saas\requirements.txt
echo.
echo Bitti. Siteyi acmak icin Siteyi_Ac.bat
pause
