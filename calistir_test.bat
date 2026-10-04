@echo off
cd /d "%~dp0"
echo ===== TEST %date% %time% ===== >> kayit.txt
set PYTHONIOENCODING=utf-8
if not exist ".venv\Scripts\python.exe" (
  echo HATA: .venv bulunamadi, kurulum.bat calistir. >> kayit.txt
  exit /b 1
)
".venv\Scripts\python.exe" -m shitpost uret spoderman --kuru --uyut >> kayit.txt 2>&1
echo ----- bitti, kod %errorlevel% ----- >> kayit.txt
