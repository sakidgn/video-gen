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
echo ===============================================
set /p secim=Secimin (1-6):
if "%secim%"=="1" python -m shitpost giris C:\BotProfil1
if "%secim%"=="2" python -m shitpost giris C:\BotProfil2 --sadece-gemini
if "%secim%"=="3" python -m shitpost youtube-yetki spoderman
if "%secim%"=="4" python -m shitpost uret spoderman --kuru
if "%secim%"=="5" python -m shitpost uret spoderman
if "%secim%"=="6" exit /b 0
goto menu
