@echo off
cd /d "%~dp0"
title Otoshort Site
echo ============================================
echo  OTOSHORT SITE - deneme modu (sahte videolar)
echo ============================================
if not exist ".venv\Scripts\python.exe" (
  where python >nul 2>nul
  if errorlevel 1 goto nopython
  echo Ilk kurulum yapiliyor, 1-2 dakika surebilir...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r saas\requirements.txt
set SAHTE_AI=1
set ADMIN_EPOSTALAR=admin@deneme.com
set KAYIT_HEDIYE_KREDI=1000
set VERI_KLASORU=%~dp0saas_veri_deneme
set PORT=8000
echo.
echo Site aciliyor: http://localhost:8000
echo Telefondan bakmak icin (ayni Wi-Fi):
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { '   http://' + $_.IPAddress + ':8000' }"
echo Kayit olurken admin@deneme.com yazarsan Yonetim paneli de acilir.
echo Her yeni hesaba deneme icin 1000 kredi verilir. Videolar sahtedir.
echo Kapatmak icin bu pencereyi kapat.
echo.
start "" http://localhost:8000
".venv\Scripts\python.exe" -m saas
pause
exit /b 0

:nopython
echo Python bulunamadi. python.org adresinden kur, kurarken "Add python.exe to PATH" kutusunu isaretle.
pause
exit /b 1
