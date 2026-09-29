@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
call .venv\Scripts\activate.bat
echo ===== TEST %date% %time% ===== >> kayit.txt
python -m shitpost uret spoderman --kuru >> kayit.txt 2>&1
