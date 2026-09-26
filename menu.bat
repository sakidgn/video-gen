@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
call .venv\Scripts\activate.bat
:menu
echo.
echo ================ SHITPOST MENU ================
echo  1) Giris yap: 1. Gemini hesabi + TikTok + Instagram
echo  2) Giris yap: 2. Gemini hesabi
echo  3) YouTube kanalini bagla
echo  4) Test videosu uret (paylasmaz)
echo  5) Video uret ve paylas
echo  6) Cikis
echo  7) Guncelle
echo  8) Hata raporunu ac (son denemenin kaydi ve resimleri)
echo ===============================================
set /p secim=Secimin (1-7):
if "%secim%"=="1" python -m shitpost giris C:\BotProfil1
if "%secim%"=="2" python -m shitpost giris C:\BotProfil2 --sadece-gemini
if "%secim%"=="3" python -m shitpost youtube-yetki spoderman
if "%secim%"=="4" python -m shitpost uret spoderman --kuru
if "%secim%"=="5" python -m shitpost uret spoderman
if "%secim%"=="6" exit /b 0
if "%secim%"=="8" python -m shitpost rapor
if "%secim%"=="7" (
  python -m shitpost guncelle
  pip install -q -r requirements.txt
  echo.
  echo Bitti. Bu pencereyi kapatip menu.bat'i tekrar ac.
  pause
  exit /b 0
)
goto menu
