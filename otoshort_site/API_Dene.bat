@echo off
cd /d "%~dp0"
title Zaply - API denemesi
echo ============================================
echo  ZAPLY - GERCEK API DENEMESI
echo ============================================
echo Bu arac .env dosyasindaki anahtarlarla GERCEK video uretir (ucretli).
echo Once sadece anahtari ve senaryoyu dener, video icin onay sorar.
echo.
if not exist ".env" (
  echo .env dosyasi yok. .env.ornek dosyasini .env adiyla kopyalayip GEMINI_API_KEY satirini doldur.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  where python >nul 2>nul
  if errorlevel 1 goto nopython
  echo Ilk kurulum yapiliyor, 1-2 dakika surebilir...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r saas\requirements.txt
set SAHTE_AI=0
set VERI_KLASORU=%~dp0saas_veri_deneme
echo Hangi kalite denensin?
echo   1 = Ekonomik (en ucuz)    2 = Standart    3 = Premium    4 = Hepsi    5 = Sadece anahtar/senaryo (videosuz)
set /p SECIM="Secimin (1-5): "
set KALITE=lite
if "%SECIM%"=="2" set KALITE=fast
if "%SECIM%"=="3" set KALITE=standard
if "%SECIM%"=="4" set KALITE=hepsi
if "%SECIM%"=="5" (
  ".venv\Scripts\python.exe" -m saas.api_dene --sadece-metin
) else (
  ".venv\Scripts\python.exe" -m saas.api_dene --kalite %KALITE%
)
echo.
echo Videolar: saas_veri_deneme\api_deneme klasorunde.
pause
exit /b 0

:nopython
echo Python bulunamadi. python.org adresinden kur, kurarken "Add python.exe to PATH" kutusunu isaretle.
pause
exit /b 1
