@echo off
cd /d "%~dp0"
title Siteyi ayri klasore kur
echo Site (Zaply) Masaustunde ayri bir klasore kuruluyor...
call .venv\Scripts\activate.bat
python -m shitpost site-kur
echo.
echo Artik siteyi Masaustundeki "Zaply Site" klasorunden (eski kurulumda "Cutless Site") ac: Siteyi_Ac.bat
pause
