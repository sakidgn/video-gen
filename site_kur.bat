@echo off
cd /d "%~dp0"
title Siteyi ayri klasore kur
echo Site (Cutless) Masaustunde ayri bir klasore kuruluyor...
call .venv\Scripts\activate.bat
python -m shitpost site-kur
echo.
echo Artik siteyi Masaustundeki "Cutless Site" klasorunden ac: Siteyi_Ac.bat
pause
