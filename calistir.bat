@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
call .venv\Scripts\activate.bat
echo ===== %date% %time% ===== >> kayit.txt
python -m shitpost uret spoderman >> kayit.txt 2>&1
