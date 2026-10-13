@echo off
cd /d "%~dp0"
title Site denemesi
echo ============================================
echo  SITE DENEMESI (sahte videolarla, ucretsiz)
echo ============================================
if not exist ".venv\Scripts\python.exe" (
  echo Once kurulum.bat calistir.
  pause
  exit /b 1
)
echo Gerekli paketler kuruluyor (ilk seferde 1-2 dakika)...
".venv\Scripts\python.exe" -m pip install -q -r saas\requirements.txt
set SAHTE_AI=1
set ADMIN_EPOSTALAR=admin@deneme.com
set KAYIT_HEDIYE_KREDI=1000
set VERI_KLASORU=%~dp0saas_veri_deneme
set PORT=8000
echo.
echo Site aciliyor: http://localhost:8000
echo Kayit olurken admin@deneme.com yazarsan Yonetim paneli de acilir.
echo Her yeni hesaba deneme icin 1000 kredi verilir. Videolar sahtedir (renkli test goruntusu).
echo Kapatmak icin bu pencereyi kapat.
echo.
start "" http://localhost:8000
".venv\Scripts\python.exe" -m saas
pause
