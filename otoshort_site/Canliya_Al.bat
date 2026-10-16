@echo off
cd /d "%~dp0"
title Zaply - Canli (vitrin)
echo ============================================
echo  ZAPLY - HERKESE ACIK DEMO YAYINI
echo ============================================
echo Site bu bilgisayardan https://....trycloudflare.com adresiyle yayinlanir.
echo Videolar sahtedir (para harcanmaz), odeme ve yonetim paneli kapalidir.
echo Bu pencereyi kapatinca yayin biter. Her acilista adres degisir.
echo.
if not exist ".venv\Scripts\python.exe" (
  where python >nul 2>nul
  if errorlevel 1 goto nopython
  echo Ilk kurulum yapiliyor, 1-2 dakika surebilir...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r saas\requirements.txt
".venv\Scripts\python.exe" -m saas.canli
pause
exit /b 0

:nopython
echo Python bulunamadi. python.org adresinden kur, kurarken "Add python.exe to PATH" kutusunu isaretle.
pause
exit /b 1
